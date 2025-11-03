#!/usr/bin/env python3
# coding: utf-8
"""
统一状态管理器

设计原则：
1. schedule_master.json 为单一数据源（Single Source of Truth）
2. 所有状态查询和更新通过本模块进行
3. 原子性写入（临时文件 → 重命名）
4. 失败时自动回滚

状态定义：
- "pending": 待制作（初始状态）
- "remixing": 混音中
- "rendering": 渲染中（视频生成中）
- "uploading": 上传中
- "completed": 已完成
- "error": 错误（需要人工介入）
"""
from __future__ import annotations

import json
import shutil
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class StateConflictError(Exception):
    """状态冲突错误（并发更新同一期数）"""
    pass

# 状态定义
STATUS_PENDING = "pending"
STATUS_REMIXING = "remixing"
STATUS_RENDERING = "rendering"
STATUS_UPLOADING = "uploading"
STATUS_COMPLETED = "completed"
STATUS_ERROR = "error"

VALID_STATUSES = {
    STATUS_PENDING,
    STATUS_REMIXING,
    STATUS_RENDERING,
    STATUS_UPLOADING,
    STATUS_COMPLETED,
    STATUS_ERROR,
}

# 状态转换规则（当前状态 → 允许的下一个状态）
STATE_TRANSITIONS = {
    STATUS_PENDING: {STATUS_REMIXING, STATUS_ERROR},
    STATUS_REMIXING: {STATUS_RENDERING, STATUS_ERROR},
    STATUS_RENDERING: {STATUS_UPLOADING, STATUS_COMPLETED, STATUS_ERROR},
    STATUS_UPLOADING: {STATUS_COMPLETED, STATUS_ERROR},
    STATUS_COMPLETED: set(),  # 终态
    STATUS_ERROR: {STATUS_PENDING, STATUS_REMIXING},  # 可从错误恢复
}


class StateLock:
    """状态锁（防止并发更新同一期数）"""
    
    def __init__(self):
        self._locks: Dict[str, threading.Lock] = {}
        self._lock_mutex = threading.Lock()
    
    @contextmanager
    def acquire(self, episode_id: str):
        """
        获取期数锁（上下文管理器）
        
        Args:
            episode_id: 期数ID
        
        Yields:
            锁对象
        """
        # 获取或创建锁
        with self._lock_mutex:
            if episode_id not in self._locks:
                self._locks[episode_id] = threading.Lock()
            lock = self._locks[episode_id]
        
        # 尝试获取锁（带超时）
        acquired = lock.acquire(timeout=30.0)
        if not acquired:
            raise StateConflictError(
                f"无法获取期数 {episode_id} 的锁（可能被其他进程占用）"
            )
        
        try:
            yield lock
        finally:
            lock.release()


class StateManager:
    """
    统一状态管理器
    
    以 schedule_master.json 为单一数据源，提供统一的状态查询和更新接口
    
    特性：
    - 原子性写入（临时文件 → 重命名）
    - 并发控制（防止同时更新同一期数）
    - 缓存机制（减少文件IO）
    """
    
    def __init__(self, schedule_path: Optional[Path] = None):
        """
        初始化状态管理器
        
        Args:
            schedule_path: 排播表文件路径（默认：config/schedule_master.json）
        """
        if schedule_path is None:
            repo_root = Path(__file__).resolve().parent.parent.parent
            schedule_path = repo_root / "config" / "schedule_master.json"
        self.schedule_path = schedule_path
        self._cache: Optional[Dict] = None
        self._cache_mtime: Optional[float] = 0.0
        self._lock = StateLock()
        self._file_mutex = threading.Lock()  # 文件写入互斥锁
    
    def _load(self, force: bool = False) -> Optional[Dict]:
        """
        加载排播表（带缓存）
        
        Args:
            force: 强制重新加载（忽略缓存）
        
        Returns:
            排播表数据字典，如果文件不存在返回None
        """
        if not self.schedule_path.exists():
            return None
        
        # 检查缓存有效性
        current_mtime = self.schedule_path.stat().st_mtime
        if not force and self._cache is not None and current_mtime == self._cache_mtime:
            return self._cache
        
        # 加载文件
        with self.schedule_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        self._cache = data
        self._cache_mtime = current_mtime
        return data
    
    @contextmanager
    def _atomic_write(self, path: Path):
        """
        原子性写入上下文管理器
        
        Args:
            path: 目标文件路径
        
        Yields:
            临时文件路径
        """
        # 确保目录存在
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # 生成临时文件路径
        temp_path = path.with_suffix(path.suffix + ".tmp")
        
        try:
            yield temp_path
            # 原子性重命名
            temp_path.replace(path)
        except Exception:
            # 如果出错，删除临时文件
            if temp_path.exists():
                temp_path.unlink()
            raise
    
    def _save(self, data: Dict) -> bool:
        """
        原子性保存排播表（线程安全）
        
        Args:
            data: 要保存的数据
        
        Returns:
            是否成功保存
        """
        # 使用文件互斥锁防止并发写入
        with self._file_mutex:
            try:
                with self._atomic_write(self.schedule_path) as temp_path:
                    with temp_path.open("w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                
                # 更新缓存
                self._cache = data
                if self.schedule_path.exists():
                    self._cache_mtime = self.schedule_path.stat().st_mtime
                
                return True
            except Exception as e:
                print(f"❌ 保存排播表失败: {e}")
                return False
    
    def get_episode(self, episode_id: str) -> Optional[Dict]:
        """
        获取期数记录
        
        Args:
            episode_id: 期数ID（YYYYMMDD格式）
        
        Returns:
            期数记录字典，如果不存在返回None
        """
        schedule = self._load()
        if not schedule:
            return None
        
        for ep in schedule.get("episodes", []):
            if ep.get("episode_id") == episode_id:
                return ep
        return None
    
    def get_episode_status(self, episode_id: str) -> str:
        """
        获取期数状态
        
        Args:
            episode_id: 期数ID
        
        Returns:
            状态字符串（默认：pending）
        """
        ep = self.get_episode(episode_id)
        if not ep:
            return STATUS_PENDING
        
        status = ep.get("status", STATUS_PENDING)
        return status if status in VALID_STATUSES else STATUS_PENDING
    
    def update_status(
        self,
        episode_id: str,
        new_status: str,
        message: Optional[str] = None,
        error_details: Optional[str] = None
    ) -> bool:
        """
        更新期数状态（带状态转换验证和并发控制）
        
        Args:
            episode_id: 期数ID
            new_status: 新状态
            message: 可选的状态消息
            error_details: 错误详情（仅在status="error"时使用）
        
        Returns:
            是否成功更新
        
        Raises:
            StateConflictError: 如果无法获取锁（并发冲突）
        """
        if new_status not in VALID_STATUSES:
            print(f"❌ 无效状态: {new_status}")
            return False
        
        # 使用锁防止并发更新
        with self._lock.acquire(episode_id):
            schedule = self._load(force=True)  # 强制重新加载，确保获取最新状态
            if not schedule:
                print("❌ 排播表不存在")
                return False
            
            ep = self.get_episode(episode_id)
            if not ep:
                print(f"❌ 期数不存在: {episode_id}")
                return False
            
            # 验证状态转换
            current_status = ep.get("status", STATUS_PENDING)
            if current_status in STATE_TRANSITIONS:
                allowed_next = STATE_TRANSITIONS[current_status]
                if new_status not in allowed_next and current_status != new_status:
                    print(f"❌ 无效状态转换: {current_status} → {new_status}")
                    print(f"   允许的下一个状态: {allowed_next}")
                    return False
            
            # 更新状态
            ep["status"] = new_status
            ep["status_updated_at"] = datetime.now().isoformat()
            
            # 添加状态消息
            if message:
                ep["status_message"] = message
            
            # 添加错误详情
            if new_status == STATUS_ERROR and error_details:
                ep["error_details"] = error_details
                ep["error_occurred_at"] = datetime.now().isoformat()
            elif new_status != STATUS_ERROR:
                # 清除错误信息（如果从错误恢复）
                ep.pop("error_details", None)
                ep.pop("error_occurred_at", None)
        
            # 记录指标（如果是错误状态）
            if new_status == STATUS_ERROR:
                try:
                    from metrics_manager import get_metrics_manager
                    metrics_manager = get_metrics_manager()
                    metrics_manager.record_event(
                        stage="state_update",
                        status="failed",
                        episode_id=episode_id,
                        error_message=error_details
                    )
                except ImportError:
                    pass
            
            return self._save(schedule)
    
    def rollback_status(self, episode_id: str, target_status: str = STATUS_PENDING) -> bool:
        """
        回滚期数状态（失败时调用，带并发控制）
        
        Args:
            episode_id: 期数ID
            target_status: 回滚目标状态（默认：pending）
        
        Returns:
            是否成功回滚
        
        Raises:
            StateConflictError: 如果无法获取锁（并发冲突）
        """
        # 使用锁防止并发更新
        with self._lock.acquire(episode_id):
            schedule = self._load(force=True)  # 强制重新加载
            if not schedule:
                return False
            
            ep = self.get_episode(episode_id)
            if not ep:
                return False
            
            # 保存回滚前的状态
            previous_status = ep.get("status", STATUS_PENDING)
            
            # 回滚状态
            ep["status"] = target_status
            ep["status_updated_at"] = datetime.now().isoformat()
            ep["rollback_from"] = previous_status
            ep["rollback_at"] = datetime.now().isoformat()
            
            # 清除错误信息
            ep.pop("error_details", None)
            ep.pop("error_occurred_at", None)
        
            # 记录回滚指标
            try:
                from metrics_manager import get_metrics_manager
                metrics_manager = get_metrics_manager()
                metrics_manager.record_event(
                    stage="rollback",
                    status="completed",
                    episode_id=episode_id
                )
            except ImportError:
                pass
        
            return self._save(schedule)
    
    def get_all_used_tracks(self, include_pending: bool = True) -> Set[str]:
        """
        动态查询所有已使用的歌曲
        
        Args:
            include_pending: 是否包含"pending"状态的期数
        
        Returns:
            所有已使用的歌曲标题集合
        """
        schedule = self._load()
        if not schedule:
            return set()
        
        all_used = set()
        for ep in schedule.get("episodes", []):
            # 如果include_pending=False，只查询非pending状态的期数
            if not include_pending:
                status = ep.get("status", STATUS_PENDING)
                if status == STATUS_PENDING:
                    continue
            
            tracks = ep.get("tracks_used", [])
            if tracks:
                all_used.update(tracks)
        
        return all_used
    
    def get_used_starting_tracks(self, include_pending: bool = True) -> Set[str]:
        """
        动态查询所有已使用的起始曲目
        
        Args:
            include_pending: 是否包含"pending"状态的期数
        
        Returns:
            所有已使用的起始曲目标题集合
        """
        schedule = self._load()
        if not schedule:
            return set()
        
        starting_tracks = set()
        for ep in schedule.get("episodes", []):
            # 如果include_pending=False，只查询非pending状态的期数
            if not include_pending:
                status = ep.get("status", STATUS_PENDING)
                if status == STATUS_PENDING:
                    continue
            
            starting = ep.get("starting_track")
            if starting:
                starting_tracks.add(starting)
        
        return starting_tracks
    
    def get_recent_tracks(self, episode_id: str, window: int = 5) -> Set[str]:
        """
        动态查询最近N期使用的歌曲
        
        Args:
            episode_id: 当前期ID
            window: 检查窗口大小（向前检查N期）
        
        Returns:
            最近N期使用的歌曲集合
        """
        schedule = self._load()
        if not schedule:
            return set()
        
        current_ep = self.get_episode(episode_id)
        if not current_ep:
            return set()
        
        current_number = current_ep.get("episode_number", 0)
        recent_tracks = set()
        
        for ep in schedule.get("episodes", []):
            ep_num = ep.get("episode_number", 0)
            # 检查是否在窗口内（当前期之前）
            if ep_num < current_number and ep_num >= current_number - window:
                tracks = ep.get("tracks_used", [])
                if tracks:
                    recent_tracks.update(tracks)
        
        return recent_tracks
    
    def update_episode_metadata(
        self,
        episode_id: str,
        title: Optional[str] = None,
        tracks_used: Optional[List[str]] = None,
        starting_track: Optional[str] = None,
        youtube_video_id: Optional[str] = None,
        youtube_video_url: Optional[str] = None,
        youtube_uploaded_at: Optional[str] = None
    ) -> bool:
        """
        更新期数元数据（标题、曲目等，不改变状态）
        
        Args:
            episode_id: 期数ID
            title: 标题
            tracks_used: 使用的歌曲列表
            starting_track: 起始曲目
            youtube_video_id: YouTube视频ID
            youtube_video_url: YouTube视频URL
            youtube_uploaded_at: 上传时间（ISO格式）
        
        Returns:
            是否成功更新
        """
        schedule = self._load()
        if not schedule:
            return False
        
        ep = self.get_episode(episode_id)
        if not ep:
            return False
        
        if title is not None:
            ep["title"] = title
        if tracks_used is not None:
            ep["tracks_used"] = tracks_used
        if starting_track is not None:
            ep["starting_track"] = starting_track
        if youtube_video_id is not None:
            ep["youtube_video_id"] = youtube_video_id
        if youtube_video_url is not None:
            ep["youtube_video_url"] = youtube_video_url
        if youtube_uploaded_at is not None:
            ep["youtube_uploaded_at"] = youtube_uploaded_at
        
        ep["metadata_updated_at"] = datetime.now().isoformat()
        
        return self._save(schedule)
    
    def verify_episode_files(self, episode_id: str, output_dir: Path) -> Tuple[bool, List[str], Dict[str, bool]]:
        """
        从文件系统验证期数文件完整性（文件系统为真相来源）
        
        Args:
            episode_id: 期数ID
            output_dir: 输出目录
        
        Returns:
            (is_complete, missing_files, file_status)
        """
        ep = self.get_episode(episode_id)
        if not ep:
            return False, ["期数不存在"], {}
        
        schedule_date_str = ep.get("schedule_date", "")
        title = ep.get("title", "")
        
        # 获取最终文件夹路径
        final_dir = None
        if schedule_date_str and title:
            try:
                from datetime import datetime as dt
                schedule_date = dt.strptime(schedule_date_str, "%Y-%m-%d")
                # 手动构造路径（避免循环导入）
                date_part = schedule_date.strftime("%Y-%m-%d")
                title_part = title.replace(" ", "_").replace("/", "_")
                final_dir = output_dir / f"{date_part}_{title_part}"
            except Exception:
                pass
        
        # 检查必需文件
        required_files = {
            "playlist": f"{episode_id}_playlist.csv",
            "cover": f"{episode_id}_cover.png",
            "audio": f"{episode_id}_full_mix.mp3",
            "youtube_srt": f"{episode_id}_youtube.srt",
            "youtube_title": f"{episode_id}_youtube_title.txt",
            "youtube_desc": f"{episode_id}_youtube_description.txt",
            "video": f"{episode_id}_youtube.mp4",
        }
        
        file_status = {}
        missing = []
        
        for key, filename in required_files.items():
            found = False
            
            # 检查output根目录
            if (output_dir / filename).exists():
                found = True
            # 检查最终文件夹
            elif final_dir and (final_dir / filename).exists():
                found = True
            # 特殊处理：音频可能有两种命名
            elif key == "audio":
                alt_names = [
                    f"{episode_id}_playlist_full_mix.mp3",
                    f"{episode_id}_full_mix.mp3",
                ]
                for alt_name in alt_names:
                    if (output_dir / alt_name).exists() or (final_dir and (final_dir / alt_name).exists()):
                        found = True
                        break
            
            file_status[key] = found
            if not found:
                missing.append(filename)
        
        is_complete = len(missing) == 0
        return is_complete, missing, file_status


# 全局单例
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """获取全局状态管理器实例"""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


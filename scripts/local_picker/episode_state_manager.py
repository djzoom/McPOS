#!/usr/bin/env python3
# coding: utf-8
"""
统一期数状态管理器

设计原则：
1. 单一数据源：以 schedule_master.json 为唯一权威数据源
2. 动态查询：使用记录不单独存储，从排播表动态查询
3. 事件驱动：生成时实时更新状态，失败时回滚

功能：
1. 管理期数的完整生命周期状态
2. 提供事务性更新（成功提交，失败回滚）
3. 从文件系统验证状态（文件存在性作为真相来源）
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class EpisodeStateManager:
    """
    统一期数状态管理器
    
    以 schedule_master.json 为单一数据源，其他模块从中读取状态
    """
    
    def __init__(self, schedule_path: Optional[Path] = None):
        if schedule_path is None:
            schedule_path = REPO_ROOT / "config" / "schedule_master.json"
        self.schedule_path = schedule_path
        self._schedule_cache: Optional[Dict] = None
    
    def load_schedule(self) -> Optional[Dict]:
        """加载排播表"""
        if not self.schedule_path.exists():
            return None
        
        if self._schedule_cache is None:
            with self.schedule_path.open("r", encoding="utf-8") as f:
                self._schedule_cache = json.load(f)
        return self._schedule_cache
    
    def save_schedule(self, schedule: Dict) -> bool:
        """保存排播表（原子性写入）"""
        try:
            # 先写入临时文件，然后原子性重命名
            temp_path = self.schedule_path.with_suffix(".json.tmp")
            with temp_path.open("w", encoding="utf-8") as f:
                json.dump(schedule, f, ensure_ascii=False, indent=2)
            temp_path.replace(self.schedule_path)
            self._schedule_cache = schedule
            return True
        except Exception as e:
            print(f"❌ 保存排播表失败: {e}")
            return False
    
    def get_episode(self, episode_id: str) -> Optional[Dict]:
        """获取期数记录"""
        schedule = self.load_schedule()
        if not schedule:
            return None
        
        for ep in schedule.get("episodes", []):
            if ep.get("episode_id") == episode_id:
                return ep
        return None
    
    def get_all_used_tracks(self, include_pending: bool = True) -> Set[str]:
        """
        动态查询所有已使用的歌曲
        
        Args:
            include_pending: 是否包含"待制作"状态的期数（默认True，因为已分配曲目）
        
        Returns:
            所有已使用的歌曲标题集合
        """
        schedule = self.load_schedule()
        if not schedule:
            return set()
        
        all_used = set()
        for ep in schedule.get("episodes", []):
            # 如果include_pending=False，只查询已完成状态的期数
            if not include_pending:
                status = ep.get("status", "待制作")
                if status != "已完成":
                    continue
            
            tracks = ep.get("tracks_used", [])
            all_used.update(tracks)
        
        return all_used
    
    def get_used_starting_tracks(self, include_pending: bool = True) -> Set[str]:
        """
        动态查询所有已使用的起始曲目
        
        Args:
            include_pending: 是否包含"待制作"状态的期数（默认True）
        
        Returns:
            所有已使用的起始曲目标题集合
        """
        schedule = self.load_schedule()
        if not schedule:
            return set()
        
        starting_tracks = set()
        for ep in schedule.get("episodes", []):
            # 如果include_pending=False，只查询已完成状态的期数
            if not include_pending:
                status = ep.get("status", "待制作")
                if status != "已完成":
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
        schedule = self.load_schedule()
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
                recent_tracks.update(tracks)
        
        return recent_tracks
    
    def update_episode_transactional(
        self,
        episode_id: str,
        title: Optional[str] = None,
        tracks_used: Optional[List[str]] = None,
        starting_track: Optional[str] = None,
        status: Optional[str] = None,
        partial_success: bool = False
    ) -> bool:
        """
        事务性更新期数记录
        
        如果partial_success=True，即使后续阶段可能失败，也允许更新部分信息
        如果partial_success=False，只在所有阶段成功时才更新状态
        
        Returns:
            是否成功更新
        """
        schedule = self.load_schedule()
        if not schedule:
            return False
        
        ep = self.get_episode(episode_id)
        if not ep:
            return False
        
        # 保存原始状态（用于回滚）
        original_status = ep.get("status")
        original_title = ep.get("title")
        original_tracks = ep.get("tracks_used", [])
        original_starting = ep.get("starting_track")
        
        # 更新字段
        if title is not None:
            ep["title"] = title
        if tracks_used is not None:
            ep["tracks_used"] = tracks_used
        if starting_track is not None:
            ep["starting_track"] = starting_track
        
        # 状态更新逻辑：
        # - 如果partial_success=False，只更新status为"已完成"当所有阶段完成
        # - 如果partial_success=True，可以标记为"制作中"或保持"待制作"
        if status is not None:
            if partial_success and status == "已完成":
                # 不允许部分成功时标记为已完成
                ep["status"] = "制作中"
            else:
                ep["status"] = status
        
        # 保存（原子性）
        if self.save_schedule(schedule):
            return True
        else:
            # 回滚
            ep["status"] = original_status
            if original_title:
                ep["title"] = original_title
            ep["tracks_used"] = original_tracks
            if original_starting:
                ep["starting_track"] = original_starting
            return False
    
    def rollback_episode(self, episode_id: str, rollback_to: Optional[str] = None) -> bool:
        """
        回滚期数状态（在失败时调用）
        
        Args:
            episode_id: 期数ID
            rollback_to: 回滚到的状态（None表示清除部分数据）
        """
        schedule = self.load_schedule()
        if not schedule:
            return False
        
        ep = self.get_episode(episode_id)
        if not ep:
            return False
        
        if rollback_to == "pending":
            # 清除生成的数据，恢复到待制作状态
            ep["status"] = "待制作"
            # 可选：清除标题和曲目，但如果已经有部分生成，保留它们可能更好
            # ep["title"] = None
            # ep["tracks_used"] = []
            # ep["starting_track"] = None
        elif rollback_to is not None:
            ep["status"] = rollback_to
        
        return self.save_schedule(schedule)
    
    def verify_episode_files(self, episode_id: str, output_dir: Path) -> Tuple[bool, List[str], Dict[str, bool]]:
        """
        从文件系统验证期数文件完整性（文件系统为真相来源）
        
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
                from utils import get_final_output_dir
                schedule_date = datetime.strptime(schedule_date_str, "%Y-%m-%d")
                final_dir = get_final_output_dir(schedule_date, title)
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
    
    def sync_from_filesystem(self, output_dir: Path, auto_fix: bool = False) -> Dict:
        """
        从文件系统同步状态（文件系统为真相来源）
        
        Returns:
            同步统计信息
        """
        schedule = self.load_schedule()
        if not schedule:
            return {"synced": 0, "errors": 0}
        
        stats = {
            "synced": 0,
            "errors": 0,
            "updated": [],
            "rolled_back": [],
        }
        
        for ep in schedule.get("episodes", []):
            episode_id = ep.get("episode_id")
            if not episode_id:
                continue
            
            # 验证文件完整性
            is_complete, missing, file_status = self.verify_episode_files(episode_id, output_dir)
            current_status = ep.get("status", "待制作")
            
            if is_complete:
                # 文件完整，应该标记为"已完成"
                if current_status != "已完成":
                    if auto_fix:
                        ep["status"] = "已完成"
                        stats["updated"].append(episode_id)
                    stats["synced"] += 1
            else:
                # 文件不完整，如果状态是"已完成"，需要回滚
                if current_status == "已完成":
                    if auto_fix:
                        ep["status"] = "制作中"  # 回滚到制作中，保留已有数据
                        stats["rolled_back"].append({
                            "id": episode_id,
                            "missing": missing[:3],  # 只记录前3个缺失文件
                        })
                    stats["errors"] += 1
        
        if auto_fix and (stats["updated"] or stats["rolled_back"]):
            self.save_schedule(schedule)
        
        return stats


# 全局单例
_state_manager: Optional[EpisodeStateManager] = None


def get_state_manager() -> EpisodeStateManager:
    """获取全局状态管理器实例"""
    global _state_manager
    if _state_manager is None:
        _state_manager = EpisodeStateManager()
    return _state_manager


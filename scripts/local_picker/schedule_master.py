#!/usr/bin/env python3
# coding: utf-8
"""
永恒排播表系统

功能：
1. 一次性生成所有排播计划（永恒标准，不再变更）
2. 追踪图片使用（确保不重复，不够时提示）
3. 追踪标题模式（避免形式重复）
4. 追踪歌曲使用（避免临近期数重复）
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set

# 永恒排播表文件（一旦生成就不再变更）
SCHEDULE_MASTER_PATH = Path("config/schedule_master.json")

# 默认起始排播日期（系统当前日期）
def get_default_start_date() -> datetime:
    """获取默认起始日期：系统当前日期（00:00:00）"""
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

DEFAULT_START_DATE = get_default_start_date()

# 排播间隔（天）
SCHEDULE_INTERVAL_DAYS = 2

# 导入状态管理
try:
    from episode_status import (
        STATUS_待制作,
        STATUS_已完成,
        STATUS_已跳过,
        normalize_status,
        is_pending_status,
        is_completed_status,
    )
except ImportError:
    # 向后兼容：如果没有episode_status模块，使用旧状态
    STATUS_待制作 = "待制作"
    STATUS_已完成 = "已完成"
    STATUS_已跳过 = "已跳过"
    
    def normalize_status(s: str) -> str:
        return s or "待制作"
    
    def is_pending_status(s: str) -> bool:
        return normalize_status(s) not in ["已完成", "已跳过"]
    
    def is_completed_status(s: str) -> bool:
        return normalize_status(s) == "已完成"


@dataclass
class ScheduleEpisode:
    """排播表中的单期记录"""
    episode_number: int  # 期数（从1开始）
    schedule_date: str  # 排播日期 YYYY-MM-DD
    episode_id: str  # 排播ID YYYYMMDD
    image_path: Optional[str] = None  # 分配的图片路径
    image_used: bool = False  # 图片是否已使用
    title: Optional[str] = None  # 生成的标题
    title_pattern: Optional[str] = None  # 标题模式（用于去重）
    tracks_used: List[str] = field(default_factory=list)  # 使用的歌曲列表
    starting_track: Optional[str] = None  # 起始曲目
    status: str = "待制作"  # 待制作 / 制作中 / 上传中 / 排播完毕待播出 / 已完成 / 已跳过


@dataclass
class ScheduleMaster:
    """永恒排播表"""
    created_at: str  # 创建时间
    start_date: str  # 起始日期
    schedule_interval_days: int  # 排播间隔
    total_episodes: int  # 总期数
    episodes: List[Dict] = field(default_factory=list)  # 所有期记录
    images_pool: List[str] = field(default_factory=list)  # 可用图片池
    images_used: Set[str] = field(default_factory=set)  # 已使用图片
    title_patterns: List[str] = field(default_factory=list)  # 已使用的标题模式
    
    @classmethod
    def create(
        cls,
        total_episodes: int,
        start_date: Optional[datetime] = None,
        schedule_interval_days: int = SCHEDULE_INTERVAL_DAYS,
        images_dir: Optional[Path] = None
    ) -> "ScheduleMaster":
        """
        创建永恒排播表
        
        Args:
            total_episodes: 总期数
            start_date: 起始日期（默认：系统时间下一天）
            schedule_interval_days: 排播间隔
            images_dir: 图片目录
        """
        if start_date is None:
            start_date = get_default_start_date()
        
        # 收集所有可用图片
        if images_dir is None:
            # 使用相对路径，避免导入循环
            repo_root = Path(__file__).parent.parent.parent
            images_dir = repo_root / "assets" / "design" / "images"
        
        image_files = sorted(list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg")))
        images_pool = [str(img.resolve()) for img in image_files]
        
        if total_episodes > len(images_pool):
            raise ValueError(
                f"期数 {total_episodes} 超过可用图片数量 {len(images_pool)}。"
                f"需要至少 {total_episodes} 张图片。"
            )
        
        # 生成所有期数
        episodes = []
        import random
        rng = random.Random(42)  # 固定种子，确保可复现
        
        # 随机分配图片（但保持顺序）
        shuffled_images = images_pool.copy()
        rng.shuffle(shuffled_images)
        
        # 收集所有分配的图片（用于标记为已使用）
        assigned_images = set()
        
        for i in range(total_episodes):
            schedule_date = start_date + timedelta(days=i * schedule_interval_days)
            image_path = shuffled_images[i] if i < len(shuffled_images) else None
            episode = ScheduleEpisode(
                episode_number=i + 1,
                schedule_date=schedule_date.strftime("%Y-%m-%d"),
                episode_id=schedule_date.strftime("%Y%m%d"),
                image_path=image_path,
                status=STATUS_待制作
            )
            episodes.append(asdict(episode))
            # 收集分配的图片
            if image_path:
                assigned_images.add(image_path)
        
        return cls(
            created_at=datetime.now().isoformat(),
            start_date=start_date.strftime("%Y-%m-%d"),
            schedule_interval_days=schedule_interval_days,
            total_episodes=total_episodes,
            episodes=episodes,
            images_pool=images_pool,
            images_used=assigned_images,  # 将所有分配的图片标记为已使用
            title_patterns=[]
        )
    
    @classmethod
    def load(cls, path: Path = SCHEDULE_MASTER_PATH) -> Optional["ScheduleMaster"]:
        """加载永恒排播表"""
        if not path.exists():
            return None
        
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # 转换 images_used 从 list 到 set
            if isinstance(data.get("images_used"), list):
                data["images_used"] = set(data["images_used"])
            return cls(**data)
        except Exception as e:
            print(f"[WARN] 加载排播表失败: {e}")
            return None
    
    def save(self, path: Path = SCHEDULE_MASTER_PATH) -> None:
        """保存永恒排播表"""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        # 转换 images_used 从 set 到 list（JSON不支持set）
        data["images_used"] = list(data["images_used"])
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_episode(self, episode_id: str) -> Optional[Dict]:
        """获取指定期的记录"""
        for ep in self.episodes:
            if ep.get("episode_id") == episode_id:
                return ep
        return None
    
    def get_episode_by_number(self, episode_number: int) -> Optional[Dict]:
        """根据期数获取记录"""
        for ep in self.episodes:
            if ep.get("episode_number") == episode_number:
                return ep
        return None
    
    def mark_image_used(self, image_path: str) -> None:
        """标记图片已使用"""
        self.images_used.add(image_path)
    
    def sync_images_from_assignments(self) -> int:
        """
        基于排播表中的图片分配同步图片使用标记
        
        原则：
        - 只要图片被分配给排播表中的某一期，就应该标记为"已使用"
        - 这样确保图片不会被重复分配给其他期数
        - 删除期数后，对应的图片标记会被移除
        
        Returns:
            同步的图片数量（正数=添加的，负数=移除的）
        """
        # 从排播表中提取所有分配的图片
        assigned_images = set()
        for ep in self.episodes:
            image_path = ep.get("image_path")
            if image_path:
                assigned_images.add(image_path)
        
        # 添加缺失的标记（已分配但未标记）
        added_count = 0
        for img in assigned_images:
            if img not in self.images_used:
                self.images_used.add(img)
                added_count += 1
        
        # 清理多余的标记（已标记但未分配）
        removed_count = 0
        extra_marked = self.images_used - assigned_images
        for img in extra_marked:
            self.images_used.discard(img)
            removed_count += 1
        
        return added_count - removed_count
    
    def check_image_available(self, episode_id: str) -> tuple[bool, Optional[str]]:
        """检查期数是否有可用图片"""
        ep = self.get_episode(episode_id)
        if not ep:
            return False, None
        image_path = ep.get("image_path")
        if not image_path:
            return False, None
        if image_path in self.images_used:
            return False, image_path
        return True, image_path
    
    def check_title_pattern(self, title: str) -> tuple[bool, str]:
        """
        检查标题模式是否重复（包含短语级检查）
        
        Returns:
            (is_unique, pattern)
        """
        # 首先检查短语重复
        phrase_unique, repeated_phrases = self.check_phrase_repetition(title)
        if not phrase_unique:
            # 短语重复，生成一个标记pattern
            pattern = f"phrase_dup_{'_'.join(repeated_phrases[:2])}"
            return False, pattern
        
        # 提取标题模式：去除常见词，保留核心结构
        pattern = self._extract_title_pattern(title)
        is_unique = pattern not in self.title_patterns
        return is_unique, pattern
    
    def check_phrase_repetition(self, title: str) -> tuple[bool, List[str]]:
        """
        检查标题中是否包含已使用的常见短语
        
        Returns:
            (is_unique, repeated_phrases): 是否唯一，以及重复的短语列表
        """
        # 常见短语列表（需要避免重复的）
        common_phrases = [
            "soft sigh", "a cat's soft sigh", "soft sigh of", "soft sigh",
            "did you dream of", "did you dream",
            "lost in", "found in", "lost in...found in",
            "unseen depths", "unseen depth",
            "slow blink", "slow blink of", "the slow blink",
            "whispers of fur", "whispers of",
            "velvet paws", "velvet paws on",
            "curled up", "curled-up", "a curled up",
            "nestled deep", "nestled in",
        ]
        
        title_lower = title.lower()
        repeated_phrases = []
        
        # 检查当前标题中的短语
        for phrase in common_phrases:
            if phrase in title_lower:
                # 检查这个短语是否在已使用的标题中出现过
                for ep in self.episodes:
                    ep_title = ep.get("title", "").lower()
                    if ep_title and phrase in ep_title:
                        if phrase not in repeated_phrases:
                            repeated_phrases.append(phrase)
                        break
        
        return len(repeated_phrases) == 0, repeated_phrases
    
    def _extract_title_pattern(self, title: str) -> str:
        """提取标题模式（用于去重）"""
        import re
        # 转换为小写
        title_lower = title.lower()
        
        # 移除常见前缀/后缀
        common_prefixes = ["the", "a", "an"]
        common_suffixes = ["dreams", "dream", "night", "nights", "day", "days"]
        
        words = re.findall(r'\b\w+\b', title_lower)
        
        # 移除常见词
        filtered = []
        for w in words:
            if w not in common_prefixes and w not in common_suffixes:
                filtered.append(w)
        
        # 如果过滤后为空，使用原始词（取前3个词）
        if not filtered:
            filtered = words[:3]
        
        # 提取模式：前3个关键词 + 总词数
        pattern = "_".join(filtered[:3]) + f"_{len(words)}"
        return pattern
    
    def add_title_pattern(self, pattern: str) -> None:
        """添加标题模式到已使用列表"""
        if pattern not in self.title_patterns:
            self.title_patterns.append(pattern)
    
    def get_recent_tracks(self, episode_id: str, window: int = 5) -> Set[str]:
        """
        获取最近 N 期使用的歌曲（避免临近期数重复）
        
        Args:
            episode_id: 当前期ID
            window: 检查窗口大小（向前检查N期）
        """
        current_ep = self.get_episode(episode_id)
        if not current_ep:
            return set()
        
        current_number = current_ep.get("episode_number", 0)
        recent_tracks = set()
        
        for ep in self.episodes:
            ep_num = ep.get("episode_number", 0)
            # 检查是否在窗口内（当前期之前）
            if ep_num < current_number and ep_num >= current_number - window:
                tracks = ep.get("tracks_used", [])
                recent_tracks.update(tracks)
        
        return recent_tracks
    
    def get_used_starting_tracks(self) -> Set[str]:
        """获取所有已使用的起始曲目"""
        starting_tracks = set()
        for ep in self.episodes:
            starting = ep.get("starting_track")
            if starting:
                starting_tracks.add(starting)
        return starting_tracks
    
    def get_all_used_tracks(self) -> Set[str]:
        """获取所有已使用的歌曲（用于识别新歌）"""
        all_used = set()
        for ep in self.episodes:
            tracks = ep.get("tracks_used", [])
            all_used.update(tracks)
        return all_used
    
    def update_episode(
        self,
        episode_id: str,
        title: Optional[str] = None,
        tracks_used: Optional[List[str]] = None,
        starting_track: Optional[str] = None,
        status: Optional[str] = None
    ) -> bool:
        """更新期数记录"""
        ep = self.get_episode(episode_id)
        if not ep:
            return False
        
        if title:
            ep["title"] = title
            # 提取并添加标题模式
            _, pattern = self.check_title_pattern(title)
            ep["title_pattern"] = pattern
            self.add_title_pattern(pattern)
        
        if tracks_used:
            ep["tracks_used"] = tracks_used
        
        if starting_track:
            ep["starting_track"] = starting_track
        
        if status:
            ep["status"] = status
        
        # 不再自动标记图片已使用（基于完成状态）
        # 图片标记应该根据排播表中的分配来决定，通过 sync_images_from_assignments() 同步
        
        return True
    
    def check_remaining_images(self) -> tuple[int, List[str]]:
        """检查剩余可用图片"""
        total_images = len(self.images_pool)
        used_count = len(self.images_used)
        remaining = total_images - used_count
        
        # 找出未使用的图片
        unused = [img for img in self.images_pool if img not in self.images_used]
        
        return remaining, unused
    
    def get_next_pending_episode(self) -> Optional[Dict]:
        """获取下一个待处理的期数"""
        for ep in self.episodes:
            if is_pending_status(ep.get("status", STATUS_待制作)):
                return ep
        return None
    
    def get_end_date(self) -> str:
        """获取结束日期（最后一个episode的日期）"""
        if not self.episodes:
            return self.start_date
        last_ep = self.episodes[-1]
        return last_ep.get("schedule_date", self.start_date)
    
    def extend(self, additional_episodes: int, images_dir: Optional[Path] = None) -> None:
        """
        扩展排播表，添加新的期数
        
        Args:
            additional_episodes: 要添加的期数
            images_dir: 图片目录（默认：assets/design/images）
        """
        if additional_episodes <= 0:
            raise ValueError("要添加的期数必须大于0")
        
        # 收集可用图片（排除已使用的）
        if images_dir is None:
            repo_root = Path(__file__).parent.parent.parent
            images_dir = repo_root / "assets" / "design" / "images"
        
        all_image_files = sorted(list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg")))
        all_images_pool = [str(img.resolve()) for img in all_image_files]
        
        # 获取未使用的图片
        unused_images = [img for img in all_images_pool if img not in self.images_used]
        
        if additional_episodes > len(unused_images):
            raise ValueError(
                f"要添加的期数 {additional_episodes} 超过剩余可用图片数量 {len(unused_images)}。"
                f"需要至少 {additional_episodes} 张未使用的图片。"
            )
        
        # 计算新的起始日期（从最后一个episode的日期+间隔开始）
        from datetime import timedelta
        last_ep_date_str = self.get_end_date()
        last_ep_date = datetime.fromisoformat(last_ep_date_str)
        next_date = last_ep_date + timedelta(days=self.schedule_interval_days)
        
        # 获取当前最大期数
        current_max_number = max([ep.get("episode_number", 0) for ep in self.episodes], default=0)
        
        # 随机分配图片
        import random
        rng = random.Random(42 + current_max_number)  # 基于当前期数的种子，确保可复现但不同
        shuffled_unused = unused_images.copy()
        rng.shuffle(shuffled_unused)
        
        # 生成新的期数
        new_episodes = []
        for i in range(additional_episodes):
            schedule_date = next_date + timedelta(days=i * self.schedule_interval_days)
            episode = ScheduleEpisode(
                episode_number=current_max_number + i + 1,
                schedule_date=schedule_date.strftime("%Y-%m-%d"),
                episode_id=schedule_date.strftime("%Y%m%d"),
                image_path=shuffled_unused[i] if i < len(shuffled_unused) else None,
                status=STATUS_待制作
            )
            new_episodes.append(asdict(episode))
        
        # 添加到现有episodes
        self.episodes.extend(new_episodes)
        self.total_episodes = len(self.episodes)
        
        # 更新images_pool（如果图片池中还没有新图片，则添加）
        for img in all_images_pool:
            if img not in self.images_pool:
                self.images_pool.append(img)


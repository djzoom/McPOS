"""
简单调度器

从文件系统或排期文件中获取需要处理的 episode 列表。
所有调度都基于文件系统扫描，不使用 ASR。
"""

from typing import List, Optional
from datetime import datetime, timedelta

from ..models import EpisodeSpec


def get_episodes_for_day(channel_id: str, date: str) -> List[EpisodeSpec]:
    """
    获取某一天需要处理的 episodes
    
    可以从 schedule_master.json 或 ASR 中读取。
    """
    # TODO: 实现从文件系统扫描或排期文件读取逻辑
    # 暂时返回空列表
    return []


def get_episodes_for_month(channel_id: str, year: int, month: int) -> List[EpisodeSpec]:
    """
    获取某个月需要处理的 episodes
    """
    # TODO: 实现从文件系统扫描或排期文件读取逻辑
    # 暂时返回空列表
    return []


def get_incomplete_episodes(channel_id: Optional[str] = None) -> List[EpisodeSpec]:
    """
    获取所有未完成的 episodes
    
    用于补全缺失资产或重试失败的阶段。
    """
    # TODO: 从文件系统扫描未完成的 episodes
    return []


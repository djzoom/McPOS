"""
状态查询与聚合

提供基于文件系统的状态统计和聚合功能。
所有状态查询都基于文件系统扫描，不使用 ASR。
"""

from typing import List, Dict, Optional
from datetime import datetime

from ..models import EpisodeState, StageName


def get_episode_completion_rate(channel_id: str, year: int, month: int) -> Dict[str, float]:
    """
    计算某个月各阶段的完成比例
    
    返回格式: {"init": 0.95, "cover": 0.90, ...}
    """
    # TODO: 从文件系统扫描该月的所有 episodes，统计各阶段完成情况
    return {stage.value: 0.0 for stage in StageName}


def get_failure_reasons(channel_id: Optional[str] = None) -> Dict[str, int]:
    """
    统计失败原因
    
    返回格式: {"error_message": count}
    """
    # TODO: 从文件系统扫描所有失败的 episodes，统计错误信息
    return {}


def get_blocked_stages(channel_id: Optional[str] = None) -> Dict[StageName, int]:
    """
    统计当前阻塞在哪些阶段
    
    返回格式: {StageName.INIT: 5, StageName.MIX: 2, ...}
    """
    # TODO: 从文件系统扫描所有未完成且 current_stage 不为 None 的 episodes
    return {}


def list_episodes_by_status(
    channel_id: Optional[str] = None,
    completed: Optional[bool] = None,
) -> List[EpisodeState]:
    """
    根据完成状态列出 episodes
    """
    # TODO: 实现状态过滤逻辑
    return []


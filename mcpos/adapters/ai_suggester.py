"""
AI Suggester Boundary

这是所有"AI 选曲/推荐"的唯一入口。
文案类（标题、描述生成）请使用 `mcpos/adapters/ai_title_generator.py`。

generate_playlist_for_episode 可以选择调用它，也可以完全不调用；
但 McPOS 其它地方不允许直接 import openai 或任何 SDK。

未来要上"情绪匹配""BPM 匹配""AI 主题推荐"，只需要一直往这个文件里加实现，
generate_playlist_for_episode 的签名不需要改。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, List, Dict
from pathlib import Path

from ..models import EpisodeSpec


@dataclass(frozen=True)
class TrackCandidate:
    """
    AI 推荐的曲目候选
    
    这是一个不可变的结果对象，不应在后续逻辑中被修改。
    """
    track_id: str
    path: str
    duration_ms: int
    score: float  # 推荐分数 (0.0 - 1.0)
    meta: Optional[Dict[str, Any]] = None


# 类型别名（简化，实际可以从 models 导入更完整的类型）
LibraryIndex = List[Path]
EpisodeConfig = Dict[str, Any]
PlaylistHistory = Dict[str, Any]


async def suggest_tracks_for_episode(
    spec: EpisodeSpec,
    library_index: LibraryIndex,
    config: EpisodeConfig,
    history: PlaylistHistory | None = None,
    max_candidates: int = 200,
) -> List[TrackCandidate]:
    """
    可选的 AI 辅助推荐边界函数。
    
    这是所有 AI 推荐功能的唯一入口。
    
    - Called only from generate_playlist_for_episode() in mcpos/assets/init.py
    - Inside this function you may call any LLM / recommendation API.
    - MUST be safe to bypass (i.e. generate_playlist_for_episode must still work
      if this function returns empty list or raises).
    - Future: can swap AI provider (OpenAI / Suno / RAG / etc.) without touching core
    
    Args:
        spec: Episode specification
        library_index: List of available track paths
        config: Episode configuration (target_duration, special_tags, etc.)
        history: Optional playlist history for deduplication
        max_candidates: Maximum number of candidates to return
    
    Returns:
        List of track candidates with scores
    """
    # 初始版本：完全不用外部 AI，返回空列表
    # 未来可以在这里接入：
    # - OpenAI API for theme-based recommendations
    # - Suno API for style matching
    # - RAG system for semantic search
    # - Custom ML model for BPM/energy matching
    
    return []


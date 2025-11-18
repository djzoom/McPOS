"""
Assets 层：各类资产的唯一入口

每个模块负责一种资产或一个阶段的处理逻辑。
"""

from .init import init_episode
from .cover import generate_cover_for_episode
from .text import generate_text_base_assets, generate_text_srt
from .mix import run_remix_for_episode
from .render import run_render_for_episode

__all__ = [
    "init_episode",
    "generate_cover_for_episode",
    "generate_text_base_assets",
    "generate_text_srt",
    "run_remix_for_episode",
    "run_render_for_episode",
]


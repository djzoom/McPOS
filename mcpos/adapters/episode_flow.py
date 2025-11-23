"""
EpisodeFlow 适配器

McPOS 原则：完全独立，不依赖外部文件夹。
本适配器将在 McPOS 内部实现混音和渲染逻辑，不引用 src/core/episode_flow.py。
未来如果需要复用旧世界的工具函数，只通过命令行调用或文件接口，不直接 import。
"""

from typing import Any

# 预留：后续实现会用到 EpisodeSpec, AssetPaths, get_config
# from ..models import EpisodeSpec, AssetPaths
# from ..config import get_config


def build_episode_flow(spec: Any, asset_paths: Any) -> Any:
    """
    根据 EpisodeSpec 和 AssetPaths 构建混音/渲染引擎实例
    
    McPOS 原则：所有逻辑在 McPOS 内部实现，不引用外部模块。
    未来实现时，将直接在 McPOS 内部实现混音和渲染逻辑，或通过命令行/文件接口调用外部工具。
    
    Args:
        spec: EpisodeSpec 实例（预留，后续实现会用到）
        asset_paths: AssetPaths 实例（预留，后续实现会用到）
    
    Returns:
        混音/渲染引擎实例（未来实现）
    """
    # TODO: 在 McPOS 内部实现混音和渲染逻辑
    # 不直接 import src/core/episode_flow.py
    # 可以通过命令行调用 FFmpeg 等工具，或通过文件接口与外部工具交互
    raise NotImplementedError("build_episode_flow is not implemented yet")


def get_remix_engine(episode_flow: Any) -> Any:
    """
    从 EpisodeFlow 获取 remix_engine
    
    Args:
        episode_flow: EpisodeFlow 实例
    
    Returns:
        remix_engine 实例（未来实现）
    """
    # TODO: 返回 episode_flow.remix_engine
    raise NotImplementedError("get_remix_engine is not implemented yet")


def get_render_engine(episode_flow: Any) -> Any:
    """
    从 EpisodeFlow 获取 render_engine
    
    Args:
        episode_flow: EpisodeFlow 实例
    
    Returns:
        render_engine 实例（未来实现）
    """
    # TODO: 返回 episode_flow.render_engine
    raise NotImplementedError("get_render_engine is not implemented yet")


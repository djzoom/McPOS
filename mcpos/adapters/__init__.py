"""
Adapters 层：新旧世界的边界封装

将旧世界的实现变成 McPOS 易用的接口。
McPOS 原则：完全独立，不依赖外部文件夹的业务逻辑。

边界模块（Boundary Modules）：所有"未来可能换库/换 provider"的依赖都通过边界模块。
未来换库时，只改 adapter 文件，不动核心骨架。
"""

from .filesystem import (
    build_asset_paths,
    check_asset_exists,
    detect_episode_state_from_filesystem,
)
from .episode_flow import build_episode_flow
from .render_engine import render_episode_video, RenderResult
from .ai_suggester import suggest_tracks_for_episode, TrackCandidate
from .uploader import upload_episode_video, verify_episode_upload, UploadResult, VerifyResult

__all__ = [
    "build_asset_paths",
    "check_asset_exists",
    "detect_episode_state_from_filesystem",
    "build_episode_flow",
    "render_episode_video",
    "RenderResult",
    "suggest_tracks_for_episode",
    "TrackCandidate",
    "upload_episode_video",
    "verify_episode_upload",
    "UploadResult",
    "VerifyResult",
]


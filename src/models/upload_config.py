#!/usr/bin/env python3
# coding: utf-8
"""
上传配置数据模型

使用 dataclass 封装上传配置参数
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class UploadConfig:
    """YouTube 上传配置"""

    video_file: Path
    title: str
    description: str
    privacy_status: str = "unlisted"
    category_id: int = 10
    tags: List[str] = field(default_factory=lambda: ["lofi", "music", "Kat Records", "chill"])
    subtitle_path: Optional[Path] = None
    thumbnail_path: Optional[Path] = None
    episode_id: Optional[str] = None
    max_retries: int = 5
    schedule: bool = False
    default_language: str = "en"
    playlist_id: Optional[str] = None

    def __post_init__(self) -> None:
        """验证配置参数"""
        if not self.video_file.exists():
            from ..core.errors import UploadError

            raise UploadError(f"Video file not found: {self.video_file}")

        if not self.title:
            self.title = f"Kat Records Lo-Fi Mix - {self.episode_id or 'Unknown'}"

        if not self.description:
            self.description = "Kat Records - Lo-Fi Radio Mix"


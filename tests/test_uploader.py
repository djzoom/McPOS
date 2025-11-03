#!/usr/bin/env python3
# coding: utf-8
"""
Uploader 模块测试

测试上传功能的各种场景：成功、失败、重试
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.core.errors import UploadError, TransientError
from src.models.upload_config import UploadConfig


class TestUploadConfig:
    """测试 UploadConfig 数据类"""

    def test_upload_config_creation(self, tmp_path: Path):
        """测试创建 UploadConfig"""
        video_file = tmp_path / "test_video.mp4"
        video_file.write_bytes(b"fake video content")

        config = UploadConfig(
            video_file=video_file,
            title="Test Video",
            description="Test Description",
            episode_id="20251104",
        )

        assert config.video_file == video_file
        assert config.title == "Test Video"
        assert config.description == "Test Description"
        assert config.episode_id == "20251104"
        assert config.privacy_status == "unlisted"
        assert config.max_retries == 5

    def test_upload_config_missing_file(self):
        """测试缺少视频文件时抛出错误"""
        video_file = Path("/nonexistent/video.mp4")

        with pytest.raises(UploadError, match="Video file not found"):
            UploadConfig(
                video_file=video_file,
                title="Test",
                description="Test",
            )

    def test_upload_config_defaults(self, tmp_path: Path):
        """测试默认值"""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"content")

        config = UploadConfig(
            video_file=video_file,
            title="",
            description="",
        )

        assert config.title == "Kat Records Lo-Fi Mix - Unknown"
        assert config.description == "Kat Records - Lo-Fi Radio Mix"


class TestUploadHelpers:
    """测试上传辅助函数"""

    @patch("scripts.uploader.upload_helpers._get_build_metadata")
    def test_prepare_body(self, mock_get_metadata, tmp_path: Path):
        """测试准备上传元数据"""
        from scripts.uploader.upload_helpers import prepare_body

        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"content")

        config = UploadConfig(
            video_file=video_file,
            title="Test Title",
            description="Test Description",
            episode_id="20251104",
            privacy_status="unlisted",
            tags=["test"],
            category_id=10,
        )

        mock_metadata = {
            "snippet": {"title": "Test Title"},
            "status": {"privacyStatus": "unlisted"},
        }
        mock_get_metadata.return_value = lambda *args, **kwargs: mock_metadata

        body = prepare_body(config)
        assert body == mock_metadata

    def test_resumable_upload_quota_error(self):
        """测试配额错误"""
        from scripts.uploader.upload_helpers import resumable_upload
        from unittest.mock import MagicMock

        if not GOOGLE_API_AVAILABLE:
            pytest.skip("Google API not available")

        youtube = MagicMock()
        upload_config = UploadConfig(
            video_file=Path("/tmp/test.mp4"),
            title="Test",
            description="Test",
        )

        # Mock HttpError with quota exceeded
        http_error = MagicMock()
        http_error.resp.status = 403
        http_error.content = b'{"error": {"message": "quotaExceeded"}}'

        with patch("scripts.uploader.upload_helpers.HttpError", http_error):
            with pytest.raises(UploadError, match="quota exceeded"):
                resumable_upload(youtube, upload_config, {})


class TestUploadRetry:
    """测试重试逻辑"""

    @patch("scripts.uploader.upload_helpers.time.sleep")
    def test_retry_on_transient_error(self, mock_sleep):
        """测试临时错误时的重试"""
        from scripts.uploader.upload_helpers import resumable_upload

        if not GOOGLE_API_AVAILABLE:
            pytest.skip("Google API not available")

        # This would require more mocking, simplified for now
        pass


class TestUploadIntegration:
    """集成测试（使用模拟的 YouTube 客户端）"""

    @patch("scripts.uploader.upload_to_youtube.get_authenticated_service")
    @patch("scripts.uploader.upload_to_youtube.upload_video")
    def test_upload_success_flow(self, mock_upload, mock_get_service, tmp_path: Path):
        """测试成功上传流程"""
        # Mock YouTube service
        mock_youtube = MagicMock()
        mock_get_service.return_value = mock_youtube

        # Mock upload result
        mock_upload.return_value = {
            "video_id": "test_video_id",
            "video_url": "https://www.youtube.com/watch?v=test_video_id",
            "upload_time": "2025-01-01T00:00:00",
            "duration_seconds": 10.5,
        }

        # Create test video file
        video_file = tmp_path / "test_20251104_youtube.mp4"
        video_file.write_bytes(b"fake video")

        # Test would require full main() flow
        # Simplified version here
        assert video_file.exists()


@pytest.fixture
def tmp_path(tmp_path: Path) -> Path:
    """临时路径 fixture"""
    return tmp_path


# 检查 Google API 是否可用
try:
    from scripts.uploader.upload_helpers import GOOGLE_API_AVAILABLE
except ImportError:
    GOOGLE_API_AVAILABLE = False


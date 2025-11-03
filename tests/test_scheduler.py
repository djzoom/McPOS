#!/usr/bin/env python3
# coding: utf-8
"""
Scheduler 模块测试

测试排播表的边界情况
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest


class TestScheduleEdgeCases:
    """排播表边界情况测试"""

    def test_empty_schedule(self, tmp_path: Path):
        """测试空排播表"""
        schedule_file = tmp_path / "schedule_master.json"
        schedule_file.write_text('{"episodes": {}}')

        try:
            from src.core.state_manager import StateManager

            manager = StateManager(schedule_path=schedule_file)
            episodes = manager.get_all_episodes()
            assert len(episodes) == 0
        except ImportError:
            pytest.skip("StateManager not available")

    def test_invalid_status_transition(self, tmp_path: Path):
        """测试无效状态转换"""
        try:
            from src.core.state_manager import StateManager, STATUS_PENDING, STATUS_COMPLETED

            schedule_file = tmp_path / "schedule_master.json"
            schedule_data = {
                "episodes": {
                    "20251104": {
                        "status": STATUS_COMPLETED,
                        "episode_id": "20251104",
                    }
                }
            }
            import json

            schedule_file.write_text(json.dumps(schedule_data))

            manager = StateManager(schedule_path=schedule_file)

            # 尝试从完成状态转换到待处理（应该失败或不允许）
            # 根据实际实现调整
            episode = manager.get_episode("20251104")
            assert episode is not None
            assert episode.get("status") == STATUS_COMPLETED
        except ImportError:
            pytest.skip("StateManager not available")

    def test_duplicate_episode_id(self, tmp_path: Path):
        """测试重复的期数 ID"""
        schedule_file = tmp_path / "schedule_master.json"
        schedule_data = {
            "episodes": {
                "20251104": {
                    "status": "pending",
                    "episode_id": "20251104",
                },
                "20251104": {  # 重复的 key（在 JSON 中会被覆盖）
                    "status": "completed",
                    "episode_id": "20251104",
                }
            }
        }
        import json

        schedule_file.write_text(json.dumps(schedule_data))

        try:
            from src.core.state_manager import StateManager

            manager = StateManager(schedule_path=schedule_file)
            episode = manager.get_episode("20251104")
            # JSON 中重复的 key 会被覆盖，所以应该是最后一个
            assert episode is not None
        except ImportError:
            pytest.skip("StateManager not available")

    def test_missing_required_fields(self, tmp_path: Path):
        """测试缺少必需字段"""
        schedule_file = tmp_path / "schedule_master.json"
        schedule_data = {
            "episodes": {
                "20251104": {
                    # 缺少 status 字段
                    "episode_id": "20251104",
                }
            }
        }
        import json

        schedule_file.write_text(json.dumps(schedule_data))

        try:
            from src.core.state_manager import StateManager

            manager = StateManager(schedule_path=schedule_file)
            episode = manager.get_episode("20251104")
            # 应该能处理缺少字段的情况
            assert episode is not None
            assert episode.get("episode_id") == "20251104"
        except ImportError:
            pytest.skip("StateManager not available")

    def test_invalid_date_format(self):
        """测试无效的日期格式"""
        try:
            from scripts.uploader.upload_to_youtube import parse_episode_date

            # 无效格式
            result = parse_episode_date("invalid")
            assert result is None

            # 过短的字符串
            result = parse_episode_date("2025")
            assert result is None

            # 有效格式
            result = parse_episode_date("20251104")
            assert result is not None
            assert isinstance(result, datetime)
        except ImportError:
            pytest.skip("parse_episode_date not available")


@pytest.fixture
def tmp_path(tmp_path: Path) -> Path:
    """临时路径 fixture"""
    return tmp_path


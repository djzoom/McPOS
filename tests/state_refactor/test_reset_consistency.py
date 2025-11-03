#!/usr/bin/env python3
# coding: utf-8
"""
重置一致性测试

测试用例：
1. reset_all后状态一致性检查
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

# 添加项目路径
import sys
from pathlib import Path as PathLib
_repo_root = PathLib(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_repo_root / "src"))
sys.path.insert(0, str(_repo_root / "scripts" / "local_picker"))

from core.state_manager import StateManager, STATUS_PENDING


@pytest.fixture
def temp_schedule_file(tmp_path):
    """创建临时排播表文件（包含各种状态）"""
    schedule_file = tmp_path / "schedule_master.json"
    
    test_data = {
        "created_at": "2025-11-02T00:00:00",
        "start_date": "2025-11-02",
        "schedule_interval_days": 2,
        "total_episodes": 3,
        "episodes": [
            {
                "episode_number": 1,
                "schedule_date": "2025-11-02",
                "episode_id": "20251102",
                "status": "completed",
                "tracks_used": ["Track 1", "Track 2"],
                "starting_track": "Track 1",
            },
            {
                "episode_number": 2,
                "schedule_date": "2025-11-04",
                "episode_id": "20251104",
                "status": "error",
                "tracks_used": ["Track 3"],
                "starting_track": "Track 3",
            },
            {
                "episode_number": 3,
                "schedule_date": "2025-11-06",
                "episode_id": "20251106",
                "status": "pending",
                "tracks_used": [],
            },
        ],
        "images_pool": [],
        "images_used": ["image1.png", "image2.png"],
        "title_patterns": [],
    }
    
    with schedule_file.open("w", encoding="utf-8") as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)
    
    return schedule_file


def test_reset_all_consistency(temp_schedule_file):
    """测试reset_all后的状态一致性"""
    # 模拟reset_schedule_master的逻辑
    with temp_schedule_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 重置所有期数状态为pending
    for ep in data.get("episodes", []):
        ep["status"] = STATUS_PENDING
        ep["tracks_used"] = []
        ep["starting_track"] = None
        ep.pop("error_details", None)
        ep.pop("error_occurred_at", None)
    
    # 清空images_used
    data["images_used"] = []
    
    # 保存
    with temp_schedule_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 验证
    state_manager = StateManager(schedule_path=temp_schedule_file)
    
    # 所有期数应该是pending
    for ep in data["episodes"]:
        ep_id = ep["episode_id"]
        assert state_manager.get_episode_status(ep_id) == STATUS_PENDING
    
    # tracks_used应该为空
    used_tracks = state_manager.get_all_used_tracks(include_pending=True)
    assert len(used_tracks) == 0
    
    # images_used应该为空
    schedule = state_manager._load()
    assert len(schedule.get("images_used", [])) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


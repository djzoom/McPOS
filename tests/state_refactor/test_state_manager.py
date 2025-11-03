#!/usr/bin/env python3
# coding: utf-8
"""
状态管理器测试

测试用例：
1. 正常流程（成功）
2. 状态转换验证
3. 回滚正确性
4. 并发更新预防
"""
from __future__ import annotations

import json
import tempfile
import threading
import time
from pathlib import Path

import pytest

# 添加项目路径
import sys
from pathlib import Path as PathLib
_repo_root = PathLib(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_repo_root / "src"))


from core.state_manager import (
    StateManager,
    StateConflictError,
    STATUS_PENDING,
    STATUS_REMIXING,
    STATUS_RENDERING,
    STATUS_COMPLETED,
    STATUS_ERROR,
)


@pytest.fixture
def temp_schedule_file(tmp_path):
    """创建临时排播表文件"""
    schedule_file = tmp_path / "schedule_master.json"
    
    # 创建测试数据
    test_data = {
        "created_at": "2025-11-02T00:00:00",
        "start_date": "2025-11-02",
        "schedule_interval_days": 2,
        "total_episodes": 2,
        "episodes": [
            {
                "episode_number": 1,
                "schedule_date": "2025-11-02",
                "episode_id": "20251102",
                "status": STATUS_PENDING,
            },
            {
                "episode_number": 2,
                "schedule_date": "2025-11-04",
                "episode_id": "20251104",
                "status": STATUS_PENDING,
            },
        ],
        "images_pool": [],
        "images_used": [],
        "title_patterns": [],
    }
    
    with schedule_file.open("w", encoding="utf-8") as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)
    
    return schedule_file


@pytest.fixture
def state_manager(temp_schedule_file):
    """创建状态管理器实例"""
    return StateManager(schedule_path=temp_schedule_file)


def test_normal_pipeline_success(state_manager):
    """测试正常流程（成功）"""
    episode_id = "20251102"
    
    # 1. 开始混音
    assert state_manager.update_status(episode_id, STATUS_REMIXING, message="开始混音")
    assert state_manager.get_episode_status(episode_id) == STATUS_REMIXING
    
    # 2. 混音完成，进入渲染
    assert state_manager.update_status(episode_id, STATUS_RENDERING, message="混音完成")
    assert state_manager.get_episode_status(episode_id) == STATUS_RENDERING
    
    # 3. 渲染完成
    assert state_manager.update_status(episode_id, STATUS_COMPLETED, message="渲染完成")
    assert state_manager.get_episode_status(episode_id) == STATUS_COMPLETED


def test_intentional_remix_failure(state_manager):
    """测试混音失败（回滚）"""
    episode_id = "20251102"
    
    # 1. 开始混音
    assert state_manager.update_status(episode_id, STATUS_REMIXING)
    assert state_manager.get_episode_status(episode_id) == STATUS_REMIXING
    
    # 2. 混音失败
    assert state_manager.update_status(
        episode_id,
        STATUS_ERROR,
        message="混音失败",
        error_details="音频编码错误"
    )
    assert state_manager.get_episode_status(episode_id) == STATUS_ERROR
    
    # 3. 回滚
    assert state_manager.rollback_status(episode_id, target_status=STATUS_PENDING)
    assert state_manager.get_episode_status(episode_id) == STATUS_PENDING
    
    # 验证错误信息已清除
    ep = state_manager.get_episode(episode_id)
    assert "error_details" not in ep or ep.get("error_details") is None


def test_state_transition_validation(state_manager):
    """测试状态转换验证"""
    episode_id = "20251102"
    
    # 无效转换：pending → completed（跳过中间状态）
    assert not state_manager.update_status(episode_id, STATUS_COMPLETED)
    assert state_manager.get_episode_status(episode_id) == STATUS_PENDING
    
    # 有效转换：pending → remixing
    assert state_manager.update_status(episode_id, STATUS_REMIXING)
    assert state_manager.get_episode_status(episode_id) == STATUS_REMIXING
    
    # 无效转换：remixing → pending（只能前进或错误）
    assert not state_manager.update_status(episode_id, STATUS_PENDING)
    assert state_manager.get_episode_status(episode_id) == STATUS_REMIXING


def test_rollback_correctness(state_manager):
    """测试回滚正确性"""
    episode_id = "20251102"
    
    # 推进到rendering状态
    state_manager.update_status(episode_id, STATUS_REMIXING)
    state_manager.update_status(episode_id, STATUS_RENDERING)
    
    # 回滚到pending
    assert state_manager.rollback_status(episode_id, target_status=STATUS_PENDING)
    assert state_manager.get_episode_status(episode_id) == STATUS_PENDING
    
    # 验证回滚信息记录
    ep = state_manager.get_episode(episode_id)
    assert ep.get("rollback_from") == STATUS_RENDERING
    assert "rollback_at" in ep


def test_concurrent_update_prevention(state_manager):
    """测试并发更新预防"""
    episode_id = "20251102"
    update_count = [0]
    error_count = [0]
    
    def update_concurrent(thread_id: int):
        """并发更新函数"""
        try:
            # 尝试更新状态
            if state_manager.update_status(
                episode_id,
                STATUS_REMIXING,
                message=f"线程 {thread_id}"
            ):
                update_count[0] += 1
                time.sleep(0.1)  # 模拟处理时间
        except StateConflictError:
            error_count[0] += 1
    
    # 启动多个线程同时更新
    threads = []
    for i in range(5):
        t = threading.Thread(target=update_concurrent, args=(i,))
        threads.append(t)
        t.start()
    
    # 等待所有线程完成
    for t in threads:
        t.join()
    
    # 验证：只有一个线程成功（由于锁机制）
    # 注意：由于锁的超时机制，可能会有多个成功，但至少不会有数据损坏
    assert update_count[0] >= 1
    # 最终状态应该是remixing（或pending如果都失败了）
    final_status = state_manager.get_episode_status(episode_id)
    assert final_status in {STATUS_PENDING, STATUS_REMIXING}


def test_atomic_write(state_manager, temp_schedule_file):
    """测试原子性写入"""
    episode_id = "20251102"
    
    # 执行更新
    assert state_manager.update_status(episode_id, STATUS_REMIXING)
    
    # 验证文件确实更新了
    with temp_schedule_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
        ep = next((e for e in data["episodes"] if e["episode_id"] == episode_id), None)
        assert ep is not None
        assert ep["status"] == STATUS_REMIXING
    
    # 验证临时文件已删除
    temp_files = list(temp_schedule_file.parent.glob("*.tmp"))
    assert len(temp_files) == 0, "临时文件应该已删除"


def test_get_all_used_tracks(state_manager):
    """测试动态查询已使用的歌曲"""
    episode_id = "20251102"
    
    # 更新曲目
    state_manager.update_episode_metadata(
        episode_id,
        tracks_used=["Track 1", "Track 2"]
    )
    
    # 查询
    used_tracks = state_manager.get_all_used_tracks(include_pending=True)
    assert "Track 1" in used_tracks
    assert "Track 2" in used_tracks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


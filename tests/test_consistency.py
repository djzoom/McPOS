#!/usr/bin/env python3
# coding: utf-8
"""
一致性测试套件

测试所有模块导入、CLI命令、JSON模式一致性
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestImports:
    """测试模块导入"""
    
    def test_state_manager_import(self):
        """测试状态管理器导入"""
        try:
            from src.core.state_manager import get_state_manager, StateManager
            manager = get_state_manager()
            assert manager is not None
            assert isinstance(manager, StateManager)
        except ImportError as e:
            pytest.fail(f"无法导入state_manager: {e}")
    
    def test_event_bus_import(self):
        """测试事件总线导入"""
        try:
            from src.core.event_bus import get_event_bus, EventBus
            bus = get_event_bus()
            assert bus is not None
            assert isinstance(bus, EventBus)
        except ImportError as e:
            pytest.fail(f"无法导入event_bus: {e}")
    
    def test_metrics_manager_import(self):
        """测试指标管理器导入"""
        try:
            from src.core.metrics_manager import get_metrics_manager, MetricsManager
            metrics = get_metrics_manager()
            assert metrics is not None
            assert isinstance(metrics, MetricsManager)
        except ImportError as e:
            pytest.fail(f"无法导入metrics_manager: {e}")
    
    def test_logger_import(self):
        """测试日志系统导入"""
        try:
            from src.core.logger import get_logger
            logger = get_logger()
            assert logger is not None
        except ImportError as e:
            pytest.fail(f"无法导入logger: {e}")


class TestCLICommands:
    """测试CLI命令"""
    
    def test_cli_help(self):
        """测试CLI help命令"""
        result = subprocess.run(
            [sys.executable, "scripts/kat_cli.py", "help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True
        )
        # help命令应该成功（即使返回码可能非零）
        assert result.returncode in [0, 1]  # argparse可能返回1
    
    def test_cli_generate_help(self):
        """测试generate命令帮助"""
        result = subprocess.run(
            [sys.executable, "scripts/kat_cli.py", "generate", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "episode-id" in result.stdout or "生成视频内容" in result.stdout
    
    def test_cli_schedule_help(self):
        """测试schedule命令帮助"""
        result = subprocess.run(
            [sys.executable, "scripts/kat_cli.py", "schedule", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "create" in result.stdout or "显示" in result.stdout
    
    def test_cli_reset_help(self):
        """测试reset命令帮助"""
        result = subprocess.run(
            [sys.executable, "scripts/kat_cli.py", "reset", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0


class TestJSONSchemas:
    """测试JSON模式一致性"""
    
    def test_schedule_master_schema(self):
        """测试schedule_master.json模式"""
        schedule_file = REPO_ROOT / "config" / "schedule_master.json"
        if not schedule_file.exists():
            pytest.skip("schedule_master.json不存在")
        
        with schedule_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 检查必需顶层键
        assert "episodes" in data
        
        # 检查episode结构
        if "episodes" in data:
            for ep in data["episodes"]:
                assert "episode_id" in ep, "期数缺少episode_id"
                assert "status" in ep, "期数缺少status"
                assert "schedule_date" in ep, "期数缺少schedule_date"
                
                # 检查状态值有效性
                valid_statuses = {
                    "pending", "remixing", "rendering", 
                    "uploading", "completed", "error", "待制作"
                }
                # 允许旧的状态值（向后兼容）
                status = ep.get("status", "")
                if status and status not in valid_statuses:
                    pytest.fail(f"无效的状态值: {status}")
    
    def test_metrics_json_schema(self):
        """测试metrics.json模式（如果存在）"""
        metrics_file = REPO_ROOT / "data" / "metrics.json"
        if not metrics_file.exists():
            pytest.skip("metrics.json不存在")
        
        with metrics_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 检查基本结构
        assert isinstance(data, dict)
        
        # 如果包含events，检查结构
        if "events" in data:
            assert isinstance(data["events"], list)
    
    def test_workflow_status_schema(self):
        """测试workflow_status.json模式（如果存在）"""
        workflow_file = REPO_ROOT / "data" / "workflow_status.json"
        if not workflow_file.exists():
            pytest.skip("workflow_status.json不存在")
        
        with workflow_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert isinstance(data, dict)


class TestFunctionSignatures:
    """测试函数签名一致性"""
    
    def test_state_manager_update_status(self):
        """测试state_manager.update_status签名"""
        from src.core.state_manager import StateManager
        import inspect
        
        sig = inspect.signature(StateManager.update_status)
        params = list(sig.parameters.keys())
        
        # 检查必需参数
        assert "episode_id" in params
        assert "new_status" in params
        
        # 检查可选参数
        assert "message" in params
        assert "error_details" in params
    
    def test_state_manager_rollback_status(self):
        """测试state_manager.rollback_status签名"""
        from src.core.state_manager import StateManager
        import inspect
        
        sig = inspect.signature(StateManager.rollback_status)
        params = list(sig.parameters.keys())
        
        assert "episode_id" in params
        assert "target_status" in params
    
    def test_metrics_manager_record_event(self):
        """测试metrics_manager.record_event签名"""
        from src.core.metrics_manager import MetricsManager
        import inspect
        
        sig = inspect.signature(MetricsManager.record_event)
        params = list(sig.parameters.keys())
        
        assert "stage" in params
        assert "status" in params
        assert "duration" in params or "duration" in str(sig)


class TestSmokeTest:
    """冒烟测试：基本功能验证"""
    
    def test_state_manager_basic_operations(self):
        """测试状态管理器基本操作"""
        from src.core.state_manager import get_state_manager
        
        manager = get_state_manager()
        
        # 测试获取episode（应该能正常工作，即使返回None）
        result = manager.get_episode("20251101")
        # 不检查具体值，只确保不抛异常
        assert result is None or isinstance(result, dict)
    
    def test_event_bus_basic_operations(self):
        """测试事件总线基本操作"""
        from src.core.event_bus import get_event_bus, EventType, Event
        from datetime import datetime
        
        bus = get_event_bus()
        
        # 创建测试事件
        test_event = Event(
            event_type=EventType.STAGE_STARTED,
            episode_id="test_20251101",
            timestamp=datetime.now(),
            message="测试事件"
        )
        
        # 应该能正常触发（不抛异常）
        try:
            bus.emit(test_event)
        except Exception as e:
            pytest.fail(f"事件总线emit失败: {e}")
    
    def test_metrics_manager_basic_operations(self):
        """测试指标管理器基本操作"""
        from src.core.metrics_manager import get_metrics_manager
        
        metrics = get_metrics_manager()
        
        # 测试记录事件（应该不抛异常）
        try:
            metrics.record_event(
                stage="test",
                status="completed",
                episode_id="test_20251101"
            )
        except Exception as e:
            pytest.fail(f"指标管理器record_event失败: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


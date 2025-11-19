"""
统一的事件模型

定义事件类型和事件总线接口，用于向日志、WebSocket 或其他监听者广播。
"""

from __future__ import annotations

from typing import Dict, Any, Callable, List
from datetime import datetime

from .logging import log_info, log_error


# 事件监听器列表
_listeners: List[Callable[[str, Dict[str, Any]], None]] = []


def emit_event(event_type: str, data: Dict[str, Any]) -> None:
    """
    发出一个事件
    
    Args:
        event_type: 事件类型，如 "stage_started", "stage_finished", "episode_failed"
        data: 事件数据字典
    """
    event = {
        "type": event_type,
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }
    
    # 通过 McPOS logging boundary 记录事件
    log_info(f"[event] {event_type}: {event}")
    
    # 通知所有监听器
    for listener in _listeners:
        try:
            listener(event_type, data)
        except Exception as e:  # noqa: BLE001
            log_error(f"[event] Error in event listener: {e}")


def register_listener(listener: Callable[[str, Dict[str, Any]], None]) -> None:
    """
    注册事件监听器
    
    Args:
        listener: 接收 (event_type, data) 的回调函数
    """
    _listeners.append(listener)


def unregister_listener(listener: Callable[[str, Dict[str, Any]], None]) -> None:
    """
    取消注册事件监听器
    """
    if listener in _listeners:
        _listeners.remove(listener)


class EventType:
    """事件类型常量"""
    STAGE_STARTED = "stage_started"
    STAGE_FINISHED = "stage_finished"
    STAGE_FAILED = "stage_failed"
    EPISODE_STARTED = "episode_started"
    EPISODE_FINISHED = "episode_finished"
    EPISODE_FAILED = "episode_failed"
    RUN_STARTED = "run_started"
    RUN_FINISHED = "run_finished"

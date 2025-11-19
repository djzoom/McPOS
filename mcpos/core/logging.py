"""
McPOS Logging Boundary

所有日志的唯一入口。McPOS 其它代码不允许直接 print、
也不允许直接调用第三方 logger。

将来要接 Sentry / JSON log / WebSocket 通知，只改这一层。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..models import StageName


@dataclass
class StageEvent:
    """结构化阶段事件，用于未来接入 UI / Sentry / WebSocket"""
    channel_id: str
    episode_id: str
    stage: StageName
    status: Literal["queued", "running", "done", "failed"]
    message: str | None = None
    extra: dict[str, Any] | None = None


def log_info(msg: str) -> None:
    """
    McPOS-wide info log.
    
    Future: can be replaced with structured logger / Sentry / file logging.
    """
    print(f"[INFO] {msg}")


def log_warning(msg: str) -> None:
    """
    McPOS-wide warning log.
    """
    print(f"[WARN] {msg}")


def log_error(msg: str) -> None:
    """
    McPOS-wide error log.
    """
    print(f"[ERROR] {msg}")


def log_stage_event(event: StageEvent) -> None:
    """
    结构化阶段事件日志。
    
    用于阶段进度追踪，未来可接入 UI / Sentry / WebSocket。
    今天：只是 print。明天：发送到结构化日志 / WebSocket。
    """
    base = (
        f"[STAGE] {event.channel_id}/{event.episode_id} "
        f"{event.stage.value} -> {event.status}"
    )
    if event.message:
        base += f" ({event.message})"
    print(base)

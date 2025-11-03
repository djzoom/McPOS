#!/usr/bin/env python3
# coding: utf-8
"""
事件总线

设计原则：
1. 轻量级事件分发系统
2. 每个阶段成功/失败时触发事件
3. 事件自动更新 schedule_master.json 状态
4. 支持日志记录
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Set

# 添加src目录到路径（如果尚未添加）
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root / "src") not in sys.path:
    sys.path.insert(0, str(_repo_root / "src" / "core"))

try:
    from state_manager import (
        StateManager,
        STATUS_COMPLETED,
        STATUS_ERROR,
        STATUS_PENDING,
        STATUS_REMIXING,
        STATUS_RENDERING,
        get_state_manager,
    )
except ImportError:
    # 如果导入失败，定义占位符（向后兼容）
    STATUS_PENDING = "pending"
    STATUS_REMIXING = "remixing"
    STATUS_RENDERING = "rendering"
    STATUS_COMPLETED = "completed"
    STATUS_ERROR = "error"
    
    def get_state_manager():
        return None

# 导入结构化日志
try:
    from logger import get_logger
    structured_logger = get_logger()
    USE_STRUCTURED_LOGGING = True
except ImportError:
    # 回退到标准日志
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    structured_logger = None
    USE_STRUCTURED_LOGGING = False


class EventType(Enum):
    """事件类型"""
    # 阶段事件
    STAGE_STARTED = "stage.started"
    STAGE_COMPLETED = "stage.completed"
    STAGE_FAILED = "stage.failed"
    
    # 具体阶段
    REMIX_STARTED = "remix.started"
    REMIX_COMPLETED = "remix.completed"
    REMIX_FAILED = "remix.failed"
    
    VIDEO_RENDER_STARTED = "video.render.started"
    VIDEO_RENDER_COMPLETED = "video.render.completed"
    VIDEO_RENDER_FAILED = "video.render.failed"
    
    YOUTUBE_ASSETS_GENERATED = "youtube.assets.generated"
    YOUTUBE_ASSETS_FAILED = "youtube.assets.failed"
    
    # 上传事件
    UPLOAD_STARTED = "upload.started"
    UPLOAD_COMPLETED = "upload.completed"
    UPLOAD_FAILED = "upload.failed"
    
    # 状态更新
    STATUS_UPDATED = "status.updated"
    STATUS_ROLLED_BACK = "status.rolled_back"


@dataclass
class Event:
    """事件对象"""
    event_type: EventType
    episode_id: str
    timestamp: datetime
    message: Optional[str] = None
    error_details: Optional[str] = None
    metadata: Optional[Dict] = None


class EventBus:
    """
    事件总线
    
    负责事件分发和状态更新
    """
    
    def __init__(self):
        self.state_manager = get_state_manager()
        self._subscribers: Dict[EventType, List[Callable[[Event], None]]] = {}
        self._event_history: List[Event] = []
        self._max_history = 100  # 最多保存100个事件
        
        # 集成指标管理器
        try:
            from metrics_manager import get_metrics_manager
            self.metrics_manager = get_metrics_manager()
            self._metrics_available = True
        except ImportError:
            self.metrics_manager = None
            self._metrics_available = False
        
        # 阶段开始时间记录（用于计算耗时）
        self._stage_starts: Dict[str, Dict[str, datetime]] = defaultdict(dict)  # {episode_id: {stage: datetime}}
    
    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """
        订阅事件
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def emit(self, event: Event) -> None:
        """
        触发事件
        
        Args:
            event: 事件对象
        """
        # 记录事件
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
        
        # 记录日志（结构化）
        if USE_STRUCTURED_LOGGING and structured_logger:
            structured_logger.info(
                event_name=event.event_type.value,
                message=event.message or "No message",
                episode_id=event.episode_id,
                metadata=event.metadata
            )
        elif not USE_STRUCTURED_LOGGING:
            logger.info(
                f"[Event] {event.event_type.value} - Episode {event.episode_id}: {event.message or 'No message'}"
            )
        
        # 记录指标
        if self._metrics_available and self.metrics_manager:
            self._record_metrics(event)
        
        # 自动状态更新
        self._auto_update_status(event)
        
        # 通知订阅者
        event_type = event.event_type
        
        # 通知特定事件类型的订阅者
        if event_type in self._subscribers:
            for handler in self._subscribers[event_type]:
                try:
                    handler(event)
                except Exception as e:
                    import traceback
                    error_tb = traceback.format_exc()
                    if USE_STRUCTURED_LOGGING and structured_logger:
                        structured_logger.error(
                            event_name="event.handler.error",
                            message=f"事件处理函数错误: {e}",
                            traceback=error_tb
                        )
                    elif not USE_STRUCTURED_LOGGING:
                        logger.error(f"事件处理函数错误: {e}", exc_info=True)
        
        # 通知通用阶段事件订阅者
        if event_type in [EventType.STAGE_STARTED, EventType.STAGE_COMPLETED, EventType.STAGE_FAILED]:
            generic_type = event_type
            if generic_type in self._subscribers:
                for handler in self._subscribers[generic_type]:
                    try:
                        handler(event)
                    except Exception as e:
                        logger.error(f"事件处理函数错误: {e}", exc_info=True)
    
    def _auto_update_status(self, event: Event) -> None:
        """
        根据事件自动更新状态
        
        Args:
            event: 事件对象
        """
        # 如果state_manager未初始化，跳过状态更新（静默失败）
        if not self.state_manager:
            return
        
        episode_id = event.episode_id
        event_type = event.event_type
        
        # 导入STATUS_UPLOADING
        try:
            from state_manager import STATUS_UPLOADING
        except ImportError:
            STATUS_UPLOADING = "uploading"
        
        # 状态映射：事件类型 → 状态
        status_map = {
            EventType.REMIX_STARTED: STATUS_REMIXING,
            EventType.REMIX_COMPLETED: STATUS_RENDERING,  # 混音完成后进入渲染阶段
            EventType.REMIX_FAILED: STATUS_ERROR,
            
            EventType.VIDEO_RENDER_STARTED: STATUS_RENDERING,
            EventType.VIDEO_RENDER_COMPLETED: STATUS_UPLOADING,  # 视频渲染完成后进入上传阶段
            EventType.VIDEO_RENDER_FAILED: STATUS_ERROR,
            
            EventType.YOUTUBE_ASSETS_GENERATED: None,  # 不改变状态
            EventType.YOUTUBE_ASSETS_FAILED: STATUS_ERROR,
            
            EventType.UPLOAD_STARTED: STATUS_UPLOADING,
            EventType.UPLOAD_COMPLETED: STATUS_COMPLETED,  # 上传完成 = 最终完成
            EventType.UPLOAD_FAILED: STATUS_ERROR,
        }
        
        new_status = status_map.get(event_type)
        
        if new_status:
            if new_status == STATUS_ERROR:
                # 错误状态
                self.state_manager.update_status(
                    episode_id=episode_id,
                    new_status=STATUS_ERROR,
                    message=event.message,
                    error_details=event.error_details or str(event.error_details)
                )
            else:
                # 正常状态更新
                self.state_manager.update_status(
                    episode_id=episode_id,
                    new_status=new_status,
                    message=event.message
                )
        elif event_type == EventType.STAGE_FAILED:
            # 通用失败事件
            self.state_manager.update_status(
                episode_id=episode_id,
                new_status=STATUS_ERROR,
                message=event.message,
                error_details=event.error_details or "未知错误"
            )
    
    def emit_stage_started(self, episode_id: str, stage_name: str) -> None:
        """触发阶段开始事件"""
        event = Event(
            event_type=EventType.STAGE_STARTED,
            episode_id=episode_id,
            timestamp=datetime.now(),
            message=f"阶段开始: {stage_name}",
            metadata={"stage": stage_name}
        )
        self.emit(event)
    
    def emit_stage_completed(self, episode_id: str, stage_name: str) -> None:
        """触发阶段完成事件"""
        event = Event(
            event_type=EventType.STAGE_COMPLETED,
            episode_id=episode_id,
            timestamp=datetime.now(),
            message=f"阶段完成: {stage_name}",
            metadata={"stage": stage_name}
        )
        self.emit(event)
    
    def emit_stage_failed(self, episode_id: str, stage_name: str, error: str) -> None:
        """触发阶段失败事件"""
        event = Event(
            event_type=EventType.STAGE_FAILED,
            episode_id=episode_id,
            timestamp=datetime.now(),
            message=f"阶段失败: {stage_name}",
            error_details=error,
            metadata={"stage": stage_name}
        )
        self.emit(event)
    
    def emit_remix_started(self, episode_id: str) -> None:
        """触发混音开始事件"""
        event = Event(
            event_type=EventType.REMIX_STARTED,
            episode_id=episode_id,
            timestamp=datetime.now(),
            message="开始混音"
        )
        self.emit(event)
    
    def emit_remix_completed(self, episode_id: str) -> None:
        """触发混音完成事件"""
        event = Event(
            event_type=EventType.REMIX_COMPLETED,
            episode_id=episode_id,
            timestamp=datetime.now(),
            message="混音完成"
        )
        self.emit(event)
    
    def emit_remix_failed(self, episode_id: str, error: str) -> None:
        """触发混音失败事件"""
        event = Event(
            event_type=EventType.REMIX_FAILED,
            episode_id=episode_id,
            timestamp=datetime.now(),
            message="混音失败",
            error_details=error
        )
        self.emit(event)
    
    def emit_video_render_started(self, episode_id: str) -> None:
        """触发视频渲染开始事件"""
        event = Event(
            event_type=EventType.VIDEO_RENDER_STARTED,
            episode_id=episode_id,
            timestamp=datetime.now(),
            message="开始视频渲染"
        )
        self.emit(event)
    
    def emit_video_render_completed(self, episode_id: str) -> None:
        """触发视频渲染完成事件"""
        event = Event(
            event_type=EventType.VIDEO_RENDER_COMPLETED,
            episode_id=episode_id,
            timestamp=datetime.now(),
            message="视频渲染完成"
        )
        self.emit(event)
    
    def emit_video_render_failed(self, episode_id: str, error: str) -> None:
        """触发视频渲染失败事件"""
        event = Event(
            event_type=EventType.VIDEO_RENDER_FAILED,
            episode_id=episode_id,
            timestamp=datetime.now(),
            message="视频渲染失败",
            error_details=error
        )
        self.emit(event)
    
    def emit_upload_started(self, episode_id: str) -> None:
        """触发上传开始事件"""
        event = Event(
            event_type=EventType.UPLOAD_STARTED,
            episode_id=episode_id,
            timestamp=datetime.now(),
            message="开始上传到YouTube"
        )
        self.emit(event)
    
    def emit_upload_completed(self, episode_id: str, video_id: str, video_url: str) -> None:
        """触发上传完成事件"""
        event = Event(
            event_type=EventType.UPLOAD_COMPLETED,
            episode_id=episode_id,
            timestamp=datetime.now(),
            message=f"上传完成: {video_url}",
            metadata={"video_id": video_id, "video_url": video_url}
        )
        self.emit(event)
    
    def emit_upload_failed(self, episode_id: str, error: str) -> None:
        """触发上传失败事件"""
        event = Event(
            event_type=EventType.UPLOAD_FAILED,
            episode_id=episode_id,
            timestamp=datetime.now(),
            message="上传失败",
            error_details=error
        )
        self.emit(event)
    
    def emit_youtube_assets_generated(self, episode_id: str) -> None:
        """触发YouTube资源生成事件"""
        event = Event(
            event_type=EventType.YOUTUBE_ASSETS_GENERATED,
            episode_id=episode_id,
            timestamp=datetime.now(),
            message="YouTube资源生成完成"
        )
        self.emit(event)
    
    def emit_youtube_assets_failed(self, episode_id: str, error: str) -> None:
        """触发YouTube资源生成失败事件"""
        event = Event(
            event_type=EventType.YOUTUBE_ASSETS_FAILED,
            episode_id=episode_id,
            timestamp=datetime.now(),
            message="YouTube资源生成失败",
            error_details=error
        )
        self.emit(event)
    
    def _record_metrics(self, event: Event) -> None:
        """记录事件到指标管理器"""
        if not self.metrics_manager:
            return
        
        episode_id = event.episode_id
        event_type = event.event_type
        
        # 确定阶段名称
        stage_map = {
            EventType.REMIX_STARTED: "remix",
            EventType.REMIX_COMPLETED: "remix",
            EventType.REMIX_FAILED: "remix",
            EventType.VIDEO_RENDER_STARTED: "render",
            EventType.VIDEO_RENDER_COMPLETED: "render",
            EventType.VIDEO_RENDER_FAILED: "render",
            EventType.YOUTUBE_ASSETS_GENERATED: "youtube",
            EventType.YOUTUBE_ASSETS_FAILED: "youtube",
        }
        
        stage = stage_map.get(event_type, "unknown")
        
        # 确定状态
        if "started" in event_type.value:
            status = "started"
            # 记录开始时间
            if episode_id:
                self._stage_starts[episode_id][stage] = event.timestamp
                self.metrics_manager.record_stage_start(episode_id, stage)
        elif "completed" in event_type.value or "generated" in event_type.value:
            status = "completed"
        elif "failed" in event_type.value:
            status = "failed"
        else:
            status = "unknown"
        
        # 计算耗时（如果有开始时间记录）
        duration = None
        if status in ("completed", "failed") and episode_id and stage in self._stage_starts.get(episode_id, {}):
            start_time = self._stage_starts[episode_id][stage]
            duration = (event.timestamp - start_time).total_seconds()
            # 清除开始时间记录
            del self._stage_starts[episode_id][stage]
            if not self._stage_starts[episode_id]:
                del self._stage_starts[episode_id]
        
        # 记录到指标管理器
        self.metrics_manager.record_event(
            stage=stage,
            status=status,
            duration=duration,
            episode_id=episode_id,
            error_message=event.error_details if status == "failed" else None
        )
    
    def get_event_history(self, episode_id: Optional[str] = None, limit: int = 10) -> List[Event]:
        """
        获取事件历史
        
        Args:
            episode_id: 可选，筛选特定期数
            limit: 返回数量限制
        
        Returns:
            事件列表
        """
        events = self._event_history
        
        if episode_id:
            events = [e for e in events if e.episode_id == episode_id]
        
        return events[-limit:]


# 全局事件总线单例
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


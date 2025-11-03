"""
WebSocket Routes for Real-time Updates

Provides WebSocket endpoints for real-time status updates and event streaming.
Uses enhanced ConnectionManager with heartbeat and cleanup.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict
from datetime import datetime
import asyncio
import json
import random

from core.websocket_manager import ConnectionManager

router = APIRouter()

# Global connection managers with enhanced features
status_manager = ConnectionManager(heartbeat_interval=5, timeout_seconds=15)
events_manager = ConnectionManager(heartbeat_interval=5, timeout_seconds=15)

# Track last event for status broadcast
_last_event = None


def generate_mock_channel_status(channel_id: str) -> Dict:
    """Generate mock channel status update"""
    statuses = ["pending", "processing", "uploading", "completed", "failed"]
    status = random.choice(statuses)
    
    return {
        "channel_id": channel_id,
        "status": status,
        "progress": random.randint(0, 100) if status in ["processing", "uploading"] else None,
        "updated_at": datetime.utcnow().isoformat(),
    }


def generate_mock_event() -> Dict:
    """Generate mock event for event stream"""
    event_types = ["INFO", "WARNING", "ERROR", "SUCCESS"]
    stages = ["remixing", "rendering", "uploading", "validation"]
    channels = [f"CH-{i:03d}" for i in range(1, 11)]
    
    event_type = random.choice(event_types)
    channel = random.choice(channels)
    stage = random.choice(stages)
    
    messages = {
        "INFO": [
            f"Channel {channel} started {stage}",
            f"Channel {channel} completed {stage}",
            f"Channel {channel} queued new task",
        ],
        "WARNING": [
            f"Channel {channel} {stage} taking longer than expected",
            f"Channel {channel} queue backup detected",
        ],
        "ERROR": [
            f"Upload failed on Channel {channel}",
            f"Channel {channel} {stage} error occurred",
        ],
        "SUCCESS": [
            f"Channel {channel} successfully uploaded",
            f"Channel {channel} task completed",
        ],
    }
    
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": event_type,
        "message": random.choice(messages[event_type]),
        "channel_id": channel,
        "stage": stage,
    }
    
    # Update last event
    global _last_event
    _last_event = event
    
    return event


async def broadcast_status_updates():
    """Periodically broadcast status updates with queue_status, success_rate, last_event"""
    await status_manager.start_heartbeat()
    await status_manager.start_cleanup()
    
    while True:
        try:
            # Calculate queue status
            total_channels = 10
            active_channels = random.randint(5, 8)
            queue_status = {
                "total": total_channels,
                "active": active_channels,
                "pending": random.randint(0, 3),
                "processing": random.randint(1, 4),
                "completed": random.randint(2, 6),
                "failed": random.randint(0, 2),
            }
            
            # Calculate success rate
            total_completed = queue_status["completed"] + queue_status["failed"]
            success_rate = (
                (queue_status["completed"] / total_completed * 100)
                if total_completed > 0
                else 0.0
            )
            
            # Get last event
            last_event = _last_event or {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "message": "System initialized",
            }
            
            # Broadcast status update
            message = {
                "type": "status_update",
                "data": {
                    "queue_status": queue_status,
                    "success_rate": round(success_rate, 2),
                    "last_event": last_event,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }
            
            await status_manager.broadcast(message)
            await asyncio.sleep(10)  # Broadcast every 10 seconds
        except Exception as e:
            import logging
            logging.error(f"Error in status broadcast: {e}")
            await asyncio.sleep(5)


async def broadcast_events():
    """Periodically broadcast events"""
    await events_manager.start_heartbeat()
    await events_manager.start_cleanup()
    
    while True:
        try:
            event = generate_mock_event()
            message = {
                "type": "event",
                "data": event,
            }
            
            await events_manager.broadcast(message)
            # Random interval between 3-8 seconds for more realistic event stream
            await asyncio.sleep(random.uniform(3, 8))
        except Exception as e:
            import logging
            logging.error(f"Error in event broadcast: {e}")
            await asyncio.sleep(5)


# Global version counter for event deduplication
_event_version = 0

def _get_next_version() -> int:
    """Get next event version number"""
    global _event_version
    _event_version += 1
    return _event_version

# T2R Event Broadcasting
def generate_t2r_event(
    event_type: str, 
    data: Dict, 
    level: str = "info"
) -> Dict:
    """
    Generate T2R-specific event with unified schema.
    
    Schema:
    {
        "type": "t2r_{event_type}",
        "version": int,
        "ts": "ISO8601 timestamp",
        "level": "info|warn|error",
        "data": {...}
    }
    """
    return {
        "type": f"t2r_{event_type}",
        "version": _get_next_version(),
        "ts": datetime.utcnow().isoformat(),
        "level": level,
        "data": data,
    }


async def broadcast_t2r_event(
    event_type: str, 
    data: Dict,
    level: str = "info"
):
    """
    Broadcast T2R event to all connected clients.
    
    Args:
        event_type: Event type (e.g., "scan_progress", "fix_applied")
        data: Event data payload
        level: Event level ("info", "warn", "error")
    """
    message = generate_t2r_event(event_type, data, level)
    await status_manager.broadcast(message)
    await events_manager.broadcast(message)


# Background tasks
status_task = None
events_task = None


@router.websocket("/ws/status")
async def websocket_status_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time status updates"""
    connection_id = await status_manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            # Handle message (ping/pong)
            await status_manager.handle_message(connection_id, data)
    except WebSocketDisconnect:
        status_manager.disconnect(connection_id)
    except Exception as e:
        import logging
        logging.error(f"Error in status WebSocket: {e}")
        status_manager.disconnect(connection_id)


@router.websocket("/ws/events")
async def websocket_events_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time event streaming"""
    connection_id = await events_manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            # Handle message (ping/pong)
            await events_manager.handle_message(connection_id, data)
    except WebSocketDisconnect:
        events_manager.disconnect(connection_id)
    except Exception as e:
        import logging
        logging.error(f"Error in events WebSocket: {e}")
        events_manager.disconnect(connection_id)


async def start_broadcast_tasks():
    """Start background broadcast tasks"""
    global status_task, events_task
    if status_task is None:
        status_task = asyncio.create_task(broadcast_status_updates())
    if events_task is None:
        events_task = asyncio.create_task(broadcast_events())

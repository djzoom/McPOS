"""
Task Control Routes

API endpoints for task control (start, pause, retry).
Supports single channel and batch operations.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

router = APIRouter()


class TaskControlRequest(BaseModel):
    channel_id: Optional[str] = None
    action: str  # "start", "pause", "retry", "stop", "retry_failed"
    channels: Optional[List[str]] = None  # For batch operations


class TaskControlResponse(BaseModel):
    status: str
    message: str
    channel_id: Optional[str] = None
    channels: Optional[List[str]] = None
    timestamp: str


@router.post("/api/task/control", response_model=TaskControlResponse)
async def control_task(request: TaskControlRequest):
    """
    Control task for a channel or batch of channels
    
    Actions:
    - start: Start a new task
    - pause: Pause current task
    - retry: Retry failed task
    - stop: Stop current task
    - retry_failed: Retry failed tasks for multiple channels (requires 'channels' field)
    
    Examples:
    - Single channel: {"channel_id": "CH-001", "action": "start"}
    - Batch retry: {"action": "retry_failed", "channels": ["CH-006", "CH-009"]}
    """
    valid_actions = ["start", "pause", "retry", "stop", "retry_failed"]
    
    if request.action not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action. Must be one of: {', '.join(valid_actions)}"
        )
    
    # Batch operation validation
    if request.action == "retry_failed":
        if not request.channels or len(request.channels) == 0:
            raise HTTPException(
                status_code=400,
                detail="'retry_failed' action requires 'channels' field with at least one channel ID"
            )
        
        # Process batch retry
        processed_channels = []
        for channel_id in request.channels:
            # In real implementation, validate channel exists and has failed tasks
            processed_channels.append(channel_id)
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Batch retry for channels: {request.channels}")
        
        return TaskControlResponse(
            status="ok",
            message=f"Retry initiated for {len(processed_channels)} channels",
            channels=processed_channels,
            timestamp=datetime.utcnow().isoformat()
        )
    
    # Single channel operation validation
    if not request.channel_id:
        raise HTTPException(
            status_code=400,
            detail="'channel_id' is required for single channel operations"
        )
    
    # Mock implementation - just log and return success
    action_messages = {
        "start": f"Channel {request.channel_id} task started",
        "pause": f"Channel {request.channel_id} task paused",
        "retry": f"Channel {request.channel_id} task retry initiated",
        "stop": f"Channel {request.channel_id} task stopped",
    }
    
    message = action_messages.get(request.action, "Action processed")
    
    # In real implementation, this would:
    # 1. Validate channel exists
    # 2. Check current task state
    # 3. Execute the action (update Redis, database, etc.)
    # 4. Trigger WebSocket notification
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Task control: {request.action} for {request.channel_id}")
    
    return TaskControlResponse(
        status="ok",
        message=message,
        channel_id=request.channel_id,
        timestamp=datetime.utcnow().isoformat()
    )

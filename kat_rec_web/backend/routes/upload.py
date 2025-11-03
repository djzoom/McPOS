"""
Upload Routes

API endpoints for upload task management.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from services.redis_service import RedisService
from services.database import get_db
from services.channel_service import ChannelService
from sqlalchemy.ext.asyncio import AsyncSession
import os

router = APIRouter()

# Initialize Redis service
redis_service = RedisService(os.getenv("REDIS_URL", "redis://localhost:6379"))


class UploadTaskRequest(BaseModel):
    """Request model for upload task"""
    episode_id: str
    video_file: str
    title: Optional[str] = None
    description: Optional[str] = None
    privacy: Optional[str] = "unlisted"


@router.post("/upload")
async def enqueue_upload(
    task: UploadTaskRequest,
    channel_id: Optional[str] = Query(None, description="Channel ID (defaults to current)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Enqueue an upload task
    
    Adds a video upload task to the Redis queue.
    Future: supports multi-channel uploads via channel_id.
    """
    # Get channel (validate it exists)
    channel_service = ChannelService(db)
    channel = await channel_service.get_channel(channel_id)
    
    # Enqueue task
    task_data = {
        "episode_id": task.episode_id,
        "video_file": task.video_file,
        "title": task.title,
        "description": task.description,
        "privacy": task.privacy or "unlisted",
        "created_at": datetime.utcnow().isoformat()
    }
    
    task_id = await redis_service.enqueue_upload(channel.id, task_data)
    
    return {
        "task_id": task_id,
        "channel_id": channel.id,
        "status": "queued",
        "message": f"Upload task {task.episode_id} queued for channel {channel.id}"
    }


@router.get("/upload/queue")
async def get_upload_queue():
    """
    Get upload queue status
    
    Returns current queue length and status.
    """
    queue_status = await redis_service.get_queue_status()
    return queue_status


"""
Status Routes

API endpoints for system health and status.
"""
from fastapi import APIRouter
from services.redis_service import RedisService
from datetime import datetime
import os

router = APIRouter()

# Initialize Redis service
redis_service = RedisService(os.getenv("REDIS_URL", "redis://localhost:6379"))


@router.get("/status")
async def get_status():
    """
    Get system status
    
    Returns system heartbeat, Redis connection status, and queue info.
    """
    redis_connected = await redis_service.ping()
    queue_status = await redis_service.get_queue_status()
    
    return {
        "status": "running",
        "service": "Kat Rec Web Control Center",
        "version": "1.0.0",
        "redis": {
            "connected": redis_connected,
            "queue": queue_status
        },
        "timestamp": datetime.utcnow().isoformat()
    }


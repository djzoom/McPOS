"""
Episodes and Channel Routes for T2R

Provides endpoints compatible with main dashboard components.
"""
from fastapi import APIRouter
from typing import Dict, List
from datetime import datetime
import logging
from pathlib import Path

from ..services.schedule_service import load_schedule_master

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/episodes")
async def list_episodes() -> Dict:
    """
    List all episodes from schedule_master.json.
    
    Compatible with Mission Control component format.
    
    Returns:
        {
            "episodes": [
                {
                    "episode_id": str,
                    "episode_number": int (optional),
                    "schedule_date": str,
                    "status": str,
                    "image_path": str (optional),
                    "output_file": str (optional),
                    "locked_at": str (optional),
                    "lock_reason": str (optional)
                }
            ],
            "total": int,
            "timestamp": str
        }
    """
    try:
        schedule = load_schedule_master()
        if not schedule:
            return {
                "episodes": [],
                "total": 0,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        episodes_list = schedule.get("episodes", [])
        
        # Map T2R status to Mission Control status
        def map_status(t2r_status: str) -> str:
            status_map = {
                "待制作": "pending",
                "已完成": "completed",
                "已锁定": "completed",  # Locked episodes are considered completed
                "排播完毕待播出": "completed",
                "error": "error",
                "pending": "pending",
                "remixing": "remixing",
                "rendering": "rendering",
                "uploading": "uploading",
                "completed": "completed",
            }
            return status_map.get(t2r_status, "pending")
        
        # Convert to Mission Control format
        formatted_episodes = []
        for idx, ep in enumerate(episodes_list, 1):
            formatted_episodes.append({
                "episode_id": ep.get("episode_id", ""),
                "episode_number": ep.get("episode_number") or idx,
                "schedule_date": ep.get("schedule_date", ""),
                "status": map_status(ep.get("status", "待制作")),
                "title": ep.get("title"),  # Include title for Schedule Board
                "image_path": ep.get("image_path"),
                "output_file": ep.get("output_file"),
                "locked_at": ep.get("locked_at"),
                "lock_reason": ep.get("lock_reason"),
            })
        
        return {
            "episodes": formatted_episodes,
            "total": len(formatted_episodes),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to list episodes: {e}", exc_info=True)
        return {
            "episodes": [],
            "total": 0,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/channel")
async def get_channel_info() -> Dict:
    """
    Get Kat Rec channel information.
    
    Compatible with Channel Workbench component format.
    
    Returns:
        {
            "id": str,
            "name": str,
            "isActive": bool,
            "nextSchedule": str (optional),
            "queueCount": int,
            "totalEpisodes": int,
            "lockedCount": int
        }
    """
    try:
        schedule = load_schedule_master()
        if not schedule:
            return {
                "id": "kat-rec",
                "name": "Kat Rec",
                "isActive": False,
                "queueCount": 0,
                "totalEpisodes": 0,
                "lockedCount": 0
            }
        
        episodes = schedule.get("episodes", [])
        
        # Find next pending episode (next schedule)
        pending_episodes = [
            ep for ep in episodes 
            if ep.get("status") in ["待制作", "pending"] 
            and ep.get("schedule_date")
        ]
        next_episode = min(pending_episodes, key=lambda x: x.get("schedule_date", ""), default=None) if pending_episodes else None
        
        # Count locked episodes
        locked_count = sum(1 for ep in episodes if ep.get("status") == "已锁定")
        
        return {
            "id": "kat-rec",
            "name": "Kat Rec",
            "isActive": True,  # Always active if schedule exists
            "nextSchedule": next_episode.get("schedule_date") if next_episode else None,
            "queueCount": len(pending_episodes),
            "totalEpisodes": len(episodes),
            "lockedCount": locked_count
        }
    except Exception as e:
        logger.error(f"Failed to get channel info: {e}", exc_info=True)
        return {
            "id": "kat-rec",
            "name": "Kat Rec",
            "isActive": False,
            "queueCount": 0,
            "totalEpisodes": 0,
            "lockedCount": 0,
            "error": str(e)
        }

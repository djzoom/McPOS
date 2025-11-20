"""
State Snapshot API

Provides state snapshots for frontend recovery after refresh.
"""
from typing import Dict, Optional, List
from fastapi import APIRouter, Query
from datetime import datetime
import logging

from ..services.schedule_service import (
    load_schedule_master,
    get_output_dir,
    get_work_cursor_date
)
from ..services.asset_state_registry import get_asset_state_registry, AssetType, AssetState
from ..services.asset_service import get_asset_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/state-snapshot")
async def get_state_snapshot(
    channel_id: Optional[str] = Query(None, description="Channel ID (defaults to default channel)"),
    episode_ids: Optional[str] = Query(None, description="Comma-separated episode IDs (optional, returns all if not provided)")
) -> Dict:
    """
    Get complete state snapshot for episodes.
    
    This endpoint provides a comprehensive snapshot of all episode states,
    including asset states, render status, upload status, etc.
    Useful for frontend recovery after refresh.
    
    Returns:
        {
            "status": "ok",
            "channel_id": str,
            "work_cursor_date": str | null,
            "episodes": [
                {
                    "episode_id": str,
                    "schedule_date": str,
                    "assets": {
                        "playlist": {"state": str, "file_path": str | null, ...},
                        "cover": {"state": str, ...},
                        "audio": {"state": str, ...},
                        "video": {"state": str, ...},
                        ...
                    },
                    "render_status": str,
                    "upload_status": str,
                    "work_cursor_date": str | null,
                    ...
                },
                ...
            ],
            "timestamp": str
        }
    """
    try:
        channel_key = channel_id or "kat_lofi"
        schedule = load_schedule_master(channel_key)
        
        if not schedule:
            return {
                "status": "error",
                "errors": ["Schedule not found"],
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Get work cursor date
        work_cursor_date = get_work_cursor_date(channel_key)
        
        # Get Asset State Registry
        registry = get_asset_state_registry(channel_key)
        
        # Filter episodes if episode_ids provided
        all_episodes = schedule.get("episodes", [])
        if episode_ids:
            requested_ids = [eid.strip() for eid in episode_ids.split(",")]
            episodes = [ep for ep in all_episodes if ep.get("episode_id") in requested_ids]
        else:
            episodes = all_episodes
        
        # Build snapshot for each episode
        episode_snapshots = []
        for episode_data in episodes:
            episode_id = episode_data.get("episode_id")
            if not episode_id:
                continue
            
            # Use AssetService to scan and update assets
            asset_service = get_asset_service(channel_key)
            await asset_service.scan_and_update_episode_assets(episode_id)
            
            # Get asset states from registry
            asset_states = {}
            for asset_type in AssetType:
                asset_state = await registry.get_asset_state(episode_id, asset_type.value)
                if asset_state:
                    asset_states[asset_type.value] = {
                        "state": asset_state.state,
                        "file_path": asset_state.file_path,
                        "checksum": asset_state.checksum,
                        "metadata": asset_state.metadata,
                        "updated_at": asset_state.updated_at,
                        "verified_at": asset_state.verified_at,
                        "error": asset_state.error
                    }
                else:
                    # Fallback to filesystem check
                    assets = episode_data.get("assets", {})
                    asset_path = assets.get(asset_type.value) or assets.get(f"{asset_type.value}_path")
                    if asset_path:
                        asset_states[asset_type.value] = {
                            "state": AssetState.COMPLETE.value,
                            "file_path": asset_path,
                            "updated_at": None,
                            "verified_at": None,
                            "error": None
                        }
                    else:
                        asset_states[asset_type.value] = {
                            "state": AssetState.MISSING.value,
                            "file_path": None,
                            "updated_at": None,
                            "verified_at": None,
                            "error": None
                        }
            
            # Determine render status from ASR
            video_state = asset_states.get(AssetType.VIDEO.value, {}).get("state")
            render_flag_state = asset_states.get(AssetType.RENDER_COMPLETE_FLAG.value, {}).get("state")
            render_status = "complete" if (
                video_state == AssetState.COMPLETE.value and 
                render_flag_state == AssetState.COMPLETE.value
            ) else ("in_progress" if video_state == AssetState.COMPLETE.value else "pending")
            
            # Determine upload status from ASR
            upload_log_state = asset_states.get(AssetType.UPLOAD_LOG.value, {})
            upload_log_metadata = upload_log_state.get("metadata") or {}
            if not isinstance(upload_log_metadata, dict):
                upload_log_metadata = {}
            uploaded = episode_data.get("uploaded", False)
            video_id = upload_log_metadata.get("video_id") or episode_data.get("assets", {}).get("video_id") or episode_data.get("metadata", {}).get("youtubeId")
            upload_status = "complete" if (
                upload_log_state.get("state") == AssetState.VERIFIED.value and video_id
            ) else ("failed" if uploaded and not video_id else "pending")
            
            episode_snapshot = {
                "episode_id": episode_id,
                "schedule_date": episode_data.get("schedule_date"),
                "title": episode_data.get("title"),
                "assets": asset_states,
                "render_status": render_status,
                "upload_status": upload_status,
                "uploaded": uploaded,
                "uploaded_at": uploaded_at,
                "video_id": video_id,
                "work_cursor_date": work_cursor_date
            }
            
            episode_snapshots.append(episode_snapshot)
        
        return {
            "status": "ok",
            "channel_id": channel_key,
            "work_cursor_date": work_cursor_date,
            "episodes": episode_snapshots,
            "total_episodes": len(episode_snapshots),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get state snapshot: {e}", exc_info=True)
        return {
            "status": "error",
            "errors": [str(e)],
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/state-snapshot/episode/{episode_id}")
async def get_episode_state_snapshot(
    episode_id: str,
    channel_id: Optional[str] = Query(None, description="Channel ID (defaults to default channel)")
) -> Dict:
    """
    Get state snapshot for a single episode.
    
    Returns:
        {
            "status": "ok",
            "episode_id": str,
            "assets": {...},
            "render_status": str,
            "upload_status": str,
            ...
        }
    """
    result = await get_state_snapshot(channel_id=channel_id, episode_ids=episode_id)
    
    if result.get("status") != "ok":
        return result
    
    episodes = result.get("episodes", [])
    if not episodes:
        return {
            "status": "error",
            "errors": [f"Episode {episode_id} not found"],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    return {
        "status": "ok",
        **episodes[0],
        "timestamp": datetime.utcnow().isoformat()
    }


"""
Scan and Lock Routes for T2R

Scan schedule, lock published episodes, and build asset usage index.
"""
from fastapi import APIRouter
from typing import Dict
from datetime import datetime
import logging

from ..services.schedule_service import scan_and_lock
from ...routes.websocket import broadcast_t2r_event

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/scan")
async def scan_schedule() -> Dict:
    """
    Scan schedule and output directory, lock published episodes.
    
    Returns:
        {
            "status": "ok",
            "summary": Dict,
            "data": {
                "locked_count": int,
                "new_episodes": int,
                "conflicts": List[Dict],
                "asset_usage": Dict,
                "timestamp": str
            },
            "errors": List[str]
        }
    """
    try:
        # Broadcast scan start
        await broadcast_t2r_event("scan_progress", {
            "stage": "started",
            "message": "Scan started"
        }, level="info")
        
        result = scan_and_lock()
        
        # Broadcast scan completion
        await broadcast_t2r_event("scan_progress", {
            "stage": "completed",
            "locked_count": result.get('locked_count', 0),
            "conflicts": result.get('conflicts', []),
            "message": f"Scan completed: locked {result.get('locked_count', 0)} episodes"
        }, level="info")
        
        logger.info(f"Scan completed: locked {result.get('locked_count', 0)} episodes")
        
        return {
            "status": "ok",
            "summary": {
                "locked_count": result.get('locked_count', 0),
                "conflicts_count": len(result.get('conflicts', [])),
                "asset_usage": result.get('asset_usage', {})
            },
            "data": result,
            "errors": result.get('errors', []),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "errors": [str(e)],
            "timestamp": datetime.utcnow().isoformat()
        }


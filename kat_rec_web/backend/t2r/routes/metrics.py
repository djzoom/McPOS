"""
Metrics Routes for T2R

System metrics and WebSocket health endpoints.
"""
from fastapi import APIRouter
from typing import Dict
from datetime import datetime
import logging
import psutil
import os
import time

from ...routes.websocket import status_manager, events_manager

router = APIRouter()
logger = logging.getLogger(__name__)

# Track startup time for uptime calculation
_STARTUP_TIME = time.time()


@router.get("/metrics/system")
async def get_system_metrics() -> Dict:
    """
    Get system metrics.
    
    Returns:
        {
            "cpu_percent": float,
            "memory_mb": float,
            "uptime_sec": float,
            "active_ws_connections": int,
            "timestamp": str
        }
    """
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Memory usage
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)
        
        # Uptime
        uptime_sec = time.time() - _STARTUP_TIME
        
        # WebSocket connections
        active_ws_connections = len(status_manager.connections) + len(events_manager.connections)
        
        return {
            "cpu_percent": round(cpu_percent, 2),
            "memory_mb": round(memory_mb, 2),
            "uptime_sec": round(uptime_sec, 2),
            "active_ws_connections": active_ws_connections,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        return {
            "cpu_percent": 0.0,
            "memory_mb": 0.0,
            "uptime_sec": 0.0,
            "active_ws_connections": 0,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/metrics/ws-health")
async def get_ws_health() -> Dict:
    """
    Get WebSocket health metrics.
    
    Returns:
        {
            "active_connections": int,
            "ping_loss_percent": float,
            "avg_delay_ms": float,
            "connection_ids": List[str],
            "timestamp": str
        }
    """
    try:
        # Aggregate from both managers
        status_conns = status_manager.connections
        events_conns = events_manager.connections
        
        all_connections = list(status_conns.keys()) + list(events_conns.keys())
        
        # Calculate ping loss and delay (simplified - would need tracking)
        ping_loss_percent = 0.0  # TODO: Track ping/pong responses
        avg_delay_ms = 0.0  # TODO: Track message round-trip times
        
        # For now, return basic stats
        return {
            "active_connections": len(all_connections),
            "ping_loss_percent": round(ping_loss_percent, 2),
            "avg_delay_ms": round(avg_delay_ms, 2),
            "connection_ids": all_connections[:10],  # Limit to 10 for response size
            "status_manager_count": len(status_conns),
            "events_manager_count": len(events_conns),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get WS health: {e}")
        return {
            "active_connections": 0,
            "ping_loss_percent": 0.0,
            "avg_delay_ms": 0.0,
            "connection_ids": [],
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


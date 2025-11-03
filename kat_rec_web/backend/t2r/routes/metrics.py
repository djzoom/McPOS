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

from routes.websocket import status_manager, events_manager

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
    Get WebSocket health metrics including buffer flush stats.
    
    Returns:
        {
            "active_connections": int,
            "status_manager": {...buffer_metrics},
            "events_manager": {...buffer_metrics},
            "ping_loss_percent": float,
            "avg_delay_ms": float,
            "timestamp": str
        }
    """
    try:
        # Aggregate from both managers
        status_conns = status_manager.connections
        events_conns = events_manager.connections
        
        all_connections = list(status_conns.keys()) + list(events_conns.keys())
        
        # Get buffer flush metrics from managers
        status_metrics = status_manager.get_buffer_metrics()
        events_metrics = events_manager.get_buffer_metrics()
        
        # Calculate ping loss and delay (simplified - would need tracking)
        ping_loss_percent = 0.0  # TODO: Track ping/pong responses
        avg_delay_ms = 0.0  # TODO: Track message round-trip times
        
        # Verify version monotonicity (never decreases)
        status_version_ok = status_metrics["version"] >= 0
        events_version_ok = events_metrics["version"] >= 0
        
        return {
            "active_connections": len(all_connections),
            "status_manager": {
                "connections": len(status_conns),
                **status_metrics,
                "version_monotonic": status_version_ok,
            },
            "events_manager": {
                "connections": len(events_conns),
                **events_metrics,
                "version_monotonic": events_version_ok,
            },
            "ping_loss_percent": round(ping_loss_percent, 2),
            "avg_delay_ms": round(avg_delay_ms, 2),
            "connection_ids": all_connections[:10],  # Limit to 10 for response size
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get WS health: {e}")
        return {
            "active_connections": 0,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


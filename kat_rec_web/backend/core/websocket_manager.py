"""
WebSocket Connection Manager

Enhanced WebSocket manager with heartbeat, connection tracking, timeout cleanup,
and exponential reconnect support.
"""
from fastapi import WebSocket
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import asyncio
import logging
import os
import json

# Configure logging based on environment variable
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class ConnectionInfo:
    """Track individual WebSocket connection info"""
    def __init__(self, websocket: WebSocket, connection_id: str):
        self.websocket = websocket
        self.connection_id = connection_id
        self.connected_at = datetime.utcnow()
        self.last_ping_at = datetime.utcnow()
        self.last_pong_at = datetime.utcnow()
        self.is_alive = True

    def update_ping(self):
        """Update ping timestamp"""
        self.last_ping_at = datetime.utcnow()

    def update_pong(self):
        """Update pong timestamp"""
        self.last_pong_at = datetime.utcnow()
        self.is_alive = True

    def is_stale(self, timeout_seconds: int = 15) -> bool:
        """Check if connection is stale (no pong for timeout period)"""
        time_since_pong = (datetime.utcnow() - self.last_pong_at).total_seconds()
        return time_since_pong > timeout_seconds


class ConnectionManager:
    """Enhanced WebSocket connection manager with heartbeat, cleanup, and batch buffering"""
    
    def __init__(self, heartbeat_interval: int = 5, timeout_seconds: int = 15):
        self.connections: Dict[str, ConnectionInfo] = {}
        self.heartbeat_interval = heartbeat_interval
        self.timeout_seconds = timeout_seconds
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self._connection_counter = 0
        
        # Batch buffer for messages
        self._message_buffer: List[Dict] = []
        self._buffer_lock = asyncio.Lock()
        self._buffer_flush_interval = 0.1  # 100ms
        self._buffer_task: Optional[asyncio.Task] = None
        self._version = 0

    async def connect(self, websocket: WebSocket) -> str:
        """Accept connection and track it"""
        await websocket.accept()
        connection_id = f"conn_{self._connection_counter}"
        self._connection_counter += 1
        
        conn_info = ConnectionInfo(websocket, connection_id)
        self.connections[connection_id] = conn_info
        
        logger.info(f"WebSocket client connected. ID: {connection_id}, Total: {len(self.connections)}")
        return connection_id

    def disconnect(self, connection_id: Optional[str] = None, websocket: Optional[WebSocket] = None):
        """Remove connection"""
        if connection_id and connection_id in self.connections:
            conn_info = self.connections.pop(connection_id)
            logger.info(f"WebSocket client disconnected. ID: {connection_id}, Total: {len(self.connections)}")
            return
        
        # Fallback: find by websocket
        if websocket:
            for conn_id, conn_info in list(self.connections.items()):
                if conn_info.websocket == websocket:
                    self.connections.pop(conn_id)
                    logger.info(f"WebSocket client disconnected. ID: {conn_id}, Total: {len(self.connections)}")
                    return

    async def send_ping(self, connection_id: str) -> bool:
        """Send ping to specific connection"""
        if connection_id not in self.connections:
            return False
        
        conn_info = self.connections[connection_id]
        try:
            await conn_info.websocket.send_text('"ping"')
            conn_info.update_ping()
            logger.debug(f"Sent ping to {connection_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to send ping to {connection_id}: {e}")
            self.disconnect(connection_id)
            return False

    async def send_pong(self, connection_id: str):
        """Send pong response to specific connection"""
        if connection_id not in self.connections:
            return
        
        conn_info = self.connections[connection_id]
        try:
            await conn_info.websocket.send_json({
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            })
            conn_info.update_pong()
        except Exception as e:
            logger.warning(f"Failed to send pong to {connection_id}: {e}")
            self.disconnect(connection_id)

    async def _flush_buffer(self):
        """Flush message buffer to all connections"""
        async with self._buffer_lock:
            if not self._message_buffer:
                return
            
            messages = self._message_buffer.copy()
            self._message_buffer.clear()
        
        disconnected = []
        for connection_id, conn_info in list(self.connections.items()):
            try:
                # Send all buffered messages
                for message in messages:
                    await conn_info.websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Error sending message to {connection_id}: {e}")
                disconnected.append(connection_id)
        
        # Remove disconnected connections
        for conn_id in disconnected:
            self.disconnect(conn_id)
    
    async def _flush_loop(self, interval: float = 0.1):
        """Internal flush loop for buffered messages"""
        while True:
            if self._message_buffer and self.connections:
                batch = []
                async with self._buffer_lock:
                    batch, self._message_buffer = self._message_buffer, []
                
                disconnected = []
                for connection_id, conn_info in list(self.connections.items()):
                    try:
                        for item in batch:
                            await conn_info.websocket.send_json(item)
                    except Exception as e:
                        logger.warning(f"Error sending message to {connection_id}: {e}")
                        disconnected.append(connection_id)
                
                # Remove disconnected connections
                for conn_id in disconnected:
                    self.disconnect(conn_id)
            await asyncio.sleep(interval)
    
    async def start_buffer_flush(self):
        """Start background task to flush buffer periodically"""
        if self._buffer_task and not self._buffer_task.done():
            return
        
        self._buffer_task = asyncio.create_task(self._flush_loop(self._buffer_flush_interval))
        logger.info(f"Buffer flush task started (interval: {self._buffer_flush_interval}s)")
    
    async def ensure_started(self):
        """Ensure flush loop is started (async version for startup events)"""
        if not self._buffer_task:
            await self.start_buffer_flush()
    
    async def broadcast(self, message: Dict, immediate: bool = False):
        """
        Broadcast message to all active connections.
        
        Args:
            message: Message to broadcast
            immediate: If True, send immediately; otherwise add to buffer
        """
        # Increment version for each broadcast
        self._version += 1
        message["version"] = self._version
        
        if immediate:
            # Send immediately (for heartbeat, critical messages)
            disconnected = []
            for connection_id, conn_info in list(self.connections.items()):
                try:
                    await conn_info.websocket.send_json(message)
                except Exception as e:
                    logger.warning(f"Error sending message to {connection_id}: {e}")
                    disconnected.append(connection_id)
            
            # Remove disconnected connections
            for conn_id in disconnected:
                self.disconnect(conn_id)
        else:
            # Add to buffer for batch flush
            async with self._buffer_lock:
                self._message_buffer.append(message)

    async def start_heartbeat(self):
        """Start heartbeat task (ping every interval)"""
        if self.heartbeat_task and not self.heartbeat_task.done():
            return
        
        async def heartbeat_loop():
            while True:
                try:
                    await asyncio.sleep(self.heartbeat_interval)
                    
                    # Send ping to all connections
                    connection_ids = list(self.connections.keys())
                    for conn_id in connection_ids:
                        await self.send_ping(conn_id)
                        
                except Exception as e:
                    logger.error(f"Error in heartbeat loop: {e}")
                    await asyncio.sleep(self.heartbeat_interval)
        
        self.heartbeat_task = asyncio.create_task(heartbeat_loop())
        logger.info(f"Heartbeat task started (interval: {self.heartbeat_interval}s)")

    async def start_cleanup(self):
        """Start cleanup task (remove stale connections)"""
        if self.cleanup_task and not self.cleanup_task.done():
            return
        
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(self.timeout_seconds)
                    
                    # Check for stale connections
                    stale_connections = []
                    for conn_id, conn_info in self.connections.items():
                        if conn_info.is_stale(self.timeout_seconds):
                            stale_connections.append(conn_id)
                    
                    # Remove stale connections
                    for conn_id in stale_connections:
                        logger.warning(f"Removing stale connection: {conn_id}")
                        self.disconnect(conn_id)
                        
                except Exception as e:
                    logger.error(f"Error in cleanup loop: {e}")
                    await asyncio.sleep(self.timeout_seconds)
        
        self.cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"Cleanup task started (timeout: {self.timeout_seconds}s)")

    async def handle_message(self, connection_id: str, message: str):
        """Handle incoming message from connection"""
        if connection_id not in self.connections:
            return
        
        conn_info = self.connections[connection_id]
        
        try:
            # Parse message
            msg = json.loads(message) if isinstance(message, str) else message
            
            # Handle ping from client
            if msg == "ping" or (isinstance(msg, dict) and msg.get("type") == "ping"):
                await self.send_pong(connection_id)
                return
            
            # Handle pong from client
            if msg == "pong" or (isinstance(msg, dict) and msg.get("type") == "pong"):
                conn_info.update_pong()
                return
            
            # Handle other messages
            logger.debug(f"Received message from {connection_id}: {msg}")
            
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON message from {connection_id}: {message}")
        except Exception as e:
            logger.error(f"Error handling message from {connection_id}: {e}")

    def get_connection_id(self, websocket: WebSocket) -> Optional[str]:
        """Get connection ID for a websocket"""
        for conn_id, conn_info in self.connections.items():
            if conn_info.websocket == websocket:
                return conn_id
        return None

    def get_active_count(self) -> int:
        """Get number of active connections"""
        return len(self.connections)

    async def shutdown(self):
        """Shutdown manager and cancel tasks"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        for conn_info in list(self.connections.values()):
            try:
                await conn_info.websocket.close()
            except Exception:
                pass
        
        self.connections.clear()
        logger.info("ConnectionManager shut down")


# Exponential reconnect helper
class ReconnectManager:
    """Manage exponential reconnection logic"""
    
    def __init__(self, initial_delay: float = 2.0, max_delay: float = 60.0, multiplier: float = 2.0):
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.current_delay = initial_delay
        self.attempt = 0

    def next_delay(self) -> float:
        """Get next reconnect delay (exponential backoff)"""
        delay = min(self.current_delay, self.max_delay)
        self.current_delay = min(self.current_delay * self.multiplier, self.max_delay)
        self.attempt += 1
        return delay

    def reset(self):
        """Reset reconnect state after successful connection"""
        self.current_delay = self.initial_delay
        self.attempt = 0

    async def wait(self):
        """Wait for next reconnect attempt"""
        delay = self.next_delay()
        logger.info(f"Reconnect attempt {self.attempt} in {delay:.1f}s")
        await asyncio.sleep(delay)


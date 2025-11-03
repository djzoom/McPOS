"""
Tests for WebSocket Status Endpoint

Tests connection, heartbeat, and cleanup functionality.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from fastapi.testclient import TestClient
    from main import app
except ImportError:
    # If dependencies not installed, skip import
    TestClient = None
    app = None

from core.websocket_manager import ConnectionManager, ConnectionInfo


@pytest.fixture
def client():
    """Create test client"""
    if TestClient is None or app is None:
        pytest.skip("FastAPI not available")
    return TestClient(app)


@pytest.fixture
def connection_manager():
    """Create connection manager instance"""
    return ConnectionManager(heartbeat_interval=5, timeout_seconds=15)


@pytest.mark.asyncio
async def test_websocket_connection_opens(client):
    """Test that WebSocket connection opens successfully"""
    if client is None:
        pytest.skip("Test client not available")
    with client.websocket_connect("/ws/status") as websocket:
        # Connection should be established
        assert websocket.client_state.name == "CONNECTED"
        print("✅ Connection opened successfully")


@pytest.mark.asyncio
async def test_websocket_heartbeat_sends_ping(connection_manager):
    """Test that heartbeat sends ping messages"""
    # Create a mock WebSocket
    class MockWebSocket:
        def __init__(self):
            self.sent_messages = []
        
        async def send_text(self, message: str):
            self.sent_messages.append(message)
        
        async def send_json(self, data: dict):
            self.sent_messages.append(json.dumps(data))
    
    mock_ws = MockWebSocket()
    
    # Connect
    connection_id = await connection_manager.connect(mock_ws)
    assert connection_id is not None
    
    # Start heartbeat
    await connection_manager.start_heartbeat()
    
    # Wait for heartbeat
    await asyncio.sleep(6)  # Wait slightly longer than heartbeat interval
    
    # Check that ping was sent
    ping_sent = any('"ping"' in msg or '"ping"' == msg for msg in mock_ws.sent_messages)
    assert ping_sent, f"Expected ping message, got: {mock_ws.sent_messages}"
    
    print("✅ Heartbeat ping sent successfully")
    
    # Cleanup
    connection_manager.disconnect(connection_id)
    await connection_manager.shutdown()


@pytest.mark.asyncio
async def test_websocket_auto_cleanup_after_idle(connection_manager):
    """Test that inactive connections are cleaned up after timeout"""
    # Create a mock WebSocket
    class MockWebSocket:
        async def send_text(self, message: str):
            pass
        
        async def send_json(self, data: dict):
            pass
    
    mock_ws = MockWebSocket()
    
    # Connect
    connection_id = await connection_manager.connect(mock_ws)
    initial_count = connection_manager.get_active_count()
    assert initial_count == 1
    
    # Get connection info and mark it as stale
    conn_info = connection_manager.connections[connection_id]
    # Set last_pong_at to 16 seconds ago (exceeding 15s timeout)
    conn_info.last_pong_at = datetime.utcnow() - timedelta(seconds=16)
    
    # Start cleanup task
    await connection_manager.start_cleanup()
    
    # Wait for cleanup (timeout is 15s, so wait 16s)
    await asyncio.sleep(16)
    
    # Check that connection was removed
    final_count = connection_manager.get_active_count()
    assert final_count == 0, f"Expected 0 connections, got {final_count}"
    
    print("✅ Auto cleanup worked after idle timeout")
    
    # Cleanup
    await connection_manager.shutdown()


@pytest.mark.asyncio
async def test_websocket_ping_pong_handling(connection_manager):
    """Test ping/pong message handling"""
    class MockWebSocket:
        def __init__(self):
            self.sent_messages = []
        
        async def send_text(self, message: str):
            self.sent_messages.append(message)
        
        async def send_json(self, data: dict):
            self.sent_messages.append(json.dumps(data))
    
    mock_ws = MockWebSocket()
    
    # Connect
    connection_id = await connection_manager.connect(mock_ws)
    
    # Send ping from client
    await connection_manager.handle_message(connection_id, json.dumps({"type": "ping"}))
    
    # Check that pong was sent
    pong_sent = any('"type": "pong"' in msg or '"pong"' in msg for msg in mock_ws.sent_messages)
    assert pong_sent, f"Expected pong message, got: {mock_ws.sent_messages}"
    
    # Check that pong timestamp was updated
    conn_info = connection_manager.connections[connection_id]
    assert conn_info.last_pong_at is not None
    
    print("✅ Ping/pong handling works correctly")
    
    # Cleanup
    connection_manager.disconnect(connection_id)
    await connection_manager.shutdown()


@pytest.mark.asyncio
async def test_websocket_broadcast_message(connection_manager):
    """Test broadcast message to all connections"""
    class MockWebSocket:
        def __init__(self):
            self.sent_messages = []
        
        async def send_json(self, data: dict):
            self.sent_messages.append(json.dumps(data))
    
    # Create multiple connections
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    
    conn_id1 = await connection_manager.connect(ws1)
    conn_id2 = await connection_manager.connect(ws2)
    
    # Broadcast message
    test_message = {"type": "test", "data": "hello"}
    await connection_manager.broadcast(test_message)
    
    # Check both connections received message
    assert len(ws1.sent_messages) > 0
    assert len(ws2.sent_messages) > 0
    
    # Check message content
    assert json.loads(ws1.sent_messages[0]) == test_message
    assert json.loads(ws2.sent_messages[0]) == test_message
    
    print("✅ Broadcast message to all connections")
    
    # Cleanup
    connection_manager.disconnect(conn_id1)
    connection_manager.disconnect(conn_id2)
    await connection_manager.shutdown()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])


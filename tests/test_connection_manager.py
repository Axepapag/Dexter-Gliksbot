"""
Tests for ConnectionManager

Validates connection lifecycle, event filtering, broadcasting, and heartbeat.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from fastapi import WebSocket

from dexter_autonomy.api.connection_manager import (
    ConnectionManager,
    ClientSubscription
)
from dexter_autonomy.api.websocket_events import (
    WebSocketMessage,
    EventType,
    AgentStatus,
    LogLevel,
    create_log_event,
    create_error_event
)


# ==================== Mock WebSocket ====================

class MockWebSocket:
    """Mock WebSocket for testing"""
    
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.accepted = False
        self.closed = False
        self.sent_messages = []
        self.should_fail = False
    
    async def accept(self):
        self.accepted = True
    
    async def send_text(self, data: str):
        if self.should_fail:
            raise Exception(f"Mock send failure for {self.client_id}")
        if self.closed:
            raise Exception(f"WebSocket closed for {self.client_id}")
        self.sent_messages.append(data)
    
    async def send_json(self, data: dict):
        if self.should_fail:
            raise Exception(f"Mock send failure for {self.client_id}")
        if self.closed:
            raise Exception(f"WebSocket closed for {self.client_id}")
        self.sent_messages.append(data)
    
    def close(self):
        self.closed = True


# ==================== ClientSubscription Tests ====================

def test_client_subscription_subscribe_all():
    """Test subscription with no filters (subscribe to everything)"""
    sub = ClientSubscription()
    
    assert sub.subscribe_all is True
    
    # Should match any message
    msg = WebSocketMessage(
        type=EventType.AGENT_STATUS,
        data={"agent_id": "test"}
    )
    assert sub.matches(msg) is True


def test_client_subscription_agent_filter():
    """Test subscription filtered by agent_ids"""
    sub = ClientSubscription(agent_ids={"agent-1", "agent-2"})
    
    assert sub.subscribe_all is False
    
    # Matching agent
    msg1 = WebSocketMessage(
        type=EventType.AGENT_STATUS,
        data={"agent_id": "agent-1"}
    )
    assert sub.matches(msg1) is True
    
    # Non-matching agent
    msg2 = WebSocketMessage(
        type=EventType.AGENT_STATUS,
        data={"agent_id": "agent-3"}
    )
    assert sub.matches(msg2) is False


def test_client_subscription_mission_filter():
    """Test subscription filtered by mission_ids"""
    sub = ClientSubscription(mission_ids={"mission-abc"})
    
    # Matching mission
    msg1 = WebSocketMessage(
        type=EventType.MISSION_PROGRESS,
        data={"mission_id": "mission-abc", "progress": 0.5}
    )
    assert sub.matches(msg1) is True
    
    # Non-matching mission
    msg2 = WebSocketMessage(
        type=EventType.MISSION_PROGRESS,
        data={"mission_id": "mission-xyz", "progress": 0.5}
    )
    assert sub.matches(msg2) is False


def test_client_subscription_log_level_filter():
    """Test subscription filtered by log levels"""
    sub = ClientSubscription(log_levels={LogLevel.ERROR, LogLevel.WARN})
    
    # Matching log level
    msg1 = WebSocketMessage(
        type=EventType.LOG_ERROR,
        data={"level": "ERROR", "message": "Test error"}
    )
    assert sub.matches(msg1) is True
    
    # Non-matching log level
    msg2 = WebSocketMessage(
        type=EventType.LOG_TRACE,
        data={"level": "TRACE", "message": "Trace message"}
    )
    assert sub.matches(msg2) is False


def test_client_subscription_event_type_filter():
    """Test subscription filtered by event types"""
    sub = ClientSubscription(event_types={EventType.AGENT_ERROR, EventType.MISSION_FAILED})
    
    # Matching event type
    msg1 = WebSocketMessage(
        type=EventType.AGENT_ERROR,
        data={"agent_id": "test"}
    )
    assert sub.matches(msg1) is True
    
    # Non-matching event type
    msg2 = WebSocketMessage(
        type=EventType.AGENT_STATUS,
        data={"agent_id": "test"}
    )
    assert sub.matches(msg2) is False


def test_client_subscription_update():
    """Test updating subscription filters"""
    sub = ClientSubscription()
    assert sub.subscribe_all is True
    
    # Update to add filters
    sub.update(agent_ids=["agent-1"])
    assert sub.subscribe_all is False
    assert "agent-1" in sub.agent_ids


# ==================== ConnectionManager Tests ====================

@pytest.mark.asyncio
async def test_connection_manager_connect():
    """Test client connection"""
    manager = ConnectionManager()
    ws = MockWebSocket("client-1")
    
    await manager.connect("client-1", ws)
    
    assert ws.accepted is True
    assert "client-1" in manager.active_connections
    assert "client-1" in manager.client_subscriptions
    assert manager.total_connections == 1
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_connection_manager_disconnect():
    """Test client disconnection"""
    manager = ConnectionManager()
    ws = MockWebSocket("client-1")
    
    await manager.connect("client-1", ws)
    assert "client-1" in manager.active_connections
    
    await manager.disconnect("client-1")
    assert "client-1" not in manager.active_connections
    assert manager.total_disconnections == 1
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_connection_manager_multiple_connections():
    """Test multiple concurrent connections"""
    manager = ConnectionManager()
    
    clients = [MockWebSocket(f"client-{i}") for i in range(5)]
    
    for i, ws in enumerate(clients):
        await manager.connect(f"client-{i}", ws)
    
    assert len(manager.active_connections) == 5
    assert manager.total_connections == 5
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_connection_manager_broadcast_all():
    """Test broadcasting to all clients"""
    manager = ConnectionManager()
    
    # Connect 3 clients
    clients = [MockWebSocket(f"client-{i}") for i in range(3)]
    for i, ws in enumerate(clients):
        await manager.connect(f"client-{i}", ws)
    
    # Broadcast message
    msg = WebSocketMessage(
        type=EventType.AGENT_STATUS,
        data={"agent_id": "test", "status": "idle"}
    )
    
    await manager.broadcast(msg)
    
    # All clients should receive message (after state snapshot + replay)
    for ws in clients:
        # Find non-snapshot messages
        agent_status_msgs = [m for m in ws.sent_messages if '"type":"agent.status"' in m]
        assert len(agent_status_msgs) >= 1
    
    # Event should be in history
    assert len(manager.event_history) == 1
    assert manager.total_messages_sent >= 3  # At least 1 to each client
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_connection_manager_broadcast_filtered():
    """Test broadcasting with client filters"""
    manager = ConnectionManager()
    
    # Client 1: subscribes to agent-1 only
    ws1 = MockWebSocket("client-1")
    await manager.connect("client-1", ws1, filters={"agent_ids": ["agent-1"]})
    
    # Client 2: subscribes to agent-2 only
    ws2 = MockWebSocket("client-2")
    await manager.connect("client-2", ws2, filters={"agent_ids": ["agent-2"]})
    
    # Broadcast message for agent-1
    msg = WebSocketMessage(
        type=EventType.AGENT_STATUS,
        data={"agent_id": "agent-1", "status": "on_task"}
    )
    
    await manager.broadcast(msg)
    
    # Only client-1 should receive agent-1 message
    agent1_msgs = [m for m in ws1.sent_messages if '"agent_id":"agent-1"' in m]
    agent2_msgs = [m for m in ws2.sent_messages if '"agent_id":"agent-1"' in m]
    
    assert len(agent1_msgs) >= 1  # Client 1 receives
    assert len(agent2_msgs) == 0  # Client 2 does not receive
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_connection_manager_send_to_client():
    """Test sending message to specific client"""
    manager = ConnectionManager()
    ws = MockWebSocket("client-1")
    
    await manager.connect("client-1", ws)
    
    msg = create_log_event(
        level=LogLevel.INFO,
        message="Test message"
    )
    
    success = await manager.send_to_client("client-1", msg)
    assert success is True
    
    # Check message received
    log_msgs = [m for m in ws.sent_messages if '"level":"INFO"' in m]
    assert len(log_msgs) == 1
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_connection_manager_send_to_nonexistent_client():
    """Test sending to non-existent client"""
    manager = ConnectionManager()
    
    msg = create_log_event(
        level=LogLevel.INFO,
        message="Test"
    )
    
    success = await manager.send_to_client("nonexistent", msg)
    assert success is False
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_connection_manager_update_subscription():
    """Test updating client subscription filters"""
    manager = ConnectionManager()
    ws = MockWebSocket("client-1")
    
    # Connect with no filters (subscribe all)
    await manager.connect("client-1", ws)
    sub = manager.client_subscriptions["client-1"]
    assert sub.subscribe_all is True
    
    # Update to filter by agent
    await manager.update_subscription("client-1", {"agent_ids": ["agent-1"]})
    assert sub.subscribe_all is False
    assert "agent-1" in sub.agent_ids
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_connection_manager_event_history():
    """Test event history buffer"""
    manager = ConnectionManager(event_history_size=10)
    ws = MockWebSocket("client-1")
    
    await manager.connect("client-1", ws)
    
    # Send 15 messages (buffer size is 10)
    for i in range(15):
        msg = WebSocketMessage(
            type=EventType.LOG_TRACE,
            data={"message": f"Message {i}"}
        )
        await manager.broadcast(msg)
    
    # Only last 10 should be in history (circular buffer)
    assert len(manager.event_history) == 10
    
    # Last message should be message 14
    last_msg = manager.event_history[-1]
    assert "Message 14" in last_msg.data["message"]
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_connection_manager_fire_and_forget():
    """Test fire-and-forget broadcasting (drop on failure)"""
    manager = ConnectionManager()
    
    # Client 1: working
    ws1 = MockWebSocket("client-1")
    await manager.connect("client-1", ws1)
    
    # Client 2: will fail on send
    ws2 = MockWebSocket("client-2")
    await manager.connect("client-2", ws2)
    ws2.should_fail = True  # Simulate send failure
    
    # Broadcast message
    msg = WebSocketMessage(
        type=EventType.AGENT_STATUS,
        data={"agent_id": "test"}
    )
    
    await manager.broadcast(msg)
    
    # Client 1 should still be connected
    assert "client-1" in manager.active_connections
    
    # Client 2 should be disconnected (fire-and-forget)
    assert "client-2" not in manager.active_connections
    
    # Dropped messages tracked
    assert manager.total_messages_dropped >= 1
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_connection_manager_get_stats():
    """Test connection manager statistics"""
    manager = ConnectionManager()
    
    ws1 = MockWebSocket("client-1")
    await manager.connect("client-1", ws1, filters={"agent_ids": ["agent-1"]})
    
    ws2 = MockWebSocket("client-2")
    await manager.connect("client-2", ws2)
    
    stats = manager.get_stats()
    
    assert stats["active_connections"] == 2
    assert stats["total_connections"] == 2
    assert len(stats["clients"]) == 2
    
    # Check client subscription details
    client1_sub = next(c for c in stats["clients"] if c["client_id"] == "client-1")
    assert "agent-1" in client1_sub["subscription"]["agent_ids"]
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_connection_manager_shutdown():
    """Test graceful shutdown"""
    manager = ConnectionManager()
    
    # Connect multiple clients
    clients = [MockWebSocket(f"client-{i}") for i in range(3)]
    for i, ws in enumerate(clients):
        await manager.connect(f"client-{i}", ws)
    
    assert len(manager.active_connections) == 3
    
    # Shutdown
    await manager.shutdown()
    
    # All clients should be disconnected
    assert len(manager.active_connections) == 0


@pytest.mark.asyncio
async def test_connection_manager_replay_recent_events():
    """Test event replay on reconnect"""
    manager = ConnectionManager()
    
    # Send some events before client connects
    for i in range(5):
        msg = WebSocketMessage(
            type=EventType.LOG_TRACE,
            data={"message": f"Event {i}"}
        )
        manager.event_history.append(msg)
    
    # Connect client
    ws = MockWebSocket("client-1")
    await manager.connect("client-1", ws)
    
    # Client should receive state snapshot + replayed events
    assert len(ws.sent_messages) >= 5  # At least 5 replayed events
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_connection_manager_replay_time_window():
    """Test event replay respects 5-minute window"""
    manager = ConnectionManager()
    
    # Add old event (> 5 minutes ago)
    old_msg = WebSocketMessage(
        type=EventType.LOG_TRACE,
        data={"message": "Old event"}
    )
    old_msg.timestamp = datetime.utcnow() - timedelta(minutes=10)
    manager.event_history.append(old_msg)
    
    # Add recent event
    recent_msg = WebSocketMessage(
        type=EventType.LOG_TRACE,
        data={"message": "Recent event"}
    )
    manager.event_history.append(recent_msg)
    
    # Connect client
    ws = MockWebSocket("client-1")
    await manager.connect("client-1", ws)
    
    # Should only replay recent event (not old one)
    replayed = [m for m in ws.sent_messages if '"message":"Recent event"' in m]
    assert len(replayed) >= 1
    
    old_replayed = [m for m in ws.sent_messages if '"message":"Old event"' in m]
    assert len(old_replayed) == 0  # Old event not replayed
    
    # Cleanup
    await manager.shutdown()


@pytest.mark.asyncio
async def test_connection_manager_replay_max_100_events():
    """Test event replay limited to 100 events"""
    manager = ConnectionManager(event_history_size=200)
    
    # Add 150 recent events
    for i in range(150):
        msg = WebSocketMessage(
            type=EventType.LOG_TRACE,
            data={"message": f"Event {i}"}
        )
        manager.event_history.append(msg)
    
    # Connect client
    ws = MockWebSocket("client-1")
    await manager.connect("client-1", ws)
    
    # Should replay max 100 events + 1 state snapshot
    # (Filter for trace events to count replayed events)
    trace_events = [m for m in ws.sent_messages if '"type":"log.trace"' in m]
    assert len(trace_events) <= 100
    
    # Cleanup
    await manager.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Tests for WebSocket Event Schema

Validates Pydantic models, transformation logic, and event aggregation.
"""

import pytest
from datetime import datetime, timedelta
from dexter_autonomy.api.websocket_events import (
    # Enums
    EventType, AgentStatus, MissionPhase, LogLevel,
    # Models
    WebSocketMessage, AgentStatusEvent, MissionUpdateEvent,
    LogEntryEvent, SystemStateSnapshot, PerformanceMetricEvent,
    # Transformers
    TripleBusTransformer,
    # Utilities
    create_state_snapshot, create_error_event, create_log_event
)


# ==================== Model Tests ====================

def test_websocket_message_base():
    """Test base WebSocketMessage envelope"""
    msg = WebSocketMessage(
        type=EventType.AGENT_STATUS,
        data={"agent_id": "test-agent", "status": "idle"}
    )
    
    assert msg.type == EventType.AGENT_STATUS
    assert isinstance(msg.timestamp, datetime)
    assert msg.data["agent_id"] == "test-agent"
    assert msg.metadata == {}


def test_agent_status_event():
    """Test AgentStatusEvent validation"""
    event = AgentStatusEvent(
        agent_id="coder-1",
        agent_name="Coder Agent",
        status=AgentStatus.ON_TASK,
        current_mission="mission-123",
        uptime_seconds=3600.5,
        success_rate=0.95,
        actions_completed=42,
        last_action_timestamp=datetime.utcnow(),
        metrics={"actions_per_minute": 0.7}
    )
    
    assert event.agent_id == "coder-1"
    assert event.status == AgentStatus.ON_TASK
    assert event.success_rate == 0.95
    assert 0.0 <= event.success_rate <= 1.0


def test_agent_status_event_validation():
    """Test AgentStatusEvent field validation"""
    # success_rate must be between 0 and 1
    with pytest.raises(Exception):  # Pydantic ValidationError
        AgentStatusEvent(
            agent_id="test",
            agent_name="Test",
            status=AgentStatus.IDLE,
            uptime_seconds=100,
            success_rate=1.5,  # Invalid: > 1.0
            actions_completed=10
        )


def test_mission_update_event():
    """Test MissionUpdateEvent"""
    event = MissionUpdateEvent(
        mission_id="mission-abc",
        mission_name="Invoice Processing",
        phase=MissionPhase.EXECUTING,
        progress=0.65,
        agents_assigned=["coder-1", "scraper-2"],
        started_at=datetime.utcnow(),
        last_action="Extracted 15 invoices"
    )
    
    assert event.mission_id == "mission-abc"
    assert event.phase == MissionPhase.EXECUTING
    assert event.progress == 0.65
    assert len(event.agents_assigned) == 2


def test_log_entry_event():
    """Test LogEntryEvent"""
    event = LogEntryEvent(
        level=LogLevel.ERROR,
        message="Connection timeout",
        agent_id="web-scraper",
        mission_id="scrape-job-1",
        correlation_id="corr-123",
        bus="PRIVATE",
        topic="PROGRESS",
        details={"url": "https://example.com", "timeout_seconds": 30}
    )
    
    assert event.level == LogLevel.ERROR
    assert event.bus == "PRIVATE"
    assert event.details["timeout_seconds"] == 30


def test_system_state_snapshot():
    """Test SystemStateSnapshot aggregation"""
    agents = [
        {
            "agent_id": "dexter",
            "agent_name": "Dexter Orchestrator",
            "status": "idle",
            "uptime_seconds": 5000,
            "success_rate": 0.99,
            "actions_completed": 150
        }
    ]
    
    missions = [
        {
            "mission_id": "mission-1",
            "mission_name": "Test Mission",
            "phase": "executing",
            "progress": 0.5,
            "agents_assigned": ["dexter"],
            "started_at": datetime.utcnow()
        }
    ]
    
    system_metrics = {
        "event_bus_messages_per_sec": 12.5,
        "event_bus_queue_depth": 3,
        "active_agents": 5,
        "active_missions": 2,
        "cpu_percent": 25.3,
        "memory_mb": 512.0,
        "brain_size_mb": 45.2,
        "uptime_seconds": 10000
    }
    
    snapshot = create_state_snapshot(agents, missions, system_metrics)
    
    assert snapshot.type == EventType.STATE_SNAPSHOT
    assert len(snapshot.data["agents"]) == 1
    assert len(snapshot.data["missions"]) == 1
    assert snapshot.data["system_metrics"]["cpu_percent"] == 25.3


# ==================== Transformer Tests ====================

def test_transformer_agent_status_aggregation():
    """Test 5-second agent status aggregation (Comet's design)"""
    transformer = TripleBusTransformer()
    agent_id = "test-agent"
    
    # First send: should allow
    assert transformer.should_send_agent_status(agent_id) is True
    
    # Immediate second send: should throttle
    assert transformer.should_send_agent_status(agent_id) is False
    
    # Wait 5 seconds (simulate)
    transformer._last_agent_status_send[agent_id] = datetime.utcnow() - timedelta(seconds=6)
    
    # After 5s: should allow again
    assert transformer.should_send_agent_status(agent_id) is True


def test_transformer_triplebus_to_websocket_main_bus():
    """Test transformation of MAIN bus events"""
    transformer = TripleBusTransformer()
    
    # TRACE event → LOG_TRACE
    trace_event = {
        "agent_id": "dexter",
        "message": "Processing intent",
        "correlation_id": "abc-123"
    }
    
    ws_msg = transformer.triplebus_to_websocket("MAIN", "TRACE", trace_event)
    
    assert ws_msg is not None
    assert ws_msg.type == EventType.LOG_TRACE
    assert ws_msg.metadata["bus"] == "MAIN"
    assert ws_msg.metadata["correlation_id"] == "abc-123"


def test_transformer_triplebus_to_websocket_collab_bus():
    """Test transformation of COLLAB bus events"""
    transformer = TripleBusTransformer()
    
    # PROPOSAL event → COLLAB_PROPOSAL
    proposal_event = {
        "from": "coder-agent",
        "collab_id": "collab-1",
        "proposal": {"solution": "Use regex extraction"}
    }
    
    ws_msg = transformer.triplebus_to_websocket("COLLAB", "PROPOSAL", proposal_event)
    
    assert ws_msg is not None
    assert ws_msg.type == EventType.COLLAB_PROPOSAL
    assert ws_msg.metadata["bus"] == "COLLAB"
    assert ws_msg.metadata["source_agent"] == "coder-agent"


def test_transformer_triplebus_to_websocket_private_bus():
    """Test transformation of PRIVATE bus events"""
    transformer = TripleBusTransformer()
    
    # TASK_ASSIGNMENT → MISSION_STARTED
    task_event = {
        "mission_id": "mission-xyz",
        "agent_id": "scraper-1",
        "task": "Scrape product data"
    }
    
    ws_msg = transformer.triplebus_to_websocket("PRIVATE", "TASK_ASSIGNMENT", task_event)
    
    assert ws_msg is not None
    assert ws_msg.type == EventType.MISSION_STARTED
    assert ws_msg.metadata["bus"] == "PRIVATE"


def test_transformer_agent_status_throttling():
    """Test agent status throttling (not sent if <5s since last)"""
    transformer = TripleBusTransformer()
    
    status_event = {
        "agent_id": "test-agent",
        "status": "on_task",
        "mission_id": "mission-1"
    }
    
    # First send: allowed
    ws_msg1 = transformer.triplebus_to_websocket("MAIN", "EFFECT", status_event)
    assert ws_msg1 is not None
    
    # Second send immediately: throttled
    ws_msg2 = transformer.triplebus_to_websocket("MAIN", "EFFECT", status_event)
    assert ws_msg2 is None  # Throttled!
    
    # Force send (critical event)
    ws_msg3 = transformer.triplebus_to_websocket("MAIN", "EFFECT", status_event, force_send=True)
    assert ws_msg3 is not None  # Force override


def test_transformer_unknown_event_ignored():
    """Test that unknown events are ignored"""
    transformer = TripleBusTransformer()
    
    unknown_event = {"some": "data"}
    
    ws_msg = transformer.triplebus_to_websocket("MAIN", "UNKNOWN_TOPIC", unknown_event)
    
    assert ws_msg is None  # Ignored


def test_transformer_binary_data_small():
    """Test binary data encoding (<100KB → base64)"""
    transformer = TripleBusTransformer()
    
    # 50KB of data
    small_data = b"x" * (50 * 1024)
    
    encoded = transformer.encode_binary_data(small_data, threshold_kb=100)
    
    assert isinstance(encoded, str)  # Base64 string
    assert len(encoded) > 0


def test_transformer_binary_data_large():
    """Test binary data encoding (>=100KB → URL reference)"""
    transformer = TripleBusTransformer()
    
    # 150KB of data
    large_data = b"x" * (150 * 1024)
    
    encoded = transformer.encode_binary_data(large_data, threshold_kb=100)
    
    assert isinstance(encoded, dict)  # URL reference
    assert "url" in encoded
    assert encoded["size_kb"] == 150


# ==================== Utility Tests ====================

def test_create_error_event():
    """Test error event creation utility"""
    error = ValueError("Invalid input format")
    
    ws_msg = create_error_event(
        agent_id="coder-1",
        agent_name="Coder Agent",
        error=error,
        mission_id="mission-123"
    )
    
    assert ws_msg.type == EventType.AGENT_ERROR
    assert ws_msg.data["error_type"] == "ValueError"
    assert ws_msg.data["error_message"] == "Invalid input format"
    assert ws_msg.data["mission_id"] == "mission-123"
    assert ws_msg.metadata["critical"] is True


def test_create_log_event():
    """Test log event creation utility"""
    ws_msg = create_log_event(
        level=LogLevel.WARN,
        message="High memory usage detected",
        agent_id="bsm",
        bus="MAIN",
        memory_mb=9500,
        threshold_mb=10000
    )
    
    assert ws_msg.type == EventType.LOG_WARN
    assert ws_msg.data["level"] == "WARN"
    assert ws_msg.data["message"] == "High memory usage detected"
    assert ws_msg.data["details"]["memory_mb"] == 9500


# ==================== JSON Serialization Tests ====================

def test_websocket_message_serialization():
    """Test WebSocketMessage can be serialized to JSON"""
    msg = WebSocketMessage(
        type=EventType.MISSION_PROGRESS,
        data={
            "mission_id": "test",
            "progress": 0.75,
            "timestamp": datetime.utcnow()
        }
    )
    
    # Should serialize without errors
    json_str = msg.json()
    assert "mission.progress" in json_str  # EventType enum value (with dot)
    assert "0.75" in json_str


def test_agent_status_event_dict():
    """Test AgentStatusEvent.dict() for WebSocket transmission"""
    event = AgentStatusEvent(
        agent_id="test",
        agent_name="Test Agent",
        status=AgentStatus.IDLE,
        uptime_seconds=1000,
        success_rate=0.8,
        actions_completed=50
    )
    
    data = event.dict()
    
    assert data["agent_id"] == "test"
    assert data["status"] == "idle"  # Enum serialized to string
    assert data["success_rate"] == 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

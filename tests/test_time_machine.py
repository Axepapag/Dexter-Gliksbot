"""
Test suite for Time Machine functionality.

Tests:
1. Timeline event logging and querying
2. State snapshot creation and storage
3. Snapshot compression and integrity
4. Rollback preview and execution
5. Automatic snapshot creation
6. Retention policy and cleanup
7. Full-text event search
"""
import asyncio
import pytest
import pytest_asyncio
import time
import json
import tempfile
import shutil
from pathlib import Path

from dexter_autonomy.brain.time_machine import (
    TimeMachine,
    TimelineEvent,
    StateSnapshot,
    EventSeverity,
    EventCategory,
    TimelineStore,
    SnapshotStore,
)


@pytest.fixture
def temp_dir():
    """Create temporary directory for test databases"""
    temp = tempfile.mkdtemp()
    yield temp
    shutil.rmtree(temp)


@pytest.fixture
def timeline_store(temp_dir):
    """Create timeline store for testing"""
    return TimelineStore(db_path=f"{temp_dir}/timeline.db")


@pytest.fixture
def snapshot_store(temp_dir):
    """Create snapshot store for testing"""
    return SnapshotStore(
        db_path=f"{temp_dir}/snapshots.db",
        data_dir=f"{temp_dir}/snapshots"
    )


@pytest_asyncio.fixture
async def time_machine(temp_dir):
    """Create Time Machine instance for testing"""
    tm = TimeMachine(
        timeline_db=f"{temp_dir}/timeline.db",
        snapshot_db=f"{temp_dir}/snapshots.db",
        snapshot_dir=f"{temp_dir}/snapshots",
        auto_snapshot_interval=1.0,  # 1 second for testing
        retention_days=1,
    )
    await tm.start()
    yield tm
    await tm.stop()


class TestTimelineEvent:
    """Test TimelineEvent dataclass"""
    
    def test_event_creation(self):
        """TimelineEvent can be created with defaults"""
        event = TimelineEvent(
            event_type="test_event",
            description="Test event description",
        )
        
        assert event.id is not None
        assert event.timestamp > 0
        assert event.severity == EventSeverity.INFO
        assert event.category == EventCategory.SYSTEM_EVENT
        assert event.event_type == "test_event"
    
    def test_event_to_dict(self):
        """TimelineEvent can be converted to dict"""
        event = TimelineEvent(
            event_type="test",
            description="Test",
            tags=["tag1", "tag2"],
            payload={"key": "value"},
        )
        
        data = event.to_dict()
        
        assert data["event_type"] == "test"
        assert data["tags"] == ["tag1", "tag2"]
        assert data["payload"] == {"key": "value"}
    
    def test_event_from_dict(self):
        """TimelineEvent can be created from dict"""
        data = {
            "id": "test-id",
            "timestamp": 123456.0,
            "severity": "error",
            "category": "agent_action",
            "event_type": "test",
            "description": "Test",
            "bus": "main",
            "agent_id": "test_agent",
            "task_root": None,
            "correlation_id": None,
            "parent_event_id": None,
            "payload": {},
            "tags": [],
            "metadata": {},
        }
        
        event = TimelineEvent.from_dict(data)
        
        assert event.id == "test-id"
        assert event.severity == EventSeverity.ERROR
        assert event.category == EventCategory.AGENT_ACTION


class TestStateSnapshot:
    """Test StateSnapshot dataclass"""
    
    def test_snapshot_creation(self):
        """StateSnapshot can be created"""
        snapshot = StateSnapshot(
            name="Test Snapshot",
            description="Test description",
            state_data={"agents": {}, "memory": {}},
        )
        
        assert snapshot.id is not None
        assert snapshot.timestamp > 0
        assert snapshot.name == "Test Snapshot"
    
    def test_snapshot_checksum(self):
        """StateSnapshot calculates checksum correctly"""
        snapshot = StateSnapshot(
            state_data={"key": "value", "nested": {"data": 123}},
        )
        
        checksum = snapshot.calculate_checksum()
        
        assert len(checksum) == 64  # SHA256 hex digest
        assert checksum == snapshot.calculate_checksum()  # Deterministic


class TestTimelineStore:
    """Test timeline storage and querying"""
    
    def test_add_event(self, timeline_store):
        """Events can be added to timeline"""
        event = TimelineEvent(
            event_type="test_event",
            description="Test event",
            severity=EventSeverity.INFO,
            category=EventCategory.SYSTEM_EVENT,
        )
        
        event_id = timeline_store.add_event(event)
        
        assert event_id == event.id
    
    def test_get_event(self, timeline_store):
        """Events can be retrieved by ID"""
        event = TimelineEvent(
            event_type="test_event",
            description="Test event",
        )
        
        timeline_store.add_event(event)
        retrieved = timeline_store.get_event(event.id)
        
        assert retrieved is not None
        assert retrieved.id == event.id
        assert retrieved.event_type == "test_event"
    
    def test_query_events_by_severity(self, timeline_store):
        """Events can be queried by severity"""
        # Add events with different severities
        timeline_store.add_event(TimelineEvent(
            event_type="info_event",
            severity=EventSeverity.INFO,
        ))
        timeline_store.add_event(TimelineEvent(
            event_type="error_event",
            severity=EventSeverity.ERROR,
        ))
        timeline_store.add_event(TimelineEvent(
            event_type="critical_event",
            severity=EventSeverity.CRITICAL,
        ))
        
        # Query errors only
        errors = timeline_store.query_events(severity=EventSeverity.ERROR)
        
        assert len(errors) == 1
        assert errors[0].event_type == "error_event"
    
    def test_query_events_by_category(self, timeline_store):
        """Events can be queried by category"""
        timeline_store.add_event(TimelineEvent(
            event_type="agent_event",
            category=EventCategory.AGENT_ACTION,
        ))
        timeline_store.add_event(TimelineEvent(
            event_type="system_event",
            category=EventCategory.SYSTEM_EVENT,
        ))
        
        # Query agent actions only
        agent_events = timeline_store.query_events(category=EventCategory.AGENT_ACTION)
        
        assert len(agent_events) == 1
        assert agent_events[0].event_type == "agent_event"
    
    def test_query_events_by_agent(self, timeline_store):
        """Events can be queried by agent ID"""
        timeline_store.add_event(TimelineEvent(
            event_type="agent1_event",
            agent_id="agent1",
        ))
        timeline_store.add_event(TimelineEvent(
            event_type="agent2_event",
            agent_id="agent2",
        ))
        
        # Query agent1 events
        agent1_events = timeline_store.query_events(agent_id="agent1")
        
        assert len(agent1_events) == 1
        assert agent1_events[0].agent_id == "agent1"
    
    def test_query_events_by_time_range(self, timeline_store):
        """Events can be queried by time range"""
        now = time.time()
        
        # Add events at different times
        event1 = TimelineEvent(event_type="old_event", timestamp=now - 3600)
        event2 = TimelineEvent(event_type="recent_event", timestamp=now - 60)
        
        timeline_store.add_event(event1)
        timeline_store.add_event(event2)
        
        # Query events from last 2 minutes
        recent_events = timeline_store.query_events(start_time=now - 120)
        
        assert len(recent_events) == 1
        assert recent_events[0].event_type == "recent_event"
    
    def test_query_events_by_correlation(self, timeline_store):
        """Events can be queried by correlation ID"""
        correlation_id = "test-correlation-123"
        
        timeline_store.add_event(TimelineEvent(
            event_type="event1",
            correlation_id=correlation_id,
        ))
        timeline_store.add_event(TimelineEvent(
            event_type="event2",
            correlation_id=correlation_id,
        ))
        timeline_store.add_event(TimelineEvent(
            event_type="event3",
            correlation_id="other-correlation",
        ))
        
        # Query correlated events
        correlated = timeline_store.query_events(correlation_id=correlation_id)
        
        assert len(correlated) == 2
    
    def test_search_events(self, timeline_store):
        """Events can be searched with full-text search"""
        timeline_store.add_event(TimelineEvent(
            event_type="user_login",
            description="User John logged in successfully",
        ))
        timeline_store.add_event(TimelineEvent(
            event_type="file_access",
            description="User accessed file report.pdf",
        ))
        
        # Search for "user"
        results = timeline_store.search_events("user")
        
        assert len(results) == 2
        
        # Search for "login"
        results = timeline_store.search_events("login")
        
        assert len(results) == 1
        assert results[0].event_type == "user_login"
    
    def test_get_event_count(self, timeline_store):
        """Event count can be retrieved"""
        # Add multiple events
        for i in range(5):
            timeline_store.add_event(TimelineEvent(
                event_type=f"event_{i}",
                severity=EventSeverity.ERROR if i < 2 else EventSeverity.INFO,
            ))
        
        total = timeline_store.get_event_count()
        assert total == 5
        
        errors = timeline_store.get_event_count(severity=EventSeverity.ERROR)
        assert errors == 2


class TestSnapshotStore:
    """Test snapshot storage and retrieval"""
    
    def test_save_snapshot(self, snapshot_store):
        """Snapshots can be saved"""
        snapshot = StateSnapshot(
            name="Test Snapshot",
            description="Test description",
            state_data={"agents": {"agent1": "active"}, "memory": {}},
        )
        
        snapshot_id = snapshot_store.save_snapshot(snapshot)
        
        assert snapshot_id == snapshot.id
        assert snapshot.checksum != ""
        assert snapshot.size_bytes > 0
    
    def test_load_snapshot(self, snapshot_store):
        """Snapshots can be loaded"""
        original = StateSnapshot(
            name="Test Snapshot",
            state_data={"test": "data", "nested": {"key": "value"}},
        )
        
        snapshot_store.save_snapshot(original)
        loaded = snapshot_store.load_snapshot(original.id)
        
        assert loaded is not None
        assert loaded.id == original.id
        assert loaded.name == "Test Snapshot"
        assert loaded.state_data == {"test": "data", "nested": {"key": "value"}}
    
    def test_snapshot_compression(self, snapshot_store):
        """Snapshots can be compressed"""
        # Large state data
        large_data = {"key" + str(i): "value" * 100 for i in range(100)}
        
        compressed = StateSnapshot(
            name="Compressed",
            state_data=large_data,
            compressed=True,
        )
        
        uncompressed = StateSnapshot(
            name="Uncompressed",
            state_data=large_data,
            compressed=False,
        )
        
        snapshot_store.save_snapshot(compressed)
        snapshot_store.save_snapshot(uncompressed)
        
        # Compressed should be smaller
        assert compressed.size_bytes < uncompressed.size_bytes
    
    def test_snapshot_integrity(self, snapshot_store):
        """Snapshot integrity is verified with checksum"""
        snapshot = StateSnapshot(
            name="Test",
            state_data={"data": "test"},
        )
        
        snapshot_store.save_snapshot(snapshot)
        
        # Corrupt the data file
        data_file = Path(snapshot_store.data_dir) / f"{snapshot.id}.json"
        data_file.write_text('{"corrupted": "data"}')
        
        # Loading should fail due to checksum mismatch
        loaded = snapshot_store.load_snapshot(snapshot.id)
        
        assert loaded is None  # Checksum validation failed
    
    def test_list_snapshots(self, snapshot_store):
        """Snapshots can be listed"""
        # Create multiple snapshots
        for i in range(3):
            snapshot_store.save_snapshot(StateSnapshot(
                name=f"Snapshot {i}",
                state_data={"index": i},
            ))
        
        snapshots = snapshot_store.list_snapshots()
        
        assert len(snapshots) == 3
        assert all("id" in s for s in snapshots)
        assert all("name" in s for s in snapshots)
    
    def test_delete_snapshot(self, snapshot_store):
        """Snapshots can be deleted"""
        snapshot = StateSnapshot(
            name="To Delete",
            state_data={"test": "data"},
        )
        
        snapshot_store.save_snapshot(snapshot)
        
        # Verify it exists
        loaded = snapshot_store.load_snapshot(snapshot.id)
        assert loaded is not None
        
        # Delete it
        result = snapshot_store.delete_snapshot(snapshot.id)
        assert result is True
        
        # Verify it's gone
        loaded = snapshot_store.load_snapshot(snapshot.id)
        assert loaded is None
    
    def test_cleanup_expired(self, snapshot_store):
        """Expired snapshots are cleaned up"""
        # Create snapshot that's already expired
        expired = StateSnapshot(
            name="Expired",
            state_data={"test": "data"},
            retained_until=time.time() - 1,  # Expired 1 second ago
        )
        
        # Create snapshot that's not expired
        active = StateSnapshot(
            name="Active",
            state_data={"test": "data"},
            retained_until=time.time() + 3600,  # Expires in 1 hour
        )
        
        snapshot_store.save_snapshot(expired)
        snapshot_store.save_snapshot(active)
        
        # Run cleanup
        count = snapshot_store.cleanup_expired()
        
        assert count == 1
        
        # Verify expired is gone, active remains
        assert snapshot_store.load_snapshot(expired.id) is None
        assert snapshot_store.load_snapshot(active.id) is not None


class TestTimeMachine:
    """Test TimeMachine integration"""
    
    @pytest.mark.asyncio
    async def test_log_event(self, time_machine):
        """Events can be logged through TimeMachine"""
        event = TimelineEvent(
            event_type="test_event",
            description="Test event",
        )
        
        event_id = await time_machine.log_event(event)
        
        assert event_id == event.id
    
    @pytest.mark.asyncio
    async def test_create_snapshot(self, time_machine):
        """Snapshots can be created through TimeMachine"""
        state_data = {
            "agents": {"agent1": {"status": "active"}},
            "memory": {"total_memories": 100},
        }
        
        snapshot_id = await time_machine.create_snapshot(
            state_data=state_data,
            name="Test Snapshot",
            description="Test description",
        )
        
        assert snapshot_id is not None
        
        # Verify snapshot exists
        snapshot = await time_machine.get_snapshot(snapshot_id)
        assert snapshot is not None
        assert snapshot.name == "Test Snapshot"
    
    @pytest.mark.asyncio
    async def test_query_events(self, time_machine):
        """Events can be queried through TimeMachine"""
        # Log some events
        await time_machine.log_event(TimelineEvent(
            event_type="test1",
            severity=EventSeverity.INFO,
        ))
        await time_machine.log_event(TimelineEvent(
            event_type="test2",
            severity=EventSeverity.ERROR,
        ))
        
        # Query all events
        all_events = await time_machine.query_events()
        assert len(all_events) >= 2
        
        # Query errors only
        errors = await time_machine.query_events(severity=EventSeverity.ERROR)
        assert len(errors) >= 1
    
    @pytest.mark.asyncio
    async def test_search_events(self, time_machine):
        """Events can be searched through TimeMachine"""
        await time_machine.log_event(TimelineEvent(
            event_type="user_action",
            description="User clicked button",
        ))
        
        results = await time_machine.search_events("button")
        
        assert len(results) >= 1
        assert any("button" in e.description for e in results)
    
    @pytest.mark.asyncio
    async def test_preview_rollback(self, time_machine):
        """Rollback can be previewed"""
        # Create snapshot
        snapshot_state = {
            "agents": {"agent1": "idle", "agent2": "working"},
        }
        snapshot_id = await time_machine.create_snapshot(
            state_data=snapshot_state,
            name="Test Snapshot",
        )
        
        # Current state is different
        current_state = {
            "agents": {"agent1": "working", "agent2": "idle", "agent3": "active"},
        }
        
        # Preview rollback
        preview = await time_machine.preview_rollback(snapshot_id, current_state)
        
        assert preview.can_rollback is True
        assert len(preview.agents_affected) == 3  # All 3 agents changed
        assert preview.snapshot_id == snapshot_id
    
    @pytest.mark.asyncio
    async def test_rollback_dry_run(self, time_machine):
        """Rollback dry run returns preview without changes"""
        snapshot_state = {"test": "data"}
        snapshot_id = await time_machine.create_snapshot(
            state_data=snapshot_state,
            name="Test",
        )
        
        current_state = {"test": "different"}
        
        result = await time_machine.rollback_to_snapshot(
            snapshot_id,
            current_state,
            dry_run=True,
        )
        
        assert result["status"] == "preview"
        assert "preview" in result
    
    @pytest.mark.asyncio
    async def test_rollback_execution(self, time_machine):
        """Rollback execution creates backup and logs event"""
        snapshot_state = {"test": "original"}
        snapshot_id = await time_machine.create_snapshot(
            state_data=snapshot_state,
            name="Original",
        )
        
        current_state = {"test": "current"}
        
        result = await time_machine.rollback_to_snapshot(
            snapshot_id,
            current_state,
            dry_run=False,
        )
        
        assert result["status"] == "success"
        assert "backup_id" in result
        assert "event_id" in result
        
        # Verify backup snapshot was created
        backup = await time_machine.get_snapshot(result["backup_id"])
        assert backup is not None
        assert "pre-rollback" in backup.name.lower()
    
    @pytest.mark.asyncio
    async def test_get_event_statistics(self, time_machine):
        """Event statistics can be retrieved"""
        # Log some events
        for i in range(5):
            await time_machine.log_event(TimelineEvent(
                event_type=f"test_{i}",
                severity=EventSeverity.ERROR if i < 2 else EventSeverity.INFO,
            ))
        
        stats = await time_machine.get_event_statistics()
        
        assert "total_events" in stats
        assert "events_last_hour" in stats
        assert "events_last_day" in stats
        assert "errors_last_hour" in stats
        assert stats["total_events"] >= 5
    
    @pytest.mark.asyncio
    async def test_list_snapshots(self, time_machine):
        """Snapshots can be listed"""
        # Create snapshots
        for i in range(3):
            await time_machine.create_snapshot(
                state_data={"index": i},
                name=f"Snapshot {i}",
            )
        
        snapshots = await time_machine.list_snapshots()
        
        assert len(snapshots) >= 3


class TestAutoSnapshot:
    """Test automatic snapshot creation"""
    
    @pytest.mark.asyncio
    async def test_auto_snapshot_creation(self, temp_dir):
        """Automatic snapshots are created at intervals"""
        tm = TimeMachine(
            timeline_db=f"{temp_dir}/timeline.db",
            snapshot_db=f"{temp_dir}/snapshots.db",
            snapshot_dir=f"{temp_dir}/snapshots",
            auto_snapshot_interval=0.5,  # 500ms for fast testing
        )
        
        await tm.start()
        
        # Wait for at least 2 snapshots
        await asyncio.sleep(1.5)
        
        await tm.stop()
        
        # Check snapshots were created
        snapshots = await tm.list_snapshots()
        
        # Should have at least 2 automatic snapshots
        auto_snapshots = [s for s in snapshots if s.get("trigger") == "automatic"]
        assert len(auto_snapshots) >= 2


class TestEventCorrelation:
    """Test event correlation and relationships"""
    
    @pytest.mark.asyncio
    async def test_correlated_events(self, time_machine):
        """Events can be correlated"""
        correlation_id = "test-correlation-123"
        
        # Log parent event
        parent_event = TimelineEvent(
            event_type="parent_event",
            description="Parent event",
            correlation_id=correlation_id,
        )
        parent_id = await time_machine.log_event(parent_event)
        
        # Log child events
        for i in range(3):
            child_event = TimelineEvent(
                event_type=f"child_event_{i}",
                description=f"Child event {i}",
                correlation_id=correlation_id,
                parent_event_id=parent_id,
            )
            await time_machine.log_event(child_event)
        
        # Query correlated events
        events = await time_machine.query_events()
        correlated = [e for e in events if e.correlation_id == correlation_id]
        
        assert len(correlated) == 4  # 1 parent + 3 children
        
        children = [e for e in correlated if e.parent_event_id == parent_id]
        assert len(children) == 3


class TestRetentionPolicy:
    """Test snapshot retention policy"""
    
    @pytest.mark.asyncio
    async def test_retention_policy(self, temp_dir):
        """Snapshots are retained according to policy"""
        tm = TimeMachine(
            timeline_db=f"{temp_dir}/timeline.db",
            snapshot_db=f"{temp_dir}/snapshots.db",
            snapshot_dir=f"{temp_dir}/snapshots",
            retention_days=1,  # 1 day retention
        )
        
        # Create snapshot
        snapshot_id = await tm.create_snapshot(
            state_data={"test": "data"},
            name="Test Snapshot",
        )
        
        snapshot = await tm.get_snapshot(snapshot_id)
        
        # Should have retained_until set
        assert snapshot.retained_until is not None
        
        # Should be ~1 day in the future
        expected_retention = time.time() + (1 * 86400)
        assert abs(snapshot.retained_until - expected_retention) < 60  # Within 1 minute

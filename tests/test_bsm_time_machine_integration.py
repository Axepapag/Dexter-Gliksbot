"""
Integration tests for BSM and Time Machine.

Tests the complete integration:
1. BSM observes events from all buses
2. BSM logs events to Time Machine timeline
3. Timeline events can be queried
4. State snapshots capture BSM observations
5. Rollback restores previous state
"""
import asyncio
import pytest
import pytest_asyncio
import time
import tempfile
import shutil
from unittest.mock import MagicMock

# Import BSM directly to avoid importing action_executor which needs PIL
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "dexter_autonomy"))

from agents.bsm import BSM
from brain.memory import BrainDB
from brain.time_machine import (
    TimeMachine,
    EventSeverity,
    EventCategory,
)
from core.triple_bus import (
    TripleBusSystem,
    MainTopic,
    CollabTopic,
    PrivateTopic,
)


@pytest.fixture
def temp_dir():
    """Create temporary directory for test databases"""
    temp = tempfile.mkdtemp()
    yield temp
    shutil.rmtree(temp)


@pytest.fixture
def mock_brain():
    """Mock BrainDB"""
    brain = MagicMock(spec=BrainDB)
    brain.add_memory = MagicMock(return_value=1)
    brain.search = MagicMock(return_value=[])
    return brain


@pytest_asyncio.fixture
async def buses():
    """Create triple bus system"""
    buses = TripleBusSystem()
    await buses.start_all()
    yield buses
    await buses.stop_all()


@pytest_asyncio.fixture
async def time_machine(temp_dir):
    """Create Time Machine instance"""
    tm = TimeMachine(
        timeline_db=f"{temp_dir}/timeline.db",
        snapshot_db=f"{temp_dir}/snapshots.db",
        snapshot_dir=f"{temp_dir}/snapshots",
        auto_snapshot_interval=10.0,  # 10 seconds for testing
        retention_days=1,
    )
    await tm.start()
    yield tm
    await tm.stop()


@pytest_asyncio.fixture
async def bsm_with_time_machine(buses, mock_brain, time_machine):
    """BSM with Time Machine integration"""
    bsm = BSM(
        buses=buses,
        brain=mock_brain,
        model=None,
        time_machine=time_machine,
    )
    await bsm.start()
    yield bsm
    await bsm.stop()


class TestBSMTimeMachineIntegration:
    """Test BSM logs events to Time Machine"""
    
    @pytest.mark.asyncio
    async def test_bsm_logs_main_bus_events(self, bsm_with_time_machine, buses, time_machine):
        """BSM automatically logs MAIN bus events to timeline"""
        # Publish user input event
        await buses.main.publish(MainTopic.USER_INPUT, {
            "content": "Test user input",
            "from": "user",
        })
        
        # Wait for observation and logging
        await asyncio.sleep(0.2)
        
        # Query timeline events
        events = await time_machine.query_events(category=EventCategory.USER_INPUT)
        
        assert len(events) >= 1
        user_input_event = events[0]
        assert user_input_event.event_type == "user_input"
        assert user_input_event.category == EventCategory.USER_INPUT
        assert user_input_event.bus == "main"
    
    @pytest.mark.asyncio
    async def test_bsm_logs_collab_bus_events(self, bsm_with_time_machine, buses, time_machine):
        """BSM automatically logs COLLAB bus events to timeline"""
        # Publish proposal event
        await buses.collab.publish(CollabTopic.PROPOSAL, {
            "from": "coder",
            "proposal": {"action": "write code", "file": "test.py"},
        })
        
        await asyncio.sleep(0.2)
        
        # Query timeline events
        events = await time_machine.query_events(category=EventCategory.COLLABORATION)
        
        assert len(events) >= 1
        collab_event = events[0]
        assert collab_event.event_type == "proposal"
        assert collab_event.category == EventCategory.COLLABORATION
        assert collab_event.bus == "collab"
    
    @pytest.mark.asyncio
    async def test_bsm_logs_private_bus_events(self, bsm_with_time_machine, buses, time_machine):
        """BSM automatically logs PRIVATE bus events to timeline"""
        # Create private bus
        private_bus = await buses.get_private("test_agent")
        await asyncio.sleep(2.5)  # Wait for BSM to subscribe
        
        # Publish task assignment
        await private_bus.publish(PrivateTopic.TASK_ASSIGNMENT, {
            "from": "dexter",
            "to": "test_agent",
            "task": {"description": "Test task"},
        })
        
        await asyncio.sleep(0.2)
        
        # Query timeline events
        events = await time_machine.query_events(agent_id="dexter")
        
        # Should have events (might include subscription and task assignment)
        assert len(events) >= 1
    
    @pytest.mark.asyncio
    async def test_bsm_logs_error_events_with_error_severity(self, bsm_with_time_machine, buses, time_machine):
        """BSM logs ERROR topic with ERROR severity"""
        # Publish error event
        await buses.main.publish(MainTopic.ERROR, {
            "message": "Test error occurred",
            "from": "system",
        })
        
        await asyncio.sleep(0.2)
        
        # Query error events
        events = await time_machine.query_events(severity=EventSeverity.ERROR)
        
        assert len(events) >= 1
        error_event = events[0]
        assert error_event.severity == EventSeverity.ERROR
        assert error_event.category == EventCategory.ERROR_EVENT
    
    @pytest.mark.asyncio
    async def test_event_correlation_through_bsm(self, bsm_with_time_machine, buses, time_machine):
        """BSM preserves correlation IDs in timeline events"""
        correlation_id = "test-correlation-123"
        
        # Publish events with same correlation ID
        await buses.main.publish(MainTopic.INTENT, {
            "kind": "click",
            "from": "dexter",
            "to": "action_executor",
            "correlation_id": correlation_id,
        })
        
        await buses.main.publish(MainTopic.EFFECT, {
            "status": "success",
            "from": "action_executor",
            "correlation_id": correlation_id,
        })
        
        await asyncio.sleep(0.2)
        
        # Query correlated events
        all_events = await time_machine.query_events()
        correlated = [e for e in all_events if e.correlation_id == correlation_id]
        
        assert len(correlated) >= 2
    
    @pytest.mark.asyncio
    async def test_timeline_search_finds_bsm_logged_events(self, bsm_with_time_machine, buses, time_machine):
        """Timeline search finds events logged by BSM"""
        # Publish event with unique content
        await buses.main.publish(MainTopic.USER_INPUT, {
            "content": "Find the unicorn button and click it",
            "from": "user",
        })
        
        await asyncio.sleep(0.2)
        
        # Search for unique term
        results = await time_machine.search_events("unicorn")
        
        assert len(results) >= 1
        assert any("unicorn" in e.description.lower() for e in results)


class TestSnapshotWithBSMData:
    """Test snapshots capture BSM observation data"""
    
    @pytest.mark.asyncio
    async def test_snapshot_includes_bsm_stats(self, bsm_with_time_machine, buses, time_machine):
        """Snapshots can include BSM statistics"""
        # Generate some BSM activity
        await buses.main.publish(MainTopic.USER_INPUT, {"content": "test1"})
        await buses.main.publish(MainTopic.USER_INPUT, {"content": "test2"})
        await asyncio.sleep(0.2)
        
        # Get BSM stats
        bsm_stats = bsm_with_time_machine.get_stats()
        
        # Create snapshot with BSM data
        state_data = {
            "bsm": bsm_stats,
            "timestamp": time.time(),
        }
        
        snapshot_id = await time_machine.create_snapshot(
            state_data=state_data,
            name="BSM State Snapshot",
            description="Includes BSM observation statistics",
        )
        
        # Retrieve snapshot
        snapshot = await time_machine.get_snapshot(snapshot_id)
        
        assert snapshot is not None
        assert "bsm" in snapshot.state_data
        assert snapshot.state_data["bsm"]["observations"] >= 2
    
    @pytest.mark.asyncio
    async def test_snapshot_triggered_by_critical_event(self, bsm_with_time_machine, buses, time_machine):
        """Critical events can trigger snapshot creation"""
        # Simulate critical error
        await buses.main.publish(MainTopic.ERROR, {
            "message": "Critical system failure",
            "severity": "critical",
            "from": "system",
        })
        
        await asyncio.sleep(0.2)
        
        # Query critical events
        critical_events = await time_machine.query_events(severity=EventSeverity.ERROR)
        
        if critical_events:
            # Create snapshot associated with critical event
            snapshot_id = await time_machine.create_snapshot(
                state_data={"error_state": "captured"},
                name="Critical Error Snapshot",
                trigger="critical_event",
                trigger_event_id=critical_events[0].id,
                tags=["critical", "error", "automatic"],
            )
            
            snapshot = await time_machine.get_snapshot(snapshot_id)
            
            assert snapshot.trigger == "critical_event"
            assert snapshot.trigger_event_id == critical_events[0].id
            assert "critical" in snapshot.tags


class TestEventStatisticsWithBSM:
    """Test event statistics reflect BSM activity"""
    
    @pytest.mark.asyncio
    async def test_event_count_matches_bsm_observations(self, bsm_with_time_machine, buses, time_machine):
        """Timeline event count reflects BSM observations"""
        initial_observations = bsm_with_time_machine._observation_count
        
        # Generate activity
        for i in range(5):
            await buses.main.publish(MainTopic.TRACE, {
                "message": f"Trace {i}",
            })
        
        await asyncio.sleep(0.3)
        
        # Check BSM observed them
        final_observations = bsm_with_time_machine._observation_count
        assert final_observations >= initial_observations + 5
        
        # Check timeline has events
        stats = await time_machine.get_event_statistics()
        assert stats["events_last_hour"] >= 5
    
    @pytest.mark.asyncio
    async def test_event_categories_reflect_bus_activity(self, bsm_with_time_machine, buses, time_machine):
        """Different bus activities create different event categories"""
        # User input (main bus)
        await buses.main.publish(MainTopic.USER_INPUT, {"content": "test"})
        
        # Collaboration (collab bus)
        await buses.collab.publish(CollabTopic.PROPOSAL, {"proposal": "test"})
        
        # Agent action (main bus)
        await buses.main.publish(MainTopic.INTENT, {"kind": "test"})
        
        await asyncio.sleep(0.2)
        
        # Check different categories exist
        user_events = await time_machine.query_events(category=EventCategory.USER_INPUT)
        collab_events = await time_machine.query_events(category=EventCategory.COLLABORATION)
        agent_events = await time_machine.query_events(category=EventCategory.AGENT_ACTION)
        
        assert len(user_events) >= 1
        assert len(collab_events) >= 1
        assert len(agent_events) >= 1


class TestRollbackWithBSM:
    """Test rollback integrates with BSM state"""
    
    @pytest.mark.asyncio
    async def test_rollback_preview_with_bsm_state(self, bsm_with_time_machine, buses, time_machine):
        """Rollback preview shows BSM state differences"""
        # Create snapshot with initial BSM state
        initial_stats = bsm_with_time_machine.get_stats()
        snapshot_id = await time_machine.create_snapshot(
            state_data={"bsm": initial_stats},
            name="Initial BSM State",
        )
        
        # Generate more activity
        for i in range(10):
            await buses.main.publish(MainTopic.USER_INPUT, {"content": f"activity {i}"})
        await asyncio.sleep(0.3)
        
        # Get current state
        current_stats = bsm_with_time_machine.get_stats()
        current_state = {"bsm": current_stats}
        
        # Preview rollback
        preview = await time_machine.preview_rollback(snapshot_id, current_state)
        
        assert preview.can_rollback is True
        assert "bsm" in preview.state_differences
    
    @pytest.mark.asyncio
    async def test_rollback_creates_backup_snapshot(self, bsm_with_time_machine, buses, time_machine):
        """Rollback automatically creates backup snapshot"""
        # Create initial snapshot
        snapshot_id = await time_machine.create_snapshot(
            state_data={"test": "initial"},
            name="Initial State",
        )
        
        # Execute rollback
        result = await time_machine.rollback_to_snapshot(
            snapshot_id=snapshot_id,
            current_state={"test": "current"},
            dry_run=False,
        )
        
        assert result["status"] == "success"
        assert "backup_id" in result
        
        # Verify backup snapshot exists
        backup = await time_machine.get_snapshot(result["backup_id"])
        assert backup is not None
        assert "backup" in backup.name.lower()
        assert backup.trigger == "pre_rollback_backup"


class TestBSMStatsWithTimeMachine:
    """Test BSM statistics include Time Machine status"""
    
    @pytest.mark.asyncio
    async def test_bsm_stats_shows_time_machine_enabled(self, bsm_with_time_machine):
        """BSM stats indicate Time Machine is enabled"""
        stats = bsm_with_time_machine.get_stats()
        
        assert "time_machine_enabled" in stats
        assert stats["time_machine_enabled"] is True
    
    @pytest.mark.asyncio
    async def test_bsm_without_time_machine(self, buses, mock_brain):
        """BSM can run without Time Machine"""
        bsm_no_tm = BSM(
            buses=buses,
            brain=mock_brain,
            model=None,
            time_machine=None,
        )
        await bsm_no_tm.start()
        
        # Should work normally
        await buses.main.publish(MainTopic.USER_INPUT, {"content": "test"})
        await asyncio.sleep(0.1)
        
        stats = bsm_no_tm.get_stats()
        assert stats["time_machine_enabled"] is False
        assert stats["observations"] >= 1
        
        await bsm_no_tm.stop()


class TestEndToEndScenario:
    """End-to-end integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self, bsm_with_time_machine, buses, time_machine):
        """
        Complete workflow: User input → BSM observes → Timeline logs → Snapshot → Query
        """
        # Step 1: User sends input
        await buses.main.publish(MainTopic.USER_INPUT, {
            "content": "Calculate invoice total",
            "from": "user",
        })
        
        # Step 2: System responds with intent
        await buses.main.publish(MainTopic.INTENT, {
            "kind": "calculate",
            "args": {"operation": "invoice_total"},
            "from": "dexter",
            "to": "calculator",
        })
        
        # Step 3: Effect reported
        await buses.main.publish(MainTopic.EFFECT, {
            "status": "success",
            "result": {"total": 1234.56},
            "from": "calculator",
        })
        
        await asyncio.sleep(0.3)
        
        # Step 4: Verify BSM observed all events
        assert bsm_with_time_machine._observation_count >= 3
        
        # Step 5: Verify timeline has all events
        events = await time_machine.query_events(limit=100)
        assert len(events) >= 3
        
        # Step 6: Search timeline
        calc_events = await time_machine.search_events("calculate")
        assert len(calc_events) >= 1
        
        # Step 7: Create snapshot
        snapshot_id = await time_machine.create_snapshot(
            state_data={
                "workflow": "complete",
                "events": len(events),
            },
            name="Workflow Complete Snapshot",
        )
        
        # Step 8: Verify snapshot exists
        snapshot = await time_machine.get_snapshot(snapshot_id)
        assert snapshot is not None
        assert snapshot.state_data["workflow"] == "complete"

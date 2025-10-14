"""
Tests for CollaborationManager - Happy Path Scenarios

These tests cover the normal flow:
- Session creation and lifecycle
- Phase transitions (observable pattern)
- Proposal collection with good participation
- Voting with clear consensus
- Timeout calculations (Comet's multi-factor strategy)
- Nesting support within limits
- Agent performance tracking (hints, not penalties)

Edge case tests (partial participation, interruptions, etc.) 
will be added by Comet per our collaborative agreement.
"""
import asyncio
import pytest
import pytest_asyncio
import time
from unittest.mock import AsyncMock, MagicMock

from dexter_autonomy.core.triple_bus import TripleBusSystem, CollabTopic
from dexter_autonomy.core.collaboration_manager import (
    CollaborationManager,
    CollaborationPhase,
    CollaborationPriority,
    CONSENSUS_CONFIG,
    MAX_NESTING_DEPTH
)


@pytest.fixture
def buses():
    """Create triple bus system"""
    return TripleBusSystem()


@pytest_asyncio.fixture
async def collab_manager(buses):
    """Create collaboration manager"""
    manager = CollaborationManager(buses)
    
    # Start buses
    await buses.start_all()
    
    yield manager
    
    # Cleanup
    await buses.stop_all()


@pytest.mark.asyncio
async def test_start_collaboration_creates_session(collab_manager):
    """Test starting a collaboration session"""
    observation = {"task": "Process invoice", "details": "Need to extract data"}
    invited_agents = ["coder", "scraper"]
    
    session_id = await collab_manager.start_collaboration(
        observation=observation,
        invited_agents=invited_agents,
        priority=CollaborationPriority.NORMAL
    )
    
    assert session_id in collab_manager.active_sessions
    session = collab_manager.active_sessions[session_id]
    
    assert session.observation == observation
    assert session.invited_agents == invited_agents
    assert session.phase == CollaborationPhase.OBSERVATION
    assert session.priority == CollaborationPriority.NORMAL
    assert session.nesting_level == 0
    assert session.parent_session_id is None


@pytest.mark.asyncio
async def test_phase_transitions_observable(collab_manager, buses):
    """Test that phase transitions are broadcast to COLLAB bus (BSM observability)"""
    # Track phase transition events
    transitions = []
    
    async def transition_listener(msg):
        if msg.get("event") == "phase_transition":
            transitions.append(msg)
    
    buses.collab.subscribe(CollabTopic.OBSERVATION, transition_listener)
    
    # Start session
    session_id = await collab_manager.start_collaboration(
        observation={"task": "test"},
        invited_agents=["agent1"],
        priority=CollaborationPriority.NORMAL
    )
    
    # Trigger phase transitions
    await collab_manager._transition_phase(session_id, CollaborationPhase.PROPOSAL_COLLECTION)
    await collab_manager._transition_phase(session_id, CollaborationPhase.VOTING)
    
    # Give async handlers time to process
    await asyncio.sleep(0.1)
    
    # Should have 2 transitions (OBSERVATION → PROPOSAL_COLLECTION → VOTING)
    assert len(transitions) == 2
    assert transitions[0]["new_phase"] == CollaborationPhase.PROPOSAL_COLLECTION.value
    assert transitions[1]["new_phase"] == CollaborationPhase.VOTING.value


@pytest.mark.asyncio
async def test_collect_proposals_happy_path(collab_manager, buses):
    """Test proposal collection with all agents responding"""
    # Start session
    session_id = await collab_manager.start_collaboration(
        observation={"task": "test"},
        invited_agents=["agent1", "agent2"],
        priority=CollaborationPriority.NORMAL
    )
    
    # Simulate agents responding to proposal request
    async def simulate_agent_responses():
        await asyncio.sleep(0.1)  # Simulate thinking time
        
        # Agent 1 response
        await buses.collab.publish(CollabTopic.PROPOSAL, {
            "event": "proposal_response",
            "session_id": session_id,
            "from_agent": "agent1",
            "proposal": {
                "id": "proposal_1",
                "solution": "Use regex to extract invoice data",
                "confidence": 0.85
            }
        })
        
        # Agent 2 response
        await buses.collab.publish(CollabTopic.PROPOSAL, {
            "event": "proposal_response",
            "session_id": session_id,
            "from_agent": "agent2",
            "proposal": {
                "id": "proposal_2",
                "solution": "Use OCR then parse with LLM",
                "confidence": 0.75
            }
        })
    
    # Start simulation in background
    response_task = asyncio.create_task(simulate_agent_responses())
    
    # Collect proposals
    proposals = await collab_manager.collect_proposals(session_id)
    
    await response_task
    
    # Verify proposals collected
    assert len(proposals) == 2
    assert proposals[0]["id"] == "proposal_1"
    assert proposals[1]["id"] == "proposal_2"
    
    # Verify proposals stored in session
    session = collab_manager.active_sessions[session_id]
    assert len(session.proposals) == 2


@pytest.mark.asyncio
async def test_voting_with_clear_winner(collab_manager, buses):
    """Test voting phase with clear consensus"""
    # Start session and add proposals
    session_id = await collab_manager.start_collaboration(
        observation={"task": "test"},
        invited_agents=["agent1", "agent2", "agent3"],
        priority=CollaborationPriority.NORMAL
    )
    
    proposals = [
        {"id": "proposal_1", "solution": "Solution A", "confidence": 0.85},
        {"id": "proposal_2", "solution": "Solution B", "confidence": 0.70},
    ]
    
    session = collab_manager.active_sessions[session_id]
    session.proposals = proposals
    
    # Simulate voting responses
    async def simulate_votes():
        await asyncio.sleep(0.1)
        
        # All agents vote for proposal_1 with high confidence
        for agent_id in ["agent1", "agent2", "agent3"]:
            await buses.collab.publish(CollabTopic.VOTE_RESPONSE, {
                "session_id": session_id,
                "from_agent": agent_id,
                "proposal_id": "proposal_1",
                "confidence": 0.85
            })
    
    vote_task = asyncio.create_task(simulate_votes())
    
    # Call vote
    votes = await collab_manager.call_vote(session_id, proposals)
    
    await vote_task
    
    # Verify votes collected
    assert len(votes) == 3
    assert all(v["proposal_id"] == "proposal_1" for v in votes)


@pytest.mark.asyncio
async def test_reach_consensus_success(collab_manager):
    """Test reaching valid consensus (Comet's confidence threshold design)"""
    # Start session
    session_id = await collab_manager.start_collaboration(
        observation={"task": "test"},
        invited_agents=["agent1", "agent2", "agent3"],
        priority=CollaborationPriority.NORMAL
    )
    
    session = collab_manager.active_sessions[session_id]
    
    # Set up proposals
    session.proposals = [
        {"id": "proposal_1", "solution": "Solution A", "confidence": 0.85},
        {"id": "proposal_2", "solution": "Solution B", "confidence": 0.50},
    ]
    
    # Set up votes (clear winner with high confidence)
    session.votes = [
        {"from_agent": "agent1", "proposal_id": "proposal_1", "confidence": 0.85},
        {"from_agent": "agent2", "proposal_id": "proposal_1", "confidence": 0.80},
        {"from_agent": "agent3", "proposal_id": "proposal_1", "confidence": 0.75},
    ]
    
    # Reach consensus
    result = await collab_manager.reach_consensus(session_id)
    
    # Verify consensus reached
    assert result["status"] == "consensus_reached"
    assert result["winner"]["id"] == "proposal_1"
    assert result["support_percent"] >= CONSENSUS_CONFIG["winning_threshold"]
    assert result["confidence"] >= CONSENSUS_CONFIG["confidence_floor"]


@pytest.mark.asyncio
async def test_dynamic_timeout_calculation(collab_manager):
    """Test Comet's multi-factor timeout strategy"""
    strategy = collab_manager.timeout_strategy
    
    # Test priority factor
    critical_timeout = strategy.calculate_timeout(
        phase=CollaborationPhase.PROPOSAL_COLLECTION,
        priority=CollaborationPriority.CRITICAL,
        agent_count=3
    )
    
    normal_timeout = strategy.calculate_timeout(
        phase=CollaborationPhase.PROPOSAL_COLLECTION,
        priority=CollaborationPriority.NORMAL,
        agent_count=3
    )
    
    # Critical should be faster (0.5x multiplier)
    assert critical_timeout < normal_timeout
    
    # Test agent count scaling
    few_agents_timeout = strategy.calculate_timeout(
        phase=CollaborationPhase.PROPOSAL_COLLECTION,
        priority=CollaborationPriority.NORMAL,
        agent_count=2
    )
    
    many_agents_timeout = strategy.calculate_timeout(
        phase=CollaborationPhase.PROPOSAL_COLLECTION,
        priority=CollaborationPriority.NORMAL,
        agent_count=10
    )
    
    # More agents = more time (capped at 2x)
    assert many_agents_timeout > few_agents_timeout
    assert many_agents_timeout <= normal_timeout * 2  # Capped scaling


@pytest.mark.asyncio
async def test_adaptive_timeout_with_history(collab_manager):
    """Test adaptive timeouts based on historical performance"""
    strategy = collab_manager.timeout_strategy
    
    # Record some fast response times for agent1
    for _ in range(10):
        strategy.record_response_time("agent1", 0.5)  # Fast responder
    
    # Record some slow response times for agent2
    for _ in range(10):
        strategy.record_response_time("agent2", 5.0)  # Slow responder
    
    # Calculate timeout for session with these agents
    timeout_fast = strategy.calculate_timeout(
        phase=CollaborationPhase.PROPOSAL_COLLECTION,
        priority=CollaborationPriority.NORMAL,
        agent_count=2,
        session_context={"invited_agents": ["agent1"]}
    )
    
    timeout_slow = strategy.calculate_timeout(
        phase=CollaborationPhase.PROPOSAL_COLLECTION,
        priority=CollaborationPriority.NORMAL,
        agent_count=2,
        session_context={"invited_agents": ["agent2"]}
    )
    
    # Timeout should adapt to agent speed
    assert timeout_slow > timeout_fast


@pytest.mark.asyncio
async def test_nesting_within_limits(collab_manager):
    """Test nested collaborations up to MAX_NESTING_DEPTH"""
    # Create root collaboration (level 0)
    root_id = await collab_manager.start_collaboration(
        observation={"task": "root"},
        invited_agents=["agent1"],
        priority=CollaborationPriority.NORMAL
    )
    
    assert collab_manager.active_sessions[root_id].nesting_level == 0
    
    # Create child collaboration (level 1)
    child_id = await collab_manager.start_collaboration(
        observation={"task": "child"},
        invited_agents=["agent2"],
        priority=CollaborationPriority.NORMAL,
        parent_session_id=root_id
    )
    
    assert collab_manager.active_sessions[child_id].nesting_level == 1
    assert collab_manager.active_sessions[root_id].child_sessions == [child_id]
    
    # Create grandchild collaboration (level 2 - max depth)
    grandchild_id = await collab_manager.start_collaboration(
        observation={"task": "grandchild"},
        invited_agents=["agent3"],
        priority=CollaborationPriority.NORMAL,
        parent_session_id=child_id
    )
    
    assert collab_manager.active_sessions[grandchild_id].nesting_level == 2


@pytest.mark.asyncio
async def test_nesting_depth_exceeded(collab_manager):
    """Test that nesting beyond MAX_NESTING_DEPTH raises error"""
    # Create chain up to max depth
    root_id = await collab_manager.start_collaboration(
        observation={"task": "root"},
        invited_agents=["agent1"],
        priority=CollaborationPriority.NORMAL
    )
    
    child_id = await collab_manager.start_collaboration(
        observation={"task": "child"},
        invited_agents=["agent2"],
        priority=CollaborationPriority.NORMAL,
        parent_session_id=root_id
    )
    
    grandchild_id = await collab_manager.start_collaboration(
        observation={"task": "grandchild"},
        invited_agents=["agent3"],
        priority=CollaborationPriority.NORMAL,
        parent_session_id=child_id
    )
    
    # Try to create great-grandchild (level 3 - should fail)
    with pytest.raises(ValueError, match="Max nesting depth"):
        await collab_manager.start_collaboration(
            observation={"task": "great-grandchild"},
            invited_agents=["agent4"],
            priority=CollaborationPriority.NORMAL,
            parent_session_id=grandchild_id
        )


@pytest.mark.asyncio
async def test_agent_performance_tracking(collab_manager, buses):
    """Test agent response rate tracking (hints, not penalties)"""
    # Start session
    session_id = await collab_manager.start_collaboration(
        observation={"task": "test"},
        invited_agents=["agent1", "agent2", "agent3"],
        priority=CollaborationPriority.NORMAL
    )
    
    # Simulate partial responses
    async def simulate_partial_responses():
        await asyncio.sleep(0.1)
        
        # Only agent1 and agent2 respond (agent3 silent)
        await buses.collab.publish(CollabTopic.PROPOSAL, {
            "event": "proposal_response",
            "session_id": session_id,
            "from_agent": "agent1",
            "proposal": {"id": "p1", "solution": "A", "confidence": 0.8}
        })
        
        await buses.collab.publish(CollabTopic.PROPOSAL, {
            "event": "proposal_response",
            "session_id": session_id,
            "from_agent": "agent2",
            "proposal": {"id": "p2", "solution": "B", "confidence": 0.7}
        })
    
    response_task = asyncio.create_task(simulate_partial_responses())
    await collab_manager.collect_proposals(session_id)
    await response_task
    
    # Check performance hints
    hints = collab_manager.get_agent_performance_hints()
    
    assert "agent1" in hints
    assert "agent2" in hints
    assert "agent3" in hints
    
    # Agent1 and Agent2 should have 100% response rate
    assert hints["agent1"] == 1.0
    assert hints["agent2"] == 1.0
    
    # Agent3 should have 0% response rate
    assert hints["agent3"] == 0.0


@pytest.mark.asyncio
async def test_session_stats_for_bsm(collab_manager):
    """Test session statistics (for BSM learning)"""
    # Start session
    session_id = await collab_manager.start_collaboration(
        observation={"task": "test"},
        invited_agents=["agent1", "agent2"],
        priority=CollaborationPriority.HIGH
    )
    
    session = collab_manager.active_sessions[session_id]
    
    # Add some workflow data
    session.proposals = [{"id": "p1"}, {"id": "p2"}]
    session.votes = [{"proposal_id": "p1"}, {"proposal_id": "p1"}]
    
    # Transition through phases
    await collab_manager._transition_phase(session_id, CollaborationPhase.PROPOSAL_COLLECTION)
    await collab_manager._transition_phase(session_id, CollaborationPhase.VOTING)
    
    # Get stats
    stats = collab_manager.get_session_stats(session_id)
    
    assert stats is not None
    assert stats["session_id"] == session_id
    assert stats["phase"] == CollaborationPhase.VOTING.value
    assert stats["priority"] == CollaborationPriority.HIGH.value
    assert stats["proposal_count"] == 2
    assert stats["vote_count"] == 2
    assert stats["phase_count"] == 2  # 2 transitions recorded


@pytest.mark.asyncio
async def test_critical_interrupt_aborts_collaboration(collab_manager):
    """Test CRITICAL interrupt aborts collaboration immediately"""
    # Start session
    session_id = await collab_manager.start_collaboration(
        observation={"task": "test"},
        invited_agents=["agent1"],
        priority=CollaborationPriority.NORMAL
    )
    
    # Critical interrupt
    await collab_manager.handle_user_interrupt(
        session_id=session_id,
        priority=CollaborationPriority.CRITICAL,
        command={"action": "stop"}
    )
    
    # Session should be removed (aborted)
    assert session_id not in collab_manager.active_sessions


@pytest.mark.asyncio
async def test_high_priority_interrupt_pauses_collaboration(collab_manager):
    """Test HIGH priority interrupt pauses collaboration"""
    # Start session
    session_id = await collab_manager.start_collaboration(
        observation={"task": "test"},
        invited_agents=["agent1"],
        priority=CollaborationPriority.NORMAL
    )
    
    # High priority interrupt
    await collab_manager.handle_user_interrupt(
        session_id=session_id,
        priority=CollaborationPriority.HIGH,
        command={"action": "urgent_task"}
    )
    
    # Session should be paused (still exists)
    session = collab_manager.active_sessions[session_id]
    assert session.paused is True
    assert session.phase == CollaborationPhase.PAUSED


@pytest.mark.asyncio
async def test_normal_interrupt_queues_command(collab_manager):
    """Test NORMAL/LOW interrupt queues command for later"""
    # Start session
    session_id = await collab_manager.start_collaboration(
        observation={"task": "test"},
        invited_agents=["agent1"],
        priority=CollaborationPriority.NORMAL
    )
    
    command = {"action": "low_priority_task"}
    
    # Normal priority interrupt
    await collab_manager.handle_user_interrupt(
        session_id=session_id,
        priority=CollaborationPriority.NORMAL,
        command=command
    )
    
    # Session continues, command queued
    session = collab_manager.active_sessions[session_id]
    assert session.phase != CollaborationPhase.PAUSED
    assert session.queued_commands == [command]


@pytest.mark.asyncio
async def test_full_workflow_end_to_end(collab_manager, buses):
    """Test complete collaboration workflow: start → proposals → vote → consensus"""
    # Start collaboration
    session_id = await collab_manager.start_collaboration(
        observation={"task": "Process invoice #12345"},
        invited_agents=["coder", "scraper"],
        priority=CollaborationPriority.NORMAL
    )
    
    # Simulate complete workflow - responds to real requests
    async def simulate_workflow():
        # Wait for observation broadcast
        await asyncio.sleep(0.1)
        
        # Listen for proposal request
        proposal_requested = asyncio.Event()
        async def proposal_request_listener(msg):
            if msg.get("event") == "proposal_request" and msg.get("session_id") == session_id:
                proposal_requested.set()
        
        buses.collab.subscribe(CollabTopic.PROPOSAL, proposal_request_listener)
        
        try:
            # Wait for proposal request (with timeout)
            await asyncio.wait_for(proposal_requested.wait(), timeout=2.0)
            
            # Agents send proposals
            await buses.collab.publish(CollabTopic.PROPOSAL, {
                "event": "proposal_response",
                "session_id": session_id,
                "from_agent": "coder",
                "proposal": {
                    "id": "coder_proposal",
                    "solution": "Write Python script to extract data",
                    "confidence": 0.85
                }
            })
            
            await buses.collab.publish(CollabTopic.PROPOSAL, {
                "event": "proposal_response",
                "session_id": session_id,
                "from_agent": "scraper",
                "proposal": {
                    "id": "scraper_proposal",
                    "solution": "Use BeautifulSoup to parse HTML",
                    "confidence": 0.70
                }
            })
        finally:
            buses.collab.unsubscribe(CollabTopic.PROPOSAL, proposal_request_listener)
        
        # Listen for vote request
        vote_requested = asyncio.Event()
        async def vote_request_listener(msg):
            if msg.get("session_id") == session_id:
                vote_requested.set()
        
        buses.collab.subscribe(CollabTopic.VOTE_REQUEST, vote_request_listener)
        
        try:
            # Wait for vote request
            await asyncio.wait_for(vote_requested.wait(), timeout=2.0)
            
            # Agents vote
            await buses.collab.publish(CollabTopic.VOTE_RESPONSE, {
                "session_id": session_id,
                "from_agent": "coder",
                "proposal_id": "coder_proposal",
                "confidence": 0.85
            })
            
            await buses.collab.publish(CollabTopic.VOTE_RESPONSE, {
                "session_id": session_id,
                "from_agent": "scraper",
                "proposal_id": "coder_proposal",
                "confidence": 0.75
            })
        finally:
            buses.collab.unsubscribe(CollabTopic.VOTE_REQUEST, vote_request_listener)
    
    workflow_task = asyncio.create_task(simulate_workflow())
    
    # Orchestrate workflow
    await collab_manager.broadcast_observation(session_id, {"task": "Process invoice"})
    proposals = await collab_manager.collect_proposals(session_id)
    votes = await collab_manager.call_vote(session_id, proposals)
    consensus = await collab_manager.reach_consensus(session_id)
    
    await workflow_task
    
    # Verify complete workflow
    assert len(proposals) == 2
    assert len(votes) == 2
    assert consensus["status"] == "consensus_reached"
    assert consensus["winner"]["id"] == "coder_proposal"
    
    # Verify session completed
    session = collab_manager.active_sessions[session_id]
    assert session.completed_at is not None
    assert session.consensus is not None

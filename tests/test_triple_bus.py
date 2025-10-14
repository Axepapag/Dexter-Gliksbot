"""
Tests for Triple Event Bus Architecture

Tests cover:
- Basic pub/sub on each bus (MAIN, COLLAB, PRIVATE)
- BSM subscribing to ALL buses
- Dexter subscribing to ALL buses
- General agent state transitions (idle → on-task → idle)
- Message metadata injection (id, ts, bus, topic)
- Error handling in subscribers
- Lazy PRIVATE bus creation
- Bus lifecycle (start/stop)
"""
import asyncio
import pytest
import pytest_asyncio
from dexter_autonomy.core.triple_bus import (
    TripleBusSystem,
    MainTopic,
    CollabTopic,
    PrivateTopic,
    get_global_triple_bus,
    reset_global_triple_bus,
)


@pytest_asyncio.fixture
async def triple_bus():
    """Fresh triple bus system for each test"""
    buses = TripleBusSystem()
    await buses.start_all()
    yield buses
    await buses.stop_all()
    reset_global_triple_bus()


@pytest.mark.asyncio
async def test_main_bus_user_conversation(triple_bus):
    """Test MAIN bus: User → Dexter conversation"""
    received = []
    
    async def handler(msg):
        received.append(msg)
    
    # Subscribe to USER_INPUT and DEXTER_RESPONSE
    triple_bus.main.subscribe(MainTopic.USER_INPUT, handler)
    triple_bus.main.subscribe(MainTopic.DEXTER_RESPONSE, handler)
    
    # User speaks
    await triple_bus.main.publish(MainTopic.USER_INPUT, {
        "content": "Hello Dexter",
        "user_id": "test_user"
    })
    
    # Dexter responds
    await triple_bus.main.publish(MainTopic.DEXTER_RESPONSE, {
        "content": "Hello! How can I help?",
        "actions": []
    })
    
    await asyncio.sleep(0.1)  # Let drain process
    
    assert len(received) == 2
    assert received[0]["content"] == "Hello Dexter"
    assert received[0]["bus"] == "main"
    assert received[0]["topic"] == "user_input"
    assert "id" in received[0]
    assert "ts" in received[0]
    
    assert received[1]["content"] == "Hello! How can I help?"
    assert received[1]["bus"] == "main"


@pytest.mark.asyncio
async def test_collab_bus_idle_collaboration(triple_bus):
    """Test COLLAB bus: Idle agents collaborate"""
    received = []
    
    async def coder_handler(msg):
        received.append(("coder", msg))
    
    async def writer_handler(msg):
        received.append(("writer", msg))
    
    # Both agents subscribe to COLLAB topics
    triple_bus.collab.subscribe(CollabTopic.PROPOSAL, coder_handler)
    triple_bus.collab.subscribe(CollabTopic.PROPOSAL, writer_handler)
    triple_bus.collab.subscribe(CollabTopic.REFINEMENT, coder_handler)
    triple_bus.collab.subscribe(CollabTopic.REFINEMENT, writer_handler)
    
    # Coder proposes
    await triple_bus.collab.publish(CollabTopic.PROPOSAL, {
        "from": "coder",
        "proposal": "Use FastAPI for the REST endpoint"
    })
    
    # Writer refines
    await triple_bus.collab.publish(CollabTopic.REFINEMENT, {
        "from": "writer",
        "refines": "coder",
        "improvement": "Add OpenAPI documentation"
    })
    
    await asyncio.sleep(0.1)
    
    # Both agents received both messages
    assert len(received) == 4
    assert received[0][0] == "coder"
    assert received[0][1]["from"] == "coder"
    assert received[1][0] == "writer"
    assert received[1][1]["from"] == "coder"
    assert received[2][0] == "coder"
    assert received[2][1]["from"] == "writer"
    assert received[3][0] == "writer"
    assert received[3][1]["from"] == "writer"


@pytest.mark.asyncio
async def test_private_bus_on_task(triple_bus):
    """Test PRIVATE bus: On-task communication"""
    received = []
    
    async def agent_handler(msg):
        received.append(msg)
    
    # Get private bus for web_scraper agent
    private_bus = await triple_bus.get_private("web_scraper")
    
    # Agent subscribes to PRIVATE topics
    private_bus.subscribe(PrivateTopic.TASK_ASSIGNMENT, agent_handler)
    private_bus.subscribe(PrivateTopic.DEXTER_SUPPORT, agent_handler)
    private_bus.subscribe(PrivateTopic.CONTEXT_UPDATE, agent_handler)
    
    # Dexter assigns task
    await private_bus.publish(PrivateTopic.TASK_ASSIGNMENT, {
        "from": "dexter",
        "to": "web_scraper",
        "task": "Scrape product prices from example.com"
    })
    
    # BSM provides context
    await private_bus.publish(PrivateTopic.CONTEXT_UPDATE, {
        "from": "bsm",
        "to": "web_scraper",
        "context": {"past_scrapes": [...]}
    })
    
    # Dexter provides support
    await private_bus.publish(PrivateTopic.DEXTER_SUPPORT, {
        "from": "dexter",
        "to": "web_scraper",
        "support": "Try CSS selector 'div.price'"
    })
    
    await asyncio.sleep(0.1)
    
    assert len(received) == 3
    assert received[0]["bus"] == "private:web_scraper"
    assert received[0]["task"] == "Scrape product prices from example.com"
    
    # Check remaining messages (order may vary)
    sources = {msg.get("from") for msg in received[1:]}
    assert "bsm" in sources
    assert "dexter" in sources


@pytest.mark.asyncio
async def test_bsm_observes_everything(triple_bus):
    """Test BSM subscribing to ALL buses"""
    bsm_observations = []
    
    async def bsm_observer(msg):
        bsm_observations.append(msg)
    
    # BSM subscribes to MAIN bus (all topics)
    for topic in MainTopic:
        triple_bus.main.subscribe(topic, bsm_observer)
    
    # BSM subscribes to COLLAB bus (all topics)
    for topic in CollabTopic:
        triple_bus.collab.subscribe(topic, bsm_observer)
    
    # Create private bus and BSM subscribes
    private_bus = await triple_bus.get_private("test_agent")
    for topic in PrivateTopic:
        private_bus.subscribe(topic, bsm_observer)
    
    # Publish to MAIN
    await triple_bus.main.publish(MainTopic.USER_INPUT, {"content": "test main"})
    
    # Publish to COLLAB
    await triple_bus.collab.publish(CollabTopic.PROPOSAL, {"content": "test collab"})
    
    # Publish to PRIVATE
    await private_bus.publish(PrivateTopic.PROGRESS, {"content": "test private"})
    
    await asyncio.sleep(0.1)
    
    # BSM received all 3 messages
    assert len(bsm_observations) == 3
    buses_observed = {obs["bus"] for obs in bsm_observations}
    assert buses_observed == {"main", "collab", "private:test_agent"}


@pytest.mark.asyncio
async def test_dexter_monitors_everything(triple_bus):
    """Test Dexter subscribing to ALL buses"""
    dexter_observations = []
    
    async def dexter_observer(msg):
        dexter_observations.append(msg)
    
    # Dexter subscribes to MAIN (selected topics)
    triple_bus.main.subscribe(MainTopic.USER_INPUT, dexter_observer)
    triple_bus.main.subscribe(MainTopic.INTENT, dexter_observer)
    triple_bus.main.subscribe(MainTopic.ERROR, dexter_observer)
    
    # Dexter subscribes to COLLAB (to monitor and intervene)
    for topic in CollabTopic:
        triple_bus.collab.subscribe(topic, dexter_observer)
    
    # Dexter subscribes to PRIVATE buses (to support agents)
    private_bus1 = await triple_bus.get_private("agent1")
    private_bus2 = await triple_bus.get_private("agent2")
    for topic in PrivateTopic:
        private_bus1.subscribe(topic, dexter_observer)
        private_bus2.subscribe(topic, dexter_observer)
    
    # Publish to various buses
    await triple_bus.main.publish(MainTopic.USER_INPUT, {"content": "main"})
    await triple_bus.collab.publish(CollabTopic.PROPOSAL, {"content": "collab"})
    await private_bus1.publish(PrivateTopic.HELP_REQUEST, {"content": "private1"})
    await private_bus2.publish(PrivateTopic.PROGRESS, {"content": "private2"})
    
    await asyncio.sleep(0.1)
    
    # Dexter observed all messages
    assert len(dexter_observations) == 4
    buses = [obs["bus"] for obs in dexter_observations]
    assert "main" in buses
    assert "collab" in buses
    assert "private:agent1" in buses
    assert "private:agent2" in buses


@pytest.mark.asyncio
async def test_general_agent_state_transition(triple_bus):
    """Test general agent: idle → on-task → idle"""
    agent_received = []
    
    async def agent_handler(msg):
        agent_received.append(msg)
    
    # IDLE: Agent subscribes to MAIN + COLLAB
    triple_bus.main.subscribe(MainTopic.USER_INPUT, agent_handler)
    triple_bus.main.subscribe(MainTopic.DEXTER_RESPONSE, agent_handler)
    for topic in CollabTopic:
        triple_bus.collab.subscribe(topic, agent_handler)
    
    # Activity during idle
    await triple_bus.main.publish(MainTopic.USER_INPUT, {"content": "idle1"})
    await triple_bus.collab.publish(CollabTopic.PROPOSAL, {"content": "idle2"})
    await asyncio.sleep(0.1)
    
    idle_count = len(agent_received)
    assert idle_count == 2
    
    # ON TASK: Unsubscribe from MAIN + COLLAB
    triple_bus.main.unsubscribe_all(agent_handler)
    triple_bus.collab.unsubscribe_all(agent_handler)
    
    # Subscribe to PRIVATE only
    private_bus = await triple_bus.get_private("test_agent")
    for topic in PrivateTopic:
        private_bus.subscribe(topic, agent_handler)
    
    # Activity during on-task (shouldn't receive MAIN/COLLAB)
    await triple_bus.main.publish(MainTopic.USER_INPUT, {"content": "task1"})
    await triple_bus.collab.publish(CollabTopic.PROPOSAL, {"content": "task2"})
    await private_bus.publish(PrivateTopic.TASK_ASSIGNMENT, {"content": "task3"})
    await asyncio.sleep(0.1)
    
    # Only received PRIVATE message
    assert len(agent_received) == idle_count + 1
    assert agent_received[-1]["content"] == "task3"
    
    # BACK TO IDLE: Unsubscribe from PRIVATE
    private_bus.unsubscribe_all(agent_handler)
    
    # Re-subscribe to MAIN + COLLAB
    triple_bus.main.subscribe(MainTopic.USER_INPUT, agent_handler)
    for topic in CollabTopic:
        triple_bus.collab.subscribe(topic, agent_handler)
    
    await triple_bus.main.publish(MainTopic.USER_INPUT, {"content": "idle3"})
    await asyncio.sleep(0.1)
    
    # Received MAIN message again
    assert len(agent_received) == idle_count + 2
    assert agent_received[-1]["content"] == "idle3"


@pytest.mark.asyncio
async def test_error_handling_in_subscriber(triple_bus):
    """Test error handling when subscriber raises exception"""
    received = []
    
    async def good_handler(msg):
        received.append(("good", msg))
    
    async def bad_handler(msg):
        raise ValueError("Intentional test error")
    
    # Subscribe both handlers
    triple_bus.main.subscribe(MainTopic.INTENT, good_handler)
    triple_bus.main.subscribe(MainTopic.INTENT, bad_handler)
    
    # Publish message
    await triple_bus.main.publish(MainTopic.INTENT, {"content": "test"})
    await asyncio.sleep(0.1)
    
    # Good handler still received message despite bad handler error
    assert len(received) == 1
    assert received[0][0] == "good"


@pytest.mark.asyncio
async def test_lazy_private_bus_creation(triple_bus):
    """Test PRIVATE buses created on-demand"""
    stats = triple_bus.get_stats()
    assert stats["private"]["bus_count"] == 0
    
    # Create first private bus
    bus1 = await triple_bus.get_private("agent1")
    assert bus1.bus_id == "private:agent1"
    stats = triple_bus.get_stats()
    assert stats["private"]["bus_count"] == 1
    assert "agent1" in stats["private"]["agent_ids"]
    
    # Get same bus again (not created twice)
    bus1_again = await triple_bus.get_private("agent1")
    assert bus1 is bus1_again
    stats = triple_bus.get_stats()
    assert stats["private"]["bus_count"] == 1
    
    # Create second private bus
    bus2 = await triple_bus.get_private("agent2")
    stats = triple_bus.get_stats()
    assert stats["private"]["bus_count"] == 2
    assert "agent2" in stats["private"]["agent_ids"]


@pytest.mark.asyncio
async def test_destroy_private_bus(triple_bus):
    """Test destroying PRIVATE bus when agent completes task"""
    # Create private bus
    private_bus = await triple_bus.get_private("agent1")
    stats = triple_bus.get_stats()
    assert stats["private"]["bus_count"] == 1
    
    # Destroy it
    await triple_bus.destroy_private("agent1")
    stats = triple_bus.get_stats()
    assert stats["private"]["bus_count"] == 0
    assert "agent1" not in stats["private"]["agent_ids"]
    
    # Destroying non-existent bus is safe
    await triple_bus.destroy_private("non_existent")
    stats = triple_bus.get_stats()
    assert stats["private"]["bus_count"] == 0


@pytest.mark.asyncio
async def test_metadata_injection(triple_bus):
    """Test auto-injection of id, ts, bus, topic"""
    received = []
    
    async def handler(msg):
        received.append(msg)
    
    triple_bus.main.subscribe(MainTopic.USER_INPUT, handler)
    
    # Publish without metadata
    await triple_bus.main.publish(MainTopic.USER_INPUT, {"content": "test"})
    await asyncio.sleep(0.1)
    
    msg = received[0]
    assert "id" in msg
    assert "ts" in msg
    assert msg["bus"] == "main"
    assert msg["topic"] == "user_input"
    assert msg["content"] == "test"


@pytest.mark.asyncio
async def test_global_triple_bus():
    """Test global singleton pattern"""
    bus1 = get_global_triple_bus()
    bus2 = get_global_triple_bus()
    assert bus1 is bus2
    
    # Reset
    reset_global_triple_bus()
    bus3 = get_global_triple_bus()
    assert bus3 is not bus1


@pytest.mark.asyncio
async def test_subscriber_count(triple_bus):
    """Test getting subscriber count for topics"""
    async def handler1(msg):
        pass
    
    async def handler2(msg):
        pass
    
    # Initially no subscribers
    assert triple_bus.main.get_subscriber_count(MainTopic.USER_INPUT) == 0
    
    # Add subscribers
    triple_bus.main.subscribe(MainTopic.USER_INPUT, handler1)
    assert triple_bus.main.get_subscriber_count(MainTopic.USER_INPUT) == 1
    
    triple_bus.main.subscribe(MainTopic.USER_INPUT, handler2)
    assert triple_bus.main.get_subscriber_count(MainTopic.USER_INPUT) == 2
    
    # Unsubscribe
    triple_bus.main.unsubscribe(MainTopic.USER_INPUT, handler1)
    assert triple_bus.main.get_subscriber_count(MainTopic.USER_INPUT) == 1


@pytest.mark.asyncio
async def test_complete_workflow(triple_bus):
    """
    Test complete workflow:
    1. User speaks to Dexter (MAIN)
    2. Idle agents collaborate (COLLAB)
    3. Dexter assigns task to agent (PRIVATE)
    4. Agent executes with BSM context (PRIVATE)
    5. Agent completes, returns to idle
    """
    workflow_events = []
    
    async def event_logger(msg):
        workflow_events.append({
            "bus": msg["bus"],
            "topic": msg["topic"],
            "content": msg.get("content", msg.get("from", ""))
        })
    
    # BSM observes everything
    for topic in MainTopic:
        triple_bus.main.subscribe(topic, event_logger)
    for topic in CollabTopic:
        triple_bus.collab.subscribe(topic, event_logger)
    
    # 1. User speaks to Dexter
    await triple_bus.main.publish(MainTopic.USER_INPUT, {
        "content": "Please analyze this spreadsheet"
    })
    
    # 2. Dexter broadcasts to COLLAB for collaboration
    await triple_bus.collab.publish(CollabTopic.OBSERVATION, {
        "from": "dexter",
        "content": "User needs spreadsheet analysis"
    })
    
    # 3. Idle agents propose
    await triple_bus.collab.publish(CollabTopic.PROPOSAL, {
        "from": "data_analyst",
        "content": "I can parse Excel files"
    })
    
    await triple_bus.collab.publish(CollabTopic.REFINEMENT, {
        "from": "coder",
        "content": "I'll add pandas for data manipulation"
    })
    
    # 4. Dexter assigns task
    private_bus = await triple_bus.get_private("data_analyst")
    private_bus.subscribe(PrivateTopic.TASK_ASSIGNMENT, event_logger)
    private_bus.subscribe(PrivateTopic.CONTEXT_UPDATE, event_logger)
    private_bus.subscribe(PrivateTopic.PROGRESS, event_logger)
    
    await private_bus.publish(PrivateTopic.TASK_ASSIGNMENT, {
        "from": "dexter",
        "content": "Analyze spreadsheet.xlsx"
    })
    
    # 5. BSM provides context
    await private_bus.publish(PrivateTopic.CONTEXT_UPDATE, {
        "from": "bsm",
        "content": "Past analysis patterns available"
    })
    
    # 6. Agent reports progress
    await private_bus.publish(PrivateTopic.PROGRESS, {
        "from": "data_analyst",
        "content": "Loaded 1000 rows"
    })
    
    # 7. Agent completes
    await private_bus.publish(PrivateTopic.TASK_COMPLETE, {
        "from": "data_analyst",
        "content": "Analysis complete"
    })
    
    await asyncio.sleep(0.1)
    
    # Verify workflow events (at least 7: user input, observation, 2 collabs, task, context, progress)
    assert len(workflow_events) >= 7
    
    # Check sequence
    buses_in_order = [e["bus"] for e in workflow_events]
    assert "main" in buses_in_order
    assert "collab" in buses_in_order
    assert "private:data_analyst" in buses_in_order

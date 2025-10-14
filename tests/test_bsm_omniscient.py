"""
Test suite for BSM Omniscient Observer functionality.

Tests BSM's ability to:
1. Subscribe to ALL buses (MAIN, COLLAB, PRIVATE)
2. Observe everything happening in the system
3. Store all interactions for learning
4. Provide intelligent context proactively
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from dexter_autonomy.agents.bsm import BSM
from dexter_autonomy.brain.memory import BrainDB
from dexter_autonomy.core.triple_bus import (
    TripleBusSystem,
    MainTopic,
    CollabTopic,
    PrivateTopic,
)


@pytest.fixture
def mock_brain():
    """Mock BrainDB"""
    brain = MagicMock(spec=BrainDB)
    brain.add_memory = MagicMock(return_value=1)
    brain.search = MagicMock(return_value=[
        {
            "id": 1,
            "kind": "observation",
            "content": "Past similar interaction",
            "meta": {"tags": ["test"]},
            "ts": 1234567890.0,
        }
    ])
    return brain


@pytest_asyncio.fixture
async def buses():
    """Create triple bus system"""
    buses = TripleBusSystem()
    await buses.start_all()
    yield buses
    await buses.stop_all()


@pytest_asyncio.fixture
async def bsm_no_llm(buses, mock_brain):
    """BSM without LLM (for fast testing)"""
    bsm = BSM(
        buses=buses,
        brain=mock_brain,
        model=None,  # No LLM
        host="http://127.0.0.1:11434",
    )
    await bsm.start()
    yield bsm
    await bsm.stop()


@pytest_asyncio.fixture
async def bsm_with_llm(buses, mock_brain):
    """BSM with mocked LLM"""
    with patch('dexter_autonomy.agents.bsm.OllamaClient') as mock_ollama:
        mock_client = MagicMock()
        mock_client.chat = MagicMock(return_value='{"summary": "test", "tags": ["auto"]}')
        mock_ollama.return_value = mock_client
        
        bsm = BSM(
            buses=buses,
            brain=mock_brain,
            model="qwen2.5:3b-instruct",
            host="http://127.0.0.1:11434",
        )
        await bsm.start()
        yield bsm
        await bsm.stop()


class TestBSMSubscription:
    """Test BSM subscribes to all buses"""
    
    @pytest.mark.asyncio
    async def test_bsm_subscribes_to_main_topics(self, bsm_no_llm, buses):
        """BSM should subscribe to ALL MAIN topics"""
        for topic in MainTopic:
            count = buses.main.get_subscriber_count(topic)
            assert count >= 1, f"BSM not subscribed to MAIN topic: {topic}"
    
    @pytest.mark.asyncio
    async def test_bsm_subscribes_to_collab_topics(self, bsm_no_llm, buses):
        """BSM should subscribe to ALL COLLAB topics"""
        for topic in CollabTopic:
            count = buses.collab.get_subscriber_count(topic)
            assert count >= 1, f"BSM not subscribed to COLLAB topic: {topic}"
    
    @pytest.mark.asyncio
    async def test_bsm_monitors_private_buses(self, bsm_no_llm, buses):
        """BSM should monitor and subscribe to PRIVATE buses"""
        # Create a PRIVATE bus for an agent
        private_bus = await buses.get_private("test_agent")
        
        # Wait for BSM to detect and subscribe (monitoring loop runs every 2s)
        await asyncio.sleep(2.5)
        
        # BSM should have subscribed to all PRIVATE topics
        for topic in PrivateTopic:
            count = private_bus.get_subscriber_count(topic)
            assert count >= 1, f"BSM not subscribed to PRIVATE topic: {topic}"
        
        # Check BSM tracking
        assert "test_agent" in bsm_no_llm._monitored_private_buses


class TestBSMObservation:
    """Test BSM observes all messages"""
    
    @pytest.mark.asyncio
    async def test_observe_main_bus_user_input(self, bsm_no_llm, buses, mock_brain):
        """BSM observes USER_INPUT on MAIN bus"""
        await buses.main.publish(MainTopic.USER_INPUT, {
            "content": "Hello Dexter",
            "from": "user",
        })
        
        # Wait for observation to be processed
        await asyncio.sleep(0.1)
        
        # BSM should have stored observation
        assert bsm_no_llm._observation_count >= 1
        assert mock_brain.add_memory.called
    
    @pytest.mark.asyncio
    async def test_observe_main_bus_dexter_response(self, bsm_no_llm, buses, mock_brain):
        """BSM observes DEXTER_RESPONSE on MAIN bus"""
        await buses.main.publish(MainTopic.DEXTER_RESPONSE, {
            "content": "I can help with that",
            "from": "dexter",
        })
        
        await asyncio.sleep(0.1)
        
        assert bsm_no_llm._observation_count >= 1
        assert mock_brain.add_memory.called
    
    @pytest.mark.asyncio
    async def test_observe_main_bus_intent(self, bsm_no_llm, buses, mock_brain):
        """BSM observes INTENT on MAIN bus"""
        await buses.main.publish(MainTopic.INTENT, {
            "kind": "click",
            "args": {"x": 100, "y": 200},
            "from": "dexter",
            "to": "action_executor",
        })
        
        await asyncio.sleep(0.1)
        
        assert bsm_no_llm._observation_count >= 1
        assert mock_brain.add_memory.called
    
    @pytest.mark.asyncio
    async def test_observe_collab_bus_proposal(self, bsm_no_llm, buses, mock_brain):
        """BSM observes PROPOSAL on COLLAB bus"""
        await buses.collab.publish(CollabTopic.PROPOSAL, {
            "from": "coder",
            "proposal": {"action": "write code", "file": "test.py"},
        })
        
        await asyncio.sleep(0.1)
        
        assert bsm_no_llm._observation_count >= 1
        assert mock_brain.add_memory.called
    
    @pytest.mark.asyncio
    async def test_observe_private_bus_task_assignment(self, bsm_no_llm, buses, mock_brain):
        """BSM observes TASK_ASSIGNMENT on PRIVATE bus"""
        # Create PRIVATE bus
        private_bus = await buses.get_private("web_scraper")
        await asyncio.sleep(2.5)  # Wait for BSM to subscribe
        
        # Publish task assignment
        await private_bus.publish(PrivateTopic.TASK_ASSIGNMENT, {
            "from": "dexter",
            "to": "web_scraper",
            "task": {"description": "Scrape website", "url": "https://example.com"},
        })
        
        await asyncio.sleep(0.1)
        
        # BSM should observe (count will include subscription observation too)
        assert bsm_no_llm._observation_count >= 1
    
    @pytest.mark.asyncio
    async def test_observe_all_message_types(self, bsm_no_llm, buses, mock_brain):
        """BSM observes messages from all three buses"""
        # MAIN bus message
        await buses.main.publish(MainTopic.USER_INPUT, {"content": "test main"})
        
        # COLLAB bus message
        await buses.collab.publish(CollabTopic.PROPOSAL, {"proposal": "test collab"})
        
        # PRIVATE bus message
        private_bus = await buses.get_private("agent1")
        await asyncio.sleep(2.5)  # Wait for BSM to subscribe
        await private_bus.publish(PrivateTopic.PROGRESS, {"progress": 50})
        
        await asyncio.sleep(0.2)
        
        # BSM should have observed at least 3 messages
        assert bsm_no_llm._observation_count >= 3


class TestBSMStorage:
    """Test BSM stores observations correctly"""
    
    @pytest.mark.asyncio
    async def test_storage_includes_metadata(self, bsm_no_llm, buses, mock_brain):
        """BSM stores observations with correct metadata"""
        # Reset mock to clear any previous calls
        mock_brain.add_memory.reset_mock()
        
        await buses.main.publish(MainTopic.USER_INPUT, {
            "content": "Test message",
            "from": "user",
        })
        
        await asyncio.sleep(0.1)
        
        # Check add_memory was called with metadata
        assert mock_brain.add_memory.called
        
        # Find the call that corresponds to USER_INPUT (not CONTEXT_AVAILABLE)
        user_input_call = None
        for call in mock_brain.add_memory.call_args_list:
            meta = call[0][2]  # Third argument is meta dict
            if meta.get("topic") == "user_input":
                user_input_call = call
                break
        
        assert user_input_call is not None, "USER_INPUT observation not found"
        meta = user_input_call[0][2]
        assert meta["bus"] == "main"
        assert meta["topic"] == "user_input"
        assert meta["from"] == "user"
    
    @pytest.mark.asyncio
    async def test_storage_handles_all_buses(self, bsm_no_llm, buses, mock_brain):
        """BSM stores observations from all buses with correct bus metadata"""
        # MAIN
        await buses.main.publish(MainTopic.TRACE, {"message": "trace"})
        await asyncio.sleep(0.05)
        
        # COLLAB
        await buses.collab.publish(CollabTopic.CRITIQUE, {"critique": "test"})
        await asyncio.sleep(0.05)
        
        # PRIVATE
        private_bus = await buses.get_private("agent2")
        await asyncio.sleep(2.5)
        await private_bus.publish(PrivateTopic.HELP_REQUEST, {"request": "help"})
        await asyncio.sleep(0.1)
        
        # Check all were stored
        assert mock_brain.add_memory.call_count >= 3


class TestBSMContextProvisioning:
    """Test BSM provides context proactively"""
    
    @pytest.mark.asyncio
    async def test_context_provided_on_user_input(self, bsm_no_llm, buses, mock_brain):
        """BSM provides CONTEXT_AVAILABLE when user speaks"""
        # Set up mock brain to return relevant memories
        mock_brain.search.return_value = [
            {"id": 1, "content": "Similar past query", "meta": {"tags": ["test"]}, "ts": 123.0}
        ]
        
        # Track CONTEXT_AVAILABLE messages
        context_messages = []
        async def capture_context(msg):
            context_messages.append(msg)
        
        buses.main.subscribe(MainTopic.CONTEXT_AVAILABLE, capture_context)
        
        # User input
        await buses.main.publish(MainTopic.USER_INPUT, {
            "content": "How do I save a file?",
            "from": "user",
        })
        
        await asyncio.sleep(0.2)
        
        # BSM should broadcast context
        assert len(context_messages) >= 1
        assert context_messages[0]["from"] == "bsm"
        assert "context" in context_messages[0]
        assert "memories" in context_messages[0]
    
    @pytest.mark.asyncio
    async def test_context_sent_to_private_bus_on_task(self, bsm_no_llm, buses, mock_brain):
        """BSM sends CONTEXT_UPDATE to PRIVATE bus on task assignment"""
        mock_brain.search.return_value = [
            {"id": 2, "content": "Past similar task", "meta": {}, "ts": 456.0}
        ]
        
        # Create PRIVATE bus and wait for BSM to subscribe
        private_bus = await buses.get_private("coder")
        await asyncio.sleep(2.5)
        
        # Track CONTEXT_UPDATE messages
        context_updates = []
        async def capture_update(msg):
            context_updates.append(msg)
        
        private_bus.subscribe(PrivateTopic.CONTEXT_UPDATE, capture_update)
        
        # Task assignment
        await private_bus.publish(PrivateTopic.TASK_ASSIGNMENT, {
            "from": "dexter",
            "to": "coder",
            "task": {"description": "Write Python function"},
        })
        
        await asyncio.sleep(0.2)
        
        # BSM should send context update
        assert len(context_updates) >= 1
        assert context_updates[0]["from"] == "bsm"
        assert "context" in context_updates[0]
    
    @pytest.mark.asyncio
    async def test_context_on_help_request(self, bsm_no_llm, buses, mock_brain):
        """BSM provides context when agent requests help"""
        mock_brain.search.return_value = [
            {"id": 3, "content": "Solution pattern", "meta": {}, "ts": 789.0}
        ]
        
        private_bus = await buses.get_private("writer")
        await asyncio.sleep(2.5)
        
        context_updates = []
        async def capture_update(msg):
            context_updates.append(msg)
        
        private_bus.subscribe(PrivateTopic.CONTEXT_UPDATE, capture_update)
        
        # Help request
        await private_bus.publish(PrivateTopic.HELP_REQUEST, {
            "from": "writer",
            "request": "How to format markdown?",
        })
        
        await asyncio.sleep(0.2)
        
        assert len(context_updates) >= 1
        assert context_updates[0]["trigger"] == "help_request"
    
    @pytest.mark.asyncio
    async def test_context_on_collaboration_proposal(self, bsm_no_llm, buses, mock_brain):
        """BSM provides context when agents propose solutions"""
        mock_brain.search.return_value = [
            {"id": 4, "content": "Past proposal outcome", "meta": {}, "ts": 999.0}
        ]
        
        context_messages = []
        async def capture_context(msg):
            context_messages.append(msg)
        
        buses.main.subscribe(MainTopic.CONTEXT_AVAILABLE, capture_context)
        
        # Agent proposes solution
        await buses.collab.publish(CollabTopic.PROPOSAL, {
            "from": "coder",
            "proposal": {"solution": "Refactor the code", "approach": "OOP"},
        })
        
        await asyncio.sleep(0.2)
        
        assert len(context_messages) >= 1
        assert context_messages[0]["trigger"] == "collaboration_proposal"
    
    @pytest.mark.asyncio
    async def test_no_context_when_no_relevant_memories(self, bsm_no_llm, buses, mock_brain):
        """BSM doesn't provide context when no relevant memories found"""
        # Mock brain returns empty search results
        mock_brain.search.return_value = []
        
        context_messages = []
        async def capture_context(msg):
            context_messages.append(msg)
        
        buses.main.subscribe(MainTopic.CONTEXT_AVAILABLE, capture_context)
        
        # User input
        await buses.main.publish(MainTopic.USER_INPUT, {
            "content": "Random unrelated query xyz123",
            "from": "user",
        })
        
        await asyncio.sleep(0.2)
        
        # No context should be provided (no relevant memories)
        assert len(context_messages) == 0


class TestBSMNeverExecutes:
    """Test BSM NEVER executes actions, only observes"""
    
    @pytest.mark.asyncio
    async def test_bsm_never_publishes_intent(self, bsm_no_llm, buses):
        """BSM should NEVER publish INTENT (commands)"""
        intent_messages = []
        async def capture_intent(msg):
            intent_messages.append(msg)
        
        buses.main.subscribe(MainTopic.INTENT, capture_intent)
        
        # Trigger various observations
        await buses.main.publish(MainTopic.USER_INPUT, {"content": "Click button"})
        await buses.collab.publish(CollabTopic.PROPOSAL, {"proposal": "Execute action"})
        
        await asyncio.sleep(0.3)
        
        # BSM should NEVER have published INTENT
        bsm_intents = [msg for msg in intent_messages if msg.get("from") == "bsm"]
        assert len(bsm_intents) == 0, "BSM published INTENT - BSM must NEVER execute!"
    
    @pytest.mark.asyncio
    async def test_bsm_only_publishes_context(self, bsm_no_llm, buses, mock_brain):
        """BSM should only publish CONTEXT_AVAILABLE and CONTEXT_UPDATE"""
        mock_brain.search.return_value = [{"id": 1, "content": "test", "meta": {}, "ts": 1.0}]
        
        all_main_messages = []
        async def capture_all(msg):
            all_main_messages.append(msg)
        
        for topic in MainTopic:
            buses.main.subscribe(topic, capture_all)
        
        # Trigger context provisioning
        await buses.main.publish(MainTopic.USER_INPUT, {"content": "test"})
        await asyncio.sleep(0.2)
        
        # Check BSM only published CONTEXT_AVAILABLE
        bsm_messages = [msg for msg in all_main_messages if msg.get("from") == "bsm"]
        for msg in bsm_messages:
            assert msg["topic"] == "context_available", f"BSM published {msg['topic']} - should only publish context!"


class TestBSMStatistics:
    """Test BSM tracking and statistics"""
    
    @pytest.mark.asyncio
    async def test_observation_count_tracked(self, bsm_no_llm, buses):
        """BSM tracks number of observations"""
        initial_count = bsm_no_llm._observation_count
        
        await buses.main.publish(MainTopic.USER_INPUT, {"content": "msg1"})
        await buses.main.publish(MainTopic.DEXTER_RESPONSE, {"content": "msg2"})
        await buses.collab.publish(CollabTopic.PROPOSAL, {"proposal": "msg3"})
        
        await asyncio.sleep(0.2)
        
        assert bsm_no_llm._observation_count >= initial_count + 3
    
    @pytest.mark.asyncio
    async def test_context_provided_count_tracked(self, bsm_no_llm, buses, mock_brain):
        """BSM tracks number of context provisions"""
        mock_brain.search.return_value = [{"id": 1, "content": "test", "meta": {}, "ts": 1.0}]
        
        initial_count = bsm_no_llm._context_provided_count
        
        # Trigger context provisioning
        await buses.main.publish(MainTopic.USER_INPUT, {"content": "query1"})
        await asyncio.sleep(0.1)
        await buses.main.publish(MainTopic.USER_INPUT, {"content": "query2"})
        await asyncio.sleep(0.1)
        
        assert bsm_no_llm._context_provided_count >= initial_count + 2
    
    @pytest.mark.asyncio
    async def test_get_stats(self, bsm_no_llm, buses, mock_brain):
        """BSM get_stats() returns correct information"""
        mock_brain.search.return_value = [{"id": 1, "content": "test", "meta": {}, "ts": 1.0}]
        
        # Generate some activity
        await buses.main.publish(MainTopic.USER_INPUT, {"content": "test"})
        private_bus = await buses.get_private("agent_x")
        await asyncio.sleep(2.6)
        
        stats = bsm_no_llm.get_stats()
        
        assert stats["started"] is True
        assert stats["observations"] >= 1
        assert stats["context_provided"] >= 1
        assert stats["monitored_private_buses"] >= 1
        assert "agent_x" in stats["private_bus_ids"]


class TestBSMWithLLM:
    """Test BSM with LLM for enhanced context determination"""
    
    @pytest.mark.asyncio
    async def test_llm_used_for_observation_summarization(self, bsm_with_llm, buses, mock_brain):
        """BSM uses LLM to summarize observations"""
        await buses.main.publish(MainTopic.USER_INPUT, {
            "content": "Long detailed message that should be summarized by LLM",
        })
        
        await asyncio.sleep(0.1)
        
        # ingest() should have been called, which uses LLM when available
        assert mock_brain.add_memory.called
    
    @pytest.mark.asyncio
    async def test_llm_used_for_context_determination(self, bsm_with_llm, buses, mock_brain):
        """BSM uses LLM to determine what context is helpful"""
        # Mock the LLM response for context determination
        with patch.object(bsm_with_llm, '_determine_needed_context', return_value="Helpful context"):
            mock_brain.search.return_value = [
                {"id": 1, "content": "Past interaction", "meta": {"tags": ["helpful"]}, "ts": 123.0}
            ]
            
            context_messages = []
            async def capture_context(msg):
                context_messages.append(msg)
            
            buses.main.subscribe(MainTopic.CONTEXT_AVAILABLE, capture_context)
            
            await buses.main.publish(MainTopic.USER_INPUT, {
                "content": "Complex query requiring LLM analysis",
            })
            
            await asyncio.sleep(0.2)
            
            # BSM should provide context (LLM helps determine relevance)
            assert len(context_messages) >= 1


class TestBSMStartStop:
    """Test BSM start/stop lifecycle"""
    
    @pytest.mark.asyncio
    async def test_bsm_can_be_started_and_stopped(self, buses, mock_brain):
        """BSM can be started and stopped cleanly"""
        bsm = BSM(buses=buses, brain=mock_brain, model=None)
        
        # Start
        await bsm.start()
        assert bsm._started is True
        
        # Stop
        await bsm.stop()
        assert bsm._started is False
    
    @pytest.mark.asyncio
    async def test_bsm_idempotent_start(self, buses, mock_brain):
        """BSM start() is idempotent"""
        bsm = BSM(buses=buses, brain=mock_brain, model=None)
        
        await bsm.start()
        await bsm.start()  # Should not crash
        await bsm.start()  # Should not crash
        
        assert bsm._started is True
        
        await bsm.stop()
    
    @pytest.mark.asyncio
    async def test_bsm_stops_observing_after_stop(self, buses, mock_brain):
        """BSM stops observing after stop()"""
        bsm = BSM(buses=buses, brain=mock_brain, model=None)
        await bsm.start()
        
        # Observe something
        await buses.main.publish(MainTopic.USER_INPUT, {"content": "before stop"})
        await asyncio.sleep(0.1)
        count_before = bsm._observation_count
        
        # Stop BSM
        await bsm.stop()
        
        # Publish more messages
        await buses.main.publish(MainTopic.USER_INPUT, {"content": "after stop"})
        await asyncio.sleep(0.1)
        
        # Observation count should not increase
        assert bsm._observation_count == count_before

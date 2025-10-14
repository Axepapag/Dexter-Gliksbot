"""
Test suite for GeneralAgent Base Class

Tests GeneralAgent's ability to:
1. Manage state machine (idle ↔ on_task)
2. Auto-switch bus subscriptions based on state
3. Collaborate when idle
4. Focus on task when assigned
5. Validate tasks with policy
6. Receive context from BSM
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from dexter_autonomy.agents.general_agent import AgentState, GeneralAgent
from dexter_autonomy.core.policy_overlay import CompositeDenyPolicy
from dexter_autonomy.core.triple_bus import (
    CollabTopic,
    MainTopic,
    PrivateTopic,
    TripleBusSystem,
)


class TestAgent(GeneralAgent):
    """Concrete test agent for testing GeneralAgent base class"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executed_tasks = []
        self.proposals_generated = []
        self.refinements_generated = []
        self.critiques_generated = []
        self.votes_generated = []
    
    async def _execute_task_impl(self, task):
        """Test implementation - just records task, simulates failure for 'Will fail' tasks"""
        self.executed_tasks.append(task)
        
        # Simulate failure for testing error handling
        if "Will fail" in task.get("description", ""):
            raise RuntimeError("Simulated task failure")
        
        return {"status": "success", "output": f"Executed: {task.get('description')}"}
    
    async def generate_proposal(self, observation):
        proposal = {"solution": "Test solution", "confidence": 0.9}
        self.proposals_generated.append(proposal)
        return proposal
    
    async def refine_proposal(self, proposal):
        refinement = {"refined_solution": "Improved solution"}
        self.refinements_generated.append(refinement)
        return refinement
    
    async def critique_proposal(self, proposal):
        critique = {"issues": ["Minor issue"], "severity": "minor"}
        self.critiques_generated.append(critique)
        return critique
    
    async def vote(self, proposals):
        vote = proposals[0]["id"] if proposals else ""
        self.votes_generated.append(vote)
        return vote


@pytest.fixture
def mock_policy():
    """Mock policy that allows everything"""
    policy = MagicMock(spec=CompositeDenyPolicy)
    return policy


@pytest_asyncio.fixture
async def buses():
    """Create triple bus system"""
    buses = TripleBusSystem()
    await buses.start_all()
    yield buses
    await buses.stop_all()


@pytest_asyncio.fixture
async def test_agent(buses, mock_policy):
    """Create test agent"""
    agent = TestAgent(
        agent_id="test_agent_1",
        agent_type="test",
        buses=buses,
        policy=mock_policy,
        system_prompt="You are a test agent",
        capabilities=["test_capability_1", "test_capability_2"],
    )
    await agent.start()
    yield agent
    await agent.stop()


class TestAgentStateMachine:
    """Test state machine transitions"""
    
    @pytest.mark.asyncio
    async def test_agent_starts_in_idle_state(self, test_agent):
        """Agent should start in IDLE state"""
        assert test_agent.state == AgentState.IDLE
    
    @pytest.mark.asyncio
    async def test_idle_to_on_task_transition(self, test_agent, buses):
        """Agent transitions from IDLE to ON_TASK when assigned task"""
        # Get private bus and assign task
        private_bus = await buses.get_private("test_agent_1")
        await private_bus.publish(PrivateTopic.TASK_ASSIGNMENT, {
            "from": "dexter",
            "to": "test_agent_1",
            "task": {"id": "task1", "description": "Test task"},
        })
        
        # Wait for task to be processed
        await asyncio.sleep(0.2)
        
        # Agent should be ON_TASK (or back to IDLE if task completed quickly)
        # Since our test agent completes immediately, it should be IDLE again
        assert test_agent.state == AgentState.IDLE
        assert len(test_agent.executed_tasks) == 1
    
    @pytest.mark.asyncio
    async def test_on_task_to_idle_transition_after_completion(self, test_agent, buses):
        """Agent returns to IDLE after completing task"""
        private_bus = await buses.get_private("test_agent_1")
        
        # Assign task
        await private_bus.publish(PrivateTopic.TASK_ASSIGNMENT, {
            "task": {"id": "task1", "description": "Quick task"},
        })
        
        await asyncio.sleep(0.2)
        
        # Should be back to IDLE
        assert test_agent.state == AgentState.IDLE
        assert test_agent._current_task is None


class TestBusSubscriptionManagement:
    """Test bus subscription management based on state"""
    
    @pytest.mark.asyncio
    async def test_idle_agent_subscribes_to_main_bus(self, test_agent, buses):
        """Idle agent should subscribe to MAIN bus topics"""
        # Check MAIN bus subscriptions
        assert buses.main.get_subscriber_count(MainTopic.USER_INPUT) >= 1
        assert buses.main.get_subscriber_count(MainTopic.DEXTER_RESPONSE) >= 1
        assert buses.main.get_subscriber_count(MainTopic.CONTEXT_AVAILABLE) >= 1
    
    @pytest.mark.asyncio
    async def test_idle_agent_subscribes_to_collab_bus(self, test_agent, buses):
        """Idle agent should subscribe to COLLAB bus topics"""
        assert buses.collab.get_subscriber_count(CollabTopic.OBSERVATION) >= 1
        assert buses.collab.get_subscriber_count(CollabTopic.PROPOSAL) >= 1
        assert buses.collab.get_subscriber_count(CollabTopic.VOTE_REQUEST) >= 1
    
    @pytest.mark.asyncio
    async def test_on_task_agent_unsubscribes_from_main_collab(self, buses, mock_policy):
        """On-task agent should unsubscribe from MAIN and COLLAB"""
        # Create agent but manually transition to ON_TASK
        agent = TestAgent(
            agent_id="test_agent_2",
            agent_type="test",
            buses=buses,
            policy=mock_policy,
        )
        await agent.start()
        
        # Check initial subscriptions (IDLE)
        main_before = buses.main.get_subscriber_count(MainTopic.USER_INPUT)
        collab_before = buses.collab.get_subscriber_count(CollabTopic.PROPOSAL)
        
        # Transition to ON_TASK
        task = {"id": "long_task", "description": "Long running task"}
        await agent._enter_task_mode(task)
        
        # Check subscriptions reduced
        main_after = buses.main.get_subscriber_count(MainTopic.USER_INPUT)
        collab_after = buses.collab.get_subscriber_count(CollabTopic.PROPOSAL)
        
        assert main_after < main_before
        assert collab_after < collab_before
        
        await agent.stop()
    
    @pytest.mark.asyncio
    async def test_on_task_agent_subscribes_to_private_bus(self, buses, mock_policy):
        """On-task agent should subscribe to PRIVATE bus"""
        agent = TestAgent(
            agent_id="test_agent_3",
            agent_type="test",
            buses=buses,
            policy=mock_policy,
        )
        await agent.start()
        
        # Get private bus
        private_bus = await buses.get_private("test_agent_3")
        
        # Transition to ON_TASK
        task = {"id": "task1", "description": "Test"}
        await agent._enter_task_mode(task)
        
        # Check PRIVATE bus subscriptions
        assert private_bus.get_subscriber_count(PrivateTopic.TASK_ASSIGNMENT) >= 1
        assert private_bus.get_subscriber_count(PrivateTopic.CONTEXT_UPDATE) >= 1
        assert private_bus.get_subscriber_count(PrivateTopic.DEXTER_SUPPORT) >= 1
        
        await agent.stop()


class TestIdleCollaboration:
    """Test idle agent collaboration on COLLAB bus"""
    
    @pytest.mark.asyncio
    async def test_idle_agent_receives_user_input(self, test_agent, buses):
        """Idle agent should receive USER_INPUT"""
        user_input_received = []
        
        async def track_user_input(msg):
            user_input_received.append(msg)
        
        # Override handler to track
        test_agent._on_user_input = track_user_input
        buses.main.subscribe(MainTopic.USER_INPUT, test_agent._on_user_input)
        
        await buses.main.publish(MainTopic.USER_INPUT, {
            "content": "Test user input",
            "from": "user",
        })
        
        await asyncio.sleep(0.1)
        
        assert len(user_input_received) >= 1
    
    @pytest.mark.asyncio
    async def test_idle_agent_receives_context_from_bsm(self, test_agent, buses):
        """Idle agent should receive CONTEXT_AVAILABLE from BSM"""
        await buses.main.publish(MainTopic.CONTEXT_AVAILABLE, {
            "from": "bsm",
            "context": "Relevant context here",
            "memories": [{"id": 1, "content": "Past memory"}],
        })
        
        await asyncio.sleep(0.1)
        
        # Agent should have stored context
        assert test_agent._latest_context is not None
        assert test_agent._latest_context["from"] == "bsm"
    
    @pytest.mark.asyncio
    async def test_idle_agent_can_observe_collab_messages(self, test_agent, buses):
        """Idle agent should observe COLLAB bus messages"""
        proposals_seen = []
        
        async def track_proposals(msg):
            if test_agent.state == AgentState.IDLE:
                proposals_seen.append(msg)
        
        test_agent._on_proposal = track_proposals
        buses.collab.subscribe(CollabTopic.PROPOSAL, test_agent._on_proposal)
        
        await buses.collab.publish(CollabTopic.PROPOSAL, {
            "from": "other_agent",
            "proposal": {"solution": "Other agent's solution"},
        })
        
        await asyncio.sleep(0.1)
        
        assert len(proposals_seen) >= 1


class TestOnTaskExecution:
    """Test on-task agent behavior"""
    
    @pytest.mark.asyncio
    async def test_agent_executes_assigned_task(self, test_agent, buses):
        """Agent should execute task when assigned"""
        private_bus = await buses.get_private("test_agent_1")
        
        await private_bus.publish(PrivateTopic.TASK_ASSIGNMENT, {
            "task": {"id": "task1", "description": "Write code"},
        })
        
        await asyncio.sleep(0.2)
        
        assert len(test_agent.executed_tasks) == 1
        assert test_agent.executed_tasks[0]["description"] == "Write code"
    
    @pytest.mark.asyncio
    async def test_agent_reports_task_completion(self, test_agent, buses):
        """Agent should report TASK_COMPLETE after execution"""
        completions = []
        
        async def track_completions(msg):
            completions.append(msg)
        
        private_bus = await buses.get_private("test_agent_1")
        private_bus.subscribe(PrivateTopic.TASK_COMPLETE, track_completions)
        
        await private_bus.publish(PrivateTopic.TASK_ASSIGNMENT, {
            "task": {"id": "task1", "description": "Test task"},
        })
        
        await asyncio.sleep(0.2)
        
        assert len(completions) >= 1
        assert completions[0]["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_on_task_agent_receives_context_from_bsm(self, buses, mock_policy):
        """On-task agent should receive CONTEXT_UPDATE from BSM on PRIVATE bus"""
        agent = TestAgent(
            agent_id="test_agent_4",
            agent_type="test",
            buses=buses,
            policy=mock_policy,
        )
        await agent.start()
        
        # Assign task
        private_bus = await buses.get_private("test_agent_4")
        task = {"id": "task1", "description": "Test"}
        await agent._enter_task_mode(task)
        
        # BSM sends context
        await private_bus.publish(PrivateTopic.CONTEXT_UPDATE, {
            "from": "bsm",
            "context": "Task-specific context",
            "memories": [{"id": 2, "content": "Relevant memory"}],
        })
        
        await asyncio.sleep(0.1)
        
        # Agent should have received context
        assert agent._latest_context is not None
        assert agent._latest_context["from"] == "bsm"
        
        await agent.stop()
    
    @pytest.mark.asyncio
    async def test_agent_can_request_help_from_dexter(self, buses, mock_policy):
        """Agent should be able to request help via PRIVATE bus"""
        agent = TestAgent(
            agent_id="test_agent_5",
            agent_type="test",
            buses=buses,
            policy=mock_policy,
        )
        await agent.start()
        
        help_requests = []
        
        async def track_help(msg):
            help_requests.append(msg)
        
        private_bus = await buses.get_private("test_agent_5")
        private_bus.subscribe(PrivateTopic.HELP_REQUEST, track_help)
        
        # Enter task mode
        task = {"id": "task1", "description": "Difficult task"}
        await agent._enter_task_mode(task)
        
        # Request help
        await agent.request_help_from_dexter("Need help with difficult part")
        
        await asyncio.sleep(0.1)
        
        assert len(help_requests) >= 1
        assert "difficult part" in help_requests[0]["request"]
        
        await agent.stop()
    
    @pytest.mark.asyncio
    async def test_agent_can_report_progress(self, buses, mock_policy):
        """Agent should report progress during task execution"""
        agent = TestAgent(
            agent_id="test_agent_6",
            agent_type="test",
            buses=buses,
            policy=mock_policy,
        )
        await agent.start()
        
        progress_reports = []
        
        async def track_progress(msg):
            progress_reports.append(msg)
        
        private_bus = await buses.get_private("test_agent_6")
        private_bus.subscribe(PrivateTopic.PROGRESS, track_progress)
        
        # Enter task mode
        task = {"id": "task1", "description": "Long task"}
        await agent._enter_task_mode(task)
        
        # Report progress
        await agent.report_progress(50, "Halfway done")
        await agent.report_progress(100, "Complete")
        
        await asyncio.sleep(0.1)
        
        assert len(progress_reports) >= 2
        assert progress_reports[0]["progress"] == 50
        assert progress_reports[1]["progress"] == 100
        
        await agent.stop()


class TestPolicyValidation:
    """Test task policy validation"""
    
    @pytest.mark.asyncio
    async def test_agent_validates_task_structure(self, buses, mock_policy):
        """Agent should validate task has required structure"""
        agent = TestAgent(
            agent_id="test_agent_7",
            agent_type="test",
            buses=buses,
            policy=mock_policy,
        )
        await agent.start()
        
        # Invalid task (no description)
        result = await agent.execute_task({"id": "task1"})
        
        assert result["status"] == "denied"
        assert "description" in result["reason"]
        
        await agent.stop()
    
    @pytest.mark.asyncio
    async def test_agent_executes_valid_task(self, test_agent):
        """Agent should execute valid task"""
        task = {"id": "task1", "description": "Valid task"}
        result = await test_agent.execute_task(task)
        
        assert result["status"] == "success"
        assert len(test_agent.executed_tasks) == 1


class TestCollaborationMethods:
    """Test collaboration method implementations"""
    
    @pytest.mark.asyncio
    async def test_generate_proposal(self, test_agent):
        """Agent can generate proposals"""
        observation = {"user_request": "Build feature X"}
        proposal = await test_agent.generate_proposal(observation)
        
        assert "solution" in proposal
        assert len(test_agent.proposals_generated) == 1
    
    @pytest.mark.asyncio
    async def test_refine_proposal(self, test_agent):
        """Agent can refine proposals"""
        original_proposal = {"id": "prop1", "solution": "Original"}
        refinement = await test_agent.refine_proposal(original_proposal)
        
        assert "refined_solution" in refinement
        assert len(test_agent.refinements_generated) == 1
    
    @pytest.mark.asyncio
    async def test_critique_proposal(self, test_agent):
        """Agent can critique proposals"""
        proposal = {"id": "prop1", "solution": "Flawed solution"}
        critique = await test_agent.critique_proposal(proposal)
        
        assert "issues" in critique
        assert len(test_agent.critiques_generated) == 1
    
    @pytest.mark.asyncio
    async def test_vote_on_proposals(self, test_agent):
        """Agent can vote on proposals"""
        proposals = [
            {"id": "prop1", "solution": "Solution A"},
            {"id": "prop2", "solution": "Solution B"},
        ]
        vote = await test_agent.vote(proposals)
        
        assert vote in ["prop1", "prop2"]
        assert len(test_agent.votes_generated) == 1


class TestStatistics:
    """Test agent statistics tracking"""
    
    @pytest.mark.asyncio
    async def test_get_stats(self, test_agent):
        """get_stats() returns correct information"""
        stats = test_agent.get_stats()
        
        assert stats["agent_id"] == "test_agent_1"
        assert stats["agent_type"] == "test"
        assert stats["state"] == "idle"
        assert "tasks_completed" in stats
        assert "capabilities" in stats
        assert "test_capability_1" in stats["capabilities"]
    
    @pytest.mark.asyncio
    async def test_stats_track_task_completion(self, test_agent, buses):
        """Stats should track completed tasks"""
        initial_count = test_agent._tasks_completed
        
        private_bus = await buses.get_private("test_agent_1")
        await private_bus.publish(PrivateTopic.TASK_ASSIGNMENT, {
            "task": {"id": "task1", "description": "Test"},
        })
        
        await asyncio.sleep(0.2)
        
        assert test_agent._tasks_completed == initial_count + 1


class TestAgentLifecycle:
    """Test agent start/stop lifecycle"""
    
    @pytest.mark.asyncio
    async def test_agent_can_start_and_stop(self, buses, mock_policy):
        """Agent can start and stop cleanly"""
        agent = TestAgent(
            agent_id="test_agent_8",
            agent_type="test",
            buses=buses,
            policy=mock_policy,
        )
        
        # Start
        await agent.start()
        assert agent._started is True
        assert agent.state == AgentState.IDLE
        
        # Stop
        await agent.stop()
        assert agent._started is False
    
    @pytest.mark.asyncio
    async def test_idempotent_start(self, buses, mock_policy):
        """Agent start() is idempotent"""
        agent = TestAgent(
            agent_id="test_agent_9",
            agent_type="test",
            buses=buses,
            policy=mock_policy,
        )
        
        await agent.start()
        await agent.start()  # Should not crash
        await agent.start()  # Should not crash
        
        assert agent._started is True
        
        await agent.stop()
    
    @pytest.mark.asyncio
    async def test_stop_cleans_up_subscriptions(self, buses, mock_policy):
        """Stop should clean up all subscriptions"""
        agent = TestAgent(
            agent_id="test_agent_10",
            agent_type="test",
            buses=buses,
            policy=mock_policy,
        )
        
        await agent.start()
        
        # Check subscriptions exist
        main_count_before = buses.main.get_subscriber_count(MainTopic.USER_INPUT)
        
        await agent.stop()
        
        # Check subscriptions removed
        main_count_after = buses.main.get_subscriber_count(MainTopic.USER_INPUT)
        assert main_count_after < main_count_before


class TestErrorHandling:
    """Test error handling in task execution"""
    
    @pytest.mark.asyncio
    async def test_agent_reports_failed_task(self, buses, mock_policy):
        """Agent should report failure when task execution fails"""
        
        class FailingAgent(GeneralAgent):
            async def _execute_task_impl(self, task):
                raise ValueError("Simulated failure")
        
        agent = FailingAgent(
            agent_id="failing_agent",
            agent_type="test",
            buses=buses,
            policy=mock_policy,
        )
        await agent.start()
        
        completions = []
        
        async def track_completions(msg):
            completions.append(msg)
        
        private_bus = await buses.get_private("failing_agent")
        private_bus.subscribe(PrivateTopic.TASK_COMPLETE, track_completions)
        
        await private_bus.publish(PrivateTopic.TASK_ASSIGNMENT, {
            "task": {"id": "task1", "description": "Will fail"},
        })
        
        await asyncio.sleep(0.2)
        
        assert len(completions) >= 1
        assert completions[0]["status"] == "failed"
        assert "error" in completions[0]
        
        await agent.stop()

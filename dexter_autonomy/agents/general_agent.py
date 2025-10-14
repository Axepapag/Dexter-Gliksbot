"""
GeneralAgent Base Class - Foundation for all general agents

GeneralAgent provides:
- State machine: idle ↔ on_task
- Bus subscription management: auto-switch between MAIN+COLLAB (idle) and PRIVATE (on-task)
- Collaboration methods: propose, refine, critique, vote
- Task execution framework with policy validation
- Context awareness: receives BSM's intelligent context provisioning

Architecture:
    IDLE state: Listen to MAIN + COLLAB → Collaborate with other idle agents
    ON_TASK state: Listen to PRIVATE only → Focus on assigned task
    
State transitions:
    idle → on_task: When Dexter assigns task via TASK_ASSIGNMENT
    on_task → idle: When task completes via TASK_COMPLETE
"""
from __future__ import annotations

import asyncio
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from ..core.policy_overlay import CompositeDenyPolicy
from ..core.triple_bus import (
    CollabTopic,
    MainTopic,
    PrivateTopic,
    TripleBusSystem,
)


class AgentState(str, Enum):
    """Agent state machine states"""
    IDLE = "idle"
    ON_TASK = "on_task"


class GeneralAgent:
    """
    Base class for all general agents (Coder, Writer, Scraper, etc.)
    
    Key Features:
    - State machine: Automatically manages bus subscriptions based on state
    - Idle mode: Collaborates on COLLAB bus, monitors MAIN bus
    - On-task mode: Focuses on PRIVATE bus only, ignores collaboration
    - Policy validation: All tasks validated before execution
    - Context awareness: Receives and uses BSM's context provisioning
    
    Subclass Usage:
        class CoderAgent(GeneralAgent):
            async def _execute_task_impl(self, task: Dict[str, Any]) -> Dict[str, Any]:
                # Implement actual task execution
                code = self._generate_code(task)
                return {"status": "success", "code": code}
    """
    
    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        buses: TripleBusSystem,
        policy: CompositeDenyPolicy,
        *,
        system_prompt: str = "",
        capabilities: Optional[List[str]] = None,
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.buses = buses
        self.policy = policy
        self.system_prompt = system_prompt
        self.capabilities = capabilities or []
        
        # State management
        self.state = AgentState.IDLE
        self._current_task: Optional[Dict[str, Any]] = None
        self._private_bus: Optional[Any] = None
        
        # Context from BSM
        self._latest_context: Optional[Dict[str, Any]] = None
        
        # Statistics
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._proposals_made = 0
        self._votes_cast = 0
        self._refinements_made = 0
        self._critiques_made = 0
        
        # Started flag
        self._started = False
    
    async def start(self):
        """Start agent in IDLE state"""
        if self._started:
            return
        
        # Create PRIVATE bus for this agent (so it can receive task assignments)
        self._private_bus = await self.buses.get_private(self.agent_id)
        
        # Subscribe to TASK_ASSIGNMENT on PRIVATE bus (even while idle, to receive assignments)
        self._private_bus.subscribe(PrivateTopic.TASK_ASSIGNMENT, self._on_task_assignment)
        
        await self._enter_idle_mode()
        self._started = True
    
    async def stop(self):
        """Stop agent and clean up subscriptions"""
        if not self._started:
            return
        
        if self.state == AgentState.IDLE:
            await self._exit_idle_mode()
        elif self.state == AgentState.ON_TASK:
            await self._exit_task_mode()
        
        # Unsubscribe from TASK_ASSIGNMENT on PRIVATE bus
        if self._private_bus:
            self._private_bus.unsubscribe(PrivateTopic.TASK_ASSIGNMENT, self._on_task_assignment)
            # Don't destroy PRIVATE bus here if on task - _exit_task_mode() handles it
            if self.state == AgentState.IDLE:
                await self.buses.destroy_private(self.agent_id)
                self._private_bus = None
        
        self._started = False
    
    # ========== STATE MANAGEMENT ==========
    
    async def _enter_idle_mode(self):
        """
        Enter IDLE mode: Subscribe to MAIN + COLLAB buses
        
        In IDLE mode, agent:
        - Monitors MAIN bus (observes user/Dexter conversations)
        - Actively participates on COLLAB bus (proposals, refinements, votes)
        - Waits for task assignment
        """
        self.state = AgentState.IDLE
        
        # Subscribe to MAIN bus topics
        self.buses.main.subscribe(MainTopic.USER_INPUT, self._on_user_input)
        self.buses.main.subscribe(MainTopic.DEXTER_RESPONSE, self._on_dexter_response)
        self.buses.main.subscribe(MainTopic.CONTEXT_AVAILABLE, self._on_context_available)
        
        # Subscribe to COLLAB bus topics
        self.buses.collab.subscribe(CollabTopic.OBSERVATION, self._on_observation)
        self.buses.collab.subscribe(CollabTopic.PROPOSAL, self._on_proposal)
        self.buses.collab.subscribe(CollabTopic.REFINEMENT, self._on_refinement)
        self.buses.collab.subscribe(CollabTopic.CRITIQUE, self._on_critique)
        self.buses.collab.subscribe(CollabTopic.VOTE_REQUEST, self._on_vote_request)
        self.buses.collab.subscribe(CollabTopic.DEXTER_INTERVENTION, self._on_dexter_intervention)
    
    async def _exit_idle_mode(self):
        """Exit IDLE mode: Unsubscribe from MAIN + COLLAB"""
        # Unsubscribe from MAIN
        self.buses.main.unsubscribe(MainTopic.USER_INPUT, self._on_user_input)
        self.buses.main.unsubscribe(MainTopic.DEXTER_RESPONSE, self._on_dexter_response)
        self.buses.main.unsubscribe(MainTopic.CONTEXT_AVAILABLE, self._on_context_available)
        
        # Unsubscribe from COLLAB
        self.buses.collab.unsubscribe(CollabTopic.OBSERVATION, self._on_observation)
        self.buses.collab.unsubscribe(CollabTopic.PROPOSAL, self._on_proposal)
        self.buses.collab.unsubscribe(CollabTopic.REFINEMENT, self._on_refinement)
        self.buses.collab.unsubscribe(CollabTopic.CRITIQUE, self._on_critique)
        self.buses.collab.unsubscribe(CollabTopic.VOTE_REQUEST, self._on_vote_request)
        self.buses.collab.unsubscribe(CollabTopic.DEXTER_INTERVENTION, self._on_dexter_intervention)
    
    async def _enter_task_mode(self, task: Dict[str, Any]):
        """
        Enter ON_TASK mode: Unsubscribe from MAIN+COLLAB, subscribe to additional PRIVATE topics
        
        In ON_TASK mode, agent:
        - ONLY listens to own PRIVATE bus
        - Ignores MAIN bus (no distractions)
        - Ignores COLLAB bus (no collaboration)
        - Receives context from BSM via PRIVATE bus
        - Receives support from Dexter via PRIVATE bus
        """
        # Exit idle mode first
        if self.state == AgentState.IDLE:
            await self._exit_idle_mode()
        
        self.state = AgentState.ON_TASK
        self._current_task = task
        
        # PRIVATE bus already exists from start()
        # Subscribe to additional PRIVATE bus topics (TASK_ASSIGNMENT already subscribed)
        self._private_bus.subscribe(PrivateTopic.DEXTER_SUPPORT, self._on_dexter_support)
        self._private_bus.subscribe(PrivateTopic.CONTEXT_UPDATE, self._on_context_update)
        self._private_bus.subscribe(PrivateTopic.HELP_REQUEST, self._on_help_request)
    
    async def _exit_task_mode(self):
        """Exit ON_TASK mode: Unsubscribe from additional PRIVATE topics, return to IDLE"""
        if self._private_bus:
            # Unsubscribe from additional PRIVATE topics (keep TASK_ASSIGNMENT subscribed)
            self._private_bus.unsubscribe(PrivateTopic.DEXTER_SUPPORT, self._on_dexter_support)
            self._private_bus.unsubscribe(PrivateTopic.CONTEXT_UPDATE, self._on_context_update)
            self._private_bus.unsubscribe(PrivateTopic.HELP_REQUEST, self._on_help_request)
            
            # Don't destroy PRIVATE bus - agent still needs to receive future task assignments
        
        self._current_task = None
        
        # Return to idle mode
        await self._enter_idle_mode()
    
    # ========== MAIN BUS HANDLERS (IDLE MODE) ==========
    
    async def _on_user_input(self, msg: Dict[str, Any]):
        """Handle USER_INPUT on MAIN bus (idle agents observe)"""
        if self.state != AgentState.IDLE:
            return
        
        # Agent observes user input, may decide to propose solution
        # Subclasses can override to generate proposals
        pass
    
    async def _on_dexter_response(self, msg: Dict[str, Any]):
        """Handle DEXTER_RESPONSE on MAIN bus (idle agents observe)"""
        if self.state != AgentState.IDLE:
            return
        
        # Agent observes Dexter's response
        # Subclasses can override to understand context
        pass
    
    async def _on_context_available(self, msg: Dict[str, Any]):
        """Handle CONTEXT_AVAILABLE from BSM (idle agents receive context)"""
        if self.state != AgentState.IDLE:
            return
        
        # BSM provides context to all agents
        self._latest_context = msg
    
    # ========== COLLAB BUS HANDLERS (IDLE MODE) ==========
    
    async def _on_observation(self, msg: Dict[str, Any]):
        """Handle OBSERVATION on COLLAB bus (Dexter shares understanding)"""
        if self.state != AgentState.IDLE:
            return
        
        # Dexter broadcasts observation, agent may propose solution
        # Subclasses can override to generate proposals
        pass
    
    async def _on_proposal(self, msg: Dict[str, Any]):
        """Handle PROPOSAL on COLLAB bus (peer agent proposes)"""
        if self.state != AgentState.IDLE:
            return
        
        # Another agent proposed, this agent may refine or critique
        # Subclasses can override to participate
        pass
    
    async def _on_refinement(self, msg: Dict[str, Any]):
        """Handle REFINEMENT on COLLAB bus (peer improves proposal)"""
        if self.state != AgentState.IDLE:
            return
        
        # Another agent refined a proposal
        pass
    
    async def _on_critique(self, msg: Dict[str, Any]):
        """Handle CRITIQUE on COLLAB bus (peer identifies issues)"""
        if self.state != AgentState.IDLE:
            return
        
        # Another agent critiqued a proposal
        pass
    
    async def _on_vote_request(self, msg: Dict[str, Any]):
        """Handle VOTE_REQUEST on COLLAB bus (Dexter calls vote)"""
        if self.state != AgentState.IDLE:
            return
        
        # Dexter requests vote on proposals
        # Subclasses should override to cast informed votes
        pass
    
    async def _on_dexter_intervention(self, msg: Dict[str, Any]):
        """Handle DEXTER_INTERVENTION on COLLAB bus (Dexter guides)"""
        if self.state != AgentState.IDLE:
            return
        
        # Dexter intervenes to guide collaboration
        pass
    
    # ========== PRIVATE BUS HANDLERS (ON-TASK MODE) ==========
    
    async def _on_task_assignment(self, msg: Dict[str, Any]):
        """Handle TASK_ASSIGNMENT on PRIVATE bus"""
        task = msg.get("task", {})
        
        # Enter task mode if not already
        if self.state == AgentState.IDLE:
            await self._enter_task_mode(task)
        else:
            # Update current task
            self._current_task = task
        
        # Execute task
        try:
            result = await self.execute_task(task)
            
            # Check if execution returned an error status
            if result.get("status") in ["error", "denied", "failed"]:
                # Report failure
                await self._private_bus.publish(PrivateTopic.TASK_COMPLETE, {
                    "from": self.agent_id,
                    "task": task,
                    "result": result,
                    "error": result.get("error", result.get("reason", "Task failed")),
                    "status": "failed",
                })
                
                # Return to idle mode
                await self._exit_task_mode()
            else:
                # Report success
                await self._private_bus.publish(PrivateTopic.TASK_COMPLETE, {
                    "from": self.agent_id,
                    "task": task,
                    "result": result,
                    "status": "success",
                })
                
                self._tasks_completed += 1
                
                # Return to idle mode
                await self._exit_task_mode()
            
        except Exception as e:
            # Report failure (unexpected exception)
            await self._private_bus.publish(PrivateTopic.TASK_COMPLETE, {
                "from": self.agent_id,
                "task": task,
                "error": str(e),
                "status": "failed",
            })
            
            self._tasks_failed += 1
            
            # Return to idle mode
            await self._exit_task_mode()
    
    async def _on_dexter_support(self, msg: Dict[str, Any]):
        """Handle DEXTER_SUPPORT on PRIVATE bus (Dexter helps)"""
        # Dexter provides help/guidance during task execution
        support = msg.get("support", {})
        # Subclasses can use this to adjust execution
        pass
    
    async def _on_context_update(self, msg: Dict[str, Any]):
        """Handle CONTEXT_UPDATE from BSM on PRIVATE bus"""
        # BSM sends relevant context for current task
        self._latest_context = msg
    
    async def _on_help_request(self, msg: Dict[str, Any]):
        """Handle HELP_REQUEST on PRIVATE bus"""
        # Agent can request help from Dexter
        pass
    
    # ========== COLLABORATION METHODS (CALLED FROM SUBCLASSES) ==========
    
    async def generate_proposal(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate proposal for collaboration.
        
        Subclasses should override to provide domain-specific proposals.
        
        Returns:
            Proposal dict with structure:
            {
                "solution": str,
                "approach": str,
                "confidence": float,
                "reasoning": str,
                "requires": [str]  # Required capabilities/resources
            }
        """
        # Default: No proposal
        return {}
    
    async def refine_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Refine another agent's proposal.
        
        Subclasses should override to improve proposals in their domain.
        
        Returns:
            Refinement dict with structure:
            {
                "original_proposal_id": str,
                "improvements": [str],
                "refined_solution": str,
                "confidence": float
            }
        """
        # Default: No refinement
        return {}
    
    async def critique_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Critique another agent's proposal (identify issues).
        
        Subclasses should override to spot problems in their domain.
        
        Returns:
            Critique dict with structure:
            {
                "proposal_id": str,
                "issues": [str],
                "severity": str,  # "minor", "major", "blocking"
                "suggestions": [str]
            }
        """
        # Default: No critique
        return {}
    
    async def vote(self, proposals: List[Dict[str, Any]]) -> str:
        """
        Vote on proposals.
        
        Subclasses should override to cast informed votes.
        
        Args:
            proposals: List of proposals to vote on
        
        Returns:
            proposal_id of chosen proposal
        """
        # Default: Vote for first proposal
        return proposals[0].get("id", "") if proposals else ""
    
    # ========== TASK EXECUTION ==========
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute assigned task with policy validation.
        
        This method validates the task against policy before executing.
        Subclasses should implement _execute_task_impl() for actual execution.
        
        Args:
            task: Task dict from TASK_ASSIGNMENT
        
        Returns:
            Result dict with status, output, etc.
        """
        # Validate task against policy
        allowed, reason = await self._validate_task(task)
        if not allowed:
            return {
                "status": "denied",
                "reason": reason,
                "policy_violation": True,
            }
        
        # Execute task (subclass implements)
        try:
            result = await self._execute_task_impl(task)
            return result
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__,
            }
    
    async def _validate_task(self, task: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate task against policy.
        
        Subclasses can override to add domain-specific validation.
        
        Returns:
            (allowed: bool, reason: str)
        """
        # Basic validation: Check task structure
        if not task or not isinstance(task, dict):
            return False, "Invalid task structure"
        
        # Check if task description exists
        if "description" not in task:
            return False, "Task missing description"
        
        # Subclasses should override to add domain-specific policy checks
        # e.g., file write permissions, network access, etc.
        
        return True, ""
    
    async def _execute_task_impl(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute task implementation (subclass must override).
        
        This is where the actual task execution happens.
        Subclasses MUST implement this method.
        
        Args:
            task: Task dict with description, parameters, etc.
        
        Returns:
            Result dict with status, output, etc.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _execute_task_impl()"
        )
    
    # ========== HELPER METHODS ==========
    
    async def request_help_from_dexter(self, request: str):
        """Request help from Dexter via PRIVATE bus"""
        if self.state != AgentState.ON_TASK or not self._private_bus:
            return
        
        await self._private_bus.publish(PrivateTopic.HELP_REQUEST, {
            "from": self.agent_id,
            "request": request,
            "current_task": self._current_task,
        })
    
    async def report_progress(self, progress: int, message: str = ""):
        """Report task progress to Dexter via PRIVATE bus"""
        if self.state != AgentState.ON_TASK or not self._private_bus:
            return
        
        await self._private_bus.publish(PrivateTopic.PROGRESS, {
            "from": self.agent_id,
            "progress": progress,
            "message": message,
            "task_id": self._current_task.get("id") if self._current_task else None,
        })
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics"""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "state": self.state.value,
            "current_task": self._current_task.get("id") if self._current_task else None,
            "tasks_completed": self._tasks_completed,
            "tasks_failed": self._tasks_failed,
            "proposals_made": self._proposals_made,
            "votes_cast": self._votes_cast,
            "refinements_made": self._refinements_made,
            "critiques_made": self._critiques_made,
            "has_context": self._latest_context is not None,
            "capabilities": self.capabilities,
        }

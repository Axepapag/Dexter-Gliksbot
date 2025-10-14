from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Dict, List, Optional

from ..brain.memory import BrainDB
from ..core.triple_bus import (
    CollabTopic,
    MainTopic,
    PrivateTopic,
    TripleBusSystem,
)
from .adapters.ollama_adapter import OllamaClient

DEFAULT_BSM_PROMPT = (
    'Summarize the observation and return JSON with fields: '
    '"summary": str, "tags": [str], "entities": [{"type": "", "value": ""}], '
    '"relations": [{"source": "", "target": "", "relation": ""}].\n<<<\n{obs}\n>>>'
)
DEFAULT_BSM_SYSTEM = "Respond with a single JSON object only."

DEFAULT_CONTEXT_PROMPT = (
    "Based on this current situation and past memories, what context would be most helpful?\n"
    "Current: {current}\n"
    "Memories: {memories}\n"
    "Respond with JSON: {\"relevant_context\": str, \"confidence\": float, \"reason\": str}"
)


class BSM:
    """
    Brain/State Model (BSM) - The Omniscient Observer
    
    BSM is the all-seeing brain of Dexter:
    - Subscribes to ALL buses (MAIN, COLLAB, all PRIVATE)
    - Observes EVERYTHING happening in the system
    - Stores all interactions for learning
    - Provides intelligent context proactively to agents
    - NEVER executes actions, only observes/stores/learns/provides
    
    Architecture:
        BSM → Observes → Stores → Learns → Provides Context
        
    Context Provisioning:
        - MAIN bus: Broadcasts CONTEXT_AVAILABLE for all agents
        - PRIVATE bus: Sends CONTEXT_UPDATE to specific on-task agents
    """
    
    def __init__(
        self,
        buses: TripleBusSystem,
        brain: BrainDB,
        model: str | None = None,
        host: str = "http://127.0.0.1:11434",
        temperature: float = 0.1,
        *,
        api_key_env: str | None = None,
        system_prompt: str | None = None,
        prompt: str | None = None,
        context_prompt: str | None = None,
        client_options: Optional[Dict[str, object]] = None,
        call_options: Optional[Dict[str, object]] = None,
    ) -> None:
        self.buses = buses
        self.model = model
        self.brain = brain
        self.temperature = temperature
        self.prompt = prompt or DEFAULT_BSM_PROMPT
        self.context_prompt = context_prompt or DEFAULT_CONTEXT_PROMPT
        self.system_prompt = system_prompt or DEFAULT_BSM_SYSTEM
        self.call_options = dict(call_options or {})

        self.ollama = (
            OllamaClient(host, api_key_env=api_key_env, default_options=client_options)
            if model
            else None
        )
        
        # Tracking
        self._observation_count = 0
        self._context_provided_count = 0
        self._monitored_private_buses = set()
        self._monitoring_task: Optional[asyncio.Task] = None
        self._started = False

    async def start(self):
        """
        Start BSM - Subscribe to ALL buses and begin omniscient observation.
        
        BSM subscribes to:
        1. ALL MAIN topics (user input, dexter responses, intents, effects, errors, traces)
        2. ALL COLLAB topics (proposals, refinements, critiques, votes, consensus)
        3. ALL PRIVATE buses (monitors for new buses, subscribes to all topics)
        """
        if self._started:
            return
        
        # Subscribe to ALL MAIN topics
        for topic in MainTopic:
            self.buses.main.subscribe(topic, self._observe_main)
        
        # Subscribe to ALL COLLAB topics
        for topic in CollabTopic:
            self.buses.collab.subscribe(topic, self._observe_collab)
        
        # Start monitoring for new PRIVATE buses
        self._monitoring_task = asyncio.create_task(self._monitor_private_buses())
        
        self._started = True
    
    async def stop(self):
        """Stop BSM observation"""
        if not self._started:
            return
        
        # Unsubscribe from MAIN
        for topic in MainTopic:
            self.buses.main.unsubscribe(topic, self._observe_main)
        
        # Unsubscribe from COLLAB
        for topic in CollabTopic:
            self.buses.collab.unsubscribe(topic, self._observe_collab)
        
        # Stop monitoring private buses
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        self._started = False
    
    async def _observe_main(self, msg: Dict[str, Any]):
        """
        Observe MAIN bus message.
        
        MAIN bus contains:
        - USER_INPUT: User speaks to Dexter
        - DEXTER_RESPONSE: Dexter replies (includes extracted actions)
        - INTENT: Commands (mostly from Dexter to system agents)
        - EFFECT: Results (system agents report back)
        - ERROR: Errors (Dexter handles)
        - TRACE: Debug logs
        """
        await self._observe(msg, bus="main")
    
    async def _observe_collab(self, msg: Dict[str, Any]):
        """
        Observe COLLAB bus message.
        
        COLLAB bus contains:
        - OBSERVATION: Dexter shares understanding
        - PROPOSAL: Agent proposes solution
        - REFINEMENT: Agent improves peer's proposal
        - CRITIQUE: Agent identifies issues
        - CONSENSUS: Agreement reached
        - VOTE_REQUEST/VOTE_RESPONSE: Voting on proposals
        - DEXTER_INTERVENTION: Dexter enters to guide
        """
        await self._observe(msg, bus="collab")
    
    async def _observe_private(self, msg: Dict[str, Any]):
        """
        Observe PRIVATE bus message.
        
        PRIVATE bus contains (per-agent):
        - TASK_ASSIGNMENT: Dexter/user assigns task
        - PROGRESS: Agent reports progress
        - DEXTER_SUPPORT: Dexter provides help
        - HELP_REQUEST: Agent requests Dexter's help
        - CONTEXT_UPDATE: BSM sends relevant context (this is BSM's own message)
        - TASK_COMPLETE: Agent finished task
        """
        # Don't observe our own CONTEXT_UPDATE messages (avoid loop)
        if msg.get("topic") == PrivateTopic.CONTEXT_UPDATE.value and msg.get("from") == "bsm":
            return
        
        await self._observe(msg, bus="private")
    
    async def _observe(self, msg: Dict[str, Any], bus: str):
        """
        Core observation logic - store everything, extract knowledge, provide context.
        
        Flow:
        1. Observe: Receive message from any bus
        2. Store: Add to brain (STM/LTM)
        3. Learn: Extract entities, relations, patterns
        4. Provide: Determine and broadcast/send relevant context
        """
        self._observation_count += 1
        
        # Build observation content
        content = json.dumps(msg)
        
        # Extract metadata
        meta = {
            "bus": bus,
            "topic": msg.get("topic", "unknown"),
            "from": msg.get("from", "unknown"),
            "to": msg.get("to", []) if isinstance(msg.get("to"), list) else [msg.get("to", "")],
            "ts": msg.get("ts", time.time()),
            "msg_id": msg.get("id", ""),
        }
        
        # Store observation using ingest (with LLM summarization if available)
        await asyncio.to_thread(
            self.ingest,
            content,
            meta
        )
        
        # Determine if context should be provided based on this observation
        await self._provide_context_if_needed(msg, bus)
    
    async def _monitor_private_buses(self):
        """
        Continuously monitor for new PRIVATE buses and subscribe to them.
        
        BSM must observe ALL PRIVATE buses, including ones created after BSM starts.
        This loop checks every 2 seconds for new PRIVATE buses.
        """
        while True:
            try:
                await asyncio.sleep(2)  # Check every 2 seconds
                
                # Get all active PRIVATE buses
                current_private_buses = self.buses.get_all_private_buses()
                
                # Subscribe to any new buses
                for agent_id, private_bus in current_private_buses.items():
                    if agent_id not in self._monitored_private_buses:
                        # New PRIVATE bus detected - subscribe to ALL topics
                        for topic in PrivateTopic:
                            private_bus.subscribe(topic, self._observe_private)
                        
                        self._monitored_private_buses.add(agent_id)
                
            except asyncio.CancelledError:
                raise
            except Exception:
                # Don't crash monitoring loop on errors
                pass
    
    async def _provide_context_if_needed(self, msg: Dict[str, Any], bus: str):
        """
        Determine if context should be provided based on current observation.
        
        Context provisioning strategies:
        1. MAIN bus USER_INPUT → Search memories, broadcast CONTEXT_AVAILABLE
        2. COLLAB bus PROPOSAL → Search for similar past proposals
        3. PRIVATE bus TASK_ASSIGNMENT → Search for relevant task history
        4. PRIVATE bus HELP_REQUEST → Search for solution patterns
        
        BSM decides WHEN and WHAT context is relevant (agents don't request).
        """
        topic = msg.get("topic", "")
        
        # Strategy 1: User input → Provide context about user's question/request
        if bus == "main" and topic == MainTopic.USER_INPUT.value:
            await self._provide_context_for_user_input(msg)
        
        # Strategy 2: Task assignment → Provide context about similar tasks
        elif bus == "private" and topic == PrivateTopic.TASK_ASSIGNMENT.value:
            await self._provide_context_for_task(msg)
        
        # Strategy 3: Help request → Provide solution patterns
        elif bus == "private" and topic == PrivateTopic.HELP_REQUEST.value:
            await self._provide_context_for_help(msg)
        
        # Strategy 4: Collaboration proposal → Provide past experience
        elif bus == "collab" and topic == CollabTopic.PROPOSAL.value:
            await self._provide_context_for_proposal(msg)
    
    async def _provide_context_for_user_input(self, msg: Dict[str, Any]):
        """Provide context when user speaks"""
        user_content = msg.get("content", "")
        if not user_content:
            return
        
        # Search memories for relevant past interactions
        relevant_memories = await asyncio.to_thread(
            self.brain.search,
            user_content,
            k=5
        )
        
        if not relevant_memories:
            return
        
        # Determine what context is most helpful (using LLM if available)
        context = await self._determine_needed_context(
            current=user_content,
            memories=relevant_memories
        )
        
        if context:
            # Broadcast to MAIN bus (all agents can see)
            await self.buses.main.publish(MainTopic.CONTEXT_AVAILABLE, {
                "from": "bsm",
                "context": context,
                "memories": relevant_memories,
                "trigger": "user_input",
            })
            self._context_provided_count += 1
    
    async def _provide_context_for_task(self, msg: Dict[str, Any]):
        """Provide context when task assigned"""
        task_description = msg.get("task", {}).get("description", "")
        agent_id = msg.get("to", "")
        
        if not task_description or not agent_id:
            return
        
        # Search for similar past tasks
        relevant_memories = await asyncio.to_thread(
            self.brain.search,
            task_description,
            k=5
        )
        
        if relevant_memories:
            # Send to specific agent's PRIVATE bus
            private_bus = await self.buses.get_private(agent_id)
            await private_bus.publish(PrivateTopic.CONTEXT_UPDATE, {
                "from": "bsm",
                "context": f"Found {len(relevant_memories)} similar past tasks",
                "memories": relevant_memories,
                "trigger": "task_assignment",
            })
            self._context_provided_count += 1
    
    async def _provide_context_for_help(self, msg: Dict[str, Any]):
        """Provide context when agent requests help"""
        help_request = msg.get("request", "")
        agent_id = msg.get("from", "")
        
        if not help_request or not agent_id:
            return
        
        # Search for solution patterns
        relevant_memories = await asyncio.to_thread(
            self.brain.search,
            help_request,
            k=5
        )
        
        if relevant_memories:
            # Send to agent's PRIVATE bus
            private_bus = await self.buses.get_private(agent_id)
            await private_bus.publish(PrivateTopic.CONTEXT_UPDATE, {
                "from": "bsm",
                "context": f"Found {len(relevant_memories)} relevant solutions",
                "memories": relevant_memories,
                "trigger": "help_request",
            })
            self._context_provided_count += 1
    
    async def _provide_context_for_proposal(self, msg: Dict[str, Any]):
        """Provide context when agent proposes solution"""
        proposal = msg.get("proposal", {})
        proposal_text = json.dumps(proposal) if isinstance(proposal, dict) else str(proposal)
        
        if not proposal_text:
            return
        
        # Search for similar past proposals/solutions
        relevant_memories = await asyncio.to_thread(
            self.brain.search,
            proposal_text,
            k=5
        )
        
        if relevant_memories:
            # Broadcast to MAIN bus (all collaborating agents can see)
            await self.buses.main.publish(MainTopic.CONTEXT_AVAILABLE, {
                "from": "bsm",
                "context": f"Found {len(relevant_memories)} similar past proposals",
                "memories": relevant_memories,
                "trigger": "collaboration_proposal",
            })
            self._context_provided_count += 1
    
    async def _determine_needed_context(
        self, current: str, memories: List[Dict[str, Any]]
    ) -> str:
        """
        Use LLM to determine what context is most helpful.
        
        If no LLM available, return simple summary.
        """
        if not self.ollama or not self.model or not memories:
            return f"Found {len(memories)} relevant past interactions"
        
        # Build context determination prompt
        memories_text = "\n".join([
            f"- {m['content'][:200]}... (ts: {m['ts']}, tags: {m['meta'].get('tags', [])})"
            for m in memories[:3]
        ])
        
        prompt_body = self.context_prompt.replace("{current}", current[:500])
        prompt_body = prompt_body.replace("{memories}", memories_text)
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt_body},
        ]
        
        try:
            out = await asyncio.to_thread(
                self.ollama.chat,
                self.model,
                messages,
                temperature=self.temperature,
                options=self.call_options,
            )
            match = re.search(r"\{.*\}", out, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
                return result.get("relevant_context", "")
        except Exception:
            pass
        
        return f"Found {len(memories)} relevant past interactions"
    
    def ingest(self, obs: str, meta: Dict[str, Any]) -> int:
        """
        Ingest observation into brain (legacy method, kept for compatibility).
        
        Now used internally by _observe() method.
        """
        if not self.ollama or not self.model:
            return self.brain.add_memory("observation", obs[:500], meta)

        prompt_body = self.prompt.replace("{obs}", obs[:4000])
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt_body},
        ]
        try:
            out = self.ollama.chat(
                self.model,
                messages,
                temperature=self.temperature,
                options=self.call_options,
            )
            match = re.search(r"\{.*\}", out, re.DOTALL)
            document = json.loads(match.group(0)) if match else {}
        except Exception:
            document = {}

        summary = document.get("summary") or obs[:500]
        tags = document.get("tags", [])
        memory_meta = {"tags": tags, **meta}
        return self.brain.add_memory("observation", summary, memory_meta)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get BSM statistics"""
        return {
            "started": self._started,
            "observations": self._observation_count,
            "context_provided": self._context_provided_count,
            "monitored_private_buses": len(self._monitored_private_buses),
            "private_bus_ids": list(self._monitored_private_buses),
        }

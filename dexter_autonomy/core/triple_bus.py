"""
Triple Event Bus Architecture for Dexter-Gliksbot

Three independent buses:
1. MAIN - User ↔ Dexter conversation + system commands
2. COLLAB - Idle general agents collaborate in background
3. PRIVATE - Per-agent channels for on-task communication

BSM and Dexter subscribe to ALL buses.
General agents subscribe based on status (idle vs on-task).
"""
from __future__ import annotations
import asyncio
import time
import uuid
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Optional

Handler = Callable[[dict], Awaitable[None]]


class MainTopic(str, Enum):
    """MAIN bus topics: User ↔ Dexter + system commands"""
    USER_INPUT = "user_input"
    DEXTER_RESPONSE = "dexter_response"
    INTENT = "intent"
    EFFECT = "effect"
    ERROR = "error"
    TRACE = "trace"
    CONTEXT_AVAILABLE = "context_available"


class CollabTopic(str, Enum):
    """COLLAB bus topics: Idle agent collaboration"""
    OBSERVATION = "observation"
    PROPOSAL = "proposal"
    REFINEMENT = "refinement"
    CRITIQUE = "critique"
    CONSENSUS = "consensus"
    VOTE_REQUEST = "vote_request"
    VOTE_RESPONSE = "vote_response"
    DEXTER_INTERVENTION = "dexter_intervention"
    
    # CollaborationManager lifecycle events (for BSM observability)
    COLLABORATION_STARTED = "collaboration_started"
    COLLABORATION_COMPLETE = "collaboration_complete"
    COLLABORATION_ABORTED = "collaboration_aborted"
    COLLABORATION_PAUSED = "collaboration_paused"
    PHASE_TRANSITION = "phase_transition"
    DEADLINE_WARNING = "deadline_warning"


class PrivateTopic(str, Enum):
    """PRIVATE bus topics: Per-agent on-task communication"""
    TASK_ASSIGNMENT = "task_assignment"
    PROGRESS = "progress"
    DEXTER_SUPPORT = "dexter_support"
    HELP_REQUEST = "help_request"
    CONTEXT_UPDATE = "context_update"
    TASK_COMPLETE = "task_complete"


class EventBus:
    """
    Single event bus with typed topics.
    Used as base for MAIN, COLLAB, and PRIVATE buses.
    """
    
    def __init__(self, bus_id: str, topics: type[Enum]):
        self.bus_id = bus_id
        self.topics = topics
        self.queues: Dict[str, asyncio.Queue] = {
            t.value: asyncio.Queue(maxsize=1000) for t in topics
        }
        self.subscribers: Dict[str, list[Handler]] = {
            t.value: [] for t in topics
        }
        self._tasks: list[asyncio.Task] = []
        self._started = False
        self._start_lock = asyncio.Lock()
    
    async def _drain(self, topic: str):
        """Process messages from queue and dispatch to subscribers"""
        while True:
            msg = await self.queues[topic].get()
            for handler in list(self.subscribers[topic]):
                try:
                    await handler(msg)
                except Exception as exc:
                    # Log error but don't crash the drain loop
                    error_msg = {
                        "id": str(uuid.uuid4()),
                        "ts": time.time(),
                        "bus": self.bus_id,
                        "topic": topic,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    }
                    # Try to publish to ERROR topic if it exists
                    if "error" in self.queues:
                        try:
                            await self.queues["error"].put(error_msg)
                        except:
                            pass  # Avoid error loop
    
    async def start(self):
        """Start all drain tasks"""
        async with self._start_lock:
            if self._started:
                return
            loop = asyncio.get_running_loop()
            for topic in self.topics:
                task = loop.create_task(self._drain(topic.value))
                self._tasks.append(task)
            self._started = True
    
    async def stop(self):
        """Stop all drain tasks"""
        if not self._started:
            return
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        self._started = False
    
    def subscribe(self, topic: Enum, handler: Handler):
        """Subscribe to a topic"""
        topic_value = topic.value if isinstance(topic, Enum) else topic
        if topic_value not in self.subscribers:
            raise ValueError(f"Unknown topic: {topic_value}")
        self.subscribers[topic_value].append(handler)
    
    def unsubscribe(self, topic: Enum, handler: Handler):
        """Unsubscribe from a topic"""
        topic_value = topic.value if isinstance(topic, Enum) else topic
        if topic_value in self.subscribers:
            try:
                self.subscribers[topic_value].remove(handler)
            except ValueError:
                pass  # Handler wasn't subscribed
    
    def unsubscribe_all(self, handler: Handler):
        """Unsubscribe handler from all topics"""
        for topic_subscribers in self.subscribers.values():
            try:
                topic_subscribers.remove(handler)
            except ValueError:
                pass
    
    async def publish(self, topic: Enum, payload: Dict[str, Any]):
        """Publish message to topic"""
        topic_value = topic.value if isinstance(topic, Enum) else topic
        
        if topic_value not in self.queues:
            raise ValueError(f"Unknown topic: {topic_value}")
        
        # Auto-inject metadata
        if "id" not in payload:
            payload["id"] = str(uuid.uuid4())
        if "ts" not in payload:
            payload["ts"] = time.time()
        if "bus" not in payload:
            payload["bus"] = self.bus_id
        if "topic" not in payload:
            payload["topic"] = topic_value
        
        await self.queues[topic_value].put(payload)
    
    def get_subscriber_count(self, topic: Enum) -> int:
        """Get number of subscribers for a topic"""
        topic_value = topic.value if isinstance(topic, Enum) else topic
        return len(self.subscribers.get(topic_value, []))


class TripleBusSystem:
    """
    Complete triple bus architecture for Dexter-Gliksbot.
    
    Usage:
        buses = TripleBusSystem()
        await buses.start_all()
        
        # MAIN bus: User ↔ Dexter
        await buses.main.publish(MainTopic.USER_INPUT, {"content": "Hello"})
        
        # COLLAB bus: Idle agents collaborate
        await buses.collab.publish(CollabTopic.PROPOSAL, {"from": "coder", "proposal": {...}})
        
        # PRIVATE bus: On-task communication
        await buses.get_private("web_scraper").publish(PrivateTopic.PROGRESS, {"progress": 50})
    """
    
    def __init__(self):
        # 1. MAIN bus: Conversation + system commands
        self.main = EventBus("main", MainTopic)
        
        # 2. COLLAB bus: Idle agent collaboration
        self.collab = EventBus("collab", CollabTopic)
        
        # 3. PRIVATE buses: Per-agent channels (lazy creation)
        self._private_buses: Dict[str, EventBus] = {}
        self._private_bus_lock = asyncio.Lock()
    
    async def start_all(self):
        """Start all buses"""
        await self.main.start()
        await self.collab.start()
        # Private buses started on-demand when created
    
    async def stop_all(self):
        """Stop all buses"""
        await self.main.stop()
        await self.collab.stop()
        for private_bus in self._private_buses.values():
            await private_bus.stop()
    
    async def get_private(self, agent_id: str) -> EventBus:
        """
        Get or create PRIVATE bus for agent.
        Lazy creation - only created when agent assigned task.
        """
        if agent_id in self._private_buses:
            return self._private_buses[agent_id]
        
        async with self._private_bus_lock:
            # Double-check after acquiring lock
            if agent_id in self._private_buses:
                return self._private_buses[agent_id]
            
            # Create new private bus
            private_bus = EventBus(f"private:{agent_id}", PrivateTopic)
            await private_bus.start()
            self._private_buses[agent_id] = private_bus
            return private_bus
    
    async def destroy_private(self, agent_id: str):
        """
        Destroy PRIVATE bus for agent.
        Called when agent completes task and returns to idle.
        """
        if agent_id not in self._private_buses:
            return
        
        async with self._private_bus_lock:
            if agent_id in self._private_buses:
                await self._private_buses[agent_id].stop()
                del self._private_buses[agent_id]
    
    def get_all_private_buses(self) -> Dict[str, EventBus]:
        """Get all active PRIVATE buses (for BSM/Dexter monitoring)"""
        return dict(self._private_buses)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about all buses"""
        return {
            "main": {
                "topics": len(self.main.queues),
                "subscribers": sum(len(subs) for subs in self.main.subscribers.values()),
                "started": self.main._started,
            },
            "collab": {
                "topics": len(self.collab.queues),
                "subscribers": sum(len(subs) for subs in self.collab.subscribers.values()),
                "started": self.collab._started,
            },
            "private": {
                "bus_count": len(self._private_buses),
                "agent_ids": list(self._private_buses.keys()),
            },
        }


# Global instance (singleton pattern for convenience)
_global_triple_bus: Optional[TripleBusSystem] = None


def get_global_triple_bus() -> TripleBusSystem:
    """Get or create global triple bus system"""
    global _global_triple_bus
    if _global_triple_bus is None:
        _global_triple_bus = TripleBusSystem()
    return _global_triple_bus


def reset_global_triple_bus():
    """Reset global triple bus (for testing)"""
    global _global_triple_bus
    _global_triple_bus = None

"""
WebSocket Manager - TripleBus to Cockpit Bridge

Bridges TripleBus events to WebSocket clients via ConnectionManager.
Observes all buses (MAIN, COLLAB, PRIVATE) and transforms events for Cockpit UI.

Design Decisions (Comet Collaboration):
- Cache from event stream (Option B) - BSM-like observation pattern
- Optional force_refresh for critical scenarios (2s timeout)
- Staleness monitoring with cache_age tracking
- LRU cache (max 1000 agents, 500 missions)
- 5s aggregation for agent status updates (non-critical)
- Immediate broadcast for critical events (errors, mission failures)
"""

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
import psutil
import os

from dexter_autonomy.core.triple_bus import TripleBusSystem, MainTopic, CollabTopic, PrivateTopic
from dexter_autonomy.api.connection_manager import ConnectionManager
from dexter_autonomy.api.websocket_events import (
    WebSocketMessage,
    EventType,
    AgentStatus,
    MissionPhase,
    TripleBusTransformer,
    create_state_snapshot
)

logger = logging.getLogger(__name__)


class LRUCache(OrderedDict):
    """LRU cache with max size"""
    
    def __init__(self, max_size: int):
        super().__init__()
        self.max_size = max_size
    
    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self.max_size:
            oldest = next(iter(self))
            del self[oldest]


class WebSocketManager:
    """
    Bridges TripleBus events to WebSocket clients.
    
    Architecture:
    - Subscribes to ALL buses (observer pattern like BSM)
    - Maintains state cache from observed events
    - Transforms TripleBus events → WebSocket messages
    - Broadcasts to ConnectionManager → Cockpit clients
    - Aggregates high-frequency events (5s for agent status)
    - Immediate delivery for critical events
    """
    
    def __init__(
        self,
        triple_bus: TripleBusSystem,
        event_history_size: int = 1000,
        max_agents: int = 1000,
        max_missions: int = 500
    ):
        self.bus = triple_bus
        self.connection_manager = ConnectionManager(event_history_size=event_history_size)
        self.transformer = TripleBusTransformer()
        
        # State caches (LRU)
        self._agent_state_cache: LRUCache = LRUCache(max_agents)
        self._mission_state_cache: LRUCache = LRUCache(max_missions)
        self._system_metrics_cache: Dict[str, Any] = {}
        
        # Timestamps for staleness monitoring
        self._agent_last_seen: Dict[str, datetime] = {}
        self._mission_last_seen: Dict[str, datetime] = {}
        self._system_metrics_last_update: datetime = datetime.utcnow()
        
        # Subscription tracking
        self._subscribed_private_buses: Set[str] = set()
        
        # Lifecycle
        self._started = False
        self._start_time = datetime.utcnow()
        
        # Override ConnectionManager's get_state_snapshot
        self.connection_manager.get_state_snapshot = self.get_state_snapshot
    
    async def start(self) -> None:
        """Start WebSocketManager and subscribe to all buses"""
        if self._started:
            logger.warning("WebSocketManager already started")
            return
        
        logger.info("Starting WebSocketManager...")
        
        # Subscribe to MAIN bus
        self.bus.main.subscribe(MainTopic.TRACE, self._handle_main_event)
        self.bus.main.subscribe(MainTopic.ERROR, self._handle_main_event)
        self.bus.main.subscribe(MainTopic.EFFECT, self._handle_main_event)
        self.bus.main.subscribe(MainTopic.CONTEXT_AVAILABLE, self._handle_main_event)
        
        # Subscribe to COLLAB bus (all topics)
        for topic in CollabTopic:
            self.bus.collab.subscribe(topic, self._handle_collab_event)
        
        # Subscribe to existing PRIVATE buses (access private attribute)
        for agent_id, private_bus in self.bus._private_buses.items():
            self._subscribe_to_private_bus(agent_id, private_bus)
        
        # Start periodic system metrics collection
        asyncio.create_task(self._collect_system_metrics_loop())
        
        self._started = True
        self._start_time = datetime.utcnow()
        
        logger.info("WebSocketManager started successfully")
    
    async def stop(self) -> None:
        """Stop WebSocketManager and cleanup"""
        if not self._started:
            return
        
        logger.info("Stopping WebSocketManager...")
        
        # Unsubscribe from all buses (TripleBus handles this on shutdown)
        # Shutdown ConnectionManager
        await self.connection_manager.shutdown()
        
        self._started = False
        logger.info("WebSocketManager stopped")
    
    def _subscribe_to_private_bus(self, agent_id: str, private_bus) -> None:
        """Subscribe to a PRIVATE bus for an agent"""
        if agent_id in self._subscribed_private_buses:
            return
        
        # Subscribe to all PRIVATE topics
        for topic in PrivateTopic:
            private_bus.subscribe(topic, self._handle_private_event)
        
        self._subscribed_private_buses.add(agent_id)
        logger.debug(f"Subscribed to PRIVATE bus for agent: {agent_id}")
    
    async def _handle_main_event(self, event: Dict[str, Any]) -> None:
        """Handle events from MAIN bus"""
        topic = event.get("_topic")  # Injected by EventBus
        
        # Update state cache
        self._update_cache_from_event("MAIN", topic, event)
        
        # Transform to WebSocket message
        ws_message = self.transformer.triplebus_to_websocket(
            bus="MAIN",
            topic=topic,
            event_data=event,
            force_send=self._is_critical_event(event)
        )
        
        if ws_message:
            await self.connection_manager.broadcast(ws_message)
    
    async def _handle_collab_event(self, event: Dict[str, Any]) -> None:
        """Handle events from COLLAB bus"""
        topic = event.get("_topic")
        
        # Transform and broadcast collaboration events
        ws_message = self.transformer.triplebus_to_websocket(
            bus="COLLAB",
            topic=topic,
            event_data=event,
            force_send=False  # Collaboration events not critical
        )
        
        if ws_message:
            await self.connection_manager.broadcast(ws_message)
    
    async def _handle_private_event(self, event: Dict[str, Any]) -> None:
        """Handle events from PRIVATE buses"""
        topic = event.get("_topic")
        agent_id = event.get("agent_id", "unknown")
        
        # Update mission cache
        self._update_cache_from_event("PRIVATE", topic, event)
        
        # Transform to WebSocket message
        ws_message = self.transformer.triplebus_to_websocket(
            bus="PRIVATE",
            topic=topic,
            event_data=event,
            force_send=self._is_critical_event(event)
        )
        
        if ws_message:
            await self.connection_manager.broadcast(ws_message)
    
    def _update_cache_from_event(self, bus: str, topic: str, event: Dict[str, Any]) -> None:
        """Update state cache from observed event"""
        now = datetime.utcnow()
        
        # Update agent state cache
        if "agent_id" in event:
            agent_id = event["agent_id"]
            
            # Extract agent status from event
            if "status" in event:
                self._agent_state_cache[agent_id] = {
                    "agent_id": agent_id,
                    "agent_name": event.get("agent_name", agent_id),
                    "status": event["status"],
                    "current_mission": event.get("mission_id"),
                    "uptime_seconds": (now - self._start_time).total_seconds(),
                    "success_rate": event.get("success_rate", 0.0),
                    "actions_completed": event.get("actions_completed", 0),
                    "last_action_timestamp": now,
                    "metrics": event.get("metrics", {})
                }
                self._agent_last_seen[agent_id] = now
        
        # Update mission state cache
        if "mission_id" in event:
            mission_id = event["mission_id"]
            
            if "progress" in event or "phase" in event:
                existing = self._mission_state_cache.get(mission_id, {})
                self._mission_state_cache[mission_id] = {
                    "mission_id": mission_id,
                    "mission_name": event.get("mission_name", existing.get("mission_name", mission_id)),
                    "phase": event.get("phase", existing.get("phase", "executing")),
                    "progress": event.get("progress", existing.get("progress", 0.0)),
                    "agents_assigned": event.get("agents_assigned", existing.get("agents_assigned", [])),
                    "started_at": existing.get("started_at", now),
                    "last_action": event.get("message", event.get("last_action"))
                }
                self._mission_last_seen[mission_id] = now
    
    def _is_critical_event(self, event: Dict[str, Any]) -> bool:
        """Check if event should be sent immediately (bypass aggregation)"""
        # Error events are critical
        if event.get("level") == "ERROR" or "error" in event:
            return True
        
        # Mission failures are critical
        if event.get("status") == "failed" or event.get("phase") == "failed":
            return True
        
        # Agent errors are critical
        if event.get("event_type") == "agent_error":
            return True
        
        return False
    
    async def _collect_system_metrics_loop(self) -> None:
        """Periodically collect system metrics (1Hz)"""
        while self._started:
            try:
                # Collect system metrics
                process = psutil.Process(os.getpid())
                
                self._system_metrics_cache = {
                    "event_bus_messages_per_sec": 0.0,  # TODO: Track from EventBus
                    "event_bus_queue_depth": 0,  # TODO: Track from EventBus
                    "active_agents": len(self._agent_state_cache),
                    "active_missions": len(self._mission_state_cache),
                    "cpu_percent": process.cpu_percent(),
                    "memory_mb": process.memory_info().rss / 1024 / 1024,
                    "brain_size_mb": 0.0,  # TODO: Query from BrainDB
                    "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds()
                }
                self._system_metrics_last_update = datetime.utcnow()
                
                # Broadcast system metrics
                ws_message = WebSocketMessage(
                    type=EventType.PERF_SYSTEM,
                    data=self._system_metrics_cache
                )
                await self.connection_manager.broadcast(ws_message)
                
            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
            
            await asyncio.sleep(1.0)  # 1Hz
    
    def get_state_snapshot(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get current system state snapshot.
        
        Args:
            force_refresh: If True, query agents directly (slower, 2s timeout)
                          If False, use cached state (fast, eventually consistent)
        
        Returns:
            Dict with agents, missions, system_metrics, cache_stats
        """
        if force_refresh:
            logger.warning("force_refresh=True is slow - use sparingly")
            # TODO: Implement on-demand refresh via REQUEST_STATUS on MAIN bus
            # For now, fall back to cache
        
        # Calculate cache ages
        now = datetime.utcnow()
        cache_stats = {
            "agents_cached": len(self._agent_state_cache),
            "missions_cached": len(self._mission_state_cache),
            "oldest_agent_cache_seconds": max(
                ((now - self._agent_last_seen.get(aid, now)).total_seconds()
                 for aid in self._agent_state_cache.keys()),
                default=0.0
            ),
            "oldest_mission_cache_seconds": max(
                ((now - self._mission_last_seen.get(mid, now)).total_seconds()
                 for mid in self._mission_state_cache.keys()),
                default=0.0
            ),
            "system_metrics_age_seconds": (now - self._system_metrics_last_update).total_seconds()
        }
        
        # Warn if caches are stale
        if cache_stats["oldest_agent_cache_seconds"] > 60:
            logger.warning(f"Agent cache stale: {cache_stats['oldest_agent_cache_seconds']:.1f}s")
        
        if cache_stats["oldest_mission_cache_seconds"] > 30:
            logger.warning(f"Mission cache stale: {cache_stats['oldest_mission_cache_seconds']:.1f}s")
        
        return {
            "agents": list(self._agent_state_cache.values()),
            "missions": list(self._mission_state_cache.values()),
            "system_metrics": self._system_metrics_cache,
            "cache_stats": cache_stats,
            "knowledge_graph_stats": None  # TODO: Query from KnowledgeGraph if available
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocketManager statistics"""
        return {
            "started": self._started,
            "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
            "subscribed_private_buses": len(self._subscribed_private_buses),
            "agent_cache_size": len(self._agent_state_cache),
            "mission_cache_size": len(self._mission_state_cache),
            "connection_manager": self.connection_manager.get_stats()
        }

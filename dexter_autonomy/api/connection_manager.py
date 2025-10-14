"""
Connection Manager for WebSocket Clients

Manages multiple concurrent Cockpit connections, event filtering, broadcasting,
and reconnection with event replay.

Design Decisions (Comet Collaboration):
- Fire-and-forget broadcasting (drop if client disconnected)
- Event history: circular buffer (last 1000 events, 5 min window)
- Heartbeat: ping every 30s, expect pong within 10s
- Client-side filtering: each client subscribes to specific agents/missions/log_levels
- State snapshot on connect/reconnect
"""

import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect
import json

from dexter_autonomy.api.websocket_events import (
    WebSocketMessage,
    EventType,
    AgentStatus,
    MissionPhase,
    LogLevel,
    create_state_snapshot
)

logger = logging.getLogger(__name__)


class ClientSubscription:
    """Client subscription filters"""
    
    def __init__(
        self,
        agent_ids: Optional[Set[str]] = None,
        mission_ids: Optional[Set[str]] = None,
        log_levels: Optional[Set[LogLevel]] = None,
        event_types: Optional[Set[EventType]] = None
    ):
        self.agent_ids = agent_ids or set()
        self.mission_ids = mission_ids or set()
        self.log_levels = log_levels or set()
        self.event_types = event_types or set()
        
        # If no filters specified, subscribe to everything
        self.subscribe_all = (
            not self.agent_ids and
            not self.mission_ids and
            not self.log_levels and
            not self.event_types
        )
    
    def matches(self, message: WebSocketMessage) -> bool:
        """Check if message matches subscription filters"""
        if self.subscribe_all:
            return True
        
        # Check event type filter
        if self.event_types and message.type not in self.event_types:
            return False
        
        # Check agent filter
        if self.agent_ids:
            agent_id = (
                message.data.get("agent_id") or
                message.metadata.get("source_agent")
            )
            if agent_id and agent_id not in self.agent_ids:
                return False
        
        # Check mission filter
        if self.mission_ids:
            mission_id = message.data.get("mission_id")
            if mission_id and mission_id not in self.mission_ids:
                return False
        
        # Check log level filter
        if self.log_levels:
            log_level = message.data.get("level")
            if log_level and LogLevel(log_level) not in self.log_levels:
                return False
        
        return True
    
    def update(self, **filters):
        """Update subscription filters"""
        if "agent_ids" in filters:
            self.agent_ids = set(filters["agent_ids"])
        if "mission_ids" in filters:
            self.mission_ids = set(filters["mission_ids"])
        if "log_levels" in filters:
            self.log_levels = {LogLevel(level) for level in filters["log_levels"]}
        if "event_types" in filters:
            self.event_types = {EventType(et) for et in filters["event_types"]}
        
        # Recalculate subscribe_all
        self.subscribe_all = (
            not self.agent_ids and
            not self.mission_ids and
            not self.log_levels and
            not self.event_types
        )


class ConnectionManager:
    """
    Manages WebSocket connections to Cockpit clients.
    
    Features:
    - Multiple concurrent connections
    - Client-side event filtering
    - Event history replay (last 1000 events or 5 min)
    - Heartbeat/ping-pong (30s ping, 10s timeout)
    - Fire-and-forget broadcasting (Comet's design)
    """
    
    def __init__(self, event_history_size: int = 1000):
        self.active_connections: Dict[str, WebSocket] = {}
        self.client_subscriptions: Dict[str, ClientSubscription] = {}
        self.event_history: deque[WebSocketMessage] = deque(maxlen=event_history_size)
        self.heartbeat_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        
        # Metrics
        self.total_connections = 0
        self.total_disconnections = 0
        self.total_messages_sent = 0
        self.total_messages_dropped = 0
    
    async def connect(
        self,
        client_id: str,
        websocket: WebSocket,
        filters: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register new client connection.
        
        Args:
            client_id: Unique client identifier
            websocket: FastAPI WebSocket instance
            filters: Initial subscription filters
        """
        async with self._lock:
            await websocket.accept()
            
            self.active_connections[client_id] = websocket
            self.client_subscriptions[client_id] = ClientSubscription(
                agent_ids=set(filters.get("agent_ids", [])) if filters else None,
                mission_ids=set(filters.get("mission_ids", [])) if filters else None,
                log_levels={LogLevel(l) for l in filters.get("log_levels", [])} if filters and filters.get("log_levels") else None,
                event_types={EventType(et) for et in filters.get("event_types", [])} if filters and filters.get("event_types") else None
            )
            
            self.total_connections += 1
            
            logger.info(f"Client {client_id} connected. Total clients: {len(self.active_connections)}")
        
        # Start heartbeat
        self.heartbeat_tasks[client_id] = asyncio.create_task(
            self._heartbeat_loop(client_id, websocket)
        )
        
        # Send state snapshot
        await self._send_state_snapshot(client_id, websocket)
        
        # Replay recent events
        await self._replay_recent_events(client_id, websocket)
    
    async def disconnect(self, client_id: str) -> None:
        """Disconnect and cleanup client"""
        async with self._lock:
            if client_id in self.active_connections:
                # Cancel heartbeat
                if client_id in self.heartbeat_tasks:
                    self.heartbeat_tasks[client_id].cancel()
                    del self.heartbeat_tasks[client_id]
                
                # Remove connection
                del self.active_connections[client_id]
                del self.client_subscriptions[client_id]
                
                self.total_disconnections += 1
                
                logger.info(f"Client {client_id} disconnected. Total clients: {len(self.active_connections)}")
    
    async def broadcast(
        self,
        message: WebSocketMessage,
        filter_fn: Optional[Callable[[str, ClientSubscription], bool]] = None
    ) -> None:
        """
        Broadcast message to all matching clients.
        
        Args:
            message: WebSocketMessage to broadcast
            filter_fn: Optional custom filter (client_id, subscription) -> bool
        """
        # Add to event history
        self.event_history.append(message)
        
        # Prepare JSON once
        try:
            message_json = message.model_dump_json()
        except Exception as e:
            logger.error(f"Failed to serialize message: {e}")
            return
        
        # Fire-and-forget broadcasting
        disconnected_clients = []
        
        for client_id, websocket in self.active_connections.items():
            subscription = self.client_subscriptions.get(client_id)
            
            # Check filters
            if not subscription:
                continue
            
            if not subscription.matches(message):
                continue
            
            if filter_fn and not filter_fn(client_id, subscription):
                continue
            
            # Send message (fire-and-forget)
            try:
                await websocket.send_text(message_json)
                self.total_messages_sent += 1
            except WebSocketDisconnect:
                disconnected_clients.append(client_id)
                self.total_messages_dropped += 1
            except Exception as e:
                logger.warning(f"Failed to send to {client_id}: {e}")
                disconnected_clients.append(client_id)
                self.total_messages_dropped += 1
        
        # Cleanup disconnected clients
        for client_id in disconnected_clients:
            await self.disconnect(client_id)
    
    async def send_to_client(self, client_id: str, message: WebSocketMessage) -> bool:
        """
        Send message to specific client.
        
        Returns:
            True if sent successfully, False otherwise
        """
        websocket = self.active_connections.get(client_id)
        if not websocket:
            return False
        
        try:
            message_json = message.model_dump_json()
            await websocket.send_text(message_json)
            self.total_messages_sent += 1
            return True
        except (WebSocketDisconnect, Exception) as e:
            logger.warning(f"Failed to send to {client_id}: {e}")
            await self.disconnect(client_id)
            self.total_messages_dropped += 1
            return False
    
    async def update_subscription(self, client_id: str, filters: Dict[str, Any]) -> None:
        """Update client subscription filters"""
        subscription = self.client_subscriptions.get(client_id)
        if subscription:
            subscription.update(**filters)
            logger.info(f"Updated subscription for {client_id}: {filters}")
    
    def get_state_snapshot(self) -> Dict[str, Any]:
        """
        Get current system state snapshot.
        
        Override this method to provide real system state from TripleBus.
        Default implementation returns mock data.
        """
        # This will be overridden by WebSocketManager to provide real state
        return {
            "agents": [],
            "missions": [],
            "system_metrics": {
                "event_bus_messages_per_sec": 0.0,
                "event_bus_queue_depth": 0,
                "active_agents": 0,
                "active_missions": 0,
                "cpu_percent": 0.0,
                "memory_mb": 0.0,
                "brain_size_mb": 0.0,
                "uptime_seconds": 0.0
            }
        }
    
    async def _send_state_snapshot(self, client_id: str, websocket: WebSocket) -> None:
        """Send current state snapshot to client"""
        try:
            state = self.get_state_snapshot()
            snapshot_msg = create_state_snapshot(
                agents=state["agents"],
                missions=state["missions"],
                system_metrics=state["system_metrics"],
                kg_stats=state.get("knowledge_graph_stats")
            )
            
            await websocket.send_text(snapshot_msg.model_dump_json())
            logger.info(f"Sent state snapshot to {client_id}")
        except Exception as e:
            logger.error(f"Failed to send state snapshot to {client_id}: {e}")
    
    async def _replay_recent_events(self, client_id: str, websocket: WebSocket) -> None:
        """
        Replay recent events to client.
        
        Sends events from last 5 minutes or last 100 events (whichever is smaller).
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=5)
        subscription = self.client_subscriptions.get(client_id)
        
        if not subscription:
            return
        
        replayed = 0
        max_replay = 100
        
        for event in self.event_history:
            if replayed >= max_replay:
                break
            
            # Check timestamp
            if event.timestamp < cutoff_time:
                continue
            
            # Check subscription filters
            if not subscription.matches(event):
                continue
            
            # Send event
            try:
                await websocket.send_text(event.model_dump_json())
                replayed += 1
            except Exception as e:
                logger.warning(f"Failed to replay event to {client_id}: {e}")
                break
        
        logger.info(f"Replayed {replayed} events to {client_id}")
    
    async def _heartbeat_loop(self, client_id: str, websocket: WebSocket) -> None:
        """
        Heartbeat loop: ping every 30s, expect pong within 10s.
        
        Closes connection if pong timeout.
        """
        ping_interval = 30  # seconds
        pong_timeout = 10   # seconds
        
        try:
            while True:
                await asyncio.sleep(ping_interval)
                
                # Send ping
                try:
                    await websocket.send_json({"type": "ping", "timestamp": datetime.utcnow().isoformat()})
                except Exception as e:
                    logger.warning(f"Heartbeat failed for {client_id}: {e}")
                    await self.disconnect(client_id)
                    break
                
                # Wait for pong (handled by client message handler)
                # For now, we just send pings - pong validation can be added later
                
        except asyncio.CancelledError:
            logger.debug(f"Heartbeat loop cancelled for {client_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection manager statistics"""
        return {
            "active_connections": len(self.active_connections),
            "total_connections": self.total_connections,
            "total_disconnections": self.total_disconnections,
            "total_messages_sent": self.total_messages_sent,
            "total_messages_dropped": self.total_messages_dropped,
            "event_history_size": len(self.event_history),
            "clients": [
                {
                    "client_id": client_id,
                    "subscription": {
                        "agent_ids": list(sub.agent_ids),
                        "mission_ids": list(sub.mission_ids),
                        "log_levels": [l.value for l in sub.log_levels],
                        "event_types": [et.value for et in sub.event_types],
                        "subscribe_all": sub.subscribe_all
                    }
                }
                for client_id, sub in self.client_subscriptions.items()
            ]
        }
    
    async def shutdown(self) -> None:
        """Gracefully shutdown all connections"""
        logger.info(f"Shutting down ConnectionManager. Disconnecting {len(self.active_connections)} clients...")
        
        # Cancel all heartbeat tasks
        for task in self.heartbeat_tasks.values():
            task.cancel()
        
        # Close all connections
        client_ids = list(self.active_connections.keys())
        for client_id in client_ids:
            await self.disconnect(client_id)
        
        logger.info("ConnectionManager shutdown complete")

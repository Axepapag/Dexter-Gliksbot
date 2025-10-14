"""
WebSocket Event Schema & Models

Defines Pydantic models for all WebSocket event types sent to Cockpit UI.
Provides transformation logic to convert TripleBus events to WebSocket format.

Design Decisions (Comet Collaboration):
- Aggregate high-frequency events (5s sampling for agent status)
- Real-time delivery for critical events (errors, mission completion)
- JSON format at 1Hz (default), MessagePack flag for high-throughput
- Fire-and-forget broadcasting (drop if client disconnected)
- Event replay buffer (last 1000 events, 5 min window)
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field
import base64
import json


# ==================== Enums ====================

class EventType(str, Enum):
    """WebSocket event types sent to Cockpit"""
    # State snapshots
    STATE_SNAPSHOT = "state.snapshot"
    
    # Agent events
    AGENT_STATUS = "agent.status"
    AGENT_HEARTBEAT = "agent.heartbeat"
    AGENT_ERROR = "agent.error"
    
    # Mission events
    MISSION_STARTED = "mission.started"
    MISSION_PROGRESS = "mission.progress"
    MISSION_COMPLETED = "mission.completed"
    MISSION_FAILED = "mission.failed"
    
    # Collaboration events
    COLLAB_STARTED = "collaboration.started"
    COLLAB_PROPOSAL = "collaboration.proposal"
    COLLAB_CONSENSUS = "collaboration.consensus"
    COLLAB_COMPLETE = "collaboration.complete"
    
    # Log events
    LOG_TRACE = "log.trace"
    LOG_INFO = "log.info"
    LOG_WARN = "log.warn"
    LOG_ERROR = "log.error"
    
    # Performance events
    PERF_METRIC = "performance.metric"
    PERF_SYSTEM = "performance.system"
    
    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    CONFIG_CHANGED = "config.changed"


class AgentStatus(str, Enum):
    """Agent operational status"""
    IDLE = "idle"
    ON_TASK = "on_task"
    COLLABORATING = "collaborating"
    ERROR = "error"
    OFFLINE = "offline"


class MissionPhase(str, Enum):
    """Mission lifecycle phases"""
    PLANNING = "planning"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"


class LogLevel(str, Enum):
    """Log severity levels"""
    TRACE = "TRACE"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


# ==================== Base Models ====================

class WebSocketMessage(BaseModel):
    """
    Base envelope for all WebSocket messages.
    
    All events sent to Cockpit use this structure for consistency.
    """
    type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ==================== Agent Events ====================

class AgentStatusEvent(BaseModel):
    """Agent status update (sent every 5s or on critical change)"""
    agent_id: str
    agent_name: str
    status: AgentStatus
    current_mission: Optional[str] = None
    uptime_seconds: float
    success_rate: float = Field(ge=0.0, le=1.0)
    actions_completed: int = Field(ge=0)
    last_action_timestamp: Optional[datetime] = None
    metrics: Dict[str, float] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AgentHeartbeatEvent(BaseModel):
    """Lightweight heartbeat (sent every 30s)"""
    agent_id: str
    status: AgentStatus
    uptime_seconds: float


class AgentErrorEvent(BaseModel):
    """Agent error (sent immediately)"""
    agent_id: str
    agent_name: str
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    recovery_attempted: bool = False
    mission_id: Optional[str] = None


# ==================== Mission Events ====================

class MissionUpdateEvent(BaseModel):
    """Mission progress update"""
    mission_id: str
    mission_name: str
    phase: MissionPhase
    progress: float = Field(ge=0.0, le=1.0)
    agents_assigned: List[str]
    started_at: datetime
    estimated_completion: Optional[datetime] = None
    last_action: Optional[str] = None
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class MissionStartedEvent(BaseModel):
    """Mission started (critical event)"""
    mission_id: str
    mission_name: str
    description: str
    agents_assigned: List[str]
    started_by: str  # user or agent_id
    priority: Literal["low", "medium", "high", "critical"] = "medium"


class MissionCompletedEvent(BaseModel):
    """Mission completed (critical event)"""
    mission_id: str
    mission_name: str
    success: bool
    duration_seconds: float
    actions_completed: int
    result_summary: str
    artifacts: List[str] = Field(default_factory=list)  # File paths, URLs, etc.


# ==================== Collaboration Events ====================

class CollaborationEvent(BaseModel):
    """Collaboration session update"""
    collab_id: str
    phase: str  # "proposing", "refining", "voting", "consensus"
    participants: List[str]  # agent_ids
    proposals: List[Dict[str, Any]] = Field(default_factory=list)
    consensus_reached: bool = False
    winning_proposal: Optional[Dict[str, Any]] = None


# ==================== Log Events ====================

class LogEntryEvent(BaseModel):
    """Structured log entry"""
    level: LogLevel
    message: str
    agent_id: Optional[str] = None
    mission_id: Optional[str] = None
    correlation_id: Optional[str] = None
    bus: Literal["MAIN", "COLLAB", "PRIVATE"] = "MAIN"
    topic: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# ==================== Performance Events ====================

class PerformanceMetricEvent(BaseModel):
    """Single performance metric"""
    metric_name: str
    value: float
    unit: str  # "seconds", "count", "bytes", "percent"
    agent_id: Optional[str] = None
    mission_id: Optional[str] = None


class SystemPerformanceEvent(BaseModel):
    """Aggregated system metrics (sent every 1s)"""
    event_bus_messages_per_sec: float
    event_bus_queue_depth: int
    active_agents: int
    active_missions: int
    cpu_percent: float
    memory_mb: float
    brain_size_mb: float
    uptime_seconds: float


# ==================== System Events ====================

class SystemStateSnapshot(BaseModel):
    """Complete system state (sent on connect/reconnect)"""
    agents: List[AgentStatusEvent]
    missions: List[MissionUpdateEvent]
    system_metrics: SystemPerformanceEvent
    knowledge_graph_stats: Optional[Dict[str, int]] = None  # entity_count, relation_count, etc.


class ConfigChangedEvent(BaseModel):
    """Configuration file changed (FS watcher trigger)"""
    config_file: str
    changed_keys: List[str]
    reload_required: bool = False


# ==================== Transformation Logic ====================

class TripleBusTransformer:
    """
    Transforms TripleBus events to WebSocket events.
    
    Handles aggregation, sampling, and format conversion.
    """
    
    def __init__(self):
        self._last_agent_status_send: Dict[str, datetime] = {}
        self.agent_status_interval_seconds = 5.0  # Comet's design: 5s aggregation
    
    def should_send_agent_status(self, agent_id: str) -> bool:
        """Check if agent status should be sent (5s throttle)"""
        now = datetime.utcnow()
        last_send = self._last_agent_status_send.get(agent_id)
        
        if last_send is None:
            self._last_agent_status_send[agent_id] = now
            return True
        
        if (now - last_send).total_seconds() >= self.agent_status_interval_seconds:
            self._last_agent_status_send[agent_id] = now
            return True
        
        return False
    
    def triplebus_to_websocket(
        self,
        bus: Literal["MAIN", "COLLAB", "PRIVATE"],
        topic: str,
        event_data: Dict[str, Any],
        force_send: bool = False
    ) -> Optional[WebSocketMessage]:
        """
        Convert TripleBus event to WebSocket message.
        
        Args:
            bus: Which bus the event came from
            topic: TripleBus topic (e.g., "TRACE", "PROPOSAL")
            event_data: Raw event data from TripleBus
            force_send: Override aggregation (for critical events)
        
        Returns:
            WebSocketMessage or None (if throttled)
        """
        # Detect event type from topic and data
        event_type = self._detect_event_type(bus, topic, event_data)
        
        if event_type is None:
            return None  # Ignore this event
        
        # Handle aggregation for high-frequency events
        if event_type == EventType.AGENT_STATUS and not force_send:
            agent_id = event_data.get("agent_id")
            if agent_id and not self.should_send_agent_status(agent_id):
                return None  # Throttled
        
        # Transform to WebSocket format
        ws_data = self._transform_data(event_type, event_data)
        
        return WebSocketMessage(
            type=event_type,
            data=ws_data,
            metadata={
                "bus": bus,
                "topic": topic,
                "correlation_id": event_data.get("correlation_id"),
                "source_agent": event_data.get("agent_id") or event_data.get("from")
            }
        )
    
    def _detect_event_type(
        self,
        bus: str,
        topic: str,
        event_data: Dict[str, Any]
    ) -> Optional[EventType]:
        """Detect WebSocket event type from TripleBus event"""
        # MAIN bus events
        if bus == "MAIN":
            if topic == "ERROR":
                return EventType.LOG_ERROR
            elif topic == "TRACE":
                return EventType.LOG_TRACE
            elif topic == "EFFECT":
                # Could be mission progress or agent status
                # Check for agent_id first (more specific)
                if "agent_id" in event_data and "status" in event_data:
                    return EventType.AGENT_STATUS
                elif "mission_id" in event_data and "progress" in event_data:
                    return EventType.MISSION_PROGRESS
                elif "agent_id" in event_data:
                    return EventType.AGENT_STATUS
        
        # COLLAB bus events
        elif bus == "COLLAB":
            if topic == "COLLABORATION_STARTED":
                return EventType.COLLAB_STARTED
            elif topic == "PROPOSAL":
                return EventType.COLLAB_PROPOSAL
            elif topic == "CONSENSUS":
                return EventType.COLLAB_CONSENSUS
            elif topic == "COLLABORATION_COMPLETE":
                return EventType.COLLAB_COMPLETE
        
        # PRIVATE bus events (mission-specific)
        elif bus == "PRIVATE":
            if topic == "TASK_ASSIGNMENT":
                return EventType.MISSION_STARTED
            elif topic == "PROGRESS":
                return EventType.MISSION_PROGRESS
            elif topic == "TASK_COMPLETE":
                if event_data.get("status") == "success":
                    return EventType.MISSION_COMPLETED
                else:
                    return EventType.MISSION_FAILED
        
        return None  # Ignore unknown events
    
    def _transform_data(
        self,
        event_type: EventType,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transform TripleBus data to WebSocket format"""
        # Pass through for now - can add field mapping logic here
        return event_data
    
    def encode_binary_data(self, data: bytes, threshold_kb: int = 100) -> Union[str, Dict[str, str]]:
        """
        Encode binary data for WebSocket transmission.
        
        Args:
            data: Raw binary data
            threshold_kb: Size threshold for URL reference (Comet's design: 100KB)
        
        Returns:
            Base64 string (if <100KB) or {"url": "..."} reference (if >=100KB)
        """
        size_kb = len(data) / 1024
        
        if size_kb < threshold_kb:
            # Small data: base64 encode in JSON
            return base64.b64encode(data).decode('utf-8')
        else:
            # Large data: save to temp file, return URL
            # TODO: Implement file storage and URL generation
            return {"url": f"/tmp/ws_binary_{datetime.utcnow().timestamp()}.bin", "size_kb": size_kb}


# ==================== Utility Functions ====================

def create_state_snapshot(
    agents: List[Dict[str, Any]],
    missions: List[Dict[str, Any]],
    system_metrics: Dict[str, Any],
    kg_stats: Optional[Dict[str, int]] = None
) -> WebSocketMessage:
    """
    Create a complete state snapshot message.
    
    Sent on Cockpit connect/reconnect to sync current state.
    """
    snapshot = SystemStateSnapshot(
        agents=[AgentStatusEvent(**a) for a in agents],
        missions=[MissionUpdateEvent(**m) for m in missions],
        system_metrics=SystemPerformanceEvent(**system_metrics),
        knowledge_graph_stats=kg_stats
    )
    
    return WebSocketMessage(
        type=EventType.STATE_SNAPSHOT,
        data=snapshot.dict()
    )


def create_error_event(
    agent_id: str,
    agent_name: str,
    error: Exception,
    mission_id: Optional[str] = None
) -> WebSocketMessage:
    """Create agent error event (critical - send immediately)"""
    error_event = AgentErrorEvent(
        agent_id=agent_id,
        agent_name=agent_name,
        error_type=type(error).__name__,
        error_message=str(error),
        stack_trace=None,  # Can add traceback.format_exc() if needed
        mission_id=mission_id
    )
    
    return WebSocketMessage(
        type=EventType.AGENT_ERROR,
        data=error_event.dict(),
        metadata={"critical": True}
    )


def create_log_event(
    level: LogLevel,
    message: str,
    agent_id: Optional[str] = None,
    mission_id: Optional[str] = None,
    bus: Literal["MAIN", "COLLAB", "PRIVATE"] = "MAIN",
    **details
) -> WebSocketMessage:
    """Create structured log event"""
    log_event = LogEntryEvent(
        level=level,
        message=message,
        agent_id=agent_id,
        mission_id=mission_id,
        bus=bus,
        details=details if details else None
    )
    
    event_type_map = {
        LogLevel.TRACE: EventType.LOG_TRACE,
        LogLevel.INFO: EventType.LOG_INFO,
        LogLevel.WARN: EventType.LOG_WARN,
        LogLevel.ERROR: EventType.LOG_ERROR
    }
    
    return WebSocketMessage(
        type=event_type_map[level],
        data=log_event.dict()
    )

"""
Time Machine - Temporal State Management for Dexter-Gliksbot

Provides comprehensive state snapshot and rollback capabilities:
- Creating and managing state snapshots at critical points
- Enabling rollback to previous stable states
- Maintaining comprehensive timeline event logs
- Supporting state inspection and debugging

Architecture:
    BSM (observes all) → TimeMachine (captures snapshots) → StateStore (persists)
    
Features:
- Automatic snapshot creation at configurable intervals
- Manual snapshot triggers for critical operations
- Efficient snapshot storage with compression
- Snapshot retention policies and cleanup
- One-click rollback with validation
- Preview mode to inspect state before rollback
"""
from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import sqlite3

logger = logging.getLogger(__name__)


class EventSeverity(str, Enum):
    """Event severity levels for timeline logging"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventCategory(str, Enum):
    """Event categories for filtering and correlation"""
    STATE_CHANGE = "state_change"
    AGENT_ACTION = "agent_action"
    USER_INPUT = "user_input"
    SYSTEM_EVENT = "system_event"
    ERROR_EVENT = "error_event"
    RECOVERY = "recovery"
    COLLABORATION = "collaboration"
    SNAPSHOT = "snapshot"
    ROLLBACK = "rollback"


@dataclass
class TimelineEvent:
    """
    Structured timeline event with full metadata.
    
    Every state transition, action, and system event is logged as a TimelineEvent
    for complete observability and debugging.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    severity: EventSeverity = EventSeverity.INFO
    category: EventCategory = EventCategory.SYSTEM_EVENT
    
    # Event details
    event_type: str = ""  # Specific event type (e.g., "intent_published", "agent_started")
    description: str = ""
    
    # Context
    bus: Optional[str] = None  # main, collab, private
    agent_id: Optional[str] = None
    task_root: Optional[str] = None
    
    # Correlation
    correlation_id: Optional[str] = None  # Link related events
    parent_event_id: Optional[str] = None  # For event hierarchies
    
    # Data
    payload: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TimelineEvent:
        """Create from dictionary"""
        # Convert string enums back to Enum types
        if isinstance(data.get('severity'), str):
            data['severity'] = EventSeverity(data['severity'])
        if isinstance(data.get('category'), str):
            data['category'] = EventCategory(data['category'])
        return cls(**data)


@dataclass
class StateSnapshot:
    """
    Complete state snapshot at a point in time.
    
    Captures:
    - All agent states
    - Memory state (STM/LTM summary)
    - Event bus state
    - System configuration
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    
    # Snapshot metadata
    name: str = ""  # User-friendly name
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    # Snapshot trigger
    trigger: str = "manual"  # manual, automatic, error, critical_event
    trigger_event_id: Optional[str] = None
    
    # State data
    state_data: Dict[str, Any] = field(default_factory=dict)
    
    # Compression and integrity
    compressed: bool = False
    checksum: str = ""
    size_bytes: int = 0
    
    # Lifecycle
    retained_until: Optional[float] = None  # None = retain forever
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StateSnapshot:
        """Create from dictionary"""
        return cls(**data)
    
    def calculate_checksum(self) -> str:
        """Calculate SHA256 checksum of state data"""
        data_str = json.dumps(self.state_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()


@dataclass
class RollbackPreview:
    """
    Preview of state changes before rollback.
    
    Shows what will change if rollback is executed.
    """
    snapshot_id: str
    snapshot_name: str
    snapshot_timestamp: float
    
    # Changes preview
    agents_affected: List[str]
    state_differences: Dict[str, Any]
    risk_level: str  # low, medium, high
    warnings: List[str]
    
    # Validation
    can_rollback: bool
    validation_errors: List[str]


class TimelineStore:
    """
    Storage layer for timeline events.
    
    Uses SQLite with FTS5 for fast event searching.
    """
    
    def __init__(self, db_path: str = "./data/timeline.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.db = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_schema()
        
        logger.info(f"TimelineStore initialized at {db_path}")
    
    def _init_schema(self):
        """Initialize database schema"""
        c = self.db.cursor()
        
        # Enable WAL mode for better concurrent access
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute("PRAGMA synchronous=NORMAL;")
        
        # Timeline events table
        c.execute("""
            CREATE TABLE IF NOT EXISTS timeline_events (
                id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                severity TEXT NOT NULL,
                category TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT,
                bus TEXT,
                agent_id TEXT,
                task_root TEXT,
                correlation_id TEXT,
                parent_event_id TEXT,
                payload TEXT,
                tags TEXT,
                metadata TEXT
            )
        """)
        
        # Indexes for fast querying
        c.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON timeline_events(timestamp DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_severity ON timeline_events(severity)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_category ON timeline_events(category)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_agent_id ON timeline_events(agent_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_correlation ON timeline_events(correlation_id)")
        
        # Full-text search
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS timeline_events_fts 
            USING fts5(
                event_type, 
                description,
                content='timeline_events',
                content_rowid='rowid'
            )
        """)
        
        self.db.commit()
        logger.info("Timeline store schema initialized")
    
    def add_event(self, event: TimelineEvent) -> str:
        """Add event to timeline"""
        c = self.db.cursor()
        
        c.execute("""
            INSERT INTO timeline_events 
            (id, timestamp, severity, category, event_type, description,
             bus, agent_id, task_root, correlation_id, parent_event_id,
             payload, tags, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.id,
            event.timestamp,
            event.severity.value,
            event.category.value,
            event.event_type,
            event.description,
            event.bus,
            event.agent_id,
            event.task_root,
            event.correlation_id,
            event.parent_event_id,
            json.dumps(event.payload),
            json.dumps(event.tags),
            json.dumps(event.metadata),
        ))
        
        # Add to FTS
        rowid = c.lastrowid
        c.execute("""
            INSERT INTO timeline_events_fts(rowid, event_type, description)
            VALUES (?, ?, ?)
        """, (rowid, event.event_type, event.description))
        
        self.db.commit()
        return event.id
    
    def get_event(self, event_id: str) -> Optional[TimelineEvent]:
        """Get event by ID"""
        c = self.db.cursor()
        c.execute("SELECT * FROM timeline_events WHERE id = ?", (event_id,))
        row = c.fetchone()
        
        if not row:
            return None
        
        return self._row_to_event(row)
    
    def query_events(
        self,
        severity: Optional[EventSeverity] = None,
        category: Optional[EventCategory] = None,
        agent_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        correlation_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TimelineEvent]:
        """Query events with filtering"""
        conditions = []
        params = []
        
        if severity:
            conditions.append("severity = ?")
            params.append(severity.value)
        
        if category:
            conditions.append("category = ?")
            params.append(category.value)
        
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        
        if correlation_id:
            conditions.append("correlation_id = ?")
            params.append(correlation_id)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        c = self.db.cursor()
        c.execute(f"""
            SELECT * FROM timeline_events
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """, (*params, limit, offset))
        
        return [self._row_to_event(row) for row in c.fetchall()]
    
    def search_events(self, query: str, limit: int = 100) -> List[TimelineEvent]:
        """Full-text search of events"""
        c = self.db.cursor()
        c.execute("""
            SELECT te.* FROM timeline_events te
            JOIN timeline_events_fts fts ON te.rowid = fts.rowid
            WHERE timeline_events_fts MATCH ?
            ORDER BY te.timestamp DESC
            LIMIT ?
        """, (query, limit))
        
        return [self._row_to_event(row) for row in c.fetchall()]
    
    def get_event_count(
        self,
        severity: Optional[EventSeverity] = None,
        category: Optional[EventCategory] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> int:
        """Get count of events matching criteria"""
        conditions = []
        params = []
        
        if severity:
            conditions.append("severity = ?")
            params.append(severity.value)
        
        if category:
            conditions.append("category = ?")
            params.append(category.value)
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        c = self.db.cursor()
        c.execute(f"SELECT COUNT(*) FROM timeline_events WHERE {where_clause}", params)
        return c.fetchone()[0]
    
    def _row_to_event(self, row) -> TimelineEvent:
        """Convert database row to TimelineEvent"""
        return TimelineEvent(
            id=row[0],
            timestamp=row[1],
            severity=EventSeverity(row[2]),
            category=EventCategory(row[3]),
            event_type=row[4],
            description=row[5] or "",
            bus=row[6],
            agent_id=row[7],
            task_root=row[8],
            correlation_id=row[9],
            parent_event_id=row[10],
            payload=json.loads(row[11]) if row[11] else {},
            tags=json.loads(row[12]) if row[12] else [],
            metadata=json.loads(row[13]) if row[13] else {},
        )


class SnapshotStore:
    """
    Storage layer for state snapshots.
    
    Uses SQLite for metadata and separate files for compressed snapshot data.
    """
    
    def __init__(self, db_path: str = "./data/snapshots.db", data_dir: str = "./data/snapshots"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.db = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._init_schema()
        
        logger.info(f"SnapshotStore initialized at {db_path}")
    
    def _init_schema(self):
        """Initialize database schema"""
        c = self.db.cursor()
        
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute("PRAGMA synchronous=NORMAL;")
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                tags TEXT,
                trigger TEXT NOT NULL,
                trigger_event_id TEXT,
                data_file TEXT NOT NULL,
                compressed INTEGER NOT NULL,
                checksum TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                retained_until REAL
            )
        """)
        
        c.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_timestamp ON snapshots(timestamp DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_trigger ON snapshots(trigger)")
        
        self.db.commit()
        logger.info("Snapshot store schema initialized")
    
    def save_snapshot(self, snapshot: StateSnapshot) -> str:
        """Save snapshot to storage"""
        # Calculate checksum
        snapshot.checksum = snapshot.calculate_checksum()
        
        # Serialize state data
        state_json = json.dumps(snapshot.state_data, indent=2)
        
        # Compress if enabled
        if snapshot.compressed:
            data_bytes = gzip.compress(state_json.encode())
            ext = ".json.gz"
        else:
            data_bytes = state_json.encode()
            ext = ".json"
        
        snapshot.size_bytes = len(data_bytes)
        
        # Save data file
        data_file = self.data_dir / f"{snapshot.id}{ext}"
        data_file.write_bytes(data_bytes)
        
        # Save metadata to database
        c = self.db.cursor()
        c.execute("""
            INSERT INTO snapshots
            (id, timestamp, name, description, tags, trigger, trigger_event_id,
             data_file, compressed, checksum, size_bytes, retained_until)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot.id,
            snapshot.timestamp,
            snapshot.name,
            snapshot.description,
            json.dumps(snapshot.tags),
            snapshot.trigger,
            snapshot.trigger_event_id,
            str(data_file),
            1 if snapshot.compressed else 0,
            snapshot.checksum,
            snapshot.size_bytes,
            snapshot.retained_until,
        ))
        
        self.db.commit()
        logger.info(f"Snapshot {snapshot.id} saved ({snapshot.size_bytes} bytes)")
        return snapshot.id
    
    def load_snapshot(self, snapshot_id: str) -> Optional[StateSnapshot]:
        """Load snapshot from storage"""
        c = self.db.cursor()
        c.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,))
        row = c.fetchone()
        
        if not row:
            return None
        
        # Load metadata
        snapshot = StateSnapshot(
            id=row[0],
            timestamp=row[1],
            name=row[2],
            description=row[3] or "",
            tags=json.loads(row[4]) if row[4] else [],
            trigger=row[5],
            trigger_event_id=row[6],
            compressed=bool(row[8]),
            checksum=row[9],
            size_bytes=row[10],
            retained_until=row[11],
        )
        
        # Load state data
        data_file = Path(row[7])
        if not data_file.exists():
            logger.error(f"Snapshot data file not found: {data_file}")
            return None
        
        data_bytes = data_file.read_bytes()
        
        if snapshot.compressed:
            state_json = gzip.decompress(data_bytes).decode()
        else:
            state_json = data_bytes.decode()
        
        snapshot.state_data = json.loads(state_json)
        
        # Verify checksum
        calculated_checksum = snapshot.calculate_checksum()
        if calculated_checksum != snapshot.checksum:
            logger.error(f"Snapshot checksum mismatch: {snapshot_id}")
            return None
        
        return snapshot
    
    def list_snapshots(
        self,
        limit: int = 100,
        offset: int = 0,
        trigger: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List snapshots (metadata only)"""
        conditions = []
        params = []
        
        if trigger:
            conditions.append("trigger = ?")
            params.append(trigger)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        c = self.db.cursor()
        c.execute(f"""
            SELECT id, timestamp, name, description, tags, trigger, size_bytes, retained_until
            FROM snapshots
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """, (*params, limit, offset))
        
        snapshots = []
        for row in c.fetchall():
            snapshots.append({
                "id": row[0],
                "timestamp": row[1],
                "name": row[2],
                "description": row[3] or "",
                "tags": json.loads(row[4]) if row[4] else [],
                "trigger": row[5],
                "size_bytes": row[6],
                "retained_until": row[7],
            })
        
        return snapshots
    
    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete snapshot"""
        c = self.db.cursor()
        c.execute("SELECT data_file FROM snapshots WHERE id = ?", (snapshot_id,))
        row = c.fetchone()
        
        if not row:
            return False
        
        # Delete data file
        data_file = Path(row[0])
        if data_file.exists():
            data_file.unlink()
        
        # Delete metadata
        c.execute("DELETE FROM snapshots WHERE id = ?", (snapshot_id,))
        self.db.commit()
        
        logger.info(f"Snapshot {snapshot_id} deleted")
        return True
    
    def cleanup_expired(self) -> int:
        """Delete expired snapshots based on retention policy"""
        now = time.time()
        
        c = self.db.cursor()
        c.execute("""
            SELECT id, data_file FROM snapshots
            WHERE retained_until IS NOT NULL AND retained_until < ?
        """, (now,))
        
        expired = c.fetchall()
        count = 0
        
        for snapshot_id, data_file in expired:
            # Delete data file
            data_path = Path(data_file)
            if data_path.exists():
                data_path.unlink()
            
            # Delete metadata
            c.execute("DELETE FROM snapshots WHERE id = ?", (snapshot_id,))
            count += 1
        
        self.db.commit()
        
        if count > 0:
            logger.info(f"Cleaned up {count} expired snapshots")
        
        return count


class TimeMachine:
    """
    Time Machine - Complete temporal state management system.
    
    Integrates with BSM to provide:
    - Automatic and manual state snapshots
    - Timeline event logging with full observability
    - Rollback capabilities with preview and validation
    - Error recovery integration
    
    Architecture:
        BSM → observes → TimeMachine.log_event()
        System state → TimeMachine.create_snapshot()
        Rollback request → TimeMachine.rollback_to_snapshot()
    """
    
    def __init__(
        self,
        timeline_db: str = "./data/timeline.db",
        snapshot_db: str = "./data/snapshots.db",
        snapshot_dir: str = "./data/snapshots",
        auto_snapshot_interval: float = 300.0,  # 5 minutes
        retention_days: int = 30,
        enable_compression: bool = True,
    ):
        self.timeline = TimelineStore(timeline_db)
        self.snapshots = SnapshotStore(snapshot_db, snapshot_dir)
        
        self.auto_snapshot_interval = auto_snapshot_interval
        self.retention_days = retention_days
        self.enable_compression = enable_compression
        
        self._auto_snapshot_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._started = False
        
        logger.info("TimeMachine initialized")
    
    async def start(self):
        """Start Time Machine background tasks"""
        if self._started:
            return
        
        # Start automatic snapshot creation
        self._auto_snapshot_task = asyncio.create_task(self._auto_snapshot_loop())
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self._started = True
        logger.info("TimeMachine started")
    
    async def stop(self):
        """Stop Time Machine background tasks"""
        if not self._started:
            return
        
        if self._auto_snapshot_task:
            self._auto_snapshot_task.cancel()
            try:
                await self._auto_snapshot_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self._started = False
        logger.info("TimeMachine stopped")
    
    async def log_event(self, event: TimelineEvent) -> str:
        """
        Log an event to the timeline.
        
        Called by BSM or other system components to record events.
        """
        return await asyncio.to_thread(self.timeline.add_event, event)
    
    async def create_snapshot(
        self,
        state_data: Dict[str, Any],
        name: str = "",
        description: str = "",
        trigger: str = "manual",
        trigger_event_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        Create a state snapshot.
        
        Args:
            state_data: Complete system state to snapshot
            name: Human-readable name
            description: Description of snapshot
            trigger: What triggered snapshot (manual, automatic, error, etc.)
            trigger_event_id: Associated timeline event ID
            tags: Tags for categorization
        
        Returns:
            Snapshot ID
        """
        snapshot = StateSnapshot(
            name=name or f"Snapshot {time.strftime('%Y-%m-%d %H:%M:%S')}",
            description=description,
            tags=tags or [],
            trigger=trigger,
            trigger_event_id=trigger_event_id,
            state_data=state_data,
            compressed=self.enable_compression,
            retained_until=time.time() + (self.retention_days * 86400),
        )
        
        snapshot_id = await asyncio.to_thread(self.snapshots.save_snapshot, snapshot)
        
        # Log snapshot creation event
        await self.log_event(TimelineEvent(
            severity=EventSeverity.INFO,
            category=EventCategory.SNAPSHOT,
            event_type="snapshot_created",
            description=f"Snapshot created: {name}",
            payload={
                "snapshot_id": snapshot_id,
                "trigger": trigger,
                "size_bytes": snapshot.size_bytes,
            },
        ))
        
        logger.info(f"Snapshot created: {snapshot_id} ({snapshot.size_bytes} bytes)")
        return snapshot_id
    
    async def get_snapshot(self, snapshot_id: str) -> Optional[StateSnapshot]:
        """Get snapshot by ID"""
        return await asyncio.to_thread(self.snapshots.load_snapshot, snapshot_id)
    
    async def list_snapshots(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List available snapshots"""
        return await asyncio.to_thread(self.snapshots.list_snapshots, limit, offset)
    
    async def preview_rollback(self, snapshot_id: str, current_state: Dict[str, Any]) -> RollbackPreview:
        """
        Preview rollback changes before execution.
        
        Shows what will change and validates safety.
        """
        snapshot = await self.get_snapshot(snapshot_id)
        if not snapshot:
            return RollbackPreview(
                snapshot_id=snapshot_id,
                snapshot_name="",
                snapshot_timestamp=0,
                agents_affected=[],
                state_differences={},
                risk_level="high",
                warnings=["Snapshot not found"],
                can_rollback=False,
                validation_errors=["Snapshot not found"],
            )
        
        # Calculate differences
        agents_affected = []
        state_differences = {}
        warnings = []
        
        # Compare agent states
        current_agents = current_state.get("agents", {})
        snapshot_agents = snapshot.state_data.get("agents", {})
        
        for agent_id in set(list(current_agents.keys()) + list(snapshot_agents.keys())):
            current = current_agents.get(agent_id)
            snapshot_val = snapshot_agents.get(agent_id)
            
            if current != snapshot_val:
                agents_affected.append(agent_id)
                state_differences[agent_id] = {
                    "current": current,
                    "snapshot": snapshot_val,
                }
        
        # Assess risk level
        risk_level = "low"
        if len(agents_affected) > 5:
            risk_level = "medium"
            warnings.append(f"{len(agents_affected)} agents will be affected")
        if len(agents_affected) > 10:
            risk_level = "high"
            warnings.append("Large number of agents affected - review carefully")
        
        # Calculate time delta
        time_delta = time.time() - snapshot.timestamp
        if time_delta > 3600:  # More than 1 hour
            warnings.append(f"Snapshot is {time_delta / 3600:.1f} hours old")
        
        return RollbackPreview(
            snapshot_id=snapshot_id,
            snapshot_name=snapshot.name,
            snapshot_timestamp=snapshot.timestamp,
            agents_affected=agents_affected,
            state_differences=state_differences,
            risk_level=risk_level,
            warnings=warnings,
            can_rollback=True,
            validation_errors=[],
        )
    
    async def rollback_to_snapshot(
        self,
        snapshot_id: str,
        current_state: Dict[str, Any],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Rollback system to a previous snapshot.
        
        Args:
            snapshot_id: ID of snapshot to rollback to
            current_state: Current system state (for validation and preview)
            dry_run: If True, only preview changes without executing
        
        Returns:
            Result dictionary with status and details
        """
        # Get preview
        preview = await self.preview_rollback(snapshot_id, current_state)
        
        if not preview.can_rollback:
            return {
                "status": "error",
                "message": "Rollback validation failed",
                "errors": preview.validation_errors,
            }
        
        if dry_run:
            return {
                "status": "preview",
                "preview": {
                    "snapshot_id": preview.snapshot_id,
                    "snapshot_name": preview.snapshot_name,
                    "agents_affected": preview.agents_affected,
                    "risk_level": preview.risk_level,
                    "warnings": preview.warnings,
                },
            }
        
        # Load snapshot
        snapshot = await self.get_snapshot(snapshot_id)
        if not snapshot:
            return {
                "status": "error",
                "message": "Snapshot not found",
            }
        
        # Create backup of current state before rollback
        backup_id = await self.create_snapshot(
            state_data=current_state,
            name=f"Pre-rollback backup {time.strftime('%Y-%m-%d %H:%M:%S')}",
            description=f"Automatic backup before rollback to {snapshot.name}",
            trigger="pre_rollback_backup",
            tags=["automatic", "backup", "pre_rollback"],
        )
        
        # Log rollback event
        event_id = await self.log_event(TimelineEvent(
            severity=EventSeverity.WARNING,
            category=EventCategory.ROLLBACK,
            event_type="rollback_executed",
            description=f"Rollback to snapshot: {snapshot.name}",
            payload={
                "snapshot_id": snapshot_id,
                "backup_id": backup_id,
                "agents_affected": preview.agents_affected,
            },
        ))
        
        # TODO: Execute actual state restoration
        # This would involve:
        # 1. Stopping affected agents
        # 2. Restoring agent states from snapshot
        # 3. Restarting agents
        # 4. Verifying state consistency
        
        logger.info(f"Rollback executed: {snapshot_id} (backup: {backup_id})")
        
        return {
            "status": "success",
            "snapshot_id": snapshot_id,
            "backup_id": backup_id,
            "agents_affected": preview.agents_affected,
            "event_id": event_id,
        }
    
    async def query_events(
        self,
        severity: Optional[EventSeverity] = None,
        category: Optional[EventCategory] = None,
        agent_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
    ) -> List[TimelineEvent]:
        """Query timeline events"""
        return await asyncio.to_thread(
            self.timeline.query_events,
            severity=severity,
            category=category,
            agent_id=agent_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
    
    async def search_events(self, query: str, limit: int = 100) -> List[TimelineEvent]:
        """Full-text search of timeline events"""
        return await asyncio.to_thread(self.timeline.search_events, query, limit)
    
    async def get_event_statistics(self) -> Dict[str, Any]:
        """Get timeline statistics"""
        now = time.time()
        hour_ago = now - 3600
        day_ago = now - 86400
        
        total_events = await asyncio.to_thread(self.timeline.get_event_count)
        events_hour = await asyncio.to_thread(
            self.timeline.get_event_count, start_time=hour_ago
        )
        events_day = await asyncio.to_thread(
            self.timeline.get_event_count, start_time=day_ago
        )
        
        errors_hour = await asyncio.to_thread(
            self.timeline.get_event_count,
            severity=EventSeverity.ERROR,
            start_time=hour_ago,
        )
        
        critical_hour = await asyncio.to_thread(
            self.timeline.get_event_count,
            severity=EventSeverity.CRITICAL,
            start_time=hour_ago,
        )
        
        return {
            "total_events": total_events,
            "events_last_hour": events_hour,
            "events_last_day": events_day,
            "errors_last_hour": errors_hour,
            "critical_last_hour": critical_hour,
        }
    
    async def _auto_snapshot_loop(self):
        """Background task for automatic snapshot creation"""
        while True:
            try:
                await asyncio.sleep(self.auto_snapshot_interval)
                
                # TODO: Capture current system state
                # This would integrate with BSM to get current state
                current_state = {
                    "agents": {},
                    "memory_stats": {},
                    "bus_stats": {},
                }
                
                await self.create_snapshot(
                    state_data=current_state,
                    name=f"Auto snapshot {time.strftime('%Y-%m-%d %H:%M:%S')}",
                    description="Automatic periodic snapshot",
                    trigger="automatic",
                    tags=["automatic", "periodic"],
                )
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Auto snapshot failed: {e}")
    
    async def _cleanup_loop(self):
        """Background task for cleaning up expired snapshots"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await asyncio.to_thread(self.snapshots.cleanup_expired)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Cleanup failed: {e}")

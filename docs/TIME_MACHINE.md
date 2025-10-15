# Time Machine - Temporal State Management for Dexter-Gliksbot

## Overview

The **Time Machine** is a comprehensive temporal state management system that provides:
- **Timeline Event Logging**: Structured logging of all system events with full observability
- **State Snapshots**: Automatic and manual capture of complete system state
- **Rollback Capabilities**: Safe rollback to previous stable states with preview and validation
- **Event Search & Analysis**: Full-text search and querying of historical events
- **Retention Policies**: Automatic cleanup of expired snapshots

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ BSM (Omniscient Observer)                                    │
│ - Observes ALL buses (MAIN, COLLAB, PRIVATE)                │
│ - Logs every observation to Timeline                         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ Time Machine                                                 │
├─────────────────────────────────────────────────────────────┤
│ Timeline Event Store                                         │
│ - SQLite with FTS5 full-text search                         │
│ - Event categorization & severity                           │
│ - Correlation tracking                                       │
│                                                              │
│ Snapshot Store                                               │
│ - Compressed state snapshots                                 │
│ - SHA256 integrity validation                                │
│ - Retention policy enforcement                               │
│                                                              │
│ Rollback Engine                                              │
│ - Preview changes before execution                           │
│ - Automatic pre-rollback backup                              │
│ - Risk assessment & validation                               │
└─────────────────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ REST API & WebSocket                                         │
│ - Event logging & querying                                   │
│ - Snapshot management                                        │
│ - Rollback execution                                         │
│ - Real-time event streaming (planned)                        │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Timeline Event Logging

Every event in the system is logged as a structured `TimelineEvent` with:

```python
@dataclass
class TimelineEvent:
    id: str                      # Unique event ID
    timestamp: float             # Unix timestamp
    severity: EventSeverity      # DEBUG, INFO, WARNING, ERROR, CRITICAL
    category: EventCategory      # USER_INPUT, AGENT_ACTION, ERROR_EVENT, etc.
    event_type: str             # Specific event type
    description: str            # Human-readable description
    
    # Context
    bus: Optional[str]          # main, collab, private
    agent_id: Optional[str]     # Agent that generated event
    task_root: Optional[str]    # Task context
    
    # Correlation
    correlation_id: Optional[str]     # Link related events
    parent_event_id: Optional[str]    # Event hierarchies
    
    # Data
    payload: Dict[str, Any]     # Full event data
    tags: List[str]             # Event tags
    metadata: Dict[str, Any]    # Additional metadata
```

#### Event Severities

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational events
- **WARNING**: Warning events that may require attention
- **ERROR**: Error events that affected operations
- **CRITICAL**: Critical failures requiring immediate action

#### Event Categories

- **USER_INPUT**: User interactions
- **AGENT_ACTION**: Agent operations
- **STATE_CHANGE**: State transitions
- **SYSTEM_EVENT**: System-level events
- **ERROR_EVENT**: Error occurrences
- **RECOVERY**: Error recovery operations
- **COLLABORATION**: Multi-agent collaboration
- **SNAPSHOT**: Snapshot creation/deletion
- **ROLLBACK**: Rollback operations

### 2. State Snapshots

State snapshots capture complete system state at a point in time:

```python
@dataclass
class StateSnapshot:
    id: str                     # Unique snapshot ID
    timestamp: float            # Creation time
    name: str                   # User-friendly name
    description: str            # Description
    tags: List[str]             # Tags for categorization
    
    # Trigger information
    trigger: str                # manual, automatic, error, critical_event
    trigger_event_id: Optional[str]  # Associated timeline event
    
    # State data
    state_data: Dict[str, Any]  # Complete system state
    
    # Integrity
    compressed: bool            # GZIP compression
    checksum: str               # SHA256 checksum
    size_bytes: int             # Storage size
    
    # Retention
    retained_until: Optional[float]  # Expiration time
```

#### Snapshot Triggers

- **manual**: User-initiated snapshot
- **automatic**: Periodic automatic snapshot
- **error**: Created on critical error
- **critical_event**: Triggered by system event
- **pre_rollback_backup**: Backup before rollback

### 3. Rollback System

Rollback provides safe state restoration with:

1. **Preview Mode**: See what will change before executing
2. **Risk Assessment**: Automatic risk level calculation (low/medium/high)
3. **Validation**: Safety checks before rollback
4. **Automatic Backup**: Pre-rollback state backup
5. **Event Logging**: Full audit trail of rollback operation

```python
@dataclass
class RollbackPreview:
    snapshot_id: str
    snapshot_name: str
    snapshot_timestamp: float
    
    # Impact analysis
    agents_affected: List[str]
    state_differences: Dict[str, Any]
    risk_level: str             # low, medium, high
    warnings: List[str]
    
    # Validation
    can_rollback: bool
    validation_errors: List[str]
```

## Usage

### Initialize Time Machine

```python
from dexter_autonomy.brain.time_machine import TimeMachine

time_machine = TimeMachine(
    timeline_db="./data/timeline.db",
    snapshot_db="./data/snapshots.db",
    snapshot_dir="./data/snapshots",
    auto_snapshot_interval=300.0,  # 5 minutes
    retention_days=30,
    enable_compression=True,
)

await time_machine.start()
```

### Log Events

```python
from dexter_autonomy.brain.time_machine import TimelineEvent, EventSeverity, EventCategory

event = TimelineEvent(
    severity=EventSeverity.INFO,
    category=EventCategory.AGENT_ACTION,
    event_type="task_completed",
    description="Agent completed data extraction task",
    agent_id="web_scraper",
    payload={"items_extracted": 42, "duration_ms": 1234},
    tags=["scraping", "success"],
)

event_id = await time_machine.log_event(event)
```

### Create Snapshots

```python
# Manual snapshot
snapshot_id = await time_machine.create_snapshot(
    state_data={
        "agents": get_all_agent_states(),
        "memory": get_memory_stats(),
        "bus_state": get_bus_state(),
    },
    name="Pre-deployment Snapshot",
    description="Snapshot before deploying new agent",
    tags=["manual", "deployment"],
)

# Automatic snapshots run in background every auto_snapshot_interval seconds
```

### Query Events

```python
# Query by severity
errors = await time_machine.query_events(
    severity=EventSeverity.ERROR,
    limit=100,
)

# Query by time range
recent_events = await time_machine.query_events(
    start_time=time.time() - 3600,  # Last hour
    limit=100,
)

# Query by agent
agent_events = await time_machine.query_events(
    agent_id="action_executor",
    limit=100,
)

# Full-text search
search_results = await time_machine.search_events("click button", limit=50)
```

### Rollback

```python
# Preview rollback
current_state = get_current_system_state()
preview = await time_machine.preview_rollback(
    snapshot_id="snapshot-123",
    current_state=current_state,
)

print(f"Risk Level: {preview.risk_level}")
print(f"Agents Affected: {preview.agents_affected}")
print(f"Warnings: {preview.warnings}")

if preview.can_rollback:
    # Execute rollback
    result = await time_machine.rollback_to_snapshot(
        snapshot_id="snapshot-123",
        current_state=current_state,
        dry_run=False,  # Set to True for preview only
    )
    
    print(f"Rollback: {result['status']}")
    print(f"Backup ID: {result['backup_id']}")
```

### Get Statistics

```python
stats = await time_machine.get_event_statistics()

print(f"Total Events: {stats['total_events']}")
print(f"Events (Last Hour): {stats['events_last_hour']}")
print(f"Errors (Last Hour): {stats['errors_last_hour']}")
print(f"Critical (Last Hour): {stats['critical_last_hour']}")
```

## REST API

The Time Machine provides a complete REST API:

### Timeline Events

- `POST /time-machine/events` - Log new event
- `GET /time-machine/events` - Query events (with filters)
- `GET /time-machine/events/search?query={text}` - Full-text search
- `GET /time-machine/events/stats` - Event statistics
- `GET /time-machine/events/{event_id}` - Get specific event
- `GET /time-machine/events/export/json` - Export events as JSON

### Snapshots

- `POST /time-machine/snapshots` - Create snapshot
- `GET /time-machine/snapshots` - List snapshots
- `GET /time-machine/snapshots/{id}` - Get snapshot
- `DELETE /time-machine/snapshots/{id}` - Delete snapshot

### Rollback

- `POST /time-machine/rollback/preview` - Preview rollback
- `POST /time-machine/rollback/execute` - Execute rollback

### Health

- `GET /time-machine/health` - Health check

### Example API Usage

```bash
# Log an event
curl -X POST http://localhost:8765/time-machine/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "user_action",
    "description": "User clicked submit button",
    "severity": "info",
    "category": "user_input",
    "payload": {"button": "submit", "form": "invoice"}
  }'

# Query events
curl "http://localhost:8765/time-machine/events?severity=error&limit=10"

# Search events
curl "http://localhost:8765/time-machine/events/search?query=invoice&limit=20"

# Create snapshot
curl -X POST http://localhost:8765/time-machine/snapshots \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Manual Snapshot",
    "description": "Before testing new feature",
    "state_data": {"test": "data"},
    "tags": ["manual", "testing"]
  }'

# List snapshots
curl "http://localhost:8765/time-machine/snapshots?limit=10"

# Preview rollback
curl -X POST http://localhost:8765/time-machine/rollback/preview \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_id": "abc-123",
    "current_state": {"current": "state"}
  }'
```

## Integration with BSM

The Time Machine is automatically integrated with BSM (Behavioral State Manager):

1. **BSM observes all events** on all buses (MAIN, COLLAB, PRIVATE)
2. **BSM logs observations to Timeline** via Time Machine
3. **Events are automatically categorized** based on bus and topic
4. **Severity is detected** from message content
5. **Correlation IDs are preserved** for event tracking

### BSM Event Logging Flow

```
Event on Bus → BSM._observe() → BSM._log_to_timeline() → TimeMachine.log_event()
```

### Event Categorization

BSM automatically determines event categories:

- **MAIN bus USER_INPUT** → `EventCategory.USER_INPUT`
- **MAIN bus INTENT/EFFECT** → `EventCategory.AGENT_ACTION`
- **MAIN bus ERROR** → `EventCategory.ERROR_EVENT`
- **COLLAB bus** → `EventCategory.COLLABORATION`
- **PRIVATE bus** → `EventCategory.AGENT_ACTION`

### Severity Detection

BSM automatically determines event severity:

- Topic "error" or "critical" → `EventSeverity.ERROR`
- Status contains "error" → `EventSeverity.ERROR`
- Topic "warning" → `EventSeverity.WARNING`
- Default → `EventSeverity.INFO`

## Configuration

Time Machine configuration options:

```python
time_machine = TimeMachine(
    # Database paths
    timeline_db="./data/timeline.db",          # Timeline event database
    snapshot_db="./data/snapshots.db",         # Snapshot metadata database
    snapshot_dir="./data/snapshots",           # Snapshot data directory
    
    # Automatic snapshots
    auto_snapshot_interval=300.0,              # Seconds between auto snapshots (5 min)
    
    # Retention policy
    retention_days=30,                         # Days to retain snapshots
    
    # Compression
    enable_compression=True,                   # GZIP compress snapshots
)
```

## Storage

### Timeline Database (SQLite)

- **Events table**: All timeline events
- **FTS5 table**: Full-text search index
- **Indexes**: timestamp, severity, category, agent_id, correlation_id

### Snapshot Database (SQLite)

- **Snapshots table**: Snapshot metadata
- **Data files**: Compressed JSON files in snapshot_dir

### Storage Estimates

- **Event**: ~500 bytes (compressed)
- **Snapshot**: Varies (depends on state size, compression ~50-80%)
- **1 million events**: ~500 MB
- **100 snapshots (1 MB each)**: ~50-80 MB compressed

## Testing

Comprehensive test suite with 33 tests covering:

- ✅ Timeline event logging and querying
- ✅ Event severity and category filtering
- ✅ Full-text search
- ✅ Event correlation tracking
- ✅ Snapshot creation and storage
- ✅ Snapshot compression and integrity
- ✅ Rollback preview and execution
- ✅ Automatic snapshot creation
- ✅ Retention policy cleanup
- ✅ BSM integration

Run tests:

```bash
pytest tests/test_time_machine.py -v
```

## Performance

### Timeline Queries

- **Simple queries**: <10ms
- **Complex queries with filters**: <50ms
- **Full-text search**: <100ms (depends on corpus size)
- **Event statistics**: <20ms

### Snapshots

- **Create snapshot (1 MB state)**: ~50ms (uncompressed), ~150ms (compressed)
- **Load snapshot**: ~30ms (uncompressed), ~100ms (compressed)
- **Rollback preview**: <20ms
- **Rollback execution**: ~200ms (includes backup creation)

### Scalability

- **Timeline**: Tested with 100K+ events
- **Snapshots**: Tested with 1000+ snapshots
- **Concurrent access**: WAL mode for concurrent reads/writes

## Best Practices

### Event Logging

1. **Use correlation IDs** to link related events
2. **Include relevant metadata** in payload
3. **Tag events appropriately** for easy filtering
4. **Keep descriptions concise** but informative

### Snapshots

1. **Tag snapshots consistently** (e.g., "deployment", "backup", "milestone")
2. **Enable compression** for large state data
3. **Set appropriate retention periods** based on importance
4. **Manual snapshots before critical operations**

### Rollback

1. **Always preview before rollback**
2. **Review warnings and risk level**
3. **Verify backup snapshot created**
4. **Test rollback in non-production first**

### Retention

1. **Balance retention days with storage**
2. **Keep critical snapshots (trigger="critical_event") longer**
3. **Archive old snapshots externally if needed**
4. **Monitor storage usage**

## Future Enhancements

### Planned Features

- [ ] **Real-time event streaming** via WebSocket
- [ ] **Event aggregation** for high-frequency events
- [ ] **Snapshot diff visualization** in UI
- [ ] **Automatic error recovery** based on event patterns
- [ ] **Event replay** for debugging
- [ ] **Snapshot comparison** tools
- [ ] **Advanced event analytics** (patterns, trends)
- [ ] **Export to external systems** (Elasticsearch, S3)

### Under Consideration

- [ ] Distributed timeline (multi-instance)
- [ ] Event sampling for high volume
- [ ] Snapshot streaming (incremental backups)
- [ ] Machine learning on event patterns
- [ ] Predictive failure detection

## Troubleshooting

### Issue: Events not appearing in timeline

**Solution**: Check BSM is started with Time Machine integration:

```python
bsm = BSM(buses=buses, brain=brain, time_machine=time_machine)
await bsm.start()
```

### Issue: Snapshot checksum mismatch

**Solution**: Snapshot data file corrupted. Delete and recreate snapshot.

### Issue: Timeline queries slow

**Solution**: 
1. Check indexes exist: `SELECT * FROM sqlite_master WHERE type='index'`
2. Run `ANALYZE` on database
3. Reduce query time range
4. Use pagination with LIMIT/OFFSET

### Issue: Disk space growing

**Solution**:
1. Check retention policy: `retention_days` setting
2. Run manual cleanup: `time_machine.snapshots.cleanup_expired()`
3. Delete old events manually if needed
4. Adjust `auto_snapshot_interval`

## See Also

- [BSM Documentation](./BSM.md)
- [Triple Bus Architecture](./TRIPLE_BUS.md)
- [WebSocket Streaming](../README-WEBSOCKET.md)
- [API Reference](./API.md)

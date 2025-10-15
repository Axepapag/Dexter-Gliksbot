"""
FastAPI routes for Time Machine features.

Provides REST API endpoints for:
- Timeline event logging and querying
- State snapshot management
- Rollback preview and execution
- Event statistics and search
"""
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from dexter_autonomy.brain.time_machine import (
    TimeMachine,
    TimelineEvent,
    EventSeverity,
    EventCategory,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/time-machine", tags=["time-machine"])

# Global Time Machine instance (set by main app)
time_machine: Optional[TimeMachine] = None


def set_time_machine(tm: TimeMachine):
    """Set global Time Machine instance"""
    global time_machine
    time_machine = tm


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateSnapshotRequest(BaseModel):
    """Request to create a snapshot"""
    name: str = Field(..., description="Human-readable snapshot name")
    description: str = Field("", description="Snapshot description")
    state_data: Dict[str, Any] = Field(..., description="Complete system state")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    trigger: str = Field("manual", description="What triggered the snapshot")


class RollbackRequest(BaseModel):
    """Request to rollback to a snapshot"""
    snapshot_id: str = Field(..., description="ID of snapshot to rollback to")
    current_state: Dict[str, Any] = Field(..., description="Current system state")
    dry_run: bool = Field(False, description="Preview only, don't execute")


class LogEventRequest(BaseModel):
    """Request to log a timeline event"""
    event_type: str = Field(..., description="Event type identifier")
    description: str = Field("", description="Event description")
    severity: str = Field("info", description="Event severity: debug, info, warning, error, critical")
    category: str = Field("system_event", description="Event category")
    bus: Optional[str] = Field(None, description="Event bus: main, collab, private")
    agent_id: Optional[str] = Field(None, description="Agent ID")
    task_root: Optional[str] = Field(None, description="Task root")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event payload")
    tags: List[str] = Field(default_factory=list, description="Event tags")


# ============================================================================
# Timeline Event Endpoints
# ============================================================================

@router.post("/events", response_model=Dict[str, str])
async def log_event(request: LogEventRequest):
    """
    Log a new timeline event.
    
    Creates a structured event in the timeline for observability and debugging.
    """
    if not time_machine:
        raise HTTPException(status_code=503, detail="Time Machine not initialized")
    
    try:
        # Parse severity and category
        severity = EventSeverity(request.severity.lower())
        category = EventCategory(request.category.lower())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid severity or category: {e}")
    
    event = TimelineEvent(
        event_type=request.event_type,
        description=request.description,
        severity=severity,
        category=category,
        bus=request.bus,
        agent_id=request.agent_id,
        task_root=request.task_root,
        payload=request.payload,
        tags=request.tags,
    )
    
    event_id = await time_machine.log_event(event)
    
    return {"event_id": event_id, "status": "logged"}


@router.get("/events", response_model=List[Dict[str, Any]])
async def query_events(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    category: Optional[str] = Query(None, description="Filter by category"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    start_time: Optional[float] = Query(None, description="Start timestamp (Unix)"),
    end_time: Optional[float] = Query(None, description="End timestamp (Unix)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum events to return"),
):
    """
    Query timeline events with filtering.
    
    Returns events matching the specified criteria, ordered by timestamp (newest first).
    """
    if not time_machine:
        raise HTTPException(status_code=503, detail="Time Machine not initialized")
    
    # Parse severity and category if provided
    severity_enum = None
    category_enum = None
    
    if severity:
        try:
            severity_enum = EventSeverity(severity.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")
    
    if category:
        try:
            category_enum = EventCategory(category.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    
    events = await time_machine.query_events(
        severity=severity_enum,
        category=category_enum,
        agent_id=agent_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    
    return [event.to_dict() for event in events]


@router.get("/events/search", response_model=List[Dict[str, Any]])
async def search_events(
    query: str = Query(..., description="Search query"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum events to return"),
):
    """
    Full-text search of timeline events.
    
    Searches event types and descriptions for the query string.
    """
    if not time_machine:
        raise HTTPException(status_code=503, detail="Time Machine not initialized")
    
    events = await time_machine.search_events(query, limit=limit)
    
    return [event.to_dict() for event in events]


@router.get("/events/stats", response_model=Dict[str, Any])
async def get_event_statistics():
    """
    Get timeline event statistics.
    
    Returns counts of events by time period and severity.
    """
    if not time_machine:
        raise HTTPException(status_code=503, detail="Time Machine not initialized")
    
    stats = await time_machine.get_event_statistics()
    
    return stats


@router.get("/events/{event_id}", response_model=Dict[str, Any])
async def get_event(event_id: str):
    """
    Get a specific timeline event by ID.
    """
    if not time_machine:
        raise HTTPException(status_code=503, detail="Time Machine not initialized")
    
    event = await time_machine.timeline.get_event(event_id)
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return event.to_dict()


# ============================================================================
# Snapshot Management Endpoints
# ============================================================================

@router.post("/snapshots", response_model=Dict[str, str])
async def create_snapshot(request: CreateSnapshotRequest):
    """
    Create a new state snapshot.
    
    Captures the current system state for potential rollback.
    """
    if not time_machine:
        raise HTTPException(status_code=503, detail="Time Machine not initialized")
    
    snapshot_id = await time_machine.create_snapshot(
        state_data=request.state_data,
        name=request.name,
        description=request.description,
        trigger=request.trigger,
        tags=request.tags,
    )
    
    return {"snapshot_id": snapshot_id, "status": "created"}


@router.get("/snapshots", response_model=List[Dict[str, Any]])
async def list_snapshots(
    limit: int = Query(100, ge=1, le=1000, description="Maximum snapshots to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    List available snapshots.
    
    Returns snapshot metadata (not full state data).
    """
    if not time_machine:
        raise HTTPException(status_code=503, detail="Time Machine not initialized")
    
    snapshots = await time_machine.list_snapshots(limit=limit, offset=offset)
    
    return snapshots


@router.get("/snapshots/{snapshot_id}", response_model=Dict[str, Any])
async def get_snapshot(snapshot_id: str):
    """
    Get a specific snapshot by ID.
    
    Returns full snapshot including state data.
    """
    if not time_machine:
        raise HTTPException(status_code=503, detail="Time Machine not initialized")
    
    snapshot = await time_machine.get_snapshot(snapshot_id)
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    return snapshot.to_dict()


@router.delete("/snapshots/{snapshot_id}")
async def delete_snapshot(snapshot_id: str):
    """
    Delete a snapshot.
    
    Permanently removes the snapshot and its data file.
    """
    if not time_machine:
        raise HTTPException(status_code=503, detail="Time Machine not initialized")
    
    success = await time_machine.snapshots.delete_snapshot(snapshot_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    return {"status": "deleted", "snapshot_id": snapshot_id}


# ============================================================================
# Rollback Endpoints
# ============================================================================

@router.post("/rollback/preview", response_model=Dict[str, Any])
async def preview_rollback(request: RollbackRequest):
    """
    Preview rollback changes without executing.
    
    Shows what will change if rollback is executed.
    """
    if not time_machine:
        raise HTTPException(status_code=503, detail="Time Machine not initialized")
    
    preview = await time_machine.preview_rollback(
        snapshot_id=request.snapshot_id,
        current_state=request.current_state,
    )
    
    return {
        "snapshot_id": preview.snapshot_id,
        "snapshot_name": preview.snapshot_name,
        "snapshot_timestamp": preview.snapshot_timestamp,
        "agents_affected": preview.agents_affected,
        "state_differences": preview.state_differences,
        "risk_level": preview.risk_level,
        "warnings": preview.warnings,
        "can_rollback": preview.can_rollback,
        "validation_errors": preview.validation_errors,
    }


@router.post("/rollback/execute", response_model=Dict[str, Any])
async def execute_rollback(request: RollbackRequest):
    """
    Execute rollback to a previous snapshot.
    
    Creates a backup of current state before rollback.
    Set dry_run=true to preview without executing.
    """
    if not time_machine:
        raise HTTPException(status_code=503, detail="Time Machine not initialized")
    
    result = await time_machine.rollback_to_snapshot(
        snapshot_id=request.snapshot_id,
        current_state=request.current_state,
        dry_run=request.dry_run,
    )
    
    if result.get("status") == "error":
        raise HTTPException(
            status_code=400,
            detail=result.get("message", "Rollback failed"),
        )
    
    return result


# ============================================================================
# Export Endpoints
# ============================================================================

@router.get("/events/export/json", response_model=List[Dict[str, Any]])
async def export_events_json(
    start_time: Optional[float] = Query(None, description="Start timestamp"),
    end_time: Optional[float] = Query(None, description="End timestamp"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum events"),
):
    """
    Export timeline events as JSON.
    
    Useful for external analysis or backup.
    """
    if not time_machine:
        raise HTTPException(status_code=503, detail="Time Machine not initialized")
    
    events = await time_machine.query_events(
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    
    return [event.to_dict() for event in events]


# ============================================================================
# Health and Status
# ============================================================================

@router.get("/health")
async def time_machine_health():
    """
    Check Time Machine health status.
    """
    if not time_machine:
        return {
            "status": "unavailable",
            "message": "Time Machine not initialized",
        }
    
    return {
        "status": "ok",
        "started": time_machine._started,
        "auto_snapshot_interval": time_machine.auto_snapshot_interval,
        "retention_days": time_machine.retention_days,
        "compression_enabled": time_machine.enable_compression,
    }

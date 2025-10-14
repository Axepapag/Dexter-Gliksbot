"""
Configuration Management REST API Routes

Provides HTTP endpoints for Cockpit UI to manage dexter_config.yml:
- GET /config - Retrieve full configuration
- GET /config/{section} - Retrieve specific section
- PUT /config/{section} - Update specific section
- POST /config/validate - Validate configuration changes
- POST /config/reload - Force reload from disk
- GET /config/version - Get current config version
- GET /config/snapshots - List all config snapshots
- POST /config/snapshots - Create new snapshot
- POST /config/snapshots/{id}/restore - Restore from snapshot
- GET /config/diff/{a}/{b} - Compare two snapshots

All config changes trigger WebSocket CONFIG_CHANGED events for real-time UI sync.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from dexter_autonomy.configs import get_global_config, reload_global_config
from dexter_autonomy.api.websocket_events import (
    WebSocketMessage,
    EventType,
    ConfigChangedEvent
)

logger = logging.getLogger(__name__)

# Create router for config endpoints
router = APIRouter(prefix="/config", tags=["configuration"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ConfigUpdateRequest(BaseModel):
    """Request model for config updates"""
    data: Dict[str, Any] = Field(..., description="New configuration data")
    version: Optional[int] = Field(None, description="Expected config version for optimistic locking")


class ConfigValidateRequest(BaseModel):
    """Request model for config validation"""
    section: str = Field(..., description="Section name to validate")
    data: Dict[str, Any] = Field(..., description="Configuration data to validate")


class ConfigValidateResponse(BaseModel):
    """Response model for validation"""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ConfigSnapshotRequest(BaseModel):
    """Request model for creating snapshot"""
    name: str = Field(..., description="Snapshot name")
    description: str = Field("", description="Snapshot description")


class ConfigSnapshotResponse(BaseModel):
    """Response model for snapshot"""
    id: str
    name: str
    description: str
    timestamp: datetime
    created_by: str
    version: int


class ConfigDiffResponse(BaseModel):
    """Response model for config diff"""
    added: Dict[str, Any] = Field(default_factory=dict)
    removed: Dict[str, Any] = Field(default_factory=dict)
    modified: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Configuration Endpoints
# ============================================================================

@router.get("")
@router.get("/")
async def get_full_config() -> Dict[str, Any]:
    """
    Get full configuration.
    
    Returns:
        Complete configuration dictionary
    
    Example:
        GET /config
        {
            "version": "1.0.0",
            "system": {...},
            "agents": [...],
            "providers": {...},
            ...
        }
    """
    try:
        config = get_global_config()
        return config.export_to_dict()
    except Exception as e:
        logger.error(f"Failed to get config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve configuration: {e}")


@router.get("/{section}")
async def get_config_section(section: str) -> Dict[str, Any]:
    """
    Get specific configuration section.
    
    Args:
        section: Section name (e.g., "agents", "providers", "deny_list")
    
    Returns:
        Section configuration dictionary
    
    Example:
        GET /config/agents
        [
            {"id": "bsm", "name": "Brain & State Model", ...},
            {"id": "dexter-orchestrator", ...}
        ]
    """
    try:
        config = get_global_config()
        section_data = config.get_section(section)
        
        if section_data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Section '{section}' not found in configuration"
            )
        
        return section_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get section '{section}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve section: {e}")


@router.put("/{section}")
async def update_config_section(
    section: str,
    request: ConfigUpdateRequest
) -> Dict[str, Any]:
    """
    Update specific configuration section.
    
    Args:
        section: Section name to update
        request: Update request with new data and optional version
    
    Returns:
        Updated section data and new version number
    
    Example:
        PUT /config/agents
        {
            "data": [
                {"id": "bsm", "model": "llama3:8b", ...}
            ],
            "version": 5
        }
        
        Response:
        {
            "status": "ok",
            "section": "agents",
            "new_version": 6,
            "timestamp": "2025-10-14T12:34:56Z"
        }
    
    Raises:
        409: Version conflict (optimistic locking failed)
        400: Validation failed
    """
    try:
        config = get_global_config()
        
        # Optimistic locking check
        if request.version is not None:
            current_version = config.get("_meta.version", 0)
            if current_version != request.version:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "version_conflict",
                        "message": f"Config was modified by another client. "
                                   f"Expected version {request.version}, current is {current_version}. "
                                   f"Please reload and reapply your changes.",
                        "current_version": current_version,
                        "expected_version": request.version
                    }
                )
        
        # Validate before updating
        valid, errors = config._validate_section(section, request.data)
        if not valid:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation_failed",
                    "message": "Configuration validation failed",
                    "errors": errors
                }
            )
        
        # Update section
        config.update_section(section, request.data)
        
        # Increment version
        new_version = config.get("_meta.version", 0) + 1
        config.set("_meta.version", new_version)
        config.set("_meta.last_modified", datetime.now().isoformat())
        
        # Save atomically
        config.save()
        
        logger.info(f"Updated config section '{section}', new version: {new_version}")
        
        # Broadcast change to WebSocket clients
        # (This will be handled by file system watcher in ConfigManager)
        
        return {
            "status": "ok",
            "section": section,
            "new_version": new_version,
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update section '{section}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {e}")


@router.post("/validate")
async def validate_config(request: ConfigValidateRequest) -> ConfigValidateResponse:
    """
    Validate configuration changes without applying them.
    
    Args:
        request: Validation request with section and data
    
    Returns:
        Validation result with errors and warnings
    
    Example:
        POST /config/validate
        {
            "section": "agents",
            "data": {"id": "bsm", "temperature": 2.5}
        }
        
        Response:
        {
            "valid": false,
            "errors": ["Temperature 2.5 exceeds maximum 2.0"],
            "warnings": []
        }
    """
    try:
        config = get_global_config()
        valid, errors = config._validate_section(request.section, request.data)
        
        # TODO: Add warnings for suboptimal configs
        warnings = []
        
        return ConfigValidateResponse(
            valid=valid,
            errors=errors,
            warnings=warnings
        )
    
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Validation error: {e}")


@router.post("/reload")
async def reload_config() -> Dict[str, Any]:
    """
    Force reload configuration from disk.
    
    Useful after manual file edits or to discard unsaved changes.
    
    Returns:
        Reload status and new version
    
    Example:
        POST /config/reload
        
        Response:
        {
            "status": "reloaded",
            "version": 7,
            "timestamp": "2025-10-14T12:35:00Z"
        }
    """
    try:
        reload_global_config()
        config = get_global_config()
        version = config.get("_meta.version", 0)
        
        logger.info(f"Config reloaded, version: {version}")
        
        return {
            "status": "reloaded",
            "version": version,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Failed to reload config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload configuration: {e}")


@router.get("/version")
async def get_config_version() -> Dict[str, Any]:
    """
    Get current configuration version.
    
    Used for optimistic locking and change detection.
    
    Returns:
        Current version number and last modified timestamp
    
    Example:
        GET /config/version
        
        Response:
        {
            "version": 7,
            "last_modified": "2025-10-14T12:35:00Z"
        }
    """
    try:
        config = get_global_config()
        return {
            "version": config.get("_meta.version", 0),
            "last_modified": config.get("_meta.last_modified", None)
        }
    
    except Exception as e:
        logger.error(f"Failed to get version: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get version: {e}")


# ============================================================================
# Agent & Provider Shortcuts
# ============================================================================

@router.get("/agents")
async def get_agents_config() -> List[Dict[str, Any]]:
    """Get all agent configurations."""
    return await get_config_section("agents")


@router.get("/agents/{agent_id}")
async def get_agent_config(agent_id: str) -> Dict[str, Any]:
    """
    Get specific agent configuration.
    
    Args:
        agent_id: Agent identifier (e.g., "bsm", "dexter-orchestrator")
    
    Returns:
        Agent configuration dictionary
    """
    try:
        config = get_global_config()
        agent_config = config.get_agent_config(agent_id)
        
        if agent_config is None:
            raise HTTPException(
                status_code=404,
                detail=f"Agent '{agent_id}' not found in configuration"
            )
        
        return agent_config
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent config for '{agent_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers")
async def get_providers_config() -> Dict[str, Any]:
    """Get all provider configurations."""
    return await get_config_section("providers")


@router.get("/providers/{provider_name}")
async def get_provider_config(provider_name: str) -> Dict[str, Any]:
    """
    Get specific provider configuration.
    
    Args:
        provider_name: Provider name (e.g., "ollama", "openai", "perplexity")
    
    Returns:
        Provider configuration dictionary
    """
    try:
        config = get_global_config()
        provider_config = config.get_provider_config(provider_name)
        
        if provider_config is None:
            raise HTTPException(
                status_code=404,
                detail=f"Provider '{provider_name}' not found in configuration"
            )
        
        return provider_config
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get provider config for '{provider_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Snapshot Management (Placeholder - to be implemented)
# ============================================================================

@router.get("/snapshots")
async def list_snapshots() -> List[ConfigSnapshotResponse]:
    """
    List all configuration snapshots.
    
    Returns:
        List of snapshots with metadata
    
    TODO: Implement ConfigVersionManager
    """
    # Placeholder - will be implemented in Phase 2.2
    return []


@router.post("/snapshots")
async def create_snapshot(request: ConfigSnapshotRequest) -> ConfigSnapshotResponse:
    """
    Create new configuration snapshot.
    
    Args:
        request: Snapshot creation request with name and description
    
    Returns:
        Created snapshot metadata
    
    TODO: Implement ConfigVersionManager
    """
    # Placeholder - will be implemented in Phase 2.2
    raise HTTPException(status_code=501, detail="Snapshots not yet implemented")


@router.post("/snapshots/{snapshot_id}/restore")
async def restore_snapshot(snapshot_id: str) -> Dict[str, Any]:
    """
    Restore configuration from snapshot.
    
    Args:
        snapshot_id: Snapshot ID to restore
    
    Returns:
        Restore status
    
    TODO: Implement ConfigVersionManager
    """
    # Placeholder - will be implemented in Phase 2.2
    raise HTTPException(status_code=501, detail="Snapshots not yet implemented")


@router.get("/diff/{snapshot_a}/{snapshot_b}")
async def get_config_diff(snapshot_a: str, snapshot_b: str) -> ConfigDiffResponse:
    """
    Compare two configuration snapshots.
    
    Args:
        snapshot_a: First snapshot ID
        snapshot_b: Second snapshot ID
    
    Returns:
        Diff showing added, removed, and modified sections
    
    TODO: Implement diff algorithm
    """
    # Placeholder - will be implemented in Phase 2.2
    raise HTTPException(status_code=501, detail="Config diff not yet implemented")

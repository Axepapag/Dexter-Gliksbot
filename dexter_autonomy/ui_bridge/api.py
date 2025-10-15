"""
FastAPI Application for Dexter-Gliksbot UI Bridge

Provides REST and WebSocket endpoints for Cockpit UI integration.
Implements real-time streaming of events from TripleBus to multiple clients.

Endpoints:
- GET /health, /healthz - Health checks
- WS /ws/cockpit - WebSocket for real-time event streaming
- GET /ws/health - WebSocket system health
- GET /stats - WebSocket statistics

Architecture:
    TripleBus (MAIN, COLLAB, PRIVATE)
        ↓
    WebSocketManager (observer + cache)
        ↓
    ConnectionManager (filtering + broadcasting)
        ↓
    FastAPI WebSocket (/ws/cockpit)
        ↓
    Cockpit Clients (WPF, Python, Browser)
"""
import os
import logging
import uuid
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dexter_autonomy.core.triple_bus import TripleBusSystem, get_global_triple_bus
from dexter_autonomy.api.websocket_manager import WebSocketManager
from dexter_autonomy.api.connection_manager import ClientSubscription
from dexter_autonomy.api.config_routes import router as config_router

logger = logging.getLogger(__name__)

# Global instances
triple_bus: Optional[TripleBusSystem] = None
ws_manager: Optional[WebSocketManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler for startup/shutdown.
    
    Startup:
    - Initialize TripleBus system
    - Create WebSocketManager
    - Subscribe to all buses
    
    Shutdown:
    - Stop WebSocketManager
    - Stop TripleBus system
    """
    global triple_bus, ws_manager
    
    logger.info("Starting Dexter UI Bridge...")
    
    # Initialize TripleBus
    triple_bus = get_global_triple_bus()
    await triple_bus.start_all()
    logger.info("TripleBus system started")
    
    # Initialize WebSocketManager
    ws_manager = WebSocketManager(triple_bus)
    await ws_manager.start()
    logger.info("WebSocketManager started")
    
    logger.info("UI Bridge ready for connections")
    
    yield
    
    # Shutdown
    logger.info("Shutting down UI Bridge...")
    
    if ws_manager:
        await ws_manager.stop()
        logger.info("WebSocketManager stopped")
    
    if triple_bus:
        await triple_bus.stop_all()
        logger.info("TripleBus system stopped")
    
    logger.info("UI Bridge shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Dexter UI Bridge API",
    description="Real-time WebSocket streaming for Dexter-Gliksbot Cockpit UI",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for browser clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include configuration routes
app.include_router(config_router)


# ============================================================================
# Health Check Endpoints
# ============================================================================

@app.get("/health")
@app.get("/healthz")
async def health_check() -> JSONResponse:
    """
    Basic health check endpoint.
    
    Returns:
        - status: "ok" if system operational
        - components: Status of TripleBus and WebSocketManager
    """
    try:
        health_status = {
            "status": "ok",
            "components": {
                "triple_bus": {
                    "status": "running" if triple_bus and triple_bus.main._started else "stopped",
                    "main_bus": triple_bus.main._started if triple_bus else False,
                    "collab_bus": triple_bus.collab._started if triple_bus else False,
                    "private_buses": len(triple_bus._private_buses) if triple_bus else 0,
                },
                "websocket_manager": {
                    "status": "running" if ws_manager and ws_manager._started else "stopped",
                    "active_connections": len(ws_manager.connection_manager.active_connections) if ws_manager else 0,
                    "event_history_size": len(ws_manager.connection_manager.event_history) if ws_manager else 0,
                }
            }
        }
        return JSONResponse(content=health_status, status_code=200)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=503
        )


@app.get("/ws/health")
async def websocket_health() -> Dict[str, Any]:
    """
    WebSocket system health check.
    
    Returns detailed statistics about WebSocket infrastructure:
    - Active connections count
    - Event history size
    - Cache statistics (agents, missions)
    - System metrics
    """
    if not ws_manager:
        raise HTTPException(status_code=503, detail="WebSocketManager not initialized")
    
    try:
        stats = ws_manager.get_stats()
        return {
            "status": "healthy",
            "websocket_manager": stats,
            "connection_manager": ws_manager.connection_manager.get_stats()
        }
    except Exception as e:
        logger.error(f"WebSocket health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """
    Get comprehensive system statistics.
    
    Returns:
        - TripleBus stats (topics, subscribers)
        - WebSocketManager stats (cache sizes, uptime)
        - ConnectionManager stats (clients, messages)
    """
    if not triple_bus or not ws_manager:
        raise HTTPException(status_code=503, detail="System not fully initialized")
    
    try:
        return {
            "triple_bus": triple_bus.get_stats(),
            "websocket_manager": ws_manager.get_stats(),
            "connection_manager": ws_manager.connection_manager.get_stats()
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@app.websocket("/ws/cockpit")
async def websocket_cockpit(
    websocket: WebSocket,
    agent_ids: Optional[str] = Query(None, description="Comma-separated agent IDs to filter"),
    mission_ids: Optional[str] = Query(None, description="Comma-separated mission IDs to filter"),
    log_levels: Optional[str] = Query(None, description="Comma-separated log levels (TRACE,INFO,WARN,ERROR)"),
    event_types: Optional[str] = Query(None, description="Comma-separated event types to filter"),
    client_id: Optional[str] = Query(None, description="Optional client ID (auto-generated if not provided)"),
):
    """
    WebSocket endpoint for real-time Cockpit UI streaming.
    
    Connection Flow:
    1. Client connects with optional filters (agent_ids, mission_ids, log_levels, event_types)
    2. Server sends state snapshot (current agents, missions, system metrics)
    3. Server replays recent events (last 5 minutes or 100 events)
    4. Server streams real-time events (5s aggregation for agent status, immediate for critical)
    5. Heartbeat: Server pings every 30s, expects pong within 10s
    
    Query Parameters:
        - agent_ids: Filter events by agent (e.g., "agent-1,agent-2")
        - mission_ids: Filter events by mission (e.g., "mission-1")
        - log_levels: Filter log events (e.g., "ERROR,WARN")
        - event_types: Filter event types (e.g., "AGENT_STATUS,MISSION_PROGRESS")
        - client_id: Custom client identifier (default: auto-generated UUID)
    
    Message Format (JSON):
        {
            "type": "agent_status",  # EventType enum value
            "timestamp": "2025-10-14T12:34:56.789Z",
            "data": {
                "agent_id": "web-scraper",
                "status": "on_task",
                "current_mission": "mission-1",
                "metrics": {...}
            },
            "metadata": {
                "bus": "MAIN",
                "topic": "TRACE",
                "correlation_id": "abc123"
            }
        }
    
    Authentication:
        - Development: No authentication (bypass)
        - Production: JWT token validation (TODO: implement)
    
    Rate Limiting:
        - 1000 messages/minute per client (TODO: implement)
    
    Error Handling:
        - Client disconnect: Fire-and-forget (server drops events, logs disconnect)
        - Heartbeat timeout: Server closes connection after 10s without pong
        - Server error: Server sends error message, closes connection
    """
    if not ws_manager:
        await websocket.close(code=1011, reason="WebSocketManager not initialized")
        return
    
    # Generate client ID if not provided
    if not client_id:
        client_id = f"cockpit-{uuid.uuid4().hex[:8]}"
    
    # Parse filters
    filters = {}
    if agent_ids:
        filters["agent_ids"] = set(agent_ids.split(","))
    if mission_ids:
        filters["mission_ids"] = set(mission_ids.split(","))
    if log_levels:
        from dexter_autonomy.api.websocket_events import LogLevel
        filters["log_levels"] = set(LogLevel[level.upper()] for level in log_levels.split(",") if level.upper() in LogLevel.__members__)
    if event_types:
        from dexter_autonomy.api.websocket_events import EventType
        filters["event_types"] = set(EventType[et.upper()] for et in event_types.split(",") if et.upper() in EventType.__members__)
    
    logger.info(f"WebSocket connection request from {client_id} with filters: {filters}")
    
    try:
        # Connect client to ConnectionManager
        await ws_manager.connection_manager.connect(
            client_id=client_id,
            websocket=websocket,
            filters=filters
        )
        
        logger.info(f"WebSocket client {client_id} connected successfully")
        
        # Keep connection alive - ConnectionManager handles everything
        # (state snapshot, event replay, heartbeat, broadcasting)
        while True:
            try:
                # Receive messages from client (for pong responses, filter updates, etc.)
                message = await websocket.receive_json()
                
                # Handle client messages
                if message.get("type") == "update_filters":
                    # Client wants to update subscription filters
                    new_filters = message.get("filters", {})
                    ws_manager.connection_manager.update_subscription(client_id, new_filters)
                    logger.debug(f"Updated filters for {client_id}: {new_filters}")
                    
                elif message.get("type") == "pong":
                    # Heartbeat response (handled by ConnectionManager)
                    pass
                    
                elif message.get("type") == "request_snapshot":
                    # Client requests fresh state snapshot
                    force_refresh = message.get("force_refresh", False)
                    snapshot = ws_manager.get_state_snapshot(force_refresh=force_refresh)
                    await websocket.send_json({
                        "type": "state_snapshot",
                        "timestamp": snapshot["timestamp"],
                        "data": snapshot
                    })
                    
            except WebSocketDisconnect:
                logger.info(f"WebSocket client {client_id} disconnected")
                break
            except Exception as e:
                logger.error(f"Error processing message from {client_id}: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket client {client_id} disconnected during handshake")
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass
    finally:
        # Cleanup
        await ws_manager.connection_manager.disconnect(client_id)
        logger.info(f"WebSocket client {client_id} cleanup complete")


# ============================================================================
# Development Endpoints (TODO: Remove in production or add auth)
# ============================================================================

@app.get("/debug/connections")
async def debug_connections() -> Dict[str, Any]:
    """
    Debug endpoint: List all active WebSocket connections.
    
    Returns client IDs, filters, and connection times.
    """
    if not ws_manager:
        raise HTTPException(status_code=503, detail="WebSocketManager not initialized")
    
    connections = []
    for client_id, subscription in ws_manager.connection_manager.client_subscriptions.items():
        connections.append({
            "client_id": client_id,
            "filters": {
                "agent_ids": list(subscription.agent_ids) if subscription.agent_ids else [],
                "mission_ids": list(subscription.mission_ids) if subscription.mission_ids else [],
                "log_levels": [level.value for level in subscription.log_levels] if subscription.log_levels else [],
                "event_types": [et.value for et in subscription.event_types] if subscription.event_types else [],
                "subscribe_all": subscription.subscribe_all
            }
        })
    
    return {
        "total_connections": len(connections),
        "connections": connections
    }


@app.get("/debug/cache")
async def debug_cache() -> Dict[str, Any]:
    """
    Debug endpoint: Inspect WebSocketManager cache contents.
    
    Returns cached agent states, mission states, and system metrics.
    """
    if not ws_manager:
        raise HTTPException(status_code=503, detail="WebSocketManager not initialized")
    
    return {
        "agents": {k: v for k, v in ws_manager._agent_state_cache.items()},
        "missions": {k: v for k, v in ws_manager._mission_state_cache.items()},
        "system_metrics": ws_manager._system_metrics_cache,
        "cache_stats": {
            "agent_count": len(ws_manager._agent_state_cache),
            "mission_count": len(ws_manager._mission_state_cache),
            "oldest_agent_age_seconds": ws_manager._get_oldest_cache_age("agent"),
            "oldest_mission_age_seconds": ws_manager._get_oldest_cache_age("mission")
        }
    }


# ============================================================================
# Additional WebSocket Endpoints (Cockpit Compatibility)
# ============================================================================

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket, client_id: Optional[str] = Query(None)):
    """WebSocket endpoint for logs only (delegates to /ws/cockpit with log filter)"""
    return await websocket_cockpit(
        websocket=websocket,
        event_types="LOG",
        client_id=client_id or f"logs-{uuid.uuid4().hex[:8]}"
    )

@app.websocket("/ws/agents")
async def websocket_agents(websocket: WebSocket, client_id: Optional[str] = Query(None)):
    """WebSocket endpoint for agent status updates (delegates to /ws/cockpit)"""
    return await websocket_cockpit(
        websocket=websocket,
        event_types="AGENT_STATUS",
        client_id=client_id or f"agents-{uuid.uuid4().hex[:8]}"
    )

@app.websocket("/ws/missions")
async def websocket_missions(websocket: WebSocket, client_id: Optional[str] = Query(None)):
    """WebSocket endpoint for mission updates (delegates to /ws/cockpit)"""
    return await websocket_cockpit(
        websocket=websocket,
        event_types="MISSION_PROGRESS,MISSION_COMPLETE",
        client_id=client_id or f"missions-{uuid.uuid4().hex[:8]}"
    )

@app.websocket("/ws/performance")
async def websocket_performance(websocket: WebSocket, client_id: Optional[str] = Query(None)):
    """WebSocket endpoint for performance metrics (delegates to /ws/cockpit)"""
    return await websocket_cockpit(
        websocket=websocket,
        event_types="PERFORMANCE",
        client_id=client_id or f"performance-{uuid.uuid4().hex[:8]}"
    )

@app.websocket("/ws/config")
async def websocket_config(websocket: WebSocket, client_id: Optional[str] = Query(None)):
    """WebSocket endpoint for config changes (delegates to /ws/cockpit)"""
    return await websocket_cockpit(
        websocket=websocket,
        event_types="CONFIG_CHANGED",
        client_id=client_id or f"config-{uuid.uuid4().hex[:8]}"
    )

# ============================================================================
# Root Endpoint
# ============================================================================

@app.get("/")
async def root() -> Dict[str, str]:
    """
    Root endpoint with API information.
    """
    return {
        "name": "Dexter UI Bridge API",
        "version": "1.0.0",
        "description": "Real-time WebSocket streaming for Dexter-Gliksbot Cockpit UI",
        "endpoints": {
            "health": "GET /health, /healthz",
            "websocket": "WS /ws/cockpit (unified real-time streaming)",
            "websocket_logs": "WS /ws/logs (log events only)",
            "websocket_agents": "WS /ws/agents (agent status only)",
            "websocket_missions": "WS /ws/missions (mission updates only)",
            "websocket_performance": "WS /ws/performance (metrics only)",
            "websocket_config": "WS /ws/config (config changes only)",
            "websocket_health": "GET /ws/health (WebSocket system status)",
            "stats": "GET /stats (system statistics)",
            "debug_connections": "GET /debug/connections (active WebSocket clients)",
            "debug_cache": "GET /debug/cache (WebSocketManager cache inspection)"
        },
        "documentation": "/docs (Swagger UI)"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)

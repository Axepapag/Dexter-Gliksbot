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
import time
import asyncio
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yaml
from pathlib import Path
from pydantic import BaseModel, Field

from dexter_autonomy.core.triple_bus import TripleBusSystem, get_global_triple_bus, MainTopic
from dexter_autonomy.core.policy_overlay import CompositeDenyPolicy
from dexter_autonomy.api.websocket_manager import WebSocketManager
from dexter_autonomy.api.connection_manager import ClientSubscription
from dexter_autonomy.api.config_routes import router as config_router
from dexter_autonomy.api.time_machine_routes import router as time_machine_router, set_time_machine
from dexter_autonomy.brain.time_machine import TimeMachine
from dexter_autonomy.brain.memory import BrainDB
from dexter_autonomy.agents.bsm import BSM
from dexter_autonomy.agents.dexter_orchestrator import DexterOrchestrator
from dexter_autonomy.agents.action_executor import ActionExecutor
from dexter_autonomy.agents.chatdock import ChatDockAgent
from dexter_autonomy.agents.providers import get_provider, PROVIDERS

logger = logging.getLogger(__name__)

# Global instances
triple_bus: Optional[TripleBusSystem] = None
ws_manager: Optional[WebSocketManager] = None
time_machine: Optional[TimeMachine] = None
bsm: Optional[BSM] = None
dexter: Optional[DexterOrchestrator] = None
action_executor: Optional[ActionExecutor] = None
config_data: Optional[Dict[str, Any]] = None  # Loaded configuration


def load_config() -> Dict[str, Any]:
    """Load configuration from dexter_config.yml"""
    config_path = Path("configs/dexter_config.yml")
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    else:
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return {
            "agents": {
                "dexter-orchestrator": {
                    "provider": "ollama",
                    "model": "qwen2.5:3b-instruct",
                    "temperature": 0.15
                },
                "bsm-brain": {
                    "provider": "ollama",
                    "model": "qwen2.5:3b-instruct",
                    "temperature": 0.3
                }
            }
        }


def get_agent_provider(agent_config: Dict[str, Any]):
    """Create LLM provider from agent configuration"""
    provider_name = agent_config.get("provider", "ollama")
    model = agent_config.get("model")
    endpoint = agent_config.get("endpoint")
    api_key_env = agent_config.get("api_key_env")
    temperature = agent_config.get("temperature", 0.7)
    
    # Get provider-specific settings
    kwargs = {}
    if "thinking_enabled" in agent_config:
        kwargs["thinking_enabled"] = agent_config["thinking_enabled"]
    if "thinking_budget" in agent_config:
        kwargs["thinking_budget"] = agent_config["thinking_budget"]
    if "max_output_tokens" in agent_config:
        kwargs["max_output_tokens"] = agent_config["max_output_tokens"]
    if "timeout" in agent_config:
        kwargs["timeout"] = agent_config["timeout"]
    
    try:
        provider = get_provider(
            provider_name=provider_name,
            endpoint=endpoint,
            api_key_env=api_key_env,
            model=model,
            **kwargs
        )
        logger.info(f"Created provider: {provider_name} with model: {model}")
        return provider
    except Exception as e:
        logger.error(f"Failed to create provider {provider_name}: {e}")
        # Fallback to Ollama
        logger.warning("Falling back to Ollama provider")
        return get_provider(
            provider_name="ollama",
            endpoint="http://127.0.0.1:11434",
            model="qwen2.5:3b-instruct"
        )


# ============================================================================
# Request/Response Models
# ============================================================================

class ChatRequest(BaseModel):
    """Request model for chat endpoints"""
    message: str = Field(..., description="Message to send to the agent")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="LLM temperature override")


class ChatResponse(BaseModel):
    """Response model for chat endpoints"""
    response: str = Field(..., description="Agent's response")
    agent: str = Field(..., description="Which agent responded")
    timestamp: float = Field(..., description="Response timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional response metadata")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler for startup/shutdown.
    
    Startup:
    - Initialize TripleBus system
    - Initialize Time Machine
    - Initialize BSM with Time Machine integration
    - Create WebSocketManager
    - Subscribe to all buses
    
    Shutdown:
    - Stop BSM
    - Stop Time Machine
    - Stop WebSocketManager
    - Stop TripleBus system
    """
    global triple_bus, ws_manager, time_machine, bsm, dexter, action_executor, config_data
    
    logger.info("Starting Dexter UI Bridge...")
    
    # Load configuration
    config_data = load_config()
    logger.info(f"Loaded configuration (environment: {config_data.get('environment', 'unknown')})")
    
    # Initialize TripleBus and Policy with empty profile (permissive by default)
    policy = CompositeDenyPolicy(profile={}, overlay=None)
    triple_bus = get_global_triple_bus()
    await triple_bus.start_all()
    logger.info("TripleBus system started")
    
    # Initialize Time Machine
    time_machine = TimeMachine(
        timeline_db="./data/timeline.db",
        snapshot_db="./data/snapshots.db",
        snapshot_dir="./data/snapshots",
        auto_snapshot_interval=300.0,  # 5 minutes
        retention_days=30,
        enable_compression=True,
    )
    await time_machine.start()
    set_time_machine(time_machine)
    logger.info("Time Machine started")
    
    # Initialize Brain
    brain = BrainDB(db_path="./data/brain.db")
    logger.info("Brain initialized")
    
    # Initialize ActionExecutor
    action_executor = ActionExecutor(triple_bus, policy, None)  # tesseract_path=None for now
    logger.info("ActionExecutor initialized")
    
    # Get agent configurations
    agents_config = config_data.get("agents", {})
    dexter_config = agents_config.get("dexter-orchestrator", {})
    bsm_config = agents_config.get("bsm-brain", {})
    
    # Create providers for agents
    logger.info("Creating LLM providers...")
    dexter_provider = get_agent_provider(dexter_config)
    bsm_provider = get_agent_provider(bsm_config)
    
    # Store providers globally for hot-swapping
    dexter_provider_instance = dexter_provider
    bsm_provider_instance = bsm_provider
    
    logger.info(f"Dexter provider: {dexter_provider.name} / {dexter_provider.default_model}")
    logger.info(f"BSM provider: {bsm_provider.name} / {bsm_provider.default_model}")
    
    # Note: BSM and Dexter classes need to be updated to use providers
    # For now, keeping the old initialization but logging the provider info
    # TODO: Refactor BSM/Dexter to accept provider instead of Ollama client
    
    # Initialize BSM (temporarily with Ollama until refactored)
    bsm = BSM(
        buses=triple_bus,
        brain=brain,
        model=bsm_provider.default_model,
        host=bsm_provider.endpoint if hasattr(bsm_provider, 'endpoint') else "http://127.0.0.1:11434",
        temperature=bsm_config.get("temperature", 0.3),
        time_machine=time_machine,
    )
    await bsm.start()
    logger.info(f"BSM started (omniscient observer active)")
    
    # Initialize ChatDock Agent
    chatdock = ChatDockAgent(triple_bus, policy, action_executor, bsm, None)
    logger.info("ChatDock initialized")
    
    # Initialize Dexter Orchestrator (keep simple config for now)
    config = {
        "slots": {
            "dexter-orchestrator": {
                "endpoint": dexter_provider.endpoint if hasattr(dexter_provider, 'endpoint') else "http://127.0.0.1:11434",
                "api_key_env": dexter_config.get("api_key_env", "GOOGLE_API_KEY"),
                "model": dexter_provider.default_model,
                "system_prompt": dexter_config.get("system_prompt", "You are Dexter, the central orchestrator."),
                "ollama_options": {}
            }
        }
    }
    
    dexter = DexterOrchestrator(
        buses=triple_bus,
        policy=policy,
        brain=brain,
        executor=action_executor,
        bsm=bsm,
        chatdock=chatdock,
        config=config
    )
    logger.info(f"Dexter Orchestrator initialized (provider: {dexter_provider.name})")
    
    # Store providers globally for use in chat endpoints
    app.state.dexter_provider = dexter_provider
    app.state.bsm_provider = bsm_provider
    app.state.config = config_data
    
    # Initialize WebSocketManager
    ws_manager = WebSocketManager(triple_bus)
    await ws_manager.start()
    logger.info("WebSocketManager started")
    
    logger.info(f"UI Bridge ready - Dexter ({dexter_provider.name}) and BSM ({bsm_provider.name}) are ONLINE")
    logger.info(f"Provider hot-swap: Update configs/dexter_config.yml and reload")
    
    yield
    
    # Shutdown
    logger.info("Shutting down UI Bridge...")
    
    if bsm:
        await bsm.stop()
        logger.info("BSM stopped")
    
    if time_machine:
        await time_machine.stop()
        logger.info("Time Machine stopped")
    
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

# Include Time Machine routes
app.include_router(time_machine_router)


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
        - components: Status of all system components
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
                },
                "time_machine": {
                    "status": "running" if time_machine and time_machine._started else "stopped",
                    "auto_snapshot_interval": time_machine.auto_snapshot_interval if time_machine else None,
                    "retention_days": time_machine.retention_days if time_machine else None,
                },
                "bsm": {
                    "status": "running" if bsm and bsm._started else "stopped",
                    "observations": bsm._observation_count if bsm else 0,
                    "context_provided": bsm._context_provided_count if bsm else 0,
                    "time_machine_enabled": bsm.time_machine is not None if bsm else False,
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


@app.get("/slots")
async def get_agent_slots() -> JSONResponse:
    """
    Get agent slot configurations for the Cockpit UI.
    
    Returns agent configurations from dexter_config.yml in a format
    compatible with the legacy Cockpit UI expectations.
    """
    try:
        if not config_data:
            return JSONResponse(
                content={"error": "Configuration not loaded"},
                status_code=500
            )
        
        agents_config = config_data.get("agents", {})
        
        # Transform our config format to the UI's expected format
        slots = {}
        for agent_id, agent_cfg in agents_config.items():
            slots[agent_id] = {
                "label": agent_cfg.get("label", agent_id),
                "description": agent_cfg.get("description", ""),
                "endpoint": agent_cfg.get("endpoint", "http://127.0.0.1:8765"),
                "model": agent_cfg.get("model", ""),
                "api_key_env": agent_cfg.get("api_key_env", ""),
                "temperature": agent_cfg.get("temperature", 0.7),
                "system_prompt": agent_cfg.get("system_prompt", ""),
                "provider": agent_cfg.get("provider", "ollama")
            }
        
        return JSONResponse(content={
            "slots": slots,
            "default_slot": "dexter-orchestrator"
        })
    except Exception as e:
        logger.error(f"Failed to get agent slots: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )


# ============================================================================
# Chat Endpoints - Dexter and BSM
# ============================================================================

@app.post("/dexter/chat", response_model=ChatResponse)
async def chat_with_dexter(request: ChatRequest) -> ChatResponse:
    """
    Chat with Dexter Orchestrator using configured LLM provider.
    
    Dexter will process your message, potentially extract actions,
    coordinate with other agents, and respond with natural language.
    
    BSM observes all interactions on the MAIN bus.
    
    Provider is hot-swappable via dexter_config.yml
    """
    if not dexter:
        raise HTTPException(status_code=503, detail="Dexter not initialized")
    
    try:
        logger.info(f"Received chat request for Dexter: {request.message[:100]}...")
        
        # Get provider from app state
        provider = app.state.dexter_provider
        system_prompt = dexter.config.get("slots", {}).get("dexter-orchestrator", {}).get("system_prompt", "You are Dexter.")
        
        # Build conversation messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.message}
        ]
        
        # Invoke LLM via provider (runs in thread pool to not block async)
        loop = asyncio.get_running_loop()
        response_obj = await loop.run_in_executor(
            None,
            lambda: provider.chat(
                messages=messages,
                temperature=request.temperature or 0.15,
            )
        )
        
        response_text = response_obj.content
        
        # Publish to MAIN bus so BSM observes
        await triple_bus.main.publish(MainTopic.USER_INPUT, {
            "source": "api",
            "message": request.message,
            "timestamp": time.time()
        })
        
        await triple_bus.main.publish(MainTopic.TRACE, {
            "agent": "dexter",
            "message": response_text,
            "timestamp": time.time(),
            "provider": provider.name,
            "model": response_obj.model
        })
        
        logger.info(f"Dexter response ({provider.name}/{response_obj.model}): {response_text[:100]}...")
        
        return ChatResponse(
            response=response_text,
            agent="dexter",
            timestamp=time.time(),
            metadata={
                "provider": provider.name,
                "model": response_obj.model,
                "usage": response_obj.usage
            }
        )
        
    except Exception as e:
        logger.error(f"Dexter chat failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Dexter chat failed: {str(e)}")


@app.post("/bsm/chat", response_model=ChatResponse)
async def chat_with_bsm(request: ChatRequest) -> ChatResponse:
    """
    Chat with BSM (Brain/State Model) using configured LLM provider.
    
    BSM can analyze patterns, provide context from observations,
    and answer questions about system state and learning.
    
    BSM observes its own responses on the MAIN bus.
    
    Provider is hot-swappable via dexter_config.yml
    """
    if not bsm:
        raise HTTPException(status_code=503, detail="BSM not initialized")
    
    try:
        logger.info(f"Received chat request for BSM: {request.message[:100]}...")
        
        # Get provider from app state
        provider = app.state.bsm_provider
        bsm_config = app.state.config.get("agents", {}).get("bsm-brain", {})
        system_prompt = bsm_config.get("system_prompt", "You are BSM, the Brain/State Model.")
        
        # Build conversation messages with BSM's context
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.message}
        ]
        
        # Invoke LLM via provider (runs in thread pool)
        loop = asyncio.get_running_loop()
        response_obj = await loop.run_in_executor(
            None,
            lambda: provider.chat(
                messages=messages,
                temperature=request.temperature or bsm_config.get("temperature", 0.3),
            )
        )
        
        response_text = response_obj.content
        
        # Publish to MAIN bus so BSM observes (meta: BSM observing itself)
        await triple_bus.main.publish(MainTopic.USER_INPUT, {
            "source": "api",
            "target": "bsm",
            "message": request.message,
            "timestamp": time.time()
        })
        
        await triple_bus.main.publish(MainTopic.TRACE, {
            "agent": "bsm",
            "message": response_text,
            "timestamp": time.time(),
            "provider": provider.name,
            "model": response_obj.model,
            "observations": bsm._observation_count,
            "context_provided": bsm._context_provided_count
        })
        
        logger.info(f"BSM response ({provider.name}/{response_obj.model}): {response_text[:100]}...")
        
        return ChatResponse(
            response=response_text,
            agent="bsm",
            timestamp=time.time(),
            metadata={
                "provider": provider.name,
                "model": response_obj.model,
                "observations": bsm._observation_count,
                "context_provided": bsm._context_provided_count,
                "usage": response_obj.usage
            }
        )
        
    except Exception as e:
        logger.error(f"BSM chat failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"BSM chat failed: {str(e)}")


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

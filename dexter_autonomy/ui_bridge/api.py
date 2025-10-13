"""FastAPI bridge for Dexter Autonomy UI."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import yaml

from ..core.event_bus import EventBus, Topic
from ..core.policy_overlay import CompositeDenyPolicy
from ..core.profiles import load_profiles, select_profile
from ..brain.memory import BrainDB
from ..agents.action_executor import ActionExecutor
from ..agents.aum import AUM
from ..agents.bsm import BSM
from ..agents.chatdock import ChatDockAgent
from ..agents.dexter_orchestrator import DexterOrchestrator
from ..agents.adapters.ollama_adapter import OllamaClient

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Dexter Autonomy API",
    description="API for the Dexter Windows automation system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state (initialized in lifespan)
orchestrator: Optional[DexterOrchestrator] = None
bus: Optional[EventBus] = None
brain: Optional[BrainDB] = None


# Pydantic models
class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    response: str
    status: str = "success"
    context: Optional[Dict[str, Any]] = None


class IntentRequest(BaseModel):
    kind: str
    args: Optional[Dict[str, Any]] = None
    source: Optional[str] = "api"


class OCRRequest(BaseModel):
    hwnd: Optional[int] = None
    region: Optional[Dict[str, int]] = None


class Slot(BaseModel):
    id: str = Field(..., description="Unique slot identifier")
    label: str = Field(..., description="Human-readable label")
    description: str = Field(..., description="Slot description")
    endpoint: str = Field(..., description="API endpoint URL")
    api_key_env: Optional[str] = Field(None, description="Environment variable for API key")
    model: str = Field(..., description="Model name")
    temperature: float = Field(0.2, ge=0.0, le=2.0, description="Temperature parameter")
    system_prompt: Optional[str] = Field(None, description="System prompt")
    ollama_options: Optional[Dict[str, Any]] = Field(None, description="Additional Ollama options")


class SlotsResponse(BaseModel):
    slots: Dict[str, Slot]
    hash: str


class MemoryQuery(BaseModel):
    query: str
    limit: Optional[int] = 10
    task_id: Optional[str] = None


# Utility functions
def get_slots_path() -> Path:
    """Get path to slots.yml configuration file."""
    return Path("configs/slots.yml")


def load_slots() -> Dict[str, Any]:
    """Load slots from YAML file."""
    slots_path = get_slots_path()
    if not slots_path.exists():
        return {"slots": {}}
    
    with open(slots_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        return data


def save_slots(data: Dict[str, Any]) -> None:
    """Save slots to YAML file atomically."""
    slots_path = get_slots_path()
    slots_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to temp file first
    temp_path = slots_path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
    
    # Atomic replace
    temp_path.replace(slots_path)


def compute_slots_hash(data: Dict[str, Any]) -> str:
    """Compute hash of slots configuration."""
    import hashlib
    json_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


# Startup/shutdown
@app.on_event("startup")
async def startup():
    """Initialize components on startup."""
    global orchestrator, bus, brain
    
    logger.info("Starting Dexter API bridge...")
    
    try:
        # Initialize event bus
        bus = EventBus()
        
        # Initialize brain
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        brain = BrainDB(data_dir / "brain.db")
        
        # Initialize policy
        profiles_data = load_profiles("configs/denylist.profiles.yml")
        profile = select_profile(profiles_data, "medium")
        policy = CompositeDenyPolicy(profile, overlay=None)
        
        # Initialize agents
        aum = AUM(llm_client=None)  # Will be initialized with orchestrator
        bsm = BSM(brain, llm_client=None)
        executor = ActionExecutor(bus, policy)
        chatdock = ChatDockAgent(bus, policy, executor, aum, bsm, tesseract_path=None)
        
        # Load Dexter config
        dexter_config_path = Path("configs/slots.yml")
        if dexter_config_path.exists():
            with open(dexter_config_path, "r", encoding="utf-8") as f:
                slots_data = yaml.safe_load(f) or {}
                dexter_slot = slots_data.get("slots", {}).get("dexter-orchestrator", {})
        else:
            dexter_slot = {}
        
        # Initialize orchestrator
        orchestrator = DexterOrchestrator(
            bus=bus,
            policy=policy,
            brain=brain,
            executor=executor,
            aum=aum,
            bsm=bsm,
            chatdock=chatdock,
            config=dexter_slot
        )
        
        # Start the event bus
        await bus.start()
        
        logger.info("Dexter API bridge started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start API bridge: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown():
    """Clean up on shutdown."""
    logger.info("Shutting down Dexter API bridge...")
    
    if bus:
        await bus.stop()


# Health endpoints
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "orchestrator_initialized": orchestrator is not None,
        "bus_initialized": bus is not None,
        "brain_initialized": brain is not None,
    }


@app.get("/healthz")
async def healthz():
    """Kubernetes-style health check."""
    return {"status": "ok"}


# Chat endpoints
@app.post("/dexter/chat", response_model=ChatResponse)
async def dexter_chat(request: ChatRequest):
    """Send a message directly to Dexter orchestrator."""
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    try:
        # Create an intent for Dexter
        intent = {
            "target": "dexter",
            "message": request.message,
            "context": request.context or {}
        }
        
        response = await orchestrator.handle_direct_communication(intent)
        return ChatResponse(
            response=response.get("response", ""),
            status=response.get("status", "success"),
            context=response.get("context")
        )
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Intent endpoints
@app.post("/intent")
async def submit_intent(intent: IntentRequest):
    """Submit an intent to the event bus."""
    if bus is None:
        raise HTTPException(status_code=503, detail="Event bus not initialized")
    
    try:
        intent_data = {
            "kind": intent.kind,
            "args": intent.args or {},
            "source": intent.source,
            "timestamp": datetime.utcnow().isoformat()
        }
        await bus.publish(Topic.INTENT, intent_data)
        return {"status": "submitted", "intent": intent_data}
    except Exception as e:
        logger.error(f"Intent submission error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# OCR endpoints
@app.post("/ocr/extract")
async def ocr_extract(request: OCRRequest):
    """Extract text from screen or window via OCR."""
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    try:
        from ..tools.windows.ocr import ocr_hwnd, ocr_screen
        
        if request.hwnd:
            text = ocr_hwnd(request.hwnd)
        else:
            text = ocr_screen()
        
        return {"text": text, "status": "success"}
    except Exception as e:
        logger.error(f"OCR error: {e}", exc_info=True)
        return {"text": "", "status": "error", "error": str(e)}


@app.post("/ocr/region")
async def ocr_region(region: Dict[str, int] = Body(...)):
    """Configure OCR capture region."""
    # Store region configuration (could be saved to config or memory)
    return {"status": "configured", "region": region}


# Slots endpoints
@app.get("/slots", response_model=SlotsResponse)
async def get_slots():
    """Get all configured agent slots."""
    try:
        data = load_slots()
        slots_dict = data.get("slots", {})
        
        # Convert to Slot models
        slots = {}
        for slot_id, slot_data in slots_dict.items():
            slots[slot_id] = Slot(
                id=slot_id,
                label=slot_data.get("label", slot_id),
                description=slot_data.get("description", ""),
                endpoint=slot_data.get("endpoint", ""),
                api_key_env=slot_data.get("api_key_env"),
                model=slot_data.get("model", ""),
                temperature=slot_data.get("temperature", 0.2),
                system_prompt=slot_data.get("system_prompt"),
                ollama_options=slot_data.get("ollama_options")
            )
        
        return SlotsResponse(
            slots=slots,
            hash=compute_slots_hash(data)
        )
    except Exception as e:
        logger.error(f"Error loading slots: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/slots")
async def upsert_slot(slot: Slot):
    """Create or update an agent slot."""
    try:
        data = load_slots()
        
        if "slots" not in data:
            data["slots"] = {}
        
        # Update slot
        data["slots"][slot.id] = {
            "label": slot.label,
            "description": slot.description,
            "endpoint": slot.endpoint,
            "api_key_env": slot.api_key_env,
            "model": slot.model,
            "temperature": slot.temperature,
            "system_prompt": slot.system_prompt,
            "ollama_options": slot.ollama_options
        }
        
        # Remove None values
        data["slots"][slot.id] = {k: v for k, v in data["slots"][slot.id].items() if v is not None}
        
        save_slots(data)
        
        # Broadcast update via event bus
        if bus:
            await bus.publish(Topic.SYSTEM, {
                "event": "SLOTS_UPDATED",
                "hash": compute_slots_hash(data)
            })
        
        return {"status": "ok", "hash": compute_slots_hash(data)}
    except Exception as e:
        logger.error(f"Error upserting slot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/slots/{slot_id}")
async def delete_slot(slot_id: str):
    """Delete an agent slot."""
    try:
        data = load_slots()
        
        if "slots" not in data or slot_id not in data["slots"]:
            raise HTTPException(status_code=404, detail=f"Slot {slot_id} not found")
        
        del data["slots"][slot_id]
        save_slots(data)
        
        # Broadcast update via event bus
        if bus:
            await bus.publish(Topic.SYSTEM, {
                "event": "SLOTS_UPDATED",
                "hash": compute_slots_hash(data)
            })
        
        return {"status": "ok", "hash": compute_slots_hash(data)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting slot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Memory endpoints
@app.post("/memory/query")
async def memory_query(query: MemoryQuery):
    """Query the brain memory."""
    if brain is None:
        raise HTTPException(status_code=503, detail="Brain not initialized")
    
    try:
        results = brain.search(query.query, limit=query.limit, task_id=query.task_id)
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Memory query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/recent")
async def memory_recent(limit: int = 10, task_id: Optional[str] = None):
    """Get recent memory entries."""
    if brain is None:
        raise HTTPException(status_code=503, detail="Brain not initialized")
    
    try:
        entries = brain.get_recent(limit=limit, task_id=task_id)
        return {"entries": entries, "count": len(entries)}
    except Exception as e:
        logger.error(f"Error fetching recent memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Logs endpoints
@app.get("/logs/stream")
async def logs_stream(level: Optional[str] = None, limit: int = 100):
    """Get recent log entries."""
    # This would connect to the actual logging system
    # For now, return a placeholder
    return {
        "logs": [],
        "level": level,
        "limit": limit
    }


@app.get("/logs/export")
async def logs_export():
    """Export logs as JSONL."""
    # This would export actual logs
    # For now, return a placeholder
    return {"status": "not_implemented"}


# Policy endpoints
@app.get("/policy/current")
async def get_current_policy():
    """Get current policy configuration."""
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    try:
        return {
            "mode": orchestrator.policy.mode if hasattr(orchestrator.policy, 'mode') else "unknown",
            "active": True
        }
    except Exception as e:
        logger.error(f"Error fetching policy: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    
    if bus is None:
        await websocket.close(code=1011, reason="Event bus not initialized")
        return
    
    # Create a queue for this websocket connection
    ws_queue: asyncio.Queue = asyncio.Queue()
    
    # Handler to forward events to websocket queue
    async def forward_to_queue(payload: Dict[str, Any], topic: Topic):
        try:
            await ws_queue.put({"topic": topic.value, "payload": payload})
        except Exception as e:
            logger.error(f"Error forwarding to queue: {e}")
    
    # Subscribe handlers for each topic
    topics_to_subscribe = [Topic.INTENT, Topic.EFFECT, Topic.ERROR, Topic.SYSTEM]
    
    for topic in topics_to_subscribe:
        handler = lambda payload, t=topic: forward_to_queue(payload, t)
        bus.subscribe(topic, handler)
    
    try:
        # Task to send queued messages to websocket
        async def send_messages():
            while True:
                try:
                    msg = await ws_queue.get()
                    await websocket.send_json({
                        "topic": msg["topic"],
                        "payload": msg["payload"],
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception as e:
                    logger.error(f"Error sending websocket message: {e}")
                    break
        
        send_task = asyncio.create_task(send_messages())
        
        # Keep connection alive and receive messages
        while True:
            try:
                data = await websocket.receive_text()
                # Echo back for now
                await websocket.send_json({"echo": data})
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
        
        send_task.cancel()
        
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}", exc_info=True)
    finally:
        await websocket.close()


# Outbox endpoints (for Celery integration)
@app.get("/outbox/pending")
async def get_pending_outbox():
    """Get pending outbox items."""
    if brain is None:
        raise HTTPException(status_code=503, detail="Brain not initialized")
    
    try:
        from ..core.outbox import OutboxManager
        outbox = OutboxManager(brain.db)
        items = outbox.get_pending()
        return {"items": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Error fetching outbox: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Dexter Autonomy API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "chat": "/dexter/chat",
            "ocr": "/ocr/extract",
            "slots": "/slots",
            "memory": "/memory/query",
            "intent": "/intent",
            "websocket": "/ws"
        }
    }

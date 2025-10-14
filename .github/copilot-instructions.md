# Dexter-Gliksbot: Comprehensive AI Agent Instructions

> **Target Platform**: Windows Server 2022  
> **Status**: Active Development → Production Hardening  
> **Audience**: AI Agents & Lead Developer  
> **Last Updated**: 2025-01-13 (Architecture Finalized)

---

## 🎯 Quick Start (Essential Facts)

**What is Dexter?**  
A Windows-first AI autonomy platform combining:
- **FastAPI backend** with **triple event bus** architecture (MAIN, COLLAB, PRIVATE)
- **Windows UI automation** (pyautogui, pywinauto, Tesseract OCR)
- **Deny-first security** with global + per-agent policy enforcement
- **Omniscient BSM brain** (observes everything, provides context, learns constantly)
- **Commander Dexter** (executes most actions, monitors everything, supports all agents)
- **General agents** (execute on task, collaborate when idle)
- **WPF Cockpit UI** for 24/7 mission control
- **Celery/Redis** for background tasks

**Core Philosophy**: 
- **Dexter is the commander** - monitors everything, executes constantly, bears responsibility
- **BSM is the brain** - observes everything, learns continuously, provides context
- **General agents execute when on task** - collaborate when idle, use BSM's context
- **Deny-first security** - global + per-agent deny lists, no exceptions

**Primary Workflow**:
```
User → Dexter (deep conversation + action extraction) → 
  ├─→ MAIN bus: Dexter executes/delegates to system agents
  ├─→ COLLAB bus: Idle general agents collaborate in background
  └─→ BSM: Observes EVERYTHING, provides context, learns patterns
Agent assigned task → PRIVATE bus (focused execution, Dexter supports)
BSM continuously: stores memories, builds knowledge graph, updates neural network
```

---

## 🏗️ **FINALIZED ARCHITECTURE (Critical - Read First)**

### **Three Agent Categories**

#### **1. System Agents (Infrastructure)**
| Agent | Role | Executes? | Learns? | Listens To |
|-------|------|-----------|---------|------------|
| **ActionExecutor** | Keyboard/mouse/OCR | ✅ Yes (when commanded) | ❌ No | MAIN bus (INTENT) + PRIVATE bus |
| **ChatDock** | Window OCR capture | ✅ Yes (when commanded) | ❌ No | MAIN bus (INTENT) + PRIVATE bus |

**Rules**: Execute infrastructure only, no strategic thinking, no learning

#### **2. The Brain (BSM) - OMNISCIENT OBSERVER**
| Agent | Role | Executes? | Monitors? | Listens To |
|-------|------|-----------|-----------|------------|
| **BSM** | All-seeing brain, learner, context provider | ❌ No | ✅ **EVERYTHING** | **ALL 3 BUSES** |

**BSM's Critical Jobs**:
1. **Observes EVERYTHING**: Every bus, every action, every word, every screenshot
2. **Stores all interactions**: STM (10GB RAM) + LTM (SQLite persistent)
3. **Learns continuously**: Updates knowledge graph, extracts patterns, trains neural network
4. **Provides context proactively**: Decides what agents need, broadcasts relevant memories
5. **Never executes**: Only observes, stores, learns, provides

**BSM subscribes to ALL buses** (MAIN, COLLAB, ALL PRIVATE buses) - nothing happens without BSM seeing it.

#### **3. The Commander (Dexter) - OMNIPRESENT EXECUTOR**
| Agent | Role | Executes? | Monitors? | Listens To |
|-------|------|-----------|-----------|------------|
| **Dexter** | Commander, supervisor, active executor | ✅ **YES!** (constantly) | ✅ Everything | **ALL 3 BUSES** |

**Dexter's Critical Jobs**:
1. **Converses with user**: Deep interrogation, clarification (merged AUM logic)
2. **Executes commands**: **Most executions come FROM Dexter**
3. **Monitors everything**: All buses, all agents, all tasks
4. **Provides support**: Helps every agent via PRIVATE buses
5. **Bears responsibility**: Commander of entire operation
6. **Validates policy**: Enforces deny lists before every execution
7. **Intervenes in collaboration**: Enters COLLAB bus to guide/refine

**Dexter subscribes to ALL buses** (MAIN, COLLAB, ALL PRIVATE buses) - commands and supports everything.

#### **4. General Agents (The Workforce)**
| Agent | Role | Executes? | Learns? | Listens To |
|-------|------|-----------|-----------|------------|
| **General Agent** | Prompted: Coder, Writer, Scraper, etc. | ✅ Yes (when on task) | ❌ No (BSM does) | Status-dependent (see below) |

**State-Based Behavior**:
- **IDLE**: Listen to MAIN + COLLAB buses → Collaborate actively, propose solutions
- **ON TASK**: Listen to PRIVATE bus ONLY → Focus on mission, execute with full permissions

**Key Rules**:
- ✅ Execute domain tasks (web scraping, coding, writing, file I/O, API calls)
- ✅ Collaborate when idle (propose, refine, critique on COLLAB bus)
- ✅ Receive context from BSM (use knowledge graph, patterns, memories)
- ❌ Never learn (BSM handles all learning)
- ❌ Never execute until user/Dexter assigns task
- ❌ Never decide what context is relevant (BSM decides)

---

### **Three Event Buses (Triple Bus Architecture)**

```python
class TripleBusArchitecture:
    """
    MAIN bus: User ↔ Dexter conversation + system commands
    COLLAB bus: Idle general agents collaborate
    PRIVATE buses: One per agent for on-task communication
    """
    
    def __init__(self):
        # 1. MAIN BUS: Conversation + Commands
        self.main = EventBus(topics=[
            "USER_INPUT",       # User speaks
            "DEXTER_RESPONSE",  # Dexter replies (includes extracted actions)
            "INTENT",           # Commands (mostly from Dexter to system agents)
            "EFFECT",           # Results (system agents report back)
            "ERROR",            # Errors (Dexter handles)
            "TRACE",            # Debug logs (BSM stores)
            "CONTEXT_AVAILABLE" # BSM broadcasts context
        ])
        
        # 2. COLLAB BUS: Idle agent collaboration
        self.collab = EventBus(topics=[
            "OBSERVATION",          # Dexter shares understanding
            "PROPOSAL",             # Agent proposes solution
            "REFINEMENT",           # Agent improves peer's proposal
            "CRITIQUE",             # Agent identifies issues
            "CONSENSUS",            # Agreement reached
            "VOTE_REQUEST",         # Dexter calls vote
            "VOTE_RESPONSE",        # Agent votes
            "DEXTER_INTERVENTION"   # Dexter enters to guide
        ])
        
        # 3. PRIVATE BUSES: Per-agent channels
        self.private = {
            "agent_id": EventBus(topics=[
                "TASK_ASSIGNMENT",  # Dexter/user assigns task
                "PROGRESS",         # Agent reports progress
                "DEXTER_SUPPORT",   # Dexter provides help
                "HELP_REQUEST",     # Agent requests Dexter's help
                "CONTEXT_UPDATE",   # BSM sends relevant context
                "TASK_COMPLETE"     # Agent finished task
            ])
        }
```

**Who Listens Where**:
- **BSM**: ALL buses (MAIN + COLLAB + all PRIVATE) - observes everything
- **Dexter**: ALL buses (MAIN + COLLAB + all PRIVATE) - commands everything
- **System agents**: MAIN bus + own PRIVATE bus
- **General agents (idle)**: MAIN + COLLAB buses (monitor + collaborate)
- **General agents (on task)**: PRIVATE bus ONLY (focus on mission)

---

### **Knowledge & Learning Flow (BSM → Agents)**

```
┌─────────────────────────────────────────────────────────────┐
│ BSM (The All-Seeing Brain)                                  │
├─────────────────────────────────────────────────────────────┤
│ 1. Observes: Every message on every bus                     │
│ 2. Stores: STM (10GB RAM) + LTM (SQLite)                    │
│ 3. Learns: Knowledge graph + Neural patterns + Embeddings   │
│ 4. Decides: What context is relevant RIGHT NOW              │
│ 5. Provides: Broadcasts context to agents proactively       │
└─────────────────────────────────────────────────────────────┘
                    ↓ CONTEXT_AVAILABLE
┌─────────────────────────────────────────────────────────────┐
│ General Agents (Receive BSM's Context)                      │
├─────────────────────────────────────────────────────────────┤
│ - Receive: Past memories, patterns, knowledge graph         │
│ - Use: BSM's intelligence to work smarter                   │
│ - Benefit: "We did this last month, here's what worked"    │
│ - Don't: Learn, store, or decide what's relevant           │
└─────────────────────────────────────────────────────────────┘
```

**Key Distinction**:
- **BSM decides** what context is relevant → **Agents receive** and use it
- **BSM learns** from observations → **Agents benefit** from learned patterns
- **BSM stores** everything → **Agents access** when needed

---

## 📐 Architecture Deep Dive

### **Core Modules** (`dexter_autonomy/`)

#### **1. Event Bus** (`core/event_bus.py`)
**Status**: Needs refactoring to triple bus architecture

**Current**: Single `EventBus` with topics: `INTENT`, `EFFECT`, `ERROR`, `TRACE`, `COUNCIL`, `SYSTEM`

**Target**: Three separate buses:
```python
class TripleBusSystem:
    def __init__(self):
        self.main = EventBus()      # MAIN bus
        self.collab = EventBus()    # COLLAB bus
        self.private = {}           # Dict of PRIVATE buses per agent
```

**Pattern**:
```python
# Dexter publishes to MAIN bus
await main_bus.publish("INTENT", {"to": "action_executor", "kind": "click", ...})

# Idle agents collaborate on COLLAB bus
await collab_bus.publish("PROPOSAL", {"from": "coder", "proposal": {...}})

# On-task agent receives on PRIVATE bus
await private_bus["web_scraper"].publish("CONTEXT_UPDATE", {...})
```

#### **2. Dexter Orchestrator** (`agents/dexter_orchestrator.py`)
- **Central authority**: All intents validated here first
- Loads master deny list from `denylist.master.yml`
- Coordinates multi-agent collaboration via `_generate_collaboration_plan()`
- Maintains conversation history for long, clarifying dialogues with user
- **Never allow actions to bypass Dexter validation**
- Routes validated intents to appropriate field agents (AUM, BSM, ActionExecutor, ChatDock)

**Critical Methods**:
- `validate_intent()` - checks against deny lists before routing
- `handle_intent()` - entry point for all intents
- `_requires_collaboration()` - triggers multi-agent planning
- `send_agent_message()` - broadcasts to council

#### **3. Policy Engine** (`core/policy_overlay.py`)
- **Deny-first security**: Only deny lists exist, never allow-lists
- `CompositeDenyPolicy` merges global + per-agent deny lists
- Checks: processes, file paths, URLs, hotkeys, input patterns, injection detection
- **Single source of truth** (in progress): Unified config file with:
  - Global deny list (master)
  - Per-agent deny lists (fine-tuning)
  - Agent slots (endpoints, models, prompts, params)
  - UI-editable with instant mirroring

**Current Files** (to be merged):
- `configs/denylist.master.yml` - Dexter's override rules
- `configs/denylist.profiles.yml` - Tiered profiles (low/medium/high/paranoid)
- `configs/slots.yml` - Agent LLM configurations
- **TODO**: Consolidate into single `configs/dexter_config.yml`

**Policy Precedence**: Master (global) → Agent-specific overlay

#### **4. Agents** (`agents/`)

**AUM (Action Understanding Model)** (`aum.py`):
- Extracts structured actions from UI text/OCR via LLM
- Returns JSON: `[{"kind": "click", "args": {"x": 100, "y": 200}, "rationale": "..."}]`
- Fallback: Deterministic parser if LLM fails
- Actions: `type`, `hotkey`, `click`, `ocr`

**BSM (Brain/State Model)** (`bsm.py`):
- Summarizes observations into structured data
- Extracts: summary, tags, entities, relations
- Writes to shared brain for knowledge graph building

**ActionExecutor** (`action_executor.py`):
- Executes low-level Windows automation after policy checks
- Normalizes hotkeys (e.g., `CTRL+S` → `ctrl`, `s`)
- Handles: keyboard input, mouse clicks, OCR capture
- **Policy-gated**: Every action validated before execution

**ChatDockAgent** (`chatdock.py`):
- Docks external windows (e.g., ChatGPT) for agentic control
- Performs OCR on window handles
- Routes extracted text to AUM → ActionExecutor pipeline

**Council** (`agents/council/council.py`):
- Lightweight planning agent for multi-agent coordination
- Generates structured plans before execution
- Currently minimal - **needs expansion for rich collaboration**

#### **5. Brain (Shared Memory)** (`brain/`)

**Vision**: Sophisticated, shared learning system across all agents with:
- **Knowledge graph** (entities, relations, edges)
- **Neural patterns table** (learned behaviors)
- **Multi-tier memory**: STM (short-term), LTM (long-term)
- **FTS + semantic search** (SQLite FTS5 + numpy embeddings)
- **Task isolation**: `task_root` and `agent_id` for scoped queries

**Current State**:
- `memory.py` - Basic SQLite with FTS
- `enhanced_memory.py` - Two-tier system (STM/LTM) with embeddings
- `stm_store.py` - In-memory short-term storage
- `migrate.py` - Schema versioning

**TODO** (in progress):
- Implement knowledge graph (expand `edges` table with richer schema)
- Add neural patterns table for learned automation sequences
- Build context-aware retrieval for RAG-style agent responses
- Learning from every interaction (observation → memory → pattern extraction)

**Memory Pattern**:
```python
# Always include task_root and agent_id for isolation
brain.add_memory(
    kind="observation",
    content="User clicked button X",
    meta={"tags": ["ui", "click"], "confidence": 0.95},
    task_root="invoice_processing",
    agent_id="action_executor"
)

# Search with filters
results = brain.search(query="button", task_root="invoice_processing", k=10)
```

#### **6. Outbox Pattern** (`core/outbox.py`)
- **Transactional outbox** for guaranteed at-least-once delivery
- SQLite-backed message queue
- Prevents task loss even if worker crashes
- Used by Celery workers for background tasks

#### **7. Provider Adapters** (`agents/adapters/`)

**Current**: Ollama-only (`ollama_adapter.py`)

**Required** (in progress): Comprehensive multi-provider registry:
- Ollama (local/cloud)
- OpenAI
- Azure OpenAI
- Anthropic
- NVIDIA
- Perplexity
- GitHub Models
- Groq
- LM Studio
- **Custom HTTP endpoints** (generic OpenAI-compatible adapter)

**Implementation Strategy**:
1. Create provider protocol (`agents/providers/base.py`)
2. Implement adapters per provider (`agents/providers/openai_p.py`, etc.)
3. Registry pattern: `PROVIDERS = {name: adapter, ...}`
4. Slots reference provider by name in unified config
5. Response normalization (Ollama vs. OpenAI chat formats)

**Shim Option** (interim): `ollama_shim.py` - drop-in replacement that routes to OpenAI-compatible providers via env vars (`OLLAMA_PROVIDER=nvidia`)

---

## 🚧 In-Progress Features (Critical Path to Production)

### **1. UI Bridge Module** (`ui_bridge/api.py`)
**Status**: Partially implemented, needs completion

**Required Endpoints**:
- ✅ `GET /health`, `GET /healthz` - Basic health checks
- 🔧 `POST /dexter/chat` - Direct Dexter conversation (needs deep integration)
- 🔧 `POST /ocr/extract` - OCR extraction endpoint
- 🔧 `POST /intent` - Intent submission
- 🔧 `POST /memory/*` - Memory CRUD (`/add`, `/search`, `/task/{root}`, `/stats`, `/snapshot`)
- 🔧 `GET /outbox/*` - Outbox management (`/pending`, `/add`, `/process`, `/stats`, `/cleanup`)
- 🔧 `GET /policy/presets`, `POST /policy/profile/update` - Policy management
- 🔧 `GET /slots`, `POST /slots`, `DELETE /slots/{id}` - Agent slot CRUD with FS watcher
- 🔧 `GET /providers` - List available LLM providers
- 🔧 `WS /ws` - WebSocket for real-time events
- 🔧 `POST /ocr/region` - Dynamic OCR capture region

**Health Check Enhancement** (needs implementation):
```python
# Current: shallow checks (mode, slot, orchestrator exists)
# Required: deep checks
{
  "ollama": {"ok": True, "models": [...], "host": "..."},
  "tesseract": {"ok": True, "path": "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"},
  "windows_session": {"ok": True, "desktop_available": True},
  "redis": {"ok": True, "ping": "PONG"},
  "brain": {"ok": True, "size_mb": 45.2, "memory_count": 1523}
}
```

### **2. Windows Tools** (`tools/windows/`)
**Status**: Missing directory structure, logic exists inline

**Required Files** (extract from `action_executor.py`):
- `automation.py` - pyautogui wrappers (click, type, hotkey) with lazy imports
- `ocr.py` - Tesseract integration with `eng.traineddata` management
- `capture.py` - Screen capture via `ImageGrab`

**Hardening** (critical):
```python
# Lazy imports to prevent crashes on headless/non-Windows
try:
    import pyautogui
except ImportError:
    pyautogui = None

def _require_windows():
    if pyautogui is None:
        raise RuntimeError("Windows automation unavailable. Install pyautogui and run on Windows desktop session.")
```

### **3. Unified Configuration** (`configs/`)
**Current**: Multiple files (`dexter.yml`, `slots.yml`, `denylist.master.yml`, `denylist.profiles.yml`, `policy_catalog.yml`, `agents.overlays.yml`)

**Target**: Single `configs/dexter_config.yml` with:
```yaml
version: "1.0"

# Global deny list (applied to all agents)
deny_list:
  global:
    processes:
      patterns: ["*format*", "shutdown*", "rm -rf *"]
    files:
      write_globs: ["C:\\Windows\\**", "C:\\Program Files\\**"]
    network:
      deny_hosts: ["169.254.169.254", "pastebin.com"]
    hotkeys:
      deny: ["ALT+F4", "WIN+R"]
    input:
      max_chars: 10000
      deny_regex: ["(?i)(union|select|insert)", "(?i)(<script|javascript:)"]

# Agent slots with per-agent deny overrides
agents:
  - id: dexter-orchestrator
    name: Dexter Central Orchestrator
    provider: ollama  # or: openai, nvidia, perplexity, etc.
    endpoint: http://127.0.0.1:11434
    model: qwen2.5:3b-instruct
    api_key_env: OLLAMA_API_KEY  # env var name, never store actual keys
    temperature: 0.15
    system_prompt: "You are Dexter..."
    params:
      num_ctx: 8192
      top_p: 0.9
    # Per-agent deny list (merged with global)
    deny_list:
      files:
        write_globs: ["*.exe", "*.dll"]  # Additional restrictions for this agent

  - id: action-executor
    name: Action Executor
    provider: ollama
    # ... (inherits global deny list only)
```

**Implementation**:
- Backend: `configs/config_manager.py` - read/write with atomic file operations
- File watcher: Broadcast `SYSTEM:CONFIG_UPDATED` on external edits
- UI: Live sync with backend via WebSocket + `/config` endpoints
- Migration script: `migrate_configs.py` to consolidate existing files

### **4. Celery/Redis Workers** (`workers/tasks.py`)
**Status**: Required (not optional), needs robust implementation

**Architecture**:
- **Celery**: Long-running tasks, scheduled jobs, agent missions
- **Redis**: Message broker + result backend
- **Outbox pattern**: Ensures task delivery even on crash

**Required Tasks**:
- Email notifications (`outbox/email`)
- Scheduled observations (periodic OCR, monitoring)
- Agent mission execution (delegated by Dexter)
- Background memory processing (embeddings, knowledge graph updates)

**No "Modes"**: System always runs with workers. If Redis unavailable, fail-fast with actionable error.

### **5. WPF Cockpit Mission Control** (`cockpit/DexterCockpit`)
**Status**: ✅ **PRODUCTION READY** - Full implementation + build fixes complete (Oct 14, 2025)

**Build Status**: ✅ 0 Errors, 2 Warnings (LiveCharts compatibility - safe to ignore)

**Completed Components**:
- ✅ Full MVVM architecture (Models, ViewModels, Views, Services)
- ✅ MainWindow with AvalonDock docking system (**Dirkster.AvalonDock 4.72.1** for .NET 8.0)
- ✅ Agent Roster (left sidebar, detachable) with quick actions
- ✅ Chat View with broadcast mode, TTS, microphone support
- ✅ Logs View with 10GB RAM budget and intelligent eviction
- ✅ Performance View with real-time charts (LiveCharts 0.9.7)
- ✅ WebSocket client (5 channels: logs, agents, missions, performance, config)
- ✅ REST API client for agents/missions/logs/config endpoints
- ✅ Dependency injection with Microsoft.Extensions.DependencyInjection
- ✅ Material Design dark theme optimized for 24/7 operations
- ✅ All views fully detachable and resizable
- ✅ **4 clickable launchers** (batch + PowerShell, backend-only + full system)
- ✅ **Integrated into installer** with .NET 8.0 SDK check
- ✅ **All XAML/package issues resolved** (see BUILD-STATUS.md)

**Recent Fixes** (Oct 14, 2025):
1. ✅ Package: `AvalonDock` → `Dirkster.AvalonDock 4.72.1` (commit 083a7c9)
2. ✅ Namespace: Updated XAML to `https://github.com/Dirkster99/AvalonDock` (commit 469ef31)
3. ✅ Structure: Fixed LayoutRoot to have single child (MC3089 error resolved, commit 28d3bb9)

**Documentation**:
- ✅ [BUILD-STATUS.md](BUILD-STATUS.md) - Current build status and verification
- ✅ [COMPLETE-BUILD-FIX-SUMMARY.md](COMPLETE-BUILD-FIX-SUMMARY.md) - Full fix timeline
- ✅ [LAUNCHERS.md](LAUNCHERS.md) - Launcher usage guide
- ✅ [COCKPIT-INTEGRATION.md](COCKPIT-INTEGRATION.md) - Integration summary

**Architecture Overview** (AvalonDock Mission Control):

#### **Layout Zones**
- **Top Bar**: System status | Active missions counter | Agent health indicators
- **Left Sidebar**: Agent roster with real-time status (🟢🟡🔴⚪)
- **Center**: Mission control dashboard (tabs: Active Missions | Agent Live View | Command Console)
- **Center-Right**: Docked windows manager (Unity, QuickBooks, CAD, chatbots)
- **Bottom**: Real-time logs (JSONL stream) + Performance monitor + Policy panel
- **Floating**: OCR Vision panel (live preview, 5 FPS default, adjustable)

#### **Core Components**

**Agent Roster** (Left Sidebar):
- Visual status indicators (green/yellow/red/gray)
- Per-agent metrics: uptime, success rate, current mission
- Quick actions: pause/resume/stop/restart/view logs
- Resource usage: CPU %, memory, API calls/min

**Mission Control Dashboard** (Center):
- **Tab 1 - Active Missions**: Kanban-style cards with progress bars
- **Tab 2 - Agent Live View**: Grid layout, real-time action feeds per agent
- **Tab 3 - Command Console**: Direct Dexter chat + broadcast mode

**Docked Windows Manager** (Center-Right):
- Auto-detected external apps (hwnd tracking)
- OCR preview with confidence heatmap
- Capture controls: auto-interval (5s default), region selector
- Chatbot docking: Anthropic, ChatGPT, Llama, Perplexity as agents
- Actions: "Send to Agent", focus window, manual override

**Real-Time Logs** (Bottom Pane):
- Structured display: timestamp, level, agent, topic, message, correlation ID
- Multi-select filters: level, agent, topic, text search (regex)
- Virtualized list (10GB RAM = ~500M log entries in STM)
- Export: JSONL, CSV
- Visual cues: ERROR rows red, WARN yellow, policy denials highlighted
- LLM-managed eviction: Least important logs moved to LTM when approaching 10GB

**Performance Monitor** (Bottom Tab):
- Event bus stats: messages/sec, queue depths, latency
- Agent performance: actions/min, success rate, avg duration
- System resources: CPU, memory, Redis queue, brain size
- Charts: LiveCharts WPF (actions over time, success/failure by agent)

**OCR Vision Panel** (Floating/Dockable):
- Live screen capture: 5 FPS default (user-adjustable up to 30 FPS)
- OCR overlay: bounding boxes, confidence scores, click targets
- AI annotations: AUM-detected UI elements highlighted
- Recording toggle + frame freeze/step controls
- Chatbot output capture: treats LLM chat windows as agent inputs

**Mission Designer** (Modal/Window):
- **Phase 1** (Current): YAML editor with syntax highlighting + validation
- **Phase 4** (Planned): Visual flowchart (drag-drop nodes: action, decision, loop)
- Test mode: dry-run missions step-by-step
- Save as recipes: export to `recipes/*.yml`, load for any agent

**Alert System**:
- Toast notifications + sound alerts (configurable)
- Alert types: agent crashed, mission failed, policy violation, resource threshold
- Cooldown: 15min default per alert type
- Future: Email (Celery), Slack/Teams webhooks, SMS (Twilio)

#### **Memory Management**
- **STM (RAM)**: 10GB budget for logs + agent state
- **Eviction Strategy**: LLM (embedding model) scores importance, evicts lowest to LTM
- **LTM (SQLite)**: Persistent storage, never deleted, searchable via FTS + semantic embeddings
- **Learning**: All interactions feed knowledge graph + neural patterns

#### **Technical Stack** (.NET 8.0)
```xml
<!-- AvalonDock: Dirkster fork for .NET 8.0 support -->
<PackageReference Include="Dirkster.AvalonDock" Version="4.72.1" />
<PackageReference Include="Dirkster.AvalonDock.Themes.VS2013" Version="4.72.1" />

<!-- LiveCharts: 0.9.7 works perfectly on .NET 8.0 (2 warnings safe to ignore) -->
<PackageReference Include="LiveCharts.Wpf" Version="0.9.7" />

<!-- Material Design + other packages -->
<PackageReference Include="MaterialDesignThemes" Version="4.9.0" />
<PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
<PackageReference Include="WebSocketSharp-netstandard" Version="1.0.1" />
<PackageReference Include="CommunityToolkit.Mvvm" Version="8.2.2" />
```

**Important Notes**:
- ✅ **AvalonDock**: Must use `Dirkster.AvalonDock` (not old `AvalonDock` package)
- ✅ **LiveCharts**: 0.9.7 generates NU1701 warnings (safe - .NET Framework lib works on .NET 8.0)
- ✅ **XAML Namespace**: Use `xmlns:xcad="https://github.com/Dirkster99/AvalonDock"`
- ✅ **LayoutRoot**: Can only have ONE direct child (wrap everything in single LayoutPanel)

#### **WebSocket Channels**
```
WS /ws/logs          # Real-time log stream (TRACE, ERROR topics)
WS /ws/agents        # Agent status updates (heartbeat, status changes)
WS /ws/missions      # Mission progress updates
WS /ws/performance   # System metrics (1sec interval)
WS /ws/config        # Config change notifications
```

#### **Design System**
- **Theme**: Dark mode for 24/7 use (#1E1E1E background, #007ACC primary)
- **Typography**: Segoe UI Semibold (headers), Consolas 11pt (logs)
- **Icons**: Material Design (👤 agent, 🎯 mission, 👁️ OCR, 📋 logs, 📊 performance)

#### **Multi-Monitor Support**
- Each pane can "pop out" to separate window
- Layout saved to `layout.json`, restored on startup
- Recommended: Monitor 1 (roster + dashboard), Monitor 2 (docked windows), Monitor 3 (charts)

#### **Critical Implementation Notes**
- Remove all "Unknown NL command" placeholders
- Proper error reporting (HTTP status + message + fix instructions)
- OCR never auto-posts to chat (explicit "Send to agent" only)
- Streaming token display with stop button
- Agent limit: 10 concurrent (UI tested up to 20, backend unlimited)

### **6. Test Suite Consolidation** (`tests/`)
**Current**: Mix of pytest suite + standalone scripts at root

**Cleanup Plan**:
- Move all standalone tests (`test_outbox.py`, `test_enhanced_features.py`, etc.) into `tests/`
- Standardize fixtures (`conftest.py`)
- Add integration tests for full stack (start uvicorn, hit endpoints)
- Windows-specific CI (GitHub Actions on `windows-latest`)

**Testing Pattern**:
```python
@pytest.fixture
def dexter_stack():
    """Full stack fixture: EventBus, BrainDB, Dexter, all agents"""
    bus = EventBus()
    brain = BrainDB()
    policy = CompositeDenyPolicy(...)
    executor = ActionExecutor(bus, policy, tesseract_path)
    # ... wire up all agents
    yield DexterOrchestrator(...)
    # teardown

async def test_intent_flow(dexter_stack):
    """Test full INTENT → validation → execution → EFFECT flow"""
    intent = {"kind": "type_text", "args": {"text": "hello"}}
    result = await dexter_stack.handle_intent(intent)
    assert result["status"] == "ok"
```

---

## 🔒 Security & Policy (Deny-First Mandate)

### **Core Principles**
1. **Never add allow-lists** - only deny lists permitted
2. **Two-tier deny lists**: Global (master) + per-agent overrides
3. **Dexter validates everything** - no bypass paths
4. **Injection detection**: SQL, XSS, command injection patterns built-in

### **Policy Workflow**
```python
# Every action goes through policy check
allowed, reason = policy.allow_input("user text")
if not allowed:
    await bus.publish(Topic.EFFECT, {"status": "denied", "reason": reason})
    return

# Then execute
await action_executor.execute(...)
```

### **Adding Deny Rules**
1. Edit unified config YAML (global or per-agent section)
2. Policy engine reloads automatically (FS watcher)
3. Test with dry-run mode first (`?dry_run=true` on endpoints)

---

## 🧠 Brain & Memory (Shared Learning System)

### **Vision**
A sophisticated, shared brain that learns from every interaction:
- **Knowledge Graph**: Entities, relations, temporal edges
- **Neural Patterns**: Learned automation sequences (e.g., "invoice processing" → click sequence pattern)
- **Context-Aware Retrieval**: RAG-style memory for agent responses
- **Multi-Agent Sharing**: All agents read/write to same brain, collaborative learning

### **Current Implementation**
- SQLite with WAL mode (concurrent access)
- FTS5 for full-text search
- Basic edges table (src, rel, dst)
- Enhanced memory with STM/LTM tiers + numpy embeddings

### **TODO** (Critical)
1. **Expand knowledge graph**:
   ```sql
   CREATE TABLE entities (
       id INTEGER PRIMARY KEY,
       type TEXT,  -- person, app, file, action, etc.
       name TEXT,
       properties JSON,
       first_seen REAL,
       last_seen REAL
   );
   
   CREATE TABLE relations (
       id INTEGER PRIMARY KEY,
       src_entity_id INTEGER,
       relation_type TEXT,  -- "clicks", "opens", "requires", "follows"
       dst_entity_id INTEGER,
       confidence REAL,
       observed_count INTEGER,
       ts REAL
   );
   ```

2. **Neural patterns table**:
   ```sql
   CREATE TABLE patterns (
       id INTEGER PRIMARY KEY,
       name TEXT,  -- "invoice_entry_flow"
       description TEXT,
       actions JSON,  -- Serialized action sequence
       success_rate REAL,
       execution_count INTEGER,
       learned_from TEXT,  -- task_root or agent_id
       embedding BLOB  -- For pattern similarity search
   );
   ```

3. **Learning loop**:
   - Observation → Memory → Pattern extraction
   - Similar pattern recognition via embeddings
   - Success/failure tracking for reinforcement
   - Agent queries brain for "have we done this before?" insights

### **Memory API Guidelines**
```python
# Always scope by task and agent
memory_id = brain.add_memory(
    kind="automation_sequence",
    content="Clicked 'Submit', typed invoice #12345, pressed Enter",
    meta={
        "tags": ["invoice", "success"],
        "actions": [...],
        "duration_ms": 1234
    },
    task_root="invoice_processing_2024",
    agent_id="action_executor"
)

# Search with semantic similarity + task scope
similar = brain.search(
    query="invoice submission workflow",
    task_root="invoice_processing_2024",
    k=5
)
```

---

## 🗂️ Repository Structure & Cleanup Plan

### **Current State**
- Scattered launchers (`Launch-Dexter.bat`, `Start-Dexter.ps1`, `start.py`)
- Legacy test scripts at root
- Incomplete module stubs
- `.vs/` artifacts in repo (should be gitignored)

### **Production Structure** (Target)
```
Dexter-Gliksbot/
├── dexter_autonomy/          # Core package
│   ├── agents/               # All agents + providers
│   │   ├── providers/        # LLM provider adapters
│   │   ├── dexter_orchestrator.py
│   │   ├── aum.py, bsm.py, action_executor.py, chatdock.py
│   │   └── council/
│   ├── brain/                # Shared memory system
│   ├── core/                 # Event bus, outbox, policy
│   ├── tools/                # Windows automation (NEW)
│   │   └── windows/          # automation.py, ocr.py, capture.py
│   ├── ui_bridge/            # FastAPI app (complete endpoints)
│   └── workers/              # Celery tasks
├── cockpit/                  # WPF UI (redesigned)
├── configs/                  # Unified config
│   └── dexter_config.yml     # Single source of truth
├── tests/                    # Consolidated test suite
├── scripts/                  # Utilities (migrations, setup)
├── data/                     # Runtime data (brain.db, logs)
├── memory-bank/              # Long-term context (AI learning)
├── .github/
│   ├── copilot-instructions.md  # This file
│   └── workflows/            # CI (Windows Server 2022 tests)
├── requirements.txt
├── pyproject.toml
├── start.py                  # Single entry point
└── Install-Dexter.ps1        # Installer (Tesseract, Ollama, Redis, venv)
```

### **Cleanup Checklist**
- [ ] Remove duplicate launchers (keep `start.py` only)
- [ ] Migrate standalone test scripts to `tests/`
- [ ] Add `.vs/` to `.gitignore`
- [ ] Remove empty/stub files after integrating logic
- [ ] Consolidate config files → `dexter_config.yml`
- [ ] Extract Windows tools from `action_executor.py` → `tools/windows/`
- [ ] Complete `ui_bridge/api.py` endpoints
- [ ] Add `README-cockpit.md` for WPF build instructions

---

## 🚀 Developer Workflows

### **Starting Dexter** (Production)
```bash
# Install dependencies (one-time)
./Install-Dexter.ps1 -Model qwen2.5:3b-instruct -Port 8765

# Start full stack (Celery workers + FastAPI)
python start.py --port 8765
```

**What `start.py` Does**:
1. Checks dependencies (fail-fast if missing)
2. Runs database migrations (`brain/migrate.py`)
3. Verifies Redis connection (required)
4. Starts Celery worker + beat
5. Launches uvicorn (`ui_bridge/api.py`)
6. Prints service URLs and health check endpoint

### **Testing**
```bash
# Run full suite
pytest tests/ -v

# Run specific test
pytest tests/test_dexter.py::test_intent_flow -v

# With coverage
pytest tests/ --cov=dexter_autonomy --cov-report=html
```

### **Linting**
```bash
# Check
ruff check .

# Fix auto-fixable issues
ruff check --fix .
```

**Ruff Config** (`ruff.toml`):
```toml
line-length = 100
target-version = "py310"
select = ["E", "F", "I"]  # Errors, pyflakes, import sorting
```

### **Configuration Changes**
```bash
# Edit unified config
code configs/dexter_config.yml

# Validate
python scripts/validate_config.py

# Changes auto-reload via FS watcher (no restart needed)
```

### **Adding a New Agent**
1. Create module: `dexter_autonomy/agents/new_agent.py`
   ```python
   class NewAgent:
       def __init__(self, bus: EventBus, policy: CompositeDenyPolicy, ...):
           self.bus = bus
           self.policy = policy
           bus.subscribe(Topic.INTENT, self.handle_intent)
       
       async def handle_intent(self, intent: Dict[str, Any]):
           # Validate with policy first
           allowed, reason = self.policy.allow_action(intent)
           if not allowed:
               await self.bus.publish(Topic.EFFECT, {"status": "denied", "reason": reason})
               return
           # Execute
           result = self.do_work(intent)
           await self.bus.publish(Topic.EFFECT, {"status": "ok", "detail": result})
   ```

2. Register in orchestrator: `dexter_orchestrator.py`
   ```python
   self.new_agent = NewAgent(bus, policy, ...)
   self.active_agents["new_agent"] = {"status": "ready"}
   ```

3. Add to config: `configs/dexter_config.yml`
   ```yaml
   agents:
     - id: new-agent
       name: New Agent
       provider: ollama
       model: llama3.1:8b
       deny_list:  # Optional per-agent restrictions
         files:
           read_globs: ["*.secret"]
   ```

4. Test:
   ```python
   async def test_new_agent(dexter_stack):
       intent = {"kind": "new_agent_action", "args": {...}}
       result = await dexter_stack.handle_intent(intent)
       assert result["status"] == "ok"
   ```

### **Adding a Provider**
1. Create adapter: `dexter_autonomy/agents/providers/custom_provider.py`
   ```python
   from .base import LLMProvider
   
   class CustomProvider(LLMProvider):
       name = "custom"
       
       def health(self) -> Dict[str, Any]:
           # Ping endpoint
           return {"ok": True, "endpoint": self.base_url}
       
       def chat(self, messages: List[Dict], **kwargs) -> Dict[str, Any]:
           # Call API, normalize response
           response = requests.post(f"{self.base_url}/chat", json={...})
           return self._normalize_openai_format(response.json())
   ```

2. Register: `agents/providers/__init__.py`
   ```python
   from .custom_provider import CustomProvider
   PROVIDERS["custom"] = CustomProvider(...)
   ```

3. Use in config:
   ```yaml
   agents:
     - id: test-agent
       provider: custom
       endpoint: https://custom-llm.example.com
       api_key_env: CUSTOM_API_KEY
   ```

---

## 🎓 Patterns & Conventions

### **Event Bus Communication**
**DO**:
```python
# Publish intent → Dexter validates → routed to agent
await bus.publish(Topic.INTENT, {
    "kind": "type_text",
    "args": {"text": "hello"},
    "source": "user",
    "correlation_id": "abc123"
})

# Publish effect after execution
await bus.publish(Topic.EFFECT, {
    "status": "ok",
    "intent": original_intent,
    "detail": {"typed": 5, "duration_ms": 123}
})
```

**DON'T**:
```python
# ❌ Never call agents directly
result = action_executor.execute(...)  # Bypasses Dexter validation!

# ❌ Never skip policy checks
if user_is_admin:  # No concept of admin bypass!
    execute_dangerous_action()
```

### **Policy Validation**
**Always validate before execution**:
```python
# Check input
allowed, reason = policy.allow_input(user_text)
if not allowed:
    return {"error": "denied", "reason": reason}

# Check file access
allowed, reason = policy.allow_path(file_path, write=True)

# Check process
allowed, reason = policy.allow_process(command)

# Check network
allowed, reason = policy.allow_url(url)

# Check hotkey
allowed, reason = policy.allow_hotkey(chord)
```

### **Memory Operations**
**Always include scope**:
```python
# ✅ Good
brain.add_memory(
    kind="observation",
    content="...",
    task_root="current_mission",
    agent_id="action_executor"
)

# ❌ Bad (no scope)
brain.add_memory(kind="observation", content="...")  # Uses default "system"
```

### **Error Handling**
**User-facing errors must be actionable**:
```python
# ✅ Good
raise HTTPException(
    status_code=502,
    detail={
        "code": "provider_unreachable",
        "message": "Model unreachable at http://127.0.0.1:11434. Check if Ollama is running.",
        "fix": "Run 'ollama serve' and verify 'ollama list' shows your model."
    }
)

# ❌ Bad
raise Exception("Error")  # Not helpful!
raise HTTPException(status_code=500, detail="Unknown NL command")  # Placeholder error
```

### **Async/Await**
**All event handlers must be async**:
```python
# ✅ Correct
async def handle_intent(self, intent: Dict[str, Any]):
    result = await self.execute(intent)
    await self.bus.publish(Topic.EFFECT, result)

# ❌ Wrong
def handle_intent(self, intent):  # Not async!
    self.bus.publish(...)  # Missing await!
```

---

## 🔧 Common Issues & Fixes

### **Import Failures (Windows libs)**
**Problem**: `ModuleNotFoundError: pyautogui` on fresh install

**Fix**: Lazy imports in `tools/windows/automation.py`:
```python
try:
    import pyautogui
except ImportError:
    pyautogui = None

def _require_windows():
    if pyautogui is None:
        raise RuntimeError(
            "Windows automation unavailable. "
            "Install: pip install pyautogui pywinauto\n"
            "Ensure running on Windows desktop session (not headless)."
        )
```

### **OCR Failures**
**Problem**: Tesseract not found or `eng.traineddata` missing

**Fix**: `tools/windows/ocr.py` should:
1. Check `tesseract.exe` on PATH
2. Verify `TESSDATA_PREFIX` or default tessdata location
3. Auto-download `eng.traineddata` if missing (with enterprise network considerations)
4. Fail-fast with actionable error if unavailable

### **LLM Provider Unreachable**
**Problem**: Ollama not running, model not pulled

**Fix**: Health check on startup (`/healthz`):
```python
def _check_ollama(host: str, model: str) -> dict:
    try:
        r = requests.get(f"{host}/api/tags", timeout=2)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        if model not in models:
            return {"ok": False, "error": f"Model {model} not found. Run: ollama pull {model}"}
        return {"ok": True, "models": models}
    except Exception as e:
        return {"ok": False, "error": f"Ollama unreachable at {host}. Run: ollama serve"}
```

### **Celery/Redis Connection Issues**
**Problem**: Workers don't start, Redis connection refused

**Fix**: Fail-fast in `start.py`:
```python
def ensure_redis():
    try:
        import redis
        client = redis.Redis(host="localhost", port=6379)
        client.ping()
    except Exception as e:
        print("[ERROR] Redis required but unavailable.")
        print("  Install: https://redis.io/download")
        print("  Start: redis-server")
        sys.exit(1)
```

---

## 📋 Production Readiness Checklist

### **Phase 1: Core Completion** (Critical Path)
- [ ] Complete `ui_bridge/api.py` endpoints (all routes from spec)
- [ ] Extract Windows tools to `tools/windows/` with lazy imports
- [ ] Implement comprehensive provider registry (NVIDIA, Perplexity, GitHub, etc.)
- [ ] Consolidate configs → `dexter_config.yml` (single source of truth)
- [ ] Two-way UI sync with FS watcher
- [ ] Implement deep health checks (`/healthz`)
- [ ] Add dry-run mode to all action endpoints

### **Phase 2: Brain & Memory**
- [ ] Expand knowledge graph schema (entities, relations tables)
- [ ] Implement neural patterns table
- [ ] Build learning loop (observation → pattern extraction)
- [ ] Add context-aware retrieval for RAG

### **Phase 3: UI/UX**
- [ ] WPF cockpit redesign with AvalonDock
- [ ] Remove all "Unknown NL command" placeholders
- [ ] Implement streaming chat with token display
- [ ] Add real-time logs pane with export (JSONL)
- [ ] OCR pane with dynamic capture region

### **Phase 4: Testing & CI**
- [ ] Consolidate test suite (move standalone scripts)
- [ ] Add integration tests (full stack)
- [ ] GitHub Actions CI on Windows Server 2022
- [ ] Smoke tests (health checks, endpoint availability)

### **Phase 5: Packaging & Deployment**
- [ ] `Install-Dexter.ps1` - one-click installer
- [ ] `.env.example` with all required env vars
- [ ] Repository cleanup (remove legacy files)
- [ ] Production-ready `README.md` with quickstart
- [ ] `README-cockpit.md` for WPF build

---

## 🎯 Roadmap to Production

### **Week 1-2: Core Infrastructure**
1. Complete UI Bridge endpoints
2. Provider registry implementation
3. Config consolidation + FS watcher
4. Windows tools extraction with hardening

### **Week 3-4: Brain Enhancement**
1. Knowledge graph schema
2. Neural patterns table
3. Learning loop implementation
4. Memory API refinements

### **Week 5-6: UI/UX Polish**
1. WPF cockpit redesign (AvalonDock)
2. Streaming chat implementation
3. Logs pane with export
4. OCR pane with dynamic capture

### **Week 7-8: Testing & Packaging**
1. Test suite consolidation
2. Integration tests
3. CI setup (Windows Server 2022)
4. Installer + documentation

---

## 📚 Key Files Reference

### **Entry Points**
- `start.py` - Main launcher (migrations → workers → API)
- `Install-Dexter.ps1` - One-click installer (Tesseract, Ollama, Redis, venv)

### **Core Architecture**
- `dexter_autonomy/agents/dexter_orchestrator.py` - Central orchestrator, validation authority
- `dexter_autonomy/core/event_bus.py` - Async pub/sub event system
- `dexter_autonomy/core/policy_overlay.py` - Deny-first security engine
- `dexter_autonomy/core/outbox.py` - Transactional message queue

### **Agents**
- `dexter_autonomy/agents/aum.py` - Action understanding (LLM → structured actions)
- `dexter_autonomy/agents/bsm.py` - Brain/state model (observations → memory)
- `dexter_autonomy/agents/action_executor.py` - Windows automation execution
- `dexter_autonomy/agents/chatdock.py` - External window docking + OCR

### **Brain/Memory**
- `dexter_autonomy/brain/enhanced_memory.py` - Two-tier memory (STM/LTM)
- `dexter_autonomy/brain/memory.py` - Basic SQLite brain
- `dexter_autonomy/brain/migrate.py` - Schema migrations

### **Configuration**
- `configs/dexter_config.yml` - Unified config (target)
- `configs/slots.yml` - Agent LLM slots (current, to be merged)
- `configs/denylist.master.yml` - Global deny list (current)

### **Tests**
- `tests/test_dexter.py` - Orchestrator tests
- `tests/test_policy.py` - Policy validation tests
- `tests/test_bus.py` - Event bus tests
- `tests/test_automation_safety.py` - Safety guardrail tests

---

## 🚨 Critical Rules (Never Violate)

1. **🛡️ Security**: Never bypass Dexter validation. All intents flow through `handle_intent()`.
2. **🚫 No Allow-Lists**: Only deny lists. Never add exceptions or "admin bypass" logic.
3. **📡 Event Bus Only**: Agents communicate via event bus. No direct method calls between agents.
4. **🧠 Memory Scope**: Always include `task_root` and `agent_id` in memory operations.
5. **⚡ Async Handlers**: All event handlers must be `async def` with `await` on bus operations.
6. **🔍 Policy First**: Validate with `policy.allow_*()` before any automation action.
7. **📝 Actionable Errors**: User-facing errors must include fix instructions, never placeholders.
8. **🎯 Single Source of Truth**: Config lives in `dexter_config.yml`, mirrored to UI instantly.
9. **🪟 Windows First**: Target Windows Server 2022. Cross-platform noted for future only.
10. **🔧 No Legacy**: Remove old code/files after integrating logic. Keep repo clean.

---

## 💬 Communication Patterns

### **User ↔ Dexter Conversations**
- User speaks to Dexter (long, clarifying dialogues)
- Dexter broadcasts to all agents (they witness conversation)
- Dexter coordinates agent collaboration
- Dexter delegates tasks after user confirms intent
- User can broadcast to all OR speak to individual agents

### **Agent Collaboration**
```python
# Dexter initiates collaboration
if self._requires_collaboration(user_message):
    participants = self._resolve_participants()  # ["dexter", "aum", "bsm", "action_executor"]
    plan = await self._generate_collaboration_plan(user_message, participants, context)
    await self._publish_council_event({"event": "collaboration_plan", "plan": plan})

# Agents refine via COUNCIL topic
await bus.publish(Topic.COUNCIL, {
    "from": "aum",
    "to": ["bsm", "action_executor"],
    "message": "Proposed actions: [...]. BSM, can you verify against past patterns?"
})

# Dexter decides and delegates
await self.send_agent_message(
    sender="dexter",
    recipients=["action_executor"],
    message="Approved. Execute action sequence."
)
```

---

## 🔄 Next Steps (Immediate Priorities)

1. **Complete UI Bridge** - Finish all `/dexter/chat`, `/slots`, `/providers`, `/ocr/region` endpoints
2. **Provider Registry** - Implement multi-provider support (NVIDIA, Perplexity priority)
3. **Config Consolidation** - Merge all YAML files into `dexter_config.yml`
4. **Windows Tools Extraction** - Move automation logic to `tools/windows/` with lazy imports
5. **Deep Health Checks** - Verify Ollama, Tesseract, Redis, Brain in `/healthz`
6. **Test Cleanup** - Consolidate standalone scripts into `tests/` directory
7. **Cockpit Redesign Start** - Implement AvalonDock layout, remove NL command errors

---

## 📖 Additional Resources

- **Technical Report**: See `dexter_repo_technical_monetization_report_da.md` for monetization strategy, detailed endpoint specs, and cockpit redesign
- **Memory Bank**: `memory-bank/` contains AI learning context (evolving project knowledge)
- **Policy Catalog**: `configs/policy_catalog.yml` - UI-friendly deny rule definitions
- **Docs**: `docs/dexter_orchestrator.md`, `docs/future_directions.md` - architectural deep dives

---

## 🤝 Working with AI Agents

**When implementing features**:
1. Read this file completely before starting
2. Check "In-Progress Features" section for current priorities
3. Follow patterns & conventions strictly
4. Test with dry-run mode first
5. Update this file if you discover new critical patterns
6. Never remove features without explicit approval

**When stuck**:
1. Review "Common Issues & Fixes"
2. Check relevant test file for examples
3. Inspect event flow: `INTENT → validate → execute → EFFECT`
4. Verify policy allows action (check deny lists)
5. Ask clarifying questions before guessing

**Code quality**:
- Use type hints (`from typing import ...`)
- Write docstrings for complex functions
- Follow ruff rules (E, F, I)
- Add tests for new features
- Log important decisions in memory bank

---

_Last Updated: 2025-01-13_  
_Status: Active Development → Production Hardening_  
_Maintainers: Lead Developer + AI Agents_

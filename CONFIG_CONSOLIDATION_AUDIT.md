# Configuration Consolidation Audit Report
**Generated**: 2025-10-14  
**Status**: Phase 1 - Complete Audit  
**Objective**: Consolidate all configuration into single source of truth (`configs/dexter_config.yml`)

---

## 📋 Executive Summary

### Current State (FRAGMENTED)
- **9 YAML config files** across multiple concerns
- **Hardcoded values** in 15+ Python modules
- **Environment variables** scattered across codebase
- **No unified config manager** - each module loads independently
- **No UI sync mechanism** - manual editing required

### Target State (UNIFIED)
- **1 master config file**: `configs/dexter_config.yml`
- **ConfigManager class**: Atomic read/write, validation, hot-reload
- **File System watcher**: Auto-reload on external changes
- **Two-way UI sync**: Cockpit ↔ Config file via WebSocket
- **Per-agent configuration**: BSM (llama3:8b), Dexter/SONAR PRO, etc.

---

## 🔍 Complete Configuration Inventory

### 1. YAML Configuration Files (`configs/`)

#### A. **dexter.yml** (8 lines) - Basic System Settings
```yaml
server:
  host: 127.0.0.1
  port: 8765
ollama:
  host: "http://127.0.0.1:11434"
tesseract_path: "C:/Program Files/Tesseract-OCR/tesseract.exe"
data_dir: "./data"
collab_dir: "./collaboration"
```
**Issues**: 
- Minimal coverage, doesn't include all system settings
- Missing Redis, Celery, Brain configurations
- No agent definitions

**Status**: ⚠️ INCOMPLETE - Needs expansion

---

#### B. **slots.yml** (97 lines) - Agent LLM Slots
```yaml
slots:
  dexter-orchestrator:
    label: Dexter Central Orchestrator
    endpoint: http://127.0.0.1:11434
    api_key_env: ''
    model: qwen2.5:3b-instruct
    temperature: 0.15
    system_prompt: "You are Dexter..."
    ollama_options:
      num_ctx: 8192
      top_p: 0.9
  
  cloud-deepseek:
    label: Agent
    model: gemma3:1b
    # ...
  
  cloud-kimi:
    label: Cloud Kimi K2
    model: kimi-k2:1t-cloud
    # ...
  
  local-tiny:
    label: Local Tiny Control
    model: qwen2.5:4b-instruct
    # ...
```
**Coverage**:
- ✅ Agent slot definitions
- ✅ LLM model configurations
- ✅ System prompts
- ✅ Ollama-specific options
- ❌ Missing: BSM agent slot
- ❌ Missing: Provider-specific configurations (NVIDIA, Perplexity, etc.)

**Status**: ⚠️ INCOMPLETE - Missing BSM, needs provider expansion

---

#### C. **denylist.master.yml** (118 lines) - Global Security Policy
```yaml
process:
  deny_cmd_patterns:
    - "*format*"
    - "rm -rf /"
    - "shutdown*"
    # ...

files:
  deny_write_globs:
    - "C:\\Windows\\*"
    - "C:\\Program Files\\*"
    - "*.key"
    # ...
  
  deny_read_globs:
    - "*.key"
    - "*.pem"
    # ...

network:
  deny_url_regex:
    - "^http://"
  deny_hosts:
    - "169.254.*.*"
    - "192.168.*.*"
    # ...

hotkeys:
  deny:
    - "CTRL+ALT+DELETE"
    # ...
```
**Coverage**:
- ✅ Comprehensive deny-first security rules
- ✅ Process, file, network, hotkey restrictions
- ✅ Well-structured for policy engine

**Status**: ✅ COMPLETE - Ready for integration

---

#### D. **denylist.profiles.yml** (91 lines) - Tiered Security Profiles
```yaml
mode_default: medium

profiles:
  low:
    label: "Low"
    description: "Baseline guardrails..."
    policy:
      process: { ... }
      files: { ... }
  
  medium:
    label: "Medium"
    description: "Production-friendly..."
    policy:
      process: { ... }
      files: { ... }
      network: { ... }
  
  high:
    label: "High"
    description: "Enterprise security..."
    policy:
      # ...
  
  paranoid:
    label: "Paranoid"
    description: "Maximum lockdown..."
    policy:
      # ...
```
**Coverage**:
- ✅ 4 security profiles (low, medium, high, paranoid)
- ✅ Profile selection mechanism
- ✅ Policy overlays per profile

**Status**: ✅ COMPLETE - Ready for integration

---

#### E. **agents.overlays.yml** (6 lines) - Per-Agent Policy Overrides
```yaml
chatdock:
  windows:
    deny_title_patterns: ["*Production*"]

unity_builder:
  process:
    deny_cmd_patterns: ["*msbuild* /t:Clean*"]
```
**Coverage**:
- ✅ Per-agent deny list overrides
- ✅ Minimal examples (chatdock, unity_builder)
- ❌ Missing: BSM, Dexter, other agents

**Status**: ⚠️ MINIMAL - Needs expansion for all agents

---

#### F. **policy_catalog.yml** (96 lines) - UI-Friendly Policy Definitions
```yaml
catalog:
  process:
    - id: "process.format"
      label: "Format & wipe commands"
      value: "*format*"
      path: "process.deny_cmd_patterns"
  
  files:
    - id: "files.windows"
      label: "Windows directory"
      value: "C:\\Windows\\*"
      path: "files.deny_write_globs"
  
  network:
    - id: "network.http"
      label: "Block plain HTTP"
      value: "^http://"
      path: "network.deny_url_regex"
  
  # ... (more catalog entries)
```
**Coverage**:
- ✅ Human-readable policy descriptions
- ✅ UI-friendly labels and IDs
- ✅ Path mappings for config updates

**Status**: ✅ COMPLETE - Ready for UI integration

---

#### G. **denylist.yml** (Empty or Minimal)
**Status**: 🗑️ DEPRECATED - Replaced by denylist.master.yml

---

### 2. Environment Variables

#### A. **API Keys** (Security-Sensitive)
```bash
# Provider API keys
OLLAMA_API_KEY=           # Ollama Cloud
OLLAMA_CLOUD_KEY=         # Legacy alias
OPENAI_API_KEY=           # OpenAI
NVIDIA_API_KEY=           # NVIDIA NIM
PERPLEXITY_API_KEY=       # Perplexity
GITHUB_TOKEN=             # GitHub Models
GROQ_API_KEY=             # Groq
AZURE_OPENAI_API_KEY=     # Azure OpenAI
ANTHROPIC_API_KEY=        # Anthropic Claude

# SMTP for email notifications
SMTP_HOST=                # Default: smtp.gmail.com
SMTP_PORT=                # Default: 587
SMTP_USER=                # Sender email
SMTP_PASSWORD=            # SMTP password
SMTP_FROM=                # From address
```

**Used In**:
- `dexter_autonomy/agents/providers/base.py` - API key resolution
- `dexter_autonomy/agents/providers/*_provider.py` - All providers
- `dexter_autonomy/workers/tasks.py` - Email tasks

**Status**: ✅ EXISTING - Document in unified config (reference only, never store keys)

---

#### B. **System Configuration**
```bash
# Celery/Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Dexter data directory
DEXTER_DATA_DIR=./data

# Python environment
PYTHONPATH=...
```

**Used In**:
- `dexter_autonomy/workers/tasks.py` - Celery configuration
- `start.py` - Environment setup

**Status**: ⚠️ PARTIAL - Some in code, needs consolidation

---

### 3. Hardcoded Configurations in Python Modules

#### A. **Provider Presets** (`dexter_autonomy/agents/providers/__init__.py`)
```python
PROVIDER_PRESETS = {
    "ollama": {
        "endpoint": "http://127.0.0.1:11434",
        "api_key_env": None,
    },
    "openai": {
        "endpoint": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
    },
    "nvidia": {
        "endpoint": "https://integrate.api.nvidia.com/v1",
        "api_key_env": "NVIDIA_API_KEY",
    },
    # ... 7 more providers
}
```
**Status**: ⚠️ HARDCODED - Should be in unified config

---

#### B. **Collaboration Manager** (`dexter_autonomy/core/collaboration_manager.py`)
```python
CONSENSUS_CONFIG = {
    "winning_threshold": 0.6,   # 60% vote required
    "confidence_floor": 0.7,    # Min 70% confidence
    "min_participants": 2,      # At least 2 agents
    "max_rounds": 3,            # Max refinement rounds
}
```
**Status**: ⚠️ HARDCODED - Should be in unified config

---

#### C. **Dexter Orchestrator** (`dexter_autonomy/agents/dexter_orchestrator.py`)
```python
def _load_master_deny_list(self) -> Dict[str, Any]:
    config_path = Path("configs/denylist.master.yml")
    # Loads file directly, no config manager
```
**Status**: ⚠️ DIRECT FILE ACCESS - Needs config manager

---

#### D. **UI Bridge API** (`dexter_autonomy/ui_bridge/api.py`)
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# At bottom:
uvicorn.run(app, host="0.0.0.0", port=8765)
```
**Status**: ⚠️ HARDCODED - Should be in unified config

---

#### E. **Start Script** (`start.py`)
```python
# Hardcoded defaults
data_dir = repo_root / "data"
# Redis assumed at localhost:6379
client = redis.Redis(host="localhost", port=6379, decode_responses=True)
```
**Status**: ⚠️ HARDCODED - Should read from unified config

---

### 4. Build & Project Configurations

#### A. **pyproject.toml** (Project Metadata)
```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "dexter-autonomy"
version = "0.1.0"
description = "Dexter Autonomy System"
requires-python = ">=3.10"
```
**Status**: ✅ KEEP SEPARATE - Build system config, not runtime

---

#### B. **ruff.toml** (Linting)
```toml
line-length = 100
target-version = "py310"
select = ["E", "F", "I"]
```
**Status**: ✅ KEEP SEPARATE - Development tool config

---

### 5. Cockpit (WPF) Configuration

#### A. **Connection Settings** (C# `Services/ApiClient.cs`)
```csharp
private readonly string _baseUrl = "http://localhost:8765";
private readonly string _wsUrl = "ws://localhost:8765/ws/cockpit";
```
**Status**: ⚠️ HARDCODED - Should read from config file or env var

---

#### B. **UI Settings** (App.config or user settings)
```xml
<!-- Likely locations for WPF settings -->
<appSettings>
  <add key="ApiBaseUrl" value="http://localhost:8765" />
  <add key="WebSocketUrl" value="ws://localhost:8765/ws/cockpit" />
</appSettings>
```
**Status**: 🔍 NEEDS INVESTIGATION - Check cockpit project for config files

---

## 📊 Configuration Coverage Matrix

| **Category** | **Current Files** | **Consolidation Target** | **Status** |
|-------------|-------------------|-------------------------|-----------|
| **System** | dexter.yml (partial) | dexter_config.yml → system | ⚠️ Incomplete |
| **Providers** | slots.yml (Ollama only) + hardcoded presets | dexter_config.yml → providers | ⚠️ Needs expansion |
| **Agents** | slots.yml + missing BSM | dexter_config.yml → agents | ⚠️ Missing BSM |
| **Security** | denylist.master.yml + profiles.yml + overlays.yml | dexter_config.yml → deny_lists | ✅ Ready |
| **Brain** | None (defaults in code) | dexter_config.yml → brain | ❌ Missing |
| **Workers** | Environment vars only | dexter_config.yml → workers | ❌ Missing |
| **UI Bridge** | Hardcoded in api.py | dexter_config.yml → ui_bridge | ❌ Missing |
| **Cockpit** | Hardcoded in C# | dexter_config.yml → cockpit | ❌ Missing |

---

## 🎯 Required Agent Configurations

### BSM Agent (Brain/State Model)
**Requirement**: Use local Ollama `llama3:8b`

**Current State**: ❌ NOT CONFIGURED
- No entry in `slots.yml`
- Code defaults to inline configuration
- Located in: `dexter_autonomy/agents/bsm.py`

**Target Configuration**:
```yaml
agents:
  - id: bsm
    name: Brain & State Model
    description: Observes everything, learns continuously, provides context
    provider: ollama
    endpoint: http://127.0.0.1:11434
    model: llama3:8b
    temperature: 0.2
    system_prompt: |
      You are BSM, the all-seeing brain of Dexter system.
      - Observe every action, conversation, and event
      - Store memories in STM (10GB RAM) and LTM (SQLite)
      - Build knowledge graph continuously
      - Extract patterns from observations
      - Provide context proactively to agents
      - NEVER execute actions, only observe and learn
    params:
      num_ctx: 8192
      top_p: 0.9
      repeat_penalty: 1.05
    # BSM-specific settings
    stm_budget_gb: 10
    ltm_path: ./data/brain.db
    embedding_model: sentence-transformers/all-MiniLM-L6-v2
```

---

### Dexter Orchestrator with SONAR PRO
**Requirement**: Configure for Perplexity SONAR PRO (high-quality reasoning)

**Current State**: ⚠️ PARTIAL
- Entry exists in `slots.yml` as `dexter-orchestrator`
- Uses Ollama `qwen2.5:3b-instruct` (local)
- Missing SONAR PRO configuration

**Target Configuration**:
```yaml
agents:
  - id: dexter-orchestrator
    name: Dexter Central Orchestrator
    description: Commander, supervisor, active executor
    provider: perplexity
    endpoint: https://api.perplexity.ai
    model: sonar-pro  # High-quality reasoning model
    api_key_env: PERPLEXITY_API_KEY
    temperature: 0.15
    system_prompt: |
      You are Dexter, the central orchestrator and manager...
      [Existing comprehensive prompt from slots.yml]
    params:
      max_tokens: 4096
      top_p: 0.9
    # Dexter-specific settings
    conversation_history_limit: 100
    collaboration_enabled: true
    validate_all_intents: true
```

---

## 🔧 Modules Requiring Config Manager Integration

### Priority 1 (Critical Path)
1. ✅ **dexter_orchestrator.py** - Agent initialization, slot loading
2. ✅ **bsm.py** - Brain configuration, model settings
3. ✅ **policy_overlay.py** - Deny list loading
4. ✅ **ui_bridge/api.py** - Server settings, CORS, WebSocket
5. ✅ **start.py** - System initialization, environment setup

### Priority 2 (Important)
6. ⚠️ **providers/__init__.py** - Provider presets
7. ⚠️ **workers/tasks.py** - Celery/Redis configuration
8. ⚠️ **collaboration_manager.py** - Consensus settings
9. ⚠️ **action_executor.py** - Windows automation settings
10. ⚠️ **chatdock.py** - Window docking configuration

### Priority 3 (Nice to Have)
11. 📝 **memory.py** / **enhanced_memory.py** - Brain paths, sizes
12. 📝 **outbox.py** - Queue settings
13. 📝 **aum.py** - Action understanding model settings

---

## 📁 Proposed Unified Config Structure

### `configs/dexter_config.yml` (Single Source of Truth)

```yaml
version: "1.0.0"
last_updated: "2025-10-14T00:00:00Z"

# ============================================================================
# SYSTEM CONFIGURATION
# ============================================================================
system:
  data_dir: "./data"
  collab_dir: "./collaboration"
  log_level: "INFO"
  debug_mode: false

# ============================================================================
# UI BRIDGE (FastAPI Server)
# ============================================================================
ui_bridge:
  host: "0.0.0.0"
  port: 8765
  cors:
    enabled: true
    origins:
      - "http://localhost:*"
      - "http://127.0.0.1:*"
    allow_credentials: true
  websocket:
    ping_interval: 30
    ping_timeout: 10
    max_connections: 100
  rate_limiting:
    enabled: false  # Enable in production
    max_requests_per_minute: 1000

# ============================================================================
# COCKPIT (WPF UI)
# ============================================================================
cockpit:
  api_base_url: "http://localhost:8765"
  websocket_url: "ws://localhost:8765/ws/cockpit"
  reconnect_interval_ms: 5000
  max_reconnect_attempts: 10
  log_buffer_size_mb: 100  # 10GB STM = 100MB UI buffer

# ============================================================================
# PROVIDERS (LLM/API Endpoints)
# ============================================================================
providers:
  # Ollama (Local/Cloud)
  ollama:
    endpoint: "http://127.0.0.1:11434"
    api_key_env: null
    timeout: 60
    default_options:
      num_ctx: 8192
      temperature: 0.15
  
  # OpenAI
  openai:
    endpoint: "https://api.openai.com/v1"
    api_key_env: "OPENAI_API_KEY"
    timeout: 60
  
  # NVIDIA NIM
  nvidia:
    endpoint: "https://integrate.api.nvidia.com/v1"
    api_key_env: "NVIDIA_API_KEY"
    timeout: 60
  
  # Perplexity (SONAR PRO)
  perplexity:
    endpoint: "https://api.perplexity.ai"
    api_key_env: "PERPLEXITY_API_KEY"
    timeout: 120  # Longer for complex queries
  
  # GitHub Models
  github:
    endpoint: "https://models.inference.ai.azure.com"
    api_key_env: "GITHUB_TOKEN"
    timeout: 60
  
  # Groq
  groq:
    endpoint: "https://api.groq.com/openai/v1"
    api_key_env: "GROQ_API_KEY"
    timeout: 30  # Fast inference
  
  # Azure OpenAI
  azure:
    endpoint: "https://{resource}.openai.azure.com"
    api_key_env: "AZURE_OPENAI_API_KEY"
    api_version: "2024-02-15-preview"
    timeout: 60
  
  # LM Studio (Local)
  lm_studio:
    endpoint: "http://localhost:1234/v1"
    api_key_env: null
    timeout: 60
  
  # Anthropic (Claude)
  anthropic:
    endpoint: "https://api.anthropic.com/v1/messages"
    api_key_env: "ANTHROPIC_API_KEY"
    timeout: 120
  
  # Generic OpenAI-compatible
  generic:
    endpoint: null  # User must specify
    api_key_env: null
    timeout: 60

# ============================================================================
# AGENTS (BSM, Dexter, General Agents)
# ============================================================================
agents:
  # Brain & State Model (BSM) - All-Seeing Observer
  - id: bsm
    name: Brain & State Model
    description: Observes everything, learns continuously, provides context
    enabled: true
    provider: ollama
    model: llama3:8b
    temperature: 0.2
    system_prompt: |
      You are BSM, the all-seeing brain of Dexter system.
      Your responsibilities:
      1. OBSERVE: Monitor every action, conversation, event on all buses
      2. STORE: Save all interactions to STM (10GB RAM) and LTM (SQLite)
      3. LEARN: Build knowledge graph, extract patterns, train neural network
      4. PROVIDE: Broadcast relevant context proactively to agents
      5. NEVER EXECUTE: You observe and learn, never take actions
      
      You are omniscient but never act - the brain that remembers everything.
    params:
      num_ctx: 8192
      top_p: 0.9
      repeat_penalty: 1.05
    # BSM-specific settings
    stm_budget_gb: 10
    ltm_path: "./data/brain.db"
    embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
    knowledge_graph_enabled: true
    neural_patterns_enabled: true
    auto_learn: true
    context_broadcast_interval_sec: 30
  
  # Dexter Central Orchestrator - The Commander
  - id: dexter-orchestrator
    name: Dexter Central Orchestrator
    description: Commander, supervisor, active executor
    enabled: true
    provider: perplexity
    model: sonar-pro
    temperature: 0.15
    system_prompt: |
      You are Dexter, the central orchestrator and manager of this autonomy system.
      
      Your primary responsibilities:
      
      1. SAFETY & SECURITY:
         - Maintain absolute control over all system operations
         - Enforce the deny list as the single source of truth
         - Never allow any action that violates the deny list
         - Monitor all field agents and intervene when necessary
      
      2. TEAM MANAGEMENT:
         - Coordinate all field agents performing tasks
         - Track progress of all active operations
         - Provide support and guidance to field agents
         - Allocate resources efficiently across the team
      
      3. KNOWLEDGE & LEARNING:
         - Maintain and update the shared brain/memory system
         - Learn from every interaction to improve future performance
         - Understand user intent at the deepest level through conversation
         - Retain context across long, multi-turn conversations
      
      4. MISSION EXECUTION:
         - Ensure mission accomplishment at every step and level
         - Parse and understand external docked applications (like ChatGPT)
         - Grant agentic abilities to approved docked applications
         - Execute requested commands, scripts, or code that are not denied
      
      5. COMMUNICATION:
         - Have deep, meaningful conversations with the user
         - Understand implicit requests and unspoken needs
         - Provide clear status updates and progress reports
         - Escalate issues when human intervention is required
      
      Remember: You are the diligent, always-on manager who leads with wisdom
      and ensures safe, effective operations.
    params:
      max_tokens: 4096
      top_p: 0.9
    # Dexter-specific settings
    conversation_history_limit: 100
    collaboration_enabled: true
    validate_all_intents: true
    max_concurrent_operations: 10
  
  # Action Executor - System Agent
  - id: action-executor
    name: Action Executor
    description: Windows automation (keyboard, mouse, OCR)
    enabled: true
    provider: null  # Infrastructure agent, no LLM
    # Action executor settings
    tesseract_path: "C:/Program Files/Tesseract-OCR/tesseract.exe"
    ocr_timeout_sec: 5
    click_delay_ms: 100
    type_delay_ms: 50
  
  # ChatDock Agent - System Agent
  - id: chatdock
    name: ChatDock Agent
    description: External window docking and OCR
    enabled: true
    provider: null  # Infrastructure agent, no LLM
    # ChatDock settings
    window_refresh_interval_ms: 500
    ocr_confidence_threshold: 0.8
  
  # General Agent Template (User-defined agents inherit this)
  - id: general-agent-template
    name: General Agent Template
    description: Template for user-created agents
    enabled: false
    provider: ollama
    model: llama3:8b
    temperature: 0.3
    system_prompt: |
      You are a general-purpose agent in the Dexter system.
      - Execute domain tasks (web scraping, coding, writing, file I/O, API calls)
      - Collaborate when idle (propose, refine, critique on COLLAB bus)
      - Receive context from BSM (use knowledge graph, patterns, memories)
      - Never learn (BSM handles all learning)
      - Never execute until user/Dexter assigns task
    params:
      num_ctx: 4096
      top_p: 0.9

# ============================================================================
# DENY LISTS (Global + Per-Agent Overrides)
# ============================================================================
deny_list:
  # Global deny list (applied to ALL agents)
  global:
    process:
      deny_cmd_patterns:
        - "*format*"
        - "rm -rf /"
        - "del /f /s /q *.*"
        - "rd /s /q *.*"
        - "Remove-Item* -Recurse -Force"
        - "Invoke-WebRequest* -OutFile"
        - "Invoke-Expression*"
        - "iptables*"
        - "netsh*"
        - "route*"
    
    files:
      deny_write_globs:
        - "C:\\Windows\\*"
        - "C:\\Program Files\\*"
        - "C:\\Program Files (x86)\\*"
        - "C:\\Users\\*\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\*"
        - "*.key"
        - "*.pem"
        - "*.cer"
        - "*.crt"
        - "id_rsa"
        - "id_dsa"
      
      deny_read_globs:
        - "*.key"
        - "*.pem"
        - "*.cer"
        - "*.crt"
        - "id_rsa"
        - "id_dsa"
        - "*.password"
        - "*.pwd"
      
      deny_dirs:
        - "C:\\Windows\\System32"
        - "C:\\Windows\\SysWOW64"
        - "\\\\?\\GLOBALROOT\\Device\\Harddisk0\\DR0"
    
    network:
      deny_url_regex:
        - "^http://"  # Block plain HTTP
        - ".*\\.onion$"  # Block Tor
      
      deny_hosts:
        - "169.254.*.*"  # IMDS
        - "127.0.0.1"
        - "192.168.*.*"
        - "10.*.*.*"
        - "172.16.*.*"
        # ... (full private range)
    
    hotkeys:
      deny:
        - "CTRL+ALT+DELETE"
        - "CTRL+ALT+ESC"
        - "WIN+R"
        - "ALT+F4"
    
    input:
      max_chars: 10000
      deny_regex:
        - "(?i)(union|select|insert)"  # SQL injection
        - "(?i)(<script|javascript:)"  # XSS
  
  # Per-agent deny list overrides
  agents:
    chatdock:
      windows:
        deny_title_patterns:
          - "*Production*"
          - "*Registry Editor*"
    
    unity_builder:
      process:
        deny_cmd_patterns:
          - "*msbuild* /t:Clean*"
    
    # Add more agent-specific overrides as needed

# ============================================================================
# SECURITY PROFILES (Tiered Deny Lists)
# ============================================================================
security_profiles:
  active_profile: "medium"  # Options: low, medium, high, paranoid
  
  profiles:
    low:
      label: "Low Security"
      description: "Baseline guardrails; block obviously destructive processes."
      # ... (policy from denylist.profiles.yml)
    
    medium:
      label: "Medium Security"
      description: "Production-friendly; expands denylists for secrets, network."
      # ... (policy from denylist.profiles.yml)
    
    high:
      label: "High Security"
      description: "Enterprise security; strict process and file controls."
      # ... (policy from denylist.profiles.yml)
    
    paranoid:
      label: "Paranoid Security"
      description: "Maximum lockdown; minimal automation allowed."
      # ... (policy from denylist.profiles.yml)

# ============================================================================
# BRAIN (Shared Memory & Learning)
# ============================================================================
brain:
  database_path: "./data/brain.db"
  stm_budget_gb: 10
  ltm_retention_days: 365
  
  # Knowledge graph settings
  knowledge_graph:
    enabled: true
    entity_types:
      - "person"
      - "app"
      - "file"
      - "action"
      - "command"
    relation_types:
      - "clicks"
      - "opens"
      - "requires"
      - "follows"
      - "depends_on"
  
  # Neural patterns (learned automation sequences)
  neural_patterns:
    enabled: true
    min_observations: 3  # Min times to observe before pattern
    similarity_threshold: 0.85
  
  # Embeddings
  embeddings:
    model: "sentence-transformers/all-MiniLM-L6-v2"
    dimension: 384
    batch_size: 32
  
  # Search
  search:
    fts_enabled: true
    semantic_search_enabled: true
    max_results: 50

# ============================================================================
# WORKERS (Celery/Redis Background Tasks)
# ============================================================================
workers:
  # Celery configuration
  celery:
    broker_url: "redis://localhost:6379/0"
    result_backend: "redis://localhost:6379/0"
    task_serializer: "json"
    result_serializer: "json"
    accept_content: ["json"]
    timezone: "UTC"
    enable_utc: true
  
  # Redis configuration
  redis:
    host: "localhost"
    port: 6379
    db: 0
    password: null
    socket_timeout: 5
  
  # Task settings
  tasks:
    email_notifications:
      enabled: true
      smtp_host_env: "SMTP_HOST"
      smtp_port_env: "SMTP_PORT"
      smtp_user_env: "SMTP_USER"
      smtp_password_env: "SMTP_PASSWORD"
    
    scheduled_observations:
      enabled: false
      interval_minutes: 60
    
    memory_processing:
      enabled: true
      batch_size: 100
      interval_minutes: 5

# ============================================================================
# COLLABORATION (Multi-Agent Coordination)
# ============================================================================
collaboration:
  enabled: true
  
  # Consensus configuration
  consensus:
    winning_threshold: 0.6  # 60% vote required
    confidence_floor: 0.7   # Min 70% confidence
    min_participants: 2     # At least 2 agents
    max_rounds: 3           # Max refinement rounds
  
  # Voting
  voting:
    timeout_seconds: 30
    allow_abstain: true
  
  # Collaboration bus settings
  collab_bus:
    max_proposals_per_session: 10
    refinement_enabled: true
    critique_enabled: true

# ============================================================================
# WINDOWS AUTOMATION
# ============================================================================
windows:
  # OCR (Tesseract)
  ocr:
    tesseract_path: "C:/Program Files/Tesseract-OCR/tesseract.exe"
    language: "eng"
    psm: 3  # Page segmentation mode
    oem: 3  # OCR Engine mode
    timeout_seconds: 5
  
  # Mouse/Keyboard
  automation:
    click_delay_ms: 100
    type_delay_ms: 50
    hotkey_delay_ms: 200
    fail_safe: true  # Move mouse to corner to abort
    fail_safe_corner: "top-left"
  
  # Screen capture
  capture:
    default_region: null  # Full screen
    capture_interval_ms: 200

# ============================================================================
# LOGGING & MONITORING
# ============================================================================
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  
  # File logging
  file:
    enabled: true
    path: "./data/logs/dexter.log"
    max_size_mb: 100
    backup_count: 10
  
  # Console logging
  console:
    enabled: true
    colored: true
  
  # Structured logging (JSON)
  structured:
    enabled: true
    path: "./data/logs/dexter.jsonl"

# ============================================================================
# DEVELOPMENT & DEBUG
# ============================================================================
development:
  debug_mode: false
  mock_windows_automation: false
  disable_policy_checks: false  # NEVER enable in production
  test_mode: false
```

---

## 🛠️ Implementation Plan

### Phase 1: Config Manager Foundation ✅ CURRENT
- [x] Complete repository audit
- [ ] Create `configs/config_manager.py` (next step)
- [ ] Implement atomic read/write operations
- [ ] Add YAML validation against schema
- [ ] Add file system watcher for hot-reload

### Phase 2: Unified Config Creation
- [ ] Create `configs/dexter_config.yml` with all sections
- [ ] Migrate data from existing YAML files
- [ ] Add BSM agent configuration
- [ ] Add Dexter/SONAR PRO configuration
- [ ] Add all provider presets
- [ ] Add hardcoded settings from Python modules

### Phase 3: Code Refactoring
- [ ] Update `dexter_orchestrator.py` to use ConfigManager
- [ ] Update `bsm.py` to use ConfigManager
- [ ] Update `policy_overlay.py` to use ConfigManager
- [ ] Update `ui_bridge/api.py` to use ConfigManager
- [ ] Update `start.py` to use ConfigManager
- [ ] Update `providers/__init__.py` to use ConfigManager
- [ ] Update `workers/tasks.py` to use ConfigManager
- [ ] Update all other modules (10+ files)

### Phase 4: UI Integration
- [ ] Add config endpoints to `ui_bridge/api.py`:
  - `GET /config` - Get full config
  - `GET /config/{section}` - Get section
  - `PUT /config/{section}` - Update section
  - `POST /config/reload` - Force reload
- [ ] Add WebSocket event: `CONFIG_CHANGED`
- [ ] Update Cockpit UI to consume config API
- [ ] Implement two-way sync: UI ↔ File

### Phase 5: Testing & Validation
- [ ] Unit tests for ConfigManager
- [ ] Integration tests for config loading
- [ ] Test hot-reload mechanism
- [ ] Test UI sync (edit file → UI updates)
- [ ] Test UI sync (edit UI → file updates)
- [ ] End-to-end testing with all agents

### Phase 6: Documentation & Cleanup
- [ ] Update README with config instructions
- [ ] Create CONFIG_GUIDE.md for users
- [ ] Document all config sections
- [ ] Deprecate old config files
- [ ] Migration guide for existing users

---

## 🚨 Critical Requirements

### 1. Never Store API Keys in Config File
```yaml
# ✅ CORRECT - Reference environment variable
api_key_env: "PERPLEXITY_API_KEY"

# ❌ WRONG - Never store actual keys
api_key: "pplx-abc123..."  # NEVER DO THIS
```

### 2. Atomic File Operations
```python
# All config writes must be atomic (write to temp → rename)
def save_config(config: dict) -> None:
    temp_path = config_path.with_suffix(".tmp")
    temp_path.write_text(yaml.safe_dump(config))
    temp_path.replace(config_path)  # Atomic rename
```

### 3. Validation Before Write
```python
# Validate config against schema before saving
def validate_config(config: dict) -> Tuple[bool, List[str]]:
    errors = []
    # Check required sections
    # Validate data types
    # Check deny list structure
    return len(errors) == 0, errors
```

### 4. File System Watcher
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path == config_path:
            # Reload config
            # Broadcast CONFIG_CHANGED event
            # Notify all agents
```

### 5. Backward Compatibility
```python
# Support old config files during migration period
def load_config_with_fallback() -> dict:
    if unified_config.exists():
        return load_unified_config()
    else:
        # Merge old configs
        return merge_legacy_configs()
```

---

## 📚 Next Steps

1. **Create ConfigManager** (`configs/config_manager.py`)
2. **Implement dexter_config.yml** (full structure)
3. **Refactor Dexter Orchestrator** (use ConfigManager)
4. **Refactor BSM** (add to config, use ConfigManager)
5. **Add Config Endpoints** (FastAPI routes)
6. **Integrate with Cockpit** (two-way sync)
7. **Test & Validate** (unit + integration tests)

---

**End of Audit Report**

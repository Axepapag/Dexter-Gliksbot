# Dexter-Gliksbot Architecture Summary

**Date**: October 16, 2025  
**Status**: Confirmed via code inspection

---

## Executive Summary

Dexter-Gliksbot is a multi-agent autonomy system with a sophisticated brain/memory architecture. The system has **NO separate action executor agent** - instead, **Dexter (the orchestrator) IS the action executor** for most operations, and all agents can execute commands they need behind the deny list policy.

---

## Agent Architecture

### Primary Agents

1. **Dexter (DexterOrchestrator)** - `dexter_autonomy/agents/dexter_orchestrator.py`
   - **Role**: Central orchestrator, decision maker, safety enforcer
   - **LLM**: Google Gemini 2.5 Pro (thinking enabled)
   - **Capabilities**:
     - Conversations and user interaction
     - Multi-agent coordination
     - **Action execution** (merged with former ActionExecutor functionality)
     - Policy enforcement (deny list)
     - Mission planning and execution
   - **Key Feature**: Can extract and execute actions in single LLM call
   - **Authority**: HIGHEST - master controller

2. **BSM (Brain/State Model)** - `dexter_autonomy/agents/bsm.py`
   - **Role**: Omniscient observer, learner, context provider
   - **LLM**: Google LearnLM 1.5 Pro Experimental
   - **Capabilities**:
     - Subscribes to ALL buses (MAIN, COLLAB, all PRIVATE)
     - Observes EVERYTHING happening in the system
     - Stores all interactions for learning
     - Provides intelligent context proactively to agents
     - **NEVER executes actions** - only observes/stores/learns/provides
   - **Architecture**: BSM → Observes → Stores → Learns → Provides Context

3. **ActionExecutor** - `dexter_autonomy/agents/action_executor.py`
   - **Status**: Component class, NOT a separate agent
   - **Purpose**: Utility class for low-level automation with policy guardrails
   - **Used By**: Dexter orchestrator
   - **Functions**:
     - `handle_intent()` - Execute single intent (type_text, hotkey, click, ocr)
     - `run_actions()` - Execute sequence of actions
     - Policy enforcement at execution time
   - **Note**: This is an **implementation detail** of Dexter, not an independent agent

4. **General Agents** - `dexter_autonomy/agents/general_agent.py`
   - **Role**: Flexible multi-purpose agents
   - **Behavior**:
     - When ON TASK: Focus entirely on mission, execute with full capability
     - When IDLE: Collaborate with other agents, propose improvements
   - **LLM**: OpenAI GPT-4o-mini (configurable)
   - **Count**: Multiple instances can be spawned (general-agent-1, general-agent-2, etc.)

5. **ChatDock Agent** - `dexter_autonomy/agents/chatdock.py`
   - **Role**: Bridge to docked applications
   - **Purpose**: Grant agentic abilities to approved applications

6. **AUM (Action Understanding Module)**
   - **Status**: Merged into Dexter's action extraction capabilities
   - **Original Purpose**: Parse text into structured actions
   - **Current**: Dexter handles this internally

---

## Brain & Memory Architecture

### 1. Knowledge Graph (`dexter_autonomy/brain/knowledge_graph.py`)

**YES - There IS a knowledge graph!**

- **Architecture**: Hybrid SQLite + NetworkX
  - **SQLite**: Persistent storage (767 lines of code)
  - **NetworkX**: In-memory graph for algorithms (PageRank, shortest path, community detection)
  - **Embeddings**: sentence-transformers (all-MiniLM-L6-v2, 384 dimensions)

**Database Schema**:

```sql
-- Entities table
CREATE TABLE entities (
    id INTEGER PRIMARY KEY,
    type TEXT,              -- agent, mission, collaboration, observation, action
    name TEXT,
    properties TEXT,        -- JSON
    embedding BLOB,         -- 384-dim vector
    first_seen REAL,
    last_seen REAL,
    UNIQUE(type, name)
);

-- Relations table  
CREATE TABLE relations (
    id INTEGER PRIMARY KEY,
    src_entity_id INTEGER,
    relation_type TEXT,     -- executed_by, collaborated_with, preceded_by, etc.
    dst_entity_id INTEGER,
    confidence REAL,        -- Bayesian Beta distribution
    observed_count INTEGER,
    metadata TEXT,          -- JSON with alpha/beta params
    created_at REAL,
    updated_at REAL
);

-- Patterns table
CREATE TABLE patterns (
    id INTEGER PRIMARY KEY,
    pattern_type TEXT,      -- action_sequence, collaboration_pattern, etc.
    pattern_data TEXT,      -- JSON
    occurrences INTEGER,
    confidence REAL,
    first_seen REAL,
    last_seen REAL,
    metadata TEXT           -- JSON
);

-- Graph snapshots (for debugging)
CREATE TABLE graph_snapshots (
    snapshot_time REAL,
    entity_count INTEGER,
    relation_count INTEGER,
    pattern_count INTEGER,
    metadata TEXT           -- JSON: top_entities, graph_density
);
```

**Key Features**:

- **Bayesian Confidence Updates**: Uses Beta distribution (α, β parameters)
- **Event-driven Sync**: SQLite ↔ NetworkX syncs after 100 updates
- **Pattern Extraction**: Minimum 3 occurrences to consider pattern
- **Semantic Search**: Vector embeddings for similarity queries
- **10 Core Queries**: Designed for BSM context-aware intelligence

**Entity Types**:
- `AGENT` - General agents, Dexter, BSM
- `MISSION` - User-assigned tasks
- `COLLABORATION` - CollaborationManager sessions
- `OBSERVATION` - BSM-captured context snapshots
- `ACTION` - Executed intents (click, type, OCR)

**Relation Types**:
- `EXECUTED_BY` - Mission → Agent
- `COLLABORATED_WITH` - Agent ↔ Agent
- `PROPOSED_BY` - Proposal → Agent
- `PRECEDED_BY` - Action → Action (temporal sequence)
- `CAUSED_BY` - Error → Action
- `RESOLVED_BY` - Issue → Solution
- `OBSERVED_IN` - Action → Observation
- `PART_OF` - Action → Mission
- `SIMILAR_TO` - Mission ↔ Mission

**Intelligence Queries**:
1. `find_similar_missions()` - Cosine similarity search
2. `find_expert_agents()` - Agents with high success rate for mission type
3. `get_successful_collaboration_patterns()` - High-confidence collaborations
4. `trace_error_causes()` - Walk CAUSED_BY edges to find root cause
5. `find_synergistic_agents()` - PageRank for agent compatibility
6. `extract_action_sequences()` - Common action patterns (automation)

### 2. Patterns Table

**YES - There IS a patterns table!**

Located in the Knowledge Graph schema (see above). Patterns are:
- Extracted from recurring behaviors (min 3 occurrences)
- Tracked with confidence scores (Bayesian)
- Timestamped (first_seen, last_seen)
- Typed by pattern_type (action_sequence, collaboration_pattern, etc.)
- Used for automation and prediction

**Pattern Types Supported**:
- `action_sequence` - Common UI automation sequences
- Collaboration patterns (implicit from relations)
- Error-resolution patterns (via CAUSED_BY/RESOLVED_BY chains)

### 3. BrainDB (Basic Memory) (`dexter_autonomy/brain/memory.py`)

**Simple SQLite-based memory store**:

```sql
-- Memories table
CREATE TABLE memories (
    id INTEGER PRIMARY KEY,
    kind TEXT,
    content TEXT,
    meta TEXT,              -- JSON
    ts REAL,
    task_root TEXT DEFAULT 'default',
    agent_id TEXT DEFAULT 'system',
    embedding BLOB
);

-- Full-text search
CREATE VIRTUAL TABLE memories_fts USING fts5(
    content,
    content='memories',
    content_rowid='id'
);

-- Edges (simple relationships)
CREATE TABLE edges (
    id INTEGER PRIMARY KEY,
    src INTEGER,
    rel TEXT,
    dst INTEGER,
    ts REAL
);

-- LTM tokens (long-term memory)
CREATE TABLE ltm_tokens (
    id TEXT PRIMARY KEY,
    text TEXT,
    embedding BLOB,
    task_root TEXT,
    agent_id TEXT,
    meta TEXT,
    size INTEGER,
    atime REAL,
    refs TEXT
);
```

**Features**:
- FTS5 full-text search
- Task-based isolation (namespace: task_root)
- Agent-specific memories (agent_id)
- Embedding support for semantic search
- LTM/STM separation (10GB RAM budget for STM)

### 4. Time Machine (`dexter_autonomy/brain/time_machine.py`)

**Advanced temporal state management** (925 lines):

**Features**:
- Timeline event logging with FTS5 search
- State snapshots with GZIP compression (50-80% size reduction)
- SHA256 integrity validation
- Rollback system with preview and dry-run
- Automatic periodic snapshots
- Retention policies
- 12 REST API endpoints

**Event Categories**:
- AGENT_ACTION, USER_INPUT, SYSTEM_EVENT, COLLAB, ERROR, SECURITY

**Event Severity**:
- DEBUG, INFO, WARNING, ERROR, CRITICAL

---

## Neural Network?

**NO traditional neural network** is directly implemented in the codebase. However:

1. **Sentence Transformers** (all-MiniLM-L6-v2):
   - Pre-trained transformer model for embeddings
   - 384-dimensional vectors
   - Used for semantic similarity in Knowledge Graph

2. **LLMs as "Neural Networks"**:
   - Gemini 2.5 Pro (Dexter)
   - LearnLM 1.5 Pro (BSM)
   - These ARE neural networks, just accessed via API

3. **Future Potential**:
   - NetworkX graph could support GNN (Graph Neural Networks)
   - Embeddings could be fine-tuned with local training
   - Pattern extraction could feed into reinforcement learning

---

## Security Architecture

### Deny List Policy (`configs/dexter_config.yml`)

**Philosophy**: Deny-first (only explicitly denied = blocked)

**Global Deny List** (applies to ALL agents):
- **Processes**: Format, shutdown, taskkill, system deletion
- **Files**: Windows/, System32/, .sys, .dll, .exe
- **Network**: Metadata endpoints, internal domains
- **Input**: ALT+F4, CTRL+ALT+DEL, WIN+R, taskbar, desktop

**Per-Agent Overrides** (ADDITIONAL restrictions):
- `action-executor`: No .bat, .cmd, .ps1, no PowerShell/cmd

**Enforcement Points**:
1. Dexter (pre-execution policy check)
2. ActionExecutor (runtime guardrails)
3. CompositeDenyPolicy (merged global + per-agent rules)

---

## Communication Architecture

### Triple Bus System (`dexter_autonomy/core/triple_bus.py`)

1. **MAIN Bus** - Public coordination
   - Topics: INPUT, INTENT, EFFECT, ERROR, TRACE, CONTEXT_AVAILABLE
   - Subscribers: All agents monitor, Dexter primarily interacts

2. **COLLAB Bus** - Multi-agent collaboration
   - Topics: PROPOSAL, REFINEMENT, CRITIQUE, VOTE, CONSENSUS
   - Used when multiple agents work together

3. **PRIVATE Buses** - Agent-specific
   - Per-agent private channels
   - BSM monitors ALL private buses (omniscient)
   - Context updates from BSM

---

## Configuration

**Unified Config**: `configs/dexter_config.yml`

Consolidates (as of Oct 16, 2025):
- `configs/slots.yml` (agent LLM configuration) ✓
- `configs/denylist.yml` (security policy) ✓
- `configs/denylist.master.yml` (master deny list) ✓
- `configs/policy_catalog.yml` (policy definitions) ✓
- `configs/agents.overlays.yml` (per-agent overrides) ✓
- `configs/dexter.yml` (general settings) ✓

**Migration Script**: `scripts/migrate_configs.py`

---

## Key Takeaways

1. ✅ **NO separate action executor agent** - Dexter IS the executor
2. ✅ **All agents CAN execute commands** (behind deny list)
3. ✅ **Knowledge Graph EXISTS** - SQLite + NetworkX hybrid
4. ✅ **Patterns table EXISTS** - Part of Knowledge Graph
5. ✅ **NO traditional neural network** - Uses LLMs and sentence transformers
6. ✅ **BSM is omniscient observer** - Sees everything, executes nothing
7. ✅ **Bayesian confidence** - Beta distribution for relation/pattern strength
8. ✅ **Semantic search** - 384-dim embeddings via sentence-transformers

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    DEXTER ORCHESTRATOR                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  User Input  │  │  LLM Chat    │  │ Action Exec  │      │
│  │  Handler     │→ │  (Gemini)    │→ │ (Integrated) │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ↕                    ↕                  ↕            │
└─────────────────────────────────────────────────────────────┘
                            ↕
         ┌──────────────────────────────────────────┐
         │         TRIPLE BUS SYSTEM                 │
         │  ┌────────┐ ┌────────┐ ┌────────────┐   │
         │  │  MAIN  │ │ COLLAB │ │  PRIVATE   │   │
         │  └────────┘ └────────┘ └────────────┘   │
         └──────────────────────────────────────────┘
                    ↕           ↕         ↕
         ┌─────────────────┐   │         │
         │   BSM (BRAIN)   │───┘         │
         │  ┌───────────┐  │             │
         │  │ Observer  │  │             │
         │  │ (LearnLM) │  │             │
         │  └───────────┘  │             │
         └─────────────────┘             │
                 ↕                        ↕
    ┌────────────────────────────────────────────┐
    │         BRAIN / MEMORY LAYER               │
    │  ┌──────────────┐   ┌──────────────┐     │
    │  │ Knowledge    │   │  BrainDB     │     │
    │  │ Graph        │   │  (SQLite+FTS)│     │
    │  │ (SQLite+NX)  │   └──────────────┘     │
    │  │              │   ┌──────────────┐     │
    │  │ • Entities   │   │ Time Machine │     │
    │  │ • Relations  │   │ (Snapshots)  │     │
    │  │ • Patterns   │   └──────────────┘     │
    │  │ • Embeddings │                         │
    │  └──────────────┘                         │
    └────────────────────────────────────────────┘
                 ↕
    ┌────────────────────────────────────────────┐
    │         GENERAL AGENTS (Pool)              │
    │  ┌──────────┐  ┌──────────┐  ┌──────────┐│
    │  │ Agent-1  │  │ Agent-2  │  │ Agent-N  ││
    │  │ (GPT-4o) │  │ (GPT-4o) │  │ (GPT-4o) ││
    │  └──────────┘  └──────────┘  └──────────┘│
    └────────────────────────────────────────────┘
```

---

## References

### Source Files Inspected
- `dexter_autonomy/agents/bsm.py` - BSM observer agent
- `dexter_autonomy/agents/dexter_orchestrator.py` - Dexter orchestrator
- `dexter_autonomy/agents/action_executor.py` - Action execution utility
- `dexter_autonomy/brain/knowledge_graph.py` - Knowledge graph (767 lines)
- `dexter_autonomy/brain/memory.py` - Basic memory store
- `dexter_autonomy/brain/migrate.py` - Database migrations
- `dexter_autonomy/brain/time_machine.py` - Temporal state management
- `configs/dexter_config.yml` - Unified configuration

### Documentation
- `BSM_TIME_MACHINE_IMPLEMENTATION_SUMMARY.md` - Time Machine features

---

**Last Updated**: October 16, 2025  
**Verified By**: GitHub Copilot CLI code inspection

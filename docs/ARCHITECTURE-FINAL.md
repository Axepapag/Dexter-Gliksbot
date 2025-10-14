# Dexter-Gliksbot: Final Architecture Specification

> **Version**: 1.0  
> **Date**: 2025-01-13  
> **Status**: Finalized & Ready for Implementation

---

## 🎯 Executive Summary

Dexter-Gliksbot is a Windows-first AI autonomy platform with **three event buses**, **four agent categories**, and an **omniscient learning brain**. The system enables:

1. **Deep user conversations** (Dexter interrogates user to understand intent)
2. **Background collaboration** (idle agents refine solutions while user talks)
3. **Focused execution** (on-task agents execute with full permissions, BSM's context)
4. **Continuous learning** (BSM observes everything, builds knowledge graph)
5. **Command & support** (Dexter executes most actions, supports all agents)

---

## 🏗️ Agent Categories

### **1. System Agents (Infrastructure)**

| Agent | Role | Executes? | Learns? | Listens To |
|-------|------|-----------|---------|------------|
| **ActionExecutor** | Keyboard, mouse, OCR | ✅ On command | ❌ No | MAIN (INTENT) + PRIVATE |
| **ChatDock** | Window OCR capture | ✅ On command | ❌ No | MAIN (INTENT) + PRIVATE |

**Characteristics**:
- Pure execution, no strategic thinking
- No learning, no context awareness
- Subscribe to MAIN bus for commands
- Subscribe to own PRIVATE bus for direct communication

**Example**: User → Dexter → MAIN/INTENT → ActionExecutor executes click → EFFECT published

---

### **2. The Brain (BSM) - Omniscient Observer**

| Agent | Role | Executes? | Monitors? | Listens To |
|-------|------|-----------|-----------|------------|
| **BSM** | All-seeing brain | ❌ Never | ✅ **EVERYTHING** | **ALL 3 BUSES** |

**Critical Jobs**:
1. **Observes EVERYTHING**: Every bus, every action, every word, every screenshot
2. **Stores all interactions**: STM (10GB RAM) + LTM (SQLite)
3. **Learns continuously**: Knowledge graph + neural patterns + embeddings
4. **Decides context**: Intelligently determines what agents need
5. **Provides context**: Broadcasts CONTEXT_AVAILABLE, sends CONTEXT_UPDATE

**Subscriptions**: ALL buses (MAIN, COLLAB, ALL PRIVATE) - nothing escapes BSM

**Example Flow**:
```
User mentions "invoice processing"
  ↓
BSM (observing MAIN bus):
  - Hears keyword "invoice"
  - Searches STM/LTM: finds 15 past invoice memories
  - Queries knowledge graph: invoice entities, past workflows
  - Queries neural patterns: "invoice_processing_workflow" pattern
  - BSM DECIDES: Agents need this context
  ↓
BSM → MAIN bus: "CONTEXT_AVAILABLE" {memories, patterns, entities}
  ↓
General agents receive context, use it to propose smarter solutions
```

**Key Principle**: BSM never executes, only observes/stores/learns/provides

---

### **3. The Commander (Dexter) - Omnipresent Executor**

| Agent | Role | Executes? | Monitors? | Listens To |
|-------|------|-----------|-----------|------------|
| **Dexter** | Commander, supervisor | ✅ **YES!** (constantly) | ✅ Everything | **ALL 3 BUSES** |

**Critical Jobs**:
1. **Converses with user**: Deep interrogation, clarification (merged AUM logic)
2. **Executes commands**: **Most executions come FROM Dexter**
3. **Monitors everything**: All buses, all agents, all tasks
4. **Provides support**: Helps every agent via PRIVATE buses
5. **Bears responsibility**: Commander of entire operation
6. **Validates policy**: Enforces global + per-agent deny lists
7. **Intervenes in collaboration**: Enters COLLAB bus to guide/refine

**Subscriptions**: ALL buses (MAIN, COLLAB, ALL PRIVATE) - commands everything

**Example Flow**:
```
USER → MAIN: "Click the Submit button"
  ↓
DEXTER (listening on MAIN):
  - Converses: "I'll click Submit for you"
  - Extracts action via LLM: {"kind": "click", "args": {"x": 450, "y": 300}}
  - Validates policy: ✓ Allowed
  - EXECUTES: Publishes INTENT → ActionExecutor
  ↓
ActionExecutor executes → EFFECT published
  ↓
DEXTER (monitoring EFFECT):
  - Sees success
  - Responds to user: "✓ Clicked Submit button"
  ↓
BSM (observing everything):
  - Stores: "click_action, button=Submit, status=ok"
  - Learns: "button_click_workflow"
```

**Key Principle**: Dexter executes constantly, monitors everything, bears responsibility

---

### **4. General Agents (The Workforce)**

| Agent | Role | Executes? | Learns? | Listens To |
|-------|------|-----------|-----------|------------|
| **General Agent** | Prompted role (Coder, Writer, Scraper) | ✅ On task | ❌ No (BSM does) | Status-dependent |

**State Machine**:
- **IDLE**: Listen to MAIN + COLLAB → Collaborate actively
- **ON TASK**: Listen to PRIVATE only → Focus on mission

**Characteristics**:
- Execute domain tasks (web scraping, coding, writing, file I/O, API calls)
- Collaborate when idle (propose, refine, critique on COLLAB bus)
- Receive context from BSM (use BSM's knowledge to work smarter)
- Never learn (BSM handles all learning)
- Never execute until user/Dexter assigns task

**Example Flow (Idle → On Task → Idle)**:
```
1. IDLE STATE (Listening to MAIN + COLLAB):
   User: "I need to scrape 50 competitor websites"
     ↓
   Web Scraper (idle, listening to MAIN):
     - Generates proposal: "Use Scrapy + async, 2sec delays"
     - Publishes to COLLAB bus
     ↓
   Other idle agents collaborate:
     - Coder: "Add proxy rotation for rate limiting"
     - Writer: "Suggest output format: JSON"
     ↓
   (Collaboration continues while Dexter interrogates user)

2. TASK ASSIGNMENT:
   Dexter finishes conversation → Assigns Web Scraper
     ↓
   Web Scraper receives TASK_ASSIGNMENT on PRIVATE bus
     ↓
   Web Scraper:
     - Switches status: idle → on_task
     - Unsubscribes from MAIN + COLLAB (focus mode)
     - Subscribes to PRIVATE bus only

3. ON TASK STATE (Executing with BSM's context):
   Web Scraper:
     - Has BSM's context (past scraping memories, learned patterns)
     - Executes web scraping (HTTP requests, HTML parsing)
     - Reports PROGRESS to PRIVATE bus
     - Policy-gated (global + agent-specific deny lists)
     ↓
   Dexter (monitoring PRIVATE bus):
     - Provides DEXTER_SUPPORT when agent requests help
     ↓
   BSM (observing PRIVATE bus):
     - Stores: "scraped competitor1.com, found 15 products"
     - Learns: "web_scraping_workflow" (success +1)
     - Updates knowledge graph: new product entities

4. TASK COMPLETE:
   Web Scraper:
     - Publishes TASK_COMPLETE to PRIVATE bus
     - Switches status: on_task → idle
     - Re-subscribes to MAIN + COLLAB
     - Resumes collaborating
```

**Key Principle**: General agents execute with BSM's context, collaborate when idle

---

## 🚌 Triple Event Bus Architecture

### **1. MAIN Bus (User ↔ Dexter + System Commands)**

**Topics**:
- `USER_INPUT` - User speaks
- `DEXTER_RESPONSE` - Dexter replies (includes extracted actions)
- `INTENT` - Commands (mostly from Dexter to system agents)
- `EFFECT` - Results (system agents report back)
- `ERROR` - Errors (Dexter handles)
- `TRACE` - Debug logs (BSM stores)
- `CONTEXT_AVAILABLE` - BSM broadcasts context

**Subscribers**:
- Dexter (all topics)
- BSM (all topics)
- System agents (INTENT only)
- General agents when IDLE (USER_INPUT, DEXTER_RESPONSE, CONTEXT_AVAILABLE)

**Purpose**: User conversation + system-level commands

---

### **2. COLLAB Bus (Idle Agent Collaboration)**

**Topics**:
- `OBSERVATION` - Dexter shares understanding
- `PROPOSAL` - Agent proposes solution
- `REFINEMENT` - Agent improves peer's proposal
- `CRITIQUE` - Agent identifies issues
- `CONSENSUS` - Agreement reached
- `VOTE_REQUEST` - Dexter calls vote
- `VOTE_RESPONSE` - Agent votes
- `DEXTER_INTERVENTION` - Dexter enters to guide

**Subscribers**:
- Dexter (monitors, intervenes when needed)
- BSM (observes all collaboration)
- General agents when IDLE (propose, refine, critique, vote)

**Purpose**: Background collaboration while user talks to Dexter

---

### **3. PRIVATE Buses (Per-Agent Channels)**

**Topics** (per agent):
- `TASK_ASSIGNMENT` - Dexter/user assigns task
- `PROGRESS` - Agent reports progress
- `DEXTER_SUPPORT` - Dexter provides help
- `HELP_REQUEST` - Agent requests Dexter's help
- `CONTEXT_UPDATE` - BSM sends relevant context
- `TASK_COMPLETE` - Agent finished task

**Subscribers** (per agent's bus):
- The agent itself (always listening to own PRIVATE bus)
- Dexter (monitors all PRIVATE buses, provides support)
- BSM (observes all PRIVATE buses, provides context)

**Purpose**: Focused communication when agent is on task (no distractions from MAIN/COLLAB)

---

## 🧠 Knowledge & Learning Flow

### **BSM's Learning Pipeline**

```
1. OBSERVE (BSM listens to all buses)
   ↓
2. STORE (STM 10GB RAM + LTM SQLite)
   ↓
3. EXTRACT (entities, relations, patterns)
   ↓
4. LEARN (knowledge graph + neural patterns)
   ↓
5. DECIDE (what context is relevant NOW)
   ↓
6. PROVIDE (broadcast to agents)
```

### **Knowledge Graph Schema**

```sql
-- Entities table
CREATE TABLE entities (
    id INTEGER PRIMARY KEY,
    type TEXT,  -- person, app, file, action, competitor, product, etc.
    name TEXT,
    properties JSON,
    first_seen REAL,
    last_seen REAL
);

-- Relations table
CREATE TABLE relations (
    id INTEGER PRIMARY KEY,
    src_entity_id INTEGER,
    relation_type TEXT,  -- "clicks", "opens", "requires", "scrapes", "produces"
    dst_entity_id INTEGER,
    confidence REAL,
    observed_count INTEGER,
    last_observed REAL
);

-- Neural patterns table
CREATE TABLE patterns (
    id INTEGER PRIMARY KEY,
    name TEXT,  -- "invoice_processing_workflow", "web_scraping_workflow"
    description TEXT,
    actions JSON,  -- Serialized action sequence
    success_rate REAL,
    execution_count INTEGER,
    learned_from TEXT,  -- task_root or agent_id
    embedding BLOB  -- For pattern similarity search
);
```

### **Context Provisioning Example**

```python
# BSM observes user mention "invoice"
async def observe(self, msg):
    if "invoice" in msg.get("content", "").lower():
        # Search knowledge graph
        invoice_entities = self.knowledge_graph.query("type:invoice")
        
        # Search neural patterns
        invoice_patterns = self.patterns.search("invoice_processing")
        
        # Search memories
        invoice_memories = self.brain.search("invoice", k=20)
        
        # BSM DECIDES: This is relevant
        context = {
            "keyword": "invoice",
            "entities": invoice_entities,
            "patterns": invoice_patterns,
            "memories": invoice_memories,
            "confidence": 0.95
        }
        
        # BSM PROVIDES to agents
        await self.main_bus.publish("CONTEXT_AVAILABLE", {
            "from": "bsm",
            "context": context,
            "summary": "Loaded 20 invoice memories, 3 learned workflows"
        })
```

### **Agent Uses Context**

```python
# General agent receives BSM's context
async def on_context_available(self, msg):
    context = msg["context"]
    self.current_context = context
    
    # Use context to inform proposal
    proposal = await self.generate_proposal_with_context(
        user_request="Process invoices",
        past_memories=context["memories"],
        learned_patterns=context["patterns"],
        known_entities=context["entities"]
    )
    
    # Propose on COLLAB bus
    await self.collab_bus.publish("PROPOSAL", {
        "from": self.id,
        "proposal": proposal,
        "confidence": 0.88,
        "based_on_context": True
    })
```

**Key Distinction**:
- **BSM decides** what context is relevant → **Agents receive** and use it
- **BSM learns** from observations → **Agents benefit** from learned patterns
- **BSM stores** everything → **Agents access** when needed

---

## 🔒 Policy & Security

### **Deny-First Security Model**

```yaml
# Global deny list (applies to ALL agents)
deny_list:
  global:
    processes:
      patterns: ["*format*", "shutdown*", "rm -rf *", "del C:\\*"]
    files:
      write_globs: ["C:\\Windows\\**", "C:\\Program Files\\**", "/etc/*"]
    network:
      deny_hosts: ["169.254.169.254", "*.gov"]
    hotkeys:
      deny: ["ALT+F4", "WIN+R"]
    input:
      max_chars: 10000
      deny_regex: ["(?i)(union|select|insert)", "(?i)(<script|javascript:)"]

# Per-agent deny lists (additional restrictions)
agents:
  - id: web_scraper
    deny_list:
      network:
        deny_hosts: ["bank.com", "*.gov"]
        rate_limit:
          requests_per_min: 60
  
  - id: coder
    deny_list:
      files:
        write_globs: ["*.exe", "*.dll"]
      commands:
        deny: ["git push --force"]
  
  - id: writer
    deny_list:
      files:
        read_globs: ["*.db", "*.secret"]
      network:
        deny_hosts: ["*"]  # No web requests
```

### **Policy Enforcement**

```python
# Every action checked against global + agent-specific deny lists
def check_policy(agent_id, action):
    # Check global deny list
    if global_deny_list.denies(action):
        return False, "Denied by global policy"
    
    # Check agent-specific deny list
    if agent_id in agent_deny_lists:
        if agent_deny_lists[agent_id].denies(action):
            return False, f"Denied by {agent_id} policy"
    
    return True, None

# Dexter validates before execution
allowed, reason = check_policy("web_scraper", {"kind": "url", "url": "bank.com"})
if not allowed:
    await main_bus.publish("ERROR", {"error": reason})
```

---

## 📊 Complete Communication Flow

### **Example: User Requests Complex Task**

```
Timeline (parallel execution):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MAIN BUS (foreground):
USER: "I need to scrape 50 competitor websites for pricing data"
  ↓
DEXTER: "What format should the output be? CSV or JSON?"
  ↓
USER: "JSON, and store in our PostgreSQL database"
  ↓
DEXTER: "Should I include product descriptions or just prices?"
  ↓
USER: "Prices, features, and contact info"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BSM (background, observing MAIN):
- Hears keywords: "scrape", "competitor", "pricing"
- Searches memories: finds 10 past scraping missions
- Queries knowledge graph: 50 competitor entities
- Queries patterns: "web_scraping_workflow" (success_rate 0.94)
- Broadcasts CONTEXT_AVAILABLE with past learnings
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

COLLAB BUS (background, simultaneous):
Web Scraper (idle): [PROPOSAL] Use Scrapy + async, batch 10 sites
  ↓
Coder (idle): [CRITIQUE] Rate limiting concern, add delays
  ↓
Web Scraper (idle): [REFINEMENT v2] Added 2sec delays + proxies
  ↓
Writer (idle): [PROPOSAL] JSON schema for output format
  ↓
Data Analyst (idle): [REFINEMENT] PostgreSQL bulk insert strategy
  ↓
[CONSENSUS] All agents agree on approach (confidence: 0.92)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DEXTER finishes conversation:
DEXTER → COLLAB: "Solutions ready?"
COLLAB → DEXTER: "Yes, 1 proposal with 92% consensus"
DEXTER: "I approve. Web Scraper, execute this task."
DEXTER → Web Scraper's PRIVATE bus: TASK_ASSIGNMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Web Scraper's PRIVATE BUS (focused execution):
Web Scraper:
  - Receives TASK_ASSIGNMENT
  - Switches: idle → on_task
  - Unsubscribes from MAIN + COLLAB (focus mode)
  - Has BSM's context (past scraping workflows, competitor entities)
  - Executes with full permissions (policy-gated)
  ↓
Web Scraper → PRIVATE: PROGRESS "Scraped 5/50 sites, 10% complete"
  ↓
Web Scraper → PRIVATE: HELP_REQUEST "Competitor23.com has Cloudflare"
  ↓
DEXTER → PRIVATE: DEXTER_SUPPORT "Use Selenium with undetected-chromedriver"
  ↓
Web Scraper → PRIVATE: PROGRESS "Scraped 50/50 sites, 100% complete"
  ↓
Web Scraper → PRIVATE: TASK_COMPLETE
  ↓
Web Scraper: Switches on_task → idle, re-subscribes to MAIN + COLLAB
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BSM (observing Web Scraper's PRIVATE bus):
- Stores: "scraped_competitor1.com, found_15_products"
- Learns: "web_scraping_workflow" execution_count +1
- Updates knowledge graph: new product entities, pricing data
- Updates neural patterns: "competitor_scraping" success_rate → 0.95
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## ✅ Implementation Checklist

### **Phase 1: Core Infrastructure**
- [ ] Refactor `event_bus.py` to support triple bus (MAIN, COLLAB, PRIVATE)
- [ ] Merge AUM into Dexter (action extraction in system prompt)
- [ ] Enhance BSM to omniscient observer (subscribe to all buses)
- [ ] Create `GeneralAgent` base class with state machine (idle/on_task)

### **Phase 2: Knowledge & Learning**
- [ ] Implement knowledge graph (entities, relations tables)
- [ ] Implement neural patterns table
- [ ] BSM context provisioning (CONTEXT_AVAILABLE, CONTEXT_UPDATE)
- [ ] General agents use BSM's context to inform decisions

### **Phase 3: Collaboration**
- [ ] Implement `CollaborationManager` (convergence detection, voting)
- [ ] Idle agents propose on COLLAB bus
- [ ] Agents refine peer proposals
- [ ] Dexter intervenes in collaboration when needed

### **Phase 4: Cockpit UI**
- [ ] Per-agent windows (show bus activity, status, context received)
- [ ] MAIN/COLLAB/PRIVATE bus visualization
- [ ] BSM knowledge graph viewer
- [ ] Dexter command console

### **Phase 5: Testing & Hardening**
- [ ] Integration tests (full stack)
- [ ] Policy enforcement tests (deny lists)
- [ ] Knowledge graph tests (entity/relation extraction)
- [ ] Collaboration convergence tests

---

## 🎓 Key Principles (Never Violate)

1. **🛡️ BSM observes EVERYTHING** - All buses, all actions, all words, all screenshots
2. **🧠 BSM decides context** - Agents don't learn or decide relevance (BSM does)
3. **🎖️ Dexter executes constantly** - Most actions come FROM Dexter
4. **👥 General agents execute on task** - With full permissions, BSM's context
5. **💬 Idle agents collaborate** - On COLLAB bus, while user talks to Dexter
6. **🚫 Deny-first security** - Global + per-agent deny lists, no exceptions
7. **📡 Triple bus architecture** - MAIN (conversation), COLLAB (collaboration), PRIVATE (focus)
8. **🔄 State-based subscriptions** - Idle: MAIN+COLLAB, On-task: PRIVATE only
9. **🤝 Dexter supports all agents** - Via PRIVATE buses, provides help constantly
10. **📚 Knowledge flows BSM → Agents** - BSM provides, agents receive and use

---

**This architecture is finalized and ready for implementation. Let's build it! 🚀**

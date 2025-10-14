# Dexter Architecture Quick Reference

> **One-Page Summary** - Keep this handy while implementing!

---

## 🏗️ Four Agent Categories

| Category | Agents | Executes? | Learns? | Buses |
|----------|--------|-----------|---------|-------|
| **System** | ActionExecutor, ChatDock | ✅ On command | ❌ No | MAIN + PRIVATE |
| **Brain** | BSM | ❌ Never | ✅ Everything | **ALL** |
| **Commander** | Dexter | ✅ **Constantly** | ❌ No | **ALL** |
| **General** | Coder, Writer, Scraper... | ✅ On task | ❌ No | Idle: MAIN+COLLAB<br>Task: PRIVATE |

---

## 🚌 Three Event Buses

### **MAIN** (User ↔ Dexter + System Commands)
Topics: `USER_INPUT`, `DEXTER_RESPONSE`, `INTENT`, `EFFECT`, `ERROR`, `TRACE`, `CONTEXT_AVAILABLE`

### **COLLAB** (Idle Agent Collaboration)
Topics: `OBSERVATION`, `PROPOSAL`, `REFINEMENT`, `CRITIQUE`, `CONSENSUS`, `VOTE_REQUEST`, `VOTE_RESPONSE`, `DEXTER_INTERVENTION`

### **PRIVATE** (Per-Agent Channels)
Topics: `TASK_ASSIGNMENT`, `PROGRESS`, `DEXTER_SUPPORT`, `HELP_REQUEST`, `CONTEXT_UPDATE`, `TASK_COMPLETE`

---

## 🧠 BSM (The All-Seeing Brain)

**Listens To**: ALL buses (MAIN + COLLAB + ALL PRIVATE)  
**Executes**: Never  
**Jobs**:
1. Observe everything
2. Store everything (STM 10GB + LTM SQLite)
3. Learn continuously (knowledge graph + neural patterns)
4. Decide what context agents need
5. Provide context proactively

**Example**:
```python
# BSM observes "invoice" keyword → searches memories → provides context
await main_bus.publish("CONTEXT_AVAILABLE", {
    "from": "bsm",
    "context": {
        "memories": [...],
        "patterns": [...],
        "entities": [...]
    }
})
```

---

## 🎖️ Dexter (The Commander)

**Listens To**: ALL buses (MAIN + COLLAB + ALL PRIVATE)  
**Executes**: YES! (constantly - most executions come from Dexter)  
**Jobs**:
1. Converse with user (deep interrogation)
2. Execute commands directly (merged AUM logic)
3. Monitor everything (all agents, all tasks)
4. Provide support (via PRIVATE buses)
5. Bear responsibility (commander)
6. Validate policy (deny lists)
7. Intervene in collaboration (COLLAB bus)

**Example**:
```python
# Dexter converses AND executes
user_input = "Click Submit button"
response = await llm.chat(user_input)  # "I'll click Submit"
actions = extract_actions(response)    # [{"kind": "click", ...}]
await main_bus.publish("INTENT", {...})  # Execute via ActionExecutor
```

---

## 👥 General Agents (The Workforce)

**State Machine**:
- **IDLE**: Listen to MAIN + COLLAB → Collaborate
- **ON TASK**: Listen to PRIVATE only → Execute

**Example**:
```python
class GeneralAgent:
    def __init__(self):
        self.status = "idle"
        self._enter_idle_mode()
    
    def _enter_idle_mode(self):
        """Idle: Collaborate actively"""
        main_bus.subscribe("USER_INPUT", self.monitor_conversation)
        collab_bus.subscribe("PROPOSAL", self.on_peer_proposal)
    
    def _enter_task_mode(self, task):
        """On task: Focus on mission"""
        main_bus.unsubscribe_all(self)
        collab_bus.unsubscribe_all(self)
        # Only PRIVATE bus now
        await self.execute_task(task)
```

---

## 🔄 Typical Flow

### **Simple Command**
```
USER → MAIN: "Click Submit"
  ↓
DEXTER: Extracts action, validates policy, executes
  ↓
ActionExecutor: Clicks
  ↓
BSM: Observes, stores, learns
```

### **Complex Mission**
```
USER → MAIN: "Scrape 50 websites"
  ↓ (parallel)
DEXTER: Interrogates user            IDLE AGENTS: Collaborate on COLLAB
  ↓                                   ↓
DEXTER: Finishes, reviews proposals  CONSENSUS reached
  ↓
DEXTER → PRIVATE: Assigns Web Scraper
  ↓
Web Scraper: Executes (with BSM's context, Dexter's support)
  ↓
BSM: Observes, learns, updates patterns
```

---

## 📋 Key Rules

1. ✅ **BSM observes EVERYTHING** (all buses)
2. ✅ **BSM decides context** (agents receive)
3. ✅ **Dexter executes constantly** (most actions)
4. ✅ **General agents execute on task** (policy-gated)
5. ✅ **Idle agents collaborate** (COLLAB bus)
6. ❌ **No agent learns** (only BSM)
7. ❌ **No agent decides context** (only BSM)
8. ❌ **No execution until assigned** (user/Dexter)

---

## 🔒 Policy Enforcement

```python
# Every action checked
allowed, reason = policy.check(agent_id, action)
if not allowed:
    await bus.publish("ERROR", {"error": reason})
    return

# Proceed with execution
await execute(action)
```

**Deny Lists**: Global (all agents) + Per-agent (additional restrictions)

---

## 🗂️ Knowledge Graph

```sql
entities (id, type, name, properties, first_seen, last_seen)
relations (id, src, relation_type, dst, confidence, observed_count)
patterns (id, name, actions, success_rate, execution_count, embedding)
```

BSM extracts entities/relations from observations → builds knowledge graph → provides to agents

---

## 📁 File Structure

```
dexter_autonomy/
├── core/
│   ├── event_bus.py          # Triple bus (MAIN, COLLAB, PRIVATE)
│   ├── policy_overlay.py     # Deny-first security
│   └── outbox.py              # Transactional queue
├── agents/
│   ├── dexter_orchestrator.py  # The Commander
│   ├── bsm.py                   # The Brain
│   ├── action_executor.py      # System agent
│   ├── chatdock.py              # System agent
│   └── general_agent.py         # Base class for workforce
├── brain/
│   ├── memory.py                # STM/LTM
│   ├── knowledge_graph.py       # Entities/relations
│   └── neural_patterns.py       # Learned workflows
└── ui_bridge/
    └── api.py                   # WebSocket/REST endpoints
```

---

**Keep this card open while coding!** 🚀

# 🤝 Agent Communication Architecture

## Overview

Agents in Dexter **never call each other directly**. All communication flows through the **Event Bus** using a pub/sub pattern. This ensures loose coupling, scalability, and proper orchestration by Dexter.

---

## 🎯 Core Principle

```
❌ WRONG: Agent A → Agent B (direct call)
✅ RIGHT: Agent A → Event Bus → Agent B (pub/sub)
```

**All communication is mediated by Dexter (the orchestrator).**

---

## 📡 Communication Channels (Event Bus Topics)

The Event Bus has **6 topics** for different types of messages:

```python
class Topic(str, Enum):
    INTENT = "intent"      # User requests, action commands
    EFFECT = "effect"      # Results of actions
    ERROR = "error"        # Error notifications
    TRACE = "trace"        # Debug/trace information
    COUNCIL = "council"    # Multi-agent collaboration
    SYSTEM = "system"      # System events (config changes)
```

---

## 🔄 Communication Patterns

### **Pattern 1: User → Dexter → Agent** (Most Common)

```
┌──────┐   1. User Intent    ┌─────────┐   2. Validate   ┌──────────┐
│ User │ ──────────────────► │ Dexter  │ ───────────────►│ Policy   │
└──────┘                     │ Orchest.│                 │ Engine   │
                             └────┬────┘                 └──────────┘
                                  │
                                  │ 3. Publish to Event Bus
                                  │
                             ┌────▼────┐
                             │ INTENT  │
                             │  Topic  │
                             └────┬────┘
                                  │
                ┌─────────────────┼─────────────────┐
                │                 │                 │
         ┌──────▼──────┐   ┌─────▼────┐   ┌───────▼──────┐
         │    AUM      │   │   BSM    │   │    Action    │
         │  (listening)│   │(listening)│   │  Executor    │
         └──────┬──────┘   └─────┬────┘   └───────┬──────┘
                │                 │                 │
                │ 4. Process      │ 4. Process      │ 4. Execute
                │                 │                 │
         ┌──────▼──────┐   ┌─────▼────┐   ┌───────▼──────┐
         │   Publish   │   │ Publish  │   │   Publish    │
         │   EFFECT    │   │  EFFECT  │   │    EFFECT    │
         └─────────────┘   └──────────┘   └──────────────┘
```

**Example Flow**:
```python
# User says: "Click button at (100, 200)"

# 1. Dexter receives and validates
intent = {"kind": "click", "args": {"x": 100, "y": 200}}
allowed, reason = policy.allow_action(intent)

# 2. Dexter publishes to INTENT topic
await bus.publish(Topic.INTENT, intent)

# 3. ActionExecutor (subscribed to INTENT) receives it
async def handle_intent(self, intent):
    if intent["kind"] == "click":
        self.execute_click(intent["args"]["x"], intent["args"]["y"])
        
# 4. ActionExecutor publishes result to EFFECT topic
await bus.publish(Topic.EFFECT, {
    "status": "ok",
    "detail": {"clicked": True, "duration_ms": 123}
})
```

---

### **Pattern 2: Agent Collaboration (via COUNCIL topic)**

When multiple agents need to work together:

```
┌──────┐   "Collaborate on this task"   ┌─────────┐
│ User │ ──────────────────────────────►│ Dexter  │
└──────┘                                └────┬────┘
                                             │
                                  1. Detect │collaboration needed
                                             │
                                        ┌────▼────┐
                                        │ Council │
                                        │ Topic   │
                                        └────┬────┘
                                             │
                     ┌───────────────────────┼───────────────────────┐
                     │                       │                       │
              ┌──────▼──────┐         ┌──────▼──────┐        ┌──────▼──────┐
              │    AUM      │         │    BSM      │        │   Action    │
              │ (subscribed)│         │ (subscribed)│        │  Executor   │
              └──────┬──────┘         └──────┬──────┘        └──────┬──────┘
                     │                       │                       │
          2. Propose │actions        2. Check│patterns       2. Check│feasibility
                     │                       │                       │
              ┌──────▼──────────────────────▼───────────────────────▼──────┐
              │                  COUNCIL Topic                              │
              │  All agents post their proposals/refinements/feedback      │
              └──────┬──────────────────┬───────────────────┬──────────────┘
                     │                  │                   │
              ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐
              │   Agent A   │    │   Agent B   │    │   Agent C   │
              │   refines   │    │   refines   │    │   refines   │
              └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
                     │                  │                   │
                     └──────────────────┼───────────────────┘
                                        │
                                 3. All post to COUNCIL
                                        │
                                   ┌────▼────┐
                                   │ Dexter  │
                                   │ Reviews │
                                   │ & Decides│
                                   └────┬────┘
                                        │
                                4. Delegate│tasks
                                        │
                                   ┌────▼────┐
                                   │ INTENT  │
                                   │  Topic  │
                                   └─────────┘
```

**Code Example**:
```python
# Dexter detects collaboration needed
if self._requires_collaboration(user_message):
    participants = ["dexter", "aum", "bsm", "action_executor"]
    
    # 1. Broadcast to all agents
    await self._publish_council_event({
        "event": "collaboration_request",
        "goal": "Process invoice #12345",
        "participants": participants,
        "context": {...}
    })
    
# 2. Each agent responds on COUNCIL topic
# AUM:
await bus.publish(Topic.COUNCIL, {
    "from": "aum",
    "to": ["dexter", "bsm", "action_executor"],
    "message": "I can extract data from the invoice using OCR"
})

# BSM:
await bus.publish(Topic.COUNCIL, {
    "from": "bsm",
    "to": ["dexter", "aum"],
    "message": "I've seen similar invoices. Pattern: vendor→amount→date"
})

# Action Executor:
await bus.publish(Topic.COUNCIL, {
    "from": "action_executor",
    "to": ["dexter"],
    "message": "I can click and type the extracted data into QuickBooks"
})

# 3. Dexter reviews all proposals and delegates
await self.send_agent_message(
    sender="dexter",
    recipients=["action_executor"],
    message="Approved. Execute the plan."
)
```

---

### **Pattern 3: Broadcast Messages**

Dexter can broadcast messages to **all agents**:

```python
async def send_agent_message(
    self, 
    sender: str, 
    recipients: Optional[List[str]], 
    message: str
) -> None:
    """
    Send message from one agent to others via COUNCIL topic.
    If recipients is None, broadcasts to all active agents.
    """
    targets = recipients or [
        p for p in self._resolve_participants() 
        if p != sender
    ]
    
    event = {
        "event": "agent_message",
        "from": sender,
        "to": targets,
        "message": message,
    }
    
    # Record in conversation history
    self.conversation_history.append({
        "role": sender, 
        "content": json.dumps(event)
    })
    
    # Publish to COUNCIL topic
    await self._publish_council_event(event)
```

**Usage**:
```python
# Broadcast to all agents
await dexter.send_agent_message(
    sender="dexter",
    recipients=None,  # None = broadcast to all
    message="New policy update: Deny all shutdown commands"
)

# Send to specific agents
await dexter.send_agent_message(
    sender="dexter",
    recipients=["aum", "bsm"],
    message="Analyze this screenshot for invoice data"
)
```

---

## 🔐 Security: Dexter Validates Everything

**Critical Rule**: All intents must pass through Dexter's validation:

```python
async def handle_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
    """All intents go through Dexter first."""
    
    # 1. Check against deny list (policy engine)
    allowed, reason = self.policy.allow_action(intent)
    if not allowed:
        await self.bus.publish(Topic.EFFECT, {
            "status": "denied",
            "reason": reason
        })
        return {"status": "denied", "reason": reason}
    
    # 2. If allowed, route to appropriate agent
    await self.bus.publish(Topic.INTENT, intent)
    return {"status": "ok"}
```

**Flow**:
```
Any Action Request
       │
       ▼
  ┌─────────┐
  │ Dexter  │ ← Central authority
  │ Policy  │
  │ Check   │
  └────┬────┘
       │
   Allowed?
       │
    ┌──┴──┐
   NO    YES
    │      │
    ▼      ▼
 Deny   Publish to
 Effect  Event Bus
```

---

## 📊 Event Bus Implementation

**Key Features**:
1. **Async queues** per topic (1000 message buffer)
2. **Multiple subscribers** per topic
3. **Automatic ID and timestamp** injection
4. **Error handling** (errors published to ERROR topic)

```python
class EventBus:
    def __init__(self):
        # Each topic has its own queue
        self.queues: Dict[Topic, asyncio.Queue] = {
            t: asyncio.Queue(maxsize=1000) for t in Topic
        }
        
        # Each topic can have multiple subscribers
        self.subscribers: Dict[Topic, list[Handler]] = {
            t: [] for t in Topic
        }
    
    async def publish(self, topic: Topic, payload: Dict[str, Any]):
        """Publish message to a topic."""
        # Auto-add ID and timestamp
        if "id" not in payload:
            payload["id"] = str(uuid.uuid4())
        if "ts" not in payload:
            payload["ts"] = time.time()
        
        # Put in queue
        await self.queues[topic].put(payload)
    
    def subscribe(self, topic: Topic, handler: Handler):
        """Subscribe a handler to a topic."""
        self.subscribers[topic].append(handler)
    
    async def _drain(self, topic: Topic):
        """Continuously process messages from a topic."""
        while True:
            msg = await self.queues[topic].get()
            
            # Call all subscribers
            for handler in list(self.subscribers[topic]):
                try:
                    await handler(msg)
                except Exception as exc:
                    # Publish errors to ERROR topic
                    await self.publish(Topic.ERROR, {
                        "error": str(exc),
                        "during": topic.value,
                    })
```

---

## 🎭 Agent Subscription Examples

**Each agent subscribes to relevant topics**:

```python
# Dexter Orchestrator
class DexterOrchestrator:
    def __init__(self, bus: EventBus, ...):
        self.bus = bus
        # Subscribe to ALL topics (central authority)
        bus.subscribe(Topic.INTENT, self.handle_intent)
        bus.subscribe(Topic.COUNCIL, self.handle_council)
        bus.subscribe(Topic.SYSTEM, self.handle_system)

# Action Executor
class ActionExecutor:
    def __init__(self, bus: EventBus, ...):
        self.bus = bus
        # Subscribe to INTENT (for execution commands)
        bus.subscribe(Topic.INTENT, self.handle_intent)
    
    async def handle_intent(self, intent: Dict[str, Any]):
        """Execute validated actions."""
        if intent["kind"] == "click":
            result = self.click(intent["args"]["x"], intent["args"]["y"])
            await self.bus.publish(Topic.EFFECT, {
                "status": "ok",
                "detail": result
            })

# AUM (Action Understanding Model)
class AUM:
    def __init__(self, bus: EventBus, ...):
        self.bus = bus
        # Subscribe to INTENT (for text analysis)
        bus.subscribe(Topic.INTENT, self.handle_intent)
    
    async def handle_intent(self, intent: Dict[str, Any]):
        """Convert text to structured actions."""
        if intent["kind"] == "analyze_text":
            actions = await self.extract_actions(intent["args"]["text"])
            await self.bus.publish(Topic.EFFECT, {
                "status": "ok",
                "actions": actions
            })

# BSM (Brain/State Model)
class BSM:
    def __init__(self, bus: EventBus, ...):
        self.bus = bus
        # Subscribe to EFFECT (to learn from results)
        bus.subscribe(Topic.EFFECT, self.handle_effect)
    
    async def handle_effect(self, effect: Dict[str, Any]):
        """Learn from action results."""
        await self.store_in_memory(effect)
```

---

## 🔄 Complete Communication Flow Example

**Scenario**: User asks Dexter to "Click the Submit button"

```
1. USER SENDS MESSAGE
   User: "Click the Submit button"
   
2. DEXTER RECEIVES (direct communication endpoint)
   - Dexter parses message
   - Determines action needed: click button
   - But where? Needs OCR to find button
   
3. DEXTER BROADCASTS COLLABORATION REQUEST (COUNCIL topic)
   await bus.publish(Topic.COUNCIL, {
       "event": "collaboration_request",
       "goal": "Find and click Submit button",
       "participants": ["dexter", "aum", "chatdock", "action_executor"]
   })
   
4. AGENTS RESPOND (COUNCIL topic)
   
   ChatDock Agent:
   await bus.publish(Topic.COUNCIL, {
       "from": "chatdock",
       "message": "I can capture the screen with OCR"
   })
   
   AUM:
   await bus.publish(Topic.COUNCIL, {
       "from": "aum",
       "message": "I can extract button coordinates from OCR text"
   })
   
   ActionExecutor:
   await bus.publish(Topic.COUNCIL, {
       "from": "action_executor",
       "message": "I can execute the click once coordinates are known"
   })
   
5. DEXTER ORCHESTRATES (INTENT topic)
   
   # Step 1: Get screenshot with OCR
   await bus.publish(Topic.INTENT, {
       "kind": "ocr_capture",
       "target": "chatdock"
   })
   
   # ChatDock responds with OCR results (EFFECT topic)
   await bus.publish(Topic.EFFECT, {
       "status": "ok",
       "ocr_text": "...",
       "coordinates": {"Submit": {"x": 450, "y": 300}}
   })
   
   # Step 2: Dexter validates coordinates against policy
   allowed, reason = policy.allow_click(450, 300)
   
   # Step 3: If allowed, execute click
   await bus.publish(Topic.INTENT, {
       "kind": "click",
       "args": {"x": 450, "y": 300},
       "target": "action_executor"
   })
   
   # ActionExecutor clicks and reports (EFFECT topic)
   await bus.publish(Topic.EFFECT, {
       "status": "ok",
       "detail": {"clicked": True, "duration_ms": 120}
   })
   
6. DEXTER RESPONDS TO USER
   "Clicked Submit button at (450, 300)"
```

---

## 📋 Summary

### ✅ **DO's**:
- ✅ All agents communicate via Event Bus
- ✅ Agents subscribe to topics they care about
- ✅ Dexter validates all intents before execution
- ✅ Use COUNCIL topic for multi-agent collaboration
- ✅ Publish effects after completing actions
- ✅ Handle errors gracefully (ERROR topic)

### ❌ **DON'Ts**:
- ❌ Never call another agent's methods directly
- ❌ Never bypass Dexter's validation
- ❌ Never create direct agent-to-agent connections
- ❌ Never skip policy checks
- ❌ Never use synchronous communication

---

## 🎯 Key Takeaways

1. **Event-Driven**: All communication is async pub/sub via Event Bus
2. **Centralized Authority**: Dexter validates everything
3. **Loose Coupling**: Agents don't know about each other
4. **Scalable**: Add new agents by subscribing to topics
5. **Secure**: Policy engine checks all actions
6. **Observable**: All messages flow through traceable topics

---

**The Event Bus is the nervous system of Dexter** 🧠  
**Dexter is the brain that orchestrates everything** 🎯  
**Agents are the hands that execute actions** 🤲

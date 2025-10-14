# Migrating from Old EventBus to Triple Bus System

This guide helps migrate existing Dexter-Gliksbot code from the old single `EventBus` to the new `TripleBusSystem`.

## What Changed

### Old Architecture (Single Bus)
```python
from dexter_autonomy.core.event_bus import EventBus, Topic

bus = EventBus()
await bus.start()

# All agents used same topics
await bus.publish(Topic.INTENT, {...})
bus.subscribe(Topic.INTENT, handler)
```

### New Architecture (Triple Bus)
```python
from dexter_autonomy.core.triple_bus import TripleBusSystem, MainTopic, CollabTopic, PrivateTopic

buses = TripleBusSystem()
await buses.start_all()

# Three separate buses with specific purposes
await buses.main.publish(MainTopic.INTENT, {...})      # System commands
await buses.collab.publish(CollabTopic.PROPOSAL, {...}) # Idle collaboration  
private = await buses.get_private("agent_id")
await private.publish(PrivateTopic.PROGRESS, {...})    # On-task focus
```

## Topic Migration Map

| Old Topic | New Location | New Topic |
|-----------|--------------|-----------|
| `Topic.INTENT` | MAIN bus | `MainTopic.INTENT` |
| `Topic.EFFECT` | MAIN bus | `MainTopic.EFFECT` |
| `Topic.ERROR` | MAIN bus | `MainTopic.ERROR` |
| `Topic.TRACE` | MAIN bus | `MainTopic.TRACE` |
| `Topic.COUNCIL` | COLLAB bus | `CollabTopic.*` (see below) |
| `Topic.SYSTEM` | MAIN bus | Various (see below) |

### Old COUNCIL → New COLLAB Topics
```python
# Old: Generic COUNCIL topic
await bus.publish(Topic.COUNCIL, {"event": "collaboration_plan", ...})
await bus.publish(Topic.COUNCIL, {"event": "proposal", ...})

# New: Specific COLLAB topics
await buses.collab.publish(CollabTopic.OBSERVATION, {...})
await buses.collab.publish(CollabTopic.PROPOSAL, {...})
await buses.collab.publish(CollabTopic.REFINEMENT, {...})
await buses.collab.publish(CollabTopic.CRITIQUE, {...})
await buses.collab.publish(CollabTopic.CONSENSUS, {...})
await buses.collab.publish(CollabTopic.VOTE_REQUEST, {...})
await buses.collab.publish(CollabTopic.VOTE_RESPONSE, {...})
await buses.collab.publish(CollabTopic.DEXTER_INTERVENTION, {...})
```

### New MAIN Topics
```python
# User conversation (new!)
await buses.main.publish(MainTopic.USER_INPUT, {...})
await buses.main.publish(MainTopic.DEXTER_RESPONSE, {...})
await buses.main.publish(MainTopic.CONTEXT_AVAILABLE, {...})  # BSM broadcasts context

# System commands (existed before as INTENT/EFFECT)
await buses.main.publish(MainTopic.INTENT, {...})
await buses.main.publish(MainTopic.EFFECT, {...})
await buses.main.publish(MainTopic.ERROR, {...})
await buses.main.publish(MainTopic.TRACE, {...})
```

### New PRIVATE Topics (Per-Agent)
```python
private = await buses.get_private("agent_id")
await private.publish(PrivateTopic.TASK_ASSIGNMENT, {...})
await private.publish(PrivateTopic.PROGRESS, {...})
await private.publish(PrivateTopic.DEXTER_SUPPORT, {...})
await private.publish(PrivateTopic.HELP_REQUEST, {...})
await private.publish(PrivateTopic.CONTEXT_UPDATE, {...})  # BSM provides context
await private.publish(PrivateTopic.TASK_COMPLETE, {...})
```

## Migration Steps by File

### 1. dexter_orchestrator.py

**Before:**
```python
from dexter_autonomy.core.event_bus import EventBus, Topic

class DexterOrchestrator:
    def __init__(self, bus: EventBus, ...):
        self.bus = bus
        bus.subscribe(Topic.INTENT, self.handle_intent)
        bus.subscribe(Topic.COUNCIL, self.handle_council)
    
    async def handle_intent(self, intent: dict):
        # Validate and route
        ...
        await self.bus.publish(Topic.INTENT, validated_intent)
    
    async def send_agent_message(self, sender, recipients, message):
        await self.bus.publish(Topic.COUNCIL, {
            "from": sender,
            "to": recipients,
            "message": message
        })
```

**After:**
```python
from dexter_autonomy.core.triple_bus import TripleBusSystem, MainTopic, CollabTopic, PrivateTopic

class DexterOrchestrator:
    def __init__(self, buses: TripleBusSystem, ...):
        self.buses = buses
        
        # Subscribe to MAIN for user input and system commands
        buses.main.subscribe(MainTopic.USER_INPUT, self.on_user_input)
        buses.main.subscribe(MainTopic.INTENT, self.handle_intent)
        buses.main.subscribe(MainTopic.EFFECT, self.on_effect)
        buses.main.subscribe(MainTopic.ERROR, self.on_error)
        
        # Subscribe to ALL COLLAB to monitor/intervene
        for topic in CollabTopic:
            buses.collab.subscribe(topic, self.on_collab_message)
        
        # Will subscribe to PRIVATE buses as they're created
        self.active_private_buses = {}
    
    async def on_user_input(self, msg: dict):
        """Handle user conversation + extract actions"""
        # Deep conversation
        response = await self.converse_with_user(msg["content"])
        
        # Extract actions (merged AUM logic)
        actions = self._extract_actions(response)
        
        # Publish response
        await self.buses.main.publish(MainTopic.DEXTER_RESPONSE, {
            "content": response,
            "actions": actions
        })
        
        # If needs collaboration, broadcast to COLLAB
        if self._requires_collaboration(msg):
            await self.buses.collab.publish(CollabTopic.OBSERVATION, {
                "from": "dexter",
                "observation": self._summarize_user_intent(msg)
            })
    
    async def handle_intent(self, intent: dict):
        """Validate and route system commands"""
        # Existing validation logic
        allowed, reason = self.policy.validate_intent(intent)
        if not allowed:
            await self.buses.main.publish(MainTopic.ERROR, {
                "source": "dexter",
                "reason": reason
            })
            return
        
        # Route to appropriate agent (unchanged)
        await self.buses.main.publish(MainTopic.INTENT, intent)
    
    async def on_collab_message(self, msg: dict):
        """Monitor collaboration, intervene if needed"""
        if self._should_intervene(msg):
            await self.buses.collab.publish(CollabTopic.DEXTER_INTERVENTION, {
                "from": "dexter",
                "intervention": self._generate_guidance(msg)
            })
    
    async def assign_task(self, agent_id: str, task: dict):
        """Assign task to general agent via PRIVATE bus"""
        private = await self.buses.get_private(agent_id)
        
        # Subscribe to this PRIVATE bus to support agent
        if agent_id not in self.active_private_buses:
            for topic in PrivateTopic:
                private.subscribe(topic, self.on_private_message)
            self.active_private_buses[agent_id] = private
        
        # Assign task
        await private.publish(PrivateTopic.TASK_ASSIGNMENT, {
            "from": "dexter",
            "to": agent_id,
            "task": task
        })
    
    async def on_private_message(self, msg: dict):
        """Support agents on their PRIVATE buses"""
        if msg["topic"] == "help_request":
            # Provide support
            support = await self._generate_support(msg)
            agent_id = msg["bus"].split(":")[1]  # "private:agent_id" → "agent_id"
            private = await self.buses.get_private(agent_id)
            await private.publish(PrivateTopic.DEXTER_SUPPORT, {
                "from": "dexter",
                "to": agent_id,
                "support": support
            })
```

### 2. action_executor.py

**Before:**
```python
from dexter_autonomy.core.event_bus import EventBus, Topic

class ActionExecutor:
    def __init__(self, bus: EventBus, ...):
        self.bus = bus
        bus.subscribe(Topic.INTENT, self.on_intent)
    
    async def on_intent(self, intent: dict):
        if intent["kind"] == "click":
            result = self._click(...)
            await self.bus.publish(Topic.EFFECT, result)
```

**After:**
```python
from dexter_autonomy.core.triple_bus import TripleBusSystem, MainTopic

class ActionExecutor:
    def __init__(self, buses: TripleBusSystem, ...):
        self.buses = buses
        
        # Subscribe to MAIN for system commands only
        buses.main.subscribe(MainTopic.INTENT, self.on_intent)
    
    async def on_intent(self, msg: dict):
        """Execute if intent is for us"""
        if msg.get("to") != "action_executor":
            return  # Not for us
        
        # Execute action
        if msg["kind"] == "click":
            result = self._click(msg["args"])
        elif msg["kind"] == "type_text":
            result = self._type(msg["args"])
        # ... etc
        
        # Report result
        await self.buses.main.publish(MainTopic.EFFECT, {
            "from": "action_executor",
            "intent": msg,
            "result": result
        })
```

### 3. bsm.py (Enhanced)

**Before:**
```python
from dexter_autonomy.core.event_bus import EventBus, Topic

class BSM:
    def __init__(self, bus: EventBus, ...):
        self.bus = bus
        bus.subscribe(Topic.INTENT, self.observe)
        bus.subscribe(Topic.EFFECT, self.observe)
    
    async def observe(self, msg: dict):
        # Store observation
        await self.brain.add_memory(...)
```

**After:**
```python
from dexter_autonomy.core.triple_bus import TripleBusSystem, MainTopic, CollabTopic, PrivateTopic

class BSM:
    def __init__(self, buses: TripleBusSystem, ...):
        self.buses = buses
        
        # Subscribe to ALL MAIN topics
        for topic in MainTopic:
            buses.main.subscribe(topic, self.observe)
        
        # Subscribe to ALL COLLAB topics
        for topic in CollabTopic:
            buses.collab.subscribe(topic, self.observe)
        
        # Monitor for new PRIVATE buses
        self._monitored_private_buses = set()
        self._start_private_bus_monitoring()
    
    async def _start_private_bus_monitoring(self):
        """Continuously monitor for new PRIVATE buses and subscribe"""
        while True:
            current_private = self.buses.get_all_private_buses()
            for agent_id, private_bus in current_private.items():
                if agent_id not in self._monitored_private_buses:
                    # New PRIVATE bus created, subscribe to it
                    for topic in PrivateTopic:
                        private_bus.subscribe(topic, self.observe)
                    self._monitored_private_buses.add(agent_id)
            await asyncio.sleep(1)  # Check every second
    
    async def observe(self, msg: dict):
        """BSM observes EVERYTHING"""
        # Store to STM
        await self.stm.add(msg)
        
        # Store to LTM
        await self.brain.add_memory(
            kind="observation",
            content=json.dumps(msg),
            meta={
                "bus": msg["bus"],
                "topic": msg["topic"],
                "ts": msg["ts"]
            }
        )
        
        # Extract entities/relations
        await self.extract_knowledge(msg)
        
        # Decide if context provision needed
        if self.should_provide_context(msg):
            await self.provide_context(msg)
    
    async def should_provide_context(self, msg: dict) -> bool:
        """Decide if this observation warrants context provisioning"""
        # If task assignment, provide context
        if msg["topic"] == "task_assignment":
            return True
        
        # If collaboration starting, provide context
        if msg["topic"] == "observation" and msg["bus"] == "collab":
            return True
        
        return False
    
    async def provide_context(self, msg: dict):
        """Provide relevant context based on observation"""
        # Query knowledge graph for relevant context
        context = await self.query_knowledge_graph(msg)
        
        if msg["bus"].startswith("private:"):
            # On-task agent needs context
            agent_id = msg["bus"].split(":")[1]
            private = await self.buses.get_private(agent_id)
            await private.publish(PrivateTopic.CONTEXT_UPDATE, {
                "from": "bsm",
                "to": agent_id,
                "context": context
            })
        else:
            # Broadcast to MAIN (idle agents monitoring)
            await self.buses.main.publish(MainTopic.CONTEXT_AVAILABLE, {
                "from": "bsm",
                "context": context
            })
```

### 4. General Agent (New Base Class)

**Create new file:** `dexter_autonomy/agents/general_agent.py`

```python
from abc import ABC, abstractmethod
from dexter_autonomy.core.triple_bus import TripleBusSystem, MainTopic, CollabTopic, PrivateTopic

class GeneralAgent(ABC):
    """
    Base class for general agents (Coder, Writer, Scraper, etc.)
    
    State machine:
    - idle: Subscribe to MAIN + COLLAB, collaborate in background
    - on_task: Subscribe to PRIVATE only, focus on mission
    """
    
    def __init__(self, agent_id: str, buses: TripleBusSystem, policy):
        self.agent_id = agent_id
        self.buses = buses
        self.policy = policy
        self.state = "idle"
        self.context = {}
        self.private_bus = None
        
        self._enter_idle_mode()
    
    def _enter_idle_mode(self):
        """Idle: Monitor MAIN + COLLAB, collaborate"""
        self.state = "idle"
        
        # Subscribe to MAIN
        self.buses.main.subscribe(MainTopic.USER_INPUT, self._on_main_message)
        self.buses.main.subscribe(MainTopic.DEXTER_RESPONSE, self._on_main_message)
        self.buses.main.subscribe(MainTopic.CONTEXT_AVAILABLE, self._on_context_available)
        
        # Subscribe to ALL COLLAB
        for topic in CollabTopic:
            self.buses.collab.subscribe(topic, self._on_collab_message)
    
    async def _enter_task_mode(self):
        """On-task: Unsubscribe from MAIN/COLLAB, subscribe to PRIVATE only"""
        self.state = "on_task"
        
        # Unsubscribe from MAIN
        self.buses.main.unsubscribe_all(self._on_main_message)
        self.buses.main.unsubscribe_all(self._on_context_available)
        
        # Unsubscribe from COLLAB
        self.buses.collab.unsubscribe_all(self._on_collab_message)
        
        # Subscribe to PRIVATE
        self.private_bus = await self.buses.get_private(self.agent_id)
        for topic in PrivateTopic:
            self.private_bus.subscribe(topic, self._on_private_message)
    
    async def _on_main_message(self, msg: dict):
        """Idle: Monitor user conversation"""
        # Subclass can override to react to user input
        pass
    
    async def _on_context_available(self, msg: dict):
        """Idle: Receive context from BSM"""
        self.context = msg["context"]
    
    async def _on_collab_message(self, msg: dict):
        """Idle: Collaborate on COLLAB bus"""
        if msg["topic"] == "observation":
            # Dexter shared observation, propose solution
            proposal = await self.generate_proposal(msg)
            if proposal:
                await self.buses.collab.publish(CollabTopic.PROPOSAL, {
                    "from": self.agent_id,
                    "proposal": proposal
                })
        
        elif msg["topic"] == "proposal" and msg["from"] != self.agent_id:
            # Peer proposed, refine it
            refinement = await self.refine_proposal(msg)
            if refinement:
                await self.buses.collab.publish(CollabTopic.REFINEMENT, {
                    "from": self.agent_id,
                    "refines": msg["from"],
                    "improvement": refinement
                })
        
        elif msg["topic"] == "vote_request":
            # Dexter called vote
            vote = await self.vote(msg)
            await self.buses.collab.publish(CollabTopic.VOTE_RESPONSE, {
                "from": self.agent_id,
                "vote": vote
            })
    
    async def _on_private_message(self, msg: dict):
        """On-task: Execute mission"""
        if msg["topic"] == "task_assignment":
            await self._enter_task_mode()
            await self.execute_task(msg["task"])
        
        elif msg["topic"] == "context_update":
            # BSM provided context
            self.context = msg["context"]
        
        elif msg["topic"] == "dexter_support":
            # Dexter providing help
            await self.on_support(msg["support"])
    
    async def complete_task(self, result: dict):
        """Task complete, return to idle"""
        # Report completion
        await self.private_bus.publish(PrivateTopic.TASK_COMPLETE, {
            "from": self.agent_id,
            "result": result
        })
        
        # Unsubscribe from PRIVATE
        self.private_bus.unsubscribe_all(self._on_private_message)
        await self.buses.destroy_private(self.agent_id)
        self.private_bus = None
        
        # Re-enter idle mode
        self._enter_idle_mode()
    
    async def request_help(self, issue: str):
        """Request help from Dexter"""
        await self.private_bus.publish(PrivateTopic.HELP_REQUEST, {
            "from": self.agent_id,
            "issue": issue
        })
    
    async def report_progress(self, progress: int, message: str):
        """Report progress to Dexter"""
        await self.private_bus.publish(PrivateTopic.PROGRESS, {
            "from": self.agent_id,
            "progress": progress,
            "message": message
        })
    
    # Abstract methods (subclasses implement)
    
    @abstractmethod
    async def generate_proposal(self, observation: dict) -> dict:
        """Generate proposal for collaboration"""
        pass
    
    @abstractmethod
    async def refine_proposal(self, proposal: dict) -> dict:
        """Refine peer's proposal"""
        pass
    
    @abstractmethod
    async def vote(self, vote_request: dict) -> str:
        """Vote on proposal"""
        pass
    
    @abstractmethod
    async def execute_task(self, task: dict):
        """Execute assigned task"""
        pass
    
    @abstractmethod
    async def on_support(self, support: dict):
        """Receive support from Dexter"""
        pass
```

## Migration Checklist

- [ ] Update imports: `EventBus, Topic` → `TripleBusSystem, MainTopic, CollabTopic, PrivateTopic`
- [ ] Update `__init__`: `bus: EventBus` → `buses: TripleBusSystem`
- [ ] Update subscriptions: `bus.subscribe(Topic.X, ...)` → `buses.main.subscribe(MainTopic.X, ...)`
- [ ] Update publications: `bus.publish(Topic.X, ...)` → `buses.main.publish(MainTopic.X, ...)`
- [ ] Split COUNCIL logic into specific COLLAB topics
- [ ] Add user conversation handling (USER_INPUT, DEXTER_RESPONSE)
- [ ] For Dexter: Subscribe to ALL buses, implement support for PRIVATE
- [ ] For BSM: Subscribe to ALL buses, implement context provisioning
- [ ] For general agents: Create subclass of GeneralAgent with state machine
- [ ] Update tests to use TripleBusSystem
- [ ] Run full test suite: `pytest tests/ -v`

## Testing After Migration

```bash
# Test triple bus itself
pytest tests/test_triple_bus.py -v

# Test migrated agents
pytest tests/test_dexter.py -v
pytest tests/test_bus.py -v
pytest tests/test_policy.py -v

# Integration test
pytest tests/test_automation_safety.py -v
```

## Backward Compatibility Notes

The old `EventBus` still exists in `dexter_autonomy/core/event_bus.py` for gradual migration. However:

⚠️ **DO NOT** mix old and new:
- Once a component migrated to TripleBusSystem, don't publish to old EventBus
- Migrate entire flow at once (e.g., entire Dexter → AE → BSM flow)

✅ **Safe migration order:**
1. Create TripleBusSystem
2. Migrate BSM (omniscient observer)
3. Migrate Dexter (commander)
4. Migrate system agents (ActionExecutor, ChatDock)
5. Create GeneralAgent base class
6. Create specific general agents (WebScraperAgent, CoderAgent, etc.)
7. Remove old EventBus once all migrated

## Questions?

See:
- `docs/TRIPLE-BUS-GUIDE.md` - Complete usage guide
- `docs/ARCHITECTURE-FINAL.md` - Full architecture specification
- `tests/test_triple_bus.py` - Working examples

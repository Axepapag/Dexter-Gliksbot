# Triple Event Bus - Quick Start Guide

## Architecture Overview

The Dexter-Gliksbot system uses **three independent event buses** for communication:

1. **MAIN Bus** - User ↔ Dexter conversation + system commands
2. **COLLAB Bus** - Idle general agents collaborate in background
3. **PRIVATE Buses** - Per-agent channels for on-task communication

## Who Subscribes Where

| Agent Type | MAIN | COLLAB | PRIVATE |
|------------|------|--------|---------|
| **BSM** (Brain) | ✅ All topics | ✅ All topics | ✅ All buses |
| **Dexter** (Commander) | ✅ Selected topics | ✅ All topics | ✅ All buses |
| **System Agents** (ActionExecutor, ChatDock) | ✅ INTENT, EFFECT | ❌ Never | ✅ Own bus only |
| **General Agents** (Idle) | ✅ USER_INPUT, DEXTER_RESPONSE | ✅ All topics | ❌ None |
| **General Agents** (On-Task) | ❌ None | ❌ None | ✅ Own bus only |

## Basic Usage

### Creating the Triple Bus System

```python
from dexter_autonomy.core.triple_bus import TripleBusSystem, MainTopic, CollabTopic, PrivateTopic

# Create and start all buses
buses = TripleBusSystem()
await buses.start_all()

# Or use global singleton
from dexter_autonomy.core.triple_bus import get_global_triple_bus
buses = get_global_triple_bus()
await buses.start_all()
```

### Publishing to MAIN Bus

```python
# User speaks
await buses.main.publish(MainTopic.USER_INPUT, {
    "content": "Please analyze this invoice",
    "user_id": "john_doe"
})

# Dexter responds (with extracted actions)
await buses.main.publish(MainTopic.DEXTER_RESPONSE, {
    "content": "I'll analyze the invoice now.",
    "actions": [
        {"kind": "ocr", "args": {"region": "full_screen"}},
        {"kind": "click", "args": {"x": 100, "y": 200}}
    ]
})

# System command (Dexter → ActionExecutor)
await buses.main.publish(MainTopic.INTENT, {
    "to": "action_executor",
    "kind": "click",
    "args": {"x": 100, "y": 200},
    "rationale": "Clicking Submit button"
})

# System response (ActionExecutor → Dexter)
await buses.main.publish(MainTopic.EFFECT, {
    "from": "action_executor",
    "status": "ok",
    "detail": {"clicked": True, "duration_ms": 123}
})
```

### Publishing to COLLAB Bus (Idle Agents)

```python
# Dexter broadcasts observation
await buses.collab.publish(CollabTopic.OBSERVATION, {
    "from": "dexter",
    "observation": "User needs invoice data extracted and formatted"
})

# Coder proposes solution
await buses.collab.publish(CollabTopic.PROPOSAL, {
    "from": "coder",
    "proposal": "Use pandas to parse CSV, then format as Excel"
})

# Writer refines proposal
await buses.collab.publish(CollabTopic.REFINEMENT, {
    "from": "writer",
    "refines": "coder",
    "improvement": "Add data validation and error handling"
})

# Data analyst critiques
await buses.collab.publish(CollabTopic.CRITIQUE, {
    "from": "data_analyst",
    "critiques": "coder",
    "issue": "CSV format varies by vendor, need detection logic"
})

# Dexter calls for vote
await buses.collab.publish(CollabTopic.VOTE_REQUEST, {
    "from": "dexter",
    "proposal_id": "coder_proposal_v2",
    "options": ["proceed", "refine_more", "alternative"]
})

# Agents vote
await buses.collab.publish(CollabTopic.VOTE_RESPONSE, {
    "from": "coder",
    "vote": "proceed"
})
```

### Publishing to PRIVATE Bus (On-Task Agent)

```python
# Get or create PRIVATE bus for agent
private_bus = await buses.get_private("web_scraper")

# Dexter assigns task
await private_bus.publish(PrivateTopic.TASK_ASSIGNMENT, {
    "from": "dexter",
    "to": "web_scraper",
    "task": "Scrape product prices from example.com",
    "params": {"url": "https://example.com/products"}
})

# BSM provides context
await private_bus.publish(PrivateTopic.CONTEXT_UPDATE, {
    "from": "bsm",
    "to": "web_scraper",
    "context": {
        "past_scrapes": [...],
        "learned_patterns": [...],
        "css_selectors": {"price": "div.price"}
    }
})

# Agent reports progress
await private_bus.publish(PrivateTopic.PROGRESS, {
    "from": "web_scraper",
    "progress": 50,
    "message": "Scraped 50 products"
})

# Agent requests help
await private_bus.publish(PrivateTopic.HELP_REQUEST, {
    "from": "web_scraper",
    "issue": "Website requires JavaScript, static scraper failing"
})

# Dexter provides support
await private_bus.publish(PrivateTopic.DEXTER_SUPPORT, {
    "from": "dexter",
    "to": "web_scraper",
    "support": "Switch to Selenium for JS rendering"
})

# Agent completes task
await private_bus.publish(PrivateTopic.TASK_COMPLETE, {
    "from": "web_scraper",
    "result": {"products_scraped": 100, "output_file": "prices.csv"}
})
```

## Subscribing to Topics

### BSM - Observes EVERYTHING

```python
class BSMAgent:
    def __init__(self, buses: TripleBusSystem):
        self.buses = buses
        self.observations = []
        
        # Subscribe to ALL MAIN topics
        for topic in MainTopic:
            self.buses.main.subscribe(topic, self.observe)
        
        # Subscribe to ALL COLLAB topics
        for topic in CollabTopic:
            self.buses.collab.subscribe(topic, self.observe)
        
        # Note: BSM must also subscribe to new PRIVATE buses as they're created
        # This is handled by monitoring get_all_private_buses()
    
    async def observe(self, msg: dict):
        """BSM observes and stores everything"""
        self.observations.append(msg)
        # Store to memory
        await self.store_to_memory(msg)
        # Extract entities/relations
        await self.extract_knowledge(msg)
        # Decide if context is needed
        if self.should_provide_context(msg):
            await self.provide_context(msg)
```

### Dexter - Monitors & Commands EVERYTHING

```python
class DexterOrchestrator:
    def __init__(self, buses: TripleBusSystem):
        self.buses = buses
        
        # Subscribe to MAIN (selected topics)
        self.buses.main.subscribe(MainTopic.USER_INPUT, self.on_user_input)
        self.buses.main.subscribe(MainTopic.INTENT, self.on_intent)
        self.buses.main.subscribe(MainTopic.EFFECT, self.on_effect)
        self.buses.main.subscribe(MainTopic.ERROR, self.on_error)
        
        # Subscribe to ALL COLLAB (monitor & intervene)
        for topic in CollabTopic:
            self.buses.collab.subscribe(topic, self.on_collab_message)
        
        # Subscribe to ALL PRIVATE buses (support agents)
        # Updated dynamically as buses created
    
    async def on_user_input(self, msg: dict):
        """Deep conversation with user, extract actions"""
        response = await self.converse_and_extract(msg["content"])
        await self.buses.main.publish(MainTopic.DEXTER_RESPONSE, response)
        
        # If collaboration needed, broadcast to COLLAB
        if response.get("needs_collaboration"):
            await self.buses.collab.publish(CollabTopic.OBSERVATION, {
                "from": "dexter",
                "observation": response["summary"]
            })
```

### System Agent (ActionExecutor, ChatDock)

```python
class ActionExecutor:
    def __init__(self, buses: TripleBusSystem):
        self.buses = buses
        
        # Subscribe to MAIN for system commands
        self.buses.main.subscribe(MainTopic.INTENT, self.on_intent)
    
    async def on_intent(self, msg: dict):
        """Execute if intent is for us"""
        if msg.get("to") != "action_executor":
            return
        
        # Validate with policy
        allowed, reason = self.policy.allow_action(msg)
        if not allowed:
            await self.buses.main.publish(MainTopic.EFFECT, {
                "from": "action_executor",
                "status": "denied",
                "reason": reason
            })
            return
        
        # Execute
        result = await self.execute(msg)
        await self.buses.main.publish(MainTopic.EFFECT, result)
```

### General Agent - State Machine

```python
class GeneralAgent:
    def __init__(self, agent_id: str, buses: TripleBusSystem):
        self.agent_id = agent_id
        self.buses = buses
        self.state = "idle"
        self._enter_idle_mode()
    
    def _enter_idle_mode(self):
        """Subscribe to MAIN + COLLAB"""
        self.state = "idle"
        self.buses.main.subscribe(MainTopic.USER_INPUT, self.on_main_message)
        self.buses.main.subscribe(MainTopic.DEXTER_RESPONSE, self.on_main_message)
        for topic in CollabTopic:
            self.buses.collab.subscribe(topic, self.on_collab_message)
    
    async def _enter_task_mode(self):
        """Unsubscribe from MAIN + COLLAB, subscribe to PRIVATE only"""
        self.state = "on_task"
        # Unsubscribe from MAIN
        self.buses.main.unsubscribe_all(self.on_main_message)
        # Unsubscribe from COLLAB
        self.buses.collab.unsubscribe_all(self.on_collab_message)
        
        # Subscribe to PRIVATE
        self.private_bus = await self.buses.get_private(self.agent_id)
        for topic in PrivateTopic:
            self.private_bus.subscribe(topic, self.on_private_message)
    
    async def on_collab_message(self, msg: dict):
        """Idle: Collaborate on COLLAB bus"""
        if msg["topic"] == "observation":
            # Propose solution
            proposal = await self.generate_proposal(msg)
            await self.buses.collab.publish(CollabTopic.PROPOSAL, proposal)
        elif msg["topic"] == "proposal":
            # Refine peer's proposal
            refinement = await self.refine_proposal(msg)
            await self.buses.collab.publish(CollabTopic.REFINEMENT, refinement)
    
    async def on_private_message(self, msg: dict):
        """On-task: Execute mission"""
        if msg["topic"] == "task_assignment":
            await self.execute_task(msg)
        elif msg["topic"] == "context_update":
            # BSM provided context
            self.context = msg["context"]
        elif msg["topic"] == "dexter_support":
            # Dexter providing help
            self.apply_support(msg["support"])
    
    async def complete_task(self):
        """Return to idle mode"""
        # Unsubscribe from PRIVATE
        self.private_bus.unsubscribe_all(self.on_private_message)
        await self.buses.destroy_private(self.agent_id)
        
        # Re-enter idle mode
        self._enter_idle_mode()
```

## Message Metadata

All messages automatically include:

- `id` - Unique message ID (UUID)
- `ts` - Timestamp (Unix epoch)
- `bus` - Which bus ("main", "collab", "private:agent_id")
- `topic` - Topic name ("user_input", "proposal", "task_assignment", etc.)

```python
# You publish:
await buses.main.publish(MainTopic.USER_INPUT, {"content": "Hello"})

# Recipients receive:
{
    "id": "a1b2c3d4-...",
    "ts": 1736789012.345,
    "bus": "main",
    "topic": "user_input",
    "content": "Hello"
}
```

## Bus Lifecycle

```python
# Start all buses
await buses.start_all()

# Get stats
stats = buses.get_stats()
print(stats)
# {
#     "main": {"topics": 7, "subscribers": 15, "started": True},
#     "collab": {"topics": 8, "subscribers": 12, "started": True},
#     "private": {"bus_count": 3, "agent_ids": ["web_scraper", "coder", "data_analyst"]}
# }

# Get all private buses (for BSM/Dexter monitoring)
private_buses = buses.get_all_private_buses()
for agent_id, bus in private_buses.items():
    print(f"Agent {agent_id} has private bus {bus.bus_id}")

# Stop all buses
await buses.stop_all()
```

## Complete Example: User Task → Collaboration → Execution

```python
async def main():
    # Setup
    buses = TripleBusSystem()
    await buses.start_all()
    
    # 1. User speaks to Dexter
    await buses.main.publish(MainTopic.USER_INPUT, {
        "content": "I need to scrape product prices from Amazon"
    })
    
    # 2. Dexter broadcasts to COLLAB for collaboration
    await buses.collab.publish(CollabTopic.OBSERVATION, {
        "from": "dexter",
        "observation": "User needs web scraping solution for Amazon product prices"
    })
    
    # 3. Idle agents collaborate
    # Web scraper proposes
    await buses.collab.publish(CollabTopic.PROPOSAL, {
        "from": "web_scraper",
        "proposal": "I can scrape with Beautiful Soup + requests"
    })
    
    # Coder refines
    await buses.collab.publish(CollabTopic.REFINEMENT, {
        "from": "coder",
        "refines": "web_scraper",
        "improvement": "Use Selenium for dynamic content"
    })
    
    # Data analyst adds insight
    await buses.collab.publish(CollabTopic.REFINEMENT, {
        "from": "data_analyst",
        "refines": "web_scraper",
        "improvement": "Export to pandas DataFrame for analysis"
    })
    
    # 4. Dexter reaches consensus and assigns task
    private_bus = await buses.get_private("web_scraper")
    
    await private_bus.publish(PrivateTopic.TASK_ASSIGNMENT, {
        "from": "dexter",
        "to": "web_scraper",
        "task": "Scrape Amazon product prices",
        "params": {
            "url": "https://amazon.com/search?q=laptops",
            "fields": ["title", "price", "rating"]
        }
    })
    
    # 5. BSM provides context
    await private_bus.publish(PrivateTopic.CONTEXT_UPDATE, {
        "from": "bsm",
        "to": "web_scraper",
        "context": {
            "past_amazon_scrapes": 15,
            "success_rate": 0.93,
            "learned_selectors": {
                "title": "span.a-text-normal",
                "price": "span.a-price-whole",
                "rating": "span.a-icon-alt"
            }
        }
    })
    
    # 6. Agent executes (simulated)
    await asyncio.sleep(2)
    
    # 7. Agent reports progress
    await private_bus.publish(PrivateTopic.PROGRESS, {
        "from": "web_scraper",
        "progress": 50,
        "message": "Scraped 50/100 products"
    })
    
    # 8. Agent completes
    await private_bus.publish(PrivateTopic.TASK_COMPLETE, {
        "from": "web_scraper",
        "result": {
            "products_scraped": 100,
            "output_file": "amazon_laptops.csv"
        }
    })
    
    # 9. Dexter publishes result to MAIN
    await buses.main.publish(MainTopic.DEXTER_RESPONSE, {
        "content": "Task complete! Scraped 100 laptop prices to amazon_laptops.csv"
    })
    
    # Cleanup
    await buses.destroy_private("web_scraper")
    await buses.stop_all()

if __name__ == "__main__":
    asyncio.run(main())
```

## Testing

See `tests/test_triple_bus.py` for comprehensive test examples covering:

- ✅ MAIN bus user conversation
- ✅ COLLAB bus idle collaboration
- ✅ PRIVATE bus on-task communication
- ✅ BSM observing everything (all 3 buses)
- ✅ Dexter monitoring everything (all 3 buses)
- ✅ General agent state transitions (idle ↔ on-task)
- ✅ Error handling in subscribers
- ✅ Lazy PRIVATE bus creation
- ✅ Destroying PRIVATE buses
- ✅ Message metadata injection
- ✅ Subscriber count tracking
- ✅ Complete workflow simulation

Run tests:
```bash
cd /workspaces/Dexter-Gliksbot
python -m pytest tests/test_triple_bus.py -v
```

All 13 tests pass! ✅

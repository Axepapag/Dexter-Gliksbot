#!/usr/bin/env python3
"""
Example script demonstrating how to use Dexter orchestrator.
"""

import asyncio
import sys
from pathlib import Path

# Add the source directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from dexter_autonomy.core.event_bus import EventBus
from dexter_autonomy.core.policy_overlay import CompositeDenyPolicy
from dexter_autonomy.brain.memory import BrainDB
from dexter_autonomy.agents.action_executor import ActionExecutor
from dexter_autonomy.agents.aum import AUM
from dexter_autonomy.agents.bsm import BSM
from dexter_autonomy.agents.chatdock import ChatDockAgent
from dexter_autonomy.agents.dexter_orchestrator import DexterOrchestrator


async def main():
    """Example of using Dexter orchestrator."""
    # Create the event bus
    bus = EventBus()
    
    # Create a simple policy
    policy = CompositeDenyPolicy({
        "process": {
            "deny_cmd_patterns": ["rm -rf *"]
        },
        "files": {
            "deny_write_globs": ["C:\\Windows\\*"]
        },
        "hotkeys": {
            "deny": ["CTRL+ALT+DELETE"]
        }
    })
    
    # Create brain database
    brain = BrainDB(":memory:")
    
    # Create agents
    executor = ActionExecutor(bus, policy, None)
    aum = AUM("test-model", "http://localhost:11434", 0.1)
    bsm = BSM("test-model", "http://localhost:11434", brain, 0.1)
    chatdock = ChatDockAgent(bus, policy, executor, aum, bsm, None)
    
    # Configuration for Dexter
    config = {
        "slots": {
            "dexter-orchestrator": {
                "endpoint": "https://ollama.com",
                "api_key_env": "OLLAMA_CLOUD_KEY",
                "model": "deepseek-v3.1:671b-cloud",
                "system_prompt": "You are Dexter, the central orchestrator...",
                "ollama_options": {}
            }
        }
    }
    
    # Create Dexter orchestrator
    dexter = DexterOrchestrator(
        bus=bus,
        policy=policy,
        brain=brain,
        executor=executor,
        aum=aum,
        bsm=bsm,
        chatdock=chatdock,
        config=config
    )
    
    # Start the event bus
    await bus.start()
    
    # Example 1: Direct communication with Dexter
    print("=== Direct Communication with Dexter ===")
    intent = {
        "target": "dexter",
        "message": "Hello Dexter! Can you help me understand how to use this system?"
    }
    
    # Note: This would normally call the Ollama API, but we're not setting up
    # the actual API key here, so it would fail in a real scenario
    print("Sending message to Dexter...")
    # result = await dexter.handle_intent(intent)
    # print(f"Dexter's response: {result}")
    print("In a real scenario, Dexter would respond with helpful guidance.")
    
    # Example 2: Intent validation
    print("\n=== Intent Validation ===")
    
    # Safe intent
    safe_intent = {
        "kind": "type_text",
        "args": {"text": "Hello, world!"}
    }
    
    validation_result = await dexter.validate_intent(safe_intent)
    print(f"Safe intent validation: {validation_result}")
    
    # Dangerous intent (would be blocked)
    dangerous_intent = {
        "kind": "execute_process",
        "args": {"command": "rm -rf /"}
    }
    
    validation_result = await dexter.validate_intent(dangerous_intent)
    print(f"Dangerous intent validation: {validation_result}")
    
    # Example 3: Agent registration
    print("\n=== Agent Registration ===")
    await dexter.register_agent("excel-automation-agent", ["spreadsheet", "data-entry"])
    print("Registered Excel automation agent with Dexter")
    
    await dexter.register_agent("web-scraper-agent", ["web", "data-collection"])
    print("Registered web scraper agent with Dexter")
    
    print(f"Active agents: {list(dexter.active_agents.keys())}")
    
    # Example 4: Operation tracking
    print("\n=== Operation Tracking ===")
    await dexter.start_operation("excel-data-entry-001", "excel-automation-agent", "Enter customer data")
    print("Started operation: excel-data-entry-001")
    
    print(f"Active operations: {list(dexter.active_operations.keys())}")
    
    await dexter.complete_operation("excel-data-entry-001")
    print("Completed operation: excel-data-entry-001")
    
    if "excel-data-entry-001" in dexter.active_operations:
        print(f"Operation status: {dexter.active_operations['excel-data-entry-001']['status']}")
    
    # Stop the event bus
    await bus.stop()
    
    print("\n=== Demo Complete ===")
    print("Dexter orchestrator successfully demonstrated all core features!")


if __name__ == "__main__":
    asyncio.run(main())

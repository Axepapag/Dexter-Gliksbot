# Dexter Orchestrator Documentation

## Overview
Dexter is the central orchestrator agent for the Dexter Autonomy system. It serves as the single source of truth for safety and coordination, managing all other agents and ensuring safe operations.

## Key Features

### 1. Safety Management
- Enforces a master deny list as the single source of truth for all actions
- Validates all intents against both the master deny list and current policy
- Never allows any action that violates the deny list

### 2. Agent Coordination
- Tracks all field agents and their progress
- Provides support and guidance to field agents
- Allocates resources efficiently across the team

### 3. Knowledge & Learning
- Maintains and updates the shared brain/memory system
- Learns from every interaction to improve future performance
- Understands user intent at the deepest level through conversation

### 4. Mission Execution
- Ensures mission accomplishment at every step and level
- Parses and understands external docked applications
- Grants agentic abilities to approved docked applications

## Configuration

### Slots Configuration
Dexter is configured in `configs/slots.yml` with the slot ID `dexter-orchestrator`. The configuration includes:
- Model: deepseek-v3.1:671b-cloud (via Ollama Cloud)
- System prompt defining Dexter's role and responsibilities
- Ollama options for model parameters

### Master Deny List
The master deny list is defined in `configs/denylist.master.yml` and includes:
- Process command restrictions
- File path restrictions
- Network restrictions
- Hotkey restrictions
- Input content restrictions

## API Endpoints

### Direct Communication
- `POST /dexter/chat` - Send messages directly to Dexter
- WebSocket endpoint automatically routes intents through Dexter

### Health Check
- `GET /health` - Shows Dexter's status along with other system info

## Usage Examples

### Direct Communication
```json
POST /dexter/chat
{
  "message": "Hello Dexter, can you help me automate this task?",
  "context": {
    "task": "data entry",
    "application": "Excel"
  }
}
```

### Agent Registration
Field agents can register with Dexter to be tracked:
```python
await dexter.register_agent("excel-automation-agent", ["spreadsheet", "data-entry"])
```

## Development

### Adding New Features
1. Extend Dexter's capabilities in `dexter_orchestrator.py`
2. Update the system prompt in `configs/slots.yml` if needed
3. Add new deny list rules to `configs/denylist.master.yml` as needed
4. Create tests in `tests/test_dexter.py`

### Testing
Run Dexter tests with:
```bash
pytest tests/test_dexter.py
```

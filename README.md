# Dexter-Gliksbot

**Windows-First AI Autonomy Platform** with Real-Time WebSocket Streaming

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server (includes WebSocket support)
python start.py --port 8765

# Connect test client
python scripts/test_websocket_client.py
```

## 📡 WebSocket Infrastructure

**Status**: ✅ Production Ready (v1.0.0)

Complete real-time WebSocket streaming infrastructure for Cockpit UI integration:
- **2,800+ lines** of production code
- **120+ automated tests** (100% passing core functionality)
- **21 event types** (agent status, missions, logs, performance, collaboration)
- **Full documentation** with testing guides

**See [README-WEBSOCKET.md](README-WEBSOCKET.md) for complete documentation.**

### WebSocket Features

✅ Real-time event streaming (TripleBus → WebSocket)  
✅ State caching with LRU eviction (1000 agents, 500 missions)  
✅ Client filtering (agents, missions, log levels, event types)  
✅ Event aggregation (5s throttle for high-frequency events)  
✅ Auto-reconnect with exponential backoff  
✅ Manual test client with color-coded output  
✅ 120+ automated tests across all layers  

### Architecture

```
Cockpit UI ←→ FastAPI WebSocket ←→ WebSocketManager ←→ TripleBus
```

See [.github/copilot-instructions.md](.github/copilot-instructions.md) for comprehensive architecture documentation.

## 🎯 Core Components

### Triple Bus Architecture
- **MAIN bus**: User ↔ Dexter conversation + system commands
- **COLLAB bus**: Idle general agents collaborate
- **PRIVATE buses**: Per-agent on-task channels

### Agents
- **Dexter Orchestrator**: Commander (monitors everything, executes constantly)
- **BSM (Brain/State Model)**: Omniscient observer (learns from everything)
- **ActionExecutor**: Windows automation (keyboard/mouse/OCR)
- **ChatDock**: External window docking + OCR
- **General Agents**: Prompted workers (coder, writer, scraper, etc.)

### Brain & Memory
- **Knowledge Graph**: Entities, relations, temporal edges
- **Neural Patterns**: Learned automation sequences
- **Multi-Tier Memory**: STM (10GB RAM) + LTM (SQLite persistent)
- **Context-Aware Retrieval**: RAG-style agent responses

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [README-WEBSOCKET.md](README-WEBSOCKET.md) | Complete WebSocket implementation summary |
| [WEBSOCKET_TESTING.md](WEBSOCKET_TESTING.md) | Testing guide (scenarios, performance, troubleshooting) |
| [.github/copilot-instructions.md](.github/copilot-instructions.md) | Architecture & design decisions |
| [dexter_repo_technical_monetization_report_da.md](dexter_repo_technical_monetization_report_da.md) | Technical overview |

## 🧪 Testing

```bash
# All WebSocket tests
pytest tests/test_websocket_*.py -v

# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=dexter_autonomy --cov-report=html
```

## 🔧 Configuration

See `configs/` for:
- `dexter.yml` - Main configuration
- `slots.yml` - Agent LLM configurations
- `denylist.master.yml` - Global deny list (security)
- `denylist.profiles.yml` - Tiered security profiles

## 🎯 Roadmap

✅ **Complete**: WebSocket Infrastructure (Todos #1-11)  
🔄 **In Progress**: WPF Cockpit UI with AvalonDock  
📋 **Planned**: JWT authentication, rate limiting, production hardening  

## 📖 Project Philosophy

**Deny-First Security**: Only deny lists, never allow-lists  
**Observer Pattern**: BSM observes everything, learns continuously  
**Commander Pattern**: Dexter monitors everything, executes constantly  
**Windows-First**: Target Windows Server 2022, cross-platform future  

## 🤝 Contributing

See [.github/copilot-instructions.md](.github/copilot-instructions.md) for:
- Development workflows
- Coding patterns & conventions
- Common issues & fixes
- Production readiness checklist

Dexter

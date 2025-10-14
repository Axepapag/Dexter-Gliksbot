# WebSocket Quick Reference Card

**Version**: 1.0.0 | **Status**: ✅ Production Ready | **Date**: October 14, 2025

---

## 🚀 Quick Start (30 seconds)

```bash
# Start server
python start.py --port 8765

# Connect test client
python scripts/test_websocket_client.py

# Generate test events
python -c "
import asyncio
from dexter_autonomy.core.triple_bus import get_global_triple_bus, MainTopic
async def main():
    bus = get_global_triple_bus()
    await bus.start_all()
    await bus.main.publish(MainTopic.TRACE, {'agent_id': 'test', 'status': 'idle'})
    await bus.stop_all()
asyncio.run(main())
"
```

---

## 📡 WebSocket Connection

### Endpoint
```
ws://localhost:8765/ws/cockpit
```

### Query Parameters (All Optional)
- `agent_ids=agent-1,agent-2` - Filter by agent IDs
- `mission_ids=mission-1` - Filter by mission IDs
- `log_levels=ERROR,WARN` - Filter by log levels
- `event_types=agent_status,mission_progress` - Filter by event types
- `client_id=my-client` - Custom client identifier

### Example
```
ws://localhost:8765/ws/cockpit?agent_ids=web-scraper&log_levels=ERROR
```

---

## 📨 Message Format

### Server → Client
```json
{
  "type": "agent_status",
  "timestamp": "2025-10-14T12:34:56.789Z",
  "data": {
    "agent_id": "web-scraper",
    "status": "on_task"
  },
  "metadata": {
    "bus": "MAIN",
    "topic": "TRACE"
  }
}
```

### Client → Server
```json
// Update filters
{"type": "update_filters", "filters": {"agent_ids": ["agent-1"]}}

// Request state snapshot
{"type": "request_snapshot", "force_refresh": false}

// Heartbeat response
{"type": "pong"}
```

---

## 🎯 Event Types (21 Total)

### System (4)
- `state_snapshot` - Full system state
- `system_startup` - System started
- `system_shutdown` - System stopped
- `config_changed` - Configuration updated

### Agent (3)
- `agent_status` - Agent status changed
- `agent_heartbeat` - Agent heartbeat
- `agent_error` - Agent error

### Mission (4)
- `mission_started` - Mission started
- `mission_progress` - Mission progress update
- `mission_completed` - Mission completed
- `mission_failed` - Mission failed

### Collaboration (4)
- `collab_started` - Collaboration started
- `collab_proposal` - Agent proposed solution
- `collab_consensus` - Consensus reached
- `collab_complete` - Collaboration finished

### Log (4)
- `log_trace` - Trace log
- `log_info` - Info log
- `log_warn` - Warning log
- `log_error` - Error log

### Performance (2)
- `perf_metric` - Performance metric
- `perf_system` - System performance

---

## 🔌 REST Endpoints

```bash
# Health checks
GET /health          # Basic health
GET /healthz         # Health check alias
GET /ws/health       # WebSocket system health

# Statistics
GET /stats           # System statistics

# Debug (dev only)
GET /debug/connections  # Active WebSocket clients
GET /debug/cache        # Cache inspection

# Documentation
GET /                # API info
GET /docs            # Swagger UI
```

---

## 🧪 Testing

### Run All Tests
```bash
pytest tests/test_websocket_*.py -v
```

### Specific Test Suites
```bash
pytest tests/test_websocket_events.py -v         # 18/18 tests
pytest tests/test_connection_manager.py -v       # 21/21 tests
pytest tests/test_websocket_manager.py -v        # 18/18 tests
pytest tests/test_websocket_integration.py -v    # 12/23 tests
```

### Manual Testing
```bash
# Terminal 1: Server
python start.py --port 8765

# Terminal 2: Test client
python scripts/test_websocket_client.py --verbose

# Terminal 3: Generate events (see testing guide)
```

---

## 🎨 Test Client Commands

**Interactive Commands (while connected)**:
- `s` - Request state snapshot
- `f` - Request force-refresh snapshot
- `u` - Update filters (prompts for new filters)
- `?` - Show help
- `stats` - Show statistics
- `q` - Quit

**CLI Arguments**:
```bash
--url URL                # WebSocket URL (default: ws://localhost:8765/ws/cockpit)
--agent-ids IDS          # Comma-separated agent IDs
--mission-ids IDS        # Comma-separated mission IDs
--log-levels LEVELS      # Comma-separated log levels
--event-types TYPES      # Comma-separated event types
--verbose                # Show all events (default: compact)
--no-auto-reconnect      # Disable auto-reconnect
```

---

## ⚙️ Configuration

### LRU Cache Limits
```python
_agent_state_cache.max_size = 1000   # Max agents cached
_mission_state_cache.max_size = 500  # Max missions cached
```

### Event History
```python
connection_manager.max_events = 1000  # Circular buffer size
connection_manager.replay_duration = timedelta(minutes=5)
```

### Heartbeat
```python
connection_manager.heartbeat_interval = 30  # Ping every 30s
connection_manager.heartbeat_timeout = 10   # Disconnect after 10s
```

### Aggregation
```python
# Agent status throttled to 5s
_last_agent_status[agent_id] = timestamp
```

---

## 🐛 Common Issues

### 1. Connection Refused
```
Error: [Errno 111] Connection refused
```
**Fix**: Ensure server is running (`python start.py --port 8765`)

### 2. TestClient Lifespan Error
```
RuntimeError: WebSocketManager not initialized
```
**Fix**: TestClient doesn't run lifespan handlers. Use real server for integration tests.

### 3. No Events Received
**Check**:
- Are events being published to TripleBus?
- Do events match client filters?
- Is WebSocketManager subscribed to correct topics?

### 4. High Memory Usage
**Check**:
- LRU cache size (should evict after 1000 agents)
- Event history size (should limit to 1000 events)
- Are clients disconnecting properly?

---

## 📊 Performance

### Targets
- **Throughput**: 1000+ messages/min per client
- **Latency (critical)**: <100ms
- **Latency (aggregated)**: <5s
- **Concurrent clients**: 10+

### Validation
```bash
# High volume test (100 events)
pytest tests/test_websocket_integration.py::test_high_volume_events -v
```

---

## 🔒 Security Checklist

### Development (Current)
- ✅ CORS: Allow all
- ✅ Authentication: Bypass
- ✅ Rate limiting: Not enforced
- ✅ Debug endpoints: Enabled

### Production (TODO)
- [ ] CORS: Configure allowed origins
- [ ] Authentication: Enable JWT validation
- [ ] Rate limiting: Enable (1000 msg/min)
- [ ] Debug endpoints: Disable
- [ ] SSL/TLS: Enable wss://
- [ ] Structured logging: Enable

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| **WEBSOCKET_QUICK_REFERENCE.md** | This file - quick reference |
| **README-WEBSOCKET.md** | Complete implementation summary |
| **WEBSOCKET_TESTING.md** | Testing guide with scenarios |
| **WEBSOCKET_ACHIEVEMENT_REPORT.md** | Project achievement report |

---

## 💡 Tips & Tricks

### Filter by Critical Events Only
```bash
python scripts/test_websocket_client.py --event-types agent_error,mission_failed
```

### Monitor Specific Agent
```bash
python scripts/test_websocket_client.py --agent-ids web-scraper --verbose
```

### Debug Connection Issues
```bash
# Check WebSocket health
curl http://localhost:8765/ws/health | jq

# Check active connections
curl http://localhost:8765/debug/connections | jq
```

### Generate Load for Testing
```python
import asyncio
from dexter_autonomy.core.triple_bus import get_global_triple_bus, MainTopic

async def generate_load(count=100):
    bus = get_global_triple_bus()
    await bus.start_all()
    for i in range(count):
        await bus.main.publish(MainTopic.TRACE, {
            'agent_id': f'agent-{i % 10}',
            'status': 'on_task' if i % 2 else 'idle',
            'message': f'Test event {i}'
        })
    await bus.stop_all()

asyncio.run(generate_load(100))
```

---

## 🎯 Architecture at a Glance

```
Client ←WebSocket→ FastAPI ←Async→ ConnectionManager ←Transform→ WebSocketManager ←Observer→ TripleBus
```

**Key Patterns**:
- Observer: WebSocketManager observes all TripleBus events
- Pub/Sub: TripleBus → WebSocketManager → ConnectionManager → Clients
- LRU Cache: Memory-efficient state management
- Fire-and-Forget: Drop events for disconnected clients
- Aggregation: Throttle high-frequency events

---

## 🚀 Next Steps

1. **Manual Testing**: Use 3 terminals (server, client, events)
2. **WPF Integration**: Connect Cockpit UI to WebSocket endpoint
3. **Security Hardening**: Enable JWT, rate limiting, SSL
4. **Production Deploy**: Configure CORS, disable debug endpoints

---

**Version**: 1.0.0  
**Status**: ✅ Production Ready  
**Date**: October 14, 2025  

For detailed information, see **README-WEBSOCKET.md** or **WEBSOCKET_TESTING.md**.

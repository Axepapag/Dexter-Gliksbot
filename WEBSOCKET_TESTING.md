# WebSocket Infrastructure Testing Guide

Complete guide for testing Dexter's real-time WebSocket streaming infrastructure.

## Architecture Overview

```
TripleBus (MAIN, COLLAB, PRIVATE buses)
    ↓ observer pattern
WebSocketManager (LRU cache, 1Hz metrics)
    ↓ transform events
TripleBusTransformer (5s aggregation)
    ↓ broadcast
ConnectionManager (fire-and-forget)
    ↓ filter by subscription
FastAPI WebSocket (/ws/cockpit)
    ↓ JSON streaming
Cockpit Clients (WPF, Python, Browser)
```

## Quick Start

### 1. Start the Server

```bash
# Terminal 1: Start FastAPI server
python start.py --port 8765
```

The server will:
- Initialize TripleBusSystem (MAIN, COLLAB, PRIVATE buses)
- Start WebSocketManager (subscribe to all buses)
- Launch FastAPI on http://0.0.0.0:8765

### 2. Test with Python Client

```bash
# Terminal 2: Connect test client
python scripts/test_websocket_client.py

# Or with filters
python scripts/test_websocket_client.py --agent-ids agent-1,agent-2 --log-levels ERROR,WARN

# Verbose mode (show all message details)
python scripts/test_websocket_client.py --verbose
```

### 3. Generate Test Events

```bash
# Terminal 3: Publish test events to TripleBus
python -c "
import asyncio
from dexter_autonomy.core.triple_bus import get_global_triple_bus, MainTopic

async def main():
    bus = get_global_triple_bus()
    await bus.start_all()
    
    # Publish test events
    await bus.main.publish(MainTopic.TRACE, {
        'agent_id': 'test-agent',
        'message': 'Hello from TripleBus!'
    })
    
    await bus.stop_all()

asyncio.run(main())
"
```

## Test Client Features

### Connection Options

```bash
# All events (no filters)
python scripts/test_websocket_client.py

# Filter by agent IDs
python scripts/test_websocket_client.py --agent-ids web-scraper,coder

# Filter by mission IDs
python scripts/test_websocket_client.py --mission-ids mission-1

# Filter by log levels
python scripts/test_websocket_client.py --log-levels ERROR,WARN

# Filter by event types
python scripts/test_websocket_client.py --event-types AGENT_STATUS,MISSION_PROGRESS

# Combine multiple filters
python scripts/test_websocket_client.py \
  --agent-ids agent-1,agent-2 \
  --log-levels ERROR,WARN \
  --event-types AGENT_STATUS,LOG_ERROR

# Custom server URL
python scripts/test_websocket_client.py --url ws://192.168.1.100:8765/ws/cockpit

# Disable auto-reconnect
python scripts/test_websocket_client.py --no-auto-reconnect
```

### Message Format

All messages follow this JSON structure:

```json
{
  "type": "agent_status",
  "timestamp": "2025-10-14T12:34:56.789Z",
  "data": {
    "agent_id": "web-scraper",
    "status": "on_task",
    "current_mission": "mission-1",
    "metrics": {
      "uptime_seconds": 120.5,
      "tasks_completed": 10
    }
  },
  "metadata": {
    "bus": "MAIN",
    "topic": "TRACE",
    "correlation_id": "abc123"
  }
}
```

### Event Types

The client will receive these event types:

**System Events:**
- `state_snapshot` - Full system state (on connect)
- `system_startup` - System started
- `system_shutdown` - System shutting down
- `config_changed` - Configuration updated

**Agent Events:**
- `agent_status` - Agent status update (5s aggregation)
- `agent_heartbeat` - Agent heartbeat
- `agent_error` - Agent error

**Mission Events:**
- `mission_started` - Mission started
- `mission_progress` - Mission progress update
- `mission_completed` - Mission completed successfully
- `mission_failed` - Mission failed

**Collaboration Events:**
- `collab_started` - Collaboration session started
- `collab_proposal` - Agent proposed solution
- `collab_consensus` - Consensus reached
- `collab_complete` - Collaboration complete

**Log Events:**
- `log_trace` - TRACE level log
- `log_info` - INFO level log
- `log_warn` - WARN level log
- `log_error` - ERROR level log

**Performance Events:**
- `perf_metric` - Agent performance metric
- `perf_system` - System performance (1Hz)

### Color Coding

The test client uses ANSI colors:
- 🔴 **Red** - Errors, failures
- 🟡 **Yellow** - Warnings, disconnects
- 🟢 **Green** - Success, completions
- 🔵 **Cyan** - Info, system messages
- 🟣 **Magenta** - Agent/Mission IDs
- ⚪ **Dim** - Debug, verbose details

## API Endpoints

### REST Endpoints

```bash
# Health check
curl http://localhost:8765/health

# WebSocket system health
curl http://localhost:8765/ws/health

# System statistics
curl http://localhost:8765/stats

# Debug: Active connections
curl http://localhost:8765/debug/connections

# Debug: Cache contents
curl http://localhost:8765/debug/cache

# API documentation (Swagger UI)
open http://localhost:8765/docs
```

### WebSocket Endpoint

```
WS ws://localhost:8765/ws/cockpit
```

**Query Parameters:**
- `agent_ids` - Comma-separated agent IDs (e.g., `agent-1,agent-2`)
- `mission_ids` - Comma-separated mission IDs
- `log_levels` - Comma-separated log levels (`TRACE,INFO,WARN,ERROR`)
- `event_types` - Comma-separated event types
- `client_id` - Custom client identifier (default: auto-generated)

**Example URLs:**

```
# All events
ws://localhost:8765/ws/cockpit

# Filter by agent
ws://localhost:8765/ws/cockpit?agent_ids=web-scraper,coder

# Filter by log level
ws://localhost:8765/ws/cockpit?log_levels=ERROR,WARN

# Multiple filters
ws://localhost:8765/ws/cockpit?agent_ids=agent-1&log_levels=ERROR&event_types=AGENT_STATUS
```

## Testing Scenarios

### Scenario 1: Basic Connection

```bash
# Terminal 1
python start.py

# Terminal 2
python scripts/test_websocket_client.py
```

**Expected:**
- ✅ Connection successful
- ✅ State snapshot received (agents, missions, system metrics)
- ✅ Event replay (last 5 minutes or 100 events)
- ✅ Real-time events streaming
- ✅ Heartbeat pings every 30s

### Scenario 2: Filtered Events

```bash
python scripts/test_websocket_client.py --log-levels ERROR,WARN --verbose
```

**Expected:**
- ✅ Only ERROR and WARN log events received
- ✅ Other event types filtered out
- ✅ Verbose mode shows full message details

### Scenario 3: Multiple Clients

```bash
# Terminal 2
python scripts/test_websocket_client.py --agent-ids agent-1

# Terminal 3
python scripts/test_websocket_client.py --agent-ids agent-2

# Terminal 4
python scripts/test_websocket_client.py
```

**Expected:**
- ✅ All 3 clients connected
- ✅ Each receives filtered events independently
- ✅ No cross-client interference

### Scenario 4: Auto-Reconnect

```bash
# Start client
python scripts/test_websocket_client.py

# Stop server (Ctrl+C in Terminal 1)
# Wait 5-10 seconds
# Restart server

python start.py
```

**Expected:**
- ✅ Client detects disconnect
- ✅ Auto-reconnect with exponential backoff (2s, 4s, 8s, ...)
- ✅ Successful reconnection when server available
- ✅ Event streaming resumes

### Scenario 5: State Snapshot

```bash
python scripts/test_websocket_client.py --verbose
```

**On connect:**
- ✅ Receives `state_snapshot` event
- ✅ Contains: agents, missions, system_metrics, cache_stats

**Manual request:**
Send message to server:
```json
{"type": "request_snapshot"}
```

**Force refresh:**
```json
{"type": "request_snapshot", "force_refresh": true}
```

### Scenario 6: Filter Updates

```bash
python scripts/test_websocket_client.py
```

**Runtime filter update:**
Send message to server:
```json
{
  "type": "update_filters",
  "filters": {
    "agent_ids": ["agent-1", "agent-2"],
    "log_levels": ["ERROR", "WARN"]
  }
}
```

**Expected:**
- ✅ Server updates client subscription
- ✅ Only matching events received going forward

## Browser Testing

### Using WebSocket Test Tool

Open browser developer console:

```javascript
// Connect
const ws = new WebSocket('ws://localhost:8765/ws/cockpit');

// Handle messages
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log(`[${message.type}]`, message);
};

// Handle errors
ws.onerror = (error) => console.error('WebSocket error:', error);
ws.onclose = () => console.log('WebSocket closed');

// Request snapshot
ws.send(JSON.stringify({type: 'request_snapshot'}));

// Update filters
ws.send(JSON.stringify({
  type: 'update_filters',
  filters: {agent_ids: ['agent-1'], log_levels: ['ERROR']}
}));

// Close
ws.close();
```

### Using wscat (CLI tool)

```bash
# Install wscat
npm install -g wscat

# Connect
wscat -c ws://localhost:8765/ws/cockpit

# Send messages
> {"type": "request_snapshot"}
> {"type": "update_filters", "filters": {"log_levels": ["ERROR"]}}
```

## Performance Testing

### Metrics to Monitor

1. **Throughput**
   - Messages/second (check `/stats` endpoint)
   - Target: 1000+ messages/min per client

2. **Latency**
   - Event publish → client receive time
   - Target: <100ms for critical events, <5s for aggregated

3. **Connection Stability**
   - Uptime without disconnects
   - Auto-reconnect success rate

4. **Memory Usage**
   - Event history: 1000 events max (circular buffer)
   - Agent cache: 1000 agents max (LRU eviction)
   - Mission cache: 500 missions max (LRU eviction)

### Load Testing

```bash
# Start 10 concurrent clients
for i in {1..10}; do
  python scripts/test_websocket_client.py --agent-ids agent-$i &
done

# Monitor server stats
watch -n 1 'curl -s http://localhost:8765/stats | jq .'

# Check active connections
curl http://localhost:8765/debug/connections | jq '.total_connections'
```

## Troubleshooting

### Connection Refused

**Problem:** `Connection refused` error

**Solutions:**
1. Check server is running: `curl http://localhost:8765/health`
2. Check correct port: Default is 8765
3. Check firewall: Allow port 8765

### No Events Received

**Problem:** Client connected but no events

**Solutions:**
1. Check filters: Try with no filters first
2. Generate test events: Publish to TripleBus
3. Check `/ws/health`: Verify WebSocketManager started
4. Check `/debug/cache`: Verify cache populated

### Frequent Disconnects

**Problem:** Client keeps disconnecting

**Solutions:**
1. Check network stability
2. Check server logs for errors
3. Disable heartbeat timeout (increase from 10s)
4. Check `max_reconnect_delay` (default 30s)

### High Memory Usage

**Problem:** Server memory growing

**Solutions:**
1. Check event history size: `/stats` → `event_history_size`
2. Check cache sizes: `/debug/cache` → `cache_stats`
3. Verify LRU eviction working (max 1000 agents, 500 missions)
4. Check for memory leaks in custom handlers

## Next Steps

1. **Integration Tests** (Todo #11)
   - Automated pytest tests for full stack
   - Test all connection scenarios
   - Test filter updates, snapshots, heartbeat

2. **WPF Cockpit UI** (Todo #12)
   - Build Cockpit with AvalonDock
   - Real-time agent roster (left sidebar)
   - Mission dashboard (center)
   - Logs pane (bottom)

3. **Production Hardening**
   - Add JWT authentication
   - Implement rate limiting (1000 msg/min)
   - Configure CORS properly
   - Remove debug endpoints
   - Add monitoring/alerting

## References

- WebSocket Event Schema: `dexter_autonomy/api/websocket_events.py`
- Connection Manager: `dexter_autonomy/api/connection_manager.py`
- WebSocket Manager: `dexter_autonomy/api/websocket_manager.py`
- FastAPI App: `dexter_autonomy/ui_bridge/api.py`
- Test Client: `scripts/test_websocket_client.py`
- Architecture: `.github/copilot-instructions.md`

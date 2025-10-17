# Dexter Cockpit Issue Diagnosis

**Date**: October 16, 2025  
**Status**: 🔴 **Cockpit Does Not Run** - WebSocket Endpoint Mismatch

---

## Problem Summary

The Dexter Cockpit WPF application starts but immediately shows an error window. The underlying issue is a **WebSocket endpoint mismatch** between what the Cockpit expects and what the backend provides.

---

## Root Cause

### What the Cockpit Expects

The `DexterWebSocketClient.cs` tries to connect to **5 separate WebSocket channels**:

```csharp
// From cockpit/DexterCockpit/Services/DexterWebSocketClient.cs lines 51-78
_wsLogs = new WebSocket($"{_baseUrl}/ws/logs");          // ❌ Does not exist
_wsAgents = new WebSocket($"{_baseUrl}/ws/agents");      // ❌ Does not exist
_wsMissions = new WebSocket($"{_baseUrl}/ws/missions");  // ❌ Does not exist
_wsPerformance = new WebSocket($"{_baseUrl}/ws/performance"); // ❌ Does not exist
_wsConfig = new WebSocket($"{_baseUrl}/ws/config");      // ❌ Does not exist
```

### What the Backend Actually Provides

The FastAPI backend (`dexter_autonomy/ui_bridge/api.py`) only has **ONE** WebSocket endpoint:

```python
# From dexter_autonomy/ui_bridge/api.py line ~180
@app.websocket("/ws/cockpit")  # ✅ Single unified endpoint
async def websocket_endpoint(websocket: WebSocket, ...):
    # Handles all event types in one connection
```

---

## Architecture Mismatch

### Backend Architecture (What We Have)

```
Backend (/ws/cockpit) - SINGLE CONNECTION
    ↓
WebSocketManager
    ↓
Filters events by:
    • agents: ["*"] or ["agent-1", "agent-2"]
    • missions: ["*"] or ["mission-123"]
    • event_types: ["agent_status", "log_entry", "mission_update", ...]
    • log_level: "INFO", "WARNING", "ERROR", etc.
    ↓
Sends JSON events:
{
    "type": "agent_status",
    "timestamp": 1234567890.123,
    "data": { ... }
}
```

### Cockpit Architecture (What Was Designed)

```
Cockpit - MULTIPLE CONNECTIONS
    ↓
5 separate WebSocket clients:
    • /ws/logs          → LogReceived event
    • /ws/agents        → AgentStatusChanged event
    • /ws/missions      → MissionUpdated event
    • /ws/performance   → PerformanceDataReceived event
    • /ws/config        → ConfigChanged event
```

---

## Why This Happened

The Cockpit was designed with a **multi-channel architecture** (5 separate WebSocket connections), but the backend was implemented with a **unified single-channel architecture** (one WebSocket connection with client-side filtering).

Both architectures are valid, but they need to match!

---

## Solution Options

### Option 1: Fix the Cockpit (Recommended) ⭐

**Change**: Modify `DexterWebSocketClient.cs` to use the single `/ws/cockpit` endpoint and route events internally.

**Pros**:
- Backend is already working
- Matches WebSocket best practices (one connection, multiple event types)
- No backend changes needed

**Cons**:
- Requires C# code changes
- Need to rebuild Cockpit

**Implementation**:

```csharp
// DexterWebSocketClient.cs - UPDATED

public class DexterWebSocketClient : IDisposable
{
    private WebSocket? _ws;  // Single connection
    
    public async Task ConnectAsync()
    {
        _ws = new WebSocket($"{_baseUrl}/ws/cockpit");
        
        _ws.OnMessage += (sender, e) => 
        {
            var json = JObject.Parse(e.Data);
            var eventType = json["type"]?.ToString();
            
            switch (eventType)
            {
                case "log_entry":
                    LogReceived?.Invoke(this, new LogReceivedEventArgs(json));
                    break;
                case "agent_status":
                    AgentStatusChanged?.Invoke(this, new AgentStatusEventArgs(json));
                    break;
                case "mission_update":
                    MissionUpdated?.Invoke(this, new MissionUpdateEventArgs(json));
                    break;
                case "performance_metric":
                    PerformanceDataReceived?.Invoke(this, new PerformanceDataEventArgs(json));
                    break;
                case "config_changed":
                    ConfigChanged?.Invoke(this, new ConfigChangedEventArgs(json));
                    break;
            }
        };
        
        _ws.Connect();
        
        // Send subscription after connect
        var subscription = new {
            type = "subscribe",
            agents = new[] { "*" },
            missions = new[] { "*" },
            event_types = new[] { "*" },
            log_level = "INFO"
        };
        _ws.Send(JsonConvert.SerializeObject(subscription));
        
        IsConnected = true;
        Connected?.Invoke(this, EventArgs.Empty);
    }
    
    public void Disconnect()
    {
        _ws?.Close();
        IsConnected = false;
        Disconnected?.Invoke(this, EventArgs.Empty);
    }
}
```

---

### Option 2: Fix the Backend

**Change**: Add 5 separate WebSocket endpoints to match what Cockpit expects.

**Pros**:
- No Cockpit changes needed
- Matches original Cockpit design

**Cons**:
- Duplicates WebSocket infrastructure
- More connections = more overhead
- Backend needs significant refactoring

**Not Recommended** - The unified single-channel approach is better.

---

## Current System Status

### ✅ Working Components
- Backend FastAPI server: `http://localhost:8765`
- WebSocket endpoint: `ws://localhost:8765/ws/cockpit`
- BSM, Time Machine, Triple Bus: All running
- Health checks: Working
- REST API: Working

### ❌ Not Working
- Cockpit UI: Crashes on startup (WebSocket connection failure)
- WebSocket channels: Endpoint mismatch

---

## Temporary Workaround

While the Cockpit is being fixed, you can interact with the system via:

### 1. REST API (curl)
```bash
# Health check
curl http://localhost:8765/health

# Chat with Dexter
curl -X POST http://localhost:8765/dexter/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello Dexter"}'
```

### 2. Python WebSocket Client
```python
import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8765/ws/cockpit"
    async with websockets.connect(uri) as ws:
        # Subscribe
        await ws.send(json.dumps({
            "type": "subscribe",
            "agents": ["*"],
            "missions": ["*"],
            "log_level": "INFO"
        }))
        
        # Receive events
        async for message in ws:
            event = json.loads(message)
            print(f"Event: {event['type']}")

asyncio.run(test())
```

### 3. Browser WebSocket
Open browser console on any page:
```javascript
const ws = new WebSocket('ws://localhost:8765/ws/cockpit');
ws.onopen = () => {
    ws.send(JSON.stringify({
        type: 'subscribe',
        agents: ['*'],
        missions: ['*'],
        log_level: 'INFO'
    }));
};
ws.onmessage = (e) => {
    console.log('Event:', JSON.parse(e.data));
};
```

---

## Fix Implementation Steps

### Step 1: Backup Current Code
```powershell
cd M:\Dexter-Gliksbot\cockpit\DexterCockpit
Copy-Item Services\DexterWebSocketClient.cs Services\DexterWebSocketClient.cs.backup
```

### Step 2: Update DexterWebSocketClient.cs
Replace the multi-channel implementation with single-channel + event routing (see code above).

### Step 3: Update Event Args Classes
Ensure event args classes can parse from JObject:
```csharp
public class LogReceivedEventArgs : EventArgs
{
    public string Level { get; set; }
    public string Message { get; set; }
    public DateTime Timestamp { get; set; }
    
    public LogReceivedEventArgs(JObject json)
    {
        var data = json["data"];
        Level = data?["level"]?.ToString() ?? "INFO";
        Message = data?["message"]?.ToString() ?? "";
        Timestamp = DateTimeOffset.FromUnixTimeMilliseconds(
            (long)(json["timestamp"]?.ToObject<double>() * 1000 ?? 0)
        ).DateTime;
    }
}
```

### Step 4: Rebuild
```powershell
cd M:\Dexter-Gliksbot\cockpit\DexterCockpit
dotnet build
```

### Step 5: Test
```powershell
.\Launch-Dexter-Cockpit.ps1
```

---

## Backend Event Types Reference

The `/ws/cockpit` endpoint emits these event types:

```json
{
  "type": "agent_status",
  "timestamp": 1234567890.123,
  "data": {
    "agent_id": "agent-1",
    "status": "idle",
    "current_mission": null,
    "uptime": 123.45
  }
}

{
  "type": "log_entry",
  "timestamp": 1234567890.123,
  "data": {
    "level": "INFO",
    "agent_id": "dexter",
    "message": "Task completed",
    "topic": "main"
  }
}

{
  "type": "mission_update",
  "timestamp": 1234567890.123,
  "data": {
    "mission_id": "mission-123",
    "status": "in_progress",
    "progress": 0.5,
    "assigned_to": "agent-1"
  }
}

{
  "type": "performance_metric",
  "timestamp": 1234567890.123,
  "data": {
    "cpu_percent": 45.2,
    "memory_mb": 1024,
    "redis_queue_depth": 5,
    "brain_size_mb": 256
  }
}

{
  "type": "config_changed",
  "timestamp": 1234567890.123,
  "data": {
    "changed_keys": ["agents.dexter.model"],
    "reload_required": false
  }
}
```

---

## Testing the Fix

Once the Cockpit is fixed, verify:

1. **Connection established**: No error window on startup
2. **Agent roster populates**: Left sidebar shows agents
3. **Logs stream**: Bottom panel shows log entries
4. **Performance metrics update**: Charts in performance tab
5. **Chat works**: Can send messages to Dexter
6. **TTS optional**: May not work without voice models installed

---

## Recommendation

**Priority**: HIGH  
**Effort**: 2-4 hours (C# developer)  
**Impact**: Cockpit becomes fully functional

Fix Option 1 (update Cockpit to use `/ws/cockpit`) is strongly recommended because:
1. Backend is already production-ready
2. Single WebSocket connection is more efficient
3. Follows WebSocket best practices
4. No backend changes needed

---

**Last Updated**: October 16, 2025  
**Status**: Diagnosis complete, fix defined, awaiting implementation

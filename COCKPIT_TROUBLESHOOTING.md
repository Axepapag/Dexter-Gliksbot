# Cockpit UI Troubleshooting

**Date**: October 16, 2025  
**Issue**: Cockpit shows "Error" window on startup

---

## Current Status

✅ **Backend**: RUNNING and HEALTHY
- Health check: PASS
- WebSocket system: HEALTHY
- Chat endpoints: WORKING
- Provider system: OPERATIONAL

❌ **Cockpit UI**: Shows "Error" window
- Process starts: YES (PID found)
- Window opens: YES
- Window title: "Error" (indicates exception)
- Likely issue: Initialization exception

---

## What Works

1. ✅ Backend server on port 8765
2. ✅ WebSocket endpoint `/ws/cockpit`
3. ✅ All REST API endpoints
4. ✅ Cockpit compiles without errors
5. ✅ All DLL dependencies resolved

---

## What Doesn't Work

1. ❌ Cockpit UI initialization
2. ❌ Window shows generic "Error" title
3. ❌ No visible UI (just error dialog)

---

## Likely Causes

### 1. WebSocket Connection Timeout
The Cockpit tries to connect to `ws://localhost:8765/ws/cockpit` during initialization. If this times out or fails, it shows an error.

**Check**: WebSocket is healthy (confirmed above)

### 2. Missing ViewModel Dependencies
One of the ViewModels might be failing to initialize due to missing services.

**Check**: All ViewModels exist (confirmed)

### 3. DexterApiClient Initialization
The `DexterApiClient` might be failing to reach the backend.

**Location**: `cockpit/DexterCockpit/Services/DexterApiClient.cs`

### 4. AvalonDock Layout Issues
The docking system might be failing to load saved layouts.

**Check**: Layout persistence code

---

## Diagnostic Steps

### Step 1: Check Windows Event Log

```powershell
Get-EventLog -LogName Application -Source ".NET Runtime" -Newest 5 | 
    Where-Object {$_.TimeGenerated -gt (Get-Date).AddMinutes(-5)} | 
    Select-Object TimeGenerated, Message
```

### Step 2: Run with Console Output

The Cockpit is a WPF app with no console by default. The error dialog should show the exception message.

**What to look for in error dialog**:
- Connection refused
- Timeout
- NullReferenceException
- Service not found

### Step 3: Check Backend Logs

The backend should log when Cockpit attempts to connect:

```powershell
# Backend should show WebSocket connection attempts
# Look for:
# - "WebSocket connection request from..."
# - Connection errors
# - Authentication failures
```

### Step 4: Test WebSocket from Browser

Open browser console and test WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8765/ws/cockpit');
ws.onopen = () => {
    console.log('Connected!');
    ws.send(JSON.stringify({
        type: 'subscribe',
        agents: ['*'],
        missions: ['*'],
        log_level: 'INFO'
    }));
};
ws.onmessage = (e) => console.log('Message:', e.data);
ws.onerror = (e) => console.error('Error:', e);
ws.onclose = (e) => console.log('Closed:', e.code, e.reason);
```

---

## Quick Fixes to Try

### Fix 1: Disable WebSocket Auto-Connect

Edit `MainWindow.xaml.cs`:

```csharp
// Comment out auto-initialization
// Loaded += async (s, e) => await _viewModel.InitializeAsync();

// Let user manually connect via button
```

### Fix 2: Add Timeout to WebSocket Connection

Edit `DexterWebSocketClient.cs`:

```csharp
_ws.WaitTime = TimeSpan.FromSeconds(5);  // Add timeout
```

### Fix 3: Simplify Initialization

Edit `MainViewModel.cs`:

```csharp
public async Task InitializeAsync()
{
    _logger.LogInformation("Initializing...");
    
    try
    {
        // Comment out WebSocket connection temporarily
        // await _wsClient.ConnectAsync();
        
        // Just load UI without backend connection
        IsConnected = false;
        ConnectionStatus = "Disconnected (manual mode)";
        
        _logger.LogInformation("Initialized in offline mode");
    }
    catch (Exception ex)
    {
        _logger.LogError(ex, "Initialization failed");
        ConnectionStatus = $"Error: {ex.Message}";
    }
}
```

This would let the UI load even if backend is unreachable.

---

## Root Cause Analysis

Based on symptoms:
1. Backend is healthy ✅
2. WebSocket is operational ✅
3. Cockpit compiles ✅
4. Cockpit process starts ✅
5. Shows "Error" window ❌

**Most Likely**: The WebSocket connection in `DexterWebSocketClient.ConnectAsync()` is either:
- Throwing an exception
- Timing out
- Receiving unexpected response

**Why**: The WebSocket connection is synchronous in the UI thread during window load, blocking the UI and causing a timeout or exception.

---

## Recommended Solution

### Option 1: Make WebSocket Connection Async (Non-Blocking)

Don't connect during window load. Connect after window is shown:

```csharp
// MainWindow.xaml.cs
public MainWindow(MainViewModel viewModel)
{
    InitializeComponent();
    _viewModel = viewModel;
    DataContext = _viewModel;

    // Don't block on load
    Loaded += OnLoaded;
    Closing += (s, e) => _viewModel.Dispose();
}

private async void OnLoaded(object sender, RoutedEventArgs e)
{
    // Connect asynchronously AFTER window is shown
    await Task.Delay(500);  // Let UI render first
    await _viewModel.InitializeAsync();
}
```

### Option 2: Add Manual Connect Button

Add a "Connect" button to the UI so user can connect when ready:

```xml
<Button Content="Connect to Backend" 
        Command="{Binding ConnectCommand}"
        IsEnabled="{Binding IsConnected, Converter={StaticResource InverseBoolConverter}}"/>
```

### Option 3: Better Error Handling

Catch exceptions and show them in UI instead of crashing:

```csharp
try
{
    await _wsClient.ConnectAsync();
}
catch (Exception ex)
{
    // Don't crash - just show error in status bar
    ConnectionStatus = $"Connection failed: {ex.Message}";
    IsConnected = false;
    
    // Show MessageBox with details
    System.Windows.MessageBox.Show(
        $"Could not connect to backend:\n\n{ex.Message}\n\nYou can retry from the menu.",
        "Connection Error",
        MessageBoxButton.OK,
        MessageBoxImage.Warning
    );
}
```

---

## Temporary Workaround

Until the Cockpit is fixed, you can interact with the system via:

### 1. REST API

```powershell
# Chat with Dexter
$body = @{message="Hello Dexter"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8765/dexter/chat" -Method Post -Body $body -ContentType "application/json"

# Check health
Invoke-RestMethod -Uri "http://localhost:8765/health" -Method Get
```

### 2. Browser WebSocket Client

Create `test-cockpit.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Dexter Cockpit Test</title>
</head>
<body>
    <h1>Dexter WebSocket Test</h1>
    <button onclick="connect()">Connect</button>
    <button onclick="disconnect()">Disconnect</button>
    <div id="status">Disconnected</div>
    <div id="messages" style="height: 400px; overflow-y: scroll; border: 1px solid black; margin-top: 10px;"></div>
    
    <script>
        let ws = null;
        
        function connect() {
            ws = new WebSocket('ws://localhost:8765/ws/cockpit');
            
            ws.onopen = () => {
                document.getElementById('status').textContent = 'Connected';
                ws.send(JSON.stringify({
                    type: 'subscribe',
                    agents: ['*'],
                    missions: ['*'],
                    log_level: 'INFO'
                }));
            };
            
            ws.onmessage = (e) => {
                const msg = document.createElement('div');
                msg.textContent = e.data;
                document.getElementById('messages').appendChild(msg);
            };
            
            ws.onerror = (e) => {
                document.getElementById('status').textContent = 'Error: ' + e;
            };
            
            ws.onclose = () => {
                document.getElementById('status').textContent = 'Disconnected';
            };
        }
        
        function disconnect() {
            if (ws) ws.close();
        }
    </script>
</body>
</html>
```

---

## Next Steps

1. **Capture the actual error message** from the Cockpit error dialog
2. **Check Windows Event Log** for .NET Runtime errors
3. **Implement one of the recommended solutions** (async connect, manual button, or better error handling)
4. **Test with simplified initialization** (offline mode first)

Once we know the exact exception, we can fix it properly.

---

**Status**: Awaiting error details from Cockpit error dialog


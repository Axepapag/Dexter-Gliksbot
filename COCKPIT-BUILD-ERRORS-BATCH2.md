# 🔧 Cockpit Build Errors - Batch 2 (24 Errors)

**Date:** October 14, 2025  
**Status:** 🔴 **IN PROGRESS** - Systematic fixes needed

---

## 📊 Error Breakdown

| Category | Count | Priority |
|----------|-------|----------|
| DexterWebSocketClient API | 7 | **HIGH** |
| LogLevel Ambiguity | 6 | **MEDIUM** |
| WebSocket Dispose | 5 | **HIGH** |
| LogEntry.Id Missing | 1 | **MEDIUM** |
| ExportLogsAsync Parameters | 2 | **MEDIUM** |
| **LiveCharts Warnings** | 6 | LOW (safe) |
| **TOTAL ERRORS** | **21** | - |

---

## 🐛 Error Category 1: DexterWebSocketClient API Mismatches (7 errors)

### Error 1.1: Constructor Missing baseUrl Parameter
**File:** `App.xaml.cs` (line 37)  
**Error:** `CS7036: No argument for required parameter 'baseUrl'`

**Current Code:**
```csharp
services.AddSingleton<DexterWebSocketClient>(sp =>
    new DexterWebSocketClient(sp.GetRequiredService<ILogger<DexterWebSocketClient>>()));
```

**Fix:**
```csharp
services.AddSingleton<DexterWebSocketClient>(sp =>
    new DexterWebSocketClient("http://localhost:8765", sp.GetRequiredService<ILogger<DexterWebSocketClient>>()));
```

---

### Errors 1.2-1.3: Missing Connected/Disconnected Events
**Files:** `MainViewModel.cs` (lines 59, 60, 115, 116)  
**Errors:** `CS1061: 'DexterWebSocketClient' does not contain 'Connected' or 'Disconnected'`

**Problem:** WebSocketClient doesn't expose these events

**Solution Options:**
1. **Add events to WebSocketClient** (recommended)
2. Poll `IsConnected` property
3. Subscribe to first data event as "connected" indicator

**Recommended Fix - Add to DexterWebSocketClient.cs:**
```csharp
public event EventHandler? Connected;
public event EventHandler? Disconnected;

// In ConnectAsync():
IsConnected = true;
Connected?.Invoke(this, EventArgs.Empty);

// In Disconnect():
IsConnected = false;
Disconnected?.Invoke(this, EventArgs.Empty);
```

---

### Error 1.4: DisconnectAsync Method Missing
**File:** `MainViewModel.cs` (line 117)  
**Error:** `CS1061: 'DexterWebSocketClient' does not contain 'DisconnectAsync'`

**Problem:** Method is called `Disconnect()`, not `DisconnectAsync()`

**Fix in MainViewModel.cs:**
```csharp
// Change this:
await _wsClient.DisconnectAsync();

// To this:
_wsClient.Disconnect();
```

---

### Error 1.5: ConnectAsync Takes No Arguments
**File:** `MainViewModel.cs` (line 74)  
**Error:** `CS1501: No overload for 'ConnectAsync' takes 1 arguments`

**Current signature:**
```csharp
public async Task ConnectAsync()  // No parameters
```

**Fix in MainViewModel.cs:**
```csharp
// Change this:
await _wsClient.ConnectAsync(someArg);

// To this:
await _wsClient.ConnectAsync();
```

---

## 🐛 Error Category 2: LogLevel Ambiguity (6 errors)

**Files:** `LogsViewModel.cs` (lines 153, 153, 162, 298, 299, 300, 301, 302)  
**Errors:** `CS0104: 'LogLevel' is ambiguous between 'DexterCockpit.Models.LogLevel' and 'Microsoft.Extensions.Logging.LogLevel'`

**Problem:** We only fixed line 339 in `ParseLogLevel()`. There are **MORE instances** throughout the file.

**Fix Strategy:** Use `Models.LogLevel` everywhere in LogsViewModel.cs

**Lines to Fix:**
- Line 153: `LogLevel` → `Models.LogLevel` (2 instances)
- Line 162: `LogLevel` → `Models.LogLevel`
- Line 298-302: `LogLevel` → `Models.LogLevel` (5 instances)

---

## 🐛 Error Category 3: WebSocket Dispose Issues (5 errors)

**File:** `DexterWebSocketClient.cs` (lines 208-212)  
**Errors:** `CS1061: 'WebSocket' does not contain 'Dispose'`

**Problem:** WebSocketSharp's `WebSocket` class doesn't implement `IDisposable`

**Current Code:**
```csharp
public void Dispose()
{
    _wsLogs?.Dispose();      // ❌ Doesn't exist
    _wsAgents?.Dispose();    // ❌ Doesn't exist
    _wsPerformance?.Dispose(); // ❌ Doesn't exist
    _wsMissions?.Dispose();  // ❌ Doesn't exist
    _wsConfig?.Dispose();    // ❌ Doesn't exist
}
```

**Fix:**
```csharp
public void Dispose()
{
    // WebSocketSharp's WebSocket doesn't implement IDisposable
    // Use Close() instead, which properly cleans up
    _wsLogs?.Close();
    _wsAgents?.Close();
    _wsMissions?.Close();
    _wsPerformance?.Close();
    _wsConfig?.Close();
}
```

---

## 🐛 Error Category 4: LogEntry.Id Missing (1 error)

**File:** `LogsViewModel.cs` (line 111)  
**Error:** `CS0117: 'LogEntry' does not contain definition for 'Id'`

**Problem:** LogEntry model doesn't have an `Id` property

**Solution Options:**
1. **Add Id property to LogEntry model**
2. Use a different unique identifier
3. Use index or generated GUID

**Recommended Fix - Add to LogEntry.cs:**
```csharp
public partial class LogEntry : ObservableObject
{
    public string Id { get; set; } = Guid.NewGuid().ToString();  // Add this
    
    // ... existing properties ...
}
```

---

## 🐛 Error Category 5: ExportLogsAsync Parameter Issues (2 errors)

**Files:** `LogsViewModel.cs` (lines 227, 261)  
**Errors:** `CS1739: Best overload for 'ExportLogsAsync' does not have parameter named 'format'`

**Problem:** Method signature doesn't match usage

**Current Usage:**
```csharp
await ExportLogsAsync(format: "jsonl");  // Line 227
await ExportLogsAsync(format: "csv");    // Line 261
```

**Need to check ExportLogsAsync method signature and fix either:**
1. Add `format` parameter to method
2. Remove `format:` from call sites

---

## ⚠️ LiveCharts Warnings (6 warnings - SAFE TO IGNORE)

These are the same warnings we documented earlier. They do NOT block the build:

```
warning NU1701: Package 'LiveCharts 0.9.7' was restored using '.NETFramework...'
```

**Status:** ✅ Safe to ignore (works perfectly on .NET 8.0)

---

## 📋 Fix Priority Order

1. **HIGH PRIORITY** (Breaks compilation):
   - DexterWebSocketClient constructor (App.xaml.cs)
   - WebSocket Dispose → Close (DexterWebSocketClient.cs)
   - Add Connected/Disconnected events (DexterWebSocketClient.cs)

2. **MEDIUM PRIORITY** (API mismatches):
   - LogLevel ambiguity (all remaining instances)
   - LogEntry.Id property
   - ExportLogsAsync parameters

3. **LOW PRIORITY** (Already documented):
   - LiveCharts warnings (ignore)

---

## 🛠️ Implementation Plan

### Step 1: Fix DexterWebSocketClient.cs
```csharp
// Add events
public event EventHandler? Connected;
public event EventHandler? Disconnected;

// Fix Dispose
public void Dispose()
{
    _wsLogs?.Close();
    _wsAgents?.Close();
    _wsMissions?.Close();
    _wsPerformance?.Close();
    _wsConfig?.Close();
}

// Raise events in ConnectAsync
IsConnected = true;
Connected?.Invoke(this, EventArgs.Empty);

// Raise events in Disconnect
IsConnected = false;
Disconnected?.Invoke(this, EventArgs.Empty);
```

### Step 2: Fix App.xaml.cs
```csharp
services.AddSingleton<DexterWebSocketClient>(sp =>
    new DexterWebSocketClient("http://localhost:8765", sp.GetRequiredService<ILogger<DexterWebSocketClient>>()));
```

### Step 3: Fix MainViewModel.cs
```csharp
// Remove argument from ConnectAsync call
await _wsClient.ConnectAsync();

// Change DisconnectAsync to Disconnect
_wsClient.Disconnect();
```

### Step 4: Fix LogsViewModel.cs
- Replace ALL `LogLevel` with `Models.LogLevel` (8 more instances)
- Check ExportLogsAsync signature and fix calls

### Step 5: Fix LogEntry.cs
```csharp
public string Id { get; set; } = Guid.NewGuid().ToString();
```

---

## ✅ Expected Outcome

After fixes:
- **Errors:** 0
- **Warnings:** 2 (LiveCharts - safe)
- **Build:** SUCCESS

---

## 📝 Notes

These errors were NOT caught in our earlier fixes because:
1. We couldn't build on Linux dev container
2. ViewModels use services that weren't fully tested
3. Some LogLevel instances were missed
4. WebSocketSharp API differs from System.Net.WebSockets

**Ready to apply fixes?** Let me know and I'll implement them systematically.

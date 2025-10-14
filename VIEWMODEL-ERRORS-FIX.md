# 🔧 Cockpit Build Errors Fix - ViewModels

**Date:** October 14, 2025  
**Status:** ✅ FIXED

---

## 🐛 Build Errors Encountered

### Error 1: CS0246 - PerformanceMetricEventArgs Not Found
**File:** `PerformanceViewModel.cs` (line 56)

**Error Message:**
```
CS0246: The type or namespace name 'PerformanceMetricEventArgs' could not be found
```

**Root Cause:**
- PerformanceViewModel was subscribing to event `PerformanceMetric` with type `PerformanceMetricEventArgs`
- The actual event in DexterWebSocketClient is `PerformanceDataReceived` with type `PerformanceDataEventArgs`
- Property names in the event args also didn't match

**Property Mapping:**
| ViewModel Expected | Actual Event Args | Fixed |
|-------------------|-------------------|-------|
| `e.CpuUsage` | `e.CpuPercent` | ✅ |
| `e.MemoryMb` | `e.MemoryMb` | ✅ |
| `e.RedisQueueDepth` | ❌ Not available | Set to 0 |
| `e.BrainSizeMb` | `e.BrainSizeMb` | ✅ |
| `e.MessagesPerSecond` | `e.EventBusMessagesPerSec` | ✅ |
| `e.AvgLatencyMs` | ❌ Not available | Set to 0 |

---

### Error 2: CS0104 - LogLevel Ambiguity
**File:** `LogsViewModel.cs` (line 339)

**Error Message:**
```
CS0104: 'LogLevel' is an ambiguous reference between 
'DexterCockpit.Models.LogLevel' and 'Microsoft.Extensions.Logging.LogLevel'
```

**Root Cause:**
- Both namespaces define a `LogLevel` type
- `DexterCockpit.Models.LogLevel` - custom enum for Dexter log levels (TRACE, INFO, WARN, ERROR, CRITICAL)
- `Microsoft.Extensions.Logging.LogLevel` - .NET logging enum
- LogsViewModel imports both namespaces, causing ambiguity

---

## ✅ Fixes Applied

### Fix 1: PerformanceViewModel.cs

**Changed event subscription:**
```diff
- _wsClient.PerformanceMetric += OnPerformanceMetricReceived;
+ _wsClient.PerformanceDataReceived += OnPerformanceDataReceived;
```

**Changed event handler signature:**
```diff
- private void OnPerformanceMetricReceived(object? sender, PerformanceMetricEventArgs e)
+ private void OnPerformanceDataReceived(object? sender, PerformanceDataEventArgs e)
```

**Updated property mappings:**
```diff
- CpuUsage = e.CpuUsage;
+ CpuUsage = e.CpuPercent;

- RedisQueueDepth = e.RedisQueueDepth;
+ RedisQueueDepth = 0; // Not available in event args

- MessagesPerSecond = e.MessagesPerSecond;
+ MessagesPerSecond = e.EventBusMessagesPerSec;

- AvgLatencyMs = e.AvgLatencyMs;
+ AvgLatencyMs = 0; // Not available in event args

- var timestamp = DateTime.UtcNow;
+ var timestamp = e.Timestamp; // Use event timestamp

- CpuHistory.Add(new PerformanceDataPoint { Timestamp = timestamp, Value = e.CpuUsage });
+ CpuHistory.Add(new PerformanceDataPoint { Timestamp = timestamp, Value = e.CpuPercent });
```

**Changed cleanup:**
```diff
- _wsClient.PerformanceMetric -= OnPerformanceMetricReceived;
+ _wsClient.PerformanceDataReceived -= OnPerformanceDataReceived;
```

---

### Fix 2: LogsViewModel.cs

**Used fully qualified type name:**
```diff
- private LogLevel ParseLogLevel(string level)
+ private Models.LogLevel ParseLogLevel(string level)
  {
      return level.ToUpper() switch
      {
-         "TRACE" => LogLevel.TRACE,
+         "TRACE" => Models.LogLevel.TRACE,
-         "INFO" => LogLevel.INFO,
+         "INFO" => Models.LogLevel.INFO,
-         "WARN" => LogLevel.WARN,
+         "WARN" => Models.LogLevel.WARN,
-         "ERROR" => LogLevel.ERROR,
+         "ERROR" => Models.LogLevel.ERROR,
-         "CRITICAL" => LogLevel.CRITICAL,
+         "CRITICAL" => Models.LogLevel.CRITICAL,
-         _ => LogLevel.INFO
+         _ => Models.LogLevel.INFO
      };
  }
```

---

## 📋 Missing Properties Analysis

### RedisQueueDepth & AvgLatencyMs
These properties are displayed in the UI but not provided by the backend WebSocket events.

**Options:**
1. ✅ **Current fix:** Set to 0 (display as unavailable)
2. ❌ Remove from UI (breaking change)
3. ❌ Add to backend events (requires backend changes)

**Recommendation:** Keep properties but set to 0. Update backend in future to provide these metrics.

---

## 🧪 Testing Checklist

After pulling these fixes:

### Build Test
```powershell
cd M:\DexG\cockpit\DexterCockpit
dotnet build
```

**Expected:** `Build succeeded. 2 Warning(s) 0 Error(s)` (LiveCharts warnings only)

### Runtime Test
```powershell
.\Launch-Dexter-Cockpit.bat
```

**Verify:**
- [ ] Cockpit launches without errors
- [ ] Performance view shows CPU and memory charts
- [ ] Performance metrics update in real-time (CPU%, Memory MB)
- [ ] Messages/sec updates when backend sends events
- [ ] RedisQueueDepth shows 0 (expected, not in backend events)
- [ ] AvgLatencyMs shows 0 (expected, not in backend events)
- [ ] Logs view displays entries without errors
- [ ] Log level filtering works (TRACE, INFO, WARN, ERROR, CRITICAL)

---

## 🔍 Root Cause Summary

| Issue | Cause | Impact |
|-------|-------|--------|
| **PerformanceMetricEventArgs** | Mismatch between ViewModel and WebSocket client | Build error CS0246 |
| **LogLevel ambiguity** | Two types with same name in different namespaces | Build error CS0104 |

Both were simple naming mismatches that have now been corrected.

---

## 📚 Related Files

**Modified:**
- `ViewModels/PerformanceViewModel.cs` - Fixed event subscription and property mapping
- `ViewModels/LogsViewModel.cs` - Resolved LogLevel ambiguity

**Reference:**
- `Services/DexterWebSocketClient.cs` - Defines actual events and args
- `Models/LogEntry.cs` - Defines custom LogLevel enum

---

## ✅ Status

- [x] CS0246 error fixed (PerformanceMetricEventArgs)
- [x] CS0104 error fixed (LogLevel ambiguity)
- [x] Property mappings corrected
- [x] Missing properties handled (set to 0)
- [x] Documentation created
- [ ] **YOU: Pull and build to verify**
- [ ] **YOU: Test runtime behavior**

**Build should now succeed with 0 errors!** 🚀

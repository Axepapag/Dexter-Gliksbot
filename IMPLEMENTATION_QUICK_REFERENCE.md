# 🚀 Implementation Quick Reference

**For developers starting work on the three major Cockpit features**

---

## 📁 File Structure to Create

```
cockpit/DexterCockpit/
├── Services/
│   ├── WindowsInterop.cs                    # NEW - Win32 P/Invoke
│   ├── LayoutManager.cs                     # NEW - Layout persistence
│   └── MonitorManager.cs                    # NEW - Display management
├── Controls/
│   └── DockedWindowHost.cs                  # NEW - HwndHost for external windows
├── Models/
│   ├── DockedWindow.cs                      # NEW - Docked window model
│   └── MonitorInfo.cs                       # NEW - Monitor configuration
├── ViewModels/
│   ├── DockedWindowsViewModel.cs            # NEW - Docked windows manager
│   ├── AgentChatViewModel.cs                # NEW - Per-agent chat
│   ├── AgentChatTabManager.cs               # NEW - Tab lifecycle
│   └── MainViewModel.cs                     # MODIFY - Add new VMs
├── Views/
│   ├── DockedWindowsView.xaml               # NEW - Docked windows UI
│   └── AgentRosterView.xaml                 # MODIFY - Add chat button
└── MainWindow.xaml                           # MODIFY - Integrate new panes
```

---

## ⚡ Quick Start Commands

### 1. Create New Files
```powershell
# From cockpit/DexterCockpit directory

# Create directories if missing
New-Item -ItemType Directory -Force -Path Services, Controls

# Create files
New-Item -ItemType File -Path Services/WindowsInterop.cs
New-Item -ItemType File -Path Services/LayoutManager.cs
New-Item -ItemType File -Path Services/MonitorManager.cs
New-Item -ItemType File -Path Controls/DockedWindowHost.cs
New-Item -ItemType File -Path Models/DockedWindow.cs
New-Item -ItemType File -Path ViewModels/DockedWindowsViewModel.cs
New-Item -ItemType File -Path ViewModels/AgentChatViewModel.cs
New-Item -ItemType File -Path ViewModels/AgentChatTabManager.cs
New-Item -ItemType File -Path Views/DockedWindowsView.xaml
```

### 2. Register in DI Container (App.xaml.cs)
```csharp
// Add to ConfigureServices method
services.AddSingleton<WindowsInterop>();
services.AddSingleton<LayoutManager>();
services.AddSingleton<MonitorManager>();
services.AddTransient<DockedWindowsViewModel>();
services.AddTransient<AgentChatTabManager>();
```

### 3. Wire Up MainViewModel
```csharp
public DockedWindowsViewModel DockedWindows { get; }
public AgentChatTabManager ChatTabManager { get; }

// In constructor:
DockedWindows = dockedWindowsVM;
ChatTabManager = chatTabManager;
```

---

## 🔑 Key Code Snippets

### Docking a Window (Win32)
```csharp
// Set as child window
WindowsInterop.SetParent(childHwnd, parentHwnd);

// Modify window style
int style = WindowsInterop.GetWindowLong(childHwnd, WindowsInterop.GWL_STYLE);
style = (style | WindowsInterop.WS_CHILD | WindowsInterop.WS_VISIBLE) & ~WindowsInterop.WS_BORDER;
WindowsInterop.SetWindowLong(childHwnd, WindowsInterop.GWL_STYLE, style);

// Show window
WindowsInterop.ShowWindow(childHwnd, WindowsInterop.SW_SHOW);
```

### Creating Agent Chat Tab
```csharp
var chatViewModel = new AgentChatViewModel(agent, _apiClient, _logger);
var chatView = new ChatView { DataContext = chatViewModel };

var layoutDoc = new LayoutDocument
{
    Title = $"{agent.Name} Chat",
    Content = chatView,
    CanClose = true,
    ContentId = $"agent-chat-{agent.Id}"
};

docPane.Children.Add(layoutDoc);
layoutDoc.IsActive = true;
```

### Saving Layout
```csharp
private void OnWindowClosing(object sender, CancelEventArgs e)
{
    _layoutManager.SaveLayout(dockingManager);
}
```

### Restoring Layout
```csharp
private void OnWindowLoaded(object sender, RoutedEventArgs e)
{
    if (!_layoutManager.RestoreLayout(dockingManager))
    {
        // Fallback to default layout
        _layoutManager.LoadDefaultLayout(dockingManager);
    }
}
```

---

## 🧪 Testing Checklist

### Unit Tests
- [ ] WindowsInterop.DockWindow() with valid/invalid handles
- [ ] DockedWindowsViewModel.ScanForWindows() returns expected apps
- [ ] AgentChatTabManager.OpenAgentChat() creates unique tabs
- [ ] LayoutManager.SaveLayout() creates valid XML
- [ ] MonitorManager.RefreshMonitors() detects all displays

### Integration Tests
- [ ] Dock Unity window → Resize → Undock → No memory leaks
- [ ] Open 10 agent chats → Close all → Memory stable
- [ ] Save layout → Restart app → Layout restored correctly
- [ ] Multi-monitor: Move window → Save → Restore on correct monitor

### Manual Tests
- [ ] Scan for windows finds: Unity, QuickBooks, Browsers
- [ ] Docked window resizes with parent pane
- [ ] Agent chat tabs show isolated histories
- [ ] Layout persists across app restarts
- [ ] Multi-monitor: Floating windows restore to correct screen

---

## 🐛 Common Issues & Fixes

### Issue: `Cannot find package 'Dirkster.AvalonDock'`
**Fix:** Already resolved. Using Dirkster.AvalonDock 4.72.1 for .NET 8.0

### Issue: `SetParent failed (handle invalid)`
**Fix:** Always validate with `WindowsInterop.IsWindow(hwnd)` before operations

### Issue: `Layout restore fails after resolution change`
**Fix:** Implemented monitor compatibility check in LayoutManager

### Issue: `Multiple agent tabs share same history`
**Fix:** Ensure each AgentChatViewModel has unique `agent.Id`

### Issue: `Memory leak from unclosed tabs`
**Fix:** Implement IDisposable on AgentChatViewModel, call in tab.Closed event

---

## 📊 Performance Targets

| Metric | Target | How to Verify |
|--------|--------|---------------|
| Dock window time | <500ms | Stopwatch in DockWindow() |
| Agent tab open time | <100ms | Stopwatch in OpenAgentChat() |
| Layout save time | <1s | Stopwatch in SaveLayout() |
| Memory growth (24hr) | <10% | Task Manager after soak test |
| Max docked windows | 5 | Enforce limit in DockedWindowsViewModel |
| Max agent tabs | 20 | Enforce limit in AgentChatTabManager |

---

## 🔧 Build & Run

### Prerequisites
- .NET 8.0 SDK
- Visual Studio 2022 or Rider
- Windows 10/11 or Windows Server 2022
- Multi-monitor setup (for testing)

### Build
```powershell
cd cockpit/DexterCockpit
dotnet restore
dotnet build
```

### Run
```powershell
# Backend first (separate terminal)
cd ../../
python start.py --port 8765

# Then cockpit
cd cockpit/DexterCockpit
dotnet run
```

### Expected Output
```
Build succeeded.
    2 Warning(s)  <- LiveCharts (safe to ignore)
    0 Error(s)
```

---

## 📚 Related Documentation

- **Main Technical Plan:** `TECHNICAL_PLAN_DOCKED_WINDOWS_AGENT_TABS.md`
- **Visual Roadmap:** `FEATURE_ROADMAP_VISUAL.md`
- **Architecture:** `cockpit/ARCHITECTURE.md`
- **Build Status:** `BUILD-STATUS.md`
- **Copilot Instructions:** `.github/copilot-instructions.md`

---

## 🎯 Priority Order

1. **Start with Multi-Monitor Support** (least risk, foundational)
2. **Then Agent Chat Tabs** (parallel work possible)
3. **Finally Docked Windows** (most complex, needs Win32 expertise)

---

## 🤝 Code Review Checklist

Before submitting PR:
- [ ] All unit tests pass (dotnet test)
- [ ] No memory leaks (run soak test for 1 hour)
- [ ] Follows MVVM pattern (no logic in code-behind)
- [ ] Uses Material Design components (consistent UI)
- [ ] Logging added to all ViewModels (ILogger)
- [ ] Dispose() implemented where needed (IDisposable)
- [ ] XAML follows AvalonDock structure (single LayoutRoot child)
- [ ] Documentation updated (README-COCKPIT.md)

---

**Quick Reference Version:** 1.0  
**Last Updated:** October 16, 2025  
**For:** Developers implementing Phases 1-3 of Cockpit roadmap

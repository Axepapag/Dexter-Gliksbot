# 🎯 Full Technical Implementation Plan: Docked Windows, Agent Chat Tabs, Multi-Monitor Cockpit

**Author:** Copilot AI Agent  
**Date:** October 16, 2025  
**Status:** Technical Review & Implementation Plan  
**Target Platform:** Windows Server 2022 / Windows 10/11  
**Framework:** .NET 8.0, WPF, AvalonDock 4.72.1

---

## 📋 Executive Summary

This document provides a comprehensive technical plan for implementing three major features in the Dexter Mission Control Cockpit:

1. **Docked Windows Manager** - External application docking (Unity, QuickBooks, CAD, chatbots)
2. **Per-Agent Chat Tabs** - Dynamic agent-specific chat windows with full AvalonDock support
3. **Multi-Monitor Support** - Layout persistence, monitor management, window restoration

### Key Metrics
- **Estimated Timeline:** 4-6 weeks (breakdown below)
- **Lines of Code:** ~3,500 new, ~500 modified
- **Risk Level:** Medium (Windows API interop, handle management)
- **Priority:** High (core roadmap features)

---

## 🏗️ Feature 1: Docked Windows Manager

### Overview
Enable external Windows application windows to be embedded directly into the Cockpit UI using Win32 HWND handles. This allows Dexter to monitor and control external applications (Unity editor, QuickBooks, CAD software, chatbot windows) as first-class citizens in the docking layout.

### Technical Architecture

The docked windows feature uses Win32 API `SetParent()` to reparent external application windows into WPF `HwndHost` controls. This creates a seamless integration where external apps appear as native cockpit panels.

### Key Components

#### 1.1 Windows Interop Layer (`Services/WindowsInterop.cs`)

Provides P/Invoke wrappers for Win32 APIs:
- `SetParent()` - Reparent window
- `MoveWindow()` - Resize child window  
- `SetWindowLong()` / `GetWindowLong()` - Modify window styles
- `EnumWindows()` - Scan for dockable windows
- `FindWindow()` - Locate specific windows by title/class

#### 1.2 DockedWindowHost Control (`Controls/DockedWindowHost.cs`)

Custom `HwndHost` implementation that:
- Embeds external HWND as WPF control
- Handles resize events to synchronize child window dimensions
- Manages window lifecycle (dock/undock)
- Restores original parent on dispose

#### 1.3 DockedWindowsViewModel (`ViewModels/DockedWindowsViewModel.cs`)

Manages dockable window list:
- Scans for compatible applications (Unity, QuickBooks, CAD, Chatbots)
- Tracks docked window state
- Provides dock/undock commands
- Persists docked window list to layout

#### 1.4 DockedWindow Model (`Models/DockedWindow.cs`)

Properties:
- `IntPtr Handle` - Window handle
- `string Title` - Window title
- `ApplicationType` - Detected app type (Unity, QB, CAD, etc.)
- `bool IsDocked` - Docking state
- `DateTime LastSeen` - Last detection timestamp

### Implementation Steps

1. **Create WindowsInterop.cs** with P/Invoke declarations
2. **Implement DockedWindowHost** deriving from `HwndHost`
3. **Create DockedWindowsViewModel** with scan/dock logic
4. **Add DockedWindow model** with MVVM properties
5. **Design DockedWindowsView.xaml** with scan/dock UI
6. **Register in DI container** (`App.xaml.cs`)
7. **Integrate into MainWindow** AvalonDock layout
8. **Test with Unity, QuickBooks, Browser windows**

### Code Optimizations

**Optimization 1: Window Handle Validation**
```csharp
// Check if handle is still valid before operations
private bool ValidateHandle(IntPtr hwnd)
{
    if (hwnd == IntPtr.Zero || !WindowsInterop.IsWindow(hwnd))
    {
        _logger.LogWarning("Invalid window handle: 0x{Handle:X}", hwnd.ToInt64());
        return false;
    }
    return true;
}
```

**Optimization 2: Async Window Scanning**
```csharp
[RelayCommand]
public async Task ScanForWindowsAsync()
{
    IsScanning = true;
    try
    {
        var windows = await Task.Run(() => 
        {
            var results = new List<DockedWindow>();
            WindowsInterop.EnumWindows((hWnd, lParam) => 
            {
                // Scanning logic...
                return true;
            }, IntPtr.Zero);
            return results;
        });
        
        DockedWindows = new ObservableCollection<DockedWindow>(windows);
    }
    finally
    {
        IsScanning = false;
    }
}
```

**Optimization 3: Handle Leak Prevention**
```csharp
public class DockedWindowHost : HwndHost, IDisposable
{
    private bool _isDisposed;
    
    protected override void Dispose(bool disposing)
    {
        if (!_isDisposed)
        {
            if (disposing)
            {
                // Restore original parent (prevents handle leak)
                WindowsInterop.SetParent(_childHwnd, IntPtr.Zero);
            }
            _isDisposed = true;
        }
        base.Dispose(disposing);
    }
}
```

### Integration Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Window handle invalidation** | Medium | Periodic `IsWindow()` checks, auto-undock on failure |
| **Target app unresponsive** | Low | Timeout on Win32 calls, graceful error handling |
| **DPI scaling mismatch** | Medium | Use `SetProcessDpiAwareness()` to match target app |
| **Z-order conflicts** | Low | Set `Topmost` on docked pane, use `BringWindowToTop()` |
| **Memory leaks** | Medium | Strict IDisposable implementation, finalizers |

---

## 🗨️ Feature 2: Per-Agent Chat Tabs

### Overview
Dynamic chat tabs for each agent, allowing users to have isolated conversations with specific agents (Dexter, AUM, BSM, ActionExecutor, etc.). Each tab maintains its own history, TTS settings, and connection state.

### Technical Architecture

Uses AvalonDock `LayoutDocument` dynamically added to `LayoutDocumentPane`. Each chat tab is a full `ChatView` instance with its own `AgentChatViewModel`.

### Key Components

#### 2.1 AgentChatViewModel (`ViewModels/AgentChatViewModel.cs`)

Per-agent chat instance:
```csharp
public partial class AgentChatViewModel : ObservableObject, IDisposable
{
    private readonly Agent _agent;
    private readonly DexterApiClient _apiClient;
    private readonly ILogger<AgentChatViewModel> _logger;

    [ObservableProperty]
    private ObservableCollection<ChatMessage> messages = new();

    [ObservableProperty]
    private string userInput = string.Empty;

    [ObservableProperty]
    private bool isTtsEnabled = true;

    [ObservableProperty]
    private bool isAgentTyping = false;

    public string AgentName => _agent.Name;
    public string AgentId => _agent.Id;

    public AgentChatViewModel(Agent agent, DexterApiClient apiClient, ILogger<AgentChatViewModel> logger)
    {
        _agent = agent;
        _apiClient = apiClient;
        _logger = logger;
        LoadChatHistory();
    }

    [RelayCommand]
    public async Task SendMessageAsync()
    {
        if (string.IsNullOrWhiteSpace(UserInput))
            return;

        var userMessage = new ChatMessage
        {
            Sender = "User",
            Content = UserInput,
            Timestamp = DateTime.Now,
            IsFromUser = true
        };
        
        Messages.Add(userMessage);
        _logger.LogInformation("Sending message to {Agent}: {Message}", AgentName, UserInput);

        string messageCopy = UserInput;
        UserInput = string.Empty;
        IsAgentTyping = true;

        try
        {
            // Send to specific agent via API
            var response = await _apiClient.SendAgentMessageAsync(_agent.Id, messageCopy);
            
            var agentMessage = new ChatMessage
            {
                Sender = AgentName,
                Content = response.Message,
                Timestamp = DateTime.Now,
                IsFromUser = false
            };
            
            Messages.Add(agentMessage);

            // TTS if enabled
            if (IsTtsEnabled)
            {
                await SpeakAsync(response.Message);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send message to {Agent}", AgentName);
            Messages.Add(new ChatMessage
            {
                Sender = "System",
                Content = $"Error: {ex.Message}",
                Timestamp = DateTime.Now,
                IsError = true
            });
        }
        finally
        {
            IsAgentTyping = false;
        }
    }

    private async Task SpeakAsync(string text)
    {
        // TTS implementation (reuse from ChatViewModel)
        // Can use per-agent voice profiles
    }

    private void LoadChatHistory()
    {
        // Load from brain/SQLite per agent_id and task_root
        // Implement pagination for large histories
    }

    public void Dispose()
    {
        // Save chat history to brain
        _logger.LogInformation("Closing chat with {Agent}", AgentName);
    }
}
```

#### 2.2 AgentChatTabManager (`ViewModels/AgentChatTabManager.cs`)

Manages dynamic tab creation/removal:
```csharp
public class AgentChatTabManager
{
    private readonly DockingManager _dockingManager;
    private readonly IServiceProvider _serviceProvider;
    private readonly Dictionary<string, LayoutDocument> _openChats = new();
    private readonly ILogger<AgentChatTabManager> _logger;

    public AgentChatTabManager(
        DockingManager dockingManager,
        IServiceProvider serviceProvider,
        ILogger<AgentChatTabManager> logger)
    {
        _dockingManager = dockingManager;
        _serviceProvider = serviceProvider;
        _logger = logger;
    }

    public void OpenAgentChat(Agent agent)
    {
        // Check if already open
        if (_openChats.ContainsKey(agent.Id))
        {
            // Focus existing tab
            _openChats[agent.Id].IsActive = true;
            _logger.LogInformation("Activated existing chat tab for {Agent}", agent.Name);
            return;
        }

        _logger.LogInformation("Opening new chat tab for {Agent}", agent.Name);

        // Create ViewModel
        var viewModel = ActivatorUtilities.CreateInstance<AgentChatViewModel>(
            _serviceProvider, agent);

        // Create View
        var chatView = new ChatView { DataContext = viewModel };

        // Create LayoutDocument
        var layoutDoc = new LayoutDocument
        {
            Title = $"{agent.Name} Chat",
            Content = chatView,
            CanClose = true,
            CanFloat = true,
            ContentId = $"agent-chat-{agent.Id}"
        };

        // Handle close event
        layoutDoc.Closed += (s, e) =>
        {
            _openChats.Remove(agent.Id);
            (viewModel as IDisposable)?.Dispose();
            _logger.LogInformation("Closed chat tab for {Agent}", agent.Name);
        };

        // Add to document pane
        var docPane = _dockingManager.Layout.Descendents()
            .OfType<LayoutDocumentPane>()
            .FirstOrDefault();
        
        if (docPane != null)
        {
            docPane.Children.Add(layoutDoc);
            layoutDoc.IsActive = true;
            _openChats[agent.Id] = layoutDoc;
        }
    }

    public void CloseAgentChat(string agentId)
    {
        if (_openChats.TryGetValue(agentId, out var layoutDoc))
        {
            layoutDoc.Close();
        }
    }

    public void CloseAllAgentChats()
    {
        foreach (var layoutDoc in _openChats.Values.ToList())
        {
            layoutDoc.Close();
        }
        _openChats.Clear();
    }
}
```

#### 2.3 Integration with AgentRosterView

Add "Chat" button to each agent card:
```xml
<Button Content="💬 Chat" 
        Command="{Binding DataContext.OpenAgentChatCommand, RelativeSource={RelativeSource AncestorType=UserControl}}"
        CommandParameter="{Binding}"
        Style="{StaticResource MaterialDesignFlatButton}"
        Margin="5"/>
```

AgentRosterViewModel:
```csharp
[RelayCommand]
public void OpenAgentChat(Agent agent)
{
    _chatTabManager.OpenAgentChat(agent);
}
```

### Code Optimizations

**Optimization 1: Tab Reuse**
```csharp
// Don't create duplicate tabs for same agent
if (_openChats.ContainsKey(agent.Id))
{
    _openChats[agent.Id].IsActive = true;
    return;
}
```

**Optimization 2: Lazy Chat History Loading**
```csharp
// Load only recent messages initially
private async Task LoadChatHistoryAsync()
{
    var recent = await _apiClient.GetRecentChatMessagesAsync(_agent.Id, limit: 50);
    Messages = new ObservableCollection<ChatMessage>(recent);
    
    // Infinite scroll: load older on demand
    _hasMoreHistory = recent.Count == 50;
}
```

**Optimization 3: Message Virtualization**
```xml
<ListBox ItemsSource="{Binding Messages}"
         VirtualizingPanel.IsVirtualizing="True"
         VirtualizingPanel.VirtualizationMode="Recycling"
         VirtualizingPanel.CacheLength="10,10"
         VirtualizingPanel.CacheLengthUnit="Item"
         ScrollViewer.CanContentScroll="True"/>
```

### Integration Steps

1. **Create AgentChatViewModel.cs** with per-agent state
2. **Implement AgentChatTabManager.cs** for tab lifecycle
3. **Update AgentRosterView.xaml** with "Chat" button
4. **Register AgentChatTabManager** in DI container
5. **Pass DockingManager reference** to tab manager
6. **Add close handlers** for proper cleanup
7. **Test with multiple agents** (Dexter, AUM, BSM)

### Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Memory leak from unclosed tabs** | High | Strict IDisposable, WeakEventManager for events |
| **Chat history growth** | Medium | Pagination, limit to 1000 messages per tab |
| **TTS overlap** | Low | Queue TTS requests, cancel previous on new message |
| **Tab confusion** | Low | Color-code tabs by agent type, add agent icon |

---

## 🖥️ Feature 3: Multi-Monitor Support

### Overview
Save and restore AvalonDock layouts across sessions, including docked panel positions, floating window locations, and multi-monitor configurations.

### Technical Architecture

AvalonDock provides built-in layout serialization to XML. We extend this with monitor-awareness and resolution change detection.

### Key Components

#### 3.1 Layout Manager (`Services/LayoutManager.cs`)

```csharp
using System;
using System.IO;
using System.Windows;
using System.Xml.Serialization;
using Xcad.Wpf.AvalonDock.Layout.Serialization;
using Microsoft.Extensions.Logging;

namespace DexterCockpit.Services;

public class LayoutManager
{
    private readonly string _layoutPath;
    private readonly ILogger<LayoutManager> _logger;
    
    public LayoutManager(ILogger<LayoutManager> logger)
    {
        _layoutPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "DexterCockpit",
            "layout.xml"
        );
        
        Directory.CreateDirectory(Path.GetDirectoryName(_layoutPath)!);
        _logger = logger;
    }

    public void SaveLayout(DockingManager dockingManager)
    {
        try
        {
            _logger.LogInformation("Saving layout to {Path}", _layoutPath);
            
            var layoutSerializer = new XmlLayoutSerializer(dockingManager);
            
            // Save monitor configuration
            var monitorConfig = GetMonitorConfiguration();
            
            using var stream = File.Create(_layoutPath);
            layoutSerializer.Serialize(stream);
            
            // Save monitor info separately
            SaveMonitorConfiguration(monitorConfig);
            
            _logger.LogInformation("Layout saved successfully");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to save layout");
        }
    }

    public bool RestoreLayout(DockingManager dockingManager)
    {
        if (!File.Exists(_layoutPath))
        {
            _logger.LogInformation("No saved layout found");
            return false;
        }

        try
        {
            _logger.LogInformation("Restoring layout from {Path}", _layoutPath);
            
            // Check if monitor configuration changed
            var savedConfig = LoadMonitorConfiguration();
            var currentConfig = GetMonitorConfiguration();
            
            if (!AreMonitorConfigurationsCompatible(savedConfig, currentConfig))
            {
                _logger.LogWarning("Monitor configuration changed, resetting layout");
                return false;
            }

            var layoutSerializer = new XmlLayoutSerializer(dockingManager);
            
            // Handle missing content
            layoutSerializer.LayoutSerializationCallback += (s, e) =>
            {
                _logger.LogDebug("Restoring content: {ContentId}", e.Model.ContentId);
                
                // Recreate views based on ContentId
                e.Content = ResolveContentFromId(e.Model.ContentId);
            };

            using var stream = File.OpenRead(_layoutPath);
            layoutSerializer.Deserialize(stream);
            
            _logger.LogInformation("Layout restored successfully");
            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to restore layout");
            return false;
        }
    }

    private object? ResolveContentFromId(string contentId)
    {
        // Map ContentId to View/ViewModel
        return contentId switch
        {
            "agent-roster" => new AgentRosterView(),
            "logs" => new LogsView(),
            "performance" => new PerformanceView(),
            "docked-windows" => new DockedWindowsView(),
            _ when contentId.StartsWith("agent-chat-") => 
                ResolveAgentChat(contentId.Replace("agent-chat-", "")),
            _ => null
        };
    }

    private MonitorConfiguration GetMonitorConfiguration()
    {
        return new MonitorConfiguration
        {
            Monitors = System.Windows.Forms.Screen.AllScreens.Select(s => new MonitorInfo
            {
                DeviceName = s.DeviceName,
                Bounds = new Rectangle(s.Bounds.X, s.Bounds.Y, s.Bounds.Width, s.Bounds.Height),
                IsPrimary = s.Primary
            }).ToList()
        };
    }

    private bool AreMonitorConfigurationsCompatible(MonitorConfiguration saved, MonitorConfiguration current)
    {
        // Allow restore if:
        // 1. Same number of monitors
        // 2. Primary monitor same resolution
        
        if (saved.Monitors.Count != current.Monitors.Count)
            return false;

        var savedPrimary = saved.Monitors.FirstOrDefault(m => m.IsPrimary);
        var currentPrimary = current.Monitors.FirstOrDefault(m => m.IsPrimary);

        return savedPrimary?.Bounds.Width == currentPrimary?.Bounds.Width &&
               savedPrimary?.Bounds.Height == currentPrimary?.Bounds.Height;
    }

    private void SaveMonitorConfiguration(MonitorConfiguration config)
    {
        var configPath = _layoutPath.Replace(".xml", ".monitors.json");
        var json = System.Text.Json.JsonSerializer.Serialize(config, new System.Text.Json.JsonSerializerOptions
        {
            WriteIndented = true
        });
        File.WriteAllText(configPath, json);
    }

    private MonitorConfiguration LoadMonitorConfiguration()
    {
        var configPath = _layoutPath.Replace(".xml", ".monitors.json");
        if (!File.Exists(configPath))
            return new MonitorConfiguration { Monitors = new List<MonitorInfo>() };

        var json = File.ReadAllText(configPath);
        return System.Text.Json.JsonSerializer.Deserialize<MonitorConfiguration>(json)
            ?? new MonitorConfiguration { Monitors = new List<MonitorInfo>() };
    }
}

public class MonitorConfiguration
{
    public List<MonitorInfo> Monitors { get; set; } = new();
}

public class MonitorInfo
{
    public string DeviceName { get; set; } = string.Empty;
    public Rectangle Bounds { get; set; }
    public bool IsPrimary { get; set; }
}

public struct Rectangle
{
    public int X { get; set; }
    public int Y { get; set; }
    public int Width { get; set; }
    public int Height { get; set; }

    public Rectangle(int x, int y, int width, int height)
    {
        X = x;
        Y = y;
        Width = width;
        Height = height;
    }
}
```

#### 3.2 MainWindow Integration

```csharp
// MainWindow.xaml.cs
public partial class MainWindow : Window
{
    private readonly LayoutManager _layoutManager;
    
    public MainWindow(LayoutManager layoutManager, ...)
    {
        InitializeComponent();
        _layoutManager = layoutManager;
        
        Loaded += OnWindowLoaded;
        Closing += OnWindowClosing;
    }

    private void OnWindowLoaded(object sender, RoutedEventArgs e)
    {
        // Restore layout after window is fully loaded
        _layoutManager.RestoreLayout(dockingManager);
    }

    private void OnWindowClosing(object sender, CancelEventArgs e)
    {
        // Save layout before closing
        _layoutManager.SaveLayout(dockingManager);
    }
}
```

#### 3.3 Monitor Manager (`Services/MonitorManager.cs`)

```csharp
public class MonitorManager
{
    private readonly ILogger<MonitorManager> _logger;

    public ObservableCollection<MonitorInfo> AvailableMonitors { get; } = new();

    public MonitorManager(ILogger<MonitorManager> logger)
    {
        _logger = logger;
        RefreshMonitors();
        
        // Watch for monitor changes
        SystemEvents.DisplaySettingsChanged += (s, e) =>
        {
            _logger.LogInformation("Display settings changed, refreshing monitors");
            RefreshMonitors();
        };
    }

    public void RefreshMonitors()
    {
        AvailableMonitors.Clear();
        
        foreach (var screen in System.Windows.Forms.Screen.AllScreens)
        {
            AvailableMonitors.Add(new MonitorInfo
            {
                DeviceName = screen.DeviceName,
                Bounds = new Rectangle(screen.Bounds.X, screen.Bounds.Y, 
                                       screen.Bounds.Width, screen.Bounds.Height),
                IsPrimary = screen.Primary
            });
            
            _logger.LogInformation("Monitor: {Name}, {Width}x{Height}, Primary: {IsPrimary}",
                screen.DeviceName, screen.Bounds.Width, screen.Bounds.Height, screen.Primary);
        }
    }

    public void MoveWindowToMonitor(Window window, int monitorIndex)
    {
        if (monitorIndex < 0 || monitorIndex >= AvailableMonitors.Count)
            return;

        var monitor = AvailableMonitors[monitorIndex];
        
        // Move window to monitor's top-left corner
        window.Left = monitor.Bounds.X;
        window.Top = monitor.Bounds.Y;
        
        // Optionally maximize on that monitor
        window.WindowState = WindowState.Maximized;
        
        _logger.LogInformation("Moved window to monitor {Index}", monitorIndex);
    }
}
```

### Code Optimizations

**Optimization 1: Incremental Layout Saves**
```csharp
// Don't save on every change, debounce to every 30 seconds
private DateTime _lastSave = DateTime.MinValue;

public void SaveLayoutDebounced(DockingManager manager)
{
    if ((DateTime.Now - _lastSave).TotalSeconds < 30)
        return;
        
    SaveLayout(manager);
    _lastSave = DateTime.Now;
}
```

**Optimization 2: Async Layout Serialization**
```csharp
public async Task SaveLayoutAsync(DockingManager dockingManager)
{
    await Task.Run(() => SaveLayout(dockingManager));
}
```

**Optimization 3: Fallback to Default Layout**
```csharp
public bool RestoreLayoutOrDefault(DockingManager dockingManager)
{
    if (RestoreLayout(dockingManager))
        return true;
    
    _logger.LogInformation("Falling back to default layout");
    LoadDefaultLayout(dockingManager);
    return false;
}

private void LoadDefaultLayout(DockingManager dockingManager)
{
    // Reset to hardcoded default layout
    // Or load from embedded resource
}
```

### Integration Steps

1. **Create LayoutManager.cs** with save/restore logic
2. **Add MonitorManager.cs** for display management
3. **Register in DI container**:
   ```csharp
   services.AddSingleton<LayoutManager>();
   services.AddSingleton<MonitorManager>();
   ```
4. **Wire up MainWindow events** (Loaded, Closing)
5. **Add "Reset Layout" menu item** for user control
6. **Set ContentId on all LayoutAnchorable/LayoutDocument**:
   ```xml
   <xcad:LayoutAnchorable ContentId="agent-roster" Title="Agent Roster" .../>
   ```
7. **Test multi-monitor scenarios**:
   - Single monitor → Dual monitor
   - Resolution change
   - Docked → Undocked
   - Float windows to second monitor

### Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Layout corruption** | Medium | Backup previous layout, fallback to default |
| **Monitor config changed** | Low | Detect resolution change, reset if incompatible |
| **Missing content** | Medium | Handle LayoutSerializationCallback, graceful skip |
| **Performance on large layouts** | Low | Async serialization, debounce saves |

---

## 📅 Implementation Timeline

### Phase 1: Docked Windows (2 weeks)
- **Week 1:**
  - Days 1-2: WindowsInterop.cs + unit tests
  - Days 3-5: DockedWindowHost.cs + validation
  - Days 6-7: DockedWindowsViewModel + scanning logic
- **Week 2:**
  - Days 1-3: DockedWindowsView.xaml + UI polish
  - Days 4-5: Integration testing (Unity, QuickBooks)
  - Days 6-7: Bug fixes, documentation

### Phase 2: Agent Chat Tabs (1.5 weeks)
- **Week 3:**
  - Days 1-2: AgentChatViewModel implementation
  - Days 3-4: AgentChatTabManager + dynamic tabs
  - Days 5-6: Integration with AgentRosterView
  - Day 7: Testing with 5+ simultaneous chats

### Phase 3: Multi-Monitor Support (1.5 weeks)
- **Week 4:**
  - Days 1-2: LayoutManager.cs + XML serialization
  - Days 3-4: MonitorManager.cs + display detection
  - Days 5-6: MainWindow integration + testing
  - Day 7: Multi-monitor edge case testing

### Phase 4: Polish & Documentation (1 week)
- **Week 5:**
  - Days 1-2: UI polish, icons, tooltips
  - Days 3-4: Performance optimization
  - Days 5-6: Comprehensive testing
  - Day 7: Documentation updates

**Total: 6 weeks (with buffer)**

---

## 🎯 Code Statistics Estimate

| Component | Files | Lines | Complexity |
|-----------|-------|-------|------------|
| **Docked Windows** | 5 | ~1,500 | High (Win32 interop) |
| **Agent Chat Tabs** | 3 | ~1,200 | Medium |
| **Multi-Monitor** | 3 | ~800 | Medium |
| **Integration/Tests** | 4 | ~600 | Low-Medium |
| **TOTAL** | **15** | **~4,100** | **Medium-High** |

---

## ⚠️ Integration Risks & Mitigation

### High Priority Risks

1. **Window Handle Lifecycle Management**
   - **Risk:** Handles become invalid when target app closes
   - **Mitigation:** Periodic `IsWindow()` checks, auto-undock on failure, finalizers

2. **AvalonDock Layout Corruption**
   - **Risk:** Invalid XML breaks layout restore
   - **Mitigation:** Backup previous layout, validate before save, fallback to default

3. **Memory Leaks from Event Handlers**
   - **Risk:** WeakReference issues with AvalonDock events
   - **Mitigation:** Use WeakEventManager, strict IDisposable pattern

### Medium Priority Risks

4. **DPI Scaling Conflicts**
   - **Risk:** Child window DPI doesn't match parent
   - **Mitigation:** Call `SetProcessDpiAwareness()`, test on high-DPI monitors

5. **Performance Degradation with 10+ Docked Windows**
   - **Risk:** Too many HWND redraws slow UI
   - **Mitigation:** Limit to 5 simultaneous docked windows, throttle resize events

6. **Multi-Monitor Resolution Changes**
   - **Risk:** Layout invalid after display config change
   - **Mitigation:** Detect resolution mismatch, reset to default gracefully

### Low Priority Risks

7. **Tab Confusion with Many Agents**
   - **Risk:** User loses track of which tab is which
   - **Mitigation:** Color-code tabs, show agent icon, allow tab renaming

8. **TTS Audio Overlap**
   - **Risk:** Multiple agent chats speaking simultaneously
   - **Mitigation:** Global TTS queue, cancel previous on new message

---

## 🚀 Recommended Approach

### Priority Order
1. **Multi-Monitor Support** (least risky, high value) - 1.5 weeks
2. **Agent Chat Tabs** (medium risk, high value) - 1.5 weeks
3. **Docked Windows** (highest risk, high value) - 2 weeks

### Why This Order?
- Multi-monitor is foundational for other features
- Agent tabs are isolated, won't break existing functionality
- Docked windows need the most testing and refinement

### Resource Allocation
- **1 Senior Dev** (all phases) - architecture, Win32 interop, code review
- **1 Mid-Level Dev** (phases 2-3) - ViewModels, XAML, integration
- **1 QA Engineer** (phase 4) - multi-monitor testing, edge cases

### Testing Strategy
- **Unit Tests:** Win32 interop, ViewModel logic (80% coverage)
- **Integration Tests:** Full stack with mock backend (key scenarios)
- **Manual Tests:** Multi-monitor, external apps, layout persistence
- **Performance Tests:** 10+ docked windows, 20+ agent tabs, 24hr soak test

---

## 📚 References & Documentation

### External APIs
- **Win32 API:** [MSDN - SetParent](https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setparent)
- **AvalonDock:** [GitHub - Dirkster.AvalonDock](https://github.com/Dirkster99/AvalonDock)
- **WPF HwndHost:** [MSDN - HwndHost Class](https://docs.microsoft.com/en-us/dotnet/api/system.windows.interop.hwndhost)

### Internal Docs
- `.github/copilot-instructions.md` - Architecture guidelines
- `BUILD-STATUS.md` - Current build status
- `COCKPIT-INTEGRATION.md` - Cockpit integration summary
- `cockpit/ARCHITECTURE.md` - Detailed architecture diagram

### Code Samples
- **AvalonDock Samples:** [GitHub - AvalonDock Samples](https://github.com/Dirkster99/AvalonDockTests)
- **HwndHost Examples:** [CodeProject - Hosting Win32 in WPF](https://www.codeproject.com/Articles/35346/Hosting-Windows-in-WPF)

---

## ✅ Acceptance Criteria

### Feature 1: Docked Windows
- [ ] Can scan for and detect Unity, QuickBooks, Browser windows
- [ ] Can dock/undock windows seamlessly
- [ ] Docked window resizes correctly with parent pane
- [ ] Handle invalidation auto-undocks window gracefully
- [ ] No memory leaks after 100 dock/undock cycles

### Feature 2: Agent Chat Tabs
- [ ] Can open per-agent chat tabs dynamically
- [ ] Each tab maintains isolated conversation history
- [ ] TTS works per-tab with individual mute controls
- [ ] Tabs can be closed without affecting others
- [ ] Chat history persists across sessions

### Feature 3: Multi-Monitor Support
- [ ] Layout saves/restores correctly on single monitor
- [ ] Layout works on multi-monitor setups (2-4 monitors)
- [ ] Gracefully handles monitor config changes
- [ ] Floating windows restore to correct monitor
- [ ] "Reset Layout" restores to default cleanly

---

## 🎓 Conclusion & Recommendations

### Feasibility: ✅ **HIGH** (with caution on Win32 interop)

All three features are technically feasible with .NET 8.0 WPF and AvalonDock 4.72.1. The main challenges are:
1. Win32 HWND management (mitigated with strict handle validation)
2. AvalonDock layout complexity (mitigated with thorough testing)
3. Multi-monitor edge cases (mitigated with resolution detection)

### Timeline: **4-6 weeks** (realistic with 1-2 developers)

- Best case: 4 weeks (experienced team, no blockers)
- Realistic: 5 weeks (some Win32 debugging, testing)
- Worst case: 6 weeks (multi-monitor edge cases, performance tuning)

### Risk Level: **MEDIUM**

- Docked Windows: HIGH (Win32 API complexity)
- Agent Chat Tabs: LOW (standard MVVM pattern)
- Multi-Monitor: MEDIUM (display config edge cases)

### Recommendation: **APPROVE WITH PHASED ROLLOUT**

1. **Phase 1:** Multi-Monitor Support (de-risk first)
2. **Phase 2:** Agent Chat Tabs (parallel development possible)
3. **Phase 3:** Docked Windows (requires most iteration)
4. **Phase 4:** Polish, performance, documentation

### Alternative Approaches Considered

#### Alternative 1: Electron-based UI
- **Pros:** Cross-platform, web tech familiarity
- **Cons:** Higher memory footprint, no native HWND support
- **Verdict:** ❌ Not suitable for Windows-first platform

#### Alternative 2: UWP/WinUI 3
- **Pros:** Modern Windows API, better XAML islands
- **Cons:** Complex migration, limited docking libraries
- **Verdict:** ⚠️ Consider for future rewrite, not now

#### Alternative 3: Keep Single Chat, Add Agent Selector
- **Pros:** Simpler implementation, less memory
- **Cons:** Poor UX for multi-agent workflows
- **Verdict:** ❌ Doesn't meet roadmap vision

---

**Status:** Ready for Review  
**Next Steps:** Review with lead developer, approval to proceed with Phase 1

---

**Document Version:** 1.0  
**Last Updated:** October 16, 2025  
**Prepared By:** Copilot AI Agent (Advanced GitHub Agent)

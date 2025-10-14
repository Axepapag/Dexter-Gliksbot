# Dexter Cockpit Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         DEXTER MISSION CONTROL COCKPIT                        │
│                           (WPF .NET 8.0 Application)                          │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │         App.xaml.cs           │
                    │   (Dependency Injection)      │
                    │  - Services Registration      │
                    │  - Logger Configuration       │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │       MainWindow.xaml         │
                    │   (AvalonDock DockingManager) │
                    │  - Top Bar (Status)           │
                    │  - Docking Layout             │
                    │  - Status Bar                 │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │       MainViewModel           │
                    │    (Main Orchestrator)        │
                    │  - Connection Management      │
                    │  - Child VM Coordination      │
                    └───────────────┬───────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
┌───────▼────────┐      ┌───────────▼──────────┐     ┌────────▼─────────┐
│ AgentRosterVM  │      │     ChatViewModel    │     │   LogsViewModel  │
│ - Agent List   │      │  - Broadcast Mode    │     │ - 10GB Budget    │
│ - Status       │      │  - TTS (System.      │     │ - Ring Buffer    │
│ - Quick Actions│      │    Speech.Synthesis) │     │ - Filters        │
│                │      │  - Microphone Input  │     │ - Eviction       │
└───────┬────────┘      │  - Agent Selection   │     └────────┬─────────┘
        │               └───────────┬──────────┘              │
        │                           │                         │
┌───────▼────────┐      ┌───────────▼──────────┐     ┌────────▼─────────┐
│AgentRosterView │      │      ChatView        │     │    LogsView      │
│   (XAML)       │      │      (XAML)          │     │    (XAML)        │
│ - ListBox      │      │  - ScrollViewer      │     │ - Virtualized    │
│ - Buttons      │      │  - TextBox           │     │   ListBox        │
│ - Metrics      │      │  - Toggle Buttons    │     │ - Filters UI     │
└───────┬────────┘      └───────────┬──────────┘     └────────┬─────────┘
        │                           │                         │
        └───────────────────────────┼─────────────────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │    Services Layer             │
                    │  ┌─────────────────────────┐  │
                    │  │ DexterWebSocketClient   │  │
                    │  │  - 5 Real-Time Channels │  │
                    │  │  - Event Publishers     │  │
                    │  └─────────────┬───────────┘  │
                    │                │               │
                    │  ┌─────────────▼───────────┐  │
                    │  │   DexterApiClient       │  │
                    │  │  - REST API Wrapper     │  │
                    │  │  - Async HTTP Calls     │  │
                    │  └─────────────┬───────────┘  │
                    └────────────────┼───────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │     Dexter Backend              │
                    │   (Python FastAPI + uvicorn)    │
                    │                                 │
                    │  REST API:                      │
                    │  - GET  /healthz                │
                    │  - GET  /agents                 │
                    │  - POST /agents/{id}/pause      │
                    │  - POST /agents/{id}/resume     │
                    │  - POST /agents/{id}/stop       │
                    │  - GET  /logs/export            │
                    │                                 │
                    │  WebSocket:                     │
                    │  - WS /ws/logs                  │
                    │  - WS /ws/agents                │
                    │  - WS /ws/missions              │
                    │  - WS /ws/performance           │
                    │  - WS /ws/config                │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   Event Bus & Agents            │
                    │  - Dexter Orchestrator          │
                    │  - AUM (Action Understanding)   │
                    │  - BSM (Brain/State)            │
                    │  - ActionExecutor               │
                    │  - ChatDockAgent                │
                    └─────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════
                              DATA FLOW EXAMPLES
═══════════════════════════════════════════════════════════════════════════════

1. USER SENDS CHAT MESSAGE
   ┌──────┐   Input Text    ┌─────────┐   HTTP POST      ┌──────────┐
   │ User │ ───────────────►│ ChatVM  │ ────────────────►│ Backend  │
   └──────┘                 └────┬────┘                  └────┬─────┘
                                 │                             │
                          TTS    │                      ┌──────▼──────┐
                        ┌────────▼────┐                 │   Dexter    │
                        │ Speak Reply │                 │ Orchestrator│
                        └─────────────┘                 └──────┬──────┘
                                                               │
                                                        Broadcast to
                                                        All Agents


2. AGENT STATUS UPDATE (Real-Time)
   ┌──────────┐   Status Change   ┌────────┐   WS Message   ┌────────────┐
   │  Agent   │ ─────────────────►│Backend │ ──────────────►│ WSClient   │
   │ (Python) │                   │ WS     │                └─────┬──────┘
   └──────────┘                   └────────┘                      │
                                                              Event│Handler
                                                            ┌──────▼──────┐
                                                            │ AgentRoster │
                                                            │  ViewModel  │
                                                            └──────┬──────┘
                                                                   │
                                                            Update │UI
                                                            ┌──────▼──────┐
                                                            │ AgentRoster │
                                                            │    View     │
                                                            └─────────────┘


3. LOG STREAM (Real-Time with 10GB Budget)
   ┌──────────┐   Publish Log    ┌────────┐   WS Stream    ┌────────────┐
   │  Agent   │ ─────────────────►│Backend │ ──────────────►│ WSClient   │
   │  Action  │                   │EventBus│                └─────┬──────┘
   └──────────┘                   └────────┘                      │
                                                            OnLog  │Received
                                                            ┌──────▼──────┐
                                                            │   LogsVM    │
                                                            │ - Add Entry │
                                                            │ - Check RAM │
                                                            │ - Evict?    │
                                                            └──────┬──────┘
                                                                   │
                                                            Update │UI
                                                            ┌──────▼──────┐
                                                            │  LogsView   │
                                                            │ (Virtualized│
                                                            │  ListBox)   │
                                                            └─────────────┘


4. PAUSE AGENT (User Action)
   ┌──────┐   Click Button   ┌─────────────┐   HTTP POST   ┌──────────┐
   │ User │ ────────────────►│ AgentRoster │ ─────────────►│ Backend  │
   └──────┘                  │  ViewModel  │               │ API      │
                             └─────────────┘               └────┬─────┘
                                                                 │
                                                        Execute  │Command
                                                          ┌──────▼──────┐
                                                          │ Dexter      │
                                                          │ Validates   │
                                                          │ Policy      │
                                                          └──────┬──────┘
                                                                 │
                                                          Pause  │Agent
                                                          ┌──────▼──────┐
                                                          │   Target    │
                                                          │   Agent     │
                                                          └─────────────┘


═══════════════════════════════════════════════════════════════════════════════
                           TECHNOLOGY STACK LAYERS
═══════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────┐
│                              PRESENTATION LAYER                              │
│  - WPF (Windows Presentation Foundation)                                    │
│  - AvalonDock 4.72 (Docking System)                                         │
│  - MaterialDesignThemes 4.9 (UI Components)                                 │
│  - LiveCharts.Wpf 0.9.7 (Real-Time Charts)                                  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                            VIEW MODEL LAYER                                  │
│  - CommunityToolkit.Mvvm 8.2.2 (MVVM Helpers)                               │
│  - Observable Properties (INotifyPropertyChanged)                            │
│  - Relay Commands (ICommand Implementation)                                  │
│  - Event Aggregation                                                         │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                             SERVICE LAYER                                    │
│  - WebSocketSharp-netstandard 1.0.1 (Real-Time Comms)                       │
│  - System.Net.Http (REST API Client)                                        │
│  - System.Speech 8.0 (TTS & Speech Recognition)                             │
│  - Newtonsoft.Json 13.0.3 (JSON Serialization)                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                           INFRASTRUCTURE LAYER                               │
│  - Microsoft.Extensions.DependencyInjection 8.0 (IoC Container)             │
│  - Microsoft.Extensions.Logging 8.0 (Logging Abstraction)                   │
│  - .NET 8.0 Runtime                                                          │
└─────────────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════
                              MEMORY MANAGEMENT
═══════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────┐
│                          LOGS PANE (10GB RAM BUDGET)                         │
│                                                                              │
│  ObservableCollection<LogEntry>                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ [Entry 1] [Entry 2] [Entry 3] ... [Entry 5,000,000]                  │  │
│  │  ~2KB      ~2KB      ~2KB                                             │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Eviction Strategy (LLM-Managed):                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 1. Monitor: _currentMemoryUsageBytes                                  │  │
│  │ 2. Threshold: MAX_MEMORY_BYTES (10GB)                                 │  │
│  │ 3. When Approaching 10GB:                                             │  │
│  │    ┌────────────────────────────────────┐                             │  │
│  │    │ - Remove oldest TRACE logs (1000)  │                             │  │
│  │    │ - Remove oldest INFO logs (1000)   │                             │  │
│  │    │ - Remove oldest WARN logs (500)    │                             │  │
│  │    │ - ERROR/CRITICAL: Never auto-evict │                             │  │
│  │    └────────────────────────────────────┘                             │  │
│  │ 4. Archive to LTM (Brain SQLite)                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  UI Virtualization:                                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ VirtualizingPanel.IsVirtualizing="True"                               │  │
│  │ VirtualizingPanel.VirtualizationMode="Recycling"                      │  │
│  │                                                                        │  │
│  │ → Only visible rows rendered (viewport = ~30 rows)                    │  │
│  │ → Rows recycled on scroll (constant memory footprint)                 │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

**Legend**:
- `┌─┐` = Component boundary
- `│  │` = Container
- `───►` = Synchronous call
- `═══►` = Asynchronous/event-driven
- `▼` = Data/control flow downward
- `┬` = Split/branch

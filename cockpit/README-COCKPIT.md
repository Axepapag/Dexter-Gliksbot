# Dexter Mission Control Cockpit

**Production-grade WPF UI for 24/7 autonomous agent operations**

## 🎯 Overview

The Dexter Cockpit is a comprehensive mission control interface for managing, monitoring, and interacting with autonomous agents. Built with WPF, AvalonDock, and Material Design, it provides real-time visibility into agent operations, system performance, and shared brain state.

## ✨ Features

### **Core Capabilities**
- ✅ **Real-Time Agent Monitoring** - Live status, metrics, and resource usage
- ✅ **Multi-Agent Chat** - Broadcast mode + direct agent communication
- ✅ **Text-to-Speech (TTS)** - Per-agent voice output with mute controls
- ✅ **Microphone Input** - Push-to-talk for voice commands
- ✅ **Live Logs Stream** - 10GB RAM budget with intelligent eviction
- ✅ **Performance Dashboard** - CPU, memory, Redis queue, brain size
- ✅ **Fully Dockable UI** - All views detachable and resizable (AvalonDock)
- ✅ **Dark Theme** - Optimized for 24/7 operations

### **Agent Management**
- View all active agents with color-coded status indicators (🟢🟡🔴⚪)
- Quick actions: Pause, Resume, Stop, View Logs
- Per-agent metrics: Uptime, success rate, CPU/memory, current mission
- Dynamic agent tabs (Config, Tasks, Logs) - easy add/close

### **Chat System**
- **Broadcast Mode**: All agents listen, Dexter replies
- **Direct Mode**: Select specific agent from dropdown
- Real-time message streaming with timestamp
- Integrated TTS with per-agent mute buttons
- Microphone support for voice input

### **Logs Panel (Bottom Pane)**
- **10GB RAM budget** with LLM-managed eviction
- Multi-filter: Level (TRACE/INFO/WARN/ERROR/CRITICAL), Agent, Topic, Text search
- Virtualized list (5M entries supported)
- Export: JSONL, CSV
- Color-coded severity (ERROR = red, WARN = yellow)
- Pause/resume stream without data loss
- Memory usage indicator with progress bar

### **Performance Monitoring**
- Real-time metrics: CPU, Memory, Redis queue depth, Brain size
- Messages/sec and average latency
- Live charts (60-second rolling window)
- CPU and Memory usage graphs (LiveCharts)

## 🏗️ Architecture

### **Technology Stack**
- **.NET 8.0** - Latest framework
- **WPF** - Windows Presentation Foundation
- **AvalonDock 4.72** - Docking window system
- **MaterialDesignThemes 4.9** - Modern UI components
- **LiveCharts.Wpf 0.9.7** - Real-time charts
- **CommunityToolkit.Mvvm 8.2.2** - MVVM helpers
- **System.Speech 8.0** - TTS and speech recognition
- **WebSocketSharp** - Real-time backend communication

### **MVVM Pattern**
```
ViewModels/
  ├── MainViewModel.cs          # Main orchestrator
  ├── AgentRosterViewModel.cs   # Agent list and controls
  ├── ChatViewModel.cs          # Chat with TTS/mic
  ├── LogsViewModel.cs          # Log stream with 10GB budget
  └── PerformanceViewModel.cs   # Metrics and charts

Views/
  ├── AgentRosterView.xaml      # Left sidebar (detachable)
  ├── ChatView.xaml             # Main chat (center)
  ├── LogsView.xaml             # Bottom pane (detachable)
  └── PerformanceView.xaml      # Performance tab

Models/
  ├── Agent.cs                  # Agent model with status
  ├── Mission.cs                # Mission tracking
  └── LogEntry.cs               # Log entry with colors

Services/
  ├── DexterApiClient.cs        # REST API client
  └── DexterWebSocketClient.cs  # Real-time WebSocket (5 channels)
```

### **WebSocket Channels**
```
WS /ws/logs          # Real-time log stream
WS /ws/agents        # Agent status updates (1sec heartbeat)
WS /ws/missions      # Mission progress
WS /ws/performance   # System metrics (1sec interval)
WS /ws/config        # Config change notifications
```

## 🚀 Getting Started

### **Prerequisites**
- Windows 10/11 or Windows Server 2022
- .NET 8.0 SDK
- Visual Studio 2022 (or Rider, VS Code with C# extension)
- Dexter backend running at `http://localhost:8765`

### **Build**
```powershell
cd cockpit/DexterCockpit
dotnet restore
dotnet build
```

### **Run**
```powershell
dotnet run
```

Or open `DexterCockpit.sln` in Visual Studio and press F5.

### **Backend Setup**
Ensure Dexter backend is running:
```bash
cd ../../
python start.py --port 8765
```

## 🎨 UI Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ 🤖 DEXTER MISSION CONTROL              [🟢 Connected]           │
├────────┬────────────────────────────────────────────┬───────────┤
│        │  📋 Dexter Chat                 │ Perf Monitor│         │
│ Agent  │  ┌──────────────────────────────┐          │  Docked  │
│ Roster │  │ [Broadcast Mode: ON] 🔊 🎤   │          │  Windows │
│        │  ├──────────────────────────────┤          │          │
│ Dexter │  │  User: Hello Dexter          │          │  (Unity) │
│ 🟢 95% │  │  Dexter: Ready to assist...  │          │          │
│        │  │                               │          │  (QB)    │
│ AUM    │  └──────────────────────────────┘          │          │
│ 🟢 87% │  Agent: [Dexter v]  [Send]               │          │
│        │                                            │          │
│ BSM    │                                            │          │
│ 🟡 72% │                                            │          │
├────────┴────────────────────────────────────────────┴───────────┤
│ 📊 Real-Time Logs (10GB RAM: 2.3GB / 10GB ████░░░░ 23%)         │
│ [✓TRACE][✓INFO][✓WARN][✓ERROR] Agent:[___] Text:[_______]      │
│ 12:34:56.789 INFO  dexter    INTENT  User message received...   │
│ 12:34:56.823 TRACE action_ex EFFECT  Typed 5 chars in 123ms     │
└──────────────────────────────────────────────────────────────────┘
```

## 🔧 Configuration

### **Backend URL**
Edit `App.xaml.cs`:
```csharp
services.AddSingleton<DexterApiClient>(sp =>
    new DexterApiClient("http://your-backend:8765", ...));
```

### **TTS Voice**
Edit `ChatViewModel.cs`:
```csharp
_tts.SelectVoice("Microsoft David Desktop");  // Change voice
_tts.Rate = 0;   // Speed: -10 (slow) to 10 (fast)
_tts.Volume = 80; // Volume: 0-100
```

### **Log Memory Budget**
Edit `LogsViewModel.cs`:
```csharp
private const long MAX_MEMORY_BYTES = 10L * 1024 * 1024 * 1024; // 10GB
```

## 🎤 Voice Features

### **Text-to-Speech (TTS)**
- Automatic voice output for agent responses
- Per-agent mute button (🔊/🔇)
- Uses `System.Speech.Synthesis`
- Configurable voice, speed, volume

### **Microphone Input**
- Push-to-talk button in chat toolbar (🎤)
- Toggle on/off for continuous listening
- Speech recognition (placeholder - needs `System.Speech.Recognition`)

**To implement full speech recognition**:
1. Install `System.Speech` (already included)
2. Add `SpeechRecognitionEngine` in `ChatViewModel.cs`
3. Configure grammar for command recognition
4. Convert speech to text → send to backend

## 🎯 Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Send message |
| `Ctrl+B` | Toggle broadcast mode |
| `Ctrl+M` | Toggle microphone |
| `Ctrl+L` | Clear logs |
| `F5` | Refresh agent list |

## 🔌 Extending

### **Adding a New Agent Tab**
Agents can have dynamic tabs (Config, Tasks, Logs). To add per-agent windows:

```csharp
// In MainWindow.xaml.cs or MainViewModel
var agentTab = new LayoutDocument
{
    Title = $"{agent.Name} - Config",
    Content = new AgentConfigView { DataContext = agentViewModel }
};
dockingManager.Layout.Descendents().OfType<LayoutDocumentPane>().First().Children.Add(agentTab);
```

### **Adding a New View**
1. Create `Views/YourView.xaml` + `.xaml.cs`
2. Create `ViewModels/YourViewModel.cs`
3. Add to `MainWindow.xaml` as `LayoutAnchorable` or `LayoutDocument`
4. Register ViewModel in `App.xaml.cs` DI container

## 🧪 Testing

### **Manual Testing**
1. Start backend: `python start.py`
2. Run cockpit: `dotnet run`
3. Verify connection (🟢 indicator in top bar)
4. Test broadcast chat → Dexter should reply
5. Pause/resume agents → status should update
6. Generate logs → check bottom pane filters

### **Unit Tests** (TODO)
```powershell
cd DexterCockpit.Tests
dotnet test
```

## 📊 Performance

### **Memory Management**
- **Logs**: 10GB RAM budget, intelligent eviction (TRACE/INFO first)
- **UI Virtualization**: ListBox with `VirtualizingPanel` for 5M+ log entries
- **Agent List**: Lazy loading, only visible agents rendered

### **Real-Time Updates**
- WebSocket events trigger on UI thread (`Dispatcher.Invoke`)
- Performance metrics update every 1 second
- Chart data limited to 60 data points (1-minute window)

## 🐛 Troubleshooting

### **WebSocket Connection Failed**
- Verify backend is running: `curl http://localhost:8765/healthz`
- Check firewall rules for port 8765
- Ensure backend has WebSocket endpoints implemented

### **TTS Not Working**
- Install Windows Speech Platform (comes with Windows 10/11)
- Verify voice installed: `Control Panel → Speech → Text-to-Speech`
- Check `_tts.GetInstalledVoices()` in code

### **Microphone Not Detected**
- Check Windows microphone permissions (Privacy Settings)
- Ensure audio input device is enabled
- Test with Windows Voice Recorder first

### **High Memory Usage**
- Logs pane has 10GB budget (by design)
- Adjust `MAX_MEMORY_BYTES` in `LogsViewModel.cs`
- Check for memory leaks: Use Visual Studio Diagnostic Tools

## 🔮 Roadmap

### **Phase 2 (In Progress)**
- [ ] Per-agent chat windows (detachable)
- [ ] Mission designer (YAML editor with syntax highlighting)
- [ ] OCR vision panel (5 FPS, adjustable)
- [ ] Docked windows (Unity, QuickBooks, CAD)

### **Phase 3 (Planned)**
- [ ] Multi-monitor support with saved layouts
- [ ] Alert system (toast notifications, sound alerts)
- [ ] Policy editor UI
- [ ] Visual mission flowchart designer

### **Phase 4 (Future)**
- [ ] Chatbot docking (Anthropic, ChatGPT, Llama)
- [ ] Heatmap visualization for OCR confidence
- [ ] Correlation ID tracing (click log → see related events)
- [ ] Export missions as reusable recipes

## 📝 License

See root `LICENSE` file.

## 🤝 Contributing

This is a private project. For AI agents working on this codebase:
- Read `.github/copilot-instructions.md` first
- Follow MVVM pattern strictly
- All views must be detachable (AvalonDock `CanFloat="True"`)
- Use Material Design components
- Add logging to all ViewModels

---

**Built with ❤️ for 24/7 autonomous operations**

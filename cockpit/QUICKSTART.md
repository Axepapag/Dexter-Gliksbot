# 🚀 Dexter Cockpit - Quick Start Guide

## Prerequisites
- ✅ Windows 10/11 or Windows Server 2022
- ✅ .NET 8.0 SDK ([Download](https://dotnet.microsoft.com/download/dotnet/8.0))
- ✅ Visual Studio 2022 (optional, but recommended)

## Installation

### 1. Install .NET 8.0 SDK
```powershell
# Using winget
winget install Microsoft.DotNet.SDK.8

# Verify
dotnet --version  # Should show 8.0.x
```

### 2. Restore NuGet Packages
```powershell
cd cockpit/DexterCockpit
dotnet restore
```

## Running the Cockpit

### Option 1: Command Line
```powershell
cd cockpit/DexterCockpit
dotnet run
```

### Option 2: Visual Studio
1. Open `DexterCockpit.sln`
2. Press **F5** to run
3. Or right-click project → **Debug** → **Start New Instance**

### Option 3: Build and Run Executable
```powershell
# Build release
dotnet build -c Release

# Run
.\bin\Release\net8.0-windows\DexterCockpit.exe
```

## First Launch

When you launch the cockpit, you'll see:

1. **Connection Status** (top bar): Red 🔴 = Disconnected
2. **Agent Roster** (left sidebar): Empty until backend connects
3. **Chat Window** (center): Ready for input
4. **Logs Panel** (bottom): Shows "Ready"

### Connecting to Backend

The cockpit expects Dexter backend at `http://localhost:8765`.

**Start backend first:**
```bash
cd ../..  # Go to repo root
python start.py --port 8765
```

Once backend is running:
- Connection indicator turns green 🟢
- Agents populate in roster
- Logs start streaming
- Performance metrics update

## Configuration

### Change Backend URL
Edit `App.xaml.cs`:
```csharp
services.AddSingleton<DexterApiClient>(sp =>
    new DexterApiClient("http://your-server:8080", ...));
```

### Change TTS Voice
Edit `ChatViewModel.cs`:
```csharp
_tts.SelectVoice("Microsoft Zira Desktop");  // Female voice
_tts.Rate = 2;   // Faster speech
_tts.Volume = 100; // Max volume
```

### Adjust Log Memory Budget
Edit `LogsViewModel.cs`:
```csharp
private const long MAX_MEMORY_BYTES = 5L * 1024 * 1024 * 1024; // 5GB instead of 10GB
```

## Basic Usage

### Chat with Dexter
1. Type message in input box (bottom of chat)
2. Press **Enter** or click **Send**
3. Toggle **Broadcast Mode** to talk to all agents (Dexter replies)
4. Turn off broadcast to select specific agent from dropdown

### Control Agents
1. Select agent in roster (left sidebar)
2. Click **Pause** / **Resume** / **Stop**
3. Status updates in real-time

### Filter Logs
1. Check/uncheck log levels (TRACE, INFO, WARN, ERROR, CRITICAL)
2. Type agent name in "Filter by Agent" box
3. Type search text in "Search text..." box
4. Click **Pause** button to freeze stream

### Export Logs
1. Apply filters
2. Click **Export** button (download icon)
3. Logs saved to default downloads folder

### Detach Views
- Drag any pane title bar to detach
- Float over other windows or move to second monitor
- Drag back to dock

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send chat message |
| `Ctrl+B` | Toggle broadcast mode |
| `Ctrl+M` | Toggle microphone |
| `Ctrl+L` | Clear logs |
| `F5` | Refresh agents |

## Troubleshooting

### "Connection Failed" Error
- ✅ Start backend: `python start.py --port 8765`
- ✅ Check port 8765 is not blocked by firewall
- ✅ Verify backend health: `curl http://localhost:8765/healthz`

### No TTS Audio
- ✅ Check Windows volume (not muted)
- ✅ Verify TTS voice installed: Control Panel → Speech → Text-to-Speech
- ✅ Test with Windows Narrator first

### Microphone Not Working
- ✅ Grant microphone permissions: Settings → Privacy → Microphone
- ✅ Check default audio input device is enabled
- ✅ Test with Windows Voice Recorder

### High CPU Usage
- ✅ Pause log stream (performance impact)
- ✅ Reduce chart update frequency
- ✅ Close unused detached windows

### Application Crash
- ✅ Check Event Viewer: Windows Logs → Application
- ✅ Look for .NET runtime errors
- ✅ Delete `bin/` and `obj/`, rebuild: `dotnet clean && dotnet build`

## Need Help?

- 📖 Read full docs: `README-COCKPIT.md`
- 🐛 Check build summary: `BUILD-COMPLETE.md`
- 🤖 Review AI instructions: `.github/copilot-instructions.md`

---

**Enjoy your mission control experience! 🚀**

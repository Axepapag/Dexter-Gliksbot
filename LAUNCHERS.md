# 🚀 Dexter Launchers

Quick-start launchers for Dexter-Gliksbot system.

## 📋 Prerequisites

Before using the launchers, run the installer:
```bash
python install.py
```

This will check and install:
- ✅ Python 3.10+ dependencies
- ✅ Database initialization
- ✅ .NET 8.0 SDK (for Cockpit UI)
- ✅ Optional: Redis, Ollama, Tesseract OCR

---

## 🎯 Available Launchers

### 1. **Launch-Dexter.bat** / **Launch-Dexter.ps1** (Full Stack)
Starts both backend server AND Cockpit UI in separate windows.

**Windows (Batch)**:
```batch
# Double-click Launch-Dexter.bat
# Or from command line:
Launch-Dexter.bat
```

**Windows (PowerShell)**:
```powershell
# Right-click → Run with PowerShell
# Or from PowerShell:
.\Launch-Dexter.ps1

# With custom port:
.\Launch-Dexter.ps1 -Port 8080

# Skip Cockpit UI:
.\Launch-Dexter.ps1 -SkipCockpit
```

**What it does**:
- ✅ Starts backend server on http://localhost:8765
- ✅ Waits 5 seconds for initialization
- ✅ Launches WPF Cockpit UI (if .NET SDK installed)
- ✅ Opens separate windows for each service
- ✅ Monitors both services

**Stops services**:
- Close the terminal windows, OR
- Press Ctrl+C in the launcher window

---

### 2. **Launch-Dexter-Cockpit.bat** / **Launch-Dexter-Cockpit.ps1** (Cockpit Only)
Starts ONLY the Cockpit UI (backend must be running separately).

**Windows (Batch)**:
```batch
# Double-click Launch-Dexter-Cockpit.bat
# Or from command line:
Launch-Dexter-Cockpit.bat
```

**Windows (PowerShell)**:
```powershell
# Right-click → Run with PowerShell
# Or from PowerShell:
.\Launch-Dexter-Cockpit.ps1

# With custom backend URL:
.\Launch-Dexter-Cockpit.ps1 -Backend "http://192.168.1.100:8765"

# Release build (faster startup):
.\Launch-Dexter-Cockpit.ps1 -Build Release
```

**What it does**:
- ✅ Checks for .NET 8.0 SDK
- ✅ Restores Cockpit dependencies
- ✅ Launches WPF Cockpit UI
- ✅ Connects to backend at http://localhost:8765

**Prerequisites**:
- Backend must be running first: `python start.py --port 8765`

---

## 🛠️ Troubleshooting

### ❌ "Python not found"
**Solution**: Install Python 3.10+ from https://python.org
```bash
# Verify:
python --version
```

### ❌ ".NET SDK not found"
**Solution**: Install .NET 8.0 SDK
```powershell
# Windows:
winget install Microsoft.DotNet.SDK.8

# Or download:
https://dotnet.microsoft.com/download/dotnet/8.0

# Verify:
dotnet --version  # Should show 8.x.x
```

### ❌ "Backend health check failed"
**Solution**: Check if another service is using port 8765
```powershell
# Windows - check port:
netstat -ano | findstr :8765

# Kill process if needed:
taskkill /PID <PID> /F

# Or use different port:
.\Launch-Dexter.ps1 -Port 8080
```

### ❌ "Cockpit dependencies restore failed"
**Solution**: Manually restore from cockpit directory
```powershell
cd cockpit\DexterCockpit
dotnet restore
dotnet build
```

### ❌ "Cockpit window doesn't appear"
**Solutions**:
1. Check backend is running: http://localhost:8765/health
2. Check .NET version: `dotnet --version` (must be 8.x)
3. Check for errors in console output
4. Try manual launch:
   ```powershell
   cd cockpit\DexterCockpit
   dotnet run
   ```

### ⚠️ "Redis connection refused"
**Note**: Redis is optional but recommended for Celery workers.

**Solution**: Install and start Redis
```powershell
# Windows (using Chocolatey):
choco install redis-64

# Or download MSI installer:
https://github.com/microsoftarchive/redis/releases

# Start Redis:
redis-server

# Verify:
redis-cli ping  # Should return "PONG"
```

---

## 📊 What You'll See

### Backend Server Output
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8765
[INFO] Celery worker started with 16 workers
[INFO] Health check: OK
```

### Cockpit UI
- **Connection Status**: Green 🟢 = Connected to backend
- **Agent Roster**: Shows all connected agents with status
- **Chat Window**: Ready to send messages to Dexter
- **Logs Panel**: Real-time log streaming from backend
- **Performance Metrics**: CPU, memory, event bus stats

---

## 🎮 Usage Examples

### Scenario 1: Development (Full Stack)
```powershell
# Start everything:
.\Launch-Dexter.ps1

# Result:
# - Backend at http://localhost:8765
# - Cockpit UI window opens
# - Both running in separate windows
```

### Scenario 2: Backend Only (Testing)
```bash
# Start backend:
python start.py --port 8765

# Test with curl:
curl http://localhost:8765/health

# Or use test client:
python scripts/test_websocket_client.py
```

### Scenario 3: Cockpit Only (UI Development)
```bash
# Terminal 1 - Start backend:
python start.py --port 8765

# Terminal 2 - Start cockpit with hot reload:
cd cockpit\DexterCockpit
dotnet watch run
```

### Scenario 4: Remote Backend
```powershell
# Connect Cockpit to remote server:
.\Launch-Dexter-Cockpit.ps1 -Backend "http://192.168.1.100:8765"
```

---

## 📂 File Structure
```
Dexter-Gliksbot/
├── Launch-Dexter.bat              # Full stack launcher (Batch)
├── Launch-Dexter.ps1              # Full stack launcher (PowerShell)
├── Launch-Dexter-Cockpit.bat      # Cockpit only (Batch)
├── Launch-Dexter-Cockpit.ps1      # Cockpit only (PowerShell)
├── install.py                     # Run this first!
├── start.py                       # Backend server (used by launchers)
└── cockpit/
    └── DexterCockpit/
        ├── DexterCockpit.csproj   # WPF project
        └── ...                    # UI code
```

---

## 🔗 Related Documentation

- **Installation**: Run `python install.py` first
- **Backend Setup**: See `README.md`
- **Cockpit Guide**: See `cockpit/QUICKSTART.md`
- **WebSocket Testing**: See `README-WEBSOCKET.md`
- **Architecture**: See `.github/copilot-instructions.md`

---

## 💡 Tips

### For 24/7 Operation
1. Use **Release build** for better performance:
   ```powershell
   .\Launch-Dexter-Cockpit.ps1 -Build Release
   ```

2. Run backend as Windows Service (advanced):
   ```powershell
   # Install NSSM (Non-Sucking Service Manager)
   choco install nssm
   
   # Create service:
   nssm install Dexter "C:\Python310\python.exe" "C:\path\to\start.py --port 8765"
   
   # Start service:
   nssm start Dexter
   ```

3. Enable auto-restart on crash (PowerShell script)

### For Multi-User Environments
- Use **Redis** for shared state across instances
- Configure **different ports** for each user
- Use **remote backend** URLs in Cockpit

### For Development
- Use **dotnet watch run** for hot reload in Cockpit
- Use **--reload** flag for backend: `python start.py --reload`
- Keep logs panel open for real-time debugging

---

**Questions?** See troubleshooting section above or check logs in Cockpit UI.

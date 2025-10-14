# GitHub Codespaces Setup Guide

This guide helps you get started with Dexter-Gliksbot in GitHub Codespaces.

## 🎯 What is GitHub Codespaces?

GitHub Codespaces provides a complete, cloud-based development environment that:
- Sets up automatically with all dependencies
- Runs in your browser or VS Code
- Includes all tools and extensions pre-configured
- Requires no local installation

Perfect for:
- Quick testing and experimentation
- Backend API development
- WebSocket feature development
- Code reviews and pull requests
- Cross-platform development

## 🚀 Getting Started

### Step 1: Create a Codespace

1. Go to the [Dexter-Gliksbot repository](https://github.com/Axepapag/Dexter-Gliksbot)
2. Click the green "Code" button
3. Select "Codespaces" tab
4. Click "Create codespace on main"

The setup will take 3-5 minutes and includes:
- Installing Python 3.11 and all dependencies
- Installing .NET 8.0 SDK
- Setting up Redis server
- Configuring VS Code extensions
- Running database migrations

### Step 2: Configure Environment

Once the Codespace is ready:

```bash
# Copy environment template (already done by setup)
# Edit with your API keys
nano .env
```

Add your API keys:
```env
# Choose your preferred provider
DEFAULT_PROVIDER=openai  # or nvidia, perplexity, anthropic

# Add corresponding API key
OPENAI_API_KEY=sk-...
NVIDIA_API_KEY=nvapi-...
PERPLEXITY_API_KEY=pplx-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Step 3: Start Development

```bash
# Start the server
python start.py --port 8765

# In another terminal: Run tests
pytest tests/ -v

# In another terminal: Test WebSocket
python scripts/test_websocket_client.py
```

## 📦 What's Pre-configured

### Software
✅ Python 3.11 with all dependencies  
✅ .NET 8.0 SDK (for Cockpit development)  
✅ Redis Server (auto-starts)  
✅ Git  
✅ pytest, ruff, black  

### VS Code Extensions
✅ Python + Pylance  
✅ Black formatter  
✅ Ruff linter  
✅ C# DevKit  
✅ YAML support  
✅ GitHub Copilot  

### Ports (Auto-forwarded)
- **8765**: Dexter API Server
- **6379**: Redis
- **11434**: Ollama (if using external endpoint)

## 🔧 Common Tasks

### Running Tests
```bash
# All tests
pytest tests/ -v

# WebSocket tests only
pytest tests/test_websocket_*.py -v

# With coverage
pytest tests/ --cov=dexter_autonomy --cov-report=html
```

### Linting and Formatting
```bash
# Check code style
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
black .
```

### Using Redis
```bash
# Check Redis status
redis-cli ping

# Monitor Redis activity
redis-cli monitor

# Flush all data (careful!)
redis-cli flushall
```

### Working with Database
```bash
# Run migrations manually
python -c "
from pathlib import Path
from dexter_autonomy.brain.migrate import MigrationManager
mgr = MigrationManager(Path('data/brain.db'))
mgr.run_migrations()
"

# Check database
sqlite3 data/brain.db ".tables"
```

## ⚠️ Limitations in Codespaces

### Not Available (Linux Environment)
❌ **Windows Automation**: pyautogui, pywinauto won't work  
❌ **Tesseract OCR**: Can install but no Windows GUI to capture  
❌ **WPF Cockpit UI**: Requires Windows to build and run  
❌ **Ollama (by default)**: Need to use cloud providers or external endpoint  

### Workarounds
✅ Use **OpenAI**, **NVIDIA**, **Perplexity** for LLM providers  
✅ Test **API endpoints** and **WebSocket** functionality  
✅ Develop **backend features** and **business logic**  
✅ Write and run **tests** for all components  
✅ Use **mock objects** for Windows-specific features in tests  

## 🐛 Troubleshooting

### Redis Not Running
```bash
# Start manually
redis-server --daemonize yes

# Verify
redis-cli ping  # Should return "PONG"
```

### Port 8765 Already in Use
```bash
# Use different port
python start.py --port 8766
```

### Dependencies Out of Date
```bash
# Update all dependencies
pip install -r requirements.txt --upgrade
```

### Codespace Running Slow
- Close unused browser tabs
- Stop unnecessary services
- Restart Codespace (Codespaces menu → Restart)

### Database Locked Error
```bash
# Stop any running processes
pkill -f "python start.py"

# Remove lock files
rm -f data/brain.db-shm data/brain.db-wal
```

## 💡 Pro Tips

### Multiple Terminals
Open split terminals (Ctrl+Shift+5) to:
- Terminal 1: Run server (`python start.py`)
- Terminal 2: Run tests (`pytest --watch`)
- Terminal 3: General commands

### Auto-save
Enable in VS Code settings:
```json
"files.autoSave": "afterDelay",
"files.autoSaveDelay": 1000
```

### Remote Debugging
Use VS Code debugger with Python extension:
1. Set breakpoints in code
2. Press F5 to start debugging
3. Debug through FastAPI endpoints

### Using External Ollama
If you have Ollama running elsewhere:
```env
# In .env
OLLAMA_API_ENDPOINT=http://your-server:11434
OLLAMA_API_KEY=  # if required
```

## 🔄 Syncing with Local Development

### Pull Latest Changes
```bash
git pull origin main
```

### Push Your Changes
```bash
git add .
git commit -m "Your commit message"
git push origin your-branch
```

### Create Pull Request
- Use GitHub UI to create PR
- Codespace stays in sync with your branch

## 📊 Resource Limits

GitHub Codespaces free tier includes:
- **60 hours/month** for 2-core machines (default)
- **120 GB/month** storage
- Auto-stops after 30 minutes of inactivity

[Check usage](https://github.com/settings/billing)

## 🚀 Advanced Configuration

### Rebuild Container
If you modify `.devcontainer/devcontainer.json`:
1. Open Command Palette (F1)
2. Search "Codespaces: Rebuild Container"
3. Confirm rebuild

### Customize Setup
Edit `.devcontainer/post-create.sh` to add:
- Additional dependencies
- Custom shell aliases
- Git configuration
- Additional tools

### Forward Additional Ports
Update `devcontainer.json`:
```json
"forwardPorts": [8765, 6379, 11434, 8080],
```

## 📚 Additional Resources

- [Main README](README.md)
- [WebSocket Documentation](README-WEBSOCKET.md)
- [Architecture Guide](.github/copilot-instructions.md)
- [Devcontainer Details](.devcontainer/README.md)
- [GitHub Codespaces Docs](https://docs.github.com/en/codespaces)

## 🤝 Getting Help

- Check [Issues](https://github.com/Axepapag/Dexter-Gliksbot/issues)
- Review [Discussions](https://github.com/Axepapag/Dexter-Gliksbot/discussions)
- Read [Contributing Guide](.github/copilot-instructions.md)

---

**Happy Coding in the Cloud! ☁️**

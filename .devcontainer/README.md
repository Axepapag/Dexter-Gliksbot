# GitHub Codespaces Configuration for Dexter-Gliksbot

This directory contains the configuration for developing Dexter-Gliksbot in GitHub Codespaces.

## 🚀 Quick Start

1. **Open in Codespace**
   - Click "Code" → "Codespaces" → "Create codespace on main"
   - Wait for container to build and setup to complete (~3-5 minutes)

2. **Configure Environment**
   ```bash
   # Edit .env to add your API keys
   nano .env
   ```

3. **Start Development Server**
   ```bash
   python start.py --port 8765
   ```

4. **Run Tests**
   ```bash
   pytest tests/ -v
   ```

## 📦 What's Included

### Pre-installed Software
- **Python 3.11** with all dependencies from `requirements.txt`
- **.NET 8.0 SDK** for WPF Cockpit development
- **Redis Server** (starts automatically)
- **Git** for version control

### VS Code Extensions
- Python (with Pylance)
- Black (formatter)
- Ruff (linter)
- C# DevKit
- Docker
- YAML
- GitHub Copilot

### Ports
- **8765**: Dexter API Server
- **6379**: Redis
- **11434**: Ollama (if configured externally)

## 🔧 Configuration

### Environment Variables
The setup script creates a `.env` file from `.env.example`. You'll need to add:
- `OLLAMA_API_KEY` (if using local Ollama)
- `OPENAI_API_KEY` (if using OpenAI)
- `NVIDIA_API_KEY` (if using NVIDIA)
- `PERPLEXITY_API_KEY` (if using Perplexity)
- Other provider keys as needed

### Provider Configuration
Since Ollama is not available by default in Codespaces, you have options:
1. **Remote Ollama**: Point to external Ollama endpoint
2. **Cloud Providers**: Use OpenAI, NVIDIA, Perplexity, etc.
3. **GitHub Models**: Use GitHub's hosted models

Edit `configs/slots.yml` to configure your preferred providers.

## 🐛 Troubleshooting

### Redis Not Running
```bash
# Start Redis manually
redis-server --daemonize yes

# Verify
redis-cli ping
```

### Python Dependencies Issue
```bash
# Reinstall dependencies
pip install -r requirements.txt --upgrade
```

### Database Migration Failed
```bash
# Run migrations manually
python -c "
from pathlib import Path
from dexter_autonomy.brain.migrate import MigrationManager
mgr = MigrationManager(Path('data/brain.db'))
mgr.run_migrations()
"
```

### Port Already in Use
```bash
# Use different port
python start.py --port 8766
```

## 📚 Additional Resources

- [Main README](../README.md)
- [WebSocket Documentation](../README-WEBSOCKET.md)
- [Architecture Guide](../.github/copilot-instructions.md)
- [Testing Guide](../WEBSOCKET_TESTING.md)

## 🔄 Rebuilding Container

If you need to rebuild the container with updated configuration:
1. Open Command Palette (F1)
2. Select "Codespaces: Rebuild Container"
3. Wait for rebuild to complete

## 🎯 Development Workflow

1. **Make changes** to code
2. **Lint**: `ruff check .`
3. **Format**: `black .`
4. **Test**: `pytest tests/ -v`
5. **Run**: `python start.py`
6. **Commit**: Use VS Code source control or git CLI

## 🚨 Known Limitations

- **Windows-specific features** (pyautogui, pywinauto, Tesseract OCR) will not work in Linux Codespace
- **WPF Cockpit** cannot be run directly (requires Windows)
- **Ollama** requires external setup or alternative provider

For full Windows development, use local Windows environment or Windows VM.

## 💡 Tips

- Use **multiple terminals** to run server + tests simultaneously
- Enable **auto-save** in VS Code for faster iteration
- Use **WebSocket test client** to verify real-time features
- Check **Redis** state with `redis-cli monitor`

---

**Note**: This Codespace configuration is optimized for backend development and testing. For full Windows automation and Cockpit UI development, use a Windows environment.

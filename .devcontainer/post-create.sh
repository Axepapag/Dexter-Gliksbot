#!/bin/bash
set -e

echo "🚀 Setting up Dexter-Gliksbot Development Environment..."

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install development dependencies
echo "🔧 Installing development dependencies..."
pip install pytest pytest-cov pytest-asyncio black ruff

# Create necessary directories
echo "📁 Creating project directories..."
mkdir -p data configs logs

# Copy environment template if .env doesn't exist
if [ ! -f .env ]; then
    echo "📋 Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env to add your API keys"
fi

# Initialize database
echo "🗄️  Initializing database..."
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
try:
    from dexter_autonomy.brain.migrate import MigrationManager
    mgr = MigrationManager(Path('data/brain.db'))
    mgr.run_migrations()
    print('✅ Database migrations complete')
except Exception as e:
    print(f'⚠️  Database migration skipped: {e}')
"

# Check Redis
echo "🔴 Checking Redis..."
redis-cli ping > /dev/null 2>&1 && echo "✅ Redis is running" || echo "⚠️  Redis not running - will start on container start"

# Check if Ollama is needed
echo ""
echo "📝 Note: Ollama is not installed in Codespace by default."
echo "   To use Ollama models, you'll need to:"
echo "   1. Use a remote Ollama endpoint, OR"
echo "   2. Configure alternative providers (OpenAI, NVIDIA, Perplexity)"
echo "   3. Edit .env to set your preferred provider"

echo ""
echo "✅ Development environment setup complete!"
echo ""
echo "🎯 Quick Start:"
echo "   1. Edit .env to add API keys"
echo "   2. Start server: python start.py --port 8765"
echo "   3. Run tests: pytest tests/ -v"
echo "   4. Check WebSocket: python scripts/test_websocket_client.py"
echo ""

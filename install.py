#!/usr/bin/env python3
"""
Dexter-Gliksbot Installation Script

This script performs comprehensive installation and setup:
1. Python version check (>=3.10)
2. Dependency installation (requirements.txt)
3. Optional dependencies (Tesseract OCR, Redis, Ollama)
4. Environment configuration (.env template)
5. Database initialization
6. Health checks
7. Platform-specific setup (Windows/Linux)

Usage:
    python install.py                    # Interactive installation
    python install.py --non-interactive  # Use defaults
    python install.py --skip-optional    # Skip optional dependencies
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}")
    print(f"{text:^70}")
    print(f"{'='*70}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def run_command(cmd: List[str], capture=True, check=True) -> Tuple[int, str, str]:
    """
    Run shell command and return result.
    
    Returns:
        (returncode, stdout, stderr)
    """
    try:
        if capture:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=check
            )
            return result.returncode, result.stdout, result.stderr
        else:
            result = subprocess.run(cmd, check=check)
            return result.returncode, "", ""
    except subprocess.CalledProcessError as e:
        if capture:
            return e.returncode, e.stdout or "", e.stderr or ""
        else:
            return e.returncode, "", ""
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"


def check_python_version() -> bool:
    """Check if Python version is >= 3.10."""
    print_info("Checking Python version...")
    
    version = sys.version_info
    if version >= (3, 10):
        print_success(f"Python {version.major}.{version.minor}.{version.micro} (required: >= 3.10)")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor}.{version.micro} (required: >= 3.10)")
        print_error("Please upgrade Python: https://www.python.org/downloads/")
        return False


def check_git() -> bool:
    """Check if git is available."""
    print_info("Checking git...")
    
    returncode, stdout, _ = run_command(["git", "--version"])
    if returncode == 0:
        version = stdout.strip()
        print_success(f"Git installed: {version}")
        return True
    else:
        print_warning("Git not found (optional for development)")
        return False


def check_pip() -> bool:
    """Check if pip is available."""
    print_info("Checking pip...")
    
    returncode, stdout, _ = run_command([sys.executable, "-m", "pip", "--version"])
    if returncode == 0:
        version = stdout.strip()
        print_success(f"Pip installed: {version}")
        return True
    else:
        print_error("Pip not found (required)")
        print_error("Install pip: https://pip.pypa.io/en/stable/installation/")
        return False


def install_requirements() -> bool:
    """Install Python dependencies from requirements.txt."""
    print_info("Installing Python dependencies...")
    
    requirements_file = Path(__file__).parent / "requirements.txt"
    if not requirements_file.exists():
        print_error(f"requirements.txt not found at {requirements_file}")
        return False
    
    returncode, stdout, stderr = run_command(
        [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
        capture=False
    )
    
    if returncode == 0:
        print_success("Python dependencies installed successfully")
        return True
    else:
        print_error("Failed to install Python dependencies")
        print_error(f"Error: {stderr}")
        return False


def check_tesseract() -> Dict[str, any]:
    """Check if Tesseract OCR is installed."""
    print_info("Checking Tesseract OCR (optional)...")
    
    # Try to find tesseract
    tesseract_cmd = shutil.which("tesseract")
    
    if tesseract_cmd:
        returncode, stdout, _ = run_command(["tesseract", "--version"])
        if returncode == 0:
            version = stdout.split('\n')[0]
            print_success(f"Tesseract found: {version}")
            return {"installed": True, "path": tesseract_cmd}
    
    print_warning("Tesseract OCR not found (optional for UI automation)")
    
    system = platform.system()
    if system == "Windows":
        print_info("  Install: https://github.com/UB-Mannheim/tesseract/wiki")
        print_info("  Or: winget install UB-Mannheim.TesseractOCR")
    elif system == "Linux":
        print_info("  Install: sudo apt-get install tesseract-ocr")
    elif system == "Darwin":
        print_info("  Install: brew install tesseract")
    
    return {"installed": False, "path": None}


def check_redis() -> Dict[str, any]:
    """Check if Redis is installed and running."""
    print_info("Checking Redis (optional for Celery workers)...")
    
    # Try to connect to Redis
    try:
        import redis
        client = redis.Redis(host='localhost', port=6379, socket_connect_timeout=2)
        client.ping()
        print_success("Redis is running on localhost:6379")
        return {"installed": True, "running": True}
    except Exception as e:
        if "redis" in str(e).lower() and "module" not in str(e).lower():
            print_warning(f"Redis not running: {e}")
            return {"installed": True, "running": False}
        else:
            print_warning("Redis not found (optional for Celery workers)")
            
            system = platform.system()
            if system == "Windows":
                print_info("  Install: https://redis.io/docs/getting-started/installation/install-redis-on-windows/")
            elif system == "Linux":
                print_info("  Install: sudo apt-get install redis-server")
                print_info("  Start: sudo systemctl start redis")
            elif system == "Darwin":
                print_info("  Install: brew install redis")
                print_info("  Start: brew services start redis")
            
            return {"installed": False, "running": False}


def check_ollama() -> Dict[str, any]:
    """Check if Ollama is installed and running."""
    print_info("Checking Ollama (optional for local LLMs)...")
    
    # Try to connect to Ollama
    import requests
    
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        response.raise_for_status()
        
        data = response.json()
        models = [m["name"] for m in data.get("models", [])]
        
        if models:
            print_success(f"Ollama is running with {len(models)} model(s): {', '.join(models[:3])}")
        else:
            print_success("Ollama is running (no models pulled yet)")
            print_info("  Pull a model: ollama pull qwen2.5:3b-instruct")
        
        return {"installed": True, "running": True, "models": models}
    except Exception:
        print_warning("Ollama not found (optional for local LLMs)")
        
        system = platform.system()
        if system == "Windows":
            print_info("  Install: https://ollama.com/download/windows")
        elif system == "Linux":
            print_info("  Install: curl -fsSL https://ollama.com/install.sh | sh")
        elif system == "Darwin":
            print_info("  Install: https://ollama.com/download/mac")
        
        print_info("  After install, pull a model: ollama pull qwen2.5:3b-instruct")
        
        return {"installed": False, "running": False, "models": []}


def check_dotnet_sdk() -> Dict[str, any]:
    """Check if .NET 8.0 SDK is installed (required for WPF Cockpit)."""
    print_info("Checking .NET 8.0 SDK (required for WPF Cockpit)...")
    
    returncode, stdout, stderr = run_command(["dotnet", "--version"], capture=True, check=False)
    
    if returncode == 0:
        version = stdout.strip()
        major_version = version.split('.')[0] if version else "0"
        
        if major_version == "8":
            print_success(f".NET SDK {version} is installed")
            
            # Check if cockpit can be built
            cockpit_path = Path(__file__).parent / "cockpit" / "DexterCockpit" / "DexterCockpit.csproj"
            if cockpit_path.exists():
                print_info("  Cockpit project found, checking build status...")
                returncode, _, _ = run_command(
                    ["dotnet", "restore", str(cockpit_path.parent)],
                    capture=True,
                    check=False
                )
                if returncode == 0:
                    print_success("  Cockpit dependencies restored successfully")
                    return {"installed": True, "version": version, "cockpit_ready": True}
                else:
                    print_warning("  Could not restore cockpit dependencies")
                    return {"installed": True, "version": version, "cockpit_ready": False}
            
            return {"installed": True, "version": version, "cockpit_ready": False}
        else:
            print_warning(f".NET SDK {version} found, but version 8.0 is required for WPF Cockpit")
            print_info("  Download: https://dotnet.microsoft.com/download/dotnet/8.0")
            return {"installed": False, "version": version, "cockpit_ready": False}
    else:
        print_warning(".NET SDK not found (required for WPF Cockpit)")
        
        system = platform.system()
        if system == "Windows":
            print_info("  Install: https://dotnet.microsoft.com/download/dotnet/8.0")
            print_info("  Or use: winget install Microsoft.DotNet.SDK.8")
        elif system == "Linux":
            print_info("  Install: https://dotnet.microsoft.com/download/dotnet/8.0")
        elif system == "Darwin":
            print_info("  Install: https://dotnet.microsoft.com/download/dotnet/8.0")
            print_info("  Or use: brew install dotnet@8")
        
        return {"installed": False, "version": None, "cockpit_ready": False}


def create_env_file(interactive=True) -> bool:
    """Create .env file from template."""
    print_info("Setting up environment configuration...")
    
    env_file = Path(__file__).parent / ".env"
    env_example = Path(__file__).parent / ".env.example"
    
    if env_file.exists():
        print_warning(".env file already exists")
        if interactive:
            overwrite = input("Overwrite? (y/N): ").lower().strip() == 'y'
            if not overwrite:
                print_info("Keeping existing .env file")
                return True
    
    # Create .env.example if it doesn't exist
    if not env_example.exists():
        template = """# Dexter-Gliksbot Environment Configuration

# LLM Provider API Keys (optional - use env vars for security)
OLLAMA_API_KEY=
OPENAI_API_KEY=
NVIDIA_API_KEY=
PERPLEXITY_API_KEY=
ANTHROPIC_API_KEY=
GROQ_API_KEY=
GITHUB_TOKEN=
AZURE_OPENAI_API_KEY=

# Redis Configuration (optional - for Celery workers)
REDIS_HOST=localhost
REDIS_PORT=6379

# Database Configuration
DATABASE_PATH=data/brain.db

# API Configuration
API_HOST=0.0.0.0
API_PORT=8765

# Logging
LOG_LEVEL=INFO
LOG_FILE=data/dexter.log

# Tesseract OCR Path (Windows only, auto-detected on Linux/Mac)
# TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
"""
        env_example.write_text(template)
        print_success("Created .env.example template")
    
    # Copy to .env
    shutil.copy(env_example, env_file)
    print_success(f"Created {env_file}")
    print_info("Edit .env to add your API keys (optional)")
    
    return True


def initialize_database() -> bool:
    """Initialize the brain database."""
    print_info("Initializing brain database...")
    
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    
    db_file = data_dir / "brain.db"
    
    try:
        # Run database migration
        sys.path.insert(0, str(Path(__file__).parent))
        from dexter_autonomy.brain.migrate import run_migrations
        
        run_migrations(str(db_file))
        print_success(f"Database initialized: {db_file}")
        return True
    except Exception as e:
        print_error(f"Failed to initialize database: {e}")
        return False


def run_health_checks() -> Dict[str, bool]:
    """Run comprehensive health checks."""
    print_header("Running Health Checks")
    
    checks = {}
    
    # Check if dexter_autonomy module can be imported
    print_info("Testing module imports...")
    try:
        import dexter_autonomy
        from dexter_autonomy.core.triple_bus import TripleBusSystem
        from dexter_autonomy.agents.providers import get_provider, PROVIDERS
        print_success("Core modules import successfully")
        checks["imports"] = True
    except Exception as e:
        print_error(f"Module import failed: {e}")
        checks["imports"] = False
    
    # Check provider registry
    print_info("Checking provider registry...")
    try:
        from dexter_autonomy.agents.providers import PROVIDERS, PROVIDER_PRESETS
        expected = ["ollama", "openai", "nvidia", "perplexity", "anthropic"]
        for name in expected:
            if name not in PROVIDERS:
                raise ValueError(f"Provider '{name}' not registered")
        print_success(f"{len(PROVIDERS)} providers registered")
        checks["providers"] = True
    except Exception as e:
        print_error(f"Provider check failed: {e}")
        checks["providers"] = False
    
    # Check data directory
    print_info("Checking data directory...")
    data_dir = Path(__file__).parent / "data"
    if data_dir.exists() and data_dir.is_dir():
        print_success(f"Data directory exists: {data_dir}")
        checks["data_dir"] = True
    else:
        print_warning("Data directory not found")
        checks["data_dir"] = False
    
    return checks


def print_summary(results: Dict[str, any]):
    """Print installation summary."""
    print_header("Installation Summary")
    
    print(f"{Colors.BOLD}Core Dependencies:{Colors.ENDC}")
    print(f"  Python: {results['python']}")
    print(f"  Pip: {results['pip']}")
    print(f"  Requirements: {results['requirements']}")
    print(f"  Database: {results['database']}")
    
    print(f"\n{Colors.BOLD}Optional Dependencies:{Colors.ENDC}")
    print(f"  Tesseract OCR: {results['tesseract']['installed']}")
    print(f"  Redis: {results['redis']['installed']} (Running: {results['redis']['running']})")
    print(f"  Ollama: {results['ollama']['installed']} (Models: {len(results['ollama']['models'])})")
    
    print(f"\n{Colors.BOLD}Health Checks:{Colors.ENDC}")
    for check, passed in results.get('health_checks', {}).items():
        status = f"{Colors.OKGREEN}✓{Colors.ENDC}" if passed else f"{Colors.FAIL}✗{Colors.ENDC}"
        print(f"  {check}: {status}")
    
    print(f"\n{Colors.BOLD}Next Steps:{Colors.ENDC}")
    print("  1. Edit .env to add your API keys (optional)")
    print("  2. Start the server: python start.py --port 8765")
    
    if results['dotnet']['cockpit_ready']:
        print(f"  3. Launch Cockpit UI: {Colors.OKGREEN}Launch-Dexter-Cockpit.bat{Colors.ENDC} (double-click)")
        print("  4. Test WebSocket: python scripts/test_websocket_client.py")
    else:
        print("  3. Test WebSocket: python scripts/test_websocket_client.py")
    
    print("  5. View documentation: See README-WEBSOCKET.md")
    
    if not results['ollama']['installed']:
        print(f"\n{Colors.WARNING}  Optional: Install Ollama for local LLM support{Colors.ENDC}")
    elif not results['ollama']['models']:
        print(f"\n{Colors.WARNING}  Optional: Pull an Ollama model: ollama pull qwen2.5:3b-instruct{Colors.ENDC}")
    
    if not results['redis']['running']:
        print(f"{Colors.WARNING}  Optional: Start Redis for Celery worker support{Colors.ENDC}")
    
    if not results['dotnet']['installed']:
        print(f"{Colors.WARNING}  Optional: Install .NET 8.0 SDK to run WPF Cockpit UI{Colors.ENDC}")
    elif not results['dotnet']['cockpit_ready']:
        print(f"{Colors.WARNING}  Cockpit UI available but needs dependency restore{Colors.ENDC}")


def main():
    """Main installation flow."""
    parser = argparse.ArgumentParser(description="Dexter-Gliksbot Installer")
    parser.add_argument("--non-interactive", action="store_true", help="Non-interactive mode (use defaults)")
    parser.add_argument("--skip-optional", action="store_true", help="Skip optional dependency checks")
    parser.add_argument("--skip-env", action="store_true", help="Skip .env file creation")
    args = parser.parse_args()
    
    print_header("Dexter-Gliksbot Installation")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    
    results = {
        "python": False,
        "pip": False,
        "requirements": False,
        "database": False,
        "tesseract": {"installed": False},
        "redis": {"installed": False, "running": False},
        "ollama": {"installed": False, "running": False, "models": []},
        "dotnet": {"installed": False, "version": None, "cockpit_ready": False},
        "health_checks": {}
    }
    
    # Core checks
    print_header("Core Dependencies")
    
    results["python"] = check_python_version()
    if not results["python"]:
        print_error("Python version check failed. Installation cannot continue.")
        sys.exit(1)
    
    results["pip"] = check_pip()
    if not results["pip"]:
        print_error("Pip check failed. Installation cannot continue.")
        sys.exit(1)
    
    check_git()  # Optional, just for info
    
    # Install requirements
    print_header("Installing Dependencies")
    results["requirements"] = install_requirements()
    if not results["requirements"]:
        print_error("Dependency installation failed. Installation cannot continue.")
        sys.exit(1)
    
    # Optional dependencies
    if not args.skip_optional:
        print_header("Optional Dependencies")
        results["tesseract"] = check_tesseract()
        results["redis"] = check_redis()
        results["ollama"] = check_ollama()
        results["dotnet"] = check_dotnet_sdk()
    
    # Environment setup
    if not args.skip_env:
        print_header("Environment Configuration")
        create_env_file(interactive=not args.non_interactive)
    
    # Database initialization
    print_header("Database Setup")
    results["database"] = initialize_database()
    
    # Health checks
    results["health_checks"] = run_health_checks()
    
    # Summary
    print_summary(results)
    
    # Check if installation was successful
    critical_checks = [
        results["python"],
        results["pip"],
        results["requirements"],
        results["database"],
    ]
    
    if all(critical_checks):
        print_header("Installation Complete!")
        print_success("Dexter-Gliksbot is ready to use!")
        sys.exit(0)
    else:
        print_header("Installation Incomplete")
        print_error("Some critical checks failed. Please review the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Dexter Autonomy unified launcher.

This script ensures dependencies are installed, applies database migrations,
starts supporting workers, and finally launches the FastAPI bridge.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def info(message: str) -> None:
    print(f"[+] {message}")


def warn(message: str) -> None:
    print(f"[!] {message}")


def error(message: str) -> None:
    print(f"[x] {message}")


def setup_environment(repo_root: Path) -> None:
    """Prepare required folders and environment variables."""
    data_dir = repo_root / "data"
    data_dir.mkdir(exist_ok=True)
    (repo_root / "configs").mkdir(exist_ok=True)
    os.environ.setdefault("DEXTER_DATA_DIR", str(data_dir))


def ensure_dependencies(repo_root: Path, include_workers: bool) -> bool:
    """Install required Python packages."""
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        import pydantic  # noqa: F401
    except ImportError:
        info("Installing base requirements...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                cwd=repo_root,
            )
        except subprocess.CalledProcessError as exc:
            error(f"Failed to install base dependencies (exit code {exc.returncode}).")
            return False

    if include_workers:
        try:
            import celery  # noqa: F401
            import redis  # noqa: F401
        except ImportError:
            info("Installing worker dependencies (celery, redis)...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "celery", "redis"],
                    cwd=repo_root,
                )
            except subprocess.CalledProcessError as exc:
                error(
                    f"Failed to install Celery/Redis packages (exit code {exc.returncode})."
                )
                return False

    return True


def run_migrations(repo_root: Path) -> bool:
    """Run Dexter brain migrations."""
    info("Running database migrations...")
    try:
        sys.path.insert(0, str(repo_root))
        from dexter_autonomy.brain.migrate import MigrationManager

        mgr = MigrationManager(repo_root / "data" / "brain.db")
        mgr.run_migrations()
        info("Migrations complete.")
        return True
    except Exception as exc:  # pylint: disable=broad-except
        error(f"Migration failed: {exc}")
        return False


def ensure_redis_running() -> bool:
    """Check that Redis is reachable."""
    try:
        import redis

        client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        client.ping()
        info("Redis responded on localhost:6379.")
        return True
    except ModuleNotFoundError:
        error("Redis Python package is missing. Re-run with dependencies installed.")
    except Exception as exc:  # pylint: disable=broad-except
        error(f"Redis connection failed: {exc}")
    return False


def launch_workers(repo_root: Path) -> None:
    """Start Celery worker and beat in the background."""
    info("Starting Celery worker...")
    worker_cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "dexter_autonomy.workers.tasks",
        "worker",
        "--loglevel=info",
    ]
    subprocess.Popen(worker_cmd, cwd=repo_root)  # noqa: S603,S607

    info("Starting Celery beat...")
    beat_cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "dexter_autonomy.workers.tasks",
        "beat",
        "--loglevel=info",
    ]
    subprocess.Popen(beat_cmd, cwd=repo_root)  # noqa: S603,S607


def print_banner(port: int, workers_enabled: bool) -> None:
    """Display a quick status summary."""
    print("\n" + "=" * 60)
    print("Dexter Autonomy Enhanced is starting")
    print("=" * 60)
    print("Available services:")
    print(" • OCR          : /ocr/extract")
    print(" • Memory       : /memory/*")
    print(" • Outbox       : /outbox/*")
    print(" • Intents      : /intent")
    print(" • Dexter chat  : /dexter/chat")
    print(" • Health       : /health")
    print("")
    print(f"Workers : {'enabled' if workers_enabled else 'disabled'}")
    print(f"API     : http://localhost:{port}")
    print("=" * 60 + "\n")


def launch_api(port: int) -> int:
    """Launch the FastAPI app via uvicorn."""
    info("Starting FastAPI bridge (uvicorn)...")
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "dexter_autonomy.ui_bridge.api:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--reload",
    ]
    return subprocess.run(cmd, check=False).returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start Dexter Autonomy (full stack by default)."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for the FastAPI server (default: 8765).",
    )
    parser.add_argument(
        "--no-workers",
        action="store_true",
        help="Skip starting Celery worker/beat (requires manual handling).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).parent

    setup_environment(repo_root)

    workers_enabled = not args.no_workers
    if not ensure_dependencies(repo_root, include_workers=workers_enabled):
        sys.exit(1)

    if not run_migrations(repo_root):
        sys.exit(1)

    if workers_enabled:
        if not ensure_redis_running():
            error("Redis is required for the full stack. Start Redis and rerun.")
            sys.exit(1)
        launch_workers(repo_root)
        os.environ["DEXTER_MODE"] = "full"
    else:
        os.environ["DEXTER_MODE"] = "core"
        warn("Workers disabled: background tasks and schedules will not run.")

    print_banner(args.port, workers_enabled)
    return_code = launch_api(args.port)
    if return_code != 0:
        error(f"uvicorn exited with code {return_code}.")
        sys.exit(return_code)


if __name__ == "__main__":
    main()

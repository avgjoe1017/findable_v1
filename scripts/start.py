"""Production startup script for Findable Score Analyzer.

This script handles:
1. Running database migrations (if enabled)
2. Starting the API server with proper configuration
3. Graceful shutdown handling
"""

import os
import signal
import subprocess
import sys


def run_migrations() -> bool:
    """Run database migrations before starting the app."""
    print("Running database migrations...")
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        print("Migrations complete.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Migration failed: {e.stderr}")
        return False


def start_api() -> None:
    """Start the FastAPI application with uvicorn."""
    port = os.getenv("PORT", "8000")
    workers = os.getenv("API_WORKERS", "1")
    host = os.getenv("API_HOST", "0.0.0.0")

    print(f"Starting API server on {host}:{port} with {workers} worker(s)...")

    # Use exec to replace the current process
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "api.main:app",
            "--host",
            host,
            "--port",
            port,
            "--workers",
            workers,
            "--proxy-headers",
            "--forwarded-allow-ips",
            "*",
        ],
    )


def signal_handler(signum: int, _frame: object) -> None:
    """Handle shutdown signals gracefully."""
    print(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main() -> None:
    """Main entry point."""
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Check if we should run migrations
    run_migrations_enabled = os.getenv("RUN_MIGRATIONS", "true").lower() == "true"

    if run_migrations_enabled and not run_migrations():
        print("Migration failed, but continuing with startup...")

    # Start the API server
    start_api()


if __name__ == "__main__":
    main()

#!/bin/bash
# fresh-restart.sh - Fresh Code Ops Restart Script
# ================================================
# Handles stale worker/cache issues with a single command.
#
# Usage:
#   ./scripts/fresh-restart.sh           # Full restart (worker + clear cache)
#   ./scripts/fresh-restart.sh --worker  # Just restart worker
#   ./scripts/fresh-restart.sh --cache   # Just clear cache
#   ./scripts/fresh-restart.sh --status  # Check status only
#
# Why this exists:
#   When making code changes, old worker processes can run stale code.
#   This script ensures you're always running fresh code.

set -e

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

step() { echo -e "\n${GREEN}[✔] $1${NC}"; }
info() { echo -e "    ${CYAN}$1${NC}"; }
warn() { echo -e "    ${YELLOW}[!] $1${NC}"; }
err() { echo -e "    ${RED}[X] $1${NC}"; }

show_help() {
    cat << 'EOF'

FRESH-RESTART - Kill stale processes and restart with fresh code
================================================================

Usage:
    ./scripts/fresh-restart.sh [options]

Options:
    (no args)   Full restart: stop worker, clear cache, restart worker
    --worker    Just stop and restart the worker process
    --cache     Just clear Redis cache
    --status    Show current status (processes, cache)
    --help      Show this help message

Examples:
    # After making code changes, do a full restart:
    ./scripts/fresh-restart.sh

    # Just check what's running:
    ./scripts/fresh-restart.sh --status

    # Clear cache but don't restart worker:
    ./scripts/fresh-restart.sh --cache

Why use this:
    - Avoids "ghost processes" running old code
    - Clears stale cached data
    - Single command instead of multiple steps
    - Provides status feedback

EOF
}

get_worker_pids() {
    # Find Python processes related to the worker
    pgrep -f "worker.main" 2>/dev/null || true
    pgrep -f "rq worker" 2>/dev/null || true
}

stop_workers() {
    step "Stopping worker processes..."

    pids=$(get_worker_pids)

    if [ -z "$pids" ]; then
        info "No worker processes found"
        return
    fi

    count=$(echo "$pids" | wc -l)
    info "Found $count worker process(es)"

    for pid in $pids; do
        info "Stopping PID $pid..."
        kill -TERM "$pid" 2>/dev/null || true
    done

    # Wait a moment
    sleep 2

    # Force kill any remaining
    pids=$(get_worker_pids)
    if [ -n "$pids" ]; then
        warn "Some processes still running. Force killing..."
        for pid in $pids; do
            kill -9 "$pid" 2>/dev/null || true
        done
    fi

    info "Worker processes stopped"
}

clear_cache() {
    step "Clearing Redis cache..."

    # Try redis-cli directly
    if command -v redis-cli &> /dev/null; then
        if redis-cli PING &> /dev/null; then
            redis-cli FLUSHDB &> /dev/null && info "Redis cache cleared (FLUSHDB)"
        else
            warn "Redis not responding"
        fi
    else
        info "redis-cli not available locally"
    fi

    # Try via Docker
    if command -v docker &> /dev/null; then
        docker exec findable-redis-1 redis-cli FLUSHDB 2>/dev/null && info "Redis cache cleared via Docker" || true
    fi

    # Clear Python cache
    info "Clearing Python cache..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

    info "Python cache cleared"
}

start_worker() {
    step "Starting fresh worker..."

    # Activate virtual environment if it exists
    if [ -f "venv/bin/activate" ]; then
        info "Activating virtual environment..."
        source venv/bin/activate
    fi

    # Start worker in background
    info "Starting worker..."
    nohup python -m worker.main > worker.log 2>&1 &
    worker_pid=$!

    info "Worker started (PID: $worker_pid)"
    info "Monitor with: tail -f worker.log"
}

show_status() {
    step "Current Status"

    echo -e "\n  ${NC}Worker Processes:${NC}"
    pids=$(get_worker_pids)
    if [ -z "$pids" ]; then
        info "No worker processes running"
    else
        for pid in $pids; do
            info "PID $pid - $(ps -p $pid -o comm= 2>/dev/null || echo 'unknown')"
        done
    fi

    echo -e "\n  ${NC}Redis:${NC}"
    if command -v redis-cli &> /dev/null; then
        if redis-cli PING &> /dev/null 2>&1; then
            dbsize=$(redis-cli DBSIZE 2>/dev/null)
            info "Connected - $dbsize"
        else
            warn "Not responding"
        fi
    else
        info "redis-cli not available (check Docker)"
    fi

    echo -e "\n  ${NC}Docker Containers:${NC}"
    if command -v docker &> /dev/null; then
        docker ps --format "{{.Names}}: {{.Status}}" 2>/dev/null | while read line; do
            info "$line"
        done
    else
        warn "Docker not available"
    fi

    echo -e "\n  ${NC}Database:${NC}"
    if [ -n "$DATABASE_URL" ]; then
        info "DATABASE_URL is set"
    else
        warn "DATABASE_URL not set (check .env)"
    fi
}

# Parse arguments
DO_WORKER=false
DO_CACHE=false
DO_STATUS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --worker)
            DO_WORKER=true
            shift
            ;;
        --cache)
            DO_CACHE=true
            shift
            ;;
        --status)
            DO_STATUS=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Default: do everything if no specific flags
if [ "$DO_WORKER" = false ] && [ "$DO_CACHE" = false ] && [ "$DO_STATUS" = false ]; then
    DO_WORKER=true
    DO_CACHE=true
fi

# Main execution
echo -e "\n${CYAN}========================================"
echo "FRESH-RESTART - Clean Code Operations"
echo -e "========================================${NC}"

if [ "$DO_STATUS" = true ]; then
    show_status
    exit 0
fi

if [ "$DO_WORKER" = true ]; then
    stop_workers
fi

if [ "$DO_CACHE" = true ]; then
    clear_cache
fi

if [ "$DO_WORKER" = true ]; then
    start_worker
fi

echo -e "\n${GREEN}========================================"
echo "Restart complete!"
echo -e "========================================${NC}\n"

# Show final status
show_status

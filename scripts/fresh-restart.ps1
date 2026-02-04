# fresh-restart.ps1 - Fresh Code Ops Restart Script
# ================================================
# Handles stale worker/cache issues with a single command.
#
# Usage:
#   .\scripts\fresh-restart.ps1           # Full restart (worker + clear cache)
#   .\scripts\fresh-restart.ps1 -worker   # Just restart worker
#   .\scripts\fresh-restart.ps1 -cache    # Just clear cache
#   .\scripts\fresh-restart.ps1 -status   # Check status only
#
# Why this exists:
#   When making code changes, old worker processes can run stale code.
#   This script ensures you're always running fresh code.

param(
    [switch]$worker,
    [switch]$cache,
    [switch]$status,
    [switch]$help
)

$ErrorActionPreference = "Stop"

# Colors for output
function Write-Step { param($msg) Write-Host "`n[$([char]0x2714)] $msg" -ForegroundColor Green }
function Write-Info { param($msg) Write-Host "    $msg" -ForegroundColor Cyan }
function Write-Warn { param($msg) Write-Host "    [!] $msg" -ForegroundColor Yellow }
function Write-Error { param($msg) Write-Host "    [X] $msg" -ForegroundColor Red }

function Show-Help {
    Write-Host @"

FRESH-RESTART - Kill stale processes and restart with fresh code
================================================================

Usage:
    .\scripts\fresh-restart.ps1 [options]

Options:
    (no args)   Full restart: stop worker, clear cache, restart worker
    -worker     Just stop and restart the worker process
    -cache      Just clear Redis cache
    -status     Show current status (processes, cache)
    -help       Show this help message

Examples:
    # After making code changes, do a full restart:
    .\scripts\fresh-restart.ps1

    # Just check what's running:
    .\scripts\fresh-restart.ps1 -status

    # Clear cache but don't restart worker:
    .\scripts\fresh-restart.ps1 -cache

Why use this:
    - Avoids "ghost processes" running old code
    - Clears stale cached data
    - Single command instead of multiple steps
    - Provides status feedback

"@
}

function Get-WorkerProcesses {
    # Find Python processes related to the worker
    $procs = Get-Process -Name "python*" -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -match "worker" -or $_.CommandLine -match "worker" }

    # Also check for rq worker processes
    $rqProcs = Get-Process -Name "python*" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "rq" -or $_.CommandLine -match "worker.main" }

    $all = @()
    if ($procs) { $all += $procs }
    if ($rqProcs) { $all += $rqProcs }

    return $all | Select-Object -Unique
}

function Stop-WorkerProcesses {
    Write-Step "Stopping worker processes..."

    $procs = Get-WorkerProcesses

    if ($procs.Count -eq 0) {
        Write-Info "No worker processes found"
        return
    }

    Write-Info "Found $($procs.Count) worker process(es)"

    foreach ($proc in $procs) {
        try {
            Write-Info "Stopping PID $($proc.Id) ($($proc.ProcessName))..."
            Stop-Process -Id $proc.Id -Force
        } catch {
            Write-Warn "Could not stop PID $($proc.Id): $_"
        }
    }

    # Wait a moment for processes to terminate
    Start-Sleep -Seconds 2

    # Verify they're stopped
    $remaining = Get-WorkerProcesses
    if ($remaining.Count -gt 0) {
        Write-Warn "Some processes still running. Force killing..."
        foreach ($proc in $remaining) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }

    Write-Info "Worker processes stopped"
}

function Clear-RedisCache {
    Write-Step "Clearing Redis cache..."

    # Check if Redis is running
    $redisProc = Get-Process -Name "redis-server" -ErrorAction SilentlyContinue
    if (-not $redisProc) {
        Write-Info "Redis not running locally (might be in Docker)"
    }

    # Try to clear via redis-cli
    try {
        $result = & redis-cli FLUSHDB 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Info "Redis cache cleared (FLUSHDB)"
        } else {
            Write-Warn "Could not run redis-cli (Redis might be in Docker)"
        }
    } catch {
        Write-Warn "redis-cli not available. Try: docker exec -it findable-redis-1 redis-cli FLUSHDB"
    }

    # Also try via Docker
    try {
        $dockerResult = & docker exec findable-redis-1 redis-cli FLUSHDB 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Info "Redis cache cleared via Docker"
        }
    } catch {
        # Silent - might not be using Docker
    }

    # Clear any Python __pycache__ directories
    Write-Info "Clearing Python cache..."
    Get-ChildItem -Path . -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

    # Clear .pyc files
    Get-ChildItem -Path . -Filter "*.pyc" -Recurse -File -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue }

    Write-Info "Python cache cleared"
}

function Start-Worker {
    Write-Step "Starting fresh worker..."

    # Activate virtual environment if it exists
    $venvPath = ".\venv\Scripts\Activate.ps1"
    if (Test-Path $venvPath) {
        Write-Info "Activating virtual environment..."
        & $venvPath
    }

    # Start worker in new window
    Write-Info "Starting worker in new terminal window..."
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd $PWD; .\venv\Scripts\Activate.ps1; python -m worker.main"

    Write-Info "Worker started in new window"
    Write-Info "Monitor with: Get-Content .\worker.log -Wait"
}

function Show-Status {
    Write-Step "Current Status"

    # Worker processes
    Write-Host "`n  Worker Processes:" -ForegroundColor White
    $procs = Get-WorkerProcesses
    if ($procs.Count -eq 0) {
        Write-Info "No worker processes running"
    } else {
        foreach ($proc in $procs) {
            Write-Info "PID $($proc.Id) - $($proc.ProcessName) (Started: $($proc.StartTime))"
        }
    }

    # Redis status
    Write-Host "`n  Redis:" -ForegroundColor White
    try {
        $ping = & redis-cli PING 2>$null
        if ($ping -eq "PONG") {
            $keys = & redis-cli DBSIZE 2>$null
            Write-Info "Connected - $keys"
        } else {
            Write-Warn "Not responding"
        }
    } catch {
        Write-Info "redis-cli not available (check Docker)"
    }

    # Docker containers
    Write-Host "`n  Docker Containers:" -ForegroundColor White
    try {
        $containers = & docker ps --format "{{.Names}}: {{.Status}}" 2>$null
        if ($containers) {
            foreach ($c in $containers) {
                Write-Info $c
            }
        } else {
            Write-Info "No containers running"
        }
    } catch {
        Write-Warn "Docker not available"
    }

    # Database connection
    Write-Host "`n  Database:" -ForegroundColor White
    if ($env:DATABASE_URL) {
        Write-Info "DATABASE_URL is set"
    } else {
        Write-Warn "DATABASE_URL not set (check .env)"
    }
}

# Main execution
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "FRESH-RESTART - Clean Code Operations" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if ($help) {
    Show-Help
    exit 0
}

if ($status) {
    Show-Status
    exit 0
}

# Determine what to do
$doWorker = $worker -or (-not $worker -and -not $cache)
$doCache = $cache -or (-not $worker -and -not $cache)

if ($doWorker) {
    Stop-WorkerProcesses
}

if ($doCache) {
    Clear-RedisCache
}

if ($doWorker) {
    Start-Worker
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Restart complete!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

# Show final status
Show-Status

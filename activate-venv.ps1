# Quick activation script for virtual environment
# Usage: .\activate-venv.ps1

if (-not (Test-Path "venv")) {
    Write-Host "❌ Virtual environment not found!" -ForegroundColor Red
    Write-Host "Run setup-venv.ps1 first to create it" -ForegroundColor Yellow
    exit 1
}

Write-Host "🔌 Activating virtual environment..." -ForegroundColor Cyan
& .\venv\Scripts\Activate.ps1

Write-Host "✅ Virtual environment activated!" -ForegroundColor Green
Write-Host ""
Write-Host "Quick commands:" -ForegroundColor Cyan
Write-Host "  Run migrations:  alembic upgrade head" -ForegroundColor White
Write-Host "  Start API:       uvicorn api.main:app --reload" -ForegroundColor White
Write-Host "  Start worker:    rq worker --with-scheduler" -ForegroundColor White
Write-Host "  Run tests:       pytest" -ForegroundColor White
Write-Host "  Deactivate:      deactivate" -ForegroundColor White

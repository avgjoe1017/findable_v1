# Start RQ Worker for Windows
# This script starts the RQ worker with Windows-compatible settings

$env:PYTHONPATH = "C:\Users\joeba\Documents\findable"

Write-Host "Starting RQ Worker on Windows..." -ForegroundColor Green
Write-Host "Queue: findable-default" -ForegroundColor Cyan
Write-Host "Worker Class: SimpleWorker (Windows compatible)" -ForegroundColor Cyan
Write-Host ""

.\venv\Scripts\rq.exe worker findable-default `
    --with-scheduler `
    --path "C:\Users\joeba\Documents\findable" `
    --worker-class rq.worker.SimpleWorker

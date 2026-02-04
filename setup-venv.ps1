# Setup script for Findable Score Analyzer
# Creates virtual environment and installs all dependencies

Write-Host "🚀 Setting up Findable Score Analyzer..." -ForegroundColor Cyan
Write-Host ""

# Check if venv already exists
if (Test-Path "venv") {
    Write-Host "⚠️  Virtual environment already exists." -ForegroundColor Yellow
    $response = Read-Host "Do you want to recreate it? (y/N)"
    if ($response -eq "y" -or $response -eq "Y") {
        Write-Host "🗑️  Removing existing virtual environment..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force venv
    } else {
        Write-Host "✅ Using existing virtual environment" -ForegroundColor Green
        Write-Host ""
        Write-Host "To activate it, run:" -ForegroundColor Cyan
        Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
        exit 0
    }
}

# Create virtual environment
Write-Host "📦 Creating virtual environment..." -ForegroundColor Cyan
python -m venv venv

if (-not $?) {
    Write-Host "❌ Failed to create virtual environment" -ForegroundColor Red
    Write-Host "Make sure Python 3.11+ is installed" -ForegroundColor Yellow
    exit 1
}

# Activate virtual environment
Write-Host "🔌 Activating virtual environment..." -ForegroundColor Cyan
& .\venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host "⬆️  Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

# Install dependencies
Write-Host "📚 Installing dependencies..." -ForegroundColor Cyan
pip install -e ".[dev]"

if (-not $?) {
    Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Install pre-commit hooks
Write-Host "🪝 Installing pre-commit hooks..." -ForegroundColor Cyan
pre-commit install

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  No .env file found. Copying from .env.example..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "✏️  Please edit .env with your database credentials" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Make sure PostgreSQL and Redis are running" -ForegroundColor White
Write-Host "  2. Update .env with your database credentials" -ForegroundColor White
Write-Host "  3. Run migrations: alembic upgrade head" -ForegroundColor White
Write-Host "  4. Start the server: uvicorn api.main:app --reload" -ForegroundColor White
Write-Host ""
Write-Host "Virtual environment is activated. To deactivate, run: deactivate" -ForegroundColor Cyan

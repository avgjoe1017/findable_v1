# Findable Score Analyzer - Railway Deployment Script
# Run this script to deploy to Railway

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "FINDABLE SCORE ANALYZER - RAILWAY DEPLOYMENT" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

# Check if Railway CLI is installed
$railwayCheck = Get-Command railway -ErrorAction SilentlyContinue
if (-not $railwayCheck) {
    Write-Host "[!] Railway CLI not found. Installing..." -ForegroundColor Yellow
    npm install -g @railway/cli
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[X] Failed to install Railway CLI. Install manually: npm install -g @railway/cli" -ForegroundColor Red
        exit 1
    }
}
Write-Host "[OK] Railway CLI installed" -ForegroundColor Green

# Check Railway login
Write-Host ""
Write-Host "Checking Railway login status..." -ForegroundColor Cyan
railway whoami 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Not logged in. Opening browser to authenticate..." -ForegroundColor Yellow
    railway login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[X] Login failed" -ForegroundColor Red
        exit 1
    }
}
Write-Host "[OK] Logged in to Railway" -ForegroundColor Green

# Link or create project
Write-Host ""
Write-Host "Linking Railway project..." -ForegroundColor Cyan
$linked = railway status 2>&1
if ($linked -match "not linked") {
    Write-Host "[!] Project not linked. Creating new project..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "MANUAL STEP REQUIRED:" -ForegroundColor Yellow
    Write-Host "1. Go to https://railway.app/new" -ForegroundColor White
    Write-Host "2. Click 'Empty Project'" -ForegroundColor White
    Write-Host "3. Add PostgreSQL database (Database -> PostgreSQL)" -ForegroundColor White
    Write-Host "4. Add Redis database (Database -> Redis)" -ForegroundColor White
    Write-Host "5. Copy the project ID from the URL" -ForegroundColor White
    Write-Host ""
    $projectId = Read-Host "Enter your Railway project ID (or press Enter to link existing)"
    if ($projectId) {
        railway link $projectId
    } else {
        railway link
    }
}
Write-Host "[OK] Project linked" -ForegroundColor Green

# Set environment variables
Write-Host ""
Write-Host "Configuring environment variables..." -ForegroundColor Cyan
Write-Host ""
Write-Host "Required environment variables:" -ForegroundColor Yellow
Write-Host "  - JWT_SECRET (will be auto-generated if not set)"
Write-Host "  - OPENROUTER_API_KEY or OPENAI_API_KEY"
Write-Host ""

$jwtSecret = -join ((48..57) + (97..102) | Get-Random -Count 64 | ForEach-Object {[char]$_})
Write-Host "Generated JWT_SECRET: $jwtSecret" -ForegroundColor Cyan

$setEnvs = Read-Host "Set environment variables now? (y/n)"
if ($setEnvs -eq "y") {
    railway variables set JWT_SECRET=$jwtSecret
    railway variables set ENV=production
    railway variables set LOG_LEVEL=INFO
    railway variables set RUN_MIGRATIONS=true

    $openRouterKey = Read-Host "Enter OPENROUTER_API_KEY (or press Enter to skip)"
    if ($openRouterKey) {
        railway variables set OPENROUTER_API_KEY=$openRouterKey
    }

    $openAiKey = Read-Host "Enter OPENAI_API_KEY (or press Enter to skip)"
    if ($openAiKey) {
        railway variables set OPENAI_API_KEY=$openAiKey
    }
}

# Deploy
Write-Host ""
Write-Host "Ready to deploy!" -ForegroundColor Green
Write-Host ""
$deploy = Read-Host "Deploy now? (y/n)"
if ($deploy -eq "y") {
    Write-Host "Deploying to Railway..." -ForegroundColor Cyan
    railway up --detach

    Write-Host ""
    Write-Host "Deployment initiated!" -ForegroundColor Green
    Write-Host "Monitor progress at: https://railway.app/dashboard" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Post-deployment steps:" -ForegroundColor Yellow
    Write-Host "1. Wait for build to complete (~5 min)" -ForegroundColor White
    Write-Host "2. Run: railway run alembic upgrade head" -ForegroundColor White
    Write-Host "3. Test: curl https://your-app.up.railway.app/api/health" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "To deploy later, run: railway up" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Deployment script complete" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan

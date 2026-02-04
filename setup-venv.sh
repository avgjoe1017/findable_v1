#!/bin/bash
# Setup script for Findable Score Analyzer (Linux/Mac)
# Creates virtual environment and installs all dependencies

set -e

echo "🚀 Setting up Findable Score Analyzer..."
echo ""

# Check if venv already exists
if [ -d "venv" ]; then
    echo "⚠️  Virtual environment already exists."
    read -p "Do you want to recreate it? (y/N): " response
    if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
        echo "🗑️  Removing existing virtual environment..."
        rm -rf venv
    else
        echo "✅ Using existing virtual environment"
        echo ""
        echo "To activate it, run:"
        echo "  source venv/bin/activate"
        exit 0
    fi
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
pip install -e ".[dev]"

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
pre-commit install

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Copying from .env.example..."
    cp .env.example .env
    echo "✏️  Please edit .env with your database credentials"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Make sure PostgreSQL and Redis are running"
echo "  2. Update .env with your database credentials"
echo "  3. Run migrations: alembic upgrade head"
echo "  4. Start the server: uvicorn api.main:app --reload"
echo ""
echo "Virtual environment is activated. To deactivate, run: deactivate"

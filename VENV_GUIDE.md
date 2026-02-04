# Virtual Environment Guide

This guide helps you set up and use a Python virtual environment for the Findable Score Analyzer project.

## Why Use a Virtual Environment?

- **Isolated Dependencies**: Keeps project dependencies separate from system Python
- **Version Consistency**: Ensures everyone uses the same package versions
- **No Conflicts**: Prevents conflicts between different projects
- **Clean Uninstall**: Easy to remove by deleting the `venv` folder

## Quick Start

### First Time Setup

**Windows (PowerShell):**
```powershell
.\setup-venv.ps1
```

**Linux/Mac:**
```bash
chmod +x setup-venv.sh
./setup-venv.sh
```

This script will:
1. Create a virtual environment in the `venv` folder
2. Activate the virtual environment
3. Install all project dependencies
4. Install pre-commit hooks
5. Copy `.env.example` to `.env` (if needed)

### Daily Usage

**Activate the virtual environment:**

Windows:
```powershell
.\venv\Scripts\Activate.ps1
# or use the quick script:
.\activate-venv.ps1
```

Linux/Mac:
```bash
source venv/bin/activate
```

**You'll know it's activated when you see `(venv)` in your terminal prompt.**

**Deactivate when done:**
```bash
deactivate
```

## Common Commands (with venv activated)

### Development
```bash
# Start API server
uvicorn api.main:app --reload

# Start worker
python -m worker.main

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=api --cov=worker

# Run specific test file
pytest tests/unit/test_auth.py -v
```

### Code Quality
```bash
# Lint code
ruff check .

# Format code
black .

# Type check
mypy api worker --ignore-missing-imports

# Run all checks
ruff check . && black --check . && mypy api worker --ignore-missing-imports
```

### Dependency Management
```bash
# Install new package
pip install package-name

# Update pyproject.toml with the new dependency
# Then reinstall in editable mode:
pip install -e ".[dev]"

# List installed packages
pip list

# Show package details
pip show package-name
```

## Troubleshooting

### Virtual Environment Not Found
```powershell
# Run setup script again
.\setup-venv.ps1
```

### Wrong Python Version
```bash
# Check Python version in venv
python --version

# Should be Python 3.11+
# If not, delete venv and recreate:
rm -rf venv  # or Remove-Item -Recurse -Force venv on Windows
python -m venv venv
```

### Import Errors After Installing Packages
```bash
# Reinstall in editable mode
pip install -e ".[dev]"
```

### PowerShell Execution Policy Error (Windows)
```powershell
# If you get "cannot be loaded because running scripts is disabled"
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Module Not Found Errors
```bash
# Make sure venv is activated (you should see (venv) in prompt)
# Then reinstall dependencies:
pip install -e ".[dev]"
```

## Best Practices

1. **Always activate the venv** before running any Python commands
2. **Never commit the `venv` folder** (it's in `.gitignore`)
3. **Update `pyproject.toml`** when adding new dependencies
4. **Recreate venv** if you switch Python versions
5. **Use the same Python version** as specified in `pyproject.toml` (3.11+)

## CI/CD Note

The CI/CD pipeline (GitHub Actions) automatically creates a fresh virtual environment for each run, so you don't need to worry about it for automated tests.

## Additional Resources

- [Python venv documentation](https://docs.python.org/3/library/venv.html)
- [pip documentation](https://pip.pypa.io/en/stable/)
- [Project README](./README.md)

# Findable Score Analyzer

Measure whether AI answer engines can retrieve and use your website as a source.

## Features

- **Findable Score (0-100)**: Single metric for AI sourceability
- **Show the Math**: Transparent scoring breakdown
- **Competitive Benchmark**: Compare against competitors
- **Reality Snapshots**: Validate with actual AI model outputs
- **Fix Plan**: Actionable recommendations with impact estimates

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (for local Postgres + Redis)

### Setup

```bash
# Clone repository
git clone <repo-url>
cd findable

# Copy environment file
cp .env.example .env

# Start local services
docker-compose up -d

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run migrations
alembic upgrade head

# Start API server
uvicorn api.main:app --reload

# Start worker (separate terminal)
python -m worker.main
```

### Running Tests

```bash
pytest -v
```

### Linting

```bash
ruff check .
black --check .
mypy api worker
```

## Project Structure

```
findable/
├── api/              # FastAPI application
│   ├── routers/      # API endpoints
│   ├── models/       # SQLAlchemy models
│   ├── schemas/      # Pydantic schemas
│   ├── services/     # Business logic
│   └── providers/    # LLM provider interfaces
├── worker/           # Background job processing
├── web/              # Jinja2 templates
├── migrations/       # Alembic migrations
└── tests/            # Test suite
```

## API Endpoints

- `GET /health` - Health check
- `GET /v1/` - API version info
- `POST /v1/auth/register` - Create account
- `POST /v1/auth/login` - Authenticate
- `POST /v1/sites` - Create site
- `POST /v1/sites/{id}/runs` - Start audit
- `GET /v1/reports/{id}` - Get report

## License

MIT

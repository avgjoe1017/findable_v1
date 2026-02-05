# Production instructions

Quick reference for running Findable Score Analyzer in production (e.g. Railway).

## Required environment variables

These must be set for the API (and worker/scheduler if used); the app will not start without them.

| Variable        | Description                    | Example / notes                          |
|----------------|--------------------------------|------------------------------------------|
| `DATABASE_URL` | PostgreSQL connection string   | `postgresql+asyncpg://user:pass@host:5432/db` — usually provided by linking Postgres in Railway |
| `REDIS_URL`    | Redis connection string        | `redis://host:6379/0` — usually provided by linking Redis in Railway   |
| `JWT_SECRET`   | Secret for signing JWT tokens  | Generate with e.g. `openssl rand -hex 32`; set manually in Railway    |

Optional but recommended: `ENV=production`, `LOG_LEVEL=INFO`, `OPENROUTER_API_KEY` or `OPENAI_API_KEY`. See DEPLOYMENT.md for the full list.

## Railway: getting variables into the API service

1. In the same Railway project, add **PostgreSQL** and **Redis** (New → Database → PostgreSQL / Redis).
2. Open your **API service** (the one that runs the app from this repo).
3. In **Variables**:
   - Use **Add reference** / **Connect** to the Postgres and Redis services so Railway injects `DATABASE_URL` and `REDIS_URL`.
   - Add **JWT_SECRET** as a plain variable (generate a secure random string).
4. Save and redeploy so the new container receives the variables.

If these are missing, startup will fail with: `ValidationError: ... database_url, redis_url, jwt_secret - Field required`.

## Migrations

Migrations run on container start when using `scripts.start`. To run them manually:

```bash
railway run alembic upgrade head
```

Ensure `DATABASE_URL` is set (via linked Postgres) before running migrations.

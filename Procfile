# Procfile for Railway and Heroku deployment
# Each line defines a process type and its start command

# Main web process (API server)
web: python -m scripts.start

# Background worker for job processing
worker: python -m worker.main

# Scheduler for periodic tasks (monitoring snapshots)
scheduler: rqscheduler --host $REDIS_HOST --port $REDIS_PORT --db 0

# One-off migration process
release: alembic upgrade head

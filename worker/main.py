"""RQ Worker entrypoint."""

import os
import sys

from redis import Redis
from rq import Worker

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.config import get_settings


def run_worker() -> None:
    """Start the RQ worker."""
    settings = get_settings()

    redis_conn = Redis.from_url(str(settings.redis_url))

    queues = ["findable-high", "findable-default", "findable-low"]

    worker = Worker(queues, connection=redis_conn)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    run_worker()

"""Entry point for Celery worker.

Usage:
    cd backend && celery -A app.worker worker --loglevel=info
"""

from app.worker.celery_app import celery_app

# This import registers tasks
import app.worker.tasks  # noqa: F401

if __name__ == "__main__":
    celery_app.start()

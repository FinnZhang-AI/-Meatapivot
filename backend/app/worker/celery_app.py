"""Celery worker configuration for Meatapivot.

Provides asynchronous task processing for:
- Document parsing
- Ontology compilation
- Decision flow execution
- Function-backed action execution
"""

import os
from celery import Celery
from celery.signals import worker_ready

# Use RabbitMQ as broker and Redis as result backend
broker_url = os.getenv("RABBITMQ_URL", "amqp://admin:admin123@localhost:5672/")
result_backend = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "meatapivot",
    broker=broker_url,
    backend=result_backend,
    include=[
        "app.worker.tasks",
    ],
)

celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution
    task_always_eager=False,  # Set True for testing (run tasks synchronously)
    task_store_eager_result=True,
    
    # Retries
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Result backend
    result_expires=3600,  # 1 hour
    result_extended=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)


@worker_ready.connect
def on_worker_ready(**kwargs):
    """Called when Celery worker is ready."""
    print("Celery worker is ready")

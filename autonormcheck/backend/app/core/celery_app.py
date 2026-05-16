"""
Celery application configuration for async task processing.
"""
from celery import Celery
from app.core.config import settings

# Create Celery application
celery_app = Celery(
    "autonormcheck",
    broker=settings.CELERY_BROKER,
    backend=settings.CELERY_BACKEND,
    include=["app.workers.tasks"]
)

# Celery configuration
celery_app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    
    # Retry settings
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # Result expiration (1 hour)
    result_expires=3600,
    
    # Rate limiting
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Queue configuration
    task_routes={
        "app.workers.tasks.parse_file": {"queue": "parsing"},
        "app.workers.tasks.analyze_file": {"queue": "ai_analysis"},
        "app.workers.tasks.cleanup_expired_files": {"queue": "cleanup"},
    },
)


# Auto-discover tasks in workers module
celery_app.autodiscover_tasks(["app.workers"])


if __name__ == "__main__":
    celery_app.start()

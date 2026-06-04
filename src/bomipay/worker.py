import logging
from celery import Celery, Task
from celery.schedules import crontab
from .config import settings

logger = logging.getLogger("bomipay")


class CallbackTask(Task):
    """Celery task with automatic retry logic."""
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 3600


app = Celery(
    "bomipay",
    broker=settings.redis_url,
    backend=settings.redis_url,
    task_serializer="json",
)

app.conf.update(
    result_expires=3600,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

app.conf.beat_schedule = {
    "consume-events-every-10-seconds": {
        "task": "bomipay.tasks.event_consumption.consume_and_process_events",
        "schedule": 10.0,
    },
    "aggregate-alerts-every-5-minutes": {
        "task": "bomipay.tasks.alert_aggregation.aggregate_alerts",
        "schedule": 300.0,
        "args": ("all_merchants",),
    },
    "poll-provider-health-hourly": {
        "task": "bomipay.tasks.provider_health.poll_provider_health",
        "schedule": 3600.0,
        "args": ("all_providers",),
    },
    "calculate-provider-reliability-daily": {
        "task": "bomipay.tasks.provider_health.calculate_provider_reliability_scores",
        "schedule": crontab(hour=0, minute=0),
    },
}

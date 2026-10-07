from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery("uni", broker=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_ignore_result=True,
    timezone="Europe/Warsaw",
    beat_schedule={
        "purge-rejected-applications": {
            "task": "admissions.purge_rejected",
            "schedule": crontab(hour=3, minute=15),
        },
    },
)

"""Celery entry point: `celery -A app.worker worker` / `celery -A app.worker beat`."""

from functools import lru_cache

from celery.signals import worker_process_init

from app.celery_app import celery_app
from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.jobs import JOBS, JobFunction, load_job_modules
from app.services import build_services


@lru_cache
def _runtime() -> tuple:
    settings = get_settings()
    return make_session_factory(make_engine(settings.database_url)), build_services(settings)


@worker_process_init.connect
def _warm_up(**_kwargs) -> None:
    # Loads the embedding model once per worker process instead of on the first job.
    _runtime()


def _register(name: str, fn: JobFunction) -> None:
    @celery_app.task(
        name=name, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=5
    )
    def task(**kwargs) -> None:
        session_factory, services = _runtime()
        with session_factory() as session:
            fn(session, services, **kwargs)


load_job_modules()
for job_name, job_fn in JOBS.items():
    _register(job_name, job_fn)

app = celery_app

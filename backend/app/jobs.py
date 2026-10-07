"""Background job registry.

Job functions are plain functions taking (session, services, **kwargs). The
Celery worker wraps each one in a task; tests call them directly through an
inline queue, so job logic is covered without a broker.
"""

from collections.abc import Callable
from typing import Protocol

JobFunction = Callable[..., None]

JOBS: dict[str, JobFunction] = {}


def job(name: str) -> Callable[[JobFunction], JobFunction]:
    def register(fn: JobFunction) -> JobFunction:
        JOBS[name] = fn
        return fn

    return register


class JobQueue(Protocol):
    def enqueue(self, name: str, **kwargs) -> None: ...


class CeleryJobQueue:
    def __init__(self, celery_app):
        self._celery = celery_app

    def enqueue(self, name: str, **kwargs) -> None:
        if name not in JOBS:
            raise KeyError(f"Unknown job {name}")
        self._celery.send_task(name, kwargs=kwargs)


def load_job_modules() -> None:
    """Import every module that registers jobs."""
    from app.admissions import jobs as _admissions  # noqa: F401
    from app.assistant import jobs as _assistant  # noqa: F401
    from app.notifications import jobs as _notifications  # noqa: F401

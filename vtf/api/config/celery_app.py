"""
The Beat schedule (cron tasks) lives in Django settings under
CELERY_BEAT_SCHEDULE (see config/settings/base.py) so settings are the
single source of truth.

Local usage (no Docker, no Redis — uses SQLite broker):
  cd vtf/api

  Terminal 1 — worker:
    celery -A config.celery_app worker --loglevel=info --concurrency=2

  Terminal 2 — beat scheduler:
    celery -A config.celery_app beat --loglevel=info

  Dev shortcut (worker + beat in one process):
    celery -A config.celery_app worker --beat --loglevel=info --concurrency=2
"""
from __future__ import annotations

import logging
import os

from celery import Celery
from celery.signals import beat_init, task_failure, task_postrun, task_prerun, worker_ready

from config.logging import paris_now

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("vtf")
logger = logging.getLogger("celery")

# Read all CELERY_* keys from Django settings — includes CELERY_BEAT_SCHEDULE.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in every INSTALLED_APP.
app.autodiscover_tasks()


@worker_ready.connect
def log_worker_ready(sender=None, **kwargs) -> None:
    hostname = getattr(sender, "hostname", "unknown-worker")
    logger.info("celery_worker_started worker=%s started_at=%s", hostname, paris_now())


@beat_init.connect
def log_beat_started(sender=None, **kwargs) -> None:
    scheduler = getattr(getattr(sender, "app", None), "conf", {}).get("beat_scheduler", "")
    logger.info(
        "celery_beat_started scheduler=%s started_at=%s",
        scheduler or "unknown",
        paris_now(),
    )


@task_prerun.connect
def log_task_started(task_id=None, task=None, args=None, kwargs=None, **extra) -> None:
    task_name = getattr(task, "name", "unknown-task")
    logger.info(
        "celery_task_started task=%s task_id=%s started_at=%s args=%s kwargs=%s",
        task_name,
        task_id,
        paris_now(),
        args or (),
        kwargs or {},
    )


@task_postrun.connect
def log_task_finished(
    task_id=None,
    task=None,
    retval=None,
    state=None,
    runtime=None,
    **extra,
) -> None:
    task_name = getattr(task, "name", "unknown-task")
    if state == "SUCCESS":
        logger.debug(
            "celery_task_finished task=%s task_id=%s state=%s runtime=%s finished_at=%s",
            task_name,
            task_id,
            state,
            runtime,
            paris_now(),
        )
        return

    logger.info(
        "celery_task_finished task=%s task_id=%s state=%s runtime=%s finished_at=%s result=%r",
        task_name,
        task_id,
        state,
        runtime,
        paris_now(),
        retval,
    )


@task_failure.connect
def log_task_failed(
    task_id=None,
    exception=None,
    traceback=None,
    sender=None,
    einfo=None,
    **kwargs,
) -> None:
    task_name = getattr(sender, "name", "unknown-task")
    exc_info = None
    if exception is not None:
        exc_info = (type(exception), exception, getattr(exception, "__traceback__", None))
    logger.error(
        "celery_task_failed task=%s task_id=%s failed_at=%s error=%s",
        task_name,
        task_id,
        paris_now(),
        exception,
        exc_info=exc_info,
    )

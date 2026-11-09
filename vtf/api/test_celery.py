import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

import config.celery_app  # initializes Celery with correct broker
from apps.cache_orchestrator.tasks import task_rebuild_cache
from apps.header_scraper.tasks import (
    task_scrape_header_banner,
    task_scrape_header_banner_language,
)
from apps.recommender.tasks import task_refresh_popularity, task_check_cf_readiness, task_train_cf_model
from apps.scraper.tasks import task_monthly_scrape_all

task_refresh_popularity.delay()
print("Task sent for Refresh Popularity — check Terminal 1 for execution logs")


task_check_cf_readiness.delay()
print("Task sent for Check CF Readiness — check Terminal 1 for execution logs")

task_train_cf_model.delay()
print("Task sent for Train CF Model — check Terminal 1 for execution logs")

task_rebuild_cache.delay(
    scope="all",
    reason="Manual test trigger for scheduled daily 07:00 cache rebuild",
    triggered_by="test_celery.py",
)
print("Task sent for Rebuild Cache — check Terminal 1 for execution logs")

task_monthly_scrape_all.delay()
print("Task sent for Monthly Scrape All Villages — check Terminal 1 for execution logs")

task_scrape_header_banner.delay()
print("Task sent for Scrape Header Banner (FR + GB) — check Terminal 1 for execution logs")

task_scrape_header_banner_language.delay("FR")
print("Task sent for Scrape Header Banner Language=FR — check Terminal 1 for execution logs")

from __future__ import annotations

import logging
import os
import sys

from django.core.management import call_command
from django.db.models.signals import post_migrate
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _auto_load_enabled() -> bool:
    return os.getenv("AUTO_LOAD_CATALOG_FIXTURES", "1") == "1"


def _running_tests() -> bool:
    return any("pytest" in arg for arg in sys.argv)


@receiver(post_migrate)
def load_catalog_fixtures_after_migrate(sender, **kwargs) -> None:
    if getattr(sender, "label", None) != "catalog":
        return

    if not _auto_load_enabled():
        logger.info("catalog_auto_fixture_load_skipped disabled=true")
        return

    if _running_tests():
        logger.info("catalog_auto_fixture_load_skipped tests=true")
        return

    logger.info("catalog_auto_fixture_load_started trigger=post_migrate")
    call_command("load_vtf_mocks", verbosity=1)
    logger.info("catalog_auto_fixture_load_done trigger=post_migrate")

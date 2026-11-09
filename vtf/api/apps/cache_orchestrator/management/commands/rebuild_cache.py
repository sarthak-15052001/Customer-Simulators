"""Management command: rebuild_cache

CLI equivalent of POST /api/v1/admin/cache/rebuild.
Runs the rebuild synchronously (no Celery needed).

Usage::

    # Rebuild everything
    python manage.py rebuild_cache

    # Rebuild only pricing-related keys
    python manage.py rebuild_cache --scope=pricing

    # Rebuild a single village
    python manage.py rebuild_cache --scope=villages:biarritz

    # With a reason (stored in CacheRebuildLog)
    python manage.py rebuild_cache --scope=all --reason="Post-deploy warm"

Spec §5.1 / AC3.1 / AC3.2.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.cache_orchestrator.service import CacheOrchestrator


class Command(BaseCommand):
    help = "Invalidate and re-warm Redis cache keys for a given scope."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--scope",
            default="all",
            help=(
                "Cache scope to rebuild. "
                "Options: all | catalog | pricing | recommendations | booking_urls | "
                "villages:<id> | regions:<key>. "
                "Default: all."
            ),
        )
        parser.add_argument(
            "--reason",
            default="",
            help="Optional reason stored in CacheRebuildLog.",
        )

    def handle(self, *args, **options) -> None:
        scope = options["scope"]
        reason = options["reason"] or f"CLI: python manage.py rebuild_cache --scope={scope}"

        self.stdout.write(
            self.style.MIGRATE_HEADING(f"Rebuilding cache scope='{scope}' …")
        )

        result = CacheOrchestrator.rebuild(
            scope=scope,
            reason=reason,
            triggered_by="system:management_command:rebuild_cache",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. "
                f"keys_invalidated={result['keysInvalidated']}  "
                f"keys_rebuilt={result['keysRebuilt']}  "
                f"duration={result['durationMs']}ms"
            )
        )

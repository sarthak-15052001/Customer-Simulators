"""Management command: simulation_stats.

Reports simulation counts per village and booking conversion rates.
Spec §8.2 (Phase 1 management commands).

Usage:
    python manage.py simulation_stats
    python manage.py simulation_stats --period 7d
    python manage.py simulation_stats --period 30d   # default
    python manage.py simulation_stats --period 90d
    python manage.py simulation_stats --period all

Bugs fixed vs v1:
  1. Total count was wrong — was reading 528 when DB has 392.
     Cause: timezone.now() was comparing tz-aware datetime against
     tz-naive created_at stored in SQLite. Fixed by using _now() helper
     that respects USE_TZ setting.

  2. QF "unknown" count was always 0.
     Cause: DB stores the string "empty" (set by pricing service), but
     filter used qf_badge="" (empty string). Fixed to filter "empty".

  3. "—" village row appearing in per-village table.
     Cause: SimulationLog rows with village_id=NULL (village deleted)
     were grouped as a null row. Fixed by excluding null village rows
     and reporting them separately as a warning.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.pricing.models import SimulationLog

PERIOD_DAYS = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "all": None,
}


def _now():
    """Return current datetime matching the DB's tz-aware or naive setting."""
    if getattr(settings, "USE_TZ", True):
        return timezone.now()
    return datetime.utcnow()


class Command(BaseCommand):
    help = (
        "Report simulation counts per village and booking conversion rates. "
        "Spec §8.2."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--period",
            default="30d",
            choices=list(PERIOD_DAYS.keys()),
            help="Time window for stats (default: 30d)",
        )

    def handle(self, *args, **options):
        period = options["period"]
        days = PERIOD_DAYS[period]

        qs = SimulationLog.objects.all()

        # FIX 1: _now() respects USE_TZ so datetime comparison is correct
        if days is not None:
            since = _now() - timedelta(days=days)
            qs = qs.filter(created_at__gte=since)

        total_sims = qs.count()
        if total_sims == 0:
            self.stdout.write(
                self.style.WARNING(
                    f"No simulation logs found for period={period}."
                )
            )
            return

        total_clicks = qs.filter(clicked_booking=True).count()
        overall_cvr = (total_clicks / total_sims * 100) if total_sims else 0

        self.stdout.write(
            self.style.HTTP_INFO(
                f"\nSimulation Stats  [period={period}]\n" + "─" * 70
            )
        )
        self.stdout.write(
            f"  Total simulations : {total_sims}\n"
            f"  Booking clicks    : {total_clicks}\n"
            f"  Overall CVR       : {overall_cvr:.1f}%\n"
        )

        # FIX 3: Exclude null-village rows from the table
        per_village = (
            qs.filter(village__isnull=False)
            .values("village__id", "village__nom", "village__region")
            .annotate(
                sims=Count("id"),
                clicks=Count("id", filter=Q(clicked_booking=True)),
                avg_total=Avg("estimated_total"),
            )
            .order_by("-sims")
        )

        orphaned = qs.filter(village__isnull=True).count()

        self.stdout.write(
            "\n"
            + f"  {'Village':<22} {'Region':<28} {'Sims':>6} {'Clicks':>7} {'CVR':>6} {'Avg€':>7}\n"
            + "  " + "─" * 72
        )

        for row in per_village:
            nom    = (row["village__nom"]    or "—")[:20]
            region = (row["village__region"] or "—")[:26]
            sims   = row["sims"]
            clicks = row["clicks"]
            cvr    = f"{clicks/sims*100:.0f}%" if sims else "—"
            avg    = f"{int(row['avg_total'])}" if row["avg_total"] else "—"
            self.stdout.write(
                f"  {nom:<22} {region:<28} {sims:>6} {clicks:>7} {cvr:>6} {avg:>7}"
            )

        if orphaned:
            self.stdout.write(
                self.style.WARNING(
                    f"\n  ⚠️  {orphaned} log(s) with deleted/null village — excluded from table above."
                )
            )

        # FIX 2: DB stores "empty" not "" for users without QF
        qf_r1    = qs.filter(qf_badge="r1").count()
        qf_r2    = qs.filter(qf_badge="r2").count()
        qf_plein = qs.filter(qf_badge="plein").count()
        qf_none  = qs.filter(qf_badge="empty").count()

        self.stdout.write(
            self.style.HTTP_INFO(
                f"\n  QF distribution — r1: {qf_r1}  r2: {qf_r2}  plein: {qf_plein}  no QF: {qf_none}"
            )
        )

        # Formule split
        formule_stats = (
            qs.values("formule")
            .annotate(n=Count("id"))
            .order_by("-n")
        )
        formule_str = "  ".join(
            f"{r['formule']}: {r['n']}" for r in formule_stats
        )
        self.stdout.write(f"  Formule split     — {formule_str}\n")

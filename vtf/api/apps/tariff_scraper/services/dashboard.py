"""Village price health rollup for the admin monitoring dashboard.

Read-only aggregation over signals the scraper already writes
(``PriceSnapshot``, ``FormatChangeLog``, ``VillageTarif``, ``TariffApproval``).
No new scraping logic — this only rolls up what already exists so the
client gets one "global vision" page instead of hunting through four
separate change lists.

Design note: computed on every request (32 villages, cheap aggregate
queries — see ``compute_village_health`` for the query shape). If this
ever needs to scale past a few hundred villages, cache the result for
a minute or two rather than adding a new model.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db.models import Count, Max
from django.utils import timezone

from apps.catalog.models import Village
from apps.tariff_scraper.models import (
    CHANGE_TYPE_HARD_FAILURE,
    CHANGE_TYPE_PARSE_FAILURE,
    CHANGE_TYPE_ZERO_PRICES,
    STATUS_PENDING,
    FormatChangeLog,
    PriceSnapshot,
    TariffApproval,
    VillageTarif,
)

_STEP_ERROR_RE = re.compile(
    r"^(?P<step>Step\s+\d+\s*\([^)]+\))\s*\|\s*"
    r"(?P<source>[^|]+?)\s*\|\s*"
    r"(?P<reason>.+)$",
    re.DOTALL,
)


def _parse_pipeline_error(error: Any) -> dict[str, str]:
    text = str(error).strip()
    match = _STEP_ERROR_RE.match(text)
    if match:
        return {
            "step": match.group("step").strip(),
            "source": match.group("source").strip(),
            "reason": match.group("reason").strip(),
        }
    if " | " in text and "\u2192" in text:
        left, _, right = text.partition(" | ")
        return {
            "step": "Unhandled exception",
            "source": left.strip(),
            "reason": right.strip(),
        }
    return {
        "step": "Unknown step",
        "source": "\u2014",
        "reason": text,
    }


STATUS_GREEN = "green"
STATUS_ORANGE = "orange"
STATUS_MISSING_TARIFFS = "missing_tariffs"
STATUS_RED = "red"

STATUS_LABELS = {
    STATUS_GREEN: "OK",
    STATUS_ORANGE: "Non mise à jour récemment",
    STATUS_MISSING_TARIFFS: "Aucun tarif actif",
    STATUS_RED: "Problème détecté",
}

# How many days without a scrape before a village is flagged orange.
STALE_AFTER = timedelta(days=getattr(settings, "TARIFF_DASHBOARD_STALE_DAYS", 7))

# FormatChangeLog change_types that mean "something is actually broken"
# (as opposed to CHANGE_TYPE_PARTIAL, which your ALERTS.md treats as a
# recoverable warning, not a hard failure).
_RED_CHANGE_TYPES = {
    CHANGE_TYPE_HARD_FAILURE,
    CHANGE_TYPE_ZERO_PRICES,
    CHANGE_TYPE_PARSE_FAILURE,
}


@dataclass
class VillageHealth:
    village_id: str
    village_name: str
    region: str
    status: str  # green | orange | missing_tariffs | red
    reason: str
    last_scraped_at: datetime | None
    active_tarif_count: int
    pending_approvals: int
    error_details: list[dict[str, str]] = field(default_factory=list)


@dataclass
class DashboardSummary:
    rows: list[VillageHealth]
    counts: dict[str, int]
    generated_at: datetime
    stale_after_days: int


def compute_village_health() -> DashboardSummary:
    """One row per village, worst-status-wins.

    Red is reserved for scraper/format failures. Villages with no active
    tariffs are tracked separately so data gaps do not look like scraper
    incidents.
    """
    now = timezone.now()

    last_snapshot = dict(
        PriceSnapshot.objects.values("village_id")
        .annotate(last=Max("scraped_at"))
        .values_list("village_id", "last")
    )

    # Latest FormatChangeLog per village, without relying on DB-specific
    # DISTINCT ON (keeps this portable between Postgres/SQLite).
    last_change: dict[str, FormatChangeLog] = {}
    for log in FormatChangeLog.objects.order_by("village_id", "-detected_at").only(
        "village_id", "change_type", "detected_at", "errors"
    ):
        last_change.setdefault(log.village_id, log)

    active_counts = dict(
        VillageTarif.objects.filter(is_active=True)
        .values_list("village_id")
        .annotate(c=Count("id"))
        .values_list("village_id", "c")
    )

    pending_counts = dict(
        TariffApproval.objects.filter(status=STATUS_PENDING)
        .values_list("village_id")
        .annotate(c=Count("id"))
        .values_list("village_id", "c")
    )

    rows: list[VillageHealth] = []
    for village in Village.objects.all().only("id", "nom", "region"):
        vid = village.id
        scraped_at = last_snapshot.get(vid)
        change = last_change.get(vid)
        active_count = active_counts.get(vid, 0)

        if change is not None and change.change_type in _RED_CHANGE_TYPES:
            status = STATUS_RED
            reason = f"Dernier scrape en échec : {change.get_change_type_display()}."
        elif active_count == 0:
            status = STATUS_MISSING_TARIFFS
            reason = "Aucun tarif actif pour ce village."
        elif scraped_at is None:
            status = STATUS_ORANGE
            reason = "Jamais scrapé."
        elif (now - scraped_at) > STALE_AFTER:
            days = (now - scraped_at).days
            status = STATUS_ORANGE
            reason = f"Pas de scrape depuis {days} jours."
        else:
            status = STATUS_GREEN
            reason = "Prix à jour, aucun problème détecté."

        rows.append(
            VillageHealth(
                village_id=vid,
                village_name=village.nom,
                region=village.region,
                status=status,
                reason=reason,
                last_scraped_at=scraped_at,
                active_tarif_count=active_count,
                pending_approvals=pending_counts.get(vid, 0),
                error_details=[
                    _parse_pipeline_error(e) for e in (change.errors if change else [])
                ],
            )
        )

    order = {
        STATUS_RED: 0,
        STATUS_MISSING_TARIFFS: 1,
        STATUS_ORANGE: 2,
        STATUS_GREEN: 3,
    }
    rows.sort(key=lambda r: (order[r.status], r.village_name))

    counts = {
        STATUS_GREEN: sum(1 for r in rows if r.status == STATUS_GREEN),
        STATUS_ORANGE: sum(1 for r in rows if r.status == STATUS_ORANGE),
        STATUS_MISSING_TARIFFS: sum(
            1 for r in rows if r.status == STATUS_MISSING_TARIFFS
        ),
        STATUS_RED: sum(1 for r in rows if r.status == STATUS_RED),
    }

    return DashboardSummary(
        rows=rows,
        counts=counts,
        generated_at=now,
        stale_after_days=STALE_AFTER.days,
    )

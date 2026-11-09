"""Core scraping pipeline — orchestrates adapters, dedup, and DB persistence.

Called by Celery task_run_scraping_job and the management command.
"""
from __future__ import annotations

import logging
import uuid

from django.utils import timezone as dj_timezone

from apps.scraper.adapters.base import ScrapedActivity
from apps.scraper.adapters.google_places import GooglePlacesAdapter
from apps.scraper.adapters.tripadvisor import TripAdvisorAdapter
from apps.scraper.adapters.ot_local import OfficeTourismeAdapter
from apps.scraper.dedup import (
    create_price_change_alerts,
    deduplicate_candidates,
    find_best_match,
)
from apps.catalog.models import Village, Activity
from apps.scraper.models import ScrapingCandidate, ScrapingImportLog
from apps.scraper.services.admin_helpers import JobCancelled, is_job_cancelled
from apps.scraper.services.filter_rules import get_active_rules, match_rule
from apps.cache_orchestrator.service import CacheOrchestrator
from apps.scraper.dedup import haversine_km

logger = logging.getLogger(__name__)

# Village coordinates (lat, lng) — used when a village has no geo fields
VILLAGE_COORDS: dict[str, tuple[float, float]] = {
    "biarritz":      (43.4832, -1.5586),
    "lacanau":       (44.9737, -1.1977),
    "carcans":       (45.0869, -1.1287),
    "biscarrosse":   (44.3942, -1.1662),
    "bandol":        (43.1362,  5.7524),
    "sainte-maxime": (43.3088,  6.6389),
    "agde":          (43.3108,  3.4749),
    "chamonix":      (45.9237,  6.8694),
    "alpe-dhuez":    (45.0909,  6.0672),
    "doucy":         (45.4868,  6.3856),
    "karellis":      (45.2700,  6.2500),
    "la-plagne":     (45.5095,  6.6755),
    "montgenevre":   (44.9280,  6.7249),
    "le-sauze":      (44.3375,  6.3513),
    "praloup":       (44.3333,  6.5833),
    "arvieux":       (44.7333,  6.7167),
    "savines":       (44.5202,  6.3850),
    "saint-sauves":  (45.6167,  2.9500),
    "metabief":      (46.7683,  6.3467),
    "soultzeren":    (48.0000,  7.0667),
    "font-durle":    (44.9167,  5.3833),
    "bedoin":        (44.1244,  5.1777),
    "cereste":       (43.8500,  5.5833),
    "singleyrac":    (44.7500,  0.8333),
    "joyeuse":       (44.4833,  4.2333),
    "areches":       (45.6869,  6.5664),
    "vernet":        (42.5485,  2.3866),
    "talloires":     (45.8392,  6.2135),
    "montricher-albanne": (45.2280, 6.4030),
    "saint-cast":    (48.6333, -2.2833),
    "blainville":    (49.3333, -1.5167),
    "riec":          (47.8500, -3.7000),
}


def _get_adapter(source_name: str):
    """Instantiate an adapter by source name."""
    adapters = {
        "google_places": GooglePlacesAdapter,
        "tripadvisor": TripAdvisorAdapter,
        "ot_local": OfficeTourismeAdapter,
    }
    cls = adapters.get(source_name)
    return cls() if cls else None


def _resolve_scrape_targets(job) -> list[tuple[str, object | None, str, float, float]]:
    """Return list of (village_id, village_obj, region, lat, lng) for this job."""

    targets: list[tuple[str, object | None, str, float, float]] = []

    if job.target_type == "village" and job.target_id:
        village_id = job.target_id
        village_obj = None
        region = ""
        try:
            village_obj = Village.objects.get(pk=village_id)
            region = village_obj.region
        except Village.DoesNotExist:
            logger.warning("pipeline: village_id=%s not found in DB", village_id)
        lat, lng = VILLAGE_COORDS.get(village_id, (46.0, 2.0))
        targets.append((village_id, village_obj, region, lat, lng))
    elif job.target_type == "region" and job.target_id:
        villages = Village.objects.filter(region=job.target_id).order_by("nom")
        for village_obj in villages:
            lat, lng = VILLAGE_COORDS.get(village_obj.id, (46.0, 2.0))
            targets.append((village_obj.id, village_obj, village_obj.region, lat, lng))
        if not targets:
            logger.warning("pipeline: no villages for region=%s", job.target_id)
    else:
        logger.warning(
            "pipeline: unsupported target_type=%s target_id=%s",
            job.target_type,
            job.target_id,
        )

    return targets


def _normalise_candidate_name(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def _matches_hidden_candidate(
    candidate: ScrapedActivity, hidden_candidates, village_id: str | None
) -> bool:
    candidate_name = _normalise_candidate_name(candidate.nom)
    for hidden in hidden_candidates:
        if hidden.village_id != village_id:
            continue
        if hidden.source != candidate.source:
            continue
        if hidden.source_id and hidden.source_id == candidate.source_id:
            return True
        if _normalise_candidate_name(hidden.nom) != candidate_name:
            continue
        return True
    return False


def _scrape_sources_for_village(
    *,
    job,
    village_id: str,
    lat: float,
    lng: float,
    max_results: int,
    sources_used: list[str],
    ensure_not_cancelled,
) -> tuple[list[ScrapedActivity], dict[str, dict]]:
    """Run configured adapters for one village and return raw activities."""
    raw_candidates: list[ScrapedActivity] = []
    source_stats: dict[str, dict] = {}

    for source_name in sources_used:
        ensure_not_cancelled()
        adapter = _get_adapter(source_name)
        if adapter is None:
            logger.warning("pipeline: unknown source=%s", source_name)
            continue

        try:
            if source_name == "ot_local":
                batch = adapter.search_near(
                    lat=lat,
                    lng=lng,
                    radius_km=job.radius_km,
                    max_results=max_results,
                    village_id=village_id,
                )
            else:
                batch = adapter.search_near(
                    lat=lat,
                    lng=lng,
                    radius_km=job.radius_km,
                    max_results=max_results,
                )
            raw_candidates.extend(batch)
            source_stats[source_name] = {
                "found": len(batch),
                "new": 0,
                "errors": 0,
                "duplicates": 0,
            }
        except Exception as exc:
            logger.warning(
                "pipeline source=%s village=%s error=%s",
                source_name,
                village_id,
                exc,
            )
            source_stats[source_name] = {
                "found": 0,
                "new": 0,
                "errors": 1,
                "duplicates": 0,
            }

    return raw_candidates, source_stats


def run_scraping_job(job) -> dict:
    """Execute a ScrapingJob and persist candidates to DB.

    Args:
        job: ScrapingJob ORM instance (already set to status='running').

    Returns:
        Result summary dict matching the API response shape.
    """
    def _ensure_not_cancelled() -> None:
        job.refresh_from_db()
        if is_job_cancelled(job):
            raise JobCancelled(f"Job {job.id} cancelled")

    max_results = getattr(job, "max_results", None) or 50
    sources_used = job.sources or ["google_places", "tripadvisor", "ot_local"]
    scrape_targets = _resolve_scrape_targets(job)

    raw_candidates: list[ScrapedActivity] = []
    source_stats: dict[str, dict] = {}

    for village_id, village_obj, region, lat, lng in scrape_targets:
        _ensure_not_cancelled()
        batch, stats = _scrape_sources_for_village(
            job=job,
            village_id=village_id,
            lat=lat,
            lng=lng,
            max_results=max_results,
            sources_used=sources_used,
            ensure_not_cancelled=_ensure_not_cancelled,
        )
        raw_candidates.extend(batch)
        for source_name, values in stats.items():
            if source_name not in source_stats:
                source_stats[source_name] = {
                    "found": 0,
                    "new": 0,
                    "errors": 0,
                    "duplicates": 0,
                }
            for key in ("found", "errors"):
                source_stats[source_name][key] += values.get(key, 0)

    candidates = deduplicate_candidates(raw_candidates)

    regions = {region for _, _, region, _, _ in scrape_targets if region}
    if len(regions) == 1:
        existing_activities = list(
            Activity.objects.filter(region=next(iter(regions)))
        )
    elif regions:
        existing_activities = list(Activity.objects.filter(region__in=regions))
    else:
        existing_activities = list(Activity.objects.all())

    existing_candidate_ids = set(
        ScrapingCandidate.objects.values_list("source_id", flat=True)
    )
    hidden_candidates = list(
        ScrapingCandidate.objects.filter(status="hidden").only(
            "source", "source_id", "nom", "village"
        )
    )
    filter_rules = get_active_rules()

    new_count = 0
    duplicate_count = 0
    price_alert_count = 0
    excluded_by_rule_count = 0
    auto_hidden_by_rule_count = 0
    candidate_ids_created: list[str] = []

    primary_village = scrape_targets[0][1] if scrape_targets else None
    primary_region = scrape_targets[0][2] if scrape_targets else ""
    primary_lat = scrape_targets[0][3] if scrape_targets else 46.0
    primary_lng = scrape_targets[0][4] if scrape_targets else 2.0

    for cand in candidates:
        rule_action, matched_rule = match_rule(
            nom=cand.nom,
            region=primary_region,
            source=cand.source,
            type_emoji=getattr(cand, "type_emoji", ""),
            rules=filter_rules,
        )
        if rule_action == "exclude":
            # Matched an "exclude" filter rule (e.g. name contains "hotel"):
            # never persisted, does not count as new/duplicate.
            excluded_by_rule_count += 1
            continue

        if rule_action == "hide":
            # Matched a "hide" filter rule: still persisted (kept for
            # audit/traceability) but created already hidden, so it never
            # shows up in the main review queue and needs no manual action.
            #
            # Guard against re-scraping the same establishment on every run:
            # without this check a brand-new hidden row + audit log entry
            # was created on every run for the same source_id (bug fixed
            # 2026-08-13). Mirrors the duplicate checks used by the normal
            # (non-rule) path below.
            if cand.source_id in existing_candidate_ids or _matches_hidden_candidate(
                cand, hidden_candidates, primary_village.pk if primary_village else None
            ):
                duplicate_count += 1
                if cand.source in source_stats:
                    source_stats[cand.source]["duplicates"] += 1
                continue

            cand_id = f"cand-{uuid.uuid4().hex[:8]}"
            try:
                scraped_distance = getattr(cand, "distance_km", None)
                distance_km = (
                    round(float(scraped_distance), 2)
                    if scraped_distance is not None
                    else _compute_distance(primary_lat, primary_lng, cand.latitude, cand.longitude)
                )
                new_candidate = ScrapingCandidate.objects.create(
                    id=cand_id,
                    job=job,
                    village=primary_village,
                    region=primary_region,
                    source=cand.source,
                    source_url=cand.source_url,
                    source_id=cand.source_id,
                    nom=cand.nom[:128],
                    type_emoji=cand.type_emoji,
                    price_adult=cand.price_adult,
                    price_child=cand.price_child,
                    distance_km=distance_km,
                    rating=cand.rating,
                    review_count=cand.review_count,
                    saisons=cand.saisons,
                    status="hidden",
                    reviewed_by="",
                    edits={"reason": f"Auto-hidden by rule: {matched_rule.name}"},
                )
                ScrapingImportLog.objects.create(
                    job=job,
                    candidate=new_candidate,
                    action="auto_hide",
                    actor="rule-engine",
                    reason=f"Matched filter rule: {matched_rule.name}",
                )
                candidate_ids_created.append(cand_id)
                existing_candidate_ids.add(cand.source_id)
                auto_hidden_by_rule_count += 1
            except Exception as exc:
                logger.warning(
                    "pipeline: failed to create auto-hidden candidate nom=%s err=%s",
                    cand.nom,
                    exc,
                )
            continue

        if _matches_hidden_candidate(
            cand, hidden_candidates, primary_village.pk if primary_village else None
        ):
            duplicate_count += 1
            if cand.source in source_stats:
                source_stats[cand.source]["duplicates"] += 1
            continue

        best_match, confidence = find_best_match(cand, existing_activities)
        matched_code = getattr(best_match, "code", "") if best_match else ""

        if cand.source_id in existing_candidate_ids:
            duplicate_count += 1
            if cand.source in source_stats:
                source_stats[cand.source]["duplicates"] += 1
            price_alert_count += create_price_change_alerts(
                cand,
                best_match,
                confidence=confidence,
            ) if best_match else 0
            continue

        if best_match is not None and confidence >= 0.90:
            price_alert_count += create_price_change_alerts(
                cand,
                best_match,
                confidence=confidence,
            )
            duplicate_count += 1
            if cand.source in source_stats:
                source_stats[cand.source]["duplicates"] += 1
        else:
            new_count += 1
            if cand.source in source_stats:
                source_stats[cand.source]["new"] += 1

        cand_id = f"cand-{uuid.uuid4().hex[:8]}"
        try:
            scraped_distance = getattr(cand, "distance_km", None)
            distance_km = (
                round(float(scraped_distance), 2)
                if scraped_distance is not None
                else _compute_distance(primary_lat, primary_lng, cand.latitude, cand.longitude)
            )
            ScrapingCandidate.objects.create(
                id=cand_id,
                job=job,
                village=primary_village,
                region=primary_region or (getattr(best_match, "region", "") if best_match else ""),
                source=cand.source,
                source_url=cand.source_url,
                source_id=cand.source_id,
                nom=cand.nom[:128],
                type_emoji=cand.type_emoji,
                price_adult=cand.price_adult,
                price_child=cand.price_child,
                distance_km=distance_km,
                rating=cand.rating,
                review_count=cand.review_count,
                saisons=cand.saisons,
                matched_activity_code=matched_code,
                match_confidence=confidence,
                status="new",
            )
            candidate_ids_created.append(cand_id)
            existing_candidate_ids.add(cand.source_id)
        except Exception as exc:
            logger.warning(
                "pipeline: failed to create candidate nom=%s err=%s",
                cand.nom,
                exc,
            )

    result_summary = {
        "totalNew": new_count,
        "totalDuplicates": duplicate_count,
        "totalPriceAlerts": price_alert_count,
        "totalExcludedByRule": excluded_by_rule_count,
        "totalAutoHiddenByRule": auto_hidden_by_rule_count,
        "readyForReview": new_count,
        "sources": source_stats,
        "candidates": candidate_ids_created,
        "villagesScraped": len(scrape_targets),
    }

    logger.info(
        "pipeline done job=%s targets=%d new=%d duplicates=%d price_alerts=%d "
        "excluded_by_rule=%d auto_hidden_by_rule=%d",
        job.id,
        len(scrape_targets),
        new_count,
        duplicate_count,
        price_alert_count,
        excluded_by_rule_count,
        auto_hidden_by_rule_count,
    )

    return result_summary


def import_candidate(candidate, edits: dict | None = None, actor: str = "") -> object:
    """Import a ScrapingCandidate into the Activity catalog.

    Args:
        candidate: ScrapingCandidate ORM instance.
        edits:     Optional field overrides (nom, price_adult, etc.).
        actor:     Username/email of the staff member approving the import.

    Returns:
        The newly created Activity instance.
    """

    edits = edits or {}
    nom = edits.get("nom") or candidate.nom
    price_adult = edits.get("price_adult", candidate.price_adult) or 0
    price_child = edits.get("price_child", candidate.price_child) or 0
    saisons = edits.get("saisons") or candidate.saisons or ["hs", "vs", "ete", "fetes"]
    region = candidate.region or ""

    kind = "paid" if (price_adult or price_child) else "free"
    region_slug = region.split("/")[0].strip().lower().replace(" ", "-")[:8]
    name_slug = nom.lower().replace(" ", "-")[:32]
    name_slug = "".join(c for c in name_slug if c.isalnum() or c == "-")
    code = f"{kind}:{region_slug}:{name_slug}"

    base_code = code
    counter = 1
    while Activity.objects.filter(code=code).exists():
        code = f"{base_code}-{counter}"
        counter += 1

    activity = Activity.objects.create(
        code=code,
        region=region,
        village=candidate.village,
        kind=kind,
        nom=nom,
        type=candidate.type_emoji,
        price_adult=price_adult,
        price_child=price_child,
        saisons=saisons,
    )

    candidate.status = "imported"
    candidate.reviewed_by = actor
    candidate.reviewed_at = dj_timezone.now()
    candidate.edits = edits if edits else None
    candidate.save(update_fields=["status", "reviewed_by", "reviewed_at", "edits"])

    ScrapingImportLog.objects.create(
        job=candidate.job,
        candidate=candidate,
        action="import",
        activity=activity,
        edits=edits if edits else None,
        actor=actor,
    )

    if region:
        try:
            CacheOrchestrator.rebuild(
                scope=f"regions:{region}",
                reason=f"Imported activity: {nom}",
                triggered_by=f"scraper:import:{actor}",
            )
        except Exception:
            pass

    logger.info(
        "import_candidate: imported activity code=%s nom=%s actor=%s",
        code,
        nom,
        actor,
    )

    return activity


def _compute_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Compute haversine distance in km, safe for zero coords."""
    if not lat2 or not lng2:
        return 0.0
    return round(haversine_km(lat1, lng1, lat2, lng2), 2)

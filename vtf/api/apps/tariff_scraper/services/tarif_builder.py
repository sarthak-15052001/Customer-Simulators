"""Tarif builder — stages scraped price bands for staff approval.

Takes a VillageScrapeResult and:
  1. Creates PriceSnapshot rows (immutable audit trail).
  2. Builds a pending TariffApproval with proposed date bands + season patch.
  3. Does NOT activate VillageTarif or touch Village.tarifs until approve.

Rules (from design doc §4, §5, §8.3):
  • Skips bands where is_available=False — stored in PriceSnapshot only.
  • Skips bands where scraped_price is None.
  • PC / DP → pricing_type = per_person (weekly), unless the village's
    Village.tarif_unit == "night" (à la carte villages, e.g. Talloires),
    in which case pricing_type = per_person_per_night.
  • LOC     → pricing_type = flat_unit.
  • VillageTarif rows require both dates (proposed_bands only include dated rows).

Season buckets (``Village.tarifs``) are a lossy *fallback* projection of those
dated bands — pricing reads ``VillageTarif`` first and only falls back to the
buckets when no scraped band covers the date. See ``build_season_tarifs_patch``
for why the projection aggregates the way it does.
"""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction

from apps.tariff_scraper.models import (
    PriceSnapshot,
    TariffApproval,
    STATUS_PENDING,
    STATUS_REJECTED,
    PRICING_TYPE_PER_PERSON,
    PRICING_TYPE_FLAT_UNIT,
    PRICING_TYPE_PER_PERSON_PER_NIGHT,
)
from apps.tariff_scraper.services.scraper import VillageScrapeResult, _is_adult_column_header

logger = logging.getLogger("scraper")


@dataclass
class BuildResult:
    village_id: str
    snapshots_created: int = 0
    approval_id: int | None = None
    bands_proposed: int = 0
    # Kept for task/CLI compatibility (always 0 after scrape — applied on approve)
    tarifs_created: int = 0
    tarifs_deactivated: int = 0
    skipped_unavailable: int = 0
    skipped_no_price: int = 0
    skipped_no_dates: int = 0
    errors: list[str] = field(default_factory=list)


def _money(value: Decimal | float | int) -> float | int:
    """Serialize Decimal prices as JSON-friendly numbers."""
    as_float = float(value)
    if as_float.is_integer():
        return int(as_float)
    return round(as_float, 2)


def _merge_season_tarifs(existing: dict | None, patch: dict | None) -> dict:
    """Return the complete Village.tarifs shape after applying a scrape patch."""
    merged: dict = copy.deepcopy(existing) if isinstance(existing, dict) else {}
    if not isinstance(patch, dict):
        return merged
    for formule, seasons in patch.items():
        if not isinstance(seasons, dict):
            continue
        bucket = merged.setdefault(str(formule), {})
        if not isinstance(bucket, dict):
            bucket = {}
            merged[str(formule)] = bucket
        for sk, price in seasons.items():
            bucket[str(sk)] = price
    return merged


def _is_adult_unit(unit_type: str) -> bool:
    """Only adult-priced bands go into the Village.tarifs season buckets.

    Child age-group columns (e.g. "6 à - 11 ans", "2-5 ans") are scraped
    as separate VillageTarif rows but should NOT feed the season fallback
    buckets, which represent the adult base rate used as a pricing fallback.
    """
    if not unit_type:
        return True  # legacy bands with no unit_type are adult
    return _is_adult_column_header(unit_type)


def _open_season_keys(ouverture: str | None, bands) -> set[str] | None:
    """Season keys the village is actually open in, or None when undecidable.

    A season bucket is only meaningful for a village that is open on at least
    one day of that season. Arêches (``ouverture`` = "5/06–12/09/26") carried a
    ``fetes`` price of 728 € — a phantom for a village that shuts on 12 Sept.
    The pricing view gates on ``is_village_ouvert`` before quoting, but every
    other reader of ``Village.tarifs`` (min-price teasers, reco ranking,
    fixture exports) sees the phantom and treats it as real.

    Returns ``None`` — meaning "do not gate" — when ``ouverture`` is missing or
    unparseable, or when no band carries a date. Failing open is deliberate:
    a bad ouverture string must never silently delete a curated price.
    """
    from apps.pricing.services.calendar import is_village_ouvert, saison_key

    if not ouverture:
        return None

    band_years = {b.date_start.year for b in bands if getattr(b, "date_start", None)}
    if not band_years:
        return None

    # One full calendar year of the scrape covers every season window,
    # including `fetes`, which straddles New Year (20 Dec–6 Jan) and is
    # therefore present at both ends of the same year.
    year = min(band_years)
    cursor = date(year, 1, 1)
    end = date(year, 12, 31)
    open_keys: set[str] = set()
    while cursor <= end:
        if is_village_ouvert(ouverture, cursor):
            open_keys.add(saison_key(cursor))
        cursor += timedelta(days=1)

    # An ouverture we could not parse into any open day is an ouverture we do
    # not understand — treat it as no information rather than "closed all year".
    return open_keys or None


def build_season_tarifs_patch(
    bands,
    existing_tarifs: dict | None = None,  # accepted but deliberately unused, see below
    ouverture: str | None = None,
) -> dict:
    """Map dated priced bands → ``Village.tarifs`` season-bucket patch.

    Season keys come from ``saison_key(date_start)`` (hs / vs / ete / fetes).
    Returns only what this scrape saw — merging with the current tarifs is
    ``build_season_tarifs_proposal``'s job.

    Why the aggregation is what it is
    ---------------------------------
    VTF prices on named *date bands*, not on these four season keys, and a
    single season routinely swallows several bands at different prices. The
    Arêches grille puts five sub-ranges inside ``ete`` alone: 476 (shoulder,
    29/08–19/09), 532, 637 and 728 (peak, 25/07–15/08).

    The previous code took the *first* band seen per season (``setdefault``).
    Grille rows are emitted top-to-bottom, and the top row is the cheap
    "Hors vacances" row — so ``ete`` was claimed by the 29/08 shoulder at
    476 € and the 728 € peak never landed anywhere. A peak week quoted off
    that bucket came out 35 % under the price the booking funnel charges.

    So, per season:
      • PC / DP → the **peak** (max) band. One bucket cannot represent four
        prices; quoting the highest is the only direction that fails safe,
        and the exact per-date price is available from the dated
        ``VillageTarif`` rows anyway (``_resolve_base_tarif`` prefers them).
      • LOC     → peak **within** each unit type, then the **cheapest** unit
        type. LOC buckets are an "à partir de" figure across room types, so
        the cheapest unit is intended; taking the cheapest *date band* on top
        of that was not, and collapsed the season onto its shoulder week.

    ``ouverture`` gates which seasons may appear at all — see
    ``_open_season_keys``.

    Known residuals (accepted, not fixed here)
    ------------------------------------------
    Taking the peak means a *shoulder* week resolved from the bucket is now
    quoted high — Arêches 20–27/06 is ``ete`` to ``saison_key`` but "Hors
    vacances" (476 €) on the grille, and the bucket says 728 €. That only
    bites villages with no active ``VillageTarif`` rows, and over-quoting a
    stay VTF sells cheaper is recoverable in a way that under-quoting a stay
    VTF sells dearer is not.

    The boundaries themselves are still approximate: ``saison_key`` hardcodes
    ``ete`` as 20/06–01/09 and ``vs`` as three fixed school-holiday windows,
    while each village's grille names its own dates (Arêches: Été = 4/07–29/08)
    and French school zones differ. Fixing that means pricing off date bands
    everywhere and retiring the four-key fallback, not re-tuning the constants.
    """
    from apps.pricing.services.calendar import saison_key

    # `existing_tarifs` is intentionally not read. It used to restrict the patch
    # to season keys already present in `Village.tarifs`, which let hand-seeded
    # fixture data veto a scraped price — a village whose grille grew a December
    # band could never gain a `fetes` bucket. A band exists because the page
    # quotes that price on those dates, so it outranks the fixture. The
    # parameter stays in the signature because callers pass it positionally and
    # its removal would silently shift `ouverture` into its place.
    open_seasons = _open_season_keys(ouverture, bands)

    # formule → season → unit_type → peak price for that unit in that season
    peaks: dict[str, dict[str, dict[str, Decimal]]] = {}
    for band in bands:
        # Include genuine 0 € (Gratuit) — exclude only missing prices (PS-08)
        if not band.is_available or band.scraped_price is None:
            continue
        if band.date_start is None:
            continue
        # Child age-group bands are scraped as VillageTarif rows but should NOT
        # feed the season fallback buckets (adult base rate only). See _is_adult_unit.
        if not _is_adult_unit(getattr(band, "unit_type", "")):
            continue
        sk = saison_key(band.date_start)
        if open_seasons is not None and sk not in open_seasons:
            continue
        by_unit = peaks.setdefault(band.formule, {}).setdefault(sk, {})
        unit = band.unit_type or ""
        prev = by_unit.get(unit)
        if prev is None or band.scraped_price > prev:
            by_unit[unit] = band.scraped_price

    patch: dict[str, dict[str, float | int]] = {}
    for formule, seasons in peaks.items():
        bucket: dict[str, float | int] = {}
        for sk, by_unit in seasons.items():
            if not by_unit:
                continue
            price = min(by_unit.values()) if formule == "LOC" else max(by_unit.values())
            bucket[sk] = _money(price)
        if bucket:
            patch[formule] = bucket
    return patch


def build_season_tarifs_proposal(
    bands,
    existing_tarifs: dict | None = None,
    ouverture: str | None = None,
) -> tuple[dict, dict]:
    """Return ``(proposed_season_tarifs, notes)`` for a scrape.

    ``proposed_season_tarifs`` is the complete ``Village.tarifs`` shape the
    approval would apply. ``notes`` records what in it the scrape could *not*
    stand behind, so the review screen stops presenting stale fixture numbers
    with the same authority as freshly scraped ones:

      ``unverified``    — kept from the current tarifs because this scrape
                          produced no band for that season. Arêches proposal
                          #94 showed ``PC {hs, vs, ete, fetes}`` looking fully
                          refreshed while only ``hs`` and ``ete`` were scraped;
                          ``vs`` and ``fetes`` were seed data from 2026.
      ``dropped_closed`` — removed because the village is closed for the whole
                          season (see ``_open_season_keys``). The old value is
                          kept in the note, and ``previous_village_tarifs``
                          still snapshots the full prior state, so an approval
                          made on a stale ouverture string stays reversible.
    """
    patch = build_season_tarifs_patch(bands, existing_tarifs, ouverture)
    merged = _merge_season_tarifs(existing_tarifs, patch)
    open_seasons = _open_season_keys(ouverture, bands)

    unverified: list[dict] = []
    dropped: list[dict] = []
    for formule in sorted(merged):
        seasons = merged.get(formule)
        if not isinstance(seasons, dict):
            continue
        scraped_keys = set((patch.get(formule) or {}).keys())
        for sk in sorted(seasons):
            if sk in scraped_keys:
                continue
            entry = {"formule": formule, "season": sk, "price": seasons[sk]}
            if open_seasons is not None and sk not in open_seasons:
                dropped.append(entry)
            else:
                unverified.append(entry)

    for entry in dropped:
        merged[entry["formule"]].pop(entry["season"], None)
    # Drop formules left with no seasons at all, so the shape stays clean.
    merged = {f: s for f, s in merged.items() if s}

    return merged, {"unverified": unverified, "dropped_closed": dropped}


def build_tarifs_from_scrape(scrape: VillageScrapeResult) -> BuildResult:
    """Persist snapshots + a pending TariffApproval (no live pricing yet)."""
    result = BuildResult(village_id=scrape.village_id)
    existing_tarifs: dict = {}
    ouverture: str = ""

    try:
        from apps.catalog.models import Village

        village = (
            Village.objects.filter(pk=scrape.village_id)
            .only("id", "tarifs", "ouverture", "tarif_unit")
            .first()
        )
        if village is None:
            msg = (
                f"Unknown catalog village_id '{scrape.village_id}'. "
                "VILLAGE_URLS keys must match Village.pk."
            )
            logger.error("build_tarifs_from_scrape: %s", msg)
            result.errors.append(msg)
            return result
        existing_tarifs = village.tarifs or {}
        ouverture = village.ouverture or ""
        # Per-village PC/DP unit: "night" villages (à la carte, e.g.
        # Talloires — no weekly grid) must classify PC/DP bands as
        # per-person-per-night rather than the per-week default, or the
        # pricing engine will treat scraped nightly prices as already-weekly
        # figures. See Village.tarif_unit for details.
        is_nightly_village = getattr(village, "tarif_unit", "week") == "night"
    except Exception as exc:
        result.errors.append(f"Village lookup failed: {exc}")
        return result

    snapshots_to_create: list[PriceSnapshot] = []
    proposed_bands: list[dict] = []
    seen_proposals: set[tuple] = set()

    for band in scrape.bands:
        snapshot = PriceSnapshot(
            village_id=scrape.village_id,
            formule=band.formule,
            source_page=band.source_page,
            date_label=band.date_label,
            date_start=band.date_start,
            date_end=band.date_end,
            unit_type=band.unit_type or "",
            nb_adults=band.nb_adults,
            scraped_price=band.scraped_price,
            is_available=band.is_available,
            derivation=getattr(band, "derivation", "scraped") or "scraped",
            raw_cell_text=getattr(band, "raw_cell_text", "") or "",
            scrape_source=getattr(band, "scrape_source", "") or "summer",
        )
        snapshots_to_create.append(snapshot)

        if not band.is_available:
            result.skipped_unavailable += 1
            continue

        if band.scraped_price is None:
            result.skipped_no_price += 1
            continue

        if band.date_start is None or band.date_end is None:
            result.skipped_no_dates += 1
            continue

        if band.formule == "LOC":
            pricing_type = PRICING_TYPE_FLAT_UNIT
        elif is_nightly_village:
            pricing_type = PRICING_TYPE_PER_PERSON_PER_NIGHT
        else:
            pricing_type = PRICING_TYPE_PER_PERSON
        proposal_key = (
            band.formule,
            band.date_start,
            band.date_end,
            pricing_type,
            band.unit_type or "",
            band.scraped_price,
            getattr(band, "scrape_source", "") or "summer",
        )
        if proposal_key in seen_proposals:
            continue
        seen_proposals.add(proposal_key)

        proposed_bands.append({
            "formule": band.formule,
            "date_start": band.date_start.isoformat(),
            "date_end": band.date_end.isoformat(),
            "pricing_type": pricing_type,
            "unit_type": band.unit_type or "",
            "price": _money(band.scraped_price),
            "source_page": band.source_page,
            "date_label": band.date_label or "",
            "derivation": getattr(band, "derivation", "scraped") or "scraped",
            # Exact page text this band was parsed from, e.g. "Gratuit*",
            # "581 €", or "" for a blank cell — audit only, same as
            # PriceSnapshot.raw_cell_text. `price` above is still what gets
            # activated into VillageTarif and used by calculations.
            "raw_cell_text": getattr(band, "raw_cell_text", "") or "",
            # Which product URL season this band came from ("summer" |
            # "winter") — dual-season villages only; defaults to "summer"
            # everywhere else. Distinct from `source_page` (the scrape tier).
            "scrape_source": getattr(band, "scrape_source", "") or "summer",
            # Linked after bulk_create via index into created_snapshots
            "_snapshot_idx": len(snapshots_to_create) - 1,
        })

    proposed_season_tarifs, season_tarifs_notes = build_season_tarifs_proposal(
        scrape.bands, existing_tarifs, ouverture
    )

    try:
        with transaction.atomic():
            created_snapshots = PriceSnapshot.objects.bulk_create(snapshots_to_create)
            result.snapshots_created = len(created_snapshots)

            # Resolve snapshot PKs onto proposed bands for approve-time linking
            bands_for_approval: list[dict] = []
            for spec in proposed_bands:
                snap = created_snapshots[spec["_snapshot_idx"]]
                row = {k: v for k, v in spec.items() if k != "_snapshot_idx"}
                row["source_snapshot_id"] = snap.pk
                bands_for_approval.append(row)

            # Newer scrape supersedes any still-pending proposal for this village
            TariffApproval.objects.filter(
                village_id=scrape.village_id,
                status=STATUS_PENDING,
            ).update(
                status=STATUS_REJECTED,
                reject_reason="Superseded by a newer scrape.",
            )

            approval = TariffApproval.objects.create(
                village_id=scrape.village_id,
                status=STATUS_PENDING,
                source_url=scrape.url or "",
                proposed_bands=bands_for_approval,
                proposed_season_tarifs=proposed_season_tarifs,
                season_tarifs_notes=season_tarifs_notes,
                bands_count=len(bands_for_approval),
            )
            result.approval_id = approval.pk
            result.bands_proposed = len(bands_for_approval)

    except Exception as exc:
        logger.exception(
            "build_tarifs_from_scrape: DB write failed for %s", scrape.village_id
        )
        result.errors.append(str(exc))

    logger.info(
        "build_tarifs: village=%s snapshots=%d approval_id=%s bands_proposed=%d "
        "skip_unavail=%d skip_no_price=%d skip_no_dates=%d "
        "season_unverified=%d season_dropped_closed=%d",
        scrape.village_id,
        result.snapshots_created,
        result.approval_id,
        result.bands_proposed,
        result.skipped_unavailable,
        result.skipped_no_price,
        result.skipped_no_dates,
        len(season_tarifs_notes.get("unverified") or []),
        len(season_tarifs_notes.get("dropped_closed") or []),
    )
    return result

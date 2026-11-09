"""Apply or reject pending TariffApproval proposals.

On approve:
  1. Activate VillageTarif rows from ``proposed_bands``.
  2. Merge ``proposed_season_tarifs`` into ``Village.tarifs`` (pricing fallback),
     then replay the deletions recorded in ``season_tarifs_notes``.
  3. Best-effort sync of ``catalog/fixtures/villages.json`` for the same village.

``revert_tariff_approval`` undoes all three for an already-approved proposal.
"""
from __future__ import annotations

import copy
import json
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.db import transaction
from django.db.models import Min
from django.utils import timezone

from apps.tariff_scraper.models import (
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUS_REVERTED,
    TariffApproval,
    VillageTarif,
)

logger = logging.getLogger("scraper")

VILLAGES_FIXTURE = (
    Path(__file__).resolve().parents[2] / "catalog" / "fixtures" / "villages.json"
)


class ApprovalError(Exception):
    """Raised when an approval action cannot proceed."""


def merge_season_tarifs(existing: dict | None, patch: dict | None) -> dict:
    """Deep-merge season-bucket patch into Village.tarifs shape."""
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
            try:
                as_float = float(price)
            except (TypeError, ValueError):
                continue
            bucket[str(sk)] = int(as_float) if as_float.is_integer() else round(as_float, 2)
    return merged


def drop_closed_season_tarifs(tarifs: dict, notes: dict | None) -> dict:
    """Remove season buckets the builder flagged as closed-all-season.

    ``merge_season_tarifs`` can only ever add or overwrite keys, so a bucket
    the builder decided to delete (e.g. a ``fetes`` price on a village that
    shuts in September) would silently reappear at approve time. Deletion is
    therefore replayed here from ``season_tarifs_notes``.

    Re-merging rather than assigning ``proposed_season_tarifs`` wholesale is
    deliberate: the proposal is built at scrape time and approved later, so a
    manual edit made to ``Village.tarifs`` in between must survive. Only the
    keys explicitly listed as dropped are removed.
    """
    if not isinstance(notes, dict):
        return tarifs
    for entry in notes.get("dropped_closed") or []:
        if not isinstance(entry, dict):
            continue
        bucket = tarifs.get(str(entry.get("formule")))
        if isinstance(bucket, dict):
            bucket.pop(str(entry.get("season")), None)
    return {formule: seasons for formule, seasons in tarifs.items() if seasons}


def sync_villages_fixture(village_id: str, tarifs: dict) -> bool:
    """Update ``tarifs`` for ``village_id`` inside villages.json when writable."""
    path = VILLAGES_FIXTURE
    if not path.is_file():
        logger.warning("sync_villages_fixture: fixture missing at %s", path)
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("sync_villages_fixture: read failed: %s", exc)
        return False

    updated = False
    for entry in data:
        if entry.get("model") != "catalog.village":
            continue
        if entry.get("pk") != village_id:
            continue
        fields = entry.setdefault("fields", {})
        fields["tarifs"] = tarifs
        updated = True
        break

    if not updated:
        logger.warning(
            "sync_villages_fixture: village '%s' not found in fixture", village_id
        )
        return False

    try:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("sync_villages_fixture: write failed: %s", exc)
        return False
    return True


def _parse_band_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


@transaction.atomic
def approve_tariff_approval(
    approval: TariffApproval,
    *,
    user=None,
    sync_fixture: bool = True,
) -> TariffApproval:
    """Activate proposed bands and update Village.tarifs."""
    if approval.status != STATUS_PENDING:
        raise ApprovalError(
            f"Approval #{approval.pk} is '{approval.status}', expected '{STATUS_PENDING}'."
        )

    bands = approval.proposed_bands or []
    if not bands:
        raise ApprovalError(f"Approval #{approval.pk} has no proposed_bands.")

    from apps.catalog.models import Village

    village = Village.objects.select_for_update().get(pk=approval.village_id)
    previous = copy.deepcopy(village.tarifs) if village.tarifs else {}

    formules_found = {str(b.get("formule")) for b in bands if b.get("formule")}
    deactivated = 0
    if formules_found:
        deactivated = VillageTarif.objects.filter(
            village_id=approval.village_id,
            formule__in=list(formules_found),
            is_active=True,
        ).update(is_active=False)

    now = timezone.now()
    new_tarifs: list[VillageTarif] = []
    for band in bands:
        try:
            price = Decimal(str(band["price"]))
            date_start = _parse_band_date(band["date_start"])
            date_end = _parse_band_date(band["date_end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ApprovalError(f"Invalid proposed band: {exc}") from exc

        if price < 0:
            continue

        new_tarifs.append(
            VillageTarif(
                village_id=approval.village_id,
                formule=band["formule"],
                date_start=date_start,
                date_end=date_end,
                pricing_type=band.get("pricing_type") or "per_person",
                unit_type=band.get("unit_type") or "",
                price=price,
                source_snapshot_id=band.get("source_snapshot_id"),
                is_active=True,
                # `effective_at` is auto_now_add — passing a value here does
                # nothing, Django overwrites it on insert. Kept out on purpose
                # so nothing downstream keys on it matching `reviewed_at`;
                # `revert_tariff_approval` uses source_snapshot_id instead.
            )
        )

    VillageTarif.objects.bulk_create(new_tarifs)

    merged = merge_season_tarifs(village.tarifs, approval.proposed_season_tarifs)
    merged = drop_closed_season_tarifs(merged, approval.season_tarifs_notes)
    village.tarifs = merged
    village.save(update_fields=["tarifs"])

    approval.previous_village_tarifs = previous
    approval.status = STATUS_APPROVED
    approval.reviewed_at = now
    approval.reviewed_by = user if getattr(user, "is_authenticated", False) else None
    approval.reject_reason = ""
    approval.save(
        update_fields=[
            "previous_village_tarifs",
            "status",
            "reviewed_at",
            "reviewed_by",
            "reject_reason",
        ]
    )

    if sync_fixture:
        sync_villages_fixture(approval.village_id, merged)

    logger.info(
        "approve_tariff_approval: id=%s village=%s tarifs_created=%d deactivated=%d",
        approval.pk,
        approval.village_id,
        len(new_tarifs),
        deactivated,
    )
    return approval


@transaction.atomic
def revert_tariff_approval(
    approval: TariffApproval,
    *,
    user=None,
    sync_fixture: bool = True,
) -> TariffApproval:
    """Roll back an approved proposal — the exact inverse of ``approve``.

    ``approve`` does three things, so a revert has to undo all three:

      1. it deactivated every active band for the formules it touched,
      2. it created new bands from ``proposed_bands``,
      3. it rewrote ``Village.tarifs`` (merge + closed-season deletions).

    Undoing (3) is just restoring ``previous_village_tarifs``, an exact
    snapshot.

    Undoing (2) keys on ``source_snapshot_id``. That is the only exact link:
    ``VillageTarif.effective_at`` is ``auto_now_add``, so the value ``approve``
    passes is discarded on insert and cannot be matched against
    ``reviewed_at``. Snapshots are created once per scrape, so their ids
    identify this approval's rows and no others.

    Undoing (1) cannot be exact — there is no ``deactivated_at`` column, so
    which rows were live at approve time was never recorded. We re-activate
    the previous *generation*: per formule, the rows sharing the newest
    ``effective_at`` older than this approval's own rows. That is right
    whenever bands arrive one approval at a time, which is how the scrape
    pipeline writes them.

    Refuses to run when a newer approved proposal exists for the same village
    — reverting an older one would silently clobber the newer prices.
    """
    if approval.status != STATUS_APPROVED:
        raise ApprovalError(
            f"Approval #{approval.pk} is '{approval.status}', expected '{STATUS_APPROVED}'."
        )

    bands = approval.proposed_bands or []
    snapshot_ids = [b.get("source_snapshot_id") for b in bands if b.get("source_snapshot_id")]
    if not snapshot_ids:
        raise ApprovalError(
            f"Approval #{approval.pk} has no source_snapshot_id on its bands; "
            "its VillageTarif rows cannot be identified."
        )

    newer = (
        TariffApproval.objects.filter(
            village_id=approval.village_id,
            status=STATUS_APPROVED,
            reviewed_at__gt=approval.reviewed_at,
        )
        .order_by("reviewed_at")
        .first()
        if approval.reviewed_at is not None
        else None
    )
    if newer is not None:
        raise ApprovalError(
            f"Approval #{approval.pk} was superseded by #{newer.pk} "
            f"(approved {newer.reviewed_at:%d/%m/%Y %H:%M}). Revert that one first."
        )

    from apps.catalog.models import Village

    village = Village.objects.select_for_update().get(pk=approval.village_id)

    # (2) — drop the bands this approval activated.
    own = VillageTarif.objects.filter(
        village_id=approval.village_id,
        source_snapshot_id__in=snapshot_ids,
    )
    own_since = own.aggregate(first=Min("effective_at"))["first"]
    deactivated = own.filter(is_active=True).update(is_active=False)

    # (1) — bring back the generation that was live before it.
    formules = {str(b.get("formule")) for b in bands if b.get("formule")}
    reactivated = 0
    if own_since is not None:
        for formule in sorted(formules):
            previous_stamp = (
                VillageTarif.objects.filter(
                    village_id=approval.village_id,
                    formule=formule,
                    effective_at__lt=own_since,
                )
                .order_by("-effective_at")
                .values_list("effective_at", flat=True)
                .first()
            )
            if previous_stamp is None:
                continue
            reactivated += VillageTarif.objects.filter(
                village_id=approval.village_id,
                formule=formule,
                effective_at=previous_stamp,
            ).update(is_active=True)

    # (3) — restore the season buckets exactly as they were.
    restored = copy.deepcopy(approval.previous_village_tarifs) or {}
    village.tarifs = restored
    village.save(update_fields=["tarifs"])

    approval.status = STATUS_REVERTED
    approval.reverted_at = timezone.now()
    approval.reverted_by = user if getattr(user, "is_authenticated", False) else None
    approval.save(update_fields=["status", "reverted_at", "reverted_by"])

    if sync_fixture:
        sync_villages_fixture(approval.village_id, restored)

    logger.info(
        "revert_tariff_approval: id=%s village=%s deactivated=%d reactivated=%d",
        approval.pk,
        approval.village_id,
        deactivated,
        reactivated,
    )
    return approval


@transaction.atomic
def reject_tariff_approval(
    approval: TariffApproval,
    *,
    user=None,
    reason: str = "",
) -> TariffApproval:
    """Mark a pending proposal as rejected (no pricing changes)."""
    if approval.status != STATUS_PENDING:
        raise ApprovalError(
            f"Approval #{approval.pk} is '{approval.status}', expected '{STATUS_PENDING}'."
        )

    approval.status = STATUS_REJECTED
    approval.reject_reason = (reason or "").strip()
    approval.reviewed_at = timezone.now()
    approval.reviewed_by = user if getattr(user, "is_authenticated", False) else None
    approval.save(
        update_fields=["status", "reject_reason", "reviewed_at", "reviewed_by"]
    )
    logger.info(
        "reject_tariff_approval: id=%s village=%s reason=%s",
        approval.pk,
        approval.village_id,
        approval.reject_reason[:80],
    )
    return approval

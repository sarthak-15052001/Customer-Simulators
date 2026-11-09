"""Catalog model fields synced into the TranslationSource table.

``sync_all()`` walks the registered catalog fields, reads the current value
from the database, and creates or updates the matching ``TranslationSource``.
Saving a changed source queues the normal translation task through the
post-save signal.

Coverage: every one of the catalog app's models is represented below, with
every ``CharField``/``TextField`` (human-readable copy) registered. Fields
that hold IDs, slugs, codes, icons, URLs, foreign keys, booleans, numbers
(``IntegerField``/``PositiveSmallIntegerField``/``DecimalField``), dates
(``DateField``/``DateTimeField``), and JSON blobs are intentionally left out
of the registry — those aren't translatable prose, and ``_is_text_field``
below double-checks this at sync time so a field can never be sent to the
LLM by mistake even if the registry is edited incorrectly later.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import models as dj_models
from django.utils.text import slugify

logger = logging.getLogger("translation_manager")

# Field types that hold human-readable prose worth translating. Anything
# else (numbers, dates, booleans, JSON, FKs, slugs/codes/keys) is skipped
# gracefully by sync_field() — never stringified and sent to the LLM.
TRANSLATABLE_FIELD_TYPES = (dj_models.CharField, dj_models.TextField)


@dataclass(frozen=True)
class FieldSpec:
    app_label: str
    model_name: str
    field: str
    source_language: str = "FR"
    group: str = "Catalog"


REGISTRY: list[FieldSpec] = [
    # Village — nom/nom2/ouverture are free text; vtf_department/vtf_city/
    # vtf_slug are technical URL-building identifiers, not display copy —
    # intentionally excluded, same as region/env_code/tarif_unit (choice
    # codes) and every numeric/boolean/date/JSON field on the model.
    FieldSpec("catalog", "Village", "nom", group="Village"),
    FieldSpec("catalog", "Village", "nom2", group="Village"),
    FieldSpec("catalog", "Village", "ouverture", group="Village"),
    # LandingMapZone — name is the only text field; id/villages(JSON) excluded.
    FieldSpec("catalog", "LandingMapZone", "name", group="LandingMapZone"),
    # Formula — code/icon/icon_key are technical; sort_order is numeric.
    FieldSpec("catalog", "Formula", "label", group="Formula"),
    FieldSpec("catalog", "Formula", "short_description", group="Formula"),
    FieldSpec("catalog", "Formula", "include_text", group="Formula"),
    # Attraction — icon/km excluded (technical / numeric).
    FieldSpec("catalog", "Attraction", "nom", group="Attraction"),
    FieldSpec("catalog", "Attraction", "type", group="Attraction"),
    # Activity — code/kind/region are technical codes; price_adult/
    # price_child/saisons(JSON) excluded.
    FieldSpec("catalog", "Activity", "nom", group="Activity"),
    FieldSpec("catalog", "Activity", "type", group="Activity"),
    # Animation — order is numeric.
    FieldSpec("catalog", "Animation", "nom", group="Animation"),
    FieldSpec("catalog", "Animation", "note", group="Animation"),
    # VillageInfra — infra/anim_ete/anim_hiver/anim_hs are JSON, excluded;
    # extras_ete/extras_hiver are free TextFields.
    FieldSpec("catalog", "VillageInfra", "extras_ete", group="VillageInfra"),
    FieldSpec("catalog", "VillageInfra", "extras_hiver", group="VillageInfra"),
    # VillageClubsEte — paques/ete/toussaint are JSON dicts, no plain text
    # field exists on this model — intentionally has zero registry entries.
    # PricingRules — payload is JSON, updated_at/created_at are dates/bools
    # — intentionally has zero registry entries (no translatable copy).
    # Meal — code is a technical PK; price_adult/price_child/order numeric.
    FieldSpec("catalog", "Meal", "label", group="Meal"),
    # FuelOption — key is a technical PK; cost_per_km is a DecimalField.
    FieldSpec("catalog", "FuelOption", "label", group="FuelOption"),
    # Promo — key/icon/tag/kind are technical codes; rate is a DecimalField.
    FieldSpec("catalog", "Promo", "label", group="Promo"),
    FieldSpec("catalog", "Promo", "description", group="Promo"),
    # MarketingSeasons — key/icon technical; default_date/start_date/
    # end_date are DateFields; sort_order numeric.
    FieldSpec("catalog", "MarketingSeasons", "label", group="MarketingSeasons"),
    # MarketingSeasonEnvironment — key/icon technical; order numeric;
    # marketing_season is a FK.
    FieldSpec("catalog", "MarketingSeasonEnvironment", "label", group="MarketingSeasonEnvironment"),
    FieldSpec("catalog", "MarketingSeasonEnvironment", "sub", group="MarketingSeasonEnvironment"),
]


def _make_key(spec: FieldSpec, pk) -> str:
    raw = f"{spec.app_label}-{spec.model_name}-{spec.field}-{pk}"
    return slugify(raw)[:160]


def _is_text_field(model, field_name: str) -> bool:
    """True only for CharField/TextField — never numbers, dates, booleans,
    JSON, or relations. This is the safety net that keeps a mis-registered
    or future-renamed field (e.g. a DateField) from ever being stringified
    and shipped off to the LLM as if it were translatable prose."""
    try:
        field = model._meta.get_field(field_name)
    except Exception:
        logger.warning(
            "registry: %s.%s has no field %r — skipping.",
            model._meta.app_label,
            model.__name__,
            field_name,
        )
        return False
    return isinstance(field, TRANSLATABLE_FIELD_TYPES)


def sync_field(spec: FieldSpec) -> dict:
    """Sync one registered catalog field across every row of its model.

    Non-text fields (numbers, dates, booleans, JSON, FKs) are skipped
    gracefully here rather than raising — they simply add to ``skipped``
    in the summary so a bad registry entry never corrupts data via the LLM.
    """
    from django.apps import apps as django_apps

    from apps.translation_manager.models import TranslationSource

    model = django_apps.get_model(spec.app_label, spec.model_name)
    created = updated = unchanged = skipped = 0

    if not _is_text_field(model, spec.field):
        logger.warning(
            "sync_field: %s.%s.%s is not a CharField/TextField — skipping entire field "
            "(no rows synced, nothing sent to the LLM).",
            spec.app_label,
            spec.model_name,
            spec.field,
        )
        return {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "field_skipped": True}

    for obj in model.objects.all().iterator():
        raw_value = getattr(obj, spec.field, "")

        # Extra per-row guard: even on a text field, gracefully skip a value
        # that isn't actually a string (defensive — e.g. None, or a
        # descriptor returning something unexpected) rather than mangling it
        # through str().
        if raw_value is not None and not isinstance(raw_value, str):
            logger.warning(
                "sync_field: %s.%s.%s pk=%s returned a non-string value (%s) — skipping row.",
                spec.app_label,
                spec.model_name,
                spec.field,
                obj.pk,
                type(raw_value).__name__,
            )
            skipped += 1
            continue

        value = (raw_value or "").strip()
        if not value:
            skipped += 1
            continue

        key = _make_key(spec, obj.pk)
        model_ref = f"{spec.app_label}.{spec.model_name}.{spec.field}"

        try:
            source = TranslationSource.objects.get(key=key)
        except TranslationSource.DoesNotExist:
            TranslationSource.objects.create(
                key=key,
                source_language=spec.source_language,
                source_text=value,
                source_model_ref=model_ref,
                notes=f"Auto-synced from {model_ref} (pk={obj.pk}).",
            )
            created += 1
            continue

        if source.source_text != value or source.source_language != spec.source_language:
            source.source_text = value
            source.source_language = spec.source_language
            source.source_model_ref = model_ref
            source.save()
            updated += 1
        else:
            unchanged += 1

    return {"created": created, "updated": updated, "unchanged": unchanged, "skipped": skipped}


def sync_all() -> dict:
    """Sync every registered catalog field. Safe to run repeatedly."""
    totals = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "fields": len(REGISTRY)}
    by_group: dict[str, dict] = {}
    for spec in REGISTRY:
        try:
            result = sync_field(spec)
        except Exception:
            logger.exception(
                "sync_all: failed for %s.%s.%s", spec.app_label, spec.model_name, spec.field
            )
            continue
        for key in ("created", "updated", "unchanged", "skipped"):
            totals[key] += result[key]
        group_totals = by_group.setdefault(
            spec.group, {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0}
        )
        for key in ("created", "updated", "unchanged", "skipped"):
            group_totals[key] += result[key]
    totals["by_group"] = by_group
    return totals


def group_counts() -> dict[str, int]:
    """Number of registered catalog fields per group, for the admin panel."""
    counts: dict[str, int] = {}
    for spec in REGISTRY:
        counts[spec.group] = counts.get(spec.group, 0) + 1
    return counts

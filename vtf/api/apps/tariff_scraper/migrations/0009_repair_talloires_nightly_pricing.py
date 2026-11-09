# Repair migration.
#
# Migration 0008 reclassified VillageTarif rows for Talloires (PC/DP) from
# "per_person" to "per_person_per_night", but it did not touch
# TariffApproval.proposed_bands, which stores its own denormalized copy of
# each band's pricing_type (JSON) captured at approval time. Those snapshots
# were left stale as "per_person", which is why Talloires PC/DP still showed
# up as weekly pricing in the admin/API after 0008 was applied. This
# migration fixes both VillageTarif (in case 0008 was skipped/rolled back)
# and repairs the stale proposed_bands snapshots on TariffApproval.
from django.db import migrations

NIGHTLY_TYPE = "per_person_per_night"
WEEKLY_TYPE = "per_person"


def _reclassify_proposed_bands(
    approval, target_type: str, *, from_type: str | None = None
) -> bool:
    changed = False
    bands = list(approval.proposed_bands or [])
    for band in bands:
        if not isinstance(band, dict):
            continue
        if band.get("formule") not in {"PC", "DP"}:
            continue
        if band.get("pricing_type") == target_type:
            continue
        if from_type is not None and band.get("pricing_type") != from_type:
            continue
        band["pricing_type"] = target_type
        changed = True
    if changed:
        approval.proposed_bands = bands
    return changed


def mark_talloires_pricing_as_nightly(apps, schema_editor):
    VillageTarif = apps.get_model("tariff_scraper", "VillageTarif")
    TariffApproval = apps.get_model("tariff_scraper", "TariffApproval")

    VillageTarif.objects.filter(
        village_id="talloires",
        formule__in=["PC", "DP"],
    ).update(pricing_type=NIGHTLY_TYPE)

    # Only pending approvals matter here: proposed_bands is read to create
    # VillageTarif rows on approve, so a stale snapshot re-introduces the
    # weekly bug the moment someone approves. Approved/rejected approvals
    # are historical records of what was actually proposed/signed off and
    # must not be rewritten after the fact.
    for approval in TariffApproval.objects.filter(
        village_id="talloires", status="pending"
    ):
        if _reclassify_proposed_bands(approval, NIGHTLY_TYPE):
            approval.save(update_fields=["proposed_bands"])


def revert_talloires_pricing_to_weekly(apps, schema_editor):
    VillageTarif = apps.get_model("tariff_scraper", "VillageTarif")
    TariffApproval = apps.get_model("tariff_scraper", "TariffApproval")

    VillageTarif.objects.filter(
        village_id="talloires",
        formule__in=["PC", "DP"],
        pricing_type=NIGHTLY_TYPE,
    ).update(pricing_type=WEEKLY_TYPE)

    # Mirror the VillageTarif filter above (only rows currently NIGHTLY_TYPE)
    # so this is a true inverse of mark_talloires_pricing_as_nightly instead
    # of forcing every PC/DP band to weekly unconditionally. Still scoped to
    # pending approvals only, for the same audit-trail reason as above.
    for approval in TariffApproval.objects.filter(
        village_id="talloires", status="pending"
    ):
        if _reclassify_proposed_bands(
            approval, WEEKLY_TYPE, from_type=NIGHTLY_TYPE
        ):
            approval.save(update_fields=["proposed_bands"])


class Migration(migrations.Migration):

    dependencies = [
        ("tariff_scraper", "0008_reclassify_talloires_nightly_pricing"),
    ]

    operations = [
        migrations.RunPython(
            mark_talloires_pricing_as_nightly,
            reverse_code=revert_talloires_pricing_to_weekly,
        ),
    ]

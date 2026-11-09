# Data-only follow-up migration.
#
# A schema-only migration named "0007_alter_villagetarif_pricing_type" was
# auto-generated (via `makemigrations`) in place of the originally-provided
# "0007_villagetarif_per_night_pricing_type" migration. That auto-generated
# migration added the new pricing_type choice/max_length but never ran the
# data fix that reclassifies Talloires' existing scraped PC/DP rows from
# "per_person" (weekly) to "per_person_per_night" (nightly). This migration
# runs that data fix on its own.
from django.db import migrations


def mark_talloires_rows_as_nightly(apps, schema_editor):
    VillageTarif = apps.get_model("tariff_scraper", "VillageTarif")
    VillageTarif.objects.filter(
        village_id="talloires",
        formule__in=["PC", "DP"],
        pricing_type="per_person",
    ).update(pricing_type="per_person_per_night")


def revert_talloires_rows(apps, schema_editor):
    VillageTarif = apps.get_model("tariff_scraper", "VillageTarif")
    VillageTarif.objects.filter(
        village_id="talloires",
        formule__in=["PC", "DP"],
        pricing_type="per_person_per_night",
    ).update(pricing_type="per_person")


class Migration(migrations.Migration):

    dependencies = [
        # Replace this with whatever your actual latest applied
        # tariff_scraper migration is named, if different.
        ("tariff_scraper", "0007_alter_villagetarif_pricing_type"),
    ]

    operations = [
        migrations.RunPython(
            mark_talloires_rows_as_nightly,
            reverse_code=revert_talloires_rows,
        ),
    ]

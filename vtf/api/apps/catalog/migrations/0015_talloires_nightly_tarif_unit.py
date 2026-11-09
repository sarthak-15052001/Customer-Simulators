# Data migration companion to 0014_village_tarif_unit.
#
# 0014 only added the Village.tarif_unit column (default="week"); nothing
# ever set it to "night" for Talloires, so tarif_builder.is_nightly_village
# was always False and the pricing repair from
# tariff_scraper/0009_repair_talloires_nightly_pricing.py was silently
# undone on the next scrape (rows reclassified back to per_person). On a
# clean DB the whole chain was a no-op from the start. This migration sets
# the flag so is_nightly_village actually resolves True for Talloires.
from django.db import migrations

NIGHT = "night"
WEEK = "week"


def set_talloires_nightly(apps, schema_editor):
    Village = apps.get_model("catalog", "Village")
    Village.objects.filter(pk="talloires").update(tarif_unit=NIGHT)


def revert_talloires_nightly(apps, schema_editor):
    Village = apps.get_model("catalog", "Village")
    Village.objects.filter(pk="talloires", tarif_unit=NIGHT).update(
        tarif_unit=WEEK
    )


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0014_village_tarif_unit"),
    ]

    operations = [
        migrations.RunPython(
            set_talloires_nightly,
            reverse_code=revert_talloires_nightly,
        ),
    ]

"""Management command: load_vtf_mocks.

Loads all catalog fixtures into the DB in a single transaction.
Safe to re-run (idempotent via upsert). Spec §US-1.7.

Usage:
    python manage.py load_vtf_mocks
    python manage.py load_vtf_mocks --clear   # wipe catalog first
"""
from __future__ import annotations

import logging
from datetime import date

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import (
    Activity,
    Animation,
    Attraction,
    Formula,
    FuelOption,
    LandingMapZone,
    MarketingSeasonEnvironment,
    MarketingSeasons,
    Meal,
    PricingRules,
    Promo,
    Village,
)
from apps.catalog.services.marketing_seasons import roll_season_dates_to_current_year
from apps.cache_orchestrator.signals import post_load_vtf_mocks

logger = logging.getLogger(__name__)


FIXTURES = [
    "pricing_rules",
    "landing_map_zones",
    "villages",
    "formulas",
    "activities",
    "meals",
    "fuel_options",
    "promos",
    "marketing_seasons",
    "marketing_season_environments",
]


class Command(BaseCommand):
    help = (
        "Load all VTF catalog fixtures into the database. "
        "Idempotent — safe to re-run. Uses a single transaction (all-or-nothing)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            default=False,
            help="Wipe catalog tables before loading (useful for a clean reseed).",
        )
        parser.add_argument(
            "--fixture",
            dest="fixture",
            default=None,
            choices=FIXTURES,
            help=(
                "Load only a specific fixture instead of all. "
                "Choices: " + ", ".join(FIXTURES)
            ),
        )

    def handle(self, *args, **options):
        verbosity = options.get("verbosity", 1)

        single = options.get("fixture")
        fixtures_to_load = [single] if single else FIXTURES
        logger.info(
            "catalog_load_vtf_mocks_started fixture=%s clear=%s verbosity=%s",
            single or "all",
            options["clear"],
            verbosity,
        )

        if options["clear"] and not single:
            # --clear only makes sense for a full reload
            self._clear_catalog(verbosity)
        elif options["clear"] and single:
            logger.warning("catalog_load_vtf_mocks_clear_ignored fixture=%s", single)
            self.stdout.write(self.style.WARNING(
                "--clear is ignored when --fixture is set (would wipe unrelated data)."
            ))

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Loading VTF fixture(s): {', '.join(fixtures_to_load)}…"
        ))

        try:
            with transaction.atomic():
                for fixture in fixtures_to_load:
                    call_command(
                        "loaddata",
                        fixture,
                        verbosity=max(0, verbosity - 1),
                    )
                    if verbosity >= 1:
                        self.stdout.write(f"  ✓ {fixture}")
                    logger.info("catalog_load_vtf_mocks_fixture_loaded fixture=%s", fixture)

                # if not single or single in {"formulas", "villages"}:
                #     self._sync_village_formules()
                if not single or single in {"landing_map_zones", "villages"}:
                    self._sync_village_zones()

                if not single or single == "marketing_seasons":
                    self._sync_marketing_season_dates(verbosity)

                if not single:
                    # Full validation only on complete load
                    self._validate(verbosity)
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"Fixture '{single}' loaded successfully."
                    ))

        except Exception as exc:
            logger.exception(
                "catalog_load_vtf_mocks_failed fixture=%s clear=%s",
                single or "all",
                options["clear"],
            )
            self.stderr.write(self.style.ERROR(f"Load failed — rolled back: {exc}"))
            raise SystemExit(1)

        self._invalidate_catalog_cache()

        if verbosity >= 1:
            self.stdout.write(self.style.SUCCESS("All fixtures loaded successfully."))
        logger.info(
            "catalog_load_vtf_mocks_done fixture=%s clear=%s",
            single or "all",
            options["clear"],
        )

    # def _invalidate_catalog_cache(self) -> None:
    #     try:
    #         cache.delete_many([
    #             "vtf:catalog:landing_map",
    #             "vtf:catalog:regions:list",
    #         ])
    #     except Exception as exc:
    #         logger.warning("Could not invalidate catalog cache after fixture load: %s", exc)

    def _invalidate_catalog_cache(self) -> None:
        try:
            post_load_vtf_mocks.send(
                sender=self.__class__,
                reason="load_vtf_mocks completed",
            )
            logger.info("catalog_load_vtf_mocks_cache_rebuild_signal_sent")
        except Exception as exc:
            logger.warning(
                "Could not send post_load_vtf_mocks signal: %s — "
                "falling back to manual key delete",
                exc,
            )
            try:
                cache.delete_many([
                    "vtf:catalog:landing_map",
                    "vtf:catalog:regions:list",
                ])
            except Exception:
                pass

    def _clear_catalog(self, verbosity: int) -> None:
        if verbosity >= 1:
            self.stdout.write(self.style.WARNING("Clearing catalog tables…"))
        logger.warning("catalog_load_vtf_mocks_clearing_catalog_tables")
        with transaction.atomic():
            MarketingSeasonEnvironment.objects.all().delete()
            MarketingSeasons.objects.all().delete()
            Attraction.objects.all().delete()
            Activity.objects.all().delete()
            Animation.objects.all().delete()
            Village.objects.all().delete()
            LandingMapZone.objects.all().delete()
            Meal.objects.all().delete()
            FuelOption.objects.all().delete()
            Promo.objects.all().delete()
            PricingRules.objects.all().delete()
            Formula.objects.all().delete()
        logger.info("catalog_load_vtf_mocks_catalog_tables_cleared")

    def _validate(self, verbosity: int) -> None:
        landing_map_marker_count = sum(
            len(zone.villages or [])
            for zone in LandingMapZone.objects.only("villages")
        )

        counts = {
            "formulas": Formula.objects.count(),
            "landing_map_zones": LandingMapZone.objects.count(),
            "landing_map_markers": landing_map_marker_count,
            "villages": Village.objects.count(),
            "attractions": Attraction.objects.count(),
            "activities": Activity.objects.count(),
            "animations": Animation.objects.count(),
            "meals": Meal.objects.count(),
            "fuels": FuelOption.objects.count(),
            "promos": Promo.objects.count(),
            "marketing_seasons": MarketingSeasons.objects.count(),
            "marketing_season_environments": MarketingSeasonEnvironment.objects.count(),
            "pricing_rules": PricingRules.objects.filter(is_active=True).count(),
        }
        if verbosity >= 1:
            for k, v in counts.items():
                self.stdout.write(f"    {k}: {v}")

        if counts["pricing_rules"] != 1:
            logger.warning("catalog_load_vtf_mocks_validation_warning active_pricing_rules=%d", counts["pricing_rules"])
            self.stderr.write(self.style.WARNING("No active PricingRules found after load."))
        if counts["formulas"] != 3:
            logger.warning("catalog_load_vtf_mocks_validation_warning formulas=%d expected=3", counts["formulas"])
            self.stderr.write(self.style.WARNING(f"Expected 3 formulas, got {counts['formulas']}."))
        if counts["landing_map_zones"] != 13:
            logger.warning(
                "catalog_load_vtf_mocks_validation_warning landing_map_zones=%d expected=13",
                counts["landing_map_zones"],
            )
            self.stderr.write(self.style.WARNING(
                f"Expected 13 landing map zones, got {counts['landing_map_zones']}."
            ))
        if counts["landing_map_markers"] != 30:
            logger.warning(
                "catalog_load_vtf_mocks_validation_warning landing_map_markers=%d expected=30",
                counts["landing_map_markers"],
            )
            self.stderr.write(self.style.WARNING(
                f"Expected 30 landing map markers, got {counts['landing_map_markers']}."
            ))
        # villages_without_formules = Village.objects.filter(formules=[]).count()
        # if villages_without_formules:
        #     self.stderr.write(self.style.WARNING(
        #         f"Villages without formules after sync: {villages_without_formules}."
        #     ))

        # formules is now M2M — check via formula_objects relation.
        villages_without_formules = Village.objects.filter(formula_objects__isnull=True).count()
        if villages_without_formules:
            logger.warning(
                "catalog_load_vtf_mocks_validation_warning villages_without_formulas=%d",
                villages_without_formules,
            )
            self.stderr.write(self.style.WARNING(
                f"Villages without any formula (M2M) after load: {villages_without_formules}."
            ))
        if counts["meals"] != 4:
            logger.warning("catalog_load_vtf_mocks_validation_warning meals=%d expected=4", counts["meals"])
            self.stderr.write(self.style.WARNING(f"Expected 4 meals, got {counts['meals']}."))
        if counts["fuels"] < 1:
            logger.warning("catalog_load_vtf_mocks_validation_warning fuels=%d expected>=1", counts["fuels"])
            self.stderr.write(self.style.WARNING(f"No fuels loaded — expected at least 1."))
        if counts["marketing_seasons"] != 4:
            logger.warning(
                "catalog_load_vtf_mocks_validation_warning marketing_seasons=%d expected=4",
                counts["marketing_seasons"],
            )
            self.stderr.write(self.style.WARNING(
                f"Expected 4 marketing seasons, got {counts['marketing_seasons']}."
            ))
        if counts["marketing_season_environments"] != 13:
            logger.warning(
                "catalog_load_vtf_mocks_validation_warning marketing_season_environments=%d expected=13",
                counts["marketing_season_environments"],
            )
            self.stderr.write(self.style.WARNING(
                "Expected 13 marketing season environments, got "
                f"{counts['marketing_season_environments']}."
            ))

        missing_slugs = Village.objects.filter(vtf_slug="").values_list("id", flat=True)
        if missing_slugs:
            missing_slug_ids = list(missing_slugs)
            logger.warning(
                "catalog_load_vtf_mocks_validation_warning missing_slugs=%d ids=%s",
                len(missing_slug_ids),
                missing_slug_ids[:10],
            )
            self.stderr.write(self.style.WARNING(
                f"Villages missing vtf_slug ({len(missing_slug_ids)}): "
                + ", ".join(missing_slug_ids[:10])
            ))
        logger.info("catalog_load_vtf_mocks_validation_done counts=%s", counts)

    def _sync_village_zones(self) -> None:
        Village.objects.update(zone_id=None)
        synced = 0
        for zone in LandingMapZone.objects.only("id", "villages"):
            village_ids = [
                marker.get("villageId")
                for marker in (zone.villages or [])
                if marker.get("villageId")
            ]
            synced += Village.objects.filter(pk__in=village_ids).update(zone_id=zone.id)
        logger.info("catalog_load_vtf_mocks_zones_synced villages=%d", synced)


    def _sync_marketing_season_dates(self, verbosity: int = 1) -> None:
        """Roll each season's stored dates forward to the current real year.
 
        The fixture stores month/day patterns anchored to a fixed reference
        year (2000, or 2000-2001 for winter). Re-running this command (e.g.
        via a cron/CI reseed job) keeps `start_date` / `end_date` /
        `default_date` correct without ever editing the fixture's year by
        hand. See apps/catalog/services/marketing_seasons.py — the same
        algorithm also powers MarketingSeasonsView and the cache-warming
        job, so DB rows, the live API, and the warmed cache never drift
        from one another.
        """
        today = date.today()
        rolled = 0
        for season in MarketingSeasons.objects.all():
            new_start, new_end, new_default = roll_season_dates_to_current_year(
                season.start_date, season.end_date, today
            )
            if (
                season.start_date != new_start
                or season.end_date != new_end
                or season.default_date != new_default
            ):
                MarketingSeasons.objects.filter(pk=season.pk).update(
                    start_date=new_start,
                    end_date=new_end,
                    default_date=new_default,
                )
                rolled += 1
        if verbosity >= 1:
            self.stdout.write(f"  ✓ marketing_seasons dates rolled to {today.year}")
        logger.info(
            "catalog_load_vtf_mocks_seasons_rolled year=%d rolled=%d", today.year, rolled
        )

    # def _sync_village_formules(self) -> None:
    #     from apps.catalog.models import Formula, Village

    #     by_village: dict[str, list[str]] = {}
    #     formulas = Formula.objects.prefetch_related("villages").order_by(
    #         "sort_order",
    #         "code",
    #     )
    #     for formula in formulas:
    #         for village_id in formula.villages.values_list("id", flat=True):
    #             by_village.setdefault(village_id, []).append(formula.code)

    #     for village in Village.objects.only("id", "formules"):
    #         Village.objects.filter(pk=village.pk).update(
    #             formules=by_village.get(village.id, [])
    #         )

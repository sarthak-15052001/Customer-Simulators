"""Catalog ORM models.

Source of truth: vtf/api/docs/03-data-models.md (catalog section).
Underlying data: vtf/front/src/mocks/* and vtf/front/src/data/*.

Conventions (CLAUDE.md):
  - DB columns: snake_case.
  - Money fields: integer euros (rounding handled by services).
  - tarifs blob kept as JSONField (8 numbers per village, mirrors source mock).
"""
from __future__ import annotations

from django.db import models
from common.enums import Region, Saison, Formule, EnvCode


class Village(models.Model):
    """A VTF holiday resort. 32 entries today (May 2026).

    Source: vtf/front/src/mocks/vtfStay.mock.json
    """

    id = models.SlugField(primary_key=True, max_length=64)
    nom = models.CharField(max_length=128)
    nom2 = models.CharField(max_length=128, blank=True, default="")
    region = models.CharField(max_length=64, choices=Region.choices)
    zone = models.ForeignKey(
        "LandingMapZone",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="catalog_villages",
    )

    env_emoji = models.CharField(max_length=8)
    env_code = models.CharField(max_length=16, choices=EnvCode.choices)

    # formules = models.JSONField(default=list, blank=True)
    has_loc = models.BooleanField()
    ski = models.BooleanField()
    ouverture = models.CharField(max_length=256, blank=True, default="")
    tarifs = models.JSONField()
    # "week" (default): tarifs values are weekly PC/DP prices ("Séjour
    # semaine ... pension complète" on the public page).
    # "night": tarifs values are nightly PC/DP prices ("Tarif par nuit" —
    # à la carte villages with no weekly grid, e.g. Talloires). The pricing
    # engine must multiply these by nights instead of treating them as an
    # already-weekly price.
    tarif_unit = models.CharField(
        max_length=8,
        choices=[("week", "Per week"), ("night", "Per night")],
        default="week",
    )

    bebe_club = models.BooleanField(default=False)
    forfait_rm = models.BooleanField(default=False)
    qf_exc = models.BooleanField(default=False)
    enf_solo_half = models.BooleanField(default=False)

    vtf_department = models.CharField(max_length=64, blank=True, default="")
    vtf_city = models.CharField(max_length=64, blank=True, default="")
    vtf_slug = models.CharField(max_length=128, blank=True, default="")
    vtf_url_verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["region", "nom"]
        indexes = [
            models.Index(fields=["region"]),
            models.Index(fields=["zone"]),
            models.Index(fields=["env_code"]),
            models.Index(fields=["ski"]),
        ]

    def __str__(self) -> str:
        if self.nom2:
            return f"{self.nom} ({self.nom2})"
        return self.nom
    
    @property
    def formules(self) -> list[str]:
        """Derive formule codes from the Formula M2M relation.

        This replaces the old JSONField — Formula.villages is the single source of truth.
        Uses prefetch_related("formula_objects") when available to avoid N+1.
        """
        if hasattr(self, "_prefetched_objects_cache") and "formula_objects" in self._prefetched_objects_cache:
            return sorted(
                {f.code for f in self._prefetched_objects_cache["formula_objects"]},
                key=lambda c: {"PC": 0, "DP": 1, "LOC": 2}.get(c, 99),
            )
        return list(
            self.formula_objects.order_by("sort_order").values_list("code", flat=True)
        )


class LandingMapZone(models.Model):
    """French administrative region and its landing-map markers.

    Marker coordinates use the frontend SVG viewBox: 600px wide by 573px high.
    """

    id = models.PositiveSmallIntegerField(primary_key=True)
    name = models.CharField(max_length=128, unique=True)
    villages = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


class Formula(models.Model):
    """Bookable stay formula metadata (PC, DP, LOC)."""

    code = models.CharField(max_length=8, primary_key=True)
    villages = models.ManyToManyField(
        Village,
        related_name="formula_objects",
        blank=True,
    )
    icon = models.CharField(max_length=8)
    icon_key = models.CharField(max_length=32)
    label = models.CharField(max_length=64)
    short_description = models.CharField(max_length=128)
    include_text = models.TextField(blank=True, default="")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.label}"


class Attraction(models.Model):
    """Nearby landmarks (Mont-Blanc, Calanques, etc.) for a village.

    Source: vtfStay.mock.json:attractionsProches (originally keyed by `nom`,
    re-keyed by `village_id` on load).
    """

    village = models.ForeignKey(
        Village, on_delete=models.CASCADE, related_name="attractions"
    )
    nom = models.CharField(max_length=128)
    type = models.CharField(max_length=128)
    icon = models.CharField(max_length=8)
    km = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["km"]


class Activity(models.Model):
    """Free or paid activity around a region (not bound to a single village).

    Source: vtfExtras.mock.json:actGratuit / activitesPayantes
    """

    KIND_FREE = "free"
    KIND_PAID = "paid"
    KIND_CHOICES = [(KIND_FREE, "Gratuite"), (KIND_PAID, "Payante")]

    code = models.CharField(max_length=64, unique=True)
    region = models.CharField(max_length=64, choices=Region.choices)
    # Activity previously had no FK to Village, only a loose region string.
    village = models.ForeignKey(
        "Village",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
    )
    kind = models.CharField(max_length=4, choices=KIND_CHOICES)
    nom = models.CharField(max_length=128)
    type = models.CharField(max_length=8)
    price_adult = models.PositiveSmallIntegerField(default=0)
    price_child = models.PositiveSmallIntegerField(default=0)
    saisons = models.JSONField(default=list)

    class Meta:
        ordering = ["region", "kind", "nom"]
        indexes = [
            models.Index(fields=["region", "kind"]),
        ]


class Animation(models.Model):
    """Source: vtfExtras.mock.json:vtfAnimations (4 fixed entries)."""

    nom = models.CharField(max_length=128)
    note = models.CharField(max_length=256)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]


class VillageInfra(models.Model):
    """Per-village infrastructure & seasonal animation copy.

    Source: vtfExtras.mock.json:vtfInfra (sparse — only `lacanau` today).
    """

    village = models.OneToOneField(
        Village, on_delete=models.CASCADE, related_name="infra"
    )
    infra = models.JSONField(default=list)
    anim_ete = models.JSONField(default=list)
    anim_hiver = models.JSONField(default=list)
    anim_hs = models.JSONField(default=list)
    extras_ete = models.TextField(blank=True, default="")
    extras_hiver = models.TextField(blank=True, default="")


class VillageClubsEte(models.Model):
    """Source: vtfExtras.mock.json:vtfClubsEte"""

    village = models.OneToOneField(
        Village, on_delete=models.CASCADE, related_name="clubs"
    )
    paques = models.JSONField(default=dict)
    ete = models.JSONField(default=dict)
    toussaint = models.JSONField(default=dict)


class PricingRules(models.Model):
    """Tarif rules used by stay_estimate. One active row at a time.

    Source: vtfPricingRules.mock.json
    """

    updated_at = models.DateField()
    payload = models.JSONField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name="unique_active_pricing_rules",
            ),
        ]
        ordering = ["-created_at"]

    @classmethod
    def active(cls) -> dict | None:
        return (
            cls.objects.filter(is_active=True)
            .values_list("payload", flat=True)
            .first()
        )


class Meal(models.Model):
    """Source: vtf/front/src/data/vtfResto.ts (hardcoded)"""

    code = models.CharField(max_length=16, primary_key=True)
    label = models.CharField(max_length=64)
    price_adult = models.PositiveSmallIntegerField()
    price_child = models.PositiveSmallIntegerField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]


class FuelOption(models.Model):
    """Source: vtf/front/src/data/vtfTransport.ts:VTF_FUELS"""

    key = models.CharField(max_length=16, primary_key=True)
    label = models.CharField(max_length=32)
    cost_per_km = models.DecimalField(max_digits=4, decimal_places=2)


class Promo(models.Model):
    """Catalog of named promos. Eligibility computed at request time by
    apps.pricing.services.promos.available_sejour_promos().

    Source: vtf/front/src/data/vtfPromos.ts:SEJOUR_PROMO_CATALOG
    """

    key = models.CharField(max_length=16, primary_key=True)
    icon = models.CharField(max_length=8)
    label = models.CharField(max_length=64)
    description = models.CharField(max_length=256)
    tag = models.CharField(max_length=16)
    rate = models.DecimalField(max_digits=4, decimal_places=2)
    kind = models.CharField(max_length=8, default="auto")


class MarketingSeasons(models.Model):
    """Marketing seasons for the VTF catalog.
    
    Used to display seasonal promotions and availability information.
    """

    key = models.CharField(max_length=32, primary_key=True)
    label = models.CharField(max_length=64)
    icon = models.CharField(max_length=8)
    default_date = models.DateField()
    start_date = models.DateField()
    end_date = models.DateField()
    sort_order = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["sort_order"]
        verbose_name_plural = "Marketing Seasons"

    def __str__(self) -> str:
        return self.label


class MarketingSeasonEnvironment(models.Model):
    """Environments (funnel options) available for each marketing season.

    Example: the spring season offers Mer, Montagne, Campagne environments.
    Configurable through Django admin instead of hardcoded in views.
    """

    marketing_season = models.ForeignKey(
        MarketingSeasons,
        on_delete=models.CASCADE,
        related_name="environments",
    )
    key = models.CharField(max_length=32)
    icon = models.CharField(max_length=8)
    label = models.CharField(max_length=64)
    sub = models.CharField(max_length=256)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["marketing_season", "order"]
        unique_together = [["marketing_season", "key"]]
        verbose_name_plural = "Marketing Season Environments"

    def __str__(self) -> str:
        return f"{self.marketing_season.label} - {self.label}"

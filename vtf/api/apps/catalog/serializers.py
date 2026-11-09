"""Catalog serializers — camelCase on the wire, snake_case in Python.

Keep field counts small: full village payloads ship through `VillageDetail`,
list views use `VillageList` to keep responses light.
"""
from __future__ import annotations

from rest_framework import serializers

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
    VillageClubsEte,
    VillageInfra,
)
from apps.catalog.services.highlights import get_highlights
from apps.catalog.services.pricing_preview import (
    resolve_formule,
    resolve_nights,
    resolve_per_adult_base_with_fallback,
    village_to_pricing_dict,
)
from apps.pricing.services.calendar import saison_key


class FormulaSerializer(serializers.ModelSerializer):
    iconKey = serializers.CharField(source="icon_key")
    shortDescription = serializers.CharField(source="short_description")
    text = serializers.CharField(source="include_text")
    sortOrder = serializers.IntegerField(source="sort_order")

    class Meta:
        model = Formula
        fields = [
            "code",
            "icon",
            "iconKey",
            "label",
            "shortDescription",
            "text",
            "sortOrder",
        ]


class VillageInfraSerializer(serializers.ModelSerializer):
    """Serializer for VillageInfra with nested anim and extras fields."""

    anim = serializers.SerializerMethodField()
    extras = serializers.SerializerMethodField()

    class Meta:
        model = VillageInfra
        fields = ["infra", "anim", "extras"]

    def get_anim(self, obj: VillageInfra) -> dict:
        """Reorganize animation fields into nested dict by season."""
        return {
            "ete": obj.anim_ete or [],
            "hiver": obj.anim_hiver or [],
            "hs": obj.anim_hs or [],
        }

    def get_extras(self, obj: VillageInfra) -> dict:
        """Reorganize extras fields into nested dict by season."""
        return {
            "ete": obj.extras_ete or "",
            "hiver": obj.extras_hiver or "",
        }


class VillageClubsSerializer(serializers.ModelSerializer):
    """Serializer for VillageClubsEte model."""

    class Meta:
        model = VillageClubsEte
        fields = ["paques", "ete", "toussaint"]


class AttractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attraction
        fields = ["nom", "type", "icon", "km"]


class VillageListSerializer(serializers.ModelSerializer):
    """Lightweight payload for the /villages list endpoint."""

    env = serializers.CharField(source="env_emoji")
    envCode = serializers.CharField(source="env_code")
    hasLoc = serializers.BooleanField(source="has_loc")
    tarifUnit = serializers.CharField(source="tarif_unit")
    zoneId = serializers.IntegerField(source="zone_id", allow_null=True)
    bebeClub = serializers.BooleanField(source="bebe_club")
    forfaitRM = serializers.BooleanField(source="forfait_rm")
    qfExc = serializers.BooleanField(source="qf_exc")
    enfSoloHalf = serializers.BooleanField(source="enf_solo_half")
    infra = serializers.SerializerMethodField()
    clubsInfo = serializers.SerializerMethodField()
    perAdultBase = serializers.SerializerMethodField()
    staySubtotal = serializers.SerializerMethodField()
    saisonKey = serializers.SerializerMethodField()

    class Meta:
        model = Village
        fields = [
            "id",
            "nom",
            "nom2",
            "region",
            "zoneId",
            "env",
            "envCode",
            "formules",
            "hasLoc",
            "ski",
            "ouverture",
            "tarifs",
            "tarifUnit",
            "bebeClub",
            "forfaitRM",
            "qfExc",
            "enfSoloHalf",
            "infra",
            "clubsInfo",
            "perAdultBase",
            "staySubtotal",
            "saisonKey",
        ]

    def to_representation(self, instance):
        """Drop ``staySubtotal`` from the response entirely for PC/DP,
        instead of leaving it in as ``null``. It's only ever a real number
        for LOC (per-accommodation, needs no adult count) — see
        ``get_staySubtotal``'s docstring for why PC/DP can't have one."""
        data = super().to_representation(instance)
        if data.get("staySubtotal") is None:
            data.pop("staySubtotal", None)
        return data

    def get_infra(self, obj: Village) -> dict | None:
        """Include VillageInfra data if it exists."""
        try:
            infra_obj = obj.infra
            serializer = VillageInfraSerializer(infra_obj)
            return serializer.data
        except VillageInfra.DoesNotExist:
            return None

    def get_clubsInfo(self, obj: Village) -> dict | None:
        """Include VillageClubsEte data if it exists."""
        try:
            clubs_obj = obj.clubs
            serializer = VillageClubsSerializer(clubs_obj)
            return serializer.data
        except VillageClubsEte.DoesNotExist:
            return None

    def _pricing_query_context(self) -> tuple[str, "date", dict, int]:
        """Read ``?formule=`` / ``?dateDebut=`` / ``?dateFin=`` once per
        request and cache active pricing rules on the serializer context
        (shared across every row in a list response, avoiding one
        PricingRules query per village)."""
        from datetime import date  # local import to avoid unused top-level import

        request = self.context.get("request")
        params = request.query_params if request is not None else {}
        formule = resolve_formule(params.get("formule"))
        date_debut_raw = params.get("dateDebut")
        # ``dateFin`` = departure date. With dateDebut, derives the stay
        # length perAdultBase is priced for — the same arrival/departure
        # pair the Stay Estimate API already takes, instead of a separate
        # raw nights number. resolve_nights() already resolves the stay
        # date internally (same date.fromisoformat / today fallback as
        # resolve_stay_date), so we use its returned date directly instead
        # of calling resolve_stay_date() a second time.
        stay_date, nights = resolve_nights(
            date_debut_raw=date_debut_raw,
            date_fin_raw=params.get("dateFin"),
        )

        if "_pricing_rules_cache" not in self.context:
            self.context["_pricing_rules_cache"] = PricingRules.active() or {}
        pricing_rules = self.context["_pricing_rules_cache"]

        return formule, stay_date, pricing_rules, nights

    def _resolve_price_and_formule(self, obj: Village) -> tuple[int | None, str | None]:
        """Resolve (price, formuleUsed) once per village per request and
        cache it — perAdultBase and staySubtotal both need this exact same
        lookup, so this avoids running the fallback resolution twice."""
        cache = self.context.setdefault("_price_cache", {})
        if obj.id in cache:
            return cache[obj.id]

        formule, stay_date, pricing_rules, nights = self._pricing_query_context()
        result = resolve_per_adult_base_with_fallback(
            village=village_to_pricing_dict(obj),
            formule=formule,
            stay_date=stay_date,
            pricing_rules=pricing_rules,
            available_formules=list(obj.formules or []),
            nights=nights,
        )
        cache[obj.id] = result
        return result

    def get_perAdultBase(self, obj: Village) -> int | None:
        """Dynamic "starting from" per-adult price for this village.

        Honors ``?formule=PC|DP|LOC`` (default DP), ``?dateDebut=YYYY-MM-DD``
        (default today) and ``?dateFin=YYYY-MM-DD`` (derives nights from the
        arrival/departure pair, default 7 nights if omitted), resolving the
        price the same way the Stay Estimate API does (active scraped tarif
        first, fixture ``tarifs`` fallback, 7-night segment walk for
        multi-week stays).

        If the village doesn't sell the requested/default formule (e.g. a
        LOC-only village asked for the default DP), this automatically
        falls back to whichever formule the village *does* sell (its own
        ``formules`` list), so it shows a real price instead of ``null``.
        """
        price, _formule_used = self._resolve_price_and_formule(obj)
        return price

    def get_staySubtotal(self, obj: Village) -> int | None:
        """Stay subtotal for the resolved formule — LOC only.

        The Stay Estimate API's ``stay_subtotal`` is ``perAdultBase *
        nb_adults`` for PC/DP (plus child-age discounts and a solo-parent
        supplement), which needs a family payload this catalog endpoint
        doesn't receive — there is no village-level "default party size" to
        assume, so PC/DP intentionally returns ``null`` here rather than
        guessing an adult count.

        LOC is different: the tariff is per accommodation, not per person,
        so ``stay_subtotal`` there is exactly ``perAdultBase`` with no
        multiplication or family data needed — see the ``is_loc`` branch in
        ``estimate_sejour_total`` (``total_adults = pb_after``). This
        returns that value only when the resolved formule is LOC (whether
        requested directly, or reached via perAdultBase's own PC→DP→LOC
        fallback for a LOC-only village), and ``null`` otherwise.
        """
        price, formule_used = self._resolve_price_and_formule(obj)
        if formule_used != "LOC":
            return None
        return price

    def get_saisonKey(self, obj: Village) -> str:
        _formule, stay_date, _rules, _nights = self._pricing_query_context()
        return saison_key(stay_date)

class VillageDetailSerializer(VillageListSerializer):
    """Full village payload + nested attractions and highlights."""

    attractionsProches = AttractionSerializer(source="attractions", many=True, read_only=True)
    highlights = serializers.SerializerMethodField()
    vtfDepartment = serializers.CharField(source="vtf_department")
    vtfCity = serializers.CharField(source="vtf_city")
    vtfSlug = serializers.CharField(source="vtf_slug")

    class Meta(VillageListSerializer.Meta):
        fields = [
            *VillageListSerializer.Meta.fields,
            "attractionsProches",
            "highlights",
            "vtfDepartment",
            "vtfCity",
            "vtfSlug",
        ]

    def get_highlights(self, obj: Village) -> list[dict]:
        return get_highlights(obj)


class ActivitySerializer(serializers.ModelSerializer):
    """Outward shape mirrors the TS source: `id, nom, type, ad, enf, saisons`.

    `id` maps to the unique `code` column. For free activities `ad`/`enf` are 0.
    """

    id = serializers.CharField(source="code")
    ad = serializers.IntegerField(source="price_adult")
    enf = serializers.IntegerField(source="price_child")

    class Meta:
        model = Activity
        fields = ["id", "region", "kind", "nom", "type", "ad", "enf", "saisons"]


class AnimationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Animation
        fields = ["nom", "note", "order"]


class MealSerializer(serializers.ModelSerializer):
    """Wire shape mirrors VTF_RESTO_MEALS (id, label, priceAdult, priceChild)."""

    id = serializers.CharField(source="code")
    priceAdult = serializers.IntegerField(source="price_adult")
    priceChild = serializers.IntegerField(source="price_child")

    class Meta:
        model = Meal
        fields = ["id", "label", "priceAdult", "priceChild", "order"]


class FuelOptionSerializer(serializers.ModelSerializer):
    # `coerce_to_string=False` so the wire payload is a JSON number, not a
    # string. Frontend code using `Number(...)` or arithmetic would otherwise
    # silently break or coerce.
    costPerKm = serializers.DecimalField(
        source="cost_per_km",
        max_digits=4,
        decimal_places=2,
        coerce_to_string=False,
    )

    class Meta:
        model = FuelOption
        fields = ["key", "label", "costPerKm"]


class LandingMapZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = LandingMapZone
        fields = ["id", "name"]


class PromoSerializer(serializers.ModelSerializer):
    # Same treatment as `FuelOptionSerializer.costPerKm` — promo rate is used
    # in `1 - rate` arithmetic on the frontend.
    rate = serializers.DecimalField(
        max_digits=4, decimal_places=2, coerce_to_string=False
    )

    class Meta:
        model = Promo
        fields = ["key", "icon", "label", "description", "tag", "rate", "kind"]


class PricingRulesSerializer(serializers.ModelSerializer):
    """Returns the `payload` blob plus the `updatedAt` date."""

    updatedAt = serializers.DateField(source="updated_at")

    class Meta:
        model = PricingRules
        fields = ["updatedAt", "payload"]


class RegionSummarySerializer(serializers.Serializer):
    """{ key, count, freeActivities, paidActivities }."""

    key = serializers.CharField()
    villageCount = serializers.IntegerField()
    freeActivityCount = serializers.IntegerField()
    paidActivityCount = serializers.IntegerField()


class SeasonSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()


class SeasonForDateSerializer(serializers.Serializer):
    saisonKey = serializers.CharField()
    saisonIdx = serializers.IntegerField()


class MarketingSeasonsSerializer(serializers.ModelSerializer):
    """Serializer for marketing seasons with date fields."""

    defaultDate = serializers.DateField(source="default_date", format="%Y-%m-%d")
    startDate = serializers.DateField(source="start_date", format="%Y-%m-%d")
    endDate = serializers.DateField(source="end_date", format="%Y-%m-%d")
    sortOrder = serializers.IntegerField(source="sort_order")

    class Meta:
        model = MarketingSeasons
        fields = ["key", "label", "icon", "defaultDate", "startDate", "endDate", "sortOrder"]


class MarketingSeasonEnvironmentSerializer(serializers.ModelSerializer):
    """Serializer for season-specific environment funnel options."""

    class Meta:
        model = MarketingSeasonEnvironment
        fields = ["key", "icon", "label", "sub"]


class SimulationPdfChildSerializer(serializers.Serializer):
    age = serializers.CharField(max_length=20, trim_whitespace=True)
    discountLabel = serializers.CharField(max_length=120, trim_whitespace=True)
    amount = serializers.CharField(max_length=40, trim_whitespace=True)


class SimulationPdfPlanningSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=("day", "departure"))
    label = serializers.CharField(max_length=80, trim_whitespace=True)
    morning = serializers.CharField(max_length=180, trim_whitespace=True)
    afternoon = serializers.CharField(max_length=180, trim_whitespace=True)
    evening = serializers.CharField(max_length=180, trim_whitespace=True)


class SimulationPdfInputSerializer(serializers.Serializer):
    villageName = serializers.CharField(max_length=160, trim_whitespace=True)
    dateDebut = serializers.CharField(max_length=40, trim_whitespace=True)
    dateFin = serializers.CharField(max_length=40, trim_whitespace=True)
    nuits = serializers.CharField(max_length=20, trim_whitespace=True)
    saison = serializers.CharField(max_length=80, trim_whitespace=True)
    adultes = serializers.CharField(max_length=20, trim_whitespace=True)
    nbEnfants = serializers.CharField(max_length=20, trim_whitespace=True)
    enfantsAges = serializers.CharField(max_length=120, trim_whitespace=True)
    totalEuro = serializers.CharField(max_length=40, trim_whitespace=True)
    perPersonEuro = serializers.CharField(max_length=40, trim_whitespace=True)
    perPersonPerDay = serializers.CharField(max_length=40, trim_whitespace=True)
    perDayFamily = serializers.CharField(max_length=40, trim_whitespace=True)
    formuleLabel = serializers.CharField(max_length=120, trim_whitespace=True)
    perAdultBase = serializers.CharField(max_length=40, trim_whitespace=True)
    totalAdults = serializers.CharField(max_length=40, trim_whitespace=True)
    children = SimulationPdfChildSerializer(many=True, required=False, default=list)
    child1Age = serializers.CharField(max_length=20, trim_whitespace=True, required=False, allow_blank=True)
    child1DiscountLabel = serializers.CharField(max_length=120, trim_whitespace=True, required=False, allow_blank=True)
    child1Amount = serializers.CharField(max_length=40, trim_whitespace=True, required=False, allow_blank=True)
    child2Age = serializers.CharField(max_length=20, trim_whitespace=True, required=False, allow_blank=True)
    child2DiscountLabel = serializers.CharField(max_length=120, trim_whitespace=True, required=False, allow_blank=True)
    child2Amount = serializers.CharField(max_length=40, trim_whitespace=True, required=False, allow_blank=True)
    # Backward-compatible flat children fields.
    child3Age = serializers.CharField(max_length=20, trim_whitespace=True, required=False, allow_blank=True)
    child3DiscountLabel = serializers.CharField(max_length=120, trim_whitespace=True, required=False, allow_blank=True)
    child3Amount = serializers.CharField(max_length=40, trim_whitespace=True, required=False, allow_blank=True)
    child4Age = serializers.CharField(max_length=20, trim_whitespace=True, required=False, allow_blank=True)
    child4DiscountLabel = serializers.CharField(max_length=120, trim_whitespace=True, required=False, allow_blank=True)
    child4Amount = serializers.CharField(max_length=40, trim_whitespace=True, required=False, allow_blank=True)
    totalChildren = serializers.CharField(max_length=40, trim_whitespace=True)
    staySubtotal = serializers.CharField(max_length=40, trim_whitespace=True)
    adhesionEuro = serializers.CharField(max_length=40, trim_whitespace=True)
    stayPackageTotal = serializers.CharField(max_length=40, trim_whitespace=True)
    activitiesTotal = serializers.CharField(max_length=40, trim_whitespace=True)
    restoTotal = serializers.CharField(max_length=40, trim_whitespace=True)
    transportModeLabel = serializers.CharField(max_length=120, trim_whitespace=True)
    transportDetailNote = serializers.CharField(max_length=200, trim_whitespace=True)
    transportTotal = serializers.CharField(max_length=40, trim_whitespace=True)
    formuleIncludesText = serializers.CharField(max_length=500, trim_whitespace=True)
    hotelSavingsEuro = serializers.CharField(max_length=40, trim_whitespace=True)
    savingsPct = serializers.CharField(max_length=40, trim_whitespace=True)
    bookingUrl = serializers.URLField(max_length=500, trim_whitespace=True)
    planning = SimulationPdfPlanningSerializer(many=True, required=False, default=list)
    day1Label = serializers.CharField(max_length=80, trim_whitespace=True, required=False, allow_blank=True)
    day1Morning = serializers.CharField(max_length=180, trim_whitespace=True, required=False, allow_blank=True)
    day1Afternoon = serializers.CharField(max_length=180, trim_whitespace=True, required=False, allow_blank=True)
    day1Evening = serializers.CharField(max_length=180, trim_whitespace=True, required=False, allow_blank=True)
    day2Label = serializers.CharField(max_length=80, trim_whitespace=True, required=False, allow_blank=True)
    day2Morning = serializers.CharField(max_length=180, trim_whitespace=True, required=False, allow_blank=True)
    day2Afternoon = serializers.CharField(max_length=180, trim_whitespace=True, required=False, allow_blank=True)
    day2Evening = serializers.CharField(max_length=180, trim_whitespace=True, required=False, allow_blank=True)
    day3Label = serializers.CharField(max_length=80, trim_whitespace=True, required=False, allow_blank=True)
    day3Morning = serializers.CharField(max_length=180, trim_whitespace=True, required=False, allow_blank=True)
    day3Afternoon = serializers.CharField(max_length=180, trim_whitespace=True, required=False, allow_blank=True)
    day3Evening = serializers.CharField(max_length=180, trim_whitespace=True, required=False, allow_blank=True)
    dayNLabel = serializers.CharField(max_length=80, trim_whitespace=True, required=False, allow_blank=True)
    dayNMorning = serializers.CharField(max_length=180, trim_whitespace=True, required=False, allow_blank=True)
    dayNAfternoon = serializers.CharField(max_length=180, trim_whitespace=True, required=False, allow_blank=True)
    dayNEvening = serializers.CharField(max_length=180, trim_whitespace=True, required=False, allow_blank=True)

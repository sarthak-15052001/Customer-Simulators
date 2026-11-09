"""Pricing serializers — camelCase wire / snake_case Python.

These define the I/O contracts of every POST endpoint in §3.3 of the spec.
Validation here is intentionally lenient: business invariants live in services.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.pricing.services._round import jsround
from common.enums import Formule


class _ChildSerializer(serializers.Serializer):
    age = serializers.IntegerField(min_value=0, max_value=17)


class FamilySerializer(serializers.Serializer):
    adultes = serializers.IntegerField(min_value=1, max_value=6)
    enfants = _ChildSerializer(many=True, required=False, default=list)
    qfVal = serializers.IntegerField(required=False, allow_null=True)
    isSoloParent = serializers.BooleanField(required=False, default=False)
    maxiFamily = serializers.BooleanField(required=False, default=False)


class _ExtrasSerializer(serializers.Serializer):
    locCleaningFee = serializers.IntegerField(required=False, default=0)
    locKits = serializers.IntegerField(required=False, default=0)
    locUnitType = serializers.CharField(required=False, allow_blank=True, default="")   # ← add this


class _ActivitiesSerializer(serializers.Serializer):
    outings = serializers.IntegerField(required=False, default=0)
    priceAdult = serializers.IntegerField(required=False, default=0)
    priceChild = serializers.IntegerField(required=False, default=0)


class _ExtraActivitiesSerializer(serializers.Serializer):
    paidQtyById = serializers.DictField(
        child=serializers.IntegerField(min_value=0), required=False, default=dict
    )


class _RestoSerializer(serializers.Serializer):
    qtyByMealId = serializers.DictField(
        child=serializers.IntegerField(min_value=0), required=False, default=dict
    )


def _fuel_keys() -> list[str]:
    """Return all valid fuel keys from the DB at call-time so new fuels
    added via Django Admin are immediately accepted without code changes.
    Falls back to the three original values when the DB is unavailable
    (e.g. during migrations / schema setup).
    """
    try:
        from apps.catalog.models import FuelOption  # local import: avoids circular
        keys = list(FuelOption.objects.values_list("key", flat=True))
        if keys:
            return keys
    except Exception:  # noqa: BLE001  — DB not ready, tests, etc.
        pass
    return ["essence", "diesel", "electrique"]


class _TransportSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(
        choices=["car", "train", "onSite"], required=False, allow_null=True
    )
    distanceOneWayKm = serializers.IntegerField(required=False, default=400)
    fuel = serializers.CharField(
        required=False,
        default="essence",
        allow_blank=False,
    )

    def validate_fuel(self, value: str) -> str:
        valid = _fuel_keys()
        if value not in valid:
            raise serializers.ValidationError(
                f"« {value} » n'est pas un choix valide."
            )
        return value


class _PromosSerializer(serializers.Serializer):
    promoSejourRate = serializers.FloatField(required=False, default=0.0)
    quinzaineFutee = serializers.BooleanField(required=False, default=False)
    soloSupplementMode = serializers.ChoiceField(
        choices=["default", "reduced", "off"], required=False, default="default"
    )
    


class SejourSerializer(serializers.Serializer):
    dateDebut = serializers.DateField()
    dateFin = serializers.DateField()
    # formule = serializers.ChoiceField(choices=["PC", "DP", "LOC"])
    formule = serializers.ChoiceField(choices=Formule.choices)
    fNuits = serializers.IntegerField(required=False, default=0)
    extras = _ExtrasSerializer(required=False, default=dict)
    activities = _ActivitiesSerializer(required=False, default=dict)
    extraActivities = _ExtraActivitiesSerializer(required=False, default=dict)
    resto = _RestoSerializer(required=False, default=dict)
    transport = _TransportSerializer(required=False, default=dict, allow_null=True)
    promos = _PromosSerializer(required=False, default=dict)


class _MetaSerializer(serializers.Serializer):
    sessionId = serializers.CharField(required=False, allow_blank=True)
    referrer = serializers.CharField(required=False, allow_blank=True)
    utmSource = serializers.CharField(required=False, allow_blank=True)
    deviceType = serializers.CharField(required=False, allow_blank=True)
    screenWidth = serializers.IntegerField(required=False)
    stepTimings = serializers.DictField(required=False)
    villageChanges = serializers.ListField(child=serializers.CharField(), required=False)


class EstimateStayInputSerializer(serializers.Serializer):
    villageId = serializers.SlugField()
    family = FamilySerializer()
    sejour = SejourSerializer()
    _meta = _MetaSerializer(required=False, default=dict)


class _ChildLineOutputSerializer(serializers.Serializer):
    age = serializers.IntegerField()
    discountFraction = serializers.FloatField(source="discount_fraction")
    amount = serializers.IntegerField()


class _DisplayMetricsOutputSerializer(serializers.Serializer):
    perDayFamily = serializers.IntegerField(source="per_day_family")
    perPersonPerDay = serializers.IntegerField(source="per_person_per_day")
    totalVtfStayOnly = serializers.IntegerField(source="total_vtf_stay_only")
    savingsPct = serializers.SerializerMethodField()
    discountPct = serializers.IntegerField(source="discount_pct")

    def get_savingsPct(self, obj) -> int:
        value = obj.get("savings_pct", 0) if isinstance(obj, dict) else obj.savings_pct
        return jsround(value)


class _BudgetBreakdownOutputSerializer(serializers.Serializer):
    stay = serializers.IntegerField()
    restoration = serializers.IntegerField()
    transport = serializers.IntegerField()
    activities = serializers.IntegerField()


class SejourEstimateOutputSerializer(serializers.Serializer):
    """Output of `/estimate/stay`. Mirrors `SejourEstimate` dataclass."""

    total = serializers.IntegerField()
    perPerson = serializers.IntegerField(source="per_person")
    totalAdults = serializers.IntegerField(source="total_adults")
    totalChildren = serializers.IntegerField(source="total_children")
    perAdultBase = serializers.IntegerField(source="per_adult_base")
    childLines = _ChildLineOutputSerializer(source="child_lines", many=True)
    saisonKey = serializers.CharField(source="saison_key")
    nuits = serializers.IntegerField()
    discountRate = serializers.SerializerMethodField()
    staySubtotal = serializers.IntegerField(source="stay_subtotal")
    adhesion = serializers.IntegerField()
    soloSupplement = serializers.IntegerField(source="solo_supplement")
    extrasLoc = serializers.IntegerField(source="extras_loc")
    activitiesTotal = serializers.IntegerField(source="activities_total")
    restoTotal = serializers.IntegerField(source="resto_total")
    transportTotal = serializers.IntegerField(source="transport_total")
    hotelEstimate = serializers.IntegerField(source="hotel_estimate")
    hotelSavings = serializers.IntegerField(source="hotel_savings")
    displayMetrics = _DisplayMetricsOutputSerializer(
        source="display_metrics", required=False, allow_null=True
    )
    budgetBreakdown = _BudgetBreakdownOutputSerializer(
        source="budget_breakdown", required=False, allow_null=True
    )
    includes = serializers.DictField(
        child=serializers.CharField(),
        required=False,
    )
    bookingUrl = serializers.URLField(required=False, allow_blank=True)

    def get_discountRate(self, obj) -> float:
        value = obj.get("discount_rate", 0) if isinstance(obj, dict) else obj.discount_rate
        return round(value, 2)

    # Optional: alternative formule totals (only when client requests and main formule is LOC)
    class _FormuleAltSerializer(serializers.Serializer):
        # formule = serializers.ChoiceField(choices=["PC", "DP"])
        formule = serializers.ChoiceField(choices=[c for c in Formule.choices if c[0] != Formule.LOC.value])
        total = serializers.IntegerField()

    formuleAlternatives = _FormuleAltSerializer(many=True, required=False)
    


class CarCostInputSerializer(serializers.Serializer):
    distanceOneWayKm = serializers.FloatField(min_value=0)
    fuel = serializers.CharField()

    def validate_fuel(self, value: str) -> str:
        valid = _fuel_keys()
        if value not in valid:
            raise serializers.ValidationError(
                f"« {value} » n'est pas un choix valide."
            )
        return value


class CarCostOutputSerializer(serializers.Serializer):
    kmAR = serializers.IntegerField()
    fuelCost = serializers.IntegerField()
    tollCost = serializers.IntegerField()
    total = serializers.IntegerField()


class TrainCostInputSerializer(serializers.Serializer):
    adults = serializers.IntegerField(min_value=0)
    children = serializers.IntegerField(min_value=0)


class TrainCostOutputSerializer(serializers.Serializer):
    total = serializers.IntegerField()


class QfInputSerializer(serializers.Serializer):
    netMonthlyIncome = serializers.FloatField(min_value=0)
    parts = serializers.FloatField(min_value=1)


class QfOutputSerializer(serializers.Serializer):
    qfVal = serializers.IntegerField()
    badge = serializers.CharField()


class _RestoMealRefSerializer(serializers.Serializer):
    code = serializers.CharField()
    priceAdult = serializers.IntegerField(source="price_adult", required=False)
    priceChild = serializers.IntegerField(source="price_child", required=False)


class RestoTotalInputSerializer(serializers.Serializer):
    adults = serializers.IntegerField(min_value=0)
    children = serializers.IntegerField(min_value=0)
    qtyByMealId = serializers.DictField(child=serializers.IntegerField(min_value=0))


class RestoTotalOutputSerializer(serializers.Serializer):
    total = serializers.IntegerField()


class AvailablePromosInputSerializer(serializers.Serializer):
    dateDebut = serializers.DateField()
    dateFin = serializers.DateField()
    now = serializers.DateField(required=False)
    isSoloParent = serializers.BooleanField(required=False, default=False)
    quinzaineFutee = serializers.BooleanField(required=False, default=False)
    formule = serializers.CharField(required=False, allow_blank=True)
    villageId = serializers.SlugField(required=False, allow_blank=True)


class PromoChoiceSerializer(serializers.Serializer):
    key = serializers.CharField()
    icon = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()
    tag = serializers.CharField()
    rate = serializers.FloatField()
    kind = serializers.CharField()


class StayDaysInputSerializer(serializers.Serializer):
    dateDebut = serializers.DateField()
    dateFin = serializers.DateField()


class StayDayOutputSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    date = serializers.DateField()


class BookingLinkContextSerializer(serializers.Serializer):
    saisonKey = serializers.CharField(required=False, default="ete")
    estimatedTotal = serializers.IntegerField(required=False)
    formule = serializers.CharField(required=False)
    promosApplied = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    recoStrategy = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    recoScore = serializers.FloatField(required=False, allow_null=True)
    recoRank = serializers.IntegerField(required=False, allow_null=True)


class _DatesSerializer(serializers.Serializer):
    """`{debut, fin}` — explicit so unknown keys raise 400 instead of 500."""

    debut = serializers.DateField()
    fin = serializers.DateField()

    def validate(self, attrs):
        if attrs["fin"] < attrs["debut"]:
            raise serializers.ValidationError("`fin` must be on/after `debut`.")
        return attrs


class BookingLinkInputSerializer(serializers.Serializer):
    family = FamilySerializer()
    dates = _DatesSerializer()
    sessionId = serializers.CharField(allow_blank=True, required=False, default="")
    source = serializers.ChoiceField(
        choices=["estimate", "recommendation", "similar", "detail", "recap"],
        default="estimate",
    )
    context = BookingLinkContextSerializer(required=False, default=dict)


class BookingLinkOutputSerializer(serializers.Serializer):
    redirectUrl = serializers.URLField()
    token = serializers.CharField()
    expiresAt = serializers.DateTimeField()
    targetUrl = serializers.URLField()
    params = serializers.DictField()


class SignalInputSerializer(serializers.Serializer):
    """Lightweight beacon for VillageInteraction. Spec §6.1 + §US-3.1."""

    sessionId = serializers.CharField(allow_blank=True, required=False, default="")
    villageId = serializers.SlugField(required=False, allow_blank=True)
    kind = serializers.CharField()
    value = serializers.FloatField(required=False, default=1.0)
    metadata = serializers.DictField(required=False, default=dict)


class InteractionInputSerializer(serializers.Serializer):
    """`POST /api/v1/interactions`."""

    sessionId = serializers.CharField(allow_blank=True, required=False, default="")
    villageId = serializers.SlugField()
    kind = serializers.ChoiceField(
        choices=["view", "simulate", "bookmark", "rate", "click_cta"]
    )
    value = serializers.FloatField(required=False, default=1.0)
    metadata = serializers.DictField(required=False, default=dict)

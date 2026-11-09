"""Serializer for the POST /api/v1/mailer/send-simulation endpoint."""
from __future__ import annotations

from rest_framework import serializers


class SendSimulationSerializer(serializers.Serializer):
    # ── Recipient ──────────────────────────────────────────────────────────
    recipientEmail = serializers.EmailField()
    locale = serializers.ChoiceField(choices=["FR", "EN"], default="FR")
    bookingUrl = serializers.URLField(required=False, allow_blank=True, default="")
    redirectUrl = serializers.URLField(required=False, allow_blank=True, default="")
    bookingURL = serializers.URLField(required=False, allow_blank=True, default="")
    booking_url = serializers.URLField(required=False, allow_blank=True, default="")
    redirect_url = serializers.URLField(required=False, allow_blank=True, default="")

    # ── Destination / stay ────────────────────────────────────────────────
    villageName = serializers.CharField(max_length=128)
    nuits = serializers.IntegerField(min_value=1)
    saison = serializers.CharField(max_length=32)
    dateDebut = serializers.DateField()
    dateFin = serializers.DateField()

    # ── Family ────────────────────────────────────────────────────────────
    adultes = serializers.IntegerField(min_value=1)
    enfantsAges = serializers.ListField(child=serializers.IntegerField(min_value=0), default=list)
    childAges = serializers.CharField(required=False, allow_blank=True, default="")

    # ── Formula / context ─────────────────────────────────────────────────
    formule = serializers.CharField(max_length=64)   # "PC", "DP", "SA" or display label
    formulaIncludes = serializers.CharField(required=False, allow_blank=True, default="")
    envKey = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")

    # ── Per-person summary ────────────────────────────────────────────────
    perPersonPerDay = serializers.IntegerField(min_value=0)
    perDayFamily = serializers.IntegerField(min_value=0)
    total = serializers.IntegerField(min_value=0)
    perPerson = serializers.IntegerField(min_value=0)

    # ── Budget breakdown ─────────────────────────────────────────────────
    perAdultBase = serializers.IntegerField(min_value=0)
    totalAdults = serializers.IntegerField(min_value=0)
    childAmounts = serializers.ListField(child=serializers.IntegerField(min_value=0), default=list)
    totalChildren = serializers.IntegerField(min_value=0)
    adhesion = serializers.IntegerField(min_value=0)
    staySubtotal = serializers.IntegerField(min_value=0)

    # ── Optional cost buckets ─────────────────────────────────────────────
    activitiesTotal = serializers.IntegerField(min_value=0, default=0)
    restoTotal = serializers.IntegerField(min_value=0, default=0)

    # ── Transport ─────────────────────────────────────────────────────────
    transportMode = serializers.CharField(max_length=32, default="car")
    transportKm = serializers.IntegerField(min_value=0, default=0)
    transportLabel = serializers.CharField(required=False, allow_blank=True, default="")
    transportTotal = serializers.IntegerField(min_value=0, default=0)

    # ── Savings vs hotel ──────────────────────────────────────────────────
    hotelEstimate = serializers.IntegerField(min_value=0, default=0)
    hotelSavings = serializers.IntegerField(min_value=0, default=0)
    savingsPct = serializers.IntegerField(min_value=0, default=0)

    # ── Raw simulator state for future booking/deep-link use ─────────────
    simulationData = serializers.JSONField(required=False, default=dict)

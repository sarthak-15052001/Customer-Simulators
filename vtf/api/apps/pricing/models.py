"""Pricing-domain ORM models.

Source of truth: vtf/api/docs/03-data-models.md (pricing section).

Notes:
  - SimulationLog rows are written by EstimateStayView (do NOT skip — it is
    the data foundation for Phase 2 reco; see CLAUDE.md don'ts).
  - BookingClick rows are created by GET /api/v1/go/{token} via on_commit;
    every booking link MUST go through the redirect (AC-1.13, US-2.8).
"""
from __future__ import annotations

from django.db import models


class SimulationLog(models.Model):
    """Every /estimate/stay call is logged with full context.

    PRIMARY data source for Phase 2 recommendations & Phase 2+ SVD.
    """

    id = models.BigAutoField(primary_key=True)
    session_id = models.CharField(max_length=64, db_index=True)

    # ─── What they searched ───
    village = models.ForeignKey(
        "catalog.Village", on_delete=models.SET_NULL, null=True
    )
    region = models.CharField(max_length=64)
    formule = models.CharField(max_length=4)
    saison_key = models.CharField(max_length=8)
    date_debut = models.DateField()
    date_fin = models.DateField()
    nuits = models.SmallIntegerField()

    # ─── Who they are ───
    nb_adults = models.SmallIntegerField()
    nb_children = models.SmallIntegerField()
    children_ages = models.JSONField(default=list)
    qf_val = models.IntegerField(null=True)
    qf_badge = models.CharField(max_length=8, blank=True, default="")
    is_solo_parent = models.BooleanField(default=False)
    is_maxi_family = models.BooleanField(default=False)

    # ─── What they got ───
    estimated_total = models.IntegerField()
    per_person_per_day = models.IntegerField()
    discount_rate = models.FloatField()
    promos_applied = models.JSONField(default=list)
    transport_mode = models.CharField(max_length=16, blank=True, default="")
    transport_cost = models.IntegerField(default=0)
    activities_cost = models.IntegerField(default=0)
    resto_cost = models.IntegerField(default=0)

    # ─── Hotel comparison ───
    hotel_estimate = models.IntegerField(default=0)
    hotel_savings = models.IntegerField(default=0)
    savings_pct = models.FloatField(default=0)

    # ─── Behavior signals ───
    clicked_booking = models.BooleanField(default=False)
    booking_click_at = models.DateTimeField(null=True, blank=True)
    time_on_result_ms = models.IntegerField(null=True, blank=True)

    # ─── Meta ───
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_hash = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.CharField(max_length=256, blank=True, default="")

    # ─── Phase 2+ optional context ───
    referrer = models.CharField(max_length=256, blank=True, default="")
    utm_source = models.CharField(max_length=64, blank=True, default="")
    device_type = models.CharField(max_length=16, blank=True, default="")
    step_timings = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=["session_id", "created_at"]),
            models.Index(fields=["village", "saison_key"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]


class BookingRedirectToken(models.Model):
    """Signed-token bridge between a simulation result and the VTF booking page.

    Created by POST /api/v1/villages/{id}/booking-link.
    Consumed by GET /api/v1/go/{token} which 302s to target_url and logs
    BookingClick. Spec §US-2.8.
    """

    token = models.CharField(max_length=128, primary_key=True)
    village = models.ForeignKey("catalog.Village", on_delete=models.CASCADE)
    session_id = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField()
    target_url = models.URLField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    click_count = models.IntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["expires_at"])]


class BookingClick(models.Model):
    """One row per click on a "Réserver sur VTF" link.

    Strongest implicit signal for the recommender. Created by GET /go/{token}
    (async via on_commit). Spec §US-2.8.
    """

    id = models.BigAutoField(primary_key=True)
    # token = models.CharField(max_length=128, db_index=True)
    token = models.ForeignKey(
        "BookingRedirectToken",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clicks",
        db_index=True,
    )
    session_id = models.CharField(max_length=64, db_index=True)
    village = models.ForeignKey("catalog.Village", on_delete=models.CASCADE)

    SOURCE_CHOICES = [
        ("estimate", "From /estimate/stay result"),
        ("recommendation", "From /recommend/villages"),
        ("similar", "From /villages/{id}/similar"),
        ("detail", "From village detail page"),
        ("recap", "From recap page"),
    ]
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES)

    # Family snapshot
    family_adults = models.SmallIntegerField()
    family_children = models.JSONField()

    # Stay snapshot
    date_debut = models.DateField()
    date_fin = models.DateField()
    saison_key = models.CharField(max_length=8)
    formule = models.CharField(max_length=4)

    # Estimate context (nullable when not coming from a fresh estimate)
    estimated_total = models.IntegerField(null=True, blank=True)
    promos_applied = models.JSONField(default=list)

    # Recommendation context (nullable when source != 'recommendation')
    reco_strategy = models.CharField(max_length=32, blank=True, default="")
    reco_score = models.FloatField(null=True, blank=True)
    reco_rank = models.SmallIntegerField(null=True, blank=True)

    # Privacy-safe trace
    ip_hash = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.CharField(max_length=256, blank=True, default="")

    clicked_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_repeat = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["session_id", "clicked_at"]),
            models.Index(fields=["village", "source"]),
            models.Index(fields=["clicked_at"]),
        ]

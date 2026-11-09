"""Django admin for pricing models (logs + booking redirect)."""
from __future__ import annotations

from django.contrib import admin

from apps.pricing.models import BookingClick, BookingRedirectToken, SimulationLog


@admin.register(SimulationLog)
class SimulationLogAdmin(admin.ModelAdmin):
    """Every /estimate/stay call creates one row. High-volume — paginate aggressively."""

    list_display = (
        "id",
        "created_at",
        "session_id",
        "village",
        "formule",
        "saison_key",
        "nuits",
        "estimated_total",
        "discount_rate",
        "clicked_booking",
    )
    list_filter = (
        "formule",
        "saison_key",
        "transport_mode",
        "clicked_booking",
        "is_solo_parent",
        "is_maxi_family",
        "device_type",
        "qf_badge",
    )
    search_fields = ("session_id", "village__id", "village__nom", "ip_hash")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    autocomplete_fields = ("village",)
    readonly_fields = ("created_at",)
    list_per_page = 50
    fieldsets = (
        (None, {"fields": ("session_id", "village", "created_at")}),
        (
            "Search",
            {
                "fields": (
                    "region",
                    "formule",
                    "saison_key",
                    "date_debut",
                    "date_fin",
                    "nuits",
                )
            },
        ),
        (
            "Family",
            {
                "fields": (
                    "nb_adults",
                    "nb_children",
                    "children_ages",
                    "qf_val",
                    "qf_badge",
                    "is_solo_parent",
                    "is_maxi_family",
                )
            },
        ),
        (
            "Estimate",
            {
                "fields": (
                    "estimated_total",
                    "per_person_per_day",
                    "discount_rate",
                    "promos_applied",
                    "transport_mode",
                    "transport_cost",
                    "activities_cost",
                    "resto_cost",
                )
            },
        ),
        (
            "Hotel comparison",
            {"fields": ("hotel_estimate", "hotel_savings", "savings_pct")},
        ),
        (
            "Behavior",
            {"fields": ("clicked_booking", "booking_click_at", "time_on_result_ms")},
        ),
        (
            "Trace",
            {
                "fields": (
                    "ip_hash",
                    "user_agent",
                    "referrer",
                    "utm_source",
                    "device_type",
                    "step_timings",
                )
            },
        ),
    )


@admin.register(BookingRedirectToken)
class BookingRedirectTokenAdmin(admin.ModelAdmin):
    list_display = (
        "token",
        "village",
        "session_id",
        "click_count",
        "expires_at",
        "created_at",
    )
    search_fields = ("token", "session_id", "village__id", "village__nom")
    list_filter = ("village__region",)
    autocomplete_fields = ("village",)
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(BookingClick)
class BookingClickAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "clicked_at",
        "session_id",
        "village",
        "source",
        "estimated_total",
        "is_repeat",
    )
    list_filter = ("source", "saison_key", "formule", "is_repeat")
    search_fields = ("token", "session_id", "village__id", "village__nom")
    date_hierarchy = "clicked_at"
    ordering = ("-clicked_at",)
    autocomplete_fields = ("village",)
    list_per_page = 50

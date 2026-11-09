"""Django admin for catalog models. All catalog tables are fully consultable
and editable through /admin/.
"""
from __future__ import annotations

from django.contrib import admin

from apps.catalog.models import (
    Activity,
    Animation,
    Attraction,
    FuelOption,
    Formula,
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
from apps.tariff_scraper.admin_display import render_tarifs_grid


@admin.register(Formula)
class FormulaAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "label",
        "icon",
        "icon_key",
        "sort_order",
    )
    list_editable = ("sort_order",)
    search_fields = ("code", "label", "short_description", "include_text")
    ordering = ("sort_order", "code")
    filter_horizontal = ("villages",)


class AttractionInline(admin.TabularInline):
    model = Attraction
    extra = 0


class VillageInfraInline(admin.StackedInline):
    model = VillageInfra
    extra = 0
    can_delete = True


class VillageClubsEteInline(admin.StackedInline):
    model = VillageClubsEte
    extra = 0
    can_delete = True


@admin.register(Village)
class VillageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nom",
        "region",
        "zone",
        "env_code",
        "tarif_unit",
        "ski",
        "has_loc",
        "bebe_club",
        "qf_exc",
    )
    list_filter = ("region", "zone", "env_code", "tarif_unit", "ski", "has_loc", "bebe_club", "qf_exc", "forfait_rm")
    search_fields = ("id", "nom", "nom2", "region", "zone__name", "env_code")
    ordering = ("region", "nom")
    autocomplete_fields = ("zone",)
    inlines = (AttractionInline, VillageInfraInline, VillageClubsEteInline)
    save_on_top = True
    readonly_fields = ("get_formules", "tarifs_grid")
    fieldsets = (
        (None, {"fields": ("id", "nom", "nom2", "region", "zone")}),
        ("Environnement", {"fields": ("env_emoji", "env_code")}),
        ("Formules & tarifs", {"fields": ("get_formules", "tarif_unit", "has_loc", "ski", "tarifs_grid")}),
        ("Ouverture", {"fields": ("ouverture",)}),
        (
            "Flags",
            {"fields": ("bebe_club", "forfait_rm", "qf_exc", "enf_solo_half")},
        ),
        (
            "Booking redirect (VTF)",
            {"fields": ("vtf_department", "vtf_city", "vtf_slug", "vtf_url_verified_at")},
        ),
    )

    @admin.display(description="Formules")
    def get_formules(self, obj):
        return ", ".join(obj.formules) or "—"
    
    @admin.display(description="Tarifs")
    def tarifs_grid(self, obj):
        return render_tarifs_grid(obj.tarifs)

@admin.register(Attraction)
class AttractionAdmin(admin.ModelAdmin):
    list_display = ("village", "nom", "type", "icon", "km")
    list_filter = ("type",)
    search_fields = ("nom", "village__nom")
    autocomplete_fields = ("village",)
    ordering = ("village", "km")


@admin.register(LandingMapZone)
class LandingMapZoneAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "marker_count")
    search_fields = ("name", "villages")
    ordering = ("id",)

    @admin.display(description="Markers")
    def marker_count(self, obj):
        return len(obj.villages or [])


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("code", "region", "kind", "nom", "type", "price_adult", "price_child")
    list_filter = ("region", "kind")
    search_fields = ("code", "nom", "region")
    ordering = ("region", "kind", "nom")


@admin.register(Animation)
class AnimationAdmin(admin.ModelAdmin):
    list_display = ("order", "nom", "note")
    ordering = ("order",)
    search_fields = ("nom", "note")


# @admin.register(VillageInfra)
# class VillageInfraAdmin(admin.ModelAdmin):
#     list_display = ("village",)
#     autocomplete_fields = ("village",)
#     search_fields = ("village__nom",)


# @admin.register(VillageClubsEte)
# class VillageClubsEteAdmin(admin.ModelAdmin):
#     list_display = ("village",)
#     autocomplete_fields = ("village",)
#     search_fields = ("village__nom",)


@admin.register(PricingRules)
class PricingRulesAdmin(admin.ModelAdmin):
    """One active row at a time. Use the action below to swap which row is active."""

    list_display = ("id", "updated_at", "is_active", "created_at")
    list_filter = ("is_active",)
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    actions = ("activate_selected",)

    @admin.action(description="Mark selected as the active rules (deactivates others)")
    def activate_selected(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one row to activate.", level="error")
            return
        target = queryset.first()
        PricingRules.objects.filter(is_active=True).exclude(pk=target.pk).update(is_active=False)
        target.is_active = True
        target.save(update_fields=["is_active"])
        self.message_user(request, f"PricingRules #{target.pk} is now active.")


@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    list_display = ("order", "code", "label", "price_adult", "price_child")
    ordering = ("order",)
    search_fields = ("code", "label")


@admin.register(FuelOption)
class FuelOptionAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "cost_per_km")
    search_fields = ("key", "label")


@admin.register(Promo)
class PromoAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "tag", "rate", "kind")
    list_filter = ("kind",)
    search_fields = ("key", "label", "description")


@admin.register(MarketingSeasons)
class MarketingSeasonsAdmin(admin.ModelAdmin):
    list_display = ("sort_order", "key", "label", "icon", "start_date", "end_date")
    list_filter = ("sort_order",)
    search_fields = ("key", "label")
    ordering = ("sort_order",)
    fieldsets = (
        (None, {"fields": ("key", "label", "icon")}),
        ("Dates", {"fields": ("default_date", "start_date", "end_date")}),
        ("Ordering", {"fields": ("sort_order",)}),
    )


@admin.register(MarketingSeasonEnvironment)
class MarketingSeasonEnvironmentAdmin(admin.ModelAdmin):
    list_display = ("marketing_season", "order", "key", "label", "icon", "sub")
    list_filter = ("marketing_season",)
    search_fields = ("key", "label", "sub", "marketing_season__label")
    autocomplete_fields = ("marketing_season",)
    ordering = ("marketing_season", "order")

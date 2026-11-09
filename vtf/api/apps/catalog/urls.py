"""Catalog URL routing. See vtf/api/docs/05-api-endpoints.md."""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.catalog.views import (
    AnimationListView,
    AttractionListView,
    EnvironmentsBySeasonView,
    FuelListView,
    FormulaListView,
    LandingMapView,
    MarketingSeasonsView,
    MealListView,
    PricingRulesView,
    PromoCatalogView,
    RegionActivitiesView,
    RegionListView,
    SeasonForDateView,
    SeasonListView,
    SimulationPdfView,
    VillageViewSet,
    health_view,
)

router = DefaultRouter()
router.register(r"villages", VillageViewSet, basename="village")

urlpatterns = [
    path("", include(router.urls)),
    path("regions", RegionListView.as_view(), name="regions"),
    path("regions/<path:region>/activities", RegionActivitiesView.as_view(), name="region-activities"),
    path("seasons", SeasonListView.as_view(), name="seasons"),
    path("season", SeasonForDateView.as_view(), name="season-for-date"),
    path("marketing-seasons", MarketingSeasonsView.as_view(), name="marketing-seasons"),
    path("environments", EnvironmentsBySeasonView.as_view(), name="environments"),
    path("landing/map", LandingMapView.as_view(), name="landing-map"),
    path("formules", FormulaListView.as_view(), name="formules"),
    path("meals", MealListView.as_view(), name="meals"),
    path("fuels", FuelListView.as_view(), name="fuels"),
    path("promos/catalog", PromoCatalogView.as_view(), name="promos-catalog"),
    path("animations", AnimationListView.as_view(), name="animations"),
    path("attractions", AttractionListView.as_view(), name="attractions"),
    path("pricing-rules", PricingRulesView.as_view(), name="pricing-rules"),
    path("health", health_view, name="health"),
    path("simulations/pdf/", SimulationPdfView.as_view(), name="simulations-pdf"),
]

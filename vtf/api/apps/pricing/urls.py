"""Pricing URL routing. See vtf/api/docs/05-api-endpoints.md."""
from __future__ import annotations

from django.urls import path

from apps.pricing.views import (
    AvailablePromosView,
    BookingLinkView,
    CarCostView,
    EstimateStayView,
    InteractionView,
    QfView,
    RestoTotalView,
    SignalView,
    SimulationLogExportView,
    StayDaysView,
    TrainCostView,
    booking_redirect_view,
)

urlpatterns = [
    path("estimate/stay", EstimateStayView.as_view(), name="estimate-stay"),
    path("transport/car", CarCostView.as_view(), name="transport-car"),
    path("transport/train", TrainCostView.as_view(), name="transport-train"),
    path("family/qf", QfView.as_view(), name="family-qf"),
    path("resto/total", RestoTotalView.as_view(), name="resto-total"),
    path("promos/available", AvailablePromosView.as_view(), name="promos-available"),
    path("stay/days", StayDaysView.as_view(), name="stay-days"),
    path("villages/<slug:id>/booking-link", BookingLinkView.as_view(), name="booking-link"),
    path("go/<str:token>", booking_redirect_view, name="booking-redirect"),
    path("signals", SignalView.as_view(), name="signals"),
    path("interactions", InteractionView.as_view(), name="interactions"),
    path("exports/simulation-logs", SimulationLogExportView.as_view(), name="simulation-logs-export"),
]

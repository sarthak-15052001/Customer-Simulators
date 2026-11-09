from __future__ import annotations

from django.urls import path

from apps.mailer.views import SendSimulationEmailView

urlpatterns = [
    path("mailer/send-simulation", SendSimulationEmailView.as_view(), name="mailer-send-simulation"),
]

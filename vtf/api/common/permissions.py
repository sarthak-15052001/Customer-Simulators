"""Shared DRF permissions and staff-only API mixins.

Use for `/api/v*/admin/*` endpoints (reco weights, interaction stats, cache rebuild, …).
Public catalog and pricing endpoints stay `AllowAny` via default settings.

Typical usage:
    class RecoWeightsView(StaffAPIViewMixin, APIView):
        ...
"""
from __future__ import annotations

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import BasePermission


class IsStaffUser(BasePermission):
    """Authenticated user with `is_staff=True` (Django admin / ops tooling)."""

    message = "Staff privileges required (is_staff=True on your user account)."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)


class StaffBasicAuthentication(BasicAuthentication):
    """HTTP Basic auth without triggering the browser's native login prompt."""

    def authenticate_header(self, request) -> str | None:
        return None


class StaffBasicAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "common.permissions.StaffBasicAuthentication"
    name = "basicAuth"

    def get_security_definition(self, auto_schema) -> dict:
        return {
            "type": "http",
            "scheme": "basic",
        }


# Reusable class lists — import on any staff-only APIView / ViewSet.
STAFF_AUTHENTICATION_CLASSES = [StaffBasicAuthentication]
STAFF_PERMISSION_CLASSES = [IsStaffUser]


class StaffAPIViewMixin:
    """HTTP Basic auth for staff users."""

    authentication_classes = STAFF_AUTHENTICATION_CLASSES
    permission_classes = STAFF_PERMISSION_CLASSES

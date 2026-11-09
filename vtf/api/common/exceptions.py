"""Custom DRF exception handler — wraps ALL errors in the CustomResponse envelope.

Registered in settings:
    REST_FRAMEWORK["EXCEPTION_HANDLER"] = "common.exceptions.custom_exception_handler"

This means every error response — including:
    - 400 validation errors (serializer.is_valid(raise_exception=True))
    - 404 Not Found (get_object_or_404)
    - 429 Too Many Requests (throttle)
    - 405 Method Not Allowed
    - 500 unhandled exceptions
...will always have the shape:
    {
        "success": false,
        "message": "Human-readable description",
        "data": null,
        "errors": { "field": ["error"] }   ← only for 400 validation errors
    }
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler


# Human-readable messages per status code / exception type
_STATUS_MESSAGES: dict[int, str] = {
    400: "Invalid request — please check your input.",
    401: "Authentication required.",
    403: "You do not have permission to perform this action.",
    404: "The requested resource was not found.",
    405: "Method not allowed.",
    429: "Too many requests — please slow down and try again later.",
    500: "An unexpected server error occurred.",
    503: "Service temporarily unavailable.",
}

_EXCEPTION_MESSAGES: dict[type, str] = {
    ValidationError:      "Validation failed — check the errors field for details.",
    NotFound:             "The requested resource was not found.",
    PermissionDenied:     "You do not have permission to perform this action.",
    NotAuthenticated:     "Authentication credentials were not provided.",
    AuthenticationFailed: "Invalid authentication credentials.",
    MethodNotAllowed:     "HTTP method not allowed on this endpoint.",
    Throttled:            "Rate limit exceeded — try again later.",
}


def custom_exception_handler(exc, context) -> Response | None:
    """Replace DRF's default error response with the CustomResponse envelope."""
    # Let DRF build its standard response first.
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception — Django will return a 500.
        return None

    # Determine a friendly message.
    message = _EXCEPTION_MESSAGES.get(type(exc))
    if not message:
        message = _STATUS_MESSAGES.get(response.status_code, "An error occurred.")

    if isinstance(exc, PermissionDenied):
        request = context.get("request")
        if request is not None and not getattr(request.user, "is_authenticated", False):
            message = (
                "Staff authentication required. "
                "Use HTTP Basic auth with a staff user."
            )
        elif request is not None and not getattr(request.user, "is_staff", False):
            message = "Staff privileges required (is_staff=True on your user account)."

    # For Throttled exceptions, include the wait time in the message.
    if isinstance(exc, Throttled) and exc.wait is not None:
        wait = int(exc.wait)
        message = f"Rate limit exceeded. Retry after {wait} second{'s' if wait != 1 else ''}."

    # Pull field-level errors from ValidationError.
    errors: dict | None = None
    if isinstance(exc, ValidationError):
        raw = response.data
        if isinstance(raw, dict):
            errors = raw
        elif isinstance(raw, list):
            errors = {"non_field_errors": raw}

    # Get the original "detail" for non-validation errors (e.g. "Not found.").
    detail: str | None = None
    if not isinstance(exc, (ValidationError, NotAuthenticated, AuthenticationFailed)):
        raw_detail = getattr(exc, "detail", None)
        if raw_detail is not None:
            detail = str(raw_detail) if not isinstance(raw_detail, str) else raw_detail

    body: dict = {
        "success": False,
        "message": message,
        "data": detail,   # None for validation errors, detail string otherwise
    }
    if errors:
        body["errors"] = errors

    response.data = body
    return response

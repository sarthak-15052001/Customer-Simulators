"""Common API response helpers — spec §5.1 error shape.

Usage in any view:
    from common.response import CustomResponse

    return CustomResponse.success("Villages fetched", data=[...])
    return CustomResponse.error("Village not found", status_code=404)

Every response follows the envelope:
    {
        "success": true | false,
        "message": "Human-readable string",
        "data": <payload> | null
    }

Error responses also include DRF's standard "errors" dict when field-level
validation errors exist:
    {
        "success": false,
        "message": "Validation error",
        "data": null,
        "errors": { "dateDebut": ["This field is required."] }
    }
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response


class CustomResponse(Response):
    """Drop-in replacement for DRF Response with success/error factories."""

    @classmethod
    def success(
        cls,
        message: str,
        data=None,
        status_code: int = status.HTTP_200_OK,
    ) -> "CustomResponse":
        """Return a 2xx envelope.

        Args:
            message:     Human-readable description shown in Swagger / logs.
            data:        Serialised payload (list, dict, or None).
            status_code: HTTP status (default 200).
        """
        return cls(
            {"success": True, "message": message, "data": data},
            status=status_code,
        )

    @classmethod
    def error(
        cls,
        message: str,
        data=None,
        errors: dict | None = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> "CustomResponse":
        """Return a 4xx/5xx envelope.

        Args:
            message:     Human-readable error description.
            data:        Optional extra payload (usually None for errors).
            errors:      Field-level validation errors dict (DRF style).
            status_code: HTTP status (default 400).
        """
        body: dict = {"success": False, "message": message, "data": data}
        if errors:
            body["errors"] = errors
        return cls(body, status=status_code)

    @classmethod
    def created(cls, message: str, data=None) -> "CustomResponse":
        """Convenience for 201 Created."""
        return cls.success(message, data=data, status_code=status.HTTP_201_CREATED)

    @classmethod
    def no_content(cls) -> "CustomResponse":
        """Convenience for 204 No Content."""
        return cls(None, status=status.HTTP_204_NO_CONTENT)


def village_summary(v) -> dict:
    """Serialize a Village (or similar dict/object) to Phase-2 response shape.

    Kept in `common.response` so all apps can reuse the same camelCase wire
    format helpers.
    """
    if v is None:
        return {}

    # Accept dict passthroughs coming from some internal scorers.
    if isinstance(v, dict):
        # Already in wire format.
        if "envCode" in v:
            return v
        return {
            "id": v.get("id", ""),
            "nom": v.get("nom", ""),
            "nom2": v.get("nom2", ""),
            "region": v.get("region", ""),
            "env": v.get("env_emoji", v.get("env", "")),
            "envCode": v.get("env_code", ""),
            "formules": v.get("formules") or [],
            "ski": v.get("ski", False),
            "bebeClub": v.get("bebe_club", False),
            "qfExc": v.get("qf_exc", False),
            "enfSoloHalf": v.get("enf_solo_half", False),
            "hasLoc": v.get("has_loc", False),
        }

    # Object / Django model case (duck-typed to avoid import cycles).
    return {
        "id": getattr(v, "id", ""),
        "nom": getattr(v, "nom", ""),
        "nom2": getattr(v, "nom2", "") or "",
        "region": getattr(v, "region", ""),
        "env": getattr(v, "env_emoji", "") or "",
        "envCode": getattr(v, "env_code", "") or "",
        "formules": getattr(v, "formules", []) or [],
        "ski": getattr(v, "ski", False),
        "bebeClub": getattr(v, "bebe_club", False),
        "qfExc": getattr(v, "qf_exc", False),
        "enfSoloHalf": getattr(v, "enf_solo_half", False),
        "hasLoc": getattr(v, "has_loc", False),
    }


def serialize_recommended_village(item: dict, *, include_reasons: bool) -> dict:
    v = item.get("village")
    if v is None and item.get("village_id"):
        v = {"id": item["village_id"], "nom": item["village_id"]}

    return {
        "village": village_summary(v),
        "score": item.get("score", 0.0),
        "estimatedTotal": item.get("estimated_total"),
        "bookingUrl": item.get("booking_url") or "",
        "rank": item.get("rank", 0),
        "reasons": (item.get("reasons") or []) if include_reasons else [],
        "warnings": (item.get("warnings") or []) if include_reasons else [],
    }


def serialize_reco_result(result, *, include_reasons: bool) -> dict:
    """Serialize a `RecoResult`-like object to the Phase-2 envelope."""
    return {
        "villages": [
            serialize_recommended_village(item, include_reasons=include_reasons)
            for item in getattr(result, "villages", []) or []
        ],
        "strategy": getattr(result, "strategy", None),
        "confidence": getattr(result, "confidence", None),
        "totalScored": getattr(result, "total_scored", 0),
        "relaxedFilters": getattr(result, "relaxed_filters", []),
        "fallbackUsed": getattr(result, "fallback_used", False),
        "abGroup": getattr(result, "ab_group", None),
    }
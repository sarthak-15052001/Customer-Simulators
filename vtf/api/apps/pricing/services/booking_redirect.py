"""BookingRedirectService — bridges /estimate result and the VTF booking page.

Spec §US-2.8. The token is minted in <10 ms (no DB writes inside `mint_token`);
the row is created in a single INSERT afterwards (callers should use
`transaction.on_commit` if response time is critical).
"""
from __future__ import annotations

from apps.catalog.models import Village
from apps.pricing.models import BookingRedirectToken

from .booking_url import build_vtf_booking_url, hash_payload, mint_token


class BookingRedirectService:
    @staticmethod
    def create_token(
        *,
        village: Village,
        session_id: str,
        family: dict,
        dates: dict,
        context: dict,
    ) -> tuple[str, BookingRedirectToken, dict]:
        """Returns (token_str, db_row, params_used). Spec §US-2.8."""
        target, params = build_vtf_booking_url(
            village=village,
            family=family,
            dates=dates,
            saison_key=context.get("saisonKey", "ete"),
        )
        payload = {"family": family, "dates": dates, "context": context}
        digest = hash_payload(payload)
        token, expires_at = mint_token(
            village_id=village.id, session_id=session_id, payload_hash=digest
        )
        row = BookingRedirectToken.objects.create(
            token=token,
            village=village,
            session_id=session_id,
            payload=payload,
            target_url=target,
            expires_at=expires_at,
        )
        return token, row, params

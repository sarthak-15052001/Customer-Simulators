"""Thin Brevo transactional-email client.

Uses the raw REST endpoint (POST /v3/smtp/email) so we have zero extra
dependencies. The `sib_api_v3_sdk` package is NOT installed in the venv;
we call the API directly with `requests`.

Config is read from Django settings:
  BREVO_API_KEY   — required
  BREVO_SENDER_EMAIL — defaults to "noreply@vtf-vacances.com"
  BREVO_SENDER_NAME  — defaults to "VTF Vacances"
"""
from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

BREVO_SMTP_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoError(Exception):
    """Raised when Brevo returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Brevo API error {status_code}: {detail}")


def send_transactional_email(
    *,
    to_email: str,
    subject: str,
    html_content: str,
    sender_email: str | None = None,
    sender_name: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Send one transactional email via Brevo.

    Returns the parsed JSON response body (contains `messageId`).
    Raises `BrevoError` on HTTP errors; lets `requests` exceptions propagate
    for network-level failures.
    """
    
    api_key = getattr(settings, "BREVO_API_KEY", "")
    if not api_key or api_key.strip() == "":
        error_msg = (
            "BREVO_API_KEY is not configured. "
            "Please set BREVO_API_KEY in your .env file or Django settings."
        )
        raise BrevoError(0, error_msg)

    sender = {
        "email": sender_email or getattr(settings, "BREVO_SENDER_EMAIL", "noreply@vtf-vacances.com"),
        "name": sender_name or getattr(settings, "BREVO_SENDER_NAME", "VTF Vacances"),
    }
    
    # Validate API key format
    if not api_key.startswith("xkeysib-"):
        error_msg = (
            "Invalid BREVO_API_KEY format. "
            "API key should start with 'xkeysib-'. "
            "Check your .env file or Django settings."
        )
        raise BrevoError(0, error_msg)

    payload: dict = {
        "sender": sender,
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }
    if tags:
        payload["tags"] = tags

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key,
    }
    
    try:
        response = requests.post(BREVO_SMTP_URL, json=payload, headers=headers, timeout=15)
    except requests.exceptions.Timeout:
        error_msg = "Brevo API request timed out (15 seconds). Try again later."
        raise BrevoError(504, error_msg)
    except requests.exceptions.ConnectionError as e:
        error_msg = f"Connection error to Brevo API: {str(e)}"
        raise BrevoError(503, error_msg)
    except requests.exceptions.RequestException as e:
        error_msg = f"Request error: {str(e)}"
        raise BrevoError(500, error_msg)

    if not response.ok:
        try:
            error_data = response.json()
            detail = error_data.get("message") or error_data.get("detail") or response.text[:256]
        except Exception:
            detail = response.text[:256]
        
        error_msg = f"Brevo API returned {response.status_code}: {detail}"
        
        lower_detail = detail.lower()

        # Add specific error handling for common status codes. Brevo can return
        # IP allowlist failures as 401, so keep that cause distinct from bad keys.
        if response.status_code == 401:
            if "unrecognised ip" in lower_detail or "authorized_ips" in lower_detail:
                error_msg = f"Unauthorized: Brevo IP allowlist rejected this server. {detail}"
            else:
                error_msg = (
                    "Unauthorized: Invalid or expired BREVO_API_KEY. "
                    f"Brevo detail: {detail}"
                )
        elif response.status_code == 403:
            error_msg = "Forbidden: Check Brevo account permissions and IP allowlist settings."
        elif response.status_code == 429:
            error_msg = "Rate limited by Brevo. Please wait before retrying."
        elif response.status_code == 500:
            error_msg = "Brevo API server error. Try again later."
        elif response.status_code == 503:
            error_msg = "Brevo API temporarily unavailable. Try again later."
        
        logger.error("Brevo send failed: %s %s", response.status_code, detail)
        raise BrevoError(response.status_code, error_msg)

    message_id = response.json().get("messageId", "UNKNOWN")
    
    logger.info("Brevo email sent to %s — messageId: %s", to_email, message_id)
    return response.json()

"""Shared helpers for Discord webhook notifications."""
from __future__ import annotations

import os
import socket
from typing import Any

from django.conf import settings


def get_notification_origin() -> dict[str, str]:
    """Return a stable origin label for outbound staff notifications."""
    configured_environment = (
        getattr(settings, "NOTIFICATION_ENVIRONMENT_NAME", "")
        or os.environ.get("NOTIFICATION_ENVIRONMENT_NAME", "")
        or ("local" if getattr(settings, "DEBUG", False) else "production")
    )
    environment = (
        "production"
        if str(configured_environment).strip().lower() in {"prod", "production"}
        else "local"
    )
    domain = (
        getattr(settings, "NOTIFICATION_ORIGIN_DOMAIN", "")
        or os.environ.get("NOTIFICATION_ORIGIN_DOMAIN", "")
        or os.environ.get("PUBLIC_ORIGIN_DOMAIN", "")
        or os.environ.get("PUBLIC_DOMAIN", "")
        or ""
    )
    ip_address = (
        getattr(settings, "NOTIFICATION_ORIGIN_IP", "")
        or os.environ.get("NOTIFICATION_ORIGIN_IP", "")
        or os.environ.get("PUBLIC_ORIGIN_IP", "")
        or ""
    )

    if not domain:
        domain = socket.gethostname()
    if not ip_address:
        try:
            ip_address = socket.gethostbyname(socket.gethostname())
        except OSError:
            ip_address = "unknown"

    return {
        "environment": environment,
        "domain": str(domain).strip() or "unknown",
        "ip": str(ip_address).strip() or "unknown",
    }


def origin_field() -> dict[str, Any]:
    """Build the Discord embed field that identifies the sending environment."""
    origin = get_notification_origin()
    value = (
        f"Environment: `{origin['environment']}`\n"
        f"Domain: `{origin['domain']}`\n"
        f"IP: `{origin['ip']}`"
    )
    return {"name": "Environment", "value": value[:1024], "inline": False}


def add_origin_to_embeds(payload: dict[str, Any]) -> dict[str, Any]:
    """Add origin metadata to each Discord embed payload in-place."""
    for embed in payload.get("embeds") or []:
        fields = embed.setdefault("fields", [])
        if not any(field.get("name") == "Environment" for field in fields):
            fields.insert(0, origin_field())
    return payload

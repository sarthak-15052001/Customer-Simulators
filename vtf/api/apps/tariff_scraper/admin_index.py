"""Wraps ``admin.site.index`` to add the price-health summary to its context.

Why patch instead of overriding admin/index.html directly: the built-in
index view (django.contrib.admin.sites.AdminSite.index) already accepts an
``extra_context`` dict and the template already renders whatever is in
context — we just need the summary counts available under a known key
("tariff_health_summary") the first time the client opens the admin.
This avoids re-implementing contrib.admin's app-list markup, which is
what tends to break on Django version bumps.

templates/admin/index.html (in this project) extends the stock
admin/index.html and reads ``tariff_health_summary`` to render the
"quick insights on login" banner.
"""
from __future__ import annotations

import logging

from django.contrib import admin

logger = logging.getLogger(__name__)

_PATCH_MARKER = "_tariff_health_patched"


def patch_admin_index() -> None:
    site = admin.site
    if getattr(site, _PATCH_MARKER, False):
        return  # already patched (e.g. autoreload re-import)

    original_index = site.index

    def index_with_health(request, extra_context=None):
        extra_context = dict(extra_context or {})
        try:
            from apps.tariff_scraper.services.dashboard import compute_village_health

            extra_context["tariff_health_summary"] = compute_village_health()
        except Exception:
            # Never let a dashboard aggregation bug break the whole admin home.
            logger.exception("Failed to compute tariff price-health summary")
        return original_index(request, extra_context=extra_context)

    site.index = index_with_health
    setattr(site, _PATCH_MARKER, True)


patch_admin_index()

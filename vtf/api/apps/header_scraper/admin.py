"""Django admin for published banners and scrape history."""
from __future__ import annotations

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse

from apps.header_scraper.models import HeaderBanner, HeaderBannerSnapshot


@admin.register(HeaderBanner)
class HeaderBannerAdmin(admin.ModelAdmin):
    list_display = [
        "language",
        "is_active",
        "scraped_at",
        "content_hash_short",
        "plain_preview",
    ]
    list_filter = ["language", "is_active"]
    search_fields = ["plain_text", "source_url", "content_hash"]
    readonly_fields = [
        "language",
        "segments",
        "plain_text",
        "source_url",
        "content_hash",
        "scraped_at",
        "created_at",
        "updated_at",
    ]

    @admin.display(description="Hash")
    def content_hash_short(self, obj: HeaderBanner) -> str:
        return (obj.content_hash or "")[:12]

    @admin.display(description="Text")
    def plain_preview(self, obj: HeaderBanner) -> str:
        text = obj.plain_text or ""
        return text if len(text) <= 80 else text[:77] + "…"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "scrape-now/",
                self.admin_site.admin_view(self.scrape_now),
                name="header_scraper_headerbanner_scrape_now",
            ),
        ]
        return custom + urls

    def scrape_now(self, request):
        from apps.header_scraper.tasks import task_scrape_header_banner

        try:
            async_result = task_scrape_header_banner.delay()
            messages.success(
                request,
                f"Queued header banner scrape (task_id={async_result.id}).",
            )
        except Exception as exc:
            # Fallback: run inline if broker unavailable.
            from apps.header_scraper.services.sync import sync_all_languages

            result = sync_all_languages()
            messages.warning(
                request,
                f"Celery unavailable ({exc}); ran inline. ok={result.get('ok')}",
            )
        return HttpResponseRedirect(
            reverse("admin:header_scraper_headerbanner_changelist")
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["scrape_now_url"] = reverse(
            "admin:header_scraper_headerbanner_scrape_now"
        )
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(HeaderBannerSnapshot)
class HeaderBannerSnapshotAdmin(admin.ModelAdmin):
    change_list_template = "admin/header_scraper/base_change_list.html"
    list_display = [
        "id",
        "language",
        "status",
        "scraped_at",
        "content_hash_short",
        "error_short",
    ]
    list_filter = ["language", "status"]
    search_fields = ["plain_text", "error", "content_hash", "source_url"]
    readonly_fields = [
        "language",
        "status",
        "content_hash",
        "plain_text",
        "segments",
        "source_url",
        "error",
        "scraped_at",
    ]

    @admin.display(description="Hash")
    def content_hash_short(self, obj: HeaderBannerSnapshot) -> str:
        return (obj.content_hash or "")[:12]

    @admin.display(description="Error")
    def error_short(self, obj: HeaderBannerSnapshot) -> str:
        err = obj.error or ""
        return err if len(err) <= 60 else err[:57] + "…"

    def get_urls(self):
        urls = super().get_urls()
        from apps.header_scraper.admin_urls import urlpatterns as control_urls
        return control_urls + urls

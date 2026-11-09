"""Django admin for scraper models (Phase 3)."""
from __future__ import annotations

from django.contrib import admin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils import timezone as dj_timezone
from apps.scraper.models import (
    CandidateFilterRule,
    PriceChangeAlert,
    ScrapingCandidate,
    ScrapingImportLog,
    ScrapingJob,
)
from apps.scraper.services.filter_rules import apply_rules_retroactively

class ScrapingCandidateInline(admin.TabularInline):
    model = ScrapingCandidate
    extra = 0
    fields = ("nom", "source", "status", "price_adult", "price_child", "match_confidence")
    readonly_fields = ("source", "match_confidence")
    show_change_link = True


@admin.register(ScrapingJob)
class ScrapingJobAdmin(admin.ModelAdmin):
    change_list_template = "admin/scraper/base_change_list.html"
    list_display = ("id", "target_type", "target_id", "status", "triggered_by", "created_at")
    list_filter = ("status", "target_type")
    search_fields = ("id", "target_id", "triggered_by")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    inlines = (ScrapingCandidateInline,)
    readonly_fields = ("created_at",)

    def get_urls(self):
        urls = super().get_urls()
        from apps.scraper.admin_urls import urlpatterns as custom_urls
        return custom_urls + urls


@admin.register(ScrapingCandidate)
class ScrapingCandidateAdmin(admin.ModelAdmin):
    list_display = (
        "nom",
        "visibility_button",
        "region",
        "source",
        "status",
        "price_adult",
        "price_child",
        "match_confidence",
    )
    list_filter = ("status", "source", "region")
    search_fields = ("id", "nom", "source_id", "matched_activity_code")
    autocomplete_fields = ("village", "job")
    actions = ("hide_selected_candidates", "unhide_selected_candidates")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/hide/",
                self.admin_site.admin_view(self.hide_candidate_view),
                name="scraper_scrapingcandidate_hide",
            ),
            path(
                "<path:object_id>/unhide/",
                self.admin_site.admin_view(self.unhide_candidate_view),
                name="scraper_scrapingcandidate_unhide",
            ),
        ]
        return custom_urls + urls

    @admin.display(description="Action")
    def visibility_button(self, obj):
        if obj.status == "imported":
            return "-"
        if obj.status == "hidden":
            url = reverse("admin:scraper_scrapingcandidate_unhide", args=[obj.pk])
            label = "Unhide"
            title = f"Unhide {obj.nom}"
            color = "#0b6bcb"
        else:
            url = reverse("admin:scraper_scrapingcandidate_hide", args=[obj.pk])
            label = "Hide"
            title = f"Hide {obj.nom}"
            color = "#ba2121"
        return format_html(
            '<button type="submit" formaction="{}" formmethod="post" '
            'class="button" title="{}" style="min-width:72px; padding:3px 8px; color:{};">{}</button>',
            url,
            title,
            color,
            label,
        )

    def hide_candidate_view(self, request, object_id):
        candidate = get_object_or_404(ScrapingCandidate, pk=object_id)
        if request.method != "POST":
            return redirect(
                reverse("admin:scraper_scrapingcandidate_changelist")
            )

        if candidate.status == "imported":
            messages.warning(
                request,
                f"{candidate.nom} is already imported and cannot be hidden.",
            )
        elif candidate.status == "hidden":
            messages.info(request, f"{candidate.nom} is already hidden.")
        else:
            actor = request.user.email or request.user.get_username()
            candidate.status = "hidden"
            candidate.reviewed_by = actor
            candidate.reviewed_at = dj_timezone.now()
            candidate.edits = {"reason": "Hidden from Django admin"}
            candidate.save(
                update_fields=["status", "reviewed_by", "reviewed_at", "edits"]
            )
            ScrapingImportLog.objects.create(
                job=candidate.job,
                candidate=candidate,
                action="hide",
                actor=actor,
                reason="Hidden from Django admin",
            )
            messages.success(request, f"{candidate.nom} hidden.")

        return redirect(reverse("admin:scraper_scrapingcandidate_changelist"))

    def unhide_candidate_view(self, request, object_id):
        candidate = get_object_or_404(ScrapingCandidate, pk=object_id)
        if request.method != "POST":
            return redirect(
                reverse("admin:scraper_scrapingcandidate_changelist")
            )

        if candidate.status != "hidden":
            messages.info(request, f"{candidate.nom} is not hidden.")
        else:
            actor = request.user.email or request.user.get_username()
            candidate.status = "new"
            candidate.reviewed_by = actor
            candidate.reviewed_at = dj_timezone.now()
            candidate.edits = {"reason": "Unhidden from Django admin"}
            candidate.save(
                update_fields=["status", "reviewed_by", "reviewed_at", "edits"]
            )
            ScrapingImportLog.objects.create(
                job=candidate.job,
                candidate=candidate,
                action="unhide",
                actor=actor,
                reason="Unhidden from Django admin",
            )
            messages.success(request, f"{candidate.nom} unhidden.")

        return redirect(reverse("admin:scraper_scrapingcandidate_changelist"))

    @admin.action(description="Hide selected scraped activities")
    def hide_selected_candidates(self, request, queryset):
        actor = request.user.email or request.user.get_username()
        targets = list(queryset.exclude(status__in=("imported", "hidden")))
        updated = queryset.exclude(status__in=("imported", "hidden")).update(
            status="hidden",
            reviewed_by=actor,
            reviewed_at=dj_timezone.now(),
        )
        ScrapingImportLog.objects.bulk_create(
            [
                ScrapingImportLog(
                    job=candidate.job,
                    candidate=candidate,
                    action="hide",
                    actor=actor,
                    reason="Hidden from Django admin (bulk action)",
                )
                for candidate in targets
            ]
        )
        self.message_user(request, f"{updated} scraped activities hidden.")

    @admin.action(description="Unhide selected scraped activities")
    def unhide_selected_candidates(self, request, queryset):
        actor = request.user.email or request.user.get_username()
        targets = list(queryset.filter(status="hidden"))
        updated = queryset.filter(status="hidden").update(
            status="new",
            reviewed_by=actor,
            reviewed_at=dj_timezone.now(),
        )
        ScrapingImportLog.objects.bulk_create(
            [
                ScrapingImportLog(
                    job=candidate.job,
                    candidate=candidate,
                    action="unhide",
                    actor=actor,
                    reason="Unhidden from Django admin (bulk action)",
                )
                for candidate in targets
            ]
        )
        self.message_user(request, f"{updated} scraped activities unhidden.")


@admin.register(PriceChangeAlert)
class PriceChangeAlertAdmin(admin.ModelAdmin):
    list_display = ("id", "activity", "field", "old_value", "new_value", "status", "scraped_at")
    list_filter = ("status", "field", "source")
    search_fields = ("activity__nom",)
    ordering = ("-scraped_at",)


@admin.register(ScrapingImportLog)
class ScrapingImportLogAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "job", "candidate", "action", "actor")
    list_filter = ("action",)
    search_fields = ("actor", "reason", "candidate__nom")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(CandidateFilterRule)
class CandidateFilterRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "field",
        "pattern",
        "action",
        "scope_region",
        "scope_source",
        "is_active",
        "priority",
    )
    list_editable = ("is_active", "priority")
    list_filter = ("action", "field", "is_active")
    search_fields = ("name", "pattern", "scope_region", "scope_source")
    ordering = ("priority", "name")
    actions = ("apply_rule_to_existing_candidates",)

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user.email or request.user.get_username()
        super().save_model(request, obj, form, change)

    @admin.action(description="Apply selected rule(s) to existing candidates")
    def apply_rule_to_existing_candidates(self, request, queryset):
        """Retroactively hide/exclude-mark already-scraped candidates that
        match the selected rule(s). "Exclude" rules are applied here as a
        hide (the row already exists, so it can't be un-created) with a
        note in `edits` for traceability.
        """
        actor = request.user.email or request.user.get_username()
        # Intentionally does not filter by is_active: this lets staff test
        # a not-yet-activated rule against existing candidates before
        # flipping it on globally.
        rules = list(queryset)
        affected, _messages = apply_rules_retroactively(rules, actor=actor)
        self.message_user(request, f"{affected} existing candidates hidden by selected rule(s).")

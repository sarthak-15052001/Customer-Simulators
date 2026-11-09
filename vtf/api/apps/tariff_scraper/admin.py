from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from django.utils import timezone

from apps.tariff_scraper.models import (
    STATUS_APPROVED,
    STATUS_PENDING,
    FormatChangeLog,
    PriceSnapshot,
    TariffApproval,
    VillageTarif,
)
from apps.tariff_scraper.services.approval import (
    ApprovalError,
    approve_tariff_approval,
    reject_tariff_approval,
    revert_tariff_approval,
)
from apps.tariff_scraper.admin_display import (
    download_proposed_bands_json,
    download_proposed_season_tarifs_json,
    fr_date,
    render_bands_grid,
    render_season_tarifs_notes,
    # render_tarifs_comparison,  # hidden: season comparison table (see TariffApprovalAdmin)
    render_tarifs_grid,
)


# Date columns go through `fr_date` rather than the raw model field so the
# list view matches the JJ/MM/AAAA used by the JSON-driven grids below and by
# the VTF booking funnel. Model fields alone would already be localized by
# config/formats/fr, but only the ones Django renders itself — routing every
# column through one helper is what keeps the two paths from drifting apart.
def _fr_date_column(field: str, description: str, *, ordering: str | None = None):
    @admin.display(description=description, ordering=ordering or field)
    def column(self, obj):
        return fr_date(getattr(obj, field, None))

    column.__name__ = f"{field}_fr"
    return column


@admin.register(PriceSnapshot)
class PriceSnapshotAdmin(admin.ModelAdmin):
    change_list_template = "admin/tariff_scraper/base_change_list.html"
    list_display = [
        "village_id",
        "formule",
        "unit_type",
        "source_page",
        "scrape_source",
        "date_start_fr",
        "date_end_fr",
        "scraped_price",
        "is_available",
        "derivation",
        "scraped_at_fr",
    ]
    list_filter = [
        "formule",
        "unit_type",
        "source_page",
        "scrape_source",
        "is_available",
        "derivation",
    ]
    # `village__id`, not `village_id`: on a ForeignKey the attname resolves
    # back to the relation, so the admin's generated `village_id__icontains`
    # lands on the FK itself and raises FieldError — every search here was a
    # 500. Traversing the relation applies the lookup to Village's CharField pk.
    search_fields = ["village__id", "village__nom", "date_label"]
    ordering = ["-scraped_at"]
    readonly_fields = ["scraped_at"]

    date_start_fr = _fr_date_column("date_start", "Date debut")
    date_end_fr = _fr_date_column("date_end", "Date fin")
    scraped_at_fr = _fr_date_column("scraped_at", "Scrape le")

    def get_urls(self):
        urls = super().get_urls()
        from apps.tariff_scraper.admin_urls import urlpatterns as custom_urls
        return custom_urls + urls



@admin.register(TariffApproval)
class TariffApprovalAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "village_id",
        "status",
        "bands_count",
        "created_at_fr",
        "reviewed_at_fr",
        "reviewed_by",
    ]
    list_filter = ["status"]
    # `village__id`, not `village_id`: on a ForeignKey the attname resolves
    # back to the relation, so the admin's generated `village_id__icontains`
    # lands on the FK itself and raises FieldError — every search here was a
    # 500. Traversing the relation applies the lookup to Village's CharField pk.
    search_fields = ["village__id", "village__nom", "reject_reason"]
    ordering = ["-created_at"]
    raw_id_fields = ["reviewed_by"]
    # NOTE: this class used to declare `readonly_fields` twice; the first list
    # was dead (the second rebound the name), so anything added to it silently
    # did nothing. Merged into this single declaration.
    readonly_fields = [
        # `status` is readonly on purpose — see the "Approve / reject" section.
        "status",
        "created_at",
        "reviewed_at",
        "reverted_at",
        "reverted_by",
        "approve_action",
        "proposed_bands_grid",
        "proposed_season_tarifs_grid",
        "season_tarifs_notes_grid",
        "revert_action",
        # "proposed_tarifs_comparison",  # hidden: clients use date bands, not season fallback
        # "previous_village_tarifs_grid",  # hidden: season snapshot not needed in review UI
    ]

    created_at_fr = _fr_date_column("created_at", "Cree le")
    reviewed_at_fr = _fr_date_column("reviewed_at", "Revu le")
    reverted_at_fr = _fr_date_column("reverted_at", "Annule le")

    actions = ["approve_selected_approvals", "revert_selected_approvals"]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "village",
                    "status",
                    "approve_action",
                    "source_url",
                    "bands_count",
                    "reject_reason",
                )
            },
        ),
        (
            "Proposed pricing changes",
            {
                "fields": (
                    # "proposed_tarifs_comparison",  # hidden: season vs current confuses reviewers
                    "proposed_bands_grid",
                    "proposed_season_tarifs_grid",
                    "season_tarifs_notes_grid",
                )
            },
        ),
        (
            "Review audit",
            {
                "fields": (
                    # "previous_village_tarifs_grid",  # hidden: restore if season audit needed
                    "created_at",
                    "reviewed_at",
                    "reviewed_by",
                    "revert_action",
                    "reverted_at",
                    "reverted_by",
                )
            },
        ),
    )

    def get_urls(self):
        urls = super().get_urls()
        opts = self.model._meta
        custom = [
            path(
                "<path:object_id>/download/proposed-bands.json",
                self.admin_site.admin_view(download_proposed_bands_json),
                name=f"{opts.app_label}_{opts.model_name}_download_bands",
            ),
            path(
                "<path:object_id>/download/proposed-season-tarifs.json",
                self.admin_site.admin_view(download_proposed_season_tarifs_json),
                name=f"{opts.app_label}_{opts.model_name}_download_season_tarifs",
            ),
            path(
                "<path:object_id>/approve/",
                self.admin_site.admin_view(self.approve_view),
                name=f"{opts.app_label}_{opts.model_name}_approve",
            ),
            path(
                "<path:object_id>/reject/",
                self.admin_site.admin_view(self.reject_view),
                name=f"{opts.app_label}_{opts.model_name}_reject",
            ),
            path(
                "<path:object_id>/revert/",
                self.admin_site.admin_view(self.revert_view),
                name=f"{opts.app_label}_{opts.model_name}_revert",
            ),
        ]
        return custom + urls

    # ── Reviewer defaults ────────────────────────────────────────────────
    # `reviewed_by` is a raw_id field, so staff had to look their own user id
    # up and paste it. Both hooks below fill it from the signed-in profile;
    # neither overwrites a reviewer that is already set, so reassigning a
    # review to someone else by hand still works.

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.setdefault("reviewed_by", request.user.pk)
        return initial

    # NOTE: `save_model` used to backfill `reviewed_by` from the session
    # whenever status was non-pending. That made sense while status was an
    # editable dropdown — it stamped the person flipping it. Now that every
    # decision goes through approve/reject/revert, which set the reviewer
    # themselves, the backfill would only ever fire on an approval reviewed by
    # someone else (or by a script), and would re-attribute it to whoever
    # happened to open and save the form. Removed; the initial-data hook above
    # is enough.

    # ── Approve / reject ─────────────────────────────────────────────────
    # `status` is readonly (see readonly_fields). It used to be an editable
    # dropdown, which was a trap: flipping it to "approved" changed the label
    # and nothing else — no VillageTarif rows activated, no Village.tarifs
    # rewritten — because `approve_tariff_approval` was only ever reachable
    # from the REST endpoint. A proposal looked applied while pricing kept
    # serving the stale season buckets. Status now only moves through the
    # services, via these buttons.

    @admin.display(description="Approuver")
    def approve_action(self, obj):
        if obj is None or not obj.pk:
            return "-"
        if obj.status != STATUS_PENDING:
            return format_html(
                '<span style="color:#6b7280;">'
                "Deja arbitre (statut : {}).</span>",
                obj.status,
            )
        return format_html(
            '<a href="{}" class="button" '
            'style="background:#1a7f37;color:#fff;padding:8px 12px;'
            'border-radius:4px;text-decoration:none;">Approuver</a>'
            '<a href="{}" class="button" '
            'style="background:#6b7280;color:#fff;padding:8px 12px;'
            'border-radius:4px;text-decoration:none;margin-left:10px;">Rejeter</a>'
            '<p style="margin:8px 0 0 0;color:#6b7280;font-size:12px;">'
            "Approuver active les bandes datees et met a jour Village.tarifs. "
            "Rejeter ne touche a aucun prix.</p>",
            reverse("admin:tariff_scraper_tariffapproval_approve", args=[obj.pk]),
            reverse("admin:tariff_scraper_tariffapproval_reject", args=[obj.pk]),
        )

    def _decision_view(self, request, object_id, *, action):
        """Shared GET-confirms / POST-acts flow for approve and reject."""
        approval = get_object_or_404(TariffApproval, pk=object_id)
        opts = self.model._meta
        change_url = reverse(
            f"admin:{opts.app_label}_{opts.model_name}_change", args=[approval.pk]
        )

        if not self.has_change_permission(request, approval):
            messages.error(request, "Permission refusee.")
            return HttpResponseRedirect(change_url)

        if request.method == "POST":
            try:
                if action == "approve":
                    approve_tariff_approval(approval, user=request.user)
                    messages.success(
                        request,
                        f"Approbation #{approval.pk} appliquee : bandes datees "
                        f"activees et tarifs de {approval.village_id} mis a jour.",
                    )
                else:
                    reject_tariff_approval(
                        approval,
                        user=request.user,
                        reason=(request.POST.get("reject_reason") or "").strip(),
                    )
                    messages.success(
                        request, f"Approbation #{approval.pk} rejetee. Aucun prix modifie."
                    )
            except ApprovalError as exc:
                messages.error(request, str(exc))
            return HttpResponseRedirect(change_url)

        return TemplateResponse(
            request,
            "admin/tariff_scraper/decision_confirmation.html",
            {
                **self.admin_site.each_context(request),
                "title": (
                    f"Approuver la proposition #{approval.pk} ?"
                    if action == "approve"
                    else f"Rejeter la proposition #{approval.pk} ?"
                ),
                "action": action,
                "approval": approval,
                "bands_grid": render_bands_grid(approval.proposed_bands),
                "season_grid": render_tarifs_grid(
                    approval.proposed_season_tarifs,
                    empty="Aucun tarif saison propose.",
                ),
                "notes_grid": render_season_tarifs_notes(approval.season_tarifs_notes),
                "change_url": change_url,
                "opts": opts,
            },
        )

    def approve_view(self, request, object_id):
        return self._decision_view(request, object_id, action="approve")

    def reject_view(self, request, object_id):
        return self._decision_view(request, object_id, action="reject")

    @admin.action(description="Approuver les propositions selectionnees")
    def approve_selected_approvals(self, request, queryset):
        done = 0
        for approval in queryset.filter(status=STATUS_PENDING).order_by("created_at"):
            try:
                approve_tariff_approval(approval, user=request.user)
            except ApprovalError as exc:
                messages.error(request, f"#{approval.pk} : {exc}")
            else:
                done += 1
        if done:
            messages.success(request, f"{done} proposition(s) approuvee(s).")
        else:
            messages.info(request, "Aucune proposition en attente dans la selection.")

    # ── Revert ───────────────────────────────────────────────────────────

    @admin.display(description="Annuler l'approbation")
    def revert_action(self, obj):
        """Button linking to the confirmation page.

        Rendered as a link rather than an inline <form>: the change page is
        already wrapped in one, and nested forms are invalid HTML — the inner
        submit silently posts to the outer action instead.
        """
        if obj is None or not obj.pk:
            return "-"
        if obj.status != STATUS_APPROVED:
            return format_html(
                '<span style="color:#6b7280;">'
                "Disponible uniquement sur une approbation appliquee "
                '(statut actuel : {}).</span>',
                obj.status,
            )
        url = reverse("admin:tariff_scraper_tariffapproval_revert", args=[obj.pk])
        return format_html(
            '<a href="{}" class="button" '
            'style="background:#ba2121;color:#fff;padding:8px 12px;'
            'border-radius:4px;text-decoration:none;">'
            "Annuler l'approbation</a>"
            '<p style="margin:8px 0 0 0;color:#6b7280;font-size:12px;">'
            "Restaure les tarifs saison d'avant, desactive les bandes datees "
            "creees et remet la generation precedente.</p>",
            url,
        )

    def revert_view(self, request, object_id):
        """GET shows a confirmation page, POST performs the revert."""
        approval = get_object_or_404(TariffApproval, pk=object_id)
        opts = self.model._meta
        change_url = reverse(
            f"admin:{opts.app_label}_{opts.model_name}_change", args=[approval.pk]
        )

        if not self.has_change_permission(request, approval):
            messages.error(request, "Permission refusee.")
            return HttpResponseRedirect(change_url)

        if request.method == "POST":
            try:
                revert_tariff_approval(approval, user=request.user)
            except ApprovalError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f"Approbation #{approval.pk} annulee. Les tarifs de "
                    f"{approval.village_id} sont revenus a leur etat precedent.",
                )
            return HttpResponseRedirect(change_url)

        return TemplateResponse(
            request,
            "admin/tariff_scraper/revert_confirmation.html",
            {
                **self.admin_site.each_context(request),
                "title": f"Annuler l'approbation #{approval.pk} ?",
                "approval": approval,
                "previous_tarifs": render_tarifs_grid(
                    approval.previous_village_tarifs,
                    empty="Aucun tarif saison enregistre avant approbation.",
                ),
                "current_tarifs": render_tarifs_grid(
                    approval.proposed_season_tarifs,
                    empty="Aucun tarif saison actif.",
                ),
                "change_url": change_url,
                "opts": opts,
            },
        )

    @admin.action(description="Annuler l'approbation (revert)")
    def revert_selected_approvals(self, request, queryset):
        done, failed = 0, 0
        for approval in queryset.order_by("-reviewed_at"):
            try:
                revert_tariff_approval(approval, user=request.user)
            except ApprovalError as exc:
                failed += 1
                messages.error(request, f"#{approval.pk} : {exc}")
            else:
                done += 1
        if done:
            messages.success(request, f"{done} approbation(s) annulee(s).")
        if not done and not failed:
            messages.info(request, "Aucune approbation selectionnee.")

    @admin.display(description="Proposed date bands")
    def proposed_bands_grid(self, obj):
        download_url = None
        if obj and obj.pk:
            download_url = reverse(
                f"admin:tariff_scraper_tariffapproval_download_bands",
                args=[obj.pk],
            )
        return render_bands_grid(obj.proposed_bands, download_url=download_url)

    @admin.display(description="Proposed season tarifs")
    def proposed_season_tarifs_grid(self, obj):
        download_url = None
        if obj and obj.pk:
            download_url = reverse(
                f"admin:tariff_scraper_tariffapproval_download_season_tarifs",
                args=[obj.pk],
            )
        return render_tarifs_grid(
            obj.proposed_season_tarifs,
            download_url=download_url,
        )

    @admin.display(description="Fiabilite des saisons proposees")
    def season_tarifs_notes_grid(self, obj):
        return render_season_tarifs_notes(obj.season_tarifs_notes)

    # Hidden in admin UI: stay estimates use proposed date bands, not season tarifs.
    # Uncomment readonly_fields/fieldset entries above to restore this table.
    # @admin.display(description="Current vs proposed season tarifs")
    # def proposed_tarifs_comparison(self, obj):
    #     current = obj.previous_village_tarifs
    #     if current is None and obj.village_id:
    #         current = obj.village.tarifs
    #     return render_tarifs_comparison(current, obj.proposed_season_tarifs)

    # Hidden in admin UI: previous season tarifs are stored for audit but not shown here.
    # Uncomment readonly_fields/fieldset entries above to restore this table.
    # @admin.display(description="Previous village tarifs")
    # def previous_village_tarifs_grid(self, obj):
    #     return render_tarifs_grid(obj.previous_village_tarifs)


@admin.register(VillageTarif)
class VillageTarifAdmin(admin.ModelAdmin):
    list_display = [
        "village_id",
        "formule",
        "date_start_fr",
        "date_end_fr",
        "pricing_type",
        "unit_type",
        "price",
        "is_active",
        "effective_at_fr",
    ]
    list_filter = ["formule", "pricing_type", "is_active"]
    # `village__id`, not `village_id`: on a ForeignKey the attname resolves
    # back to the relation, so the admin's generated `village_id__icontains`
    # lands on the FK itself and raises FieldError — every search here was a
    # 500. Traversing the relation applies the lookup to Village's CharField pk.
    search_fields = ["village__id", "village__nom", "unit_type"]
    ordering = ["village_id", "formule", "date_start"]
    readonly_fields = ["effective_at", "source_snapshot"]

    date_start_fr = _fr_date_column("date_start", "Date debut")
    date_end_fr = _fr_date_column("date_end", "Date fin")
    effective_at_fr = _fr_date_column("effective_at", "Actif depuis")


@admin.register(FormatChangeLog)
class FormatChangeLogAdmin(admin.ModelAdmin):
    list_display = [
        "village_id",
        "change_type",
        "html_length",
        "table_count",
        "bands_scraped",
        "priced_bands",
        "detected_at_fr",
    ]
    list_filter = ["change_type"]
    # `village__id`, not `village_id`: on a ForeignKey the attname resolves
    # back to the relation, so the admin's generated `village_id__icontains`
    # lands on the FK itself and raises FieldError — every search here was a
    # 500. Traversing the relation applies the lookup to Village's CharField pk.
    search_fields = ["village__id", "village__nom", "source_url"]
    ordering = ["-detected_at"]
    readonly_fields = [
        "detected_at",
        "expected_markers",
        "found_markers",
        "missing_markers",
        "errors",
    ]

    detected_at_fr = _fr_date_column("detected_at", "Detecte le")

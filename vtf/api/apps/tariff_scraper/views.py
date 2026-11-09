"""Tariff Scraper API views.

All endpoints require staff Basic auth (`StaffAPIViewMixin`).

  POST /api/v4/tariff-scraper/scrape/
    Body: { "village_id": "lacanau" }   ← scrape a single catalog village
    Body: {}                             ← queue all 32 villages
    → queues a Celery task; scrape stages a pending TariffApproval.

  GET /api/v4/tariff-scraper/tariffs/
    → list all active VillageTarif rows (optional village_id / formule filters).

  GET /api/v4/tariff-scraper/tariffs/{village_id}/
    → returns all active VillageTarif rows for one village.

  GET  /api/v4/admin/tariff-scraper/approvals/
  GET  /api/v4/admin/tariff-scraper/approvals/{id}/
  POST /api/v4/admin/tariff-scraper/approvals/{id}/
       Body: { "action": "approve" | "reject" | "revert",
               "reject_reason"?: "..." }
       `revert` rolls an already-approved proposal back: restores
       Village.tarifs from the pre-approval snapshot, deactivates the bands it
       created and re-activates the previous generation.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.request import Request
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.tariff_scraper.models import TariffApproval, VillageTarif
from apps.tariff_scraper.serializers import (
    DryRunAlertResponseSerializer,
    DryRunAlertSerializer,
    FormatChangeLogSerializer,
    ScrapeRequestSerializer,
    ScrapeResponseSerializer,
    TariffApprovalActionSerializer,
    TariffApprovalSerializer,
    VillageTarifSerializer,
)
from apps.tariff_scraper.services.approval import (
    ApprovalError,
    approve_tariff_approval,
    reject_tariff_approval,
    revert_tariff_approval,
)
from apps.tariff_scraper.services.village_urls import VILLAGE_URLS, get_village_url
from common.permissions import StaffAPIViewMixin
from common.response import CustomResponse


class TariffScrapeView(StaffAPIViewMixin, APIView):
    """POST — trigger a tariff scrape job via Celery.

    Pass `village_id` (catalog Village.id) to scrape one village.
    Omit it (or pass empty string) to queue all 32 villages.
    Scrapes create PriceSnapshot + pending TariffApproval only.
    """

    @extend_schema(
        request=ScrapeRequestSerializer,
        responses={202: ScrapeResponseSerializer},
        tags=["v4"],
        summary="Trigger tariff scrape",
        description=(
            "Queues a Celery task to scrape live tarifs from the VTF website. "
            "Results are staged as a pending TariffApproval until staff approve. "
            "Provide catalog `village_id` (e.g. 'lacanau') for a single village, "
            "or omit to scrape all 32."
        ),
    )
    def post(self, request: Request) -> CustomResponse:
        serializer = ScrapeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        village_id = serializer.validated_data.get("village_id", "").strip()

        if village_id:
            if not get_village_url(village_id):
                return CustomResponse.error(
                    f"Unknown village_id '{village_id}'. Known: {sorted(VILLAGE_URLS.keys())}",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            from apps.tariff_scraper.tasks import task_scrape_village_tariffs
            async_result = task_scrape_village_tariffs.delay(village_id)
            return CustomResponse.success(
                f"Scrape queued for village '{village_id}'.",
                data={
                    "task_id": async_result.id,
                    "village_id": village_id,
                    "message": f"Scrape queued for village '{village_id}'.",
                },
                status_code=status.HTTP_202_ACCEPTED,
            )
        else:
            from apps.tariff_scraper.tasks import task_scrape_all_village_tariffs
            async_result = task_scrape_all_village_tariffs.delay()
            return CustomResponse.success(
                f"Scrape queued for all {len(VILLAGE_URLS)} villages.",
                data={
                    "task_id": async_result.id,
                    "village_id": None,
                    "message": f"Scrape queued for all {len(VILLAGE_URLS)} villages.",
                },
                status_code=status.HTTP_202_ACCEPTED,
            )


class AllVillageTariffsListView(StaffAPIViewMixin, APIView):
    """GET — list all active VillageTarif rows across villages."""

    @extend_schema(
        operation_id="v4_tariff_scraper_tariffs_list",
        parameters=[
            OpenApiParameter(
                name="village_id",
                location=OpenApiParameter.QUERY,
                description="Optional catalog village id filter, e.g. 'lacanau'",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="formule",
                location=OpenApiParameter.QUERY,
                description="Optional formule filter: PC, DP, or LOC",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="active_only",
                location=OpenApiParameter.QUERY,
                description="If true (default), only active tarifs. Pass false for history.",
                required=False,
                type=bool,
            ),
        ],
        responses={200: VillageTarifSerializer(many=True)},
        tags=["v4"],
        summary="List all scraped village tarifs",
        description=(
            "Returns approved VillageTarif rows for all villages (staff only). "
            "Optionally filter by village_id and/or formule."
        ),
    )
    def get(self, request: Request) -> CustomResponse:
        village_id = (request.query_params.get("village_id") or "").strip()
        formule = (request.query_params.get("formule") or "").strip().upper()
        active_only = request.query_params.get("active_only", "true").lower()
        active_only = active_only not in ("0", "false", "no")

        if village_id and not get_village_url(village_id):
            return CustomResponse.error(
                f"Unknown village_id '{village_id}'. Known: {sorted(VILLAGE_URLS.keys())}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if formule and formule not in ("PC", "DP", "LOC"):
            return CustomResponse.error(
                "formule must be one of: PC, DP, LOC.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        qs = VillageTarif.objects.select_related("source_snapshot", "village").order_by(
            "village_id", "formule", "date_start", "unit_type"
        )
        if active_only:
            qs = qs.filter(is_active=True)
        if village_id:
            qs = qs.filter(village_id=village_id)
        if formule:
            qs = qs.filter(formule=formule)

        data = VillageTarifSerializer(qs, many=True).data
        return CustomResponse.success(f"{len(data)} village tarifs.", data=data)


class VillageTariffListView(StaffAPIViewMixin, APIView):
    """GET — return all active VillageTarif rows for a village."""

    @extend_schema(
        operation_id="v4_tariff_scraper_tariffs_by_village",
        parameters=[
            OpenApiParameter(
                name="village_id",
                location=OpenApiParameter.PATH,
                description="Catalog village id, e.g. 'lacanau'",
                required=True,
                type=str,
            )
        ],
        responses={200: VillageTarifSerializer(many=True)},
        tags=["v4"],
        summary="List active tarifs for a village",
        description=(
            "Returns all currently active (approved) scraped tarifs for the given village. "
            "Includes PC (per_person), DP (per_person), and LOC (flat_unit) bands "
            "as available.  Ordered by formule → date_start → unit_type."
        ),
    )
    def get(self, request: Request, village_id: str) -> CustomResponse:
        if not get_village_url(village_id):
            return CustomResponse.error(
                f"Unknown village_id '{village_id}'. Known: {sorted(VILLAGE_URLS.keys())}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        qs = (
            VillageTarif.objects.filter(
                village_id=village_id,
                is_active=True,
            )
            .order_by("formule", "date_start", "unit_type")
            .select_related("source_snapshot")
        )
        serializer = VillageTarifSerializer(qs, many=True)
        return CustomResponse.success(
            "Active village tarifs fetched.",
            data=serializer.data,
        )


class TariffApprovalListView(StaffAPIViewMixin, APIView):
    """GET /api/v4/admin/tariff-scraper/approvals/ — list proposals."""

    @extend_schema(
        operation_id="v4_admin_tariff_approvals_list",
        parameters=[
            OpenApiParameter(
                name="status",
                location=OpenApiParameter.QUERY,
                description="Filter by status (default: pending). Pass empty to list all.",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="village_id",
                location=OpenApiParameter.QUERY,
                description="Filter by catalog village id",
                required=False,
                type=str,
            ),
        ],
        responses={200: TariffApprovalSerializer(many=True)},
        tags=["v4"],
        summary="List tariff scrape approvals",
    )
    def get(self, request: Request) -> CustomResponse:
        status_filter = request.query_params.get("status", "pending")
        village_id = (request.query_params.get("village_id") or "").strip()

        qs = TariffApproval.objects.select_related(
            "village", "reviewed_by", "reverted_by"
        ).order_by(
            "-created_at"
        )
        if status_filter:
            qs = qs.filter(status=status_filter)
        if village_id:
            qs = qs.filter(village_id=village_id)

        data = TariffApprovalSerializer(qs[:100], many=True).data
        return CustomResponse.success(f"{len(data)} tariff approvals.", data=data)


class TariffApprovalDetailView(StaffAPIViewMixin, APIView):
    """GET one approval; POST approve/reject."""

    @extend_schema(
        operation_id="v4_admin_tariff_approvals_retrieve",
        responses={200: TariffApprovalSerializer},
        tags=["v4"],
        summary="Get tariff scrape approval detail",
    )
    def get(self, request: Request, approval_id: int) -> CustomResponse:
        try:
            approval = TariffApproval.objects.select_related(
                "village", "reviewed_by", "reverted_by"
            ).get(pk=approval_id)
        except TariffApproval.DoesNotExist:
            return CustomResponse.error(
                f"Approval {approval_id} not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return CustomResponse.success(
            f"Approval {approval_id}.",
            data=TariffApprovalSerializer(approval).data,
        )

    @extend_schema(
        operation_id="v4_admin_tariff_approvals_action",
        request=TariffApprovalActionSerializer,
        responses={200: TariffApprovalSerializer},
        tags=["v4"],
        summary="Approve, reject or revert a tariff scrape proposal",
        description=(
            "On approve: activates VillageTarif bands and merges season prices into "
            "Village.tarifs (and villages.json fixture when writable). "
            "On reject: leaves live pricing unchanged. "
            "On revert: restores Village.tarifs from the pre-approval snapshot, "
            "deactivates the bands the approval created and re-activates the "
            "previous generation. Only valid on an approved proposal, and refused "
            "when a newer approved proposal exists for the same village."
        ),
    )
    def post(self, request: Request, approval_id: int) -> CustomResponse:
        serializer = TariffApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        reject_reason = serializer.validated_data.get("reject_reason", "")

        try:
            approval = TariffApproval.objects.select_related(
                "village", "reviewed_by", "reverted_by"
            ).get(pk=approval_id)
        except TariffApproval.DoesNotExist:
            return CustomResponse.error(
                f"Approval {approval_id} not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Dispatch every action explicitly. This used to be
        # `if approve: ... else: reject`, which would have silently rejected
        # any action added to the serializer's choices later on.
        try:
            if action == "approve":
                approval = approve_tariff_approval(approval, user=request.user)
                msg = f"Approval {approval_id} approved — VillageTarif + Village.tarifs updated."
            elif action == "revert":
                approval = revert_tariff_approval(approval, user=request.user)
                msg = (
                    f"Approval {approval_id} reverted — Village.tarifs restored and "
                    "the previous bands re-activated."
                )
            elif action == "reject":
                approval = reject_tariff_approval(
                    approval, user=request.user, reason=reject_reason
                )
                msg = f"Approval {approval_id} rejected."
            else:  # pragma: no cover — ChoiceField already rejects these
                return CustomResponse.error(
                    f"Unknown action '{action}'.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        except ApprovalError as exc:
            return CustomResponse.error(str(exc), status_code=status.HTTP_400_BAD_REQUEST)

        return CustomResponse.success(
            msg,
            data=TariffApprovalSerializer(approval).data,
        )


class FormatChangeLogView(StaffAPIViewMixin, APIView):
    """GET /api/v4/tariff-scraper/format-changes/ — list detected format changes.

    Query params:
      village_id  — filter by catalog village id
      change_type — filter by type: marker_missing, zero_prices, parse_failure, etc.
      limit       — max results (default 50)
    """

    @extend_schema(
        operation_id="v4_tariff_format_changes_list",
        parameters=[
            OpenApiParameter(
                name="village_id",
                location=OpenApiParameter.QUERY,
                description="Filter by catalog village id, e.g. 'lacanau'",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="change_type",
                location=OpenApiParameter.QUERY,
                description=(
                    "Filter by change type: marker_missing, zero_prices, "
                    "parse_failure, partial, hard_failure"
                ),
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="limit",
                location=OpenApiParameter.QUERY,
                description="Max results (default 50, max 200)",
                required=False,
                type=int,
            ),
        ],
        responses={200: FormatChangeLogSerializer(many=True)},
        tags=["v4"],
        summary="List detected format changes",
        description=(
            "Returns the audit trail of detected VTF page format changes. "
            "Each entry records what markers were expected vs found, "
            "HTML diagnostics, and error details."
        ),
    )
    def get(self, request: Request) -> CustomResponse:
        from apps.tariff_scraper.models import FormatChangeLog

        village_id = (request.query_params.get("village_id") or "").strip()
        change_type = (request.query_params.get("change_type") or "").strip()
        limit = request.query_params.get("limit", "50")

        try:
            limit = min(int(limit), 200)
        except (ValueError, TypeError):
            limit = 50

        qs = FormatChangeLog.objects.select_related("village").order_by("-detected_at")

        if village_id:
            if not get_village_url(village_id):
                return CustomResponse.error(
                    f"Unknown village_id '{village_id}'. Known: {sorted(VILLAGE_URLS.keys())}",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(village_id=village_id)

        if change_type:
            valid_types = [
                "marker_missing", "zero_prices", "parse_failure",
                "partial", "hard_failure",
            ]
            if change_type not in valid_types:
                return CustomResponse.error(
                    f"change_type must be one of: {', '.join(valid_types)}",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(change_type=change_type)

        data = FormatChangeLogSerializer(qs[:limit], many=True).data
        return CustomResponse.success(f"{len(data)} format change(s) logged.", data=data)
    
class DryRunAlertView(StaffAPIViewMixin, APIView):
    """POST /api/v4/tariff-scraper/dry-run/ — test alert pipeline with fake payload.

    Sends a Discord alert AND saves to FormatChangeLog (for non-success scenarios).
    Use this to verify the alert system end-to-end without hitting the real VTF site.

    Scenarios:
      hard_failure  → 🔴 RED (HTTP 404 / blocked)
      zero_prices   → 🔴 RED (page loaded, no prices)
      parse_failure → 🟡 YELLOW (dates/prices couldn't parse)
      marker_missing→ 🔴 RED (all grille markers gone from page)
      partial       → 🟡 YELLOW (some data with errors)
      success       → 🟢 GREEN (clean scrape OK)
      batch_summary → 🔴/🟡 (fake 32-village batch result)
    """

    @extend_schema(
        operation_id="v4_tariff_dry_run_alert",
        request=DryRunAlertSerializer,
        responses={200: DryRunAlertResponseSerializer},
        tags=["v4"],
        summary="Dry-run test alert pipeline",
        description=(
            "Sends a Discord alert + saves to FormatChangeLog using a fake payload. "
            "Use this to verify the alert system works end-to-end."
        ),
    )
    def post(self, request: Request) -> CustomResponse:
        from apps.tariff_scraper.services.alerts import (
            notify_scrape_failure,
            notify_scrape_success,
            notify_format_change,
            notify_batch_summary,
        )
        from apps.tariff_scraper.tasks import _log_format_change

        serializer = DryRunAlertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        scenario = serializer.validated_data["scenario"]
        village_id = serializer.validated_data.get("village_id", "lacanau")
        url = f"https://www.vtf-vacances.com/fr_FR/summer/village-vacances/test/{village_id}/fake"

        if scenario == "success":
            summary = {
                "village_id": village_id,
                "url": url,
                "priced_bands": 12,
                "bands_proposed": 10,
                "bands_scraped": 12,
                "approval_id": 999,
                "scrape_errors": [],
                "build_errors": [],
            }
            notify_scrape_success(summary)
            return CustomResponse.success(
                f"Success alert sent for village '{village_id}'.",
                data={"scenario": scenario, "village_id": village_id},
            )

        if scenario == "batch_summary":
            results = [
                {"village_id": "lacanau", "ok": True, "priced_bands": 12},
                {"village_id": "bandol", "ok": True, "priced_bands": 8},
                {"village_id": "chamonix", "ok": True, "priced_bands": 15},
                {"village_id": "saint-cast", "ok": True, "priced_bands": 10},
                {"village_id": "biarritz", "ok": True, "priced_bands": 9},
                {"village_id": "agde", "ok": False, "priced_bands": 0,
                 "scrape_errors": ["Step 1 (HTTP Fetch) | scraper.py → scrape_price_grid_http() | HTTP 403 Forbidden"],
                 "format_change": {"change_detected": True, "change_type": "hard_failure",
                                   "expected_markers": [], "found_markers": [],
                                   "missing_markers": [], "html_length": 0,
                                   "table_count": 0, "bands_scraped": 0, "priced_bands": 0}},
                {"village_id": "alpe-dhuez", "ok": False, "priced_bands": 0,
                 "scrape_errors": ["Step 2 (HTML Grid Parse) | scraper.py → scrape_price_grid_http() | Page loaded (html_len=48000) but no price grid markers found (grille tarifaire, pension complète, etc.). The VTF page layout may have changed."],
                 "format_change": {"change_detected": True, "change_type": "marker_missing",
                                   "expected_markers": ["grille tarifaire", "pension complète"],
                                   "found_markers": [], "missing_markers": ["grille tarifaire", "pension complète"],
                                   "html_length": 48000, "table_count": 0,
                                   "bands_scraped": 0, "priced_bands": 0}},
                {"village_id": "metabief", "ok": False, "priced_bands": 0,
                 "scrape_errors": [], "build_errors": ["Step 7 (Validation) | scraper.py → scrape_village() | No priced tariff bands extracted from any source (grille, widget, or LLM). Total bands scraped: 8. Nothing will be written to VillageTarif."],
                 "format_change": {"change_detected": True, "change_type": "parse_failure",
                                   "expected_markers": ["grille tarifaire"],
                                   "found_markers": ["grille tarifaire"],
                                   "missing_markers": [], "html_length": 52000,
                                   "table_count": 3, "bands_scraped": 5, "priced_bands": 0}},
            ]
            notify_batch_summary(results)
            return CustomResponse.success(
                "Batch summary alert sent (8 villages: 5 OK, 3 failed).",
                data={"scenario": scenario, "villages": len(results)},
            )

        # Build scenario-specific summary
        base = {
            "village_id": village_id,
            "url": url,
            "build_errors": [],
            "scrape_errors": [],
        }

        if scenario == "hard_failure":
            summary = {
                **base,
                "bands_scraped": 0,
                "priced_bands": 0,
                "bands_proposed": 0,
                "scrape_errors": ["Step 1 (HTTP Fetch) | scraper.py → scrape_price_grid_http() | HTTP 404 Client Error: Not Found for url: " + url],
                "format_change": {
                    "change_detected": True,
                    "change_type": "hard_failure",
                    "expected_markers": ["grille tarifaire", "pension complète", "location"],
                    "found_markers": [],
                    "missing_markers": ["grille tarifaire", "pension complète", "location"],
                    "html_length": 0,
                    "table_count": 0,
                    "bands_scraped": 0,
                    "priced_bands": 0,
                },
            }
        elif scenario == "zero_prices":
            summary = {
                **base,
                "bands_scraped": 0,
                "priced_bands": 0,
                "bands_proposed": 0,
                "scrape_errors": [
                    "Step 2 (HTML Grid Parse) | scraper.py → scrape_price_grid_http() | Page loaded (html_len=48000) but no price grid markers found (grille tarifaire, pension complète, etc.). The VTF page layout may have changed.",
                    "Step 3 (Browser Launch) | scraper.py → scrape_village() | Playwright launched but HTTP grille returned no bands.",
                    "Step 4 (Playwright Grid Parse) | scraper.py → scrape_price_grid() | Page rendered but no price table found in DOM.",
                    "Step 5 (Widget Scrape) | scraper.py → scrape_booking_widget() | Booking widget not found on page.",
                    "Step 7 (Validation) | scraper.py → scrape_village() | No priced tariff bands extracted from any source (grille, widget, or LLM). Total bands scraped: 0. Nothing will be written to VillageTarif.",
                ],
                "format_change": {
                    "change_detected": True,
                    "change_type": "zero_prices",
                    "expected_markers": ["grille tarifaire", "pension complète", "location"],
                    "found_markers": [],
                    "missing_markers": ["grille tarifaire", "pension complète", "location"],
                    "html_length": 48000,
                    "table_count": 0,
                    "bands_scraped": 0,
                    "priced_bands": 0,
                },
            }
        elif scenario == "parse_failure":
            summary = {
                **base,
                "bands_scraped": 8,
                "priced_bands": 0,
                "bands_proposed": 0,
                "build_errors": ["Step 6 (LLM Fallback) | llm_fallback.py → parse_grille_with_llm() | Date format changed: could not parse 'Semaine 24'"],
                "format_change": {
                    "change_detected": True,
                    "change_type": "parse_failure",
                    "expected_markers": ["grille tarifaire", "pension complète"],
                    "found_markers": ["grille tarifaire", "pension complète"],
                    "missing_markers": [],
                    "html_length": 51000,
                    "table_count": 3,
                    "bands_scraped": 8,
                    "priced_bands": 0,
                },
            }
        elif scenario == "marker_missing":
            summary = {
                **base,
                "bands_scraped": 0,
                "priced_bands": 0,
                "bands_proposed": 0,
                "scrape_errors": [
                    "Step 2 (HTML Grid Parse) | scraper.py → scrape_price_grid_http() | Page loaded (html_len=45000) but no price grid markers found (grille tarifaire, pension complète, demi-pension, location, séjour semaine). The VTF page layout may have changed.",
                    "Step 4 (Playwright Grid Parse) | scraper.py → scrape_price_grid() | Page rendered but no price table found in DOM.",
                    "Step 5 (Widget Scrape) | scraper.py → scrape_booking_widget() | Booking widget not found on page.",
                    "Step 7 (Validation) | scraper.py → scrape_village() | No priced tariff bands extracted from any source (grille, widget, or LLM). Total bands scraped: 0. Nothing will be written to VillageTarif.",
                ],
                "format_change": {
                    "change_detected": True,
                    "change_type": "marker_missing",
                    "expected_markers": ["grille tarifaire", "pension complète", "demi-pension", "location", "séjour semaine"],
                    "found_markers": ["Bienvenue"],
                    "missing_markers": ["grille tarifaire", "pension complète", "demi-pension", "location", "séjour semaine"],
                    "html_length": 45000,
                    "table_count": 0,
                    "bands_scraped": 0,
                    "priced_bands": 0,
                },
            }
        elif scenario == "partial":
            summary = {
                **base,
                "bands_scraped": 10,
                "priced_bands": 3,
                "bands_proposed": 2,
                "build_errors": ["Step 7 (Validation) | scraper.py → scrape_village() | Skipped 7 bands: no parseable dates"],
                "format_change": {
                    "change_detected": True,
                    "change_type": "partial",
                    "expected_markers": ["grille tarifaire", "pension complète"],
                    "found_markers": ["grille tarifaire"],
                    "missing_markers": ["pension complète"],
                    "html_length": 49000,
                    "table_count": 2,
                    "bands_scraped": 10,
                    "priced_bands": 3,
                },
            }
        else:
            return CustomResponse.error(
                f"Unknown scenario '{scenario}'.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Send Discord alert
        notify_scrape_failure(summary)

        # Save to FormatChangeLog DB
        _log_format_change(summary)

        return CustomResponse.success(
            f"Alert sent and logged for scenario '{scenario}' (village: {village_id}).",
            data={"scenario": scenario, "village_id": village_id},
        )

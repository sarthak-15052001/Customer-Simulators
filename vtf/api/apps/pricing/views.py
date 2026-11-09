"""Pricing endpoints: estimate, transport, qf, resto, promos, stay days,
booking-link, /go/{token} redirect.

Logging: every /estimate/stay creates a `SimulationLog` row inside
`transaction.on_commit` so the calc response is unblocked even if the log
fails. Every /go/{token} hit creates a `BookingClick` row the same way.
See `vtf/api/docs/06-data-collection-strategy.md`.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, timedelta

from common.response import CustomResponse
from common.throttles import (
    EstimateIpThrottle,
    InteractionsSessionThrottle,
)
from common.utils import (
    get_client_ip as _client_ip,
)
from common.utils import (
    get_session_id as _session_id,
)
from common.utils import (
    hash_ip as _hash_ip,
)
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiExample,
    extend_schema,
)
from rest_framework.decorators import api_view
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from apps.catalog.models import Activity, Meal, PricingRules, Village
from apps.catalog.services.formulas import formula_includes_map
from apps.pricing.models import BookingClick, BookingRedirectToken, SimulationLog
from apps.pricing.serializers import (
    AvailablePromosInputSerializer,
    BookingLinkInputSerializer,
    BookingLinkOutputSerializer,
    CarCostInputSerializer,
    CarCostOutputSerializer,
    EstimateStayInputSerializer,
    InteractionInputSerializer,
    PromoChoiceSerializer,
    QfInputSerializer,
    QfOutputSerializer,
    RestoTotalInputSerializer,
    RestoTotalOutputSerializer,
    SejourEstimateOutputSerializer,
    SignalInputSerializer,
    StayDayOutputSerializer,
    StayDaysInputSerializer,
    TrainCostInputSerializer,
    TrainCostOutputSerializer,
)
from apps.pricing.services import promos as promos_svc
from apps.pricing.services import qf as qf_svc
from apps.pricing.services import resto as resto_svc
from apps.pricing.services import stay_estimate as stay_estimate_svc
from apps.pricing.services import transport as transport_svc
from apps.pricing.services.booking_redirect import BookingRedirectService
from apps.pricing.services.booking_url import (
    VTF_FALLBACK_URL,
    hash_payload,
    verify_token,
)
from apps.pricing.services.calendar import get_stay_days, is_village_ouvert
from apps.pricing.services.family import qf_badge_kind
from apps.pricing.services.simulation_log_export import build_simulation_logs_export
from apps.recommender.models import VillageInteraction

logger = logging.getLogger(__name__)
SIMULATION_LOG_EXPORT_FILENAME = "simulation_logs.xlsx"


# def _client_ip(request) -> str:
#     fwd = request.META.get("HTTP_X_FORWARDED_FOR")
#     if fwd:
#         return fwd.split(",")[0].strip()
#     return (request.META.get("REMOTE_ADDR") or "").strip()


# def _hash_ip(ip: str) -> str:
#     if not ip:
#         return ""
#     salt = getattr(settings, "SECRET_IP_SALT", "")
#     return hashlib.sha256(f"{salt}|{ip}".encode()).hexdigest()


# def _session_id(request, fallback_meta: dict | None = None) -> str:
#     sid = request.headers.get("X-Session-ID") or ""
#     if sid:
#         return sid[:64]
#     if fallback_meta:
#         return (fallback_meta.get("sessionId") or "")[:64]
#     return ""


def _village_to_dict(v: Village) -> dict:
    """Camel-cased dict matching the TS shape consumed by the service."""
    return {
        "id": v.id,
        "nom": v.nom,
        "region": v.region,
        "env": v.env_emoji,
        "envCode": v.env_code,
        "formules": v.formules,
        "hasLoc": v.has_loc,
        "ski": v.ski,
        "ouverture": v.ouverture,
        "tarifs": v.tarifs,
        "tarifUnit": getattr(v, "tarif_unit", "week"),
        "bebeClub": v.bebe_club,
        "forfaitRM": v.forfait_rm,
        "qfExc": v.qf_exc,
        "enfSoloHalf": v.enf_solo_half,
    }


def _activities_by_region(region: str) -> list[dict]:
    """Builds [{id, nom, type, ad, enf, saisons}] for the village's region (paid only)."""
    return [
        {
            "id": a.code,
            "nom": a.nom,
            "type": a.type,
            "ad": a.price_adult,
            "enf": a.price_child,
            "saisons": a.saisons,
        }
        for a in Activity.objects.filter(region=region, kind="paid")
    ]


def _meals_catalog() -> list[dict]:
    return [
        {"code": m.code, "label": m.label, "price_adult": m.price_adult, "price_child": m.price_child}
        for m in Meal.objects.all()
    ]


def _collect_promos(promos: dict) -> list[str]:
    out: list[str] = []
    if (promos.get("promoSejourRate") or 0) > 0:
        out.append(promos_svc.promo_key_from_rate(promos["promoSejourRate"]))
    if promos.get("quinzaineFutee"):
        out.append("quinzaine_futee")
    return [p for p in out if p and p != "none"]


# ─── Endpoints ────────────────────────────────────────────────────────────


class EstimateStayView(APIView):
    throttle_classes = [EstimateIpThrottle]
 
    """`POST /api/v1/estimate/stay` — the headline endpoint.
 
    Logs a `SimulationLog` row asynchronously. Returns the SejourEstimate plus
    a freshly-minted `bookingUrl` that goes through `/go/{token}` (spec §US-2.8).
    """
 
    @extend_schema(
        request=EstimateStayInputSerializer,
        responses=SejourEstimateOutputSerializer,
    )
    def post(self, request):
        ser = EstimateStayInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        meta = data.get("_meta") or {}
        sid = _session_id(request, meta) or "anon"
 
        village = get_object_or_404(Village, pk=data["villageId"])
        logger.info(
            "pricing_estimate_started session_id=%s village_id=%s",
            sid,
            village.id,
        )
        rules = PricingRules.active() or {}
        if not rules:
            logger.warning("pricing_estimate_missing_active_rules village_id=%s", village.id)
            return CustomResponse.error("No active pricing rules found.", status_code=503)
 
        sejour = data["sejour"]
 
        # Reject stays outside the village's real opening calendar
        # (Village.ouverture, e.g. "20/12/25–11/04 · 4/07–15/08/26"). Without
        # this, a season-key tarif (hs/vs/ete/fetes) can exist even though the
        # village is genuinely closed on those dates — e.g. Karellis has an
        # `hs` tarif but is closed 10–17/10.
        cur = sejour["dateDebut"]
        while cur < sejour["dateFin"]:
            if not is_village_ouvert(village.ouverture, cur):
                logger.warning(
                    "pricing_estimate_village_closed session_id=%s village_id=%s date=%s",
                    sid,
                    village.id,
                    cur,
                )
                return CustomResponse.error(
                    "Le village n'est pas ouvert à ces dates.", status_code=400
                )
            cur += timedelta(days=1)
 
        sejour_payload = {
            **sejour,
            "dateDebut": sejour["dateDebut"].isoformat(),
            "dateFin": sejour["dateFin"].isoformat(),
        }
        family = {
            **data["family"],
            "enfants": [{"age": c["age"]} for c in data["family"].get("enfants") or []],
        }
 
        est = stay_estimate_svc.estimate_sejour_total(
            family=family,
            sejour=sejour_payload,
            village=_village_to_dict(village),
            pricing_rules=rules,
            activities_by_region={village.region: _activities_by_region(village.region)},
            meals_catalog=_meals_catalog(),
        )
        if est is None:
            logger.warning("pricing_estimate_impossible session_id=%s village_id=%s", sid, village.id)
            return CustomResponse.error("Estimation impossible for given inputs — check family, dates and formule.", status_code=400)
 
        # Mint a redirect token so the client can render a "Réserver" CTA.
        booking_url = ""
        try:
            token, _row, _params = BookingRedirectService.create_token(
                village=village,
                session_id=sid,
                family=family,
                dates={"debut": sejour_payload["dateDebut"], "fin": sejour_payload["dateFin"]},
                context={
                    "saisonKey": est.saison_key,
                    "estimatedTotal": est.total,
                    "formule": sejour["formule"],
                    "promosApplied": _collect_promos(sejour.get("promos") or {}),
                    "source": "estimate",
                },
            )
            booking_url = request.build_absolute_uri(reverse("booking-redirect", args=[token]))
        except Exception:
            # Never block the calculation on token issues — fall back to empty.
            logger.exception(
                "pricing_booking_token_failed session_id=%s village_id=%s",
                sid,
                village.id,
            )
            booking_url = ""
 
        # Logging — async via on_commit so the response time is unaffected.
        ip_hash = _hash_ip(_client_ip(request))
        ua = (request.META.get("HTTP_USER_AGENT") or "")[:256]
        promos_applied = _collect_promos(sejour.get("promos") or {})
 
        def _write_log(
            *,
            village_id: str = village.id,
            region: str = village.region,
            est_obj=est,
            family=family,
            sejour=sejour_payload,
            sid=sid,
            ip_hash=ip_hash,
            ua=ua,
            promos_applied=promos_applied,
            meta=meta,
        ) -> None:
            try:
                row = SimulationLog.objects.create(
                    session_id=sid,
                    village_id=village_id,
                    region=region,
                    formule=sejour["formule"],
                    saison_key=est_obj.saison_key,
                    date_debut=sejour["dateDebut"],
                    date_fin=sejour["dateFin"],
                    nuits=est_obj.nuits,
                    nb_adults=family["adultes"],
                    nb_children=len(family["enfants"]),
                    children_ages=[c["age"] for c in family["enfants"]],
                    qf_val=family.get("qfVal"),
                    qf_badge=qf_badge_kind(family.get("qfVal")),
                    is_solo_parent=(family["adultes"] == 1 and len(family["enfants"]) >= 1),
                    is_maxi_family=bool(family.get("maxiFamily")),
                    estimated_total=est_obj.total,
                    per_person_per_day=(est_obj.per_person // est_obj.nuits) if est_obj.nuits else 0,
                    discount_rate=est_obj.discount_rate,
                    promos_applied=promos_applied,
                    transport_mode=(sejour.get("transport") or {}).get("mode") or "",
                    transport_cost=est_obj.transport_total,
                    activities_cost=est_obj.activities_total,
                    resto_cost=est_obj.resto_total,
                    hotel_estimate=est_obj.hotel_estimate,
                    hotel_savings=est_obj.hotel_savings,
                    savings_pct=est_obj.savings_pct,
                    ip_hash=ip_hash,
                    user_agent=ua,
                    referrer=(meta.get("referrer") or "")[:256],
                    utm_source=(meta.get("utmSource") or "")[:64],
                    device_type=(meta.get("deviceType") or "")[:16],
                    step_timings=meta.get("stepTimings") or {},
                )
                logger.info(
                    "pricing_simulation_log_created id=%s session_id=%s village_id=%s total=%s",
                    row.id,
                    sid,
                    village_id,
                    est_obj.total,
                )
            except Exception:
                logger.exception(
                    "pricing_simulation_log_failed session_id=%s village_id=%s",
                    sid,
                    village_id,
                )
 
        transaction.on_commit(_write_log)
 
        out = asdict(est)
        # Optional: include alternative formule totals (PC/DP) when client requests it.
        include_alts = bool(request.data.get("includeFormuleAlternatives"))
        if include_alts:
            alts: list[dict] = []
            current_formule = sejour.get("formule")
            for code in ("PC", "DP"):
                if code != current_formule and code in village.formules:
                    sejour_alt = {**sejour_payload, "formule": code}
                    alt_est = stay_estimate_svc.estimate_sejour_total(
                        family=family,
                        sejour=sejour_alt,
                        village=_village_to_dict(village),
                        pricing_rules=rules,
                        activities_by_region={village.region: _activities_by_region(village.region)},
                        meals_catalog=_meals_catalog(),
                    )
                    if alt_est is not None:
                        alts.append({"formule": code, "total": alt_est.total})
            if alts:
                out["formuleAlternatives"] = alts
        out["includes"] = formula_includes_map([sejour["formule"]])
        out["bookingUrl"] = booking_url
        logger.info(
            "pricing_estimate_done session_id=%s village_id=%s total=%s booking_url_created=%s",
            sid,
            village.id,
            est.total,
            bool(booking_url),
        )
        return CustomResponse.success("Stay estimate calculated.", data=SejourEstimateOutputSerializer(out).data)


class CarCostView(APIView):
    @extend_schema(request=CarCostInputSerializer, responses=CarCostOutputSerializer)
    def post(self, request):
        ser = CarCostInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        out = transport_svc.car_cost_breakdown(
            distance_one_way_km=d["distanceOneWayKm"], fuel=d["fuel"]
        )
        return CustomResponse.success("Car cost calculated.", data=out)


class TrainCostView(APIView):
    @extend_schema(request=TrainCostInputSerializer, responses=TrainCostOutputSerializer)
    def post(self, request):
        ser = TrainCostInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        return CustomResponse.success("Train cost calculated.", data={"total": transport_svc.train_total(adults=d["adults"], children=d["children"])})


class QfView(APIView):
    @extend_schema(request=QfInputSerializer, responses=QfOutputSerializer)
    def post(self, request):
        ser = QfInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        qf_val = qf_svc.calc_qf_from_income_parts(
            net_monthly_income=d["netMonthlyIncome"], parts=d["parts"]
        )
        return CustomResponse.success("Quotient familial calculated.", data={"qfVal": qf_val, "badge": qf_badge_kind(qf_val)})


class RestoTotalView(APIView):
    @extend_schema(request=RestoTotalInputSerializer, responses=RestoTotalOutputSerializer)
    def post(self, request):
        ser = RestoTotalInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        meals = _meals_catalog()
        total = resto_svc.resto_total_amount(
            meals=meals,
            qty_by_meal_id=d["qtyByMealId"],
            adults=d["adults"],
            children=d["children"],
        )
        return CustomResponse.success("Restaurant total calculated.", data={"total": total})


class AvailablePromosView(APIView):
    @extend_schema(
        request=AvailablePromosInputSerializer,
        responses=PromoChoiceSerializer(many=True),
        examples=[
            OpenApiExample(
                "Solo parent example",
                summary="Request showing solo-parent flag",
                value={"dateDebut": "2026-07-05", "dateFin": "2026-07-12", "isSoloParent": True},
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        ser = AvailablePromosInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        now = d.get("now") or date.today()
        out = promos_svc.available_sejour_promos(
            date_debut=d["dateDebut"],
            date_fin=d["dateFin"],
            now=now,
            is_solo_parent=bool(d.get("isSoloParent")),
            village_id=(d.get("villageId") or None),
            quinzaine_futee=bool(d.get("quinzaineFutee")),
            formule=d.get("formule"),
        )
        return CustomResponse.success("Available promos fetched.", data=out)


class StayDaysView(APIView):
    @extend_schema(request=StayDaysInputSerializer, responses=StayDayOutputSerializer(many=True))
    def post(self, request):
        ser = StayDaysInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        days = get_stay_days(d["dateDebut"], d["dateFin"])
        return CustomResponse.success("Stay days generated.", data=days)


class BookingLinkView(APIView):
    """`POST /api/v1/villages/{id}/booking-link` — mint a redirect token."""

    @extend_schema(
        request=BookingLinkInputSerializer,
        responses=BookingLinkOutputSerializer,
    )
    def post(self, request, id: str):
        village = get_object_or_404(Village, pk=id)
        ser = BookingLinkInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        family = {
            **d["family"],
            "enfants": [{"age": c["age"]} for c in d["family"].get("enfants") or []],
        }
        dates = {
            "debut": d["dates"]["debut"].isoformat(),
            "fin": d["dates"]["fin"].isoformat(),
        }
        sid = _session_id(request, {"sessionId": d.get("sessionId", "")}) or "anon"

        ctx_in = d.get("context") or {}
        context = {
            "saisonKey": ctx_in.get("saisonKey", "ete"),
            "estimatedTotal": ctx_in.get("estimatedTotal"),
            "formule": ctx_in.get("formule"),
            "promosApplied": ctx_in.get("promosApplied", []),
            "source": d.get("source", "estimate"),
            "recoStrategy": ctx_in.get("recoStrategy"),
            "recoScore": ctx_in.get("recoScore"),
            "recoRank": ctx_in.get("recoRank"),
        }

        token, row, params = BookingRedirectService.create_token(
            village=village,
            session_id=sid,
            family=family,
            dates=dates,
            context=context,
        )
        redirect_url = request.build_absolute_uri(reverse("booking-redirect", args=[token]))
        logger.info(
            "pricing_booking_link_created session_id=%s village_id=%s token=%s",
            sid,
            village.id,
            token,
        )
        return CustomResponse.success(
            "Booking link generated.",
            data={
                "redirectUrl": redirect_url,
                "token": token,
                "expiresAt": row.expires_at,
                "targetUrl": row.target_url,
                "params": params,
            }
        )


@extend_schema(
    parameters=[OpenApiParameter("token", str, location="path")],
    responses={302: None, 404: None},
)
@api_view(["GET"])
def booking_redirect_view(request, token: str):
    """`GET /api/v1/go/{token}` — verify, log click, 302 to VTF.

    Spec §US-2.8 / AC-1.13.

    Tampered, expired, or unknown tokens *never* raise — they 302 to the
    generic VTF homepage with no `BookingClick` row. (CLAUDE.md don'ts:
    "never raise on expired/tampered tokens".)
    """
    fallback = HttpResponseRedirect(VTF_FALLBACK_URL)
    row = BookingRedirectToken.objects.filter(pk=token).select_related("village").first()
    if row is None:
        logger.warning("pricing_booking_redirect_unknown_token token=%s", token)
        return fallback
    if row.expires_at and row.expires_at < timezone.now():
        logger.warning("pricing_booking_redirect_expired token=%s", token)
        return fallback
    payload = row.payload or {}
    if not verify_token(
        token,
        village_id=row.village_id,
        session_id=row.session_id,
        payload_hash=hash_payload(payload),
    ):
        logger.warning("pricing_booking_redirect_invalid_signature token=%s", token)
        return fallback

    family = payload.get("family") or {}
    dates = payload.get("dates") or {}
    ctx = payload.get("context") or {}

    sid = _session_id(request) or row.session_id or "anon"
    is_repeat = row.click_count > 0
    # Atomic increment — `row.click_count += 1; row.save()` would lose
    # writes under concurrent /go/{token} hits.
    BookingRedirectToken.objects.filter(pk=token).update(click_count=F("click_count") + 1)

    ip_hash = _hash_ip(_client_ip(request))
    ua = (request.META.get("HTTP_USER_AGENT") or "")[:256]

    def _log_click(
        *,
        # token=token,
        token=row,          # FK requires instance, not the raw token string
        sid=sid,
        village=row.village,
        ctx=ctx,
        family=family,
        dates=dates,
        ip_hash=ip_hash,
        ua=ua,
        is_repeat=is_repeat,
    ) -> None:
        try:
            click = BookingClick.objects.create(
                token=token,
                session_id=sid,
                village=village,
                source=ctx.get("source", "estimate"),
                family_adults=family.get("adultes", 0),
                family_children=family.get("enfants", []),
                date_debut=dates.get("debut"),
                date_fin=dates.get("fin"),
                saison_key=ctx.get("saisonKey", ""),
                formule=ctx.get("formule") or "",
                estimated_total=ctx.get("estimatedTotal"),
                promos_applied=ctx.get("promosApplied") or [],
                reco_strategy=(ctx.get("recoStrategy") or ""),
                reco_score=ctx.get("recoScore"),
                reco_rank=ctx.get("recoRank"),
                ip_hash=ip_hash,
                user_agent=ua,
                is_repeat=is_repeat,
            )
        except Exception:
            logger.exception(
                "pricing_booking_click_log_failed session_id=%s token=%s",
                sid,
                token.pk,
            )
            return
        # Flip clicked_booking on the most recent matching SimulationLog row
        # so funnel analytics reflect the conversion. Best-effort: a click
        # without a prior simulation (rare) just leaves nothing to update.
        session_ids = [sid]
        if sid == "anon":
            session_ids.append("")
        latest_pk = (
            SimulationLog.objects.filter(
                session_id__in=session_ids, village=village, clicked_booking=False
            )
            .order_by("-created_at")
            .values_list("pk", flat=True)
            .first()
        )
        if latest_pk is not None:
            click_at = timezone.now()
            created_at = (
                SimulationLog.objects.filter(pk=latest_pk)
                .values_list("created_at", flat=True)
                .first()
            )
            time_on_result_ms = None
            if created_at is not None:
                time_on_result_ms = max(0, int((click_at - created_at).total_seconds() * 1000))
            SimulationLog.objects.filter(pk=latest_pk).update(
                clicked_booking=True,
                booking_click_at=click_at,
                time_on_result_ms=time_on_result_ms,
            )
        logger.info(
            "pricing_booking_click_logged id=%s session_id=%s token=%s village_id=%s repeat=%s",
            click.id,
            sid,
            token.pk,
            village.id,
            is_repeat,
        )

    transaction.on_commit(_log_click)
    logger.info(
        "pricing_booking_redirect session_id=%s token=%s village_id=%s repeat=%s",
        sid,
        row.pk,
        row.village_id,
        is_repeat,
    )
    return HttpResponseRedirect(row.target_url or VTF_FALLBACK_URL)


# ─── Signals / Interactions ───────────────────────────────────────────────


class SignalView(APIView):
    """`POST /api/v1/signals` — fire-and-forget beacon (sendBeacon-friendly)."""

    @extend_schema(request=SignalInputSerializer, responses={201: None})
    def post(self, request):
        ser = SignalInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        sid = _session_id(request, {"sessionId": d.get("sessionId", "")}) or ""
        village_id = d.get("villageId")
        if not village_id:
            # Beacon-only event (e.g. session_start) — record nothing for now.
            return CustomResponse.created("Signal recorded.")
        kind = d["kind"]
        if kind not in {"view", "simulate", "bookmark", "rate", "click_cta"}:
            # Map common signal labels to canonical VillageInteraction kinds.
            mapping = {
                "village_view": "view",
                "result_view": "view",
                "recap_view": "view",
                "share_click": "click_cta",
                "step_complete": "view",
            }
            kind = mapping.get(kind, "view")
        try:
            VillageInteraction.objects.create(
                session_id=sid,
                village_id=village_id,
                kind=kind,
                value=d.get("value", 1.0),
                metadata=d.get("metadata") or {},
            )
        except Exception:
            # Never fail a beacon — analytics are best-effort.
            logger.debug(
                "pricing_signal_record_failed session_id=%s village_id=%s kind=%s",
                sid,
                village_id,
                kind,
                exc_info=True,
            )
        else:
            logger.info(
                "pricing_signal_recorded session_id=%s village_id=%s kind=%s",
                sid,
                village_id,
                kind,
            )
        return CustomResponse.created("Signal recorded.")


class InteractionView(APIView):
    throttle_classes = [InteractionsSessionThrottle]

    """`POST /api/v1/interactions` — typed VillageInteraction."""

    @extend_schema(request=InteractionInputSerializer, responses={201: None})
    def post(self, request):
        ser = InteractionInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        sid = _session_id(request, {"sessionId": d.get("sessionId", "")}) or ""
        # Validate village existence without fetching the full object.
        if not Village.objects.filter(pk=d["villageId"]).exists():
            return CustomResponse.error("Village not found.", status_code=404)
        row = VillageInteraction.objects.create(
            session_id=sid,
            village_id=d["villageId"],
            kind=d["kind"],
            value=d.get("value", 1.0),
            metadata=d.get("metadata") or {},
        )
        logger.info(
            "pricing_interaction_recorded id=%s session_id=%s village_id=%s kind=%s",
            row.id,
            sid,
            d["villageId"],
            d["kind"],
        )
        return CustomResponse.created("Interaction recorded.", data={"id": row.id})

class SimulationLogExportView(APIView):
    @extend_schema(
        tags=["Exports"],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description="Excel file containing all SimulationLog fields.",
            )
        },
    )
    def get(self, request):
        logger.info("pricing_simulation_logs_export_started")
        content = build_simulation_logs_export()
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{SIMULATION_LOG_EXPORT_FILENAME}"'
        logger.info("pricing_simulation_logs_export_done bytes=%s", len(content))
        return response

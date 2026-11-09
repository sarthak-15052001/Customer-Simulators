"""PDF generation for vacation-budget simulations."""
from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.text import slugify
from weasyprint import HTML


@dataclass(frozen=True)
class SimulationPdf:
    filename: str
    content: bytes


def build_simulation_pdf(payload: dict) -> SimulationPdf:
    """Build a styled PDF from a validated simulations/pdf payload."""
    rendered_html = build_simulation_pdf_html(payload)
    if "{{" in rendered_html or "}}" in rendered_html:
        raise ValueError("Simulation PDF template contains unresolved variables.")
    filename = f"simulation-{slugify(payload['villageName']) or 'vtf'}.pdf"
    return SimulationPdf(
        filename=filename,
        content=_render_html_pdf_bytes(rendered_html),
    )


def build_simulation_pdf_html(payload: dict) -> str:
    """Render the shared simulation PDF HTML template dynamically."""
    return render_to_string("pdf/simulation_pdf.html", _template_context(payload))


def _template_context(payload: dict) -> dict:
    # Keep original (camelCase) keys to avoid breaking existing callers.
    # Also provide a few convenience aliases used by the HTML template.
    context = {
        key: value if isinstance(value, (list, tuple, dict)) else str(value)
        for key, value in payload.items()
    }

    # Aliases used in `simulation_pdf.html` (camelCase-ish short names)
    # NOTE: Missing variables in Django templates render as empty strings
    # (without leaving "{{ }}" behind), so we must explicitly provide these.
    context.update(
        {
            "total": context.get("totalEuro", ""),
            "perPerson": context.get("perPersonEuro", ""),
            "formule": context.get("formuleLabel", ""),
            "adhesion": context.get("adhesionEuro", ""),
            "transportLabel": context.get("transportModeLabel", ""),
            "formulaIncludes": context.get("formuleIncludesText", ""),
            "hotelSavings": context.get("hotelSavingsEuro", ""),
            "savingsPctDisplay": _percent_display(payload.get("savingsPct", "")),
        }
    )

    snake_aliases = {
        "village_name": context.get("villageName", ""),
        "date_debut": context.get("dateDebut", ""),
        "date_fin": context.get("dateFin", ""),
        "nb_enfants": context.get("nbEnfants", ""),
        "enfants_ages": context.get("enfantsAges", ""),
        "total_euro": context.get("totalEuro", ""),
        "per_person_euro": context.get("perPersonEuro", ""),
        "per_person_per_day": context.get("perPersonPerDay", ""),
        "per_day_family": context.get("perDayFamily", ""),
        "formule_label": context.get("formuleLabel", ""),
        "per_adult_base": context.get("perAdultBase", ""),
        "total_adults": context.get("totalAdults", ""),
        "child_1_age": context.get("child1Age", ""),
        "child_1_discount_label": context.get("child1DiscountLabel", ""),
        "child_1_amount": context.get("child1Amount", ""),
        "child_2_age": context.get("child2Age", ""),
        "child_2_discount_label": context.get("child2DiscountLabel", ""),
        "child_2_amount": context.get("child2Amount", ""),
        "child_3_age": context.get("child3Age", ""),
        "child_3_discount_label": context.get("child3DiscountLabel", ""),
        "child_3_amount": context.get("child3Amount", ""),
        "child_4_age": context.get("child4Age", ""),
        "child_4_discount_label": context.get("child4DiscountLabel", ""),
        "child_4_amount": context.get("child4Amount", ""),
        "total_children": context.get("totalChildren", ""),
        "stay_subtotal": context.get("staySubtotal", ""),
        "adhesion_euro": context.get("adhesionEuro", ""),
        "stay_package_total": context.get("stayPackageTotal", ""),
        "activities_total": context.get("activitiesTotal", ""),
        "resto_total": context.get("restoTotal", ""),
        "transport_mode_label": context.get("transportModeLabel", ""),
        "transport_detail_note": context.get("transportDetailNote", ""),
        "transport_total": context.get("transportTotal", ""),
        "formule_includes_text": context.get("formuleIncludesText", ""),
        "hotel_savings_euro": context.get("hotelSavingsEuro", ""),
        "savings_pct": context.get("savingsPct", ""),
        "booking_url": context.get("bookingUrl", ""),
        "day_1_label": context.get("day1Label", ""),
        "day_1_morning": context.get("day1Morning", ""),
        "day_1_afternoon": context.get("day1Afternoon", ""),
        "day_1_evening": context.get("day1Evening", ""),
        "day_2_label": context.get("day2Label", ""),
        "day_2_morning": context.get("day2Morning", ""),
        "day_2_afternoon": context.get("day2Afternoon", ""),
        "day_2_evening": context.get("day2Evening", ""),
        "day_3_label": context.get("day3Label", ""),
        "day_3_morning": context.get("day3Morning", ""),
        "day_3_afternoon": context.get("day3Afternoon", ""),
        "day_3_evening": context.get("day3Evening", ""),
        "day_n_label": context.get("dayNLabel", ""),
        "day_n_morning": context.get("dayNMorning", ""),
        "day_n_afternoon": context.get("dayNAfternoon", ""),
        "day_n_evening": context.get("dayNEvening", ""),
    }

    context.update(snake_aliases)
    context["pdf_children"] = _children_context(payload)
    context["pdf_planning"] = _planning_context(payload)
    return context


def _children_context(payload: dict) -> list[dict]:
    children = payload.get("children") or []
    if children:
        return [
            {
                "age": str(child.get("age", "")),
                "discountLabel": str(child.get("discountLabel", "")),
                "amount": str(child.get("amount", "")),
            }
            for child in children
        ]

    rows = []
    for idx in range(1, 5):
        age = payload.get(f"child{idx}Age", "")
        discount = payload.get(f"child{idx}DiscountLabel", "")
        amount = payload.get(f"child{idx}Amount", "")
        if age or discount or amount:
            rows.append(
                {
                    "age": str(age),
                    "discountLabel": str(discount),
                    "amount": str(amount),
                }
            )
    return rows


def _percent_display(value: object) -> str:
    text = str(value).strip()
    if not text:
        return ""
    return text if text.endswith("%") else f"{text}%"


def _planning_context(payload: dict) -> list[dict]:
    planning = payload.get("planning") or []
    if planning:
        return [
            {
                "kind": str(item.get("kind", "day")),
                "label": str(item.get("label", "")),
                "morning": str(item.get("morning", "")),
                "afternoon": str(item.get("afternoon", "")),
                "evening": str(item.get("evening", "")),
            }
            for item in planning
        ]

    legacy = [
        ("day", "day1Label", "day1Morning", "day1Afternoon", "day1Evening"),
        ("day", "day2Label", "day2Morning", "day2Afternoon", "day2Evening"),
        ("day", "day3Label", "day3Morning", "day3Afternoon", "day3Evening"),
        ("departure", "dayNLabel", "dayNMorning", "dayNAfternoon", "dayNEvening"),
    ]
    rows = []
    for kind, label_key, morning_key, afternoon_key, evening_key in legacy:
        label = payload.get(label_key, "")
        morning = payload.get(morning_key, "")
        afternoon = payload.get(afternoon_key, "")
        evening = payload.get(evening_key, "")
        if label or morning or afternoon or evening:
            rows.append(
                {
                    "kind": kind,
                    "label": str(label),
                    "morning": str(morning),
                    "afternoon": str(afternoon),
                    "evening": str(evening),
                }
            )
    return rows


def _render_html_pdf_bytes(rendered_html: str) -> bytes:
    return HTML(
        string=rendered_html,
        base_url=str(settings.BASE_DIR),
    ).write_pdf()

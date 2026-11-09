"""Build the VTF vacation-budget HTML email from a validated payload dict.

Uses Django's template rendering engine for clean separation of logic and HTML.
The template is located at: templates/mailer/vacation_budget_email.html
"""
from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from django.template.loader import render_to_string


# ──────────────────────────────────────────────────────────────────────────
# Public helpers
# ──────────────────────────────────────────────────────────────────────────

def build_subject(data: dict[str, Any]) -> str:
    village = data["villageName"]
    total = _fmt(data["total"])
    nuits = data["nuits"]
    subject = f"Mon projet vacances VTF — {village} · {nuits} nuits · {total} €"
    return subject


def build_html(data: dict[str, Any]) -> str:
    """Return the full HTML string for the simulation email using Django templates."""
    
    d = data  # short alias

    # Prepare context data for template
    context = _prepare_template_context(d)
    
    # Render the template
    html = render_to_string("mailer/vacation_budget_email.html", context)
    return html


def _prepare_template_context(data: dict[str, Any]) -> dict[str, Any]:
    """Prepare all context variables for the email template."""
    d = data

    # Basic counts
    adultes = d["adultes"]
    enfants = _child_ages(d)
    nb_enfants = len(enfants)
    enfants_label = d.get("childAges") or " · ".join(f"{age} ans" for age in enfants)

    # Date formatting
    date_debut_str = _date_fr(d["dateDebut"])
    date_fin_str = _date_fr(d["dateFin"])

    # Labels and descriptions
    formule_label = _formule_label(d["formule"])
    formule_inclus = d.get("formulaIncludes") or _formule_inclus(d["formule"])
    env_label = _env_label(d.get("envKey", ""))
    transport_label = d.get("transportLabel") or _transport_label(
        d.get("transportMode", "car"),
        d.get("transportKm", 0),
        d.get("simulationData") or {},
    )

    # Build children list with amounts
    child_amounts_with_ages = [
        {
            "age": age,
            "amount_fmt": _fmt(amount),
        }
        for age, amount in zip(enfants, d.get("childAmounts", []))
    ]

    # Booking URL
    booking_url = _clean_booking_url(_booking_url_value(d))

    # All formatted values (with French thousand separators)
    context = {
        # Original data values
        "villageName": d["villageName"],
        "nuits": d["nuits"],
        "saison": d.get("saison", ""),
        "dateDebut": date_debut_str,
        "dateFin": date_fin_str,
        "adultes": adultes,
        "nb_enfants": nb_enfants,
        "childCount": nb_enfants,
        "enfants_label": enfants_label,
        "childAges": enfants_label,
        "date_debut_str": date_debut_str,
        "date_fin_str": date_fin_str,
        "formule": formule_label,
        "formule_label": formule_label,
        "formulaIncludes": formule_inclus,
        "formule_inclus": formule_inclus,
        "env_label": env_label,
        "transportLabel": transport_label,
        "transport_label": transport_label,
        "bookingUrl": booking_url,

        # Raw-style names used by the frontend-provided template.
        "total": _fmt(d["total"]),
        "perPersonPerDay": _fmt(d["perPersonPerDay"]),
        "perDayFamily": _fmt(d["perDayFamily"]),
        "perPerson": _fmt(d["perPerson"]),
        "perAdultBase": _fmt(d["perAdultBase"]),
        "totalAdults": _fmt(d["totalAdults"]),
        "totalAdultes": _fmt(d["totalAdults"]),
        "totalChildren": _fmt(d["totalChildren"]),
        "adhesion": _fmt(d["adhesion"]),
        "staySubtotal": _fmt(d["staySubtotal"]),
        "activitiesTotal": _fmt(d.get("activitiesTotal")),
        "restoTotal": _fmt(d.get("restoTotal")),
        "transportTotal": _fmt(d.get("transportTotal")),
        "hotelEstimate": _fmt(d.get("hotelEstimate")),
        "hotelSavings": _fmt(d.get("hotelSavings")),
        "savingsPct": d.get("savingsPct"),
        
        # Formatted values
        "total_fmt": _fmt(d["total"]),
        "perPersonPerDay_fmt": _fmt(d["perPersonPerDay"]),
        "perDayFamily_fmt": _fmt(d["perDayFamily"]),
        "perPerson_fmt": _fmt(d["perPerson"]),
        "perAdultBase_fmt": _fmt(d["perAdultBase"]),
        "totalAdults_fmt": _fmt(d["totalAdults"]),
        "totalChildren_fmt": _fmt(d["totalChildren"]),
        "adhesion_fmt": _fmt(d["adhesion"]),
        "staySubtotal_fmt": _fmt(d["staySubtotal"]),
        "activitiesTotal_fmt": _fmt(d.get("activitiesTotal")),
        "restoTotal_fmt": _fmt(d.get("restoTotal")),
        "transportTotal_fmt": _fmt(d.get("transportTotal")),
        "hotelEstimate_fmt": _fmt(d.get("hotelEstimate")),
        "hotelSavings_fmt": _fmt(d.get("hotelSavings")),
        
        # Child details for loop
        "child_amounts_with_ages": child_amounts_with_ages,
    }
    
    return context


# ──────────────────────────────────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────────────────────────────────

def _fmt(value: int | float | None) -> str:
    """Format a euro amount for HTML email (plain integer, no thousands separator).

    Matches the simulator UI ``formatEuro`` helper. Thin-space (U+202F) grouping
    renders as an oversized gap in Gmail/Outlook mobile, so we avoid it here.
    """
    if value is None:
        return "0"
    return str(int(value))


def _date_fr(d) -> str:
    """Format a date object or ISO string as dd/mm/yyyy."""
    if hasattr(d, "strftime"):
        return d.strftime("%d/%m/%Y")
    # ISO string
    parts = str(d).split("-")
    if len(parts) == 3:
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return str(d)


def _child_ages(data: dict[str, Any]) -> list[int]:
    ages = data.get("enfantsAges") or []
    if ages:
        return ages

    simulation_data = data.get("simulationData") or {}
    family = simulation_data.get("family") or {}
    children = family.get("enfants") or []
    return [
        child.get("age")
        for child in children
        if isinstance(child, dict) and child.get("age") is not None
    ]


def _formule_label(code: str) -> str:
    return {
        "PC": "Pension complète",
        "DP": "Demi-pension",
        "SA": "Séjour avec activités",
        "HB": "Demi-pension",
        "BB": "Chambre + petit-déjeuner",
        "RO": "Chambre seule",
    }.get(code.upper(), code)


def _formule_inclus(code: str) -> str:
    return {
        "PC": "Inclus : repas buffet et vin à table, clubs enfants, animations, piscine et espace bien-être, randonnées guidées, ménage, WIFI.",
        "DP": "Inclus : petit-déjeuner + dîner buffet, clubs enfants, animations, piscine, ménage, WIFI.",
        "HB": "Inclus : petit-déjeuner + dîner buffet, clubs enfants, animations, piscine, ménage, WIFI.",
        "SA": "Inclus : hébergement, clubs enfants, animations, piscine, une sélection d'activités incluses, ménage, WIFI.",
    }.get(code.upper(), "Inclus : clubs enfants, animations, piscine, ménage, WIFI.")


def _env_label(key: str) -> str:
    return {
        "mer": "Env. Mer",
        "montagne": "Env. Montagne",
        "campagne": "Env. Campagne",
        "ville": "Env. Ville",
    }.get(key.lower(), key.capitalize() if key else "")


def _transport_label(mode: str, km: int, simulation_data: dict[str, Any] | None = None) -> str:
    if not km and simulation_data:
        transport = ((simulation_data.get("sejour") or {}).get("transport") or {})
        km = transport.get("distanceOneWayKm") or 0
        mode = transport.get("mode") or mode

    labels = {
        "car": f"Voiture · {km} km aller",
        "train": f"Train",
        "plane": f"Avion",
        "bus": f"Bus",
    }
    return labels.get(mode.lower(), mode.capitalize())


def _clean_booking_url(value: Any) -> str:
    """Return a usable booking URL for the email CTA."""
    url = str(value or "").strip()
    if not url:
        return "https://www.vtf-vacances.com"

    # Some frontend payloads have included a stray encoded quote at the end.
    # Email clients can treat that as part of the URL and break the redirect.
    while url:
        decoded = unquote(url)
        stripped = decoded.strip().strip("\"'")
        if stripped == url:
            break
        url = stripped

    return url or "https://www.vtf-vacances.com"


def _booking_url_value(data: dict[str, Any]) -> Any:
    simulation_data = data.get("simulationData") or {}
    return (
        data.get("bookingUrl")
        or data.get("redirectUrl")
        or data.get("bookingURL")
        or data.get("booking_url")
        or data.get("redirect_url")
        or simulation_data.get("bookingUrl")
        or simulation_data.get("redirectUrl")
        or simulation_data.get("bookingURL")
        or simulation_data.get("booking_url")
        or simulation_data.get("redirect_url")
    )

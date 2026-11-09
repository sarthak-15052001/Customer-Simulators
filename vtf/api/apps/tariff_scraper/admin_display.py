"""Small HTML renderers for tariff JSON in Django admin."""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from html import escape

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET

from apps.tariff_scraper.models import TariffApproval


SEASON_ORDER = ["hs", "vs", "ete", "fetes"]
SEASON_LABELS = {
    "hs": "HS",
    "vs": "VS",
    "ete": "Ete",
    "fetes": "Fetes",
}
FORMULE_ORDER = {"PC": 0, "DP": 1, "LOC": 2}

TABLE_STYLE = (
    "border-collapse:collapse;width:100%;max-width:980px;"
    "font-size:13px;line-height:1.35;"
)
# render_bands_grid has 11 columns (Formule .. Snapshot ID) — noticeably more
# than the other tables on this page. Reusing TABLE_STYLE's 980px cap forces
# every column into the same cramped width, and the last column (Snapshot
# ID) ends up clipped. This variant drops the cap and lets the table size to
# its content inside a horizontally-scrollable wrapper instead.
BANDS_TABLE_STYLE = (
    "border-collapse:collapse;width:100%;min-width:1180px;"
    "font-size:13px;line-height:1.35;"
)
BANDS_TABLE_WRAPPER_STYLE = "overflow-x:auto;max-width:100%;"
TH_STYLE = (
    "padding:7px 9px;border:1px solid #d8dee4;background:#f6f8fa;"
    "font-weight:600;text-align:left;"
)
TD_STYLE = "padding:7px 9px;border:1px solid #d8dee4;vertical-align:top;"
PRICE_STYLE = (
    TD_STYLE
    + "text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;"
)
CHANGED_STYLE = PRICE_STYLE + "background:#fff7d6;font-weight:600;"
MUTED_STYLE = TD_STYLE + "color:#6b7280;"
DOWNLOAD_LINK_STYLE = (
    "font-size:12px;font-weight:600;color:#417690;"
    "text-decoration:underline;text-underline-offset:2px;"
)


def fr_date(value) -> str:
    """Render a date as ``JJ/MM/AAAA``, whatever shape it arrives in.

    Model ``DateField``s are localized by Django itself (config/formats/fr),
    but bands and season notes are stored as JSON, so their dates reach the
    admin as ISO strings. Both go through this helper so the review screen
    never mixes ``2026-08-01`` with ``01/08/2026``.

    Unparseable input is echoed back untouched rather than swallowed — a
    malformed scraped date is a thing a reviewer needs to see.
    """
    if value in (None, ""):
        return "-"
    if isinstance(value, datetime):
        return date_format(timezone.localtime(value) if timezone.is_aware(value) else value,
                           "SHORT_DATETIME_FORMAT")
    if isinstance(value, date):
        return date_format(value, "SHORT_DATE_FORMAT")
    text = str(value)
    for parse, fmt in ((date.fromisoformat, "SHORT_DATE_FORMAT"),
                       (datetime.fromisoformat, "SHORT_DATETIME_FORMAT")):
        try:
            return date_format(parse(text), fmt)
        except (TypeError, ValueError):
            continue
    return text


def _money(value) -> str:
    if value in (None, ""):
        return "-"
    try:
        number = Decimal(str(value))
    except Exception:
        return str(value)
    if number == number.to_integral_value():
        return f"{int(number)}\u00a0EUR"
    return f"{number:.2f}\u00a0EUR"


def _wrap_with_download(content, download_url: str, label: str) -> str:
    link = format_html(
        '<p style="margin:0 0 10px 0;">'
        '<a href="{}" style="{}" download>{}</a>'
        "</p>",
        download_url,
        DOWNLOAD_LINK_STYLE,
        label,
    )
    return format_html("{}{}", link, content)


def _json_attachment_response(payload, filename: str) -> HttpResponse:
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    response = HttpResponse(body, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@require_GET
def download_proposed_bands_json(request: HttpRequest, object_id: str) -> HttpResponse:
    approval = get_object_or_404(TariffApproval, pk=object_id)
    filename = f"tariff-approval-{approval.pk}-proposed-bands.json"
    return _json_attachment_response(approval.proposed_bands or [], filename)


@require_GET
def download_proposed_season_tarifs_json(
    request: HttpRequest, object_id: str
) -> HttpResponse:
    approval = get_object_or_404(TariffApproval, pk=object_id)
    filename = f"tariff-approval-{approval.pk}-proposed-season-tarifs.json"
    return _json_attachment_response(approval.proposed_season_tarifs or {}, filename)


def _season_keys(*tarif_maps: dict | None) -> list[str]:
    keys: set[str] = set()
    for tarifs in tarif_maps:
        if not isinstance(tarifs, dict):
            continue
        for seasons in tarifs.values():
            if isinstance(seasons, dict):
                keys.update(str(k) for k in seasons.keys())
    ordered = [key for key in SEASON_ORDER if key in keys]
    ordered.extend(sorted(keys - set(ordered)))
    return ordered


def _formule_keys(*tarif_maps: dict | None) -> list[str]:
    keys: set[str] = set()
    for tarifs in tarif_maps:
        if isinstance(tarifs, dict):
            keys.update(str(k) for k in tarifs.keys())
    return sorted(keys, key=lambda code: (FORMULE_ORDER.get(code, 99), code))


def render_tarifs_grid(
    tarifs: dict | None,
    *,
    empty: str = "No tariffs.",
    download_url: str | None = None,
    download_label: str = "Download proposed season tariff prices as JSON",
) -> str:
    """Render Village.tarifs-style JSON as formule x season table."""
    if not isinstance(tarifs, dict) or not tarifs:
        empty_msg = format_html('<span style="color:#6b7280;">{}</span>', empty)
        if download_url:
            return _wrap_with_download(empty_msg, download_url, download_label)
        return empty_msg

    seasons = _season_keys(tarifs)
    header = "".join(
        f'<th style="{TH_STYLE}">{escape(SEASON_LABELS.get(s, s))}</th>' for s in seasons
    )
    rows = []
    for formule in _formule_keys(tarifs):
        season_values = tarifs.get(formule) if isinstance(tarifs.get(formule), dict) else {}
        cells = "".join(
            f'<td style="{PRICE_STYLE}">{escape(_money(season_values.get(season)))}</td>'
            for season in seasons
        )
        rows.append(
            f'<tr><th style="{TH_STYLE}">{escape(formule)}</th>{cells}</tr>'
        )
    table = mark_safe(
        f'<table style="{TABLE_STYLE}"><thead><tr>'
        f'<th style="{TH_STYLE}">Formule</th>{header}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )
    if download_url:
        return _wrap_with_download(table, download_url, download_label)
    return table


def render_tarifs_comparison(previous: dict | None, proposed: dict | None) -> str:
    """Render previous vs proposed season prices with changed cells highlighted."""
    if not isinstance(proposed, dict) or not proposed:
        return format_html('<span style="color:#6b7280;">No proposed season tariffs.</span>')

    seasons = _season_keys(previous, proposed)
    rows = []
    for formule in _formule_keys(previous, proposed):
        prev_bucket = previous.get(formule, {}) if isinstance(previous, dict) else {}
        next_bucket = proposed.get(formule, {}) if isinstance(proposed, dict) else {}
        for season in seasons:
            old = prev_bucket.get(season) if isinstance(prev_bucket, dict) else None
            new = next_bucket.get(season) if isinstance(next_bucket, dict) else None
            if old is None and new is None:
                continue
            changed = old != new
            proposed_style = CHANGED_STYLE if changed else PRICE_STYLE
            status = "Changed" if changed else "No change"
            rows.append(
                "<tr>"
                f'<td style="{TD_STYLE}">{escape(formule)}</td>'
                f'<td style="{TD_STYLE}">{escape(SEASON_LABELS.get(season, season))}</td>'
                f'<td style="{PRICE_STYLE}">{escape(_money(old))}</td>'
                f'<td style="{proposed_style}">'
                f'{escape(_money(new))}</td>'
                f'<td style="{MUTED_STYLE}">{status}</td>'
                "</tr>"
            )

    if not rows:
        return format_html('<span style="color:#6b7280;">No season prices to compare.</span>')

    return mark_safe(
        f'<table style="{TABLE_STYLE}"><thead><tr>'
        f'<th style="{TH_STYLE}">Formule</th>'
        f'<th style="{TH_STYLE}">Season</th>'
        f'<th style="{TH_STYLE}">Current</th>'
        f'<th style="{TH_STYLE}">Proposed</th>'
        f'<th style="{TH_STYLE}">Status</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table>'
    )


STALE_STYLE = TD_STYLE + "background:#fff7d6;"
DROPPED_STYLE = TD_STYLE + "background:#fdecea;"

NOTE_KINDS = (
    (
        "unverified",
        "Non verifie par ce scrape",
        STALE_STYLE,
        "Valeur conservee depuis les tarifs actuels : aucune bande scrapee "
        "ne tombe dans cette saison.",
    ),
    (
        "dropped_closed",
        "Retire (village ferme)",
        DROPPED_STYLE,
        "Le village est ferme toute la saison ; le prix est supprime de "
        "Village.tarifs a l'approbation.",
    ),
)


def render_season_tarifs_notes(notes: dict | None) -> str:
    """Show which proposed season prices this scrape could not stand behind.

    The season grid renders a full ``formule x saison`` matrix, which reads as
    "everything was refreshed" even when the scrape only produced two of four
    buckets and the rest are carried-over fixture values. This table names them
    so a reviewer approves knowing what is actually being confirmed.
    """
    if not isinstance(notes, dict):
        return mark_safe('<span style="color:#6b7280;">-</span>')

    rows = []
    for key, label, style, why in NOTE_KINDS:
        entries = notes.get(key) or []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            rows.append(
                "<tr>"
                f'<td style="{style}">{escape(str(entry.get("formule", "-")))}</td>'
                f'<td style="{style}">'
                f'{escape(SEASON_LABELS.get(entry.get("season"), str(entry.get("season", "-"))))}'
                "</td>"
                f'<td style="{PRICE_STYLE}">{escape(_money(entry.get("price")))}</td>'
                f'<td style="{style}">{escape(label)}</td>'
                f'<td style="{MUTED_STYLE}">{escape(why)}</td>'
                "</tr>"
            )

    if not rows:
        return mark_safe(
            '<span style="color:#1a7f37;">'
            "Toutes les saisons proposees proviennent de ce scrape."
            "</span>"
        )

    return mark_safe(
        f'<table style="{TABLE_STYLE}"><thead><tr>'
        f'<th style="{TH_STYLE}">Formule</th>'
        f'<th style="{TH_STYLE}">Saison</th>'
        f'<th style="{TH_STYLE}">Prix</th>'
        f'<th style="{TH_STYLE}">Statut</th>'
        f'<th style="{TH_STYLE}">Pourquoi</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table>'
    )


def _band_formule(band: dict) -> str:
    """Formule key in stored JSON is ``formule``; accept ``formula`` as alias."""
    return band.get("formule") or band.get("formula") or "-"


def _cell(value) -> str:
    if value in (None, ""):
        return "-"
    return str(value)


def render_bands_grid(
    bands: list | None,
    *,
    download_url: str | None = None,
    download_label: str = "Download proposed date bands as JSON",
) -> str:
    """Render TariffApproval.proposed_bands as a date-band table."""
    if not bands:
        empty_msg = format_html('<span style="color:#6b7280;">No proposed bands.</span>')
        if download_url:
            return _wrap_with_download(empty_msg, download_url, download_label)
        return empty_msg

    rows = []
    for band in bands:
        if not isinstance(band, dict):
            continue
        rows.append(
            (
                _band_formule(band),
                fr_date(band.get("date_start")),
                fr_date(band.get("date_end")),
                _cell(band.get("pricing_type")),
                _cell(band.get("unit_type")),
                _money(band.get("price")),
                _cell(band.get("raw_cell_text")),
                _cell(band.get("source_page")),
                _cell(band.get("scrape_source")),
                _cell(band.get("date_label")),
                _cell(band.get("source_snapshot_id")),
            )
        )

    if not rows:
        empty_msg = format_html(
            '<span style="color:#6b7280;">No readable proposed bands.</span>'
        )
        if download_url:
            return _wrap_with_download(empty_msg, download_url, download_label)
        return empty_msg

    NOWRAP_TD_STYLE = TD_STYLE + "white-space:nowrap;"

    body = format_html_join(
        "",
        (
            f'<td style="{TD_STYLE}">{{}}</td>'
            f'<td style="{TD_STYLE}">{{}}</td>'
            f'<td style="{TD_STYLE}">{{}}</td>'
            f'<td style="{TD_STYLE}">{{}}</td>'
            f'<td style="{TD_STYLE}">{{}}</td>'
            f'<td style="{PRICE_STYLE}">{{}}</td>'
            f'<td style="{TD_STYLE}">{{}}</td>'
            f'<td style="{TD_STYLE}">{{}}</td>'
            f'<td style="{NOWRAP_TD_STYLE}">{{}}</td>'
            f'<td style="{TD_STYLE}">{{}}</td>'
            f'<td style="{NOWRAP_TD_STYLE}">{{}}</td>'
            "</tr>"
        ),
        rows,
    )
    table = format_html(
        '<table style="{}"><thead><tr>'
        '<th style="{}">Formule</th>'
        '<th style="{}">Date start</th>'
        '<th style="{}">Date end</th>'
        '<th style="{}">Pricing type</th>'
        '<th style="{}">Unit type</th>'
        '<th style="{}">Price</th>'
        '<th style="{}">Raw cell</th>'
        '<th style="{}">Source page</th>'
        '<th style="{}">Scrape Source</th>'
        '<th style="{}">Date label</th>'
        '<th style="{}">Snapshot ID</th>'
        "</tr></thead><tbody>{}</tbody></table>",
        TABLE_STYLE,
        TH_STYLE,
        TH_STYLE,
        TH_STYLE,
        TH_STYLE,
        TH_STYLE,
        TH_STYLE,
        TH_STYLE,
        TH_STYLE,
        TH_STYLE,
        TH_STYLE,
        TH_STYLE,
        body,
    )
    content = format_html(
        '<div style="overflow-x:auto;max-width:100%;">{}</div>',
        table,
    )
    if download_url:
        return _wrap_with_download(content, download_url, download_label)
    return content

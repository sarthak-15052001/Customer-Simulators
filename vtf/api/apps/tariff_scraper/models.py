"""Tariff Scraper ORM models.

Design spec: VTF_Price_Automation_Plan_Approach-3.docx (sections 8.2, 8.3).

Models:
  PriceSnapshot   — immutable record of every price read from the VTF website.
  TariffApproval  — pending scrape proposal; staff must approve before use.
  VillageTarif    — live pricing table consumed by the pricing engine
                    (only rows activated after TariffApproval).

Booking logic (without PC/DP/LOC tarif on website):
  If a date window is INDISPONIBLE or has no PC/DP/LOC row on the scraped page,
  we store it in PriceSnapshot with is_available=False (booking widget) or
  simply do not create a VillageTarif row for that formule/date band. The
  pricing engine falls back to the existing Village.tarifs JSONField for those
  cases — we never overwrite the calculation logic, only the base prices.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models


SOURCE_WIDGET = "widget"
SOURCE_GRID = "price_grid"
SOURCE_LLM = "llm_fallback"
SOURCE_CHOICES = [
    (SOURCE_WIDGET, "Booking widget"),
    (SOURCE_GRID, "Price grid (grille tarifaire)"),
    (SOURCE_LLM, "LLM fallback (local model)"),
]

SCRAPE_SOURCE_SUMMER = "summer"
SCRAPE_SOURCE_WINTER = "winter"
SCRAPE_SOURCE_CHOICES = [
    (SCRAPE_SOURCE_SUMMER, "Summer product page"),
    (SCRAPE_SOURCE_WINTER, "Winter product page"),
]

FORMULE_CHOICES = [
    ("PC", "Pension complète"),
    ("DP", "Demi-pension"),
    ("LOC", "Location"),
]

PRICING_TYPE_PER_PERSON = "per_person"
PRICING_TYPE_FLAT_UNIT = "flat_unit"
PRICING_TYPE_PER_PERSON_PER_NIGHT = "per_person_per_night"
PRICING_TYPE_CHOICES = [
    (PRICING_TYPE_PER_PERSON, "Per person per week (PC/DP)"),
    (PRICING_TYPE_FLAT_UNIT, "Flat unit per week (LOC)"),
    (
        PRICING_TYPE_PER_PERSON_PER_NIGHT,
        "Per person per night (à la carte villages, e.g. Talloires)",
    ),
]

DERIVATION_SCRAPED = "scraped"
DERIVATION_STATED = "derived_stated"
DERIVATION_ASSUMED = "derived_assumed"
DERIVATION_CHOICES = [
    (DERIVATION_SCRAPED, "Scraped from page"),
    (DERIVATION_STATED, "Derived from stated page rule"),
    (DERIVATION_ASSUMED, "Derived from default assumption"),
]


class PriceSnapshot(models.Model):
    """Immutable record of every price read from the VTF website.

    Never edited, only appended to.  is_available=False rows are skipped
    by the tarif builder but kept for audit purposes.
    """

    village = models.ForeignKey(
        "catalog.Village",
        on_delete=models.CASCADE,
        related_name="price_snapshots",
    )
    formule = models.CharField(max_length=4, choices=FORMULE_CHOICES)
    source_page = models.CharField(max_length=16, choices=SOURCE_CHOICES)

    # Which product URL SEASON this row was scraped from ("summer" | "winter"
    # — the /summer/ or /winter/ URL path). Orthogonal to `source_page`,
    # which is the scrape TIER (grid/widget/llm). Only dual-season villages
    # (see DUAL_SEASON_VILLAGE_IDS) ever produce "winter" rows; every other
    # village's rows default to "summer" for backfill/consistency.
    scrape_source = models.CharField(
        max_length=8,
        choices=SCRAPE_SOURCE_CHOICES,
        default=SCRAPE_SOURCE_SUMMER,
    )

    # Date band as shown on the VTF page (nullable when the page omits parseable dates)
    date_label = models.CharField(max_length=128, blank=True, default="")
    date_start = models.DateField(null=True, blank=True)
    date_end = models.DateField(null=True, blank=True)

    # LOC / price_grid only
    unit_type = models.CharField(max_length=64, blank=True, default="")

    # PC / DP / widget only
    nb_adults = models.PositiveSmallIntegerField(null=True, blank=True)

    # The regular (non-discounted) price as scraped.
    # If a struck-through price exists next to a promo price we store the
    # struck-through value here — the promo layer is handled separately.
    scraped_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    # Exact table-cell text as it appeared on the page, e.g. "Gratuit*",
    # "581 €", or "" for a cell that was blank. Audit trail only — every
    # calculation still reads `scraped_price` (0 for both "Gratuit*" and a
    # blank child-age cell); this just shows what the source cell said.
    raw_cell_text = models.CharField(max_length=64, blank=True, default="")

    # False → window is INDISPONIBLE; we keep the row but never use it for tarifs
    is_available = models.BooleanField(default=True)

    derivation = models.CharField(
        max_length=24,
        choices=DERIVATION_CHOICES,
        default=DERIVATION_SCRAPED,
    )

    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scraped_at", "village", "formule", "date_start"]
        indexes = [
            models.Index(fields=["village", "formule", "date_start"]),
            models.Index(fields=["scraped_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.village_id} | {self.formule} | {self.date_start}–{self.date_end}"
            f" | {self.scraped_price}€"
        )


STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
# An approval that was applied and then rolled back. Distinct from `rejected`,
# which never touched pricing — `reverted` means prices *were* live for a while,
# so the audit trail must not claim the proposal was refused up front.
STATUS_REVERTED = "reverted"
APPROVAL_STATUS_CHOICES = [
    (STATUS_PENDING, "Pending review"),
    (STATUS_APPROVED, "Approved"),
    (STATUS_REJECTED, "Rejected"),
    (STATUS_REVERTED, "Reverted"),
]


class TariffApproval(models.Model):
    """One scrape proposal awaiting (or having received) staff approval.

    Scrapes only write PriceSnapshot rows + this pending proposal.
    Pricing (`VillageTarif` + ``Village.tarifs``) is updated on approve.
    """

    village = models.ForeignKey(
        "catalog.Village",
        on_delete=models.CASCADE,
        related_name="tariff_approvals",
    )
    status = models.CharField(
        max_length=16,
        choices=APPROVAL_STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    source_url = models.URLField(max_length=512, blank=True, default="")

    # Proposed date bands ready for VillageTarif (ISO dates as strings).
    proposed_bands = models.JSONField(default=list, blank=True)

    # Season-bucket patch to merge into Village.tarifs on approve
    # e.g. {"PC": {"ete": 903, "hs": 469}, "DP": {"ete": 767.55}}
    proposed_season_tarifs = models.JSONField(default=dict, blank=True)

    # Provenance for `proposed_season_tarifs`, so the review screen can tell
    # freshly scraped numbers apart from carried-over fixture data:
    #   {"unverified": [{"formule","season","price"}, ...],
    #    "dropped_closed": [{"formule","season","price"}, ...]}
    # `unverified` = kept from the current tarifs, this scrape found no band
    # for that season. `dropped_closed` = removed because the village is shut
    # for the whole season. See services/tarif_builder.build_season_tarifs_proposal.
    season_tarifs_notes = models.JSONField(default=dict, blank=True)

    # Village.tarifs snapshot taken at approve time (audit / rollback aid)
    previous_village_tarifs = models.JSONField(null=True, blank=True)

    bands_count = models.PositiveIntegerField(default=0)
    reject_reason = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tariff_approvals_reviewed",
    )

    # A revert gets its own timestamp/author instead of overwriting the review
    # ones: `reviewed_at` is the join key to the VillageTarif rows this approval
    # created (they carry it as `effective_at`), and overwriting it would strand
    # them, along with the record of who approved in the first place.
    reverted_at = models.DateTimeField(null=True, blank=True)
    reverted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tariff_approvals_reverted",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["village", "status"]),
        ]

    def __str__(self) -> str:
        return (
            f"TariffApproval#{self.pk} {self.village_id} "
            f"{self.status} ({self.bands_count} bands)"
        )


CHANGE_TYPE_MARKER_MISSING = "marker_missing"
CHANGE_TYPE_ZERO_PRICES = "zero_prices"
CHANGE_TYPE_PARSE_FAILURE = "parse_failure"
CHANGE_TYPE_PARTIAL = "partial"
CHANGE_TYPE_HARD_FAILURE = "hard_failure"
CHANGE_TYPE_CHOICES = [
    (CHANGE_TYPE_MARKER_MISSING, "Grille markers missing from page"),
    (CHANGE_TYPE_ZERO_PRICES, "Page loaded but zero prices extracted"),
    (CHANGE_TYPE_PARSE_FAILURE, "Dates or prices could not be parsed"),
    (CHANGE_TYPE_PARTIAL, "Partial data with errors"),
    (CHANGE_TYPE_HARD_FAILURE, "HTTP fetch / unhandled exception"),
]


class FormatChangeLog(models.Model):
    """Audit trail for detected VTF page format changes.

    One row per detected format change per village scrape.  Stores what
    markers were expected vs found, and a snippet of the relevant HTML
    for debugging.  Used by the alert system and the format-changes API.
    """

    village = models.ForeignKey(
        "catalog.Village",
        on_delete=models.CASCADE,
        related_name="format_change_logs",
    )
    change_type = models.CharField(
        max_length=24,
        choices=CHANGE_TYPE_CHOICES,
        db_index=True,
    )
    source_url = models.URLField(max_length=512, blank=True, default="")

    # What the scraper expected to find
    expected_markers = models.JSONField(
        default=list, blank=True,
        help_text="List of marker strings expected on the page",
    )
    # What was actually found
    found_markers = models.JSONField(
        default=list, blank=True,
        help_text="List of marker strings actually found on the page",
    )
    missing_markers = models.JSONField(
        default=list, blank=True,
        help_text="Markers expected but not found",
    )

    # Structural diagnostics
    html_length = models.PositiveIntegerField(
        default=0,
        help_text="Length of the fetched HTML page",
    )
    table_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of <table> elements found in HTML",
    )
    bands_scraped = models.PositiveIntegerField(
        default=0,
        help_text="Number of price bands extracted",
    )
    priced_bands = models.PositiveIntegerField(
        default=0,
        help_text="Number of bands with a valid price",
    )

    # Error details
    errors = models.JSONField(
        default=list, blank=True,
        help_text="Scrape/build error messages",
    )

    # A short snippet of the HTML for debugging (first 2 KB)
    html_snippet = models.TextField(
        blank=True, default="",
        help_text="First 2KB of fetched HTML for debugging",
    )

    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-detected_at"]
        indexes = [
            models.Index(fields=["village", "detected_at"]),
            models.Index(fields=["change_type", "detected_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"FormatChange {self.village_id} | {self.change_type} | "
            f"{self.detected_at:%Y-%m-%d %H:%M}"
        )


class VillageTarif(models.Model):
    """Live pricing table.

    This is what the pricing engine reads from.  It replaces the static
    numbers in Village.tarifs for PC / DP / LOC.

    pricing_type tells the engine how to use the price:
      per_person             → weekly price; multiply by family formula
                                (adults + child fractions)
      flat_unit               → charge exactly this amount for the whole
                                booking (LOC)
      per_person_per_night   → nightly price; multiply by family formula
                                *and* by nights (à la carte villages with no
                                weekly grid, e.g. Talloires — see
                                "Tarif par nuit" on the public page instead
                                of "Séjour semaine ... pension complète")

    Only one row per (village, formule, date_start, date_end, unit_type)
    should have is_active=True at any given time.  Old rows are kept for
    history (effective_at records when each became active).
    """

    village = models.ForeignKey(
        "catalog.Village",
        on_delete=models.CASCADE,
        related_name="village_tarifs",
    )
    formule = models.CharField(max_length=4, choices=FORMULE_CHOICES)

    # Scraped date band — NOT a fixed season bucket
    date_start = models.DateField()
    date_end = models.DateField()

    pricing_type = models.CharField(
        max_length=24,
        choices=PRICING_TYPE_CHOICES,
        default=PRICING_TYPE_PER_PERSON,
    )

    # LOC: scraped unit label ("Studio 4 pers.", ...).
    # PC/DP: scraped column label ("Adultes", "6 à - 11 ans", "2-5 ans", ...).
    # Blank = adult-only village that pre-dates column labelling.
    unit_type = models.CharField(max_length=64, blank=True, default="")

    # Per-adult weekly price (PC/DP) or flat weekly unit rate (LOC)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    # Full traceability back to the scraped row
    source_snapshot = models.ForeignKey(
        PriceSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_tarifs",
    )

    is_active = models.BooleanField(default=True, db_index=True)
    effective_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["village", "formule", "date_start"]
        indexes = [
            models.Index(fields=["village", "formule", "date_start", "is_active"]),
            models.Index(fields=["village", "is_active"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.village_id} | {self.formule} | {self.date_start}–{self.date_end}"
            f" | {self.price}€ ({'active' if self.is_active else 'inactive'})"
        )

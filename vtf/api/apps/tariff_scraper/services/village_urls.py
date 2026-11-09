"""Registry of the 32 VTF village website URLs.

Keys are catalog ``Village.id`` values (same PKs as ``villages.json``).
URLs point at the live vtf-vacances product pages used by the tariff scraper.

``get_village_url`` prefers this registry, then falls back to building a URL
from ``Village.vtf_department`` / ``vtf_city`` / ``vtf_slug`` when present.
"""

from __future__ import annotations

VTF_HOST = "https://www.vtf-vacances.com/fr_FR"

# Winter-only product pages (ski resorts) use the /winter/ segment year-round
# on the marketing site for their main grille.
_WINTER_DEFAULT_IDS = frozenset({"alpe-dhuez"})

# Villages with confirmed live winter product pages *in addition to* their
# summer page (VILLAGE_URLS entry). Both URLs are scraped for these ids —
# each runs the full Tier 1-4 cascade independently, then the two seasons'
# bands merge into one TariffApproval, tagged with Scrape Source
# ("summer" | "winter" — the URL path, not the ete/hs/vs/fetes grille season).
#
# Karellis and Montricher-Albanne share one product page
# (les-balcons-de-maurienne) — each catalog id still gets its own dual scrape
# of that shared page.
DUAL_SEASON_VILLAGE_IDS = frozenset({
    "karellis",
    "montricher-albanne",
    "la-plagne",
    "le-sauze",
    "arvieux",
    "savines",
    "saint-sauves",
    "metabief",
    "soultzeren",
    "font-durle",
    "areches",
    "chamonix",
})

SCRAPE_SOURCE_SUMMER = "summer"
SCRAPE_SOURCE_WINTER = "winter"

VILLAGE_URLS: dict[str, str] = {
    # Bretagne / Normandie
    "saint-cast": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/cotes-d-armor/saint-cast-le-guildo/l-hotel-des-bains"
    ),
    "blainville": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/manche/blainville-sur-mer/le-senequet"
    ),
    "riec": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/finistere/riec-sur-belon/ker-belen"
    ),
    # Pays Basque / Aquitaine
    "biarritz": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/pyrenees-atlantiques/biarritz/le-domaine-de-francon"
    ),
    "lacanau": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/gironde/lacanau/la-forestiere"
    ),
    "carcans-les-oyats": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/gironde/carcans/les-oyats"
    ),
    "carcans-les-bruyeres": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/gironde/carcans/les-bruyeres"
    ),
    "biscarrosse": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/landes/biscarrosse/la-jaougue-soule"
    ),
    # Provence / Côte d'Azur
    "bandol": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/var/bandol/clairefont"
    ),
    "sainte-maxime": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/var/sainte-maxime/golfe-de-saint-tropez"
    ),
    # Languedoc
    "agde": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/herault/agde/le-domaine-d-agde"
    ),
    # Mountains
    "chamonix": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/haute-savoie/chamonix/les-econtres"
    ),
    "alpe-dhuez": (
        "https://www.vtf-vacances.com/fr_FR/winter/village-vacances"
        "/isere/alpe-d-huez/le-balcon-de-l-alpe"
    ),
    "doucy": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/savoie/doucy-combelouviere/les-carlines"
    ),
    # Same VTF product page for both catalog villages (shared slug).
    "karellis": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/savoie/montricher-albanne/les-balcons-de-maurienne"
    ),
    "montricher-albanne": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/savoie/montricher-albanne/les-balcons-de-maurienne"
    ),
    "la-plagne": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/savoie/la-plagne-montalbert/le-dou-de-la-ramaz"
    ),
    "montgenevre": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/hautes-alpes/montgenevre/le-grand-hotel"
    ),
    "le-sauze": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/alpes-de-haute-provence/le-sauze-barcelonnette/les-balcons-du-sauze"
    ),
    "praloup": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/alpes-de-haute-provence/uvernet-fours/l-ouka"
    ),
    "arvieux": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/hautes-alpes/arvieux/les-esquirousses"
    ),
    "savines": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/hautes-alpes/savines-le-lac/le-pigneroux"
    ),
    "saint-sauves": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/puy-de-dome/saint-sauves-d-auvergne/le-domaine-des-puys"
    ),
    "metabief": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/doubs/metabief/le-bief-rouge"
    ),
    "soultzeren": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/haut-rhin/soultzeren/les-fougeres"
    ),
    "font-durle": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/drome/bouvante/font-urle"
    ),
    "bedoin": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/vaucluse/bedoin/les-florans"
    ),
    "cereste": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/alpes-de-haute-provence/cereste/le-domaine-du-grand-luberon"
    ),
    "singleyrac": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/dordogne/singleyrac/le-domaine-du-peyrichoux"
    ),
    "areches": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/savoie/areches-beaufort/le-rafour"
    ),
    "vernet": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/pyrenees-orientales/vernet-les-bains/clair-canigou"
    ),
    "talloires": (
        "https://www.vtf-vacances.com/fr_FR/summer/village-vacances"
        "/haute-savoie/talloires/les-alerions"
    ),
}


def build_url_from_village_fields(
    *,
    department: str,
    city: str,
    slug: str,
    season: str = "summer",
) -> str | None:
    """Build a vtf-vacances product URL from catalog VTF slug fields."""
    if not (department and city and slug):
        return None
    season = "winter" if season == "winter" else "summer"
    return (
        f"{VTF_HOST}/{season}/village-vacances/"
        f"{department.strip()}/{city.strip()}/{slug.strip()}"
    )


def get_village_url(village_id: str, *, prefer_db: bool = False) -> str | None:
    """Return the scrape URL for a catalog village id, or None if unknown.

    Args:
        village_id: catalog ``Village.id``
        prefer_db: when True, try ORM ``vtf_*`` fields before the hardcoded map
    """
    if prefer_db:
        built = _url_from_orm(village_id)
        if built:
            return built
    if village_id in VILLAGE_URLS:
        return VILLAGE_URLS[village_id]
    return _url_from_orm(village_id)


def get_village_scrape_urls(village_id: str) -> list[tuple[str, str]]:
    """Return the list of ``(url, scrape_source)`` pairs to scrape for a village.

    - Dual-season villages (``DUAL_SEASON_VILLAGE_IDS``): the existing summer
      URL plus its ``/winter/`` twin — two entries.
    - Every other village: a single entry, unchanged from today's behaviour.
      ``scrape_source`` is derived from the URL path itself (``/winter/`` →
      winter, else summer) so ``alpe-dhuez`` (winter-only, not in the dual
      list) still comes back correctly labeled.

    Returns an empty list when the village has no known URL at all.
    """
    base_url = get_village_url(village_id)
    if not base_url:
        return []

    if village_id not in DUAL_SEASON_VILLAGE_IDS:
        source = SCRAPE_SOURCE_WINTER if "/winter/" in base_url else SCRAPE_SOURCE_SUMMER
        return [(base_url, source)]

    summer_url = base_url.replace("/winter/", "/summer/")
    winter_url = summer_url.replace("/summer/", "/winter/")
    return [
        (summer_url, SCRAPE_SOURCE_SUMMER),
        (winter_url, SCRAPE_SOURCE_WINTER),
    ]


def _url_from_orm(village_id: str) -> str | None:
    try:
        from apps.catalog.models import Village

        v = Village.objects.filter(pk=village_id).only(
            "vtf_department", "vtf_city", "vtf_slug", "ski"
        ).first()
    except Exception:
        return None
    if not v:
        return None
    season = "winter" if (v.ski or village_id in _WINTER_DEFAULT_IDS) else "summer"
    return build_url_from_village_fields(
        department=v.vtf_department,
        city=v.vtf_city,
        slug=v.vtf_slug,
        season=season,
    )

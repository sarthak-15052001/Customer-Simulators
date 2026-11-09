"""Office de Tourisme base URLs for each VTF village (Phase 3 scraping).

Each URL points to the regional or local tourism board site that lists
activities near the village. Override or extend via SCRAPER_OT_URLS_JSON.

Verified / corrected against live tourism sites (2026-06).
"""
from __future__ import annotations

# Village ID → Office de Tourisme (or destination board) homepage
VTF_OT_URLS: dict[str, str] = {
    # Bretagne / Normandie
    "saint-cast": "https://www.dinan-capfrehel.com",
    "blainville": "https://www.encotentin.fr",
    "riec": "https://www.quimperle-lesrias.bzh",
    # Aquitaine / Landes
    "biarritz": "https://www.destination-biarritz.fr",
    "lacanau": "https://www.medoc-atlantique.com",
    "carcans": "https://www.medoc-atlantique.com",
    "biscarrosse": "https://www.biscagrandslacs.com",
    # Méditerranée / PACA
    "bandol": "https://www.bandoltourisme.fr",
    "sainte-maxime": "https://www.sainte-maxime.com",
    "agde": "https://www.capdagde.com",
    # Alpes / Savoie
    "chamonix": "https://www.chamonix.com",
    "alpe-dhuez": "https://www.alpedhuez.com",
    "doucy": "https://www.valmorel.com",
    "karellis": "https://www.leskarellis.com",
    "la-plagne": "https://www.la-plagne.com",
    "montgenevre": "https://www.montgenevre.com",
    # Alpes du Sud
    "le-sauze": "https://www.ubaye.com",
    "praloup": "https://www.praloup.com",
    "arvieux": "https://www.queyras-montagne.com",
    "savines": "https://www.serreponcon-tourisme.com",
    # Massif Central / Jura / Vosges
    "saint-sauves": "https://www.auvergnevolcans.com",
    "metabief": "https://www.montagnes-du-jura.fr",
    "soultzeren": "https://www.vallee-munster.eu",
    "font-durle": "https://www.valence-romans-tourisme.com",
    # Campagne / Provence / Ardèche / Pyrénées
    "bedoin": "https://www.ventouxprovence.fr",
    "cereste": "https://www.luberon-apt.fr",
    "singleyrac": "https://www.dordogne-perigord-tourisme.fr",
    "joyeuse": "https://www.cevennes-ardeche.com",
    "areches": "https://www.beaufortain.com",
    "vernet": "https://www.tourisme-canigo.com",
    "talloires": "https://www.lac-annecy.com",
    "montricher-albanne": "https://www.savoie-mont-blanc.com",
}

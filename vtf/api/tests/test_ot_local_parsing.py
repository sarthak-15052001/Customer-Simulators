from __future__ import annotations

from apps.scraper.adapters.ot_local import (
    _extract_distance_km,
    _extract_price,
    _extract_rating,
    _looks_like_activity_name,
    _schema_node_to_activity,
)


def test_extract_price_from_french_tariff_lines():
    text = """
    Tarifs
    Plein tarif
    12,50 EUR
    Tarif reduit enfant
    8 EUR
    """

    assert _extract_price(text) == (12, 8)


def test_extract_price_from_inline_adult_child_tariffs():
    text = "Adulte : 14 EUR / Enfant de 5 a 12 ans : 9 EUR"

    assert _extract_price(text) == (14, 9)


def test_extract_price_from_shared_euro_tariff_line():
    text = "Tarifs : Adulte 14 / Enfant de 5 a 12 ans 9 EUR"

    assert _extract_price(text) == (14, 9)


def test_extract_price_from_table_like_cells():
    text = """
    Tarifs
    Adulte
    18 EUR
    Enfant
    11 EUR
    Gratuit pour les moins de 5 ans
    """

    assert _extract_price(text) == (18, 0)


def test_extract_price_ignores_age_ranges_without_euro_amounts():
    text = "Enfant de 5 a 12 ans accompagne d'un adulte"

    assert _extract_price(text) == (None, None)


def test_extract_rating_and_review_count_from_text_and_meta():
    text = """
    Note : 4,6 sur 5
    1 248 avis
    <meta itemprop="ratingValue" content="4.8">
    <meta itemprop="reviewCount" content="52">
    """

    assert _extract_rating(text) == (4.6, 1248)


def test_extract_rating_and_review_count_from_reversed_meta_attributes():
    text = """
    <meta content="4.8" itemprop="ratingValue">
    <meta content="52" itemprop="reviewCount">
    """

    assert _extract_rating(text) == (4.8, 52)


def test_extract_distance_supports_meters_and_kilometers():
    assert _extract_distance_km("Situe a 750 m du village") == 0.75
    assert _extract_distance_km("Distance : 12,5 km") == 12.5


def test_schema_activity_reads_aggregate_offer_rating_and_distance():
    item = {
        "@type": "TouristAttraction",
        "name": "Aquarium de Biarritz",
        "url": "/aquarium",
        "description": "Visite famille a 2,5 km.",
        "geo": {"latitude": "43.4839", "longitude": "-1.5686"},
        "offers": {
            "@type": "AggregateOffer",
            "lowPrice": "9",
            "highPrice": "16",
            "priceCurrency": "EUR",
        },
        "aggregateRating": {"ratingValue": "4.5", "reviewCount": "3200"},
    }

    activity = _schema_node_to_activity(
        item,
        page_url="https://example.test",
        village_id="biarritz",
        center_lat=43.4832,
        center_lng=-1.5586,
    )

    assert activity is not None
    assert activity.nom == "Aquarium de Biarritz"
    assert activity.price_adult == 16
    assert activity.price_child == 9
    assert activity.rating == 4.5
    assert activity.review_count == 3200
    assert activity.distance_km == 2.5


def test_schema_activity_uses_labelled_price_specifications():
    item = {
        "@type": "TouristAttraction",
        "name": "Parc aventure",
        "url": "/parc-aventure",
        "description": "Accrobranche famille.",
        "offers": {
            "@type": "Offer",
            "priceSpecification": [
                {"name": "Tarif adulte", "price": "22", "priceCurrency": "EUR"},
                {"name": "Tarif enfant", "price": "14", "priceCurrency": "EUR"},
            ],
        },
    }

    activity = _schema_node_to_activity(
        item,
        page_url="https://example.test",
        village_id="biarritz",
        center_lat=43.4832,
        center_lng=-1.5586,
    )

    assert activity is not None
    assert activity.price_adult == 22
    assert activity.price_child == 14


def test_activity_name_filter_rejects_navigation_noise():
    assert not _looks_like_activity_name("Voir plus")
    assert not _looks_like_activity_name("Newsletter Facebook Instagram")
    assert _looks_like_activity_name("Musee de la Mer")

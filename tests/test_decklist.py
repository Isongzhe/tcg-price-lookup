"""Tests for tcg/decklist.py — pure logic: pick_best_hit, build_variants, enrich."""

from __future__ import annotations

from unittest.mock import MagicMock

from tcg.client import TCGplayerClient, TCGplayerError
from tcg.deck import DeckEntry
from tcg.models import AutocompleteHit, Listing, ProductDetails, Sale, Sku

# ---------------------------------------------------------------------------
# Helpers to build model instances without hitting the real API
# ---------------------------------------------------------------------------


def _hit(
    product_id: int, name: str, line: str = "Grand Archive TCG", score: float = 1.0
) -> AutocompleteHit:
    return AutocompleteHit(
        product_id=product_id,
        product_name=name,
        product_line_name=line,
        set_name="Test Set",
        score=score,
        duplicate=False,
    )


def _listing(price: float, printing: str = "Normal", condition: str = "Near Mint") -> Listing:
    return Listing(
        product_id=1,
        price=price,
        shipping_price=0.0,
        quantity=1,
        condition=condition,
        printing=printing,
        language="English",
        seller_name=None,
        seller_key=None,
        listing_id=None,
    )


def _sale(
    price: float,
    printing: str = "Normal",
    condition: str = "Near Mint",
    order_date: str = "2025-01-01",
) -> Sale:
    return Sale(
        product_id=1,
        order_date=order_date,
        purchase_price=price,
        shipping_price=0.0,
        quantity=1,
        condition=condition,
        variant=printing,
        language="English",
    )


def _details_with_skus(*skus: tuple[str, str]) -> ProductDetails:
    """Build a minimal ProductDetails with the given (printing, condition) SKU pairs."""
    sku_list = [
        Sku(sku_id=i + 1, printing=p, condition=c, language="English")
        for i, (p, c) in enumerate(skus)
    ]
    return ProductDetails(
        product_id=1,
        product_name="Test Card",
        set_name="Test Set",
        set_code=None,
        collector_number=None,
        rarity_name=None,
        market_price=None,
        lowest_price=None,
        median_price=None,
        lowest_price_with_shipping=None,
        sellers=None,
        foil_only=False,
        normal_only=False,
        skus=sku_list,
    )


def _entry(name: str = "Test Card", qty: int = 1, section: str = "") -> DeckEntry:
    return DeckEntry(section=section, quantity=qty, card_name=name)


# ---------------------------------------------------------------------------
# pick_best_hit
# ---------------------------------------------------------------------------

from tcg.decklist import pick_best_hit


def test_pick_best_filters_by_product_line():
    hits = [
        _hit(1, "Alice", line="Grand Archive TCG"),
        _hit(2, "Alice", line="Magic: The Gathering"),
        _hit(3, "Alice", line="Grand Archive TCG"),
    ]
    result = pick_best_hit(hits, "Alice", "Grand Archive TCG")
    assert result is not None
    assert result.product_line_name == "Grand Archive TCG"


def test_pick_best_prefers_exact_base_name():
    hits = [
        _hit(1, "Alice (CSR)", score=2.0),
        _hit(2, "Alice", score=1.0),
    ]
    result = pick_best_hit(hits, "Alice", None)
    assert result is not None
    assert result.product_id == 2


def test_pick_best_prefers_no_parenthetical():
    hits = [
        _hit(1, "Alice (Full Art)", score=3.0),
        _hit(2, "Alice (CSR)", score=2.0),
        _hit(3, "Alice", score=1.0),
    ]
    result = pick_best_hit(hits, "Alice", None)
    assert result is not None
    assert result.product_id == 3


def test_pick_best_breaks_tie_by_score():
    hits = [
        _hit(1, "Alice", score=1.0),
        _hit(2, "Alice", score=3.0),
        _hit(3, "Alice", score=2.0),
    ]
    result = pick_best_hit(hits, "Alice", None)
    assert result is not None
    assert result.product_id == 2


def test_pick_best_returns_none_for_empty_hits():
    result = pick_best_hit([], "Alice", None)
    assert result is None


def test_pick_best_returns_none_when_product_line_filter_eliminates_all():
    hits = [
        _hit(1, "Alice", line="Magic: The Gathering"),
        _hit(2, "Alice", line="Pokemon TCG"),
    ]
    result = pick_best_hit(hits, "Alice", "Grand Archive TCG")
    assert result is None


# ---------------------------------------------------------------------------
# build_variants
# ---------------------------------------------------------------------------

from tcg.decklist import build_variants


def test_build_variants_groups_by_printing_and_condition():
    listings = [
        _listing(1.0, "Normal", "Near Mint"),
        _listing(2.0, "Normal", "Near Mint"),
        _listing(3.0, "Foil", "Near Mint"),
        _listing(4.0, "Foil", "Near Mint"),
    ]
    result = build_variants(listings, [])
    assert len(result) == 2
    normal = next(v for v in result if v.printing == "Normal")
    foil = next(v for v in result if v.printing == "Foil")
    assert normal.listing_count == 2
    assert foil.listing_count == 2


def test_build_variants_seeds_from_skus_when_no_market_data():
    details = _details_with_skus(("Foil", "Near Mint"))
    result = build_variants([], [], details=details)
    assert len(result) == 1
    assert result[0].printing == "Foil"
    assert result[0].listing_count == 0
    assert result[0].sale_count == 0


def test_build_variants_orders_normal_before_foil():
    listings = [
        _listing(1.0, "Foil", "Near Mint"),
        _listing(2.0, "Normal", "Near Mint"),
    ]
    result = build_variants(listings, [])
    assert result[0].printing == "Normal"
    assert result[1].printing == "Foil"


def test_build_variants_orders_nm_first_within_printing():
    listings = [
        _listing(1.0, "Normal", "Lightly Played"),
        _listing(2.0, "Normal", "Near Mint"),
    ]
    result = build_variants(listings, [])
    assert result[0].condition == "Near Mint"
    assert result[1].condition == "Lightly Played"


def test_build_variants_uses_most_recent_by_order_date():
    sales = [
        _sale(5.0, order_date="2025-01-01"),
        _sale(10.0, order_date="2025-06-15"),
        _sale(3.0, order_date="2024-12-31"),
    ]
    result = build_variants([], sales)
    assert len(result) == 1
    assert result[0].most_recent_sale == 10.0


def test_build_variants_skips_zero_price_listings():
    listings = [
        _listing(0.0, "Normal", "Near Mint"),
        _listing(1.5, "Normal", "Near Mint"),
    ]
    result = build_variants(listings, [])
    assert result[0].listing_count == 1
    assert result[0].listing_min == 1.5


# ---------------------------------------------------------------------------
# enrich
# ---------------------------------------------------------------------------

from tcg.decklist import DeckRow, enrich


def _mock_client() -> MagicMock:
    return MagicMock(spec=TCGplayerClient)


def _product_details_for(product_id: int) -> ProductDetails:
    return ProductDetails(
        product_id=product_id,
        product_name="Alice, Golden Queen",
        set_name="Distorted Reflections",
        set_code="DTR",
        collector_number="001",
        rarity_name="Ultra Rare",
        market_price=5.0,
        lowest_price=4.0,
        median_price=5.5,
        lowest_price_with_shipping=4.5,
        sellers=10,
        foil_only=False,
        normal_only=False,
        skus=[Sku(sku_id=101, printing="Normal", condition="Near Mint", language="English")],
    )


def test_enrich_unambiguous_card_uses_autocomplete_path():
    client = _mock_client()
    client.autocomplete.return_value = [_hit(644912, "Alice, Golden Queen")]
    client.product_details.return_value = _product_details_for(644912)
    client.latest_sales.return_value = []
    client.listings.return_value = []
    client.market_price.return_value = []

    entry = _entry("Alice, Golden Queen")
    results = enrich(client, entry, "Grand Archive TCG")

    assert len(results) == 1
    row, _sales, _listings = results[0]
    assert isinstance(row, DeckRow)
    assert row.product_id == 644912
    client.search_products.assert_not_called()


def test_enrich_reprint_aggregate_falls_back_to_search():
    from tcg.models import ProductSearchResult

    client = _mock_client()
    client.autocomplete.return_value = []
    client.search_products.return_value = [
        ProductSearchResult(
            product_id=1001,
            product_name="Lost Providence",
            set_name="Set A",
            rarity_name=None,
            market_price=None,
            release_date="2026-04-03T00:00:00Z",
            collector_number=None,
            product_line_name="Grand Archive TCG",
        ),
        ProductSearchResult(
            product_id=1002,
            product_name="Lost Providence",
            set_name="Set B",
            rarity_name=None,
            market_price=None,
            release_date="2025-12-05T00:00:00Z",
            collector_number=None,
            product_line_name="Grand Archive TCG",
        ),
    ]
    client.product_details.return_value = _product_details_for(1001)
    client.latest_sales.return_value = []
    client.listings.return_value = []
    client.market_price.return_value = []

    entry = _entry("Lost Providence")
    results = enrich(client, entry, "Grand Archive TCG")

    assert len(results) == 2
    # Sorted newest first
    assert results[0][0].release_date == "2026-04-03T00:00:00Z"


def test_enrich_marks_missing_when_no_match():
    client = _mock_client()
    client.autocomplete.return_value = []
    client.search_products.return_value = []

    entry = _entry("Nonexistent Card")
    results = enrich(client, entry, None)

    assert len(results) == 1
    row, _, _ = results[0]
    assert row.missing_reason == "no match"


def test_enrich_handles_autocomplete_failure():
    client = _mock_client()
    client.autocomplete.side_effect = TCGplayerError("timeout")

    entry = _entry("Any Card")
    results = enrich(client, entry, None)

    assert len(results) == 1
    row, _, _ = results[0]
    assert row.missing_reason is not None
    assert "autocomplete failed:" in row.missing_reason


def test_enrich_handles_search_failure():
    client = _mock_client()
    client.autocomplete.return_value = []
    client.search_products.side_effect = TCGplayerError("503")

    entry = _entry("Any Card")
    results = enrich(client, entry, None)

    assert len(results) == 1
    row, _, _ = results[0]
    assert row.missing_reason is not None
    assert "search failed:" in row.missing_reason

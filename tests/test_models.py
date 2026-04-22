import json
from pathlib import Path

from tcg.models import AutocompleteHit, Listing, MarketPrice, ProductDetails, Sale

FIXTURES = Path(__file__).parent / "fixtures"


def test_autocomplete_hit_parses_kebab_case():
    data = json.loads((FIXTURES / "autocomplete_alice_golde.json").read_text())
    hits = [AutocompleteHit.from_api(p) for p in data["products"]]
    assert len(hits) == 3
    assert hits[0].product_id == 644912
    assert hits[0].product_name == "Alice, Golden Queen"
    assert hits[0].product_line_name == "Grand Archive TCG"
    assert hits[0].set_name == "Distorted Reflections"
    assert hits[0].score == 3.139879


def test_autocomplete_results_sorted_by_score_desc():
    data = json.loads((FIXTURES / "autocomplete_alice_golde.json").read_text())
    hits = [AutocompleteHit.from_api(p) for p in data["products"]]
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_sale_handles_missing_fields():
    s = Sale.from_api(644912, {})
    assert s.product_id == 644912
    assert s.purchase_price == 0.0
    assert s.quantity == 0


def test_sale_parses_typical_payload():
    s = Sale.from_api(
        644912,
        {
            "orderDate": "2026-04-20T12:00:00",
            "purchasePrice": "12.50",
            "shippingPrice": 1.0,
            "quantity": 2,
            "condition": "Near Mint",
            "language": "English",
        },
    )
    assert s.purchase_price == 12.5
    assert s.quantity == 2
    assert s.condition == "Near Mint"


def test_listing_parses_typical_payload():
    l = Listing.from_api(
        644912,
        {
            "price": 9.99,
            "shippingPrice": 0,
            "quantity": 3,
            "condition": "Near Mint",
            "printing": "Normal",
            "language": "English",
            "sellerName": "CardShop",
            "listingId": 12345,
        },
    )
    assert l.price == 9.99
    assert l.quantity == 3
    assert l.seller_name == "CardShop"


def test_product_details_parses_typical_payload():
    d = ProductDetails.from_api({
        "productId": 644912,
        "productName": "Alice, Golden Queen",
        "setName": "Distorted Reflections",
        "rarityName": "Super Rare",
        "marketPrice": 3.68,
        "lowestPriceWithShipping": 4.0,
        "sellers": 7,
        "foilOnly": False,
    })
    assert d.product_id == 644912
    assert d.market_price == 3.68
    assert d.rarity_name == "Super Rare"
    assert d.foil_only is False
    assert d.sellers == 7


def test_product_details_handles_missing_market_price():
    d = ProductDetails.from_api({"productId": 1, "productName": "X", "setName": "Y"})
    assert d.market_price is None
    assert d.sellers is None


def test_market_price_handles_none_values():
    m = MarketPrice.from_api({"skuId": 1000, "marketPrice": None, "lowestPrice": "5.0"})
    assert m.sku_id == 1000
    assert m.market_price is None
    assert m.lowest_price == 5.0


def test_market_price_parses_full_payload():
    m = MarketPrice.from_api({
        "skuId": 8847725,
        "marketPrice": 39.68,
        "lowestPrice": 29.99,
        "highestPrice": 50,
        "priceCount": 6,
        "calculatedAt": "2026-04-05T06:02:19.914Z",
    })
    assert m.sku_id == 8847725
    assert m.market_price == 39.68
    assert m.price_count == 6
    assert m.calculated_at == "2026-04-05T06:02:19.914Z"


def test_product_details_parses_skus():
    d = ProductDetails.from_api({
        "productId": 644912,
        "productName": "Alice, Golden Queen",
        "setName": "DTR",
        "marketPrice": 3.68,
        "skus": [
            {"sku": 8847720, "condition": "Near Mint", "variant": "Normal", "language": "English"},
            {"sku": 8847725, "condition": "Near Mint", "variant": "Foil", "language": "English"},
        ],
    })
    assert len(d.skus) == 2
    foil_nm = d.find_sku("Foil", "Near Mint")
    assert foil_nm is not None
    assert foil_nm.sku_id == 8847725
    assert d.find_sku("Foil", "Damaged") is None  # not in list

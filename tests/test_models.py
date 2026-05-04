import json
from pathlib import Path

from tcg.models import (
    AutocompleteHit,
    Listing,
    MarketPrice,
    ProductDetails,
    ProductSearchResult,
    Sale,
)

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
    listing = Listing.from_api(
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
    assert listing.price == 9.99
    assert listing.quantity == 3
    assert listing.seller_name == "CardShop"


def test_product_details_parses_typical_payload():
    d = ProductDetails.from_api(
        {
            "productId": 644912,
            "productName": "Alice, Golden Queen",
            "setName": "Distorted Reflections",
            "rarityName": "Super Rare",
            "marketPrice": 3.68,
            "lowestPriceWithShipping": 4.0,
            "sellers": 7,
            "foilOnly": False,
        }
    )
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
    m = MarketPrice.from_api(
        {
            "skuId": 8847725,
            "marketPrice": 39.68,
            "lowestPrice": 29.99,
            "highestPrice": 50,
            "priceCount": 6,
            "calculatedAt": "2026-04-05T06:02:19.914Z",
        }
    )
    assert m.sku_id == 8847725
    assert m.market_price == 39.68
    assert m.price_count == 6
    assert m.calculated_at == "2026-04-05T06:02:19.914Z"


def test_product_details_parses_set_code_and_collector_number():
    d = ProductDetails.from_api(
        {
            "productId": 644912,
            "productName": "Alice, Golden Queen",
            "setName": "Distorted Reflections",
            "setCode": "DTR1E",
            "rarityName": "Super Rare",
            "marketPrice": 3.68,
            "formattedAttributes": {"Rarity": "Super Rare", "Number": "004"},
            "customAttributes": {"number": "004", "element": "Norm"},
        }
    )
    assert d.set_code == "DTR1E"
    assert d.collector_number == "004"


def test_product_details_collector_number_falls_back_to_custom_attributes():
    # When formattedAttributes is absent, fall back to customAttributes.number.
    d = ProductDetails.from_api(
        {
            "productId": 1,
            "productName": "X",
            "setName": "Y",
            "customAttributes": {"number": "042"},
        }
    )
    assert d.collector_number == "042"


def test_product_details_image_urls_are_cdn_links():
    d = ProductDetails.from_api({"productId": 644912, "productName": "X", "setName": "Y"})
    assert d.image_url == "https://tcgplayer-cdn.tcgplayer.com/product/644912_200w.jpg"
    assert (
        d.image_url_large == "https://tcgplayer-cdn.tcgplayer.com/product/644912_in_1000x1000.jpg"
    )


def test_product_details_parses_skus():
    d = ProductDetails.from_api(
        {
            "productId": 644912,
            "productName": "Alice, Golden Queen",
            "setName": "DTR",
            "marketPrice": 3.68,
            "skus": [
                {
                    "sku": 8847720,
                    "condition": "Near Mint",
                    "variant": "Normal",
                    "language": "English",
                },
                {
                    "sku": 8847725,
                    "condition": "Near Mint",
                    "variant": "Foil",
                    "language": "English",
                },
            ],
        }
    )
    assert len(d.skus) == 2
    foil_nm = d.find_sku("Foil", "Near Mint")
    assert foil_nm is not None
    assert foil_nm.sku_id == 8847725
    assert d.find_sku("Foil", "Damaged") is None  # not in list


def test_product_search_result_parses_typical_payload():
    r = ProductSearchResult.from_api(
        {
            "productId": 665290,
            "productName": "Lost Providence",
            "setName": "Phantom Monarchs",
            "rarityName": "Ultra Rare",
            "marketPrice": 144.64,
            "productLineName": "Grand Archive TCG",
            "customAttributes": {
                "releaseDate": "2025-12-05T00:00:00Z",
                "number": "013",
            },
            "formattedAttributes": {"Number": "013"},
        }
    )
    assert r.product_id == 665290
    assert r.set_name == "Phantom Monarchs"
    assert r.market_price == 144.64
    assert r.release_date == "2025-12-05T00:00:00Z"
    assert r.collector_number == "013"


def test_product_search_result_tolerates_missing_attributes():
    r = ProductSearchResult.from_api({"productId": 1, "productName": "X", "setName": "Y"})
    assert r.release_date is None
    assert r.collector_number is None
    assert r.market_price is None

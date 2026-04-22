from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AutocompleteHit:
    # TCGplayer occasionally returns autocomplete entries with a null
    # product-id (e.g. the card name exists but is not yet assigned to a
    # specific product, such as pre-release or duplicate aggregates).
    # Callers must check for None before issuing downstream requests.
    product_id: int | None
    product_name: str
    product_line_name: str
    set_name: str
    score: float
    duplicate: bool = False

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> AutocompleteHit:
        return cls(
            product_id=d.get("product-id"),
            product_name=d.get("product-name", ""),
            product_line_name=d.get("product-line-name", ""),
            set_name=d.get("set-name", ""),
            score=float(d.get("score") or 0.0),
            duplicate=bool(d.get("duplicate", False)),
        )


@dataclass(frozen=True, slots=True)
class Sale:
    product_id: int
    order_date: str
    purchase_price: float
    shipping_price: float
    quantity: int
    condition: str | None
    variant: str | None
    language: str | None

    @classmethod
    def from_api(cls, product_id: int, d: dict[str, Any]) -> Sale:
        return cls(
            product_id=product_id,
            order_date=d.get("orderDate", ""),
            purchase_price=float(d.get("purchasePrice", 0) or 0),
            shipping_price=float(d.get("shippingPrice", 0) or 0),
            quantity=int(d.get("quantity", 0) or 0),
            condition=d.get("condition"),
            variant=d.get("variant"),
            language=d.get("language"),
        )


@dataclass(frozen=True, slots=True)
class Listing:
    product_id: int
    price: float
    shipping_price: float
    quantity: int
    condition: str | None
    printing: str | None
    language: str | None
    seller_name: str | None
    seller_key: str | None
    listing_id: int | None

    @classmethod
    def from_api(cls, product_id: int, d: dict[str, Any]) -> Listing:
        return cls(
            product_id=product_id,
            price=float(d.get("price", 0) or 0),
            shipping_price=float(d.get("shippingPrice", 0) or 0),
            quantity=int(d.get("quantity", 0) or 0),
            condition=d.get("condition"),
            printing=d.get("printing"),
            language=d.get("language"),
            seller_name=d.get("sellerName"),
            seller_key=d.get("sellerKey"),
            listing_id=d.get("listingId"),
        )


@dataclass(frozen=True, slots=True)
class Sku:
    """一個 SKU = (product × printing × condition × language)。
    market_price 要靠這個 id 去 pricepoints 端點查。"""
    sku_id: int
    printing: str        # "Normal" / "Foil"
    condition: str       # "Near Mint" / ...
    language: str

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Sku:
        return cls(
            sku_id=int(d.get("sku") or 0),
            printing=d.get("variant", ""),
            condition=d.get("condition", ""),
            language=d.get("language", ""),
        )


@dataclass(frozen=True, slots=True)
class ProductDetails:
    """/v2/product/{id}/details — TCGplayer's authoritative per-product summary.
    `market_price` here is Normal NM; per-variant prices need pricepoints API."""
    product_id: int
    product_name: str
    set_name: str
    set_code: str | None                # e.g. "DTR1E", "PTM"
    collector_number: str | None        # e.g. "004", "013"
    rarity_name: str | None
    market_price: float | None          # Normal NM (product-level)
    lowest_price: float | None          # 整張卡最低（跨版本）
    median_price: float | None
    lowest_price_with_shipping: float | None
    sellers: int | None
    foil_only: bool
    normal_only: bool
    skus: list[Sku]

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> ProductDetails:
        # Collector number lives in formattedAttributes.Number (primary)
        # and customAttributes.number (fallback).
        formatted = d.get("formattedAttributes") or {}
        custom = d.get("customAttributes") or {}
        collector_number = formatted.get("Number") or custom.get("number")
        return cls(
            product_id=int(d.get("productId") or 0),
            product_name=d.get("productName", ""),
            set_name=d.get("setName", ""),
            set_code=d.get("setCode"),
            collector_number=str(collector_number) if collector_number else None,
            rarity_name=d.get("rarityName"),
            market_price=_opt_float(d.get("marketPrice")),
            lowest_price=_opt_float(d.get("lowestPrice")),
            median_price=_opt_float(d.get("medianPrice")),
            lowest_price_with_shipping=_opt_float(d.get("lowestPriceWithShipping")),
            sellers=int(d["sellers"]) if d.get("sellers") is not None else None,
            foil_only=bool(d.get("foilOnly", False)),
            normal_only=bool(d.get("normalOnly", False)),
            skus=[Sku.from_api(s) for s in (d.get("skus") or [])],
        )

    def find_sku(self, printing: str, condition: str, language: str = "English") -> Sku | None:
        for s in self.skus:
            if s.printing == printing and s.condition == condition and s.language == language:
                return s
        return None

    @property
    def image_url(self) -> str:
        """Public CDN image URL (200px wide — small, suitable for Sheets IMAGE())."""
        return f"https://tcgplayer-cdn.tcgplayer.com/product/{self.product_id}_200w.jpg"

    @property
    def image_url_large(self) -> str:
        """Public CDN image URL (1000x1000 — higher resolution for detailed viewing)."""
        return f"https://tcgplayer-cdn.tcgplayer.com/product/{self.product_id}_in_1000x1000.jpg"


@dataclass(frozen=True, slots=True)
class MarketPrice:
    """Per-SKU market stats from /v1/pricepoints/marketprice/skus/search."""
    sku_id: int
    market_price: float | None
    lowest_price: float | None
    highest_price: float | None
    price_count: int | None
    calculated_at: str | None

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> MarketPrice:
        return cls(
            sku_id=int(d.get("skuId") or d.get("sku") or 0),
            market_price=_opt_float(d.get("marketPrice")),
            lowest_price=_opt_float(d.get("lowestPrice") or d.get("lowPrice")),
            highest_price=_opt_float(d.get("highestPrice")),
            price_count=int(d["priceCount"]) if d.get("priceCount") is not None else None,
            calculated_at=d.get("calculatedAt"),
        )


def _opt_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

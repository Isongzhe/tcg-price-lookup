from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AutocompleteHit:
    """One suggestion row returned by the TCGplayer autocomplete endpoint.

    TCGplayer occasionally returns entries with a ``None`` product ID —
    for example, when a card name exists across multiple unresolved products
    or is a pre-release item. The client filters these out before returning,
    but callers should still guard against ``None`` if using :meth:`from_api`
    directly.

    Attributes:
        product_id: Numeric TCGplayer product ID, or ``None`` if unresolved.
        product_name: Display name of the card / product.
        product_line_name: Display name of the product line
            (e.g. ``"Grand Archive TCG"``). Matches keys in
            :data:`tcg.PRODUCT_LINES`.
        set_name: Display name of the set this product belongs to.
        score: Server-side relevance score. Higher is more relevant.
        duplicate: ``True`` when TCGplayer marks this row as a duplicate
            aggregate (same name, multiple products). The client filters
            these out automatically.
    """

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
    """One completed marketplace transaction for a TCGplayer product.

    Returned by :meth:`~tcg.TCGplayerClient.latest_sales`. Each row is one
    buyer-seller transaction and may cover multiple copies (see ``quantity``).

    Attributes:
        product_id: Numeric TCGplayer product ID this sale belongs to.
        order_date: ISO-8601 date-time string of when the order was placed
            (e.g. ``"2026-04-15T18:32:00"``). Use for recency sorting.
        purchase_price: Price paid per copy, in USD. Does not include
            shipping.
        shipping_price: Shipping cost paid, in USD.
        quantity: Number of copies in this transaction.
        condition: Card condition label (e.g. ``"Near Mint"``), or ``None``
            if not reported.
        variant: Printing label (e.g. ``"Normal"``, ``"Foil"``), or ``None``
            if not reported.
        language: Language of the card (e.g. ``"English"``), or ``None`` if
            not reported.
    """

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
    """One active seller listing on the TCGplayer marketplace.

    Returned by :meth:`~tcg.TCGplayerClient.listings`. Listings are sorted
    by ``price + shipping`` ascending at the API layer, so the first row is
    the cheapest available offer.

    Attributes:
        product_id: Numeric TCGplayer product ID this listing is for.
        price: Asking price per copy, in USD. Does not include shipping.
        shipping_price: Seller's shipping cost, in USD.
        quantity: Number of copies available in this listing.
        condition: Card condition label (e.g. ``"Near Mint"``), or ``None``
            if not reported.
        printing: Printing / foiling label (e.g. ``"Normal"``, ``"Foil"``),
            or ``None`` if not reported.
        language: Language of the card (e.g. ``"English"``), or ``None`` if
            not reported.
        seller_name: Display name of the seller, or ``None``.
        seller_key: Internal seller identifier used by TCGplayer, or ``None``.
        listing_id: Unique listing ID, or ``None`` if not returned.
    """

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
class ProductSearchResult:
    """One row from the TCGplayer product search endpoint.

    Returned by :meth:`~tcg.TCGplayerClient.search_products`. Use this to
    enumerate every printing of a card across sets (reprints). Lighter than
    :class:`ProductDetails`: no SKU list, no per-variant market prices.
    Callers that need SKU-level data should follow up with
    :meth:`~tcg.TCGplayerClient.product_details`.

    Attributes:
        product_id: Numeric TCGplayer product ID.
        product_name: Display name of the card / product.
        set_name: Display name of the set this product belongs to.
        rarity_name: Rarity label (e.g. ``"Rare"``, ``"Legendary Rare"``),
            or ``None`` if not reported.
        market_price: Product-level market price in USD (Normal NM), or
            ``None`` if no data is available.
        release_date: ISO-8601 date string from ``customAttributes.releaseDate``
            (e.g. ``"2026-03-21"``), or ``None`` if not set. Sort descending
            for newest-first ordering.
        collector_number: Collector number within the set (e.g. ``"013"``),
            or ``None`` if not reported.
        product_line_name: URL slug of the product line
            (e.g. ``"grand-archive"``). Note: this is a slug, not a display
            name — it differs from :attr:`AutocompleteHit.product_line_name`.
    """

    product_id: int
    product_name: str
    set_name: str
    rarity_name: str | None
    market_price: float | None  # product-level (Normal NM)
    release_date: str | None  # ISO-8601 from customAttributes.releaseDate
    collector_number: str | None  # customAttributes.number, e.g. "013"
    product_line_name: str | None

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> ProductSearchResult:
        custom = d.get("customAttributes") or {}
        formatted = d.get("formattedAttributes") or {}
        return cls(
            product_id=int(d.get("productId") or 0),
            product_name=d.get("productName", ""),
            set_name=d.get("setName", ""),
            rarity_name=d.get("rarityName"),
            market_price=_opt_float(d.get("marketPrice")),
            release_date=custom.get("releaseDate"),
            collector_number=str(formatted.get("Number") or custom.get("number") or "") or None,
            product_line_name=d.get("productLineName"),
        )


@dataclass(frozen=True, slots=True)
class Sku:
    """One SKU — a (product × printing × condition × language) combination.

    SKUs are embedded inside :class:`ProductDetails` and are the atomic unit
    for market price lookups. Pass :attr:`sku_id` to
    :meth:`~tcg.TCGplayerClient.market_price` to get per-variant pricing.

    Attributes:
        sku_id: Numeric TCGplayer SKU identifier.
        printing: Foiling / treatment label (e.g. ``"Normal"``, ``"Foil"``).
        condition: Card condition label (e.g. ``"Near Mint"``,
            ``"Lightly Played"``).
        language: Language of the card (e.g. ``"English"``).
    """

    sku_id: int
    printing: str  # "Normal" / "Foil"
    condition: str  # "Near Mint" / ...
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
    """Full metadata and pricing summary for one TCGplayer product.

    Returned by :meth:`~tcg.TCGplayerClient.product_details`. This is
    TCGplayer's authoritative per-product record. ``market_price`` is the
    Normal NM product-level value; for Foil or other variant prices use
    :meth:`~tcg.TCGplayerClient.market_price` with the relevant SKU IDs.

    Attributes:
        product_id: Numeric TCGplayer product ID.
        product_name: Display name of the card / product.
        set_name: Display name of the set.
        set_code: Short set identifier (e.g. ``"DTR1E"``, ``"PTM"``), or
            ``None`` if not reported.
        collector_number: Collector number within the set (e.g. ``"004"``),
            or ``None`` if not reported.
        rarity_name: Rarity label (e.g. ``"Rare"``), or ``None``.
        market_price: Normal NM market price in USD at the product level, or
            ``None`` if unavailable. For Foil market price, query the
            pricepoints endpoint via :meth:`~tcg.TCGplayerClient.market_price`.
        lowest_price: Lowest listing price in USD across all variants, or
            ``None``.
        median_price: Median listing price in USD across all variants, or
            ``None``.
        lowest_price_with_shipping: Lowest combined price + shipping in USD,
            or ``None``.
        sellers: Number of distinct sellers with active listings, or ``None``
            if not reported.
        foil_only: ``True`` if this product exists only in foil.
        normal_only: ``True`` if this product exists only in non-foil.
        skus: All SKUs for this product (all printings × conditions ×
            languages). Use to find the :attr:`Sku.sku_id` for a specific
            variant.
    """

    product_id: int
    product_name: str
    set_name: str
    set_code: str | None  # e.g. "DTR1E", "PTM"
    collector_number: str | None  # e.g. "004", "013"
    rarity_name: str | None
    market_price: float | None  # Normal NM (product-level)
    lowest_price: float | None  # lowest across all variants of this product
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
    """Market price statistics for one SKU.

    Returned by :meth:`~tcg.TCGplayerClient.market_price`. Each instance
    corresponds to one (product × printing × condition × language) SKU.
    Normal and Foil variants have separate :class:`MarketPrice` rows.

    Attributes:
        sku_id: Numeric TCGplayer SKU identifier.
        market_price: Computed market price in USD, or ``None`` if
            insufficient data. TCGplayer derives this from recent sales.
        lowest_price: Lowest active listing price in USD, or ``None``.
        highest_price: Highest active listing price in USD, or ``None``.
        price_count: Number of recent sale data points used to calculate
            ``market_price``, or ``None`` if not reported.
        calculated_at: Server-side ISO-8601 timestamp of when this market
            price was last computed (e.g. ``"2026-04-30T12:00:00"``), or
            ``None``.
    """

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

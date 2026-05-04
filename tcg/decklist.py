"""Decklist enrichment logic — pure orchestration on top of TCGplayerClient.

This module is the business-logic layer for resolving a parsed decklist to
per-card, per-variant price data.  No I/O outside the client calls; no Rich
or stdout writes.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from tcg.client import TCGplayerClient, TCGplayerError
from tcg.deck import DeckEntry
from tcg.models import AutocompleteHit, Listing, MarketPrice, ProductDetails, Sale

# Hardcoded internals — not user-facing flags.
_LISTINGS_LIMIT = 20
_SALES_LIMIT = 25

_SPECIAL_SUFFIX_RE = re.compile(r"\s*\([^)]+\)\s*$")


def pick_best_hit(
    hits: list[AutocompleteHit],
    card_name: str,
    product_line: str | None,
) -> AutocompleteHit | None:
    """Prefer product-line match, then exact base-name (no parenthetical
    suffix like '(CSR)'), then highest score."""
    if product_line:
        hits = [h for h in hits if h.product_line_name == product_line]
    if not hits:
        return None

    target = card_name.lower().strip()

    def base_name(name: str) -> str:
        return _SPECIAL_SUFFIX_RE.sub("", name).lower().strip()

    exact = [h for h in hits if base_name(h.product_name) == target]
    pool = exact or hits
    no_suffix = [h for h in pool if "(" not in h.product_name]
    pool = no_suffix or pool
    return max(pool, key=lambda h: h.score)


@dataclass
class VariantStats:
    """Price statistics for one (printing × condition) combination of a card.

    Produced by ``build_variants()`` and embedded inside :class:`DeckRow`.
    Normal and Foil variants are separate instances with independent market
    prices. All prices are in USD.

    Attributes:
        printing: Foiling / treatment label (e.g. ``"Normal"``, ``"Foil"``).
        condition: Card condition label (e.g. ``"Near Mint"``,
            ``"Lightly Played"``).
        sku_id: TCGplayer SKU ID for this specific variant, or ``None`` if
            the SKU could not be resolved from :class:`~tcg.ProductDetails`.
        market_price: TCGplayer market price in USD for this variant, or
            ``None`` if no data. Normal and Foil have separate values.
        market_price_count: Number of recent sale data points behind
            ``market_price``, or ``None`` if not available.
        listing_min: Lowest active listing price in USD, or ``None`` if no
            listings were found.
        listing_avg: Mean active listing price in USD, or ``None``.
        listing_count: Number of active listings included in the stats.
        sale_avg: Mean purchase price in USD from recent sales, or ``None``
            if no sales data.
        most_recent_sale: Purchase price in USD of the most recent sale by
            ``order_date``, or ``None``.
        sale_count: Number of recent sale records included in the stats.
    """

    printing: str  # "Normal" / "Foil"
    condition: str  # "Near Mint" / "Lightly Played" / ...
    sku_id: int | None  # TCGplayer SKU for this variant
    market_price: (
        float | None
    )  # Market price for this variant (Normal and Foil have separate values)
    market_price_count: int | None  # Number of data points behind the market price
    listing_min: float | None
    listing_avg: float | None
    listing_count: int
    sale_avg: float | None
    most_recent_sale: float | None  # Most recent sale by orderDate
    sale_count: int


@dataclass
class DeckRow:
    """One resolved decklist entry, enriched with pricing data.

    Produced by ``enrich()`` and consumed by :func:`~tcg.print_tsv`. A
    single decklist line (e.g. ``"2x Alice, Golden Queen"``) typically yields
    one ``DeckRow`` per set that card appears in. Cards that could not be
    resolved have a non-``None`` ``missing_reason`` and empty ``variants``.

    Attributes:
        section: Decklist section label (e.g. ``"Main Deck"``,
            ``"Side Deck"``).
        quantity: Number of copies specified in the decklist.
        card_name: Card name exactly as it appeared in the decklist input.
        product_id: TCGplayer product ID, or ``None`` if resolution failed.
        matched_name: Product name as returned by TCGplayer (may differ from
            ``card_name`` in capitalisation), or ``None``.
        set_name: Display name of the set, or ``None``.
        set_code: Short set identifier (e.g. ``"DTR1E"``), or ``None``.
        collector_number: Collector number within the set, or ``None``.
        rarity: Rarity label, or ``None``.
        release_date: ISO-8601 release date (e.g. ``"2026-03-21"``), used
            for newest-first reprint ordering, or ``None``.
        image_url: CDN URL for a 200 px product image, or ``None``.
        variants: Per-variant price statistics. Empty when no pricing data
            was found or when ``missing_reason`` is set.
        missing_reason: Human-readable explanation of why the card could not
            be resolved (e.g. ``"no match"``), or ``None`` on success.
    """

    section: str
    quantity: int
    card_name: str
    product_id: int | None
    matched_name: str | None
    set_name: str | None
    set_code: str | None = None
    collector_number: str | None = None
    rarity: str | None = None
    release_date: str | None = None  # ISO-8601, used for new->old reprint ordering
    image_url: str | None = None
    variants: list[VariantStats] = field(default_factory=list)
    missing_reason: str | None = None


def _group_listings(listings: list[Listing]) -> dict[tuple[str, str], list[float]]:
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for listing in listings:
        if listing.price <= 0:
            continue
        key = (listing.printing or "Unknown", listing.condition or "Unknown")
        buckets[key].append(listing.price)
    return buckets


def _group_sales(sales: list[Sale]) -> dict[tuple[str, str], list[Sale]]:
    """Keep full Sale objects so we can pick most-recent by orderDate."""
    buckets: dict[tuple[str, str], list[Sale]] = defaultdict(list)
    for s in sales:
        if s.purchase_price <= 0:
            continue
        printing = s.variant or "Unknown"
        key = (printing, s.condition or "Unknown")
        buckets[key].append(s)
    return buckets


def build_variants(
    listings: list[Listing],
    sales: list[Sale],
    details: ProductDetails | None = None,
    market_by_sku: dict[int, MarketPrice] | None = None,
) -> list[VariantStats]:
    l_buckets = _group_listings(listings)
    s_buckets = _group_sales(sales)
    keys = set(l_buckets) | set(s_buckets)

    # Seed with all SKUs from product details so variants show up even with 0
    # listings/sales (the whole point: Foil NM market price exists even when no
    # one's bought one recently).
    if details is not None:
        for sku in details.skus:
            # Only English for now — most TCG players trade English singles.
            if sku.language == "English":
                keys.add((sku.printing, sku.condition))

    out: list[VariantStats] = []
    for key in sorted(keys):
        printing, condition = key
        lp = l_buckets.get(key, [])
        sales_in_bucket = s_buckets.get(key, [])
        sp = [s.purchase_price for s in sales_in_bucket]
        most_recent = None
        if sales_in_bucket:
            most_recent = max(sales_in_bucket, key=lambda s: s.order_date or "").purchase_price

        sku_id = None
        market_price = None
        market_price_count = None
        if details is not None:
            sku = details.find_sku(printing, condition)
            if sku is not None:
                sku_id = sku.sku_id
                if market_by_sku and sku.sku_id in market_by_sku:
                    mp = market_by_sku[sku.sku_id]
                    market_price = mp.market_price
                    market_price_count = mp.price_count

        out.append(
            VariantStats(
                printing=printing,
                condition=condition,
                sku_id=sku_id,
                market_price=market_price,
                market_price_count=market_price_count,
                listing_min=min(lp) if lp else None,
                listing_avg=sum(lp) / len(lp) if lp else None,
                listing_count=len(lp),
                sale_avg=sum(sp) / len(sp) if sp else None,
                most_recent_sale=most_recent,
                sale_count=len(sp),
            )
        )
    # Order: Normal first, then Foil, then others. Within printing, NM first.
    _printing_order = {"Normal": 0, "Foil": 1}
    _condition_order = {
        "Near Mint": 0,
        "Lightly Played": 1,
        "Moderately Played": 2,
        "Heavily Played": 3,
        "Damaged": 4,
    }
    out.sort(
        key=lambda v: (
            _printing_order.get(v.printing, 99),
            _condition_order.get(v.condition, 99),
        )
    )
    return out


def _fetch_one_product(
    client: TCGplayerClient,
    entry: DeckEntry,
    product_id: int,
    fallback_name: str,
    fallback_set: str | None,
    fallback_release_date: str | None,
) -> tuple[DeckRow, list, list]:
    """Fetch all per-variant price data for a single product and build a DeckRow."""
    details = client.product_details(product_id)
    sales = client.latest_sales(product_id, limit=_SALES_LIMIT)
    listings = client.listings(product_id, limit=_LISTINGS_LIMIT)

    market_by_sku: dict[int, MarketPrice] = {}
    if details is not None and details.skus:
        sku_ids = [s.sku_id for s in details.skus if s.language == "English"]
        if sku_ids:
            mps = client.market_price(sku_ids)
            market_by_sku = {mp.sku_id: mp for mp in mps}

    variants = build_variants(listings, sales, details=details, market_by_sku=market_by_sku)

    row = DeckRow(
        section=entry.section,
        quantity=entry.quantity,
        card_name=entry.card_name,
        product_id=product_id,
        matched_name=details.product_name if details else fallback_name,
        set_name=(details.set_name if details and details.set_name else fallback_set),
        set_code=details.set_code if details else None,
        collector_number=details.collector_number if details else None,
        rarity=details.rarity_name if details else None,
        release_date=fallback_release_date,
        image_url=details.image_url if details else None,
        variants=variants,
    )
    return row, sales, listings


def enrich(
    client: TCGplayerClient,
    entry: DeckEntry,
    product_line: str | None,
) -> list[tuple[DeckRow, list, list]]:
    """Resolve a decklist entry to one or more DeckRow results.

    A single-set card yields one result. A reprinted card yields multiple
    results — one per set it appeared in, ordered newest release first.
    """
    # Step 1: autocomplete to disambiguate. Unambiguous (one hit) cards
    # take the fast path; reprint aggregates (filtered out at the client
    # layer as duplicate=true) leave `hits` empty and fall through to
    # search_products.
    try:
        hits = client.autocomplete(entry.card_name)
    except TCGplayerError as e:
        return [
            (
                DeckRow(
                    entry.section,
                    entry.quantity,
                    entry.card_name,
                    None,
                    None,
                    None,
                    missing_reason=f"autocomplete failed: {e}",
                ),
                [],
                [],
            )
        ]

    hit = pick_best_hit(hits, entry.card_name, product_line)

    if hit is not None:
        # Unambiguous single-product case. Keep the existing fast path.
        return [
            _fetch_one_product(
                client,
                entry,
                hit.product_id,
                fallback_name=hit.product_name,
                fallback_set=hit.set_name,
                fallback_release_date=None,
            )
        ]

    # Step 2: autocomplete did not resolve — likely a reprint aggregate.
    # Fall back to the search API to enumerate every set the card appears in.
    try:
        candidates = client.search_products(entry.card_name, product_line=product_line)
    except TCGplayerError as e:
        return [
            (
                DeckRow(
                    entry.section,
                    entry.quantity,
                    entry.card_name,
                    None,
                    None,
                    None,
                    missing_reason=f"search failed: {e}",
                ),
                [],
                [],
            )
        ]

    if not candidates:
        return [
            (
                DeckRow(
                    entry.section,
                    entry.quantity,
                    entry.card_name,
                    None,
                    None,
                    None,
                    missing_reason="no match",
                ),
                [],
                [],
            )
        ]

    # Order newest release first — the first row is the most recent reprint.
    candidates.sort(key=lambda c: c.release_date or "", reverse=True)

    return [
        _fetch_one_product(
            client,
            entry,
            c.product_id,
            fallback_name=c.product_name,
            fallback_set=c.set_name,
            fallback_release_date=c.release_date,
        )
        for c in candidates
    ]

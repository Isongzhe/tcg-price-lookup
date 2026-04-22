"""批次查詢整份牌表的價格。

用法:
    # 從檔案
    uv run python -m scripts.fetch_deck deck.txt

    # 從 stdin（貼上後 Ctrl+D 結束；或用管線）
    pbpaste | uv run python -m scripts.fetch_deck -

    # 只看某個卡池 + 輸出 JSON
    uv run python -m scripts.fetch_deck deck.txt \
        --product-line "Grand Archive TCG" \
        --json deck_prices.json

牌表格式:
    # Material Deck
    1 Alice, Golden Queen

    # Main Deck
    4 Some Card
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from tcg.client import TCGplayerClient, TCGplayerError
from tcg.deck import DeckEntry, parse_decklist
from tcg.models import AutocompleteHit, Listing, MarketPrice, ProductDetails, Sale
from tcg.storage import append_snapshot, snapshot_to_rows

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
    """一張卡一個（printing, condition）組合的價格統計。"""
    printing: str           # "Normal" / "Foil"
    condition: str          # "Near Mint" / "Lightly Played" / ...
    sku_id: int | None              # 該 variant 的 TCGplayer SKU
    market_price: float | None       # 該 variant 的 Market Price（Normal / Foil 各有一個）
    market_price_count: int | None   # market price 背後的樣本數
    listing_min: float | None
    listing_avg: float | None
    listing_count: int
    sale_avg: float | None
    most_recent_sale: float | None   # 按 orderDate 最近一筆
    sale_count: int


@dataclass
class DeckRow:
    section: str
    quantity: int
    card_name: str
    product_id: int | None
    matched_name: str | None
    set_name: str | None
    rarity: str | None = None
    variants: list[VariantStats] = field(default_factory=list)
    missing_reason: str | None = None


def _group_listings(listings: list[Listing]) -> dict[tuple[str, str], list[float]]:
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for l in listings:
        if l.price <= 0:
            continue
        key = (l.printing or "Unknown", l.condition or "Unknown")
        buckets[key].append(l.price)
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
    details: "ProductDetails | None" = None,
    market_by_sku: "dict[int, MarketPrice] | None" = None,
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

        out.append(VariantStats(
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
        ))
    # Order: Normal first, then Foil, then others. Within printing, NM first.
    _printing_order = {"Normal": 0, "Foil": 1}
    _condition_order = {"Near Mint": 0, "Lightly Played": 1, "Moderately Played": 2,
                        "Heavily Played": 3, "Damaged": 4}
    out.sort(key=lambda v: (
        _printing_order.get(v.printing, 99),
        _condition_order.get(v.condition, 99),
    ))
    return out


def enrich(
    client: TCGplayerClient,
    entry: DeckEntry,
    product_line: str | None,
    listings_limit: int,
    sales_limit: int,
) -> tuple[DeckRow, list, list]:
    try:
        hits = client.autocomplete(entry.card_name)
    except TCGplayerError as e:
        return (
            DeckRow(
                entry.section, entry.quantity, entry.card_name,
                None, None, None,
                missing_reason=f"autocomplete failed: {e}",
            ),
            [], [],
        )

    hit = pick_best_hit(hits, entry.card_name, product_line)
    if hit is None:
        return (
            DeckRow(
                entry.section, entry.quantity, entry.card_name,
                None, None, None,
                missing_reason="no match",
            ),
            [], [],
        )

    details = client.product_details(hit.product_id)
    sales = client.latest_sales(hit.product_id, limit=sales_limit)
    listings = client.listings(hit.product_id, limit=listings_limit)

    # Batch-fetch market prices for all English SKUs of this product
    # (one request covers Normal NM, Foil NM, and all condition tiers).
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
        product_id=hit.product_id,
        matched_name=hit.product_name,
        set_name=hit.set_name,
        rarity=details.rarity_name if details else None,
        variants=variants,
    )
    return row, sales, listings


def _fmt(v: float | None) -> str:
    return f"{v:.2f}" if v is not None else ""


def print_tsv(rows: list[DeckRow], variants_filter: set[str] | None = None) -> None:
    """One row per (card × variant). Raw data only — aggregation is Sheet's job.
    variants_filter: if given, only emit rows whose printing is in the set."""
    headers = [
        "section", "qty", "card_name", "matched_name", "set_name", "rarity",
        "product_id", "sku_id",
        "printing", "condition",
        "market_price",         # per-variant (Foil has its own!)
        "mp_sample",            # how many data points the market price is based on
        "most_recent_sale", "sale_avg", "sale_count",
        "listing_min", "listing_avg", "listing_count",
        "missing",
    ]
    print("\t".join(headers))
    for r in rows:
        if not r.variants:
            print("\t".join([
                r.section, str(r.quantity), r.card_name,
                r.matched_name or "", r.set_name or "", r.rarity or "",
                str(r.product_id or ""), "", "", "",
                "", "", "", "", "0", "", "", "0",
                r.missing_reason or "",
            ]))
            continue
        for v in r.variants:
            if variants_filter and v.printing not in variants_filter:
                continue
            print("\t".join([
                r.section, str(r.quantity), r.card_name,
                r.matched_name or "", r.set_name or "", r.rarity or "",
                str(r.product_id or ""), str(v.sku_id or ""),
                v.printing, v.condition,
                _fmt(v.market_price),
                str(v.market_price_count) if v.market_price_count is not None else "",
                _fmt(v.most_recent_sale),
                _fmt(v.sale_avg), str(v.sale_count),
                _fmt(v.listing_min), _fmt(v.listing_avg), str(v.listing_count),
                "",
            ]))


def print_summary(rows: list[DeckRow]) -> None:
    """Reference totals. Real aggregation is Sheet's job."""
    missing = [r for r in rows if r.missing_reason]

    def total_for(printing: str, condition: str = "Near Mint") -> tuple[float, int]:
        """Returns (sum, cards_with_price)."""
        total = 0.0
        n = 0
        for r in rows:
            v = next((v for v in r.variants
                      if v.printing == printing and v.condition == condition), None)
            if v and v.market_price is not None:
                total += v.market_price * r.quantity
                n += 1
        return total, n

    normal_total, normal_n = total_for("Normal")
    foil_total, foil_n = total_for("Foil")

    print(
        f"\n[reference] Normal NM Market Price × qty = ${normal_total:.2f} USD  "
        f"({normal_n}/{len(rows)} cards priced)",
        file=sys.stderr,
    )
    if foil_n > 0:
        print(
            f"[reference] Foil   NM Market Price × qty = ${foil_total:.2f} USD  "
            f"({foil_n}/{len(rows)} cards priced)",
            file=sys.stderr,
        )
    print(
        "  ↑ 真實加總請在 Sheet 用 SUMPRODUCT/QUERY 按 printing 自己算。",
        file=sys.stderr,
    )

    if missing:
        print("\nMissing:", file=sys.stderr)
        for r in missing:
            print(f"  - [{r.section}] {r.quantity}x {r.card_name}  ({r.missing_reason})", file=sys.stderr)


def read_input(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch fetch prices for a decklist")
    parser.add_argument("source", help="path to decklist file, or '-' for stdin")
    parser.add_argument("--product-line", default=None, help="e.g. 'Grand Archive TCG'")
    parser.add_argument("--json", dest="json_out", default=None, help="write detailed JSON to this path")
    parser.add_argument("--no-parquet", action="store_true", help="skip appending to data/snapshots.parquet")
    parser.add_argument("--sleep", type=float, default=0.8, help="seconds between cards (politeness)")
    parser.add_argument("--listings", type=int, default=20)
    parser.add_argument("--sales", type=int, default=25)
    parser.add_argument(
        "--printings",
        default="Normal,Foil",
        help="comma-separated printings to show (default: Normal,Foil). Use 'all' for everything.",
    )
    parser.add_argument(
        "--conditions",
        default="Near Mint",
        help="comma-separated conditions to show (default: 'Near Mint'). Use 'all' for everything.",
    )
    args = parser.parse_args(argv)

    text = read_input(args.source)
    entries = parse_decklist(text)
    if not entries:
        print("no deck entries parsed", file=sys.stderr)
        return 1

    print(f"[*] Parsed {len(entries)} entries from {args.source}", file=sys.stderr)

    client = TCGplayerClient()
    rows: list[DeckRow] = []

    for i, entry in enumerate(entries, 1):
        print(f"[{i}/{len(entries)}] {entry.quantity}x {entry.card_name}", file=sys.stderr)
        row, sales, listings = enrich(
            client, entry, args.product_line,
            listings_limit=args.listings, sales_limit=args.sales,
        )
        rows.append(row)

        if not args.no_parquet and row.product_id is not None:
            snap_rows = snapshot_to_rows(
                product_id=row.product_id,
                card_name=row.matched_name or row.card_name,
                sales=sales, listings=listings, market_prices=[],
            )
            append_snapshot(snap_rows)

        if i < len(entries):
            time.sleep(args.sleep)

    printings_filter: set[str] | None = None
    conditions_filter: set[str] | None = None
    if args.printings.strip().lower() != "all":
        printings_filter = {p.strip() for p in args.printings.split(",") if p.strip()}
    if args.conditions.strip().lower() != "all":
        conditions_filter = {c.strip() for c in args.conditions.split(",") if c.strip()}

    # Apply condition filter by pruning variants before output (printing filter
    # handled inline in print_tsv so summary stays accurate).
    if conditions_filter is not None:
        for r in rows:
            r.variants = [v for v in r.variants if v.condition in conditions_filter]

    print_tsv(rows, variants_filter=printings_filter)
    print_summary(rows)

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps([asdict(r) for r in rows], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[+] JSON written to {args.json_out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())

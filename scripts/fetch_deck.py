"""Batch fetch prices for an entire decklist.

Usage:
    # From a file
    uv run python -m scripts.fetch_deck deck.txt

    # From stdin (paste, then Ctrl+D; or pipe)
    pbpaste | uv run python -m scripts.fetch_deck -

    # Specify a product line, suppress clipboard copy
    uv run python -m scripts.fetch_deck deck.txt \\
        --product-line "Grand Archive TCG" \\
        --no-copy

Decklist format:
    # Material Deck
    1 Alice, Golden Queen

    # Main Deck
    4 Some Card
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from tcg.client import TCGplayerClient, TCGplayerError
from tcg.clipboard import write_to_clipboard
from tcg.config import load_config
from tcg.deck import DeckEntry, parse_decklist
from tcg.models import AutocompleteHit, Listing, MarketPrice, ProductDetails, Sale
from tcg.product_lines import PRODUCT_LINES, suggest, to_slug
from tcg.storage import HISTORY_AVAILABLE, append_snapshot, snapshot_to_rows

# All human-facing output goes through this console (stderr). stdout is
# reserved for the TSV so piping through pbcopy/xclip works cleanly.
console = Console(stderr=True)

_SPECIAL_SUFFIX_RE = re.compile(r"\s*\([^)]+\)\s*$")

# Hardcoded internals — not user-facing flags.
_SLEEP_BETWEEN_CARDS = 0.8
_LISTINGS_LIMIT = 20
_SALES_LIMIT = 25


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
    """Price statistics for one (printing, condition) combination of a card."""

    printing: str           # "Normal" / "Foil"
    condition: str          # "Near Mint" / "Lightly Played" / ...
    sku_id: int | None              # TCGplayer SKU for this variant
    market_price: float | None      # Market price for this variant (Normal and Foil have separate values)
    market_price_count: int | None  # Number of data points behind the market price
    listing_min: float | None
    listing_avg: float | None
    listing_count: int
    sale_avg: float | None
    most_recent_sale: float | None  # Most recent sale by orderDate
    sale_count: int


@dataclass
class DeckRow:
    section: str
    quantity: int
    card_name: str
    product_id: int | None
    matched_name: str | None
    set_name: str | None
    set_code: str | None = None
    collector_number: str | None = None
    rarity: str | None = None
    release_date: str | None = None     # ISO-8601, used for new->old reprint ordering
    image_url: str | None = None
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
        return [(
            DeckRow(
                entry.section, entry.quantity, entry.card_name,
                None, None, None,
                missing_reason=f"autocomplete failed: {e}",
            ),
            [], [],
        )]

    hit = pick_best_hit(hits, entry.card_name, product_line)

    if hit is not None:
        # Unambiguous single-product case. Keep the existing fast path.
        return [_fetch_one_product(
            client, entry, hit.product_id,
            fallback_name=hit.product_name,
            fallback_set=hit.set_name,
            fallback_release_date=None,
        )]

    # Step 2: autocomplete did not resolve — likely a reprint aggregate.
    # Fall back to the search API to enumerate every set the card appears in.
    try:
        candidates = client.search_products(entry.card_name, product_line=product_line)
    except TCGplayerError as e:
        return [(
            DeckRow(
                entry.section, entry.quantity, entry.card_name,
                None, None, None,
                missing_reason=f"search failed: {e}",
            ),
            [], [],
        )]

    if not candidates:
        return [(
            DeckRow(
                entry.section, entry.quantity, entry.card_name,
                None, None, None,
                missing_reason="no match",
            ),
            [], [],
        )]

    # Order newest release first — the first row is the most recent reprint.
    candidates.sort(key=lambda c: c.release_date or "", reverse=True)

    return [
        _fetch_one_product(
            client, entry, c.product_id,
            fallback_name=c.product_name,
            fallback_set=c.set_name,
            fallback_release_date=c.release_date,
        )
        for c in candidates
    ]


def _fmt(v: float | None) -> str:
    return f"{v:.2f}" if v is not None else ""


def print_tsv(
    rows: list[DeckRow],
    variants_filter: set[str] | None = None,
    file: "io.TextIOBase | None" = None,
) -> None:
    """One row per (card x variant). Raw data only — aggregation is Sheet's job.

    variants_filter: if given, only emit rows whose printing is in the set.
    file: output target; defaults to sys.stdout.
    """
    if file is None:
        file = sys.stdout

    headers = [
        "section", "qty", "card_name", "matched_name",
        "set_name", "set_code", "number", "rarity",
        "released",             # ISO date; used for sorting reprints new->old
        "product_id", "sku_id",
        "printing", "condition",
        "market_price",         # per-variant (Foil has its own!)
        "mp_sample",            # how many data points the market price is based on
        "most_recent_sale", "sale_avg", "sale_count",
        "listing_min", "listing_avg", "listing_count",
        "image_url",
        "missing",
    ]

    def _release(r: DeckRow) -> str:
        # Keep just the YYYY-MM-DD portion so the cell is short and sorts cleanly.
        return (r.release_date or "")[:10]

    print("\t".join(headers), file=file)
    for r in rows:
        if not r.variants:
            print("\t".join([
                r.section, str(r.quantity), r.card_name,
                r.matched_name or "",
                r.set_name or "", r.set_code or "", r.collector_number or "", r.rarity or "",
                _release(r),
                str(r.product_id or ""), "",
                "", "",
                "", "",
                "", "", "0",
                "", "", "0",
                r.image_url or "",
                r.missing_reason or "",
            ]), file=file)
            continue
        for v in r.variants:
            if variants_filter and v.printing not in variants_filter:
                continue
            print("\t".join([
                r.section, str(r.quantity), r.card_name,
                r.matched_name or "",
                r.set_name or "", r.set_code or "", r.collector_number or "", r.rarity or "",
                _release(r),
                str(r.product_id or ""), str(v.sku_id or ""),
                v.printing, v.condition,
                _fmt(v.market_price),
                str(v.market_price_count) if v.market_price_count is not None else "",
                _fmt(v.most_recent_sale),
                _fmt(v.sale_avg), str(v.sale_count),
                _fmt(v.listing_min), _fmt(v.listing_avg), str(v.listing_count),
                r.image_url or "",
                "",
            ]), file=file)


def print_summary(rows: list[DeckRow], clipboard_copied: bool) -> None:
    """Post-run UX: loud banner for missing cards, one-line status count,
    and clipboard status.

    Aggregation totals are intentionally omitted — that belongs in the
    spreadsheet where the user controls which printing/condition counts.
    """
    from rich.panel import Panel
    from rich.table import Table

    missing = [r for r in rows if r.missing_reason]
    ok = len(rows) - len(missing)

    console.print()

    if missing:
        miss_table = Table(show_header=True, header_style="bold white", box=None)
        miss_table.add_column("Section", style="dim")
        miss_table.add_column("Qty", justify="right", style="dim")
        miss_table.add_column("Card", style="bold yellow")
        miss_table.add_column("Reason", style="red")
        for r in missing:
            miss_table.add_row(
                r.section or "",
                str(r.quantity),
                r.card_name,
                r.missing_reason or "",
            )
        console.print(
            Panel(
                miss_table,
                title=f"[bold red]NOT FOUND — {len(missing)} card(s) need attention[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )

    status_style = "green" if not missing else "yellow"
    status_line = f"[{status_style}]{ok}/{len(rows)} cards priced[/{status_style}]"
    if missing:
        status_line += f"  [red]· {len(missing)} missing[/red]"
    console.print(status_line)

    if clipboard_copied:
        console.print("[green]Copied TSV to clipboard.[/green]")
    else:
        # Stdout might have been piped — give the usual hint.
        stdout_piped = not sys.stdout.isatty()
        if stdout_piped:
            console.print(
                "[cyan]TSV sent to stdout.[/cyan] "
                "[dim]If you piped to `pbcopy` / `xclip` / `wl-copy`, "
                "it is on your clipboard now — paste into Sheets.[/dim]"
            )
        else:
            console.print(
                "[dim]TSV printed above. Pipe to `| pbcopy` "
                "(macOS) or `| xclip -selection clipboard` (Linux) to copy.[/dim]"
            )


def read_input(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch fetch prices for a decklist")
    parser.add_argument(
        "source",
        nargs="?",
        default=None,
        help="path to decklist file, or '-' for stdin",
    )
    parser.add_argument(
        "--product-line",
        default=None,
        help="filter to a specific product line, e.g. 'Grand Archive TCG' (default from config)",
    )
    parser.add_argument(
        "--list-product-lines",
        action="store_true",
        help="print all known product lines as display<TAB>slug, then exit",
    )
    parser.add_argument(
        "--printings",
        default=None,
        help="comma-separated printings to show (default from config: Normal,Foil). Use 'all' for everything.",
    )
    parser.add_argument(
        "--conditions",
        default=None,
        help="comma-separated conditions to show (default from config: Near Mint). Use 'all' for everything.",
    )
    parser.add_argument(
        "--parquet",
        action="store_true",
        default=False,
        help="append a snapshot to data/snapshots.parquet (opt-in; requires the 'history' extras)",
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="disable auto-copy of TSV to clipboard for this run",
    )
    parser.add_argument(
        "--config",
        dest="config_path",
        default=None,
        type=Path,
        help="path to a TOML config file (overrides default search locations)",
    )
    args = parser.parse_args(argv)

    # --list-product-lines: print and exit immediately (before config needed)
    if args.list_product_lines:
        for display, slug in PRODUCT_LINES.items():
            print(f"{display}\t{slug}")
        return 0

    if args.source is None:
        parser.error("the following arguments are required: source")

    # Build config — CLI values only override when explicitly passed (non-None).
    cli_overrides: dict = {}
    if args.product_line is not None:
        cli_overrides["product_line"] = args.product_line
    if args.printings is not None:
        # Convert comma string to list for the config layer
        cli_overrides["printings"] = [p.strip() for p in args.printings.split(",") if p.strip()]
    if args.conditions is not None:
        cli_overrides["conditions"] = [c.strip() for c in args.conditions.split(",") if c.strip()]
    if args.parquet:
        cli_overrides["write_parquet"] = True

    config = load_config(cli_overrides, config_path=args.config_path)

    # Soft validation of --product-line
    if args.product_line is not None and to_slug(args.product_line) is None:
        console.print(
            f"[yellow]Warning: product line {args.product_line!r} is not in the known list.[/yellow]"
        )
        hints = suggest(args.product_line)
        if hints:
            console.print(f"[dim]Did you mean: {', '.join(hints)}?[/dim]")

    text = read_input(args.source)
    entries = parse_decklist(text)
    if not entries:
        console.print("[red]No deck entries parsed.[/red]")
        return 1

    console.print(
        f"[dim]Parsed[/dim] [bold]{len(entries)}[/bold] "
        f"[dim]entries from[/dim] [cyan]{args.source}[/cyan]"
    )

    client = TCGplayerClient()
    rows: list[DeckRow] = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]·[/dim]"),
        TimeElapsedColumn(),
        TextColumn("[dim]·[/dim]"),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )

    with progress:
        task_id = progress.add_task("[cyan]Fetching prices[/cyan]", total=len(entries))
        for i, entry in enumerate(entries, 1):
            progress.update(
                task_id,
                description=f"[cyan]{entry.quantity}x[/cyan] {entry.card_name}",
            )
            results = enrich(client, entry, config.product_line)
            parquet_enabled = HISTORY_AVAILABLE and (args.parquet or config.write_parquet)
            for row, sales, listings in results:
                rows.append(row)
                if parquet_enabled and row.product_id is not None:
                    snap_rows = snapshot_to_rows(
                        product_id=row.product_id,
                        card_name=row.matched_name or row.card_name,
                        sales=sales, listings=listings, market_prices=[],
                    )
                    append_snapshot(snap_rows)

            progress.advance(task_id)
            if i < len(entries):
                time.sleep(_SLEEP_BETWEEN_CARDS)

    # Resolve filter sets from config
    printings_str = ",".join(config.printings)
    conditions_str = ",".join(config.conditions)

    printings_filter: set[str] | None = None
    conditions_filter: set[str] | None = None
    if printings_str.strip().lower() != "all":
        printings_filter = {p.strip() for p in config.printings if p.strip()}
    if conditions_str.strip().lower() != "all":
        conditions_filter = {c.strip() for c in config.conditions if c.strip()}

    # Apply condition filter by pruning variants before output (printing filter
    # handled inline in print_tsv so summary stays accurate).
    if conditions_filter is not None:
        for r in rows:
            r.variants = [v for v in r.variants if v.condition in conditions_filter]

    # Build TSV into a buffer so we can print it AND copy to clipboard.
    tsv_buf = io.StringIO()
    print_tsv(rows, variants_filter=printings_filter, file=tsv_buf)
    tsv_text = tsv_buf.getvalue()

    # Print TSV to stdout
    sys.stdout.write(tsv_text)
    sys.stdout.flush()

    # Auto-clipboard
    clipboard_copied = False
    if config.copy_to_clipboard and not args.no_copy:
        clipboard_copied = write_to_clipboard(tsv_text)

    print_summary(rows, clipboard_copied=clipboard_copied)

    return 0


if __name__ == "__main__":
    sys.exit(main())

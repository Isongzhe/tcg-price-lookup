"""TSV output for decklist price data.

Stdlib-only. No Rich. No stdout side effects when a file target is passed.
"""

from __future__ import annotations

import sys

from tcg.decklist import DeckRow


def _fmt(v: float | None) -> str:
    return f"{v:.2f}" if v is not None else ""


def print_tsv(
    rows: list[DeckRow],
    variants_filter: set[str] | None = None,
    file: object | None = None,
) -> None:
    """Write enriched decklist data as a tab-separated table.

    Emits one header row followed by one data row per (card × variant)
    combination. Cards with no resolved variants emit a single placeholder
    row. Raw data only — aggregation (totals, averages across cards) is left
    to the consuming spreadsheet.

    Column order (stable contract, append-only within MAJOR):
    ``section``, ``qty``, ``card_name``, ``matched_name``, ``set_name``,
    ``set_code``, ``number``, ``rarity``, ``released``, ``product_id``,
    ``sku_id``, ``printing``, ``condition``, ``market_price``, ``mp_sample``,
    ``most_recent_sale``, ``sale_avg``, ``sale_count``, ``listing_min``,
    ``listing_avg``, ``listing_count``, ``image_url``, ``missing``.

    Args:
        rows: Enriched deck rows, typically produced by
            ``tcg.decklist.enrich()``. Each row may have zero or more
            :class:`~tcg.VariantStats` attached.
        variants_filter: If provided, only emit rows whose ``printing``
            field is a member of this set (e.g. ``{"Normal"}`` to suppress
            foil rows). ``None`` means emit all variants.
        file: Output target. Any object with a ``write`` method is accepted.
            Defaults to ``sys.stdout``.

    Returns:
        None. Output is written directly to ``file``.

    Example:
        >>> import io  # doctest: +SKIP
        >>> buf = io.StringIO()  # doctest: +SKIP
        >>> print_tsv(rows, file=buf)  # doctest: +SKIP
        >>> header = buf.getvalue().splitlines()[0]  # doctest: +SKIP
        >>> header.split("\\t")[0]  # doctest: +SKIP
        'section'
    """
    if file is None:
        file = sys.stdout

    headers = [
        "section",
        "qty",
        "card_name",
        "matched_name",
        "set_name",
        "set_code",
        "number",
        "rarity",
        "released",  # ISO date; used for sorting reprints new->old
        "product_id",
        "sku_id",
        "printing",
        "condition",
        "market_price",  # per-variant (Foil has its own!)
        "mp_sample",  # how many data points the market price is based on
        "most_recent_sale",
        "sale_avg",
        "sale_count",
        "listing_min",
        "listing_avg",
        "listing_count",
        "image_url",
        "missing",
    ]

    def _release(r: DeckRow) -> str:
        # Keep just the YYYY-MM-DD portion so the cell is short and sorts cleanly.
        return (r.release_date or "")[:10]

    print("\t".join(headers), file=file)
    for r in rows:
        if not r.variants:
            print(
                "\t".join(
                    [
                        r.section,
                        str(r.quantity),
                        r.card_name,
                        r.matched_name or "",
                        r.set_name or "",
                        r.set_code or "",
                        r.collector_number or "",
                        r.rarity or "",
                        _release(r),
                        str(r.product_id or ""),
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "0",
                        "",
                        "",
                        "0",
                        r.image_url or "",
                        r.missing_reason or "",
                    ]
                ),
                file=file,
            )
            continue
        for v in r.variants:
            if variants_filter and v.printing not in variants_filter:
                continue
            print(
                "\t".join(
                    [
                        r.section,
                        str(r.quantity),
                        r.card_name,
                        r.matched_name or "",
                        r.set_name or "",
                        r.set_code or "",
                        r.collector_number or "",
                        r.rarity or "",
                        _release(r),
                        str(r.product_id or ""),
                        str(v.sku_id or ""),
                        v.printing,
                        v.condition,
                        _fmt(v.market_price),
                        str(v.market_price_count) if v.market_price_count is not None else "",
                        _fmt(v.most_recent_sale),
                        _fmt(v.sale_avg),
                        str(v.sale_count),
                        _fmt(v.listing_min),
                        _fmt(v.listing_avg),
                        str(v.listing_count),
                        r.image_url or "",
                        "",
                    ]
                ),
                file=file,
            )

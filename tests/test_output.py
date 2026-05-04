"""Tests for tcg/output.py — print_tsv."""

from __future__ import annotations

import io

from tcg.decklist import DeckRow, VariantStats

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row(
    card_name: str = "Test Card",
    section: str = "Main Deck",
    qty: int = 1,
    product_id: int | None = 1,
    matched_name: str | None = "Test Card",
    set_name: str | None = "Test Set",
    variants: list[VariantStats] | None = None,
    missing_reason: str | None = None,
    release_date: str | None = None,
) -> DeckRow:
    return DeckRow(
        section=section,
        quantity=qty,
        card_name=card_name,
        product_id=product_id,
        matched_name=matched_name,
        set_name=set_name,
        variants=variants or [],
        missing_reason=missing_reason,
        release_date=release_date,
    )


def _variant(printing: str = "Normal", condition: str = "Near Mint") -> VariantStats:
    return VariantStats(
        printing=printing,
        condition=condition,
        sku_id=101,
        market_price=5.0,
        market_price_count=10,
        listing_min=4.0,
        listing_avg=4.5,
        listing_count=3,
        sale_avg=4.8,
        most_recent_sale=4.9,
        sale_count=5,
    )


EXPECTED_HEADERS = [
    "section",
    "qty",
    "card_name",
    "matched_name",
    "set_name",
    "set_code",
    "number",
    "rarity",
    "released",
    "product_id",
    "sku_id",
    "printing",
    "condition",
    "market_price",
    "mp_sample",
    "most_recent_sale",
    "sale_avg",
    "sale_count",
    "listing_min",
    "listing_avg",
    "listing_count",
    "image_url",
    "missing",
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

from tcg.output import print_tsv


def test_print_tsv_header_columns():
    buf = io.StringIO()
    print_tsv([], file=buf)
    lines = buf.getvalue().splitlines()
    assert len(lines) == 1
    assert lines[0].split("\t") == EXPECTED_HEADERS


def test_print_tsv_card_with_two_variants():
    row = _row(variants=[_variant("Normal"), _variant("Foil")])
    buf = io.StringIO()
    print_tsv([row], file=buf)
    lines = buf.getvalue().splitlines()
    # 1 header + 2 data rows
    assert len(lines) == 3
    # Each data row has the right number of columns
    for line in lines[1:]:
        assert len(line.split("\t")) == len(EXPECTED_HEADERS)


def test_print_tsv_missing_card_emits_one_row():
    row = _row(
        card_name="Ghost Card",
        product_id=None,
        matched_name=None,
        set_name=None,
        missing_reason="no match",
    )
    buf = io.StringIO()
    print_tsv([row], file=buf)
    lines = buf.getvalue().splitlines()
    assert len(lines) == 2
    cols = lines[1].split("\t")
    assert cols[len(EXPECTED_HEADERS) - 1] == "no match"  # last column = missing


def test_print_tsv_variants_filter():
    row = _row(variants=[_variant("Normal"), _variant("Foil")])
    buf = io.StringIO()
    print_tsv([row], file=buf, variants_filter={"Foil"})
    lines = buf.getvalue().splitlines()
    # 1 header + 1 Foil row (Normal filtered out)
    assert len(lines) == 2
    data_cols = lines[1].split("\t")
    assert data_cols[EXPECTED_HEADERS.index("printing")] == "Foil"


def test_print_tsv_writes_to_provided_file():
    buf = io.StringIO()
    row = _row(variants=[_variant()])
    print_tsv([row], file=buf)
    content = buf.getvalue()
    assert "section" in content
    assert "Test Card" in content


def test_print_tsv_release_date_truncated_to_yyyymmdd():
    row = _row(release_date="2025-12-13T00:00:00", variants=[_variant()])
    buf = io.StringIO()
    print_tsv([row], file=buf)
    lines = buf.getvalue().splitlines()
    data = lines[1].split("\t")
    released_col = EXPECTED_HEADERS.index("released")
    assert data[released_col] == "2025-12-13"

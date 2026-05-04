from tcg.deck import parse_decklist
from tcg.decklist import build_variants, pick_best_hit
from tcg.models import AutocompleteHit, Listing, Sale

SAMPLE = """# Material Deck
1 Alice, Golden Queen
1 Alice, Whim's Monarch

# Main Deck
4 Some Card

# Sideboard
"""


def test_parse_sections_and_entries():
    entries = parse_decklist(SAMPLE)
    assert len(entries) == 3
    assert entries[0].section == "Material Deck"
    assert entries[0].quantity == 1
    assert entries[0].card_name == "Alice, Golden Queen"
    assert entries[1].card_name == "Alice, Whim's Monarch"
    assert entries[2].section == "Main Deck"
    assert entries[2].quantity == 4


def test_parse_ignores_blank_and_header_only():
    entries = parse_decklist("# Main\n\n\n")
    assert entries == []


def test_parse_handles_indentation_and_extra_spaces():
    entries = parse_decklist("# X\n  2   Card Name  \n")
    assert len(entries) == 1
    assert entries[0].quantity == 2
    assert entries[0].card_name == "Card Name"


def test_parse_skips_lines_without_quantity():
    entries = parse_decklist("# X\nNo quantity here\n1 Real Card\n")
    assert len(entries) == 1
    assert entries[0].card_name == "Real Card"


def _hit(pid, name, line="Grand Archive TCG", score=1.0):
    return AutocompleteHit(pid, name, line, "Set", score)


def test_pick_best_hit_prefers_base_name():
    hits = [
        _hit(1, "Alice, Golden Queen (CSR)", score=2.0),
        _hit(2, "Alice, Golden Queen", score=3.0),
        _hit(3, "Alice, Golden Queen (CUR)", score=2.5),
    ]
    chosen = pick_best_hit(hits, "Alice, Golden Queen", "Grand Archive TCG")
    assert chosen.product_id == 2


def test_pick_best_hit_filters_product_line():
    hits = [
        _hit(1, "Alice, Golden Queen", line="Shadowverse: Evolve", score=5.0),
        _hit(2, "Alice, Golden Queen", line="Grand Archive TCG", score=3.0),
    ]
    chosen = pick_best_hit(hits, "Alice, Golden Queen", "Grand Archive TCG")
    assert chosen.product_id == 2


def test_pick_best_hit_returns_none_when_no_match():
    assert pick_best_hit([], "X", None) is None


def test_pick_best_hit_falls_back_to_suffix_when_base_unavailable():
    # Only special versions exist — shouldn't return None
    hits = [
        _hit(1, "Alice, Golden Queen (CSR)", score=2.0),
        _hit(2, "Alice, Golden Queen (CUR)", score=1.5),
    ]
    chosen = pick_best_hit(hits, "Alice, Golden Queen", "Grand Archive TCG")
    assert chosen is not None
    assert chosen.product_id == 1  # higher score


def _listing(price, printing="Normal", condition="Near Mint"):
    return Listing(644912, price, 0.0, 1, condition, printing, "English", None, None, None)


def _sale(price, variant="Normal", condition="Near Mint"):
    return Sale(644912, "2026-04-20", price, 0.0, 1, condition, variant, "English")


def test_build_variants_separates_normal_and_foil():
    listings = [
        _listing(2.54, "Normal"),
        _listing(3.32, "Normal"),
        _listing(35.89, "Foil"),
        _listing(39.70, "Foil"),
    ]
    variants = build_variants(listings, [])

    assert len(variants) == 2
    normal = next(v for v in variants if v.printing == "Normal")
    foil = next(v for v in variants if v.printing == "Foil")
    assert normal.listing_min == 2.54
    assert normal.listing_count == 2
    assert foil.listing_min == 35.89
    assert foil.listing_count == 2


def test_build_variants_separates_conditions():
    listings = [
        _listing(10.0, "Normal", "Near Mint"),
        _listing(8.0, "Normal", "Lightly Played"),
    ]
    variants = build_variants(listings, [])
    assert len(variants) == 2
    nm = next(v for v in variants if v.condition == "Near Mint")
    lp = next(v for v in variants if v.condition == "Lightly Played")
    assert nm.listing_min == 10.0
    assert lp.listing_min == 8.0


def test_build_variants_ignores_zero_prices():
    listings = [_listing(0.0), _listing(5.0)]
    variants = build_variants(listings, [])
    assert len(variants) == 1
    assert variants[0].listing_count == 1
    assert variants[0].listing_min == 5.0


def test_build_variants_merges_listings_and_sales_by_variant_condition():
    listings = [_listing(5.0, "Normal", "Near Mint")]
    sales = [_sale(4.5, "Normal", "Near Mint"), _sale(4.0, "Foil", "Near Mint")]
    variants = build_variants(listings, sales)

    assert len(variants) == 2
    normal_nm = next(v for v in variants if v.printing == "Normal")
    foil_nm = next(v for v in variants if v.printing == "Foil")
    assert normal_nm.listing_min == 5.0
    assert normal_nm.sale_avg == 4.5
    assert foil_nm.listing_min is None  # no listings
    assert foil_nm.sale_avg == 4.0


def test_build_variants_orders_normal_before_foil():
    listings = [_listing(30.0, "Foil"), _listing(3.0, "Normal")]
    variants = build_variants(listings, [])
    assert [v.printing for v in variants] == ["Normal", "Foil"]


def test_build_variants_most_recent_sale_uses_orderdate():
    sales = [
        Sale(1, "2026-04-20T10:00:00", 5.0, 0, 1, "Near Mint", "Normal", "English"),
        Sale(1, "2026-04-22T10:00:00", 7.0, 0, 1, "Near Mint", "Normal", "English"),
        Sale(1, "2026-04-21T10:00:00", 6.0, 0, 1, "Near Mint", "Normal", "English"),
    ]
    variants = build_variants([], sales)
    assert len(variants) == 1
    assert variants[0].most_recent_sale == 7.0  # latest orderDate
    assert variants[0].sale_avg == 6.0


def test_build_variants_most_recent_sale_per_variant():
    sales = [
        Sale(1, "2026-04-22", 3.0, 0, 1, "Near Mint", "Normal", "English"),
        Sale(1, "2026-04-20", 35.0, 0, 1, "Near Mint", "Foil", "English"),
    ]
    variants = build_variants([], sales)
    normal = next(v for v in variants if v.printing == "Normal")
    foil = next(v for v in variants if v.printing == "Foil")
    assert normal.most_recent_sale == 3.0
    assert foil.most_recent_sale == 35.0

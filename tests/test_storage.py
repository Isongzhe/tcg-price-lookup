from datetime import datetime, timezone
from pathlib import Path

import pytest

# Storage features depend on the `history` optional extras (polars + duckdb).
# When the extras are not installed, skip the whole module rather than erroring.
pl = pytest.importorskip("polars")
pytest.importorskip("duckdb")

from tcg.models import Listing, MarketPrice, Sale
from tcg.storage import append_snapshot, query, snapshot_to_rows


def test_snapshot_to_rows_tags_source():
    ts = datetime(2026, 4, 22, tzinfo=timezone.utc)
    rows = snapshot_to_rows(
        product_id=644912,
        card_name="Alice, Golden Queen",
        sales=[Sale(644912, "2026-04-20", 10.0, 1.0, 1, "NM", None, "EN")],
        listings=[Listing(644912, 9.5, 0.0, 2, "NM", "Normal", "EN", "Seller", None, None)],
        market_prices=[MarketPrice(1000, 644912, 9.75, 8.0, 0.0, 9.0)],
        fetched_at=ts,
    )
    assert len(rows) == 3
    sources = sorted(r["source"] for r in rows)
    assert sources == ["listing", "market", "sale"]


def test_append_snapshot_roundtrip(tmp_path: Path):
    ts = datetime(2026, 4, 22, tzinfo=timezone.utc)
    rows = snapshot_to_rows(
        product_id=644912,
        card_name="Alice, Golden Queen",
        sales=[Sale(644912, "2026-04-20", 10.0, 1.0, 1, "NM", None, "EN")],
        listings=[],
        market_prices=[],
        fetched_at=ts,
    )
    path = tmp_path / "snaps.parquet"
    append_snapshot(rows, path=path)

    df = pl.read_parquet(path)
    assert df.height == 1
    assert df["price"][0] == 10.0
    assert df["card_name"][0] == "Alice, Golden Queen"


def test_append_snapshot_appends(tmp_path: Path):
    ts = datetime(2026, 4, 22, tzinfo=timezone.utc)
    path = tmp_path / "snaps.parquet"

    for price in (10.0, 11.0):
        rows = snapshot_to_rows(
            product_id=644912,
            card_name="X",
            sales=[Sale(644912, "2026-04-20", price, 0, 1, None, None, None)],
            listings=[],
            market_prices=[],
            fetched_at=ts,
        )
        append_snapshot(rows, path=path)

    df = pl.read_parquet(path)
    assert df.height == 2


def test_duckdb_query(tmp_path: Path):
    ts = datetime(2026, 4, 22, tzinfo=timezone.utc)
    rows = snapshot_to_rows(
        product_id=644912,
        card_name="X",
        sales=[
            Sale(644912, "2026-04-20", 10.0, 0, 1, None, None, None),
            Sale(644912, "2026-04-20", 20.0, 0, 1, None, None, None),
        ],
        listings=[],
        market_prices=[],
        fetched_at=ts,
    )
    path = tmp_path / "snaps.parquet"
    append_snapshot(rows, path=path)

    df = query("SELECT AVG(price) AS avg_p FROM snapshots WHERE source = 'sale'", path=path)
    assert df["avg_p"][0] == 15.0

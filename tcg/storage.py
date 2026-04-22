from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import duckdb
import polars as pl

from tcg.models import Listing, MarketPrice, Sale

SNAPSHOT_PATH = Path("data/snapshots.parquet")

_SCHEMA = {
    "fetched_at": pl.Datetime(time_unit="us", time_zone="UTC"),
    "product_id": pl.Int64,
    "card_name": pl.Utf8,
    "source": pl.Utf8,
    "price": pl.Float64,
    "shipping_price": pl.Float64,
    "quantity": pl.Int64,
    "condition": pl.Utf8,
    "printing": pl.Utf8,
    "language": pl.Utf8,
    "variant": pl.Utf8,
    "seller_name": pl.Utf8,
    "sku_id": pl.Int64,
    "order_date": pl.Utf8,
    "market_price": pl.Float64,
    "low_price": pl.Float64,
}


def _row_base(product_id: int, card_name: str, fetched_at: datetime) -> dict:
    return {
        "fetched_at": fetched_at,
        "product_id": product_id,
        "card_name": card_name,
        "source": None,
        "price": None,
        "shipping_price": None,
        "quantity": None,
        "condition": None,
        "printing": None,
        "language": None,
        "variant": None,
        "seller_name": None,
        "sku_id": None,
        "order_date": None,
        "market_price": None,
        "low_price": None,
    }


def snapshot_to_rows(
    product_id: int,
    card_name: str,
    sales: Iterable[Sale],
    listings: Iterable[Listing],
    market_prices: Iterable[MarketPrice],
    fetched_at: datetime | None = None,
) -> list[dict]:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    rows: list[dict] = []

    for s in sales:
        row = _row_base(product_id, card_name, fetched_at)
        row.update(
            source="sale",
            price=s.purchase_price,
            shipping_price=s.shipping_price,
            quantity=s.quantity,
            condition=s.condition,
            language=s.language,
            variant=s.variant,
            order_date=s.order_date,
        )
        rows.append(row)

    for l in listings:
        row = _row_base(product_id, card_name, fetched_at)
        row.update(
            source="listing",
            price=l.price,
            shipping_price=l.shipping_price,
            quantity=l.quantity,
            condition=l.condition,
            printing=l.printing,
            language=l.language,
            seller_name=l.seller_name,
        )
        rows.append(row)

    for m in market_prices:
        row = _row_base(product_id, card_name, fetched_at)
        row.update(
            source="market",
            price=m.market_price,
            sku_id=m.sku_id,
            market_price=m.market_price,
            low_price=m.lowest_price,
        )
        rows.append(row)

    return rows


def append_snapshot(rows: list[dict], path: Path = SNAPSHOT_PATH) -> Path:
    if not rows:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    new_df = pl.DataFrame(rows, schema=_SCHEMA)
    if path.exists():
        existing = pl.read_parquet(path)
        combined = pl.concat([existing, new_df], how="vertical_relaxed")
    else:
        combined = new_df
    combined.write_parquet(path)
    return path


def query(sql: str, path: Path = SNAPSHOT_PATH) -> pl.DataFrame:
    """Run DuckDB SQL over the snapshot parquet. A view named `snapshots` is
    available if the file exists. Returns a Polars DataFrame."""
    con = duckdb.connect()
    if path.exists():
        con.execute(
            f"CREATE VIEW snapshots AS SELECT * FROM read_parquet('{path}')"
        )
    rel = con.execute(sql)
    columns = [d[0] for d in rel.description]
    data = rel.fetchall()
    if not data:
        return pl.DataFrame({c: [] for c in columns})
    rows = [dict(zip(columns, row)) for row in data]
    return pl.DataFrame(rows)

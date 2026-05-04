"""Re-query TCGplayer's productLineName aggregation and print an updated
PRODUCT_LINES literal. Paste the output back into tcg/product_lines.py.

Usage:
    uv run python -m scripts.refresh_product_lines
"""
from __future__ import annotations

from tcg.client import TCGplayerClient


def main() -> int:
    client = TCGplayerClient()
    data = client._request(
        "POST",
        "https://mp-search-api.tcgplayer.com/v1/search/request",
        params={"mpfev": "5061"},
        json={
            "algorithm": "revenue_exp_v2_1",
            "from": 0,
            "size": 0,
            "filters": {"term": {}, "range": {}, "match": {}},
            "aggregations": ["productLineName"],
            "context": {"cart": {}, "shippingCountry": "US"},
            "settings": {"useFuzzySearch": False, "didYouMean": {}},
        },
    )
    aggs = data.get("aggregations") or {}
    buckets = aggs.get("productLineName") or []
    print("PRODUCT_LINES: dict[str, str] = {")
    for b in buckets:
        slug = b.get("urlValue")
        name = b.get("value")
        if slug and name:
            print(f"    {name!r}: {slug!r},")
    print("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

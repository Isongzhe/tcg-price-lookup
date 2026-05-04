"""Connectivity smoke test.

Maintainer / dev tool. Instantiates a client and fetches recent sales for
a single hardcoded product id, used as a quick check that the environment
is set up correctly and the upstream endpoint is reachable. Not intended
as a user-facing CLI — for real use, see ``scripts/fetch_deck.py``.

Run::

    uv run python -m scripts.smoke_test
"""

from __future__ import annotations

import json

from tcg import TCGplayerClient

# A stable Grand Archive TCG product id, used as a connectivity probe.
SAMPLE_PRODUCT_ID = 665194


def main() -> int:
    client = TCGplayerClient()

    print(f"Fetching recent sales for product id {SAMPLE_PRODUCT_ID} ...")
    sales = client.latest_sales(SAMPLE_PRODUCT_ID, limit=5)

    if not sales:
        print("No sales returned. The product may be inactive or the endpoint unavailable.")
        return 1

    print(f"Received {len(sales)} sale records:\n")
    for sale in sales:
        record = {
            "order_date": sale.order_date,
            "variant": sale.variant,
            "condition": sale.condition,
            "purchase_price": sale.purchase_price,
            "quantity": sale.quantity,
        }
        print(json.dumps(record, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

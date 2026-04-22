"""CLI: 搜尋卡片 → 抓價格資料 → 存 Parquet → 印摘要。

用法:
    python -m scripts.fetch "alice golden"
    python -m scripts.fetch "alice golden" --product-line "Grand Archive TCG"
    python -m scripts.fetch "alice golden" --auto   # 自動選第一個
"""

from __future__ import annotations

import argparse
import sys

from tcg.client import TCGplayerClient
from tcg.models import AutocompleteHit
from tcg.storage import append_snapshot, snapshot_to_rows


def pick_hit(hits: list[AutocompleteHit], auto: bool) -> AutocompleteHit | None:
    if not hits:
        return None
    if auto or len(hits) == 1:
        return hits[0]

    print("\n搜尋結果：")
    for i, h in enumerate(hits):
        print(
            f"  [{i}] {h.product_name}  "
            f"({h.product_line_name} / {h.set_name})  id={h.product_id}"
        )
    while True:
        raw = input("\n選擇 index (Enter=0, q=取消): ").strip()
        if raw in ("q", "Q"):
            return None
        if raw == "":
            return hits[0]
        try:
            idx = int(raw)
            if 0 <= idx < len(hits):
                return hits[idx]
        except ValueError:
            pass
        print("無效，請重試。")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch TCGplayer price snapshot")
    parser.add_argument("query", help="卡名（可含空格）")
    parser.add_argument(
        "--product-line",
        default=None,
        help="過濾卡池，例如 'Grand Archive TCG'",
    )
    parser.add_argument("--auto", action="store_true", help="自動選第一個候選")
    parser.add_argument("--listings", type=int, default=50)
    parser.add_argument("--sales", type=int, default=25)
    args = parser.parse_args(argv)

    client = TCGplayerClient()

    print(f"[*] 搜尋: {args.query!r}")
    hits = client.autocomplete(args.query, product_line=args.product_line)
    if not hits:
        print("[-] 沒有符合的卡片。")
        return 1

    chosen = pick_hit(hits, args.auto)
    if chosen is None:
        print("[*] 已取消。")
        return 0

    print(f"[+] 選擇: {chosen.product_name} (id={chosen.product_id})")

    print("[*] 抓 latest_sales...")
    sales = client.latest_sales(chosen.product_id, limit=args.sales)
    print(f"    取得 {len(sales)} 筆成交紀錄")

    print("[*] 抓 listings...")
    listings = client.listings(chosen.product_id, limit=args.listings)
    print(f"    取得 {len(listings)} 筆在售列表")

    market = []

    rows = snapshot_to_rows(
        product_id=chosen.product_id,
        card_name=chosen.product_name,
        sales=sales,
        listings=listings,
        market_prices=market,
    )
    path = append_snapshot(rows)
    print(f"[+] 已寫入 {path}  ({len(rows)} rows)")

    if sales:
        prices = [s.purchase_price for s in sales if s.purchase_price > 0]
        if prices:
            print(
                f"\n最近成交價: min=${min(prices):.2f}  "
                f"avg=${sum(prices) / len(prices):.2f}  "
                f"max=${max(prices):.2f}"
            )
    if listings:
        prices = [l.price for l in listings if l.price > 0]
        if prices:
            print(
                f"在售最低價: ${min(prices):.2f}  "
                f"(共 {len(listings)} 筆 listings)"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())

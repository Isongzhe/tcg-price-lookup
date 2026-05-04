# tcg-price-lookup

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](./LICENSE)

TCGplayer batch price lookup. Paste a deck → get a tab-separated price sheet → drop it into Google Sheets.

---

## What it does

You have a card list. You want to know what each card costs on TCGplayer right now. Feed the deck file in, get a TSV out — the TSV is printed to your terminal and automatically copied to your clipboard. Paste it into the included Google Sheets template for a styled, image-rich table. No API key needed.

---

## Quick start

Requires [`uv`](https://docs.astral.sh/uv/getting-started/installation/) (a single-binary Python package manager).

```bash
git clone https://github.com/Isongzhe/tcg-price-lookup.git
cd tcg-price-lookup
uv sync
uv run python -m scripts.fetch_deck decks/sample_deck.txt
```

TSV is printed to your terminal AND copied to your clipboard. Paste it into a Google Sheet.

---

## Sample output

Tab-separated, one row per `card × printing × condition × reprint set`. Key columns at a glance:

**All prices are per-card** (not multiplied by `qty`). For a deck total, multiply `qty × market_price` in your spreadsheet, or sum the column.

| section | qty | card_name | set_name | printing | condition | market_price |
|---|---|---|---|---|---|---|
| Material Deck | 1 | Alice, Golden Queen | Distorted Reflections | Normal | Near Mint | 3.95 |
| Material Deck | 1 | Alice, Golden Queen | Distorted Reflections | Foil | Near Mint | 40.99 |
| Material Deck | 1 | Lost Providence | Radiant Origins | Normal | Near Mint | 43.07 |
| Material Deck | 1 | Lost Providence | Phantom Monarchs | Normal | Near Mint | 143.58 |
| Main Deck | 3 | Golden Checkmate | Radiant Origins | Normal | Near Mint | 24.63 |

Reprints (e.g. `Lost Providence`) appear once per set; the cheapest version is usually the most recent. The full 23-column TSV (image URL, sku id, listing range, recent sale stats, etc.) is in [`prices/sample_deck.tsv`](./prices/sample_deck.tsv); each column's meaning is documented in [`scripts/README.md`](./scripts/README.md).

The CLI writes this output to **three places at once**: stdout, the system clipboard, and (optionally) a file via `--output PATH` or the `output_path` config key.

---

## How it works

The CLI walks each card in your deck through five TCGplayer endpoints
(autocomplete → search → product details → recent sales → live
listings), aggregates Normal/Foil/condition variants, and emits one
TSV row per `card × printing × condition × reprint set`. No TCGplayer
API key required — see [`DISCLAIMER.md`](./DISCLAIMER.md) for how this
works and what the limits are.

Endpoints are catalogued in [`tcg/endpoints.py`](./tcg/endpoints.py);
run `uv run python -m scripts.fetch_deck --show-endpoints` to inspect
them.

---

## Defaults you might want to change

The CLI works out of the box — you only need to set these if the defaults don't fit. Run `cat tcg.toml.example` to see every setting and its current default in one place.

| Setting | How to change |
|---|---|
| Product line filter | `product_line` in `tcg.toml` or `--product-line` flag |
| Auto-copy to clipboard | `copy_to_clipboard` in `tcg.toml` or `--no-copy` flag |
| Save TSV to a file | `output_path` in `tcg.toml` or `--output PATH` flag |
| Printings shown | `printings` in `tcg.toml` or `--printings` flag |
| Conditions shown | `conditions` in `tcg.toml` or `--conditions` flag |
| Sleep between cards | `request_interval` in `tcg.toml` |

---

## Google Sheets template

The repo includes a Google Sheets template with a one-click Apps Script
formatter. Run it after pasting your TSV and it transforms the raw
data into a styled table: card image thumbnails in column A, a dark
header bar, zebra banding, currency formatting on `market_price`, and
metadata columns hidden by default (re-expand with the `[+]` toggle).

**[Copy the template to your Drive →](https://docs.google.com/spreadsheets/d/1u7r0ND0wkUTGl7k8jDayK74l2U4KIlu_WLfJCR0dgcg/copy)**

Setup instructions and source code in [`sheets/README.md`](./sheets/README.md).

---

## Configure defaults

Optional. Default behaviour works without setup. To set personal
defaults once instead of typing flags every run:

    cp tcg.toml.example tcg.toml
    # then edit tcg.toml — every key is documented inline

For environment-variable overrides and full precedence rules, see
[`scripts/README.md`](./scripts/README.md).

---

## Use as a library

The `tcg` package is a standalone HTTP client you can import into any Python project — a duckdb pipeline, a Discord bot, a FastAPI service:

```python
from tcg import TCGplayerClient

client = TCGplayerClient()
results = client.search_products("Alice, Golden Queen", product_line="Grand Archive TCG")
for r in results:
    print(r.product_id, r.set_name, r.market_price, r.release_date)
```

Full library API documented in [`tcg/README.md`](./tcg/README.md).

---

## Stability

TSV columns and dataclass fields are stable within MAJOR: new columns and fields will be appended only. Renames, reorders, removals, and semantic changes require a MAJOR version bump and are documented in [CHANGELOG.md](./CHANGELOG.md).

---

## License

Licensed under the **Apache License, Version 2.0** — see [`LICENSE`](./LICENSE) and [`NOTICE`](./NOTICE).

---

## Disclaimer

Not affiliated with TCGplayer, Inc. For commercial use of TCGplayer data, apply for the [official TCGplayer API](https://docs.tcgplayer.com/). See [DISCLAIMER.md](./DISCLAIMER.md) for full terms.

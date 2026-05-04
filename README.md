# tcg-price-lookup

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](./LICENSE)
[![Tests](https://img.shields.io/badge/tests-177%20passing-brightgreen.svg)](./tests)

TCGplayer batch price lookup. Paste a deck → get a tab-separated price sheet → drop it into Google Sheets.

---

## What it does

You have a card list. You want to know what each card costs on TCGplayer right now. Feed the deck file in, get a TSV out — the TSV is printed to your terminal and automatically copied to your clipboard. Paste it into the included Google Sheets template for a styled, image-rich table. No API key needed.

---

## Quick start

```bash
git clone https://github.com/Isongzhe/tcg-price-lookup.git
cd tcg-price-lookup
uv sync
uv run python -m scripts.fetch_deck decks/sample_deck.txt
```

TSV is printed to your terminal AND copied to your clipboard. Paste it into a Google Sheet.

---

## Sample output

```
section         qty  card_name              matched_name           set_name              set_code  number  rarity      released    product_id  sku_id   printing  condition  market_price  mp_sample  most_recent_sale  sale_avg  sale_count  listing_min  listing_avg  listing_count  image_url  missing
Material Deck   1    Alice, Golden Queen    Alice, Golden Queen    Distorted Reflections  DTR1E     004     Super Rare              644912      8847720  Normal    Near Mint  3.95          25         4.99              4.53      5           2.54         3.95         6              https://…
Material Deck   1    Alice, Golden Queen    Alice, Golden Queen    Distorted Reflections  DTR1E     004     Super Rare              644912      8847725  Foil      Near Mint  40.99         5                                        0           39.70        40.17        4              https://…
Material Deck   1    Lost Providence        Lost Providence        Radiant Origins        RDO       409     Ultra Rare  2026-04-03  688306      9230342  Normal    Near Mint  43.07         25         42.50             42.76     5           42.50        49.05        19             https://…
Material Deck   1    Lost Providence        Lost Providence        Phantom Monarchs       PTM       013     Ultra Rare  2025-12-05  665290      9028922  Normal    Near Mint  143.58        25         142.86            137.31    5           122.04       142.72       6              https://…
Main Deck       3    Golden Checkmate       Golden Checkmate       Radiant Origins        RDO       85      Ultra Rare              688297      9230292  Normal    Near Mint  24.63         25         20.00             24.24     5           21.67        26.73        20             https://…
Sideboard       2    Surging Obstruction    Surging Obstruction    Radiant Origins        RDO       247     Uncommon                688033      9227901  Normal    Near Mint  0.68          5          0.64              0.64      4           0.48         0.70         20             https://…
```

One row per card × printing × condition × reprint set. The full 23-column schema is documented in [`scripts/README.md`](./scripts/README.md).

---

## Defaults you might want to change

| Setting | Default | How to change |
|---|---|---|
| Product line filter | (none — searches all TCGs) | `product_line = "Grand Archive TCG"` in config or `--product-line` flag |
| Auto-copy to clipboard | on | `copy_to_clipboard = false` in config or `--no-copy` flag |
| Save TSV to a file | (none — only stdout/clipboard) | `output_path = "prices/last_run.tsv"` in config or `--output PATH` flag |
| Printings shown | `Normal,Foil` | `--printings all` for every printing, or comma-separated list |
| Conditions shown | `Near Mint` | `--conditions all`, or comma-separated list |
| Save snapshot to parquet | off | `--parquet` flag (requires `[history]` extras) |

---

## Configuration

Set defaults once and every run picks them up:

```toml
# ~/.config/tcg/config.toml — set once, applies to every run
product_line = "Grand Archive TCG"
output_path = "prices/last_run.tsv"
```

All settings are also available as environment variables:

| Env var | Config key |
|---|---|
| `TCG_PRODUCT_LINE` | `product_line` |
| `TCG_PRINTINGS` | `printings` |
| `TCG_CONDITIONS` | `conditions` |
| `TCG_COPY_TO_CLIPBOARD` | `copy_to_clipboard` |
| `TCG_WRITE_PARQUET` | `write_parquet` |
| `TCG_OUTPUT_PATH` | `output_path` |

Precedence: CLI flags > env vars > TOML > built-in defaults. See [`scripts/README.md`](./scripts/README.md) for the full lookup order and CLI flag reference.

---

## Google Sheets template

The repo includes a Google Sheets template with a one-click Apps Script formatter. Run it after pasting your TSV and it transforms the raw data into a styled table: card image thumbnails in column A, a dark header bar, zebra banding, currency formatting on `market_price`, and metadata columns hidden by default (they can be re-expanded with the `[+]` toggle).

Full instructions and a copy-template link are in [`sheets/README.md`](./sheets/README.md).

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

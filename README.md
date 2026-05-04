# tcg-price-lookup

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](./LICENSE)
[![Tests](https://img.shields.io/badge/tests-86%20passing-brightgreen.svg)](./tests)

TCGplayer price-lookup library and CLI. Resolves card names to TCGplayer
products, fetches per-variant Market Price, recent sales, and active
listings. Returns typed dataclasses — no storage opinions, no I/O side
effects. A CLI consumer (`scripts/fetch_deck.py`) emits TSV to stdout and
auto-copies to clipboard.

---

## Install

```bash
uv add tcg-price-lookup
# or
pip install tcg-price-lookup
```

Optional extras for local parquet snapshots (demonstration only — see
[Storage](#storage--persistence)):

```bash
uv add "tcg-price-lookup[history]"
```

---

## Use as a Library

The library is the primary integration surface. Import from `tcg`:

```python
from tcg import TCGplayerClient, PRODUCT_LINES, to_slug

client = TCGplayerClient()

# Search for products matching a name, filtered by product line
results = client.search_products("Alice, Golden Queen", product_line="Grand Archive TCG")
for r in results:
    print(r.product_id, r.set_name, r.market_price, r.release_date)
```

Fetch full details and sales for a known product ID:

```python
from tcg import TCGplayerClient, ProductDetails

client = TCGplayerClient()

# Detailed pricing per SKU (printing × condition)
details: ProductDetails = client.product_details(12345)
for sku in details.skus:
    print(sku.printing, sku.condition, sku.market_price)

# Recent sales
sales = client.latest_sales(12345)
for s in sales:
    print(s.price, s.order_date)
```

All exported types are dataclasses. The fields and TSV column order are
stable within a MAJOR version — see [Stability](#stability).

### Full public API

Everything in `tcg.__all__` is a stable public contract:

| Name | Kind | Description |
|---|---|---|
| `TCGplayerClient` | class | HTTP client |
| `TCGplayerError` | exception | All client errors |
| `ProductDetails` | dataclass | Full product + SKU data |
| `ProductSearchResult` | dataclass | One result from `search_products` |
| `AutocompleteHit` | dataclass | Raw autocomplete match |
| `Sku` | dataclass | Per-printing/condition SKU |
| `MarketPrice` | dataclass | Market price for a SKU |
| `Sale` | dataclass | One recent sale record |
| `Listing` | dataclass | One active listing |
| `PRODUCT_LINES` | dict | Display name → URL slug mapping (68 entries) |
| `to_slug` | function | Convert a product-line display name to its URL slug |

---

## Use as a CLI

```bash
uv run python -m scripts.fetch_deck deck.txt
```

Deck file format — one card per line, optional `# Section` headers:

```
# Material Deck
1 Alice, Golden Queen

# Main Deck
4 Lorraine, Wandering Warrior
3 Diana, Keeper of Tradition
```

TSV is written to stdout **and** automatically copied to the clipboard on
macOS, Linux (wl-copy/xclip/xsel), and Windows (clip). Use `--no-copy` to
suppress.

List all 68 known product lines:

```bash
uv run python -m scripts.fetch_deck --list-product-lines
```

### CLI flags

| Flag | Default | Description |
|---|---|---|
| `source` | (required) | Decklist file path, or `-` for stdin |
| `--product-line` | config/env | TCGplayer product line name |
| `--list-product-lines` | — | Print all known product lines and exit |
| `--printings` | `Normal,Foil` | Comma-separated printing names |
| `--conditions` | `Near Mint` | Comma-separated condition tiers |
| `--parquet` | off (opt-in) | Append results to `data/snapshots.parquet` |
| `--no-copy` | — | Suppress clipboard write |
| `--config PATH` | — | Path to a TOML config file |

---

## Configuration

Create `~/.config/tcg/config.toml` for user-wide defaults, or `./tcg.toml`
for project-local settings:

```toml
# ~/.config/tcg/config.toml  (or ./tcg.toml for project-local)
product_line = "Grand Archive TCG"
printings = ["Normal", "Foil"]
conditions = ["Near Mint"]
copy_to_clipboard = true
write_parquet = false
```

All keys can also be set via environment variables:

| Env var | Config key |
|---|---|
| `TCG_PRODUCT_LINE` | `product_line` |
| `TCG_PRINTINGS` | `printings` |
| `TCG_CONDITIONS` | `conditions` |
| `TCG_COPY_TO_CLIPBOARD` | `copy_to_clipboard` |
| `TCG_WRITE_PARQUET` | `write_parquet` |

**Precedence** (highest wins): CLI flags > env vars > TOML config > built-in defaults.

---

## Product Lines

The `PRODUCT_LINES` dict contains 68 known TCGplayer product lines
(snapshot 2026-05-04). To see them:

```bash
uv run python -m scripts.fetch_deck --list-product-lines
```

To refresh the list against the live TCGplayer API:

```bash
uv run python scripts/refresh_product_lines.py
```

Paste the printed literal into `tcg/product_lines.py`. Do not edit that
file by hand.

---

## Output Format

One row per `(card × printing × condition × reprint set)` tuple, TSV,
twenty-three columns:

```
section  qty  card_name  matched_name  set_name  set_code  number  rarity
released  product_id  sku_id  printing  condition
market_price  mp_sample  most_recent_sale  sale_avg  sale_count
listing_min  listing_avg  listing_count
image_url  missing
```

TSV column order is stable within a MAJOR version — see [Stability](#stability).

Wrap `image_url` values with `=IMAGE(...)` in Google Sheets to render
card thumbnails. A ready-to-use template with a one-click formatter lives
in [`sheets/`](./sheets/).

---

## Stability

The TSV column order (`print_tsv` in `scripts/fetch_deck.py`) and exported
dataclass fields (`tcg/models.py`) are a **stable contract** within the 1.x
line:

- New columns and fields will be **appended only**.
- Renames, reorders, removals, and semantic changes require a **MAJOR version bump**.
- Every breaking change is documented in [CHANGELOG.md](./CHANGELOG.md) with the new MAJOR version.

---

## Storage / Persistence

`tcg.storage` (parquet + DuckDB) is a **demonstration** of one persistence
approach. It is opt-in (`--parquet` flag or `write_parquet = true` in
config) and lives in the `[history]` extras.

Integrators building their own pipelines (duckdb, postgres, sqlite, etc.)
should consume the library's dataclasses directly — the library itself has
no storage dependencies.

---

## Testing

```bash
uv run pytest
```

All 86 tests are offline (HTTP behavior exercised through a fake session;
recorded API responses stored under `tests/fixtures/`). Storage tests are
skipped automatically when the `[history]` extras are not installed.

---

## License

Licensed under the **Apache License, Version 2.0** — see [`LICENSE`](./LICENSE)
and [`NOTICE`](./NOTICE).

## Disclaimer

**Please read [`DISCLAIMER.md`](./DISCLAIMER.md) before using this
software.** This project is not affiliated with, endorsed by, or sponsored
by TCGplayer, Inc. "TCGplayer" and all product-line names are trademarks of
their respective owners, used nominatively. For commercial use of TCGplayer
data, apply for access to the
[official TCGplayer API](https://docs.tcgplayer.com/).

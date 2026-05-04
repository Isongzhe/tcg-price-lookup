# `scripts/` — CLI entry points and maintainer tools

Thin wrappers that assemble the core logic from `tcg/` into
user-invokable commands. All presentation and argument parsing lives here;
the reusable business logic lives in `tcg/`.

## Files

| File | Purpose | Notes |
|---|---|---|
| `fetch_deck.py` | Batch decklist price lookup | Primary workflow |
| `refresh_product_lines.py` | Re-query TCGplayer product-line catalog | Maintainer tool |
| `smoke_test.py` | One-shot connectivity check | Maintainer tool |
| `_clipboard.py` | Cross-platform clipboard write | Private; CLI-internal |
| `_config.py` | TOML + env config loader | Private; CLI-internal |

---

## `fetch_deck.py`

### Basic usage

```bash
# From a file
uv run python -m scripts.fetch_deck decks/sample_deck.txt

# From stdin
pbpaste | uv run python -m scripts.fetch_deck -

# Specify product line, suppress clipboard copy
uv run python -m scripts.fetch_deck deck.txt \
    --product-line "Grand Archive TCG" \
    --no-copy
```

### CLI flags

| Flag | Default | Description |
|---|---|---|
| `source` | (required) | Decklist file path, or `-` for stdin |
| `--product-line TEXT` | config/env | Filter to this TCGplayer product line |
| `--list-product-lines` | — | Print all 68 known product lines as `display<TAB>slug`, then exit |
| `--list-endpoints` | — | Print a table of all TCGplayer endpoints in the catalog, then exit |
| `--printings TEXT` | `Normal,Foil` | Comma-separated printing names. Use `all` for everything |
| `--conditions TEXT` | `Near Mint` | Comma-separated condition tiers. Use `all` for everything |
| `--parquet` | off (opt-in) | Append results to `data/snapshots.parquet` (requires `[history]` extras) |
| `--no-copy` | — | Suppress auto-copy of TSV to clipboard for this run |
| `--output PATH` | config/env | Write TSV to this file path in addition to stdout/clipboard |
| `--config PATH` | — | Path to a TOML config file (overrides default search locations) |

### Data flow

```
decklist text
    │
    │ tcg.deck.parse_decklist()
    ▼
list[DeckEntry]
    │
    │ for each entry (with a 0.8s pause between cards):
    │   client.autocomplete()             locate productId
    │     └─ if ambiguous (reprint aggregate):
    │        client.search_products()     enumerate every set → N products
    │   for each resolved product:
    │     client.product_details()        fetch metadata and SKU list
    │     client.latest_sales()           fetch recent sales
    │     client.listings()               fetch active listings
    │     client.market_price([sku])      fetch per-variant market prices
    ▼
list[DeckRow]  (one DeckRow per resolved product; reprints produce multiple)
    │
    │ build_variants():
    │   group listings/sales by (printing, condition)
    │   merge per-SKU market prices
    ▼
    ├──> stdout (TSV, also auto-copied to the system clipboard by default)
    ├──> stderr (Rich progress bar + missing-card panel)
    └──> data/snapshots.parquet (only when --parquet is set or write_parquet=true in config)
```

### Key functions

| Function | Responsibility |
|---|---|
| `pick_best_hit()` | Selects the best autocomplete match for a given card name |
| `build_variants()` | Merges listings, sales, and per-SKU market prices into a per-variant summary |
| `enrich()` | Orchestrates the per-card fetch pipeline |
| `print_tsv()` | Formats results as tab-separated output |
| `print_summary()` | Writes reference totals and missing-card notes to stderr |

### Match selection

`pick_best_hit()` applies this precedence when autocomplete returns multiple candidates:

1. If `--product-line` is set, candidates from other product lines are discarded.
2. Candidates whose base name (without parenthetical suffixes) exactly matches the input are preferred.
3. Within that set, candidates without parenthetical suffixes (e.g. no `(CSR)` or `(CUR)`) are preferred.
4. Ties are broken by the autocomplete score.

### Output format

Twenty-three columns per row, one row per `(card × printing × condition × reprint set)` tuple:

```
section          qty              card_name         matched_name
set_name         set_code         number            rarity
released
product_id       sku_id
printing         condition
market_price     mp_sample        most_recent_sale  sale_avg
sale_count       listing_min      listing_avg       listing_count
image_url
missing
```

Column notes:

- **`section`** is the `# Section` header from the decklist (e.g. `Material Deck`).
- **`qty`** is the quantity from the decklist.
- **`card_name`** is the name as typed in the decklist.
- **`matched_name`** is the name returned by TCGplayer autocomplete.
- **`set_code`** is TCGplayer's short set identifier (e.g. `DTR1E`, `PTM`).
- **`number`** is the collector number within the set (e.g. `004`, `013`). Useful when distinguishing reprints that share a name but not a number.
- **`released`** is the set's release date (ISO `YYYY-MM-DD`). Populated on reprint-expanded rows; empty for cards resolved through autocomplete only.
- **`market_price`** is per-SKU, aggregated by TCGplayer over roughly the last 30 days of sales. Normal and Foil rows carry independent values. Not real-time.
- **`mp_sample`** is how many sales underlie `market_price`. Values ≥ 15 indicate a reliable price; values ≤ 3 mean the price is near-singleton — treat as indicative only.
- **`most_recent_sale`** has no time bound. For illiquid cards it may be weeks or months old; always read it alongside `sale_count`.
- **`sale_avg` / `sale_count`** cover the most recent 25 sales (hardcoded). The time span is driven by liquidity, not a date filter.
- **`listing_*`** is a live snapshot of active listings at run time, not historical. Capped at 20 listings (hardcoded).
- **`image_url`** is a 200 px CDN URL. Wrap with `=IMAGE()` in Google Sheets to render thumbnails.
- **`missing`** contains a reason string when the card could not be resolved or an API call failed; it is empty otherwise.

#### Data freshness

| Column | Timeframe |
|---|---|
| `market_price` / `mp_sample` | ~30-day rolling aggregate |
| `most_recent_sale` | Single newest sale (no age limit) |
| `sale_avg` / `sale_count` | Up to 25 most recent sales |
| `listing_*` | Live snapshot at run time |

The CLI never caches — every invocation re-fetches. Cross-run history is opt-in via the `[history]` extras.

### Default filtering

To limit noise, the default output includes only `Normal,Foil` printings and `Near Mint` condition. Override with:

```bash
--printings all         # include every printing
--conditions all        # include every condition tier
--printings Foil        # Foil only
```

Summary totals (written to stderr) are computed on the unfiltered data so they reflect the full price landscape regardless of display filters.

---

## Configuration

### TOML config

Two locations are probed in order when `--config` is not given:

1. `./tcg.toml` — project-local (useful for per-deck defaults)
2. `~/.config/tcg/config.toml` — user-global

Full example with all keys:

```toml
product_line = "Grand Archive TCG"
printings = ["Normal", "Foil"]
conditions = ["Near Mint"]
copy_to_clipboard = true
write_parquet = false
output_path = "~/Desktop/deck.tsv"   # ~ is expanded at load time
```

Unknown keys emit a warning and are ignored; malformed TOML raises an error with the file path.

### Environment variables

| Env var | Config key | Accepted values |
|---|---|---|
| `TCG_PRODUCT_LINE` | `product_line` | Any string |
| `TCG_PRINTINGS` | `printings` | Comma-separated list or `all` |
| `TCG_CONDITIONS` | `conditions` | Comma-separated list or `all` |
| `TCG_COPY_TO_CLIPBOARD` | `copy_to_clipboard` | `1`/`0`, `true`/`false`, `yes`/`no` |
| `TCG_WRITE_PARQUET` | `write_parquet` | `1`/`0`, `true`/`false`, `yes`/`no` |
| `TCG_OUTPUT_PATH` | `output_path` | File path (`~` is expanded) |

### Precedence

```
CLI flags  >  env vars  >  TOML config  >  built-in defaults
```

CLI values override only when explicitly provided (not-None). Env vars override TOML. TOML overrides built-in defaults. A missing config file is silently skipped (no error).

---

## Maintainer scripts

### `refresh_product_lines.py`

Re-queries the TCGplayer aggregation endpoint and prints an updated `PRODUCT_LINES` literal to stdout.

Run this when TCGplayer adds or renames a product line:

```bash
uv run python scripts/refresh_product_lines.py
```

Paste the printed literal into `tcg/product_lines.py`. Do not edit that file by hand — the slugs must match the TCGplayer API exactly.

### `smoke_test.py`

One-shot connectivity check. Fetches a single well-known card and verifies the response parses correctly. Useful after a network environment change or when debugging TLS/UA issues.

```bash
uv run python scripts/smoke_test.py
```

Does not write any output file or clipboard content.

---

## CLI-private helpers

`scripts/_clipboard.py` and `scripts/_config.py` are private to the CLI (leading-underscore names). They are not part of any public API and should not be imported from outside `scripts/`.

- **`_clipboard.write_to_clipboard(text)`** — best-effort cross-platform clipboard write (macOS `pbcopy` / Windows `clip` / Linux `wl-copy` / `xclip` / `xsel`). Returns `False` silently when no clipboard tool is available.
- **`_config.load_config(...)`** — loads CLI flag defaults from `~/.config/tcg/config.toml`, `./tcg.toml`, and `TCG_*` env vars. See `_config.py` for the full precedence implementation.

---

## Separation of concerns

The `scripts/` layer contains only CLI-specific responsibilities: argument parsing, reading input from files or stdin, writing output to stdout/clipboard/stderr/file, and formatting.

Core logic — constructing HTTP requests, parsing responses, grouping price data, writing Parquet — lives in `tcg/` and is reusable from non-CLI contexts. Alternative frontends (HTTP server, GUI, spreadsheet add-on) should be added as sibling directories without modifying `tcg/`.

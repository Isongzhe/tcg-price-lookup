# `scripts/` — Command-Line Entry Points

Thin CLI wrappers that assemble the core logic from `tcg/` into
user-invokable commands.

| Script | Purpose | Typical Use |
|---|---|---|
| `fetch.py` | Single-card lookup | Ad-hoc queries for one card |
| `fetch_deck.py` | Batch decklist lookup | Primary workflow; paste output into a spreadsheet |

---

## `fetch_deck.py`

### Data Flow

```
decklist text
    │
    │ tcg.deck.parse_decklist()
    ▼
list[DeckEntry]
    │
    │ for each entry (separated by --sleep seconds):
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
    ├──> stdout (TSV)
    ├──> stderr (Rich progress bar + missing-card panel)
    ├──> data/snapshots.parquet    (suppressed with --no-parquet)
    └──> JSON file                 (if --json was given)
```

### Key Functions

| Function | Responsibility |
|---|---|
| `pick_best_hit()` | Selects the best autocomplete match for a given card name. |
| `build_variants()` | Merges listings, sales, and per-SKU market prices into a per-variant summary. |
| `enrich()` | Orchestrates the per-card fetch pipeline. |
| `print_tsv()` | Formats results as tab-separated output. |
| `print_summary()` | Writes reference totals and missing-card notes to stderr. |

### Match Selection

`pick_best_hit()` applies the following precedence when the autocomplete
endpoint returns multiple candidates:

1. If `--product-line` is set, candidates from other product lines are
   discarded.
2. Candidates whose base name (without parenthetical suffixes) exactly
   matches the input are preferred.
3. Within that set, candidates without parenthetical suffixes (e.g. no
   `(CSR)` or `(CUR)`) are preferred over special printings.
4. Ties are broken by the autocomplete score.

### Output Columns

Twenty-three columns per row, one row per
`(card × printing × condition × reprint set)` tuple:

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

- **`set_code`** is TCGplayer's short set identifier (e.g. `DTR1E`, `PTM`).
- **`number`** is the collector number within the set (e.g. `004`, `013`).
  Useful when distinguishing reprints that share a name but not a number.
- **`released`** is the set's release date (ISO `YYYY-MM-DD`). Populated on
  reprint-expanded rows; empty for cards resolved through autocomplete.
- **`market_price`** is per-SKU, aggregated by TCGplayer over roughly
  the last 30 days of sales. Normal and Foil rows carry independent
  values. Not real-time.
- **`mp_sample`** is how many sales underlie `market_price`. High values
  (≈15+) indicate a reliable price; values ≤ 3 mean the price is a
  near-singleton — treat as indicative only.
- **`most_recent_sale`** has no time bound. For illiquid cards it may be
  weeks or months old; always read it alongside `sale_count`.
- **`sale_avg` / `sale_count`** cover the fetched window (`--sales`,
  default 25). The time span is driven by liquidity, not a date filter.
- **`listing_*`** is a live snapshot of active listings at run time, not
  historical. Capped by `--listings` (default 20).
- **`image_url`** is a 200 px CDN URL. Wrap with `=IMAGE()` in Google
  Sheets to render thumbnails.
- **`missing`** contains a reason string when the card could not be resolved
  or an API call failed; it is empty otherwise.

#### Data freshness in one line

| Column | Timeframe |
|---|---|
| `market_price` / `mp_sample` | ~30 day rolling aggregate |
| `most_recent_sale` | Single newest sale (no age limit) |
| `sale_avg` / `sale_count` | Up to `--sales` most recent sales |
| `listing_*` | Live snapshot at run time |

The CLI never caches — every invocation re-fetches. Cross-run history is
opt-in via the `history` extras.

### Default Filtering

To limit noise, the default output includes only `Normal,Foil` printings and
`Near Mint` condition. Override with:

```bash
--printings all         # include every printing
--conditions all        # include every condition tier
--printings Foil        # Foil only
```

The summary totals (written to stderr) are computed on the unfiltered data
so that they reflect the full price landscape regardless of display filters.

---

## `fetch.py`

Single-card convenience command. Accepts a card-name query and returns the
matched product's price information interactively or automatically.

```bash
# Interactive: choose among candidates
uv run python -m scripts.fetch "alice golden queen" --product-line "Grand Archive TCG"

# Non-interactive: accept the top-scoring match
uv run python -m scripts.fetch "alice golden queen" --auto
```

Output is human-readable rather than tabular. For analysis or spreadsheet
import, use `fetch_deck.py` instead.

---

## Separation of Concerns

The `scripts/` layer contains only CLI-specific responsibilities:

- Argument parsing (`argparse`)
- Reading input from files, `stdin`, or the clipboard
- Writing output to `stdout`, `stderr`, or a file
- Formatting (TSV, JSON, terminal-friendly text)

Core logic — constructing HTTP requests, parsing responses, grouping price
data, writing Parquet — lives in `tcg/` and is reusable from non-CLI
contexts (for example, a web service or a notebook).

Alternative frontends (HTTP server, GUI, spreadsheet add-on) should be added
as sibling directories (`server/`, `ui/`, etc.) without modifying `tcg/`.

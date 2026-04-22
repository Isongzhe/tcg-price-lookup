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
    │   client.autocomplete()       locate productId
    │   client.product_details()    fetch metadata and SKU list
    │   client.latest_sales()       fetch recent sales
    │   client.listings()           fetch active listings
    │   client.market_price([sku])  fetch per-variant market prices
    ▼
DeckRow (with variants: list[VariantStats])
    │
    │ build_variants():
    │   group listings/sales by (printing, condition)
    │   merge per-SKU market prices
    ▼
    ├──> stdout (TSV)
    ├──> stderr (progress + reference totals)
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

Nineteen columns per row, one row per `(card × printing × condition)` tuple:

```
section          qty              card_name         matched_name
set_name         rarity           product_id        sku_id
printing         condition
market_price     mp_sample        most_recent_sale  sale_avg
sale_count       listing_min      listing_avg       listing_count
missing
```

Column notes:

- **`market_price`** is fetched per-SKU. Normal and Foil rows carry
  independent values.
- **`mp_sample`** is the number of historical sales underlying the market
  price. Values below three should be treated as indicative only.
- **`missing`** contains a reason string when the card could not be resolved
  or an API call failed; it is empty otherwise.

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

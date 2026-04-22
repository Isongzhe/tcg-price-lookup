# tcg-price-lookup

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](./LICENSE)
[![Tests](https://img.shields.io/badge/tests-35%20passing-brightgreen.svg)](./tests)

A command-line tool that turns a plain-text decklist into a spreadsheet of
current TCGplayer prices. It resolves each card name to a TCGplayer product,
fetches per-variant Market Price, recent sales, and active listings, and
emits a tab-separated table designed to paste directly into Google Sheets or
any other spreadsheet software.

---

## Canonical Usage (1.0)

The supported entry point as of version 1.0 is a single command. A decklist
file is read, each card is queried against TCGplayer, and the resulting TSV
is placed on the system clipboard for direct pasting into a spreadsheet:

```bash
uv run python -m scripts.fetch_deck mydeck.txt \
    --product-line "Grand Archive TCG" | pbcopy
```

Replace `pbcopy` with the clipboard command for your platform:

| Platform | Pipe Target |
|---|---|
| macOS | `pbcopy` |
| Linux (X11) | `xclip -selection clipboard` |
| Linux (Wayland) | `wl-copy` |
| Windows (PowerShell) | `Set-Clipboard` |
| Any | Redirect to a file: `> output.tsv` |

Progress messages and reference totals are written to `stderr` and remain
visible in the terminal regardless of how `stdout` is redirected.

---

## Features

- **Decklist parsing.** Accepts the conventional `# Section` + `N Card Name`
  format used by most deck-builders.
- **Name-to-productId resolution.** Autocomplete is used to locate the
  correct TCGplayer product from a card name, with filtering by product
  line.
- **Per-variant pricing.** Normal and Foil variants are queried separately
  at the SKU level, so each receives its own Market Price rather than
  sharing one product-level value.
- **Multiple price signals.** Every row reports Market Price, Most Recent
  Sale, Sale Average, Listing Minimum, and Listing Average. This allows
  callers to identify stale listings (e.g., a $2 listing next to a $40
  Market Price) and to judge the reliability of each data point via the
  accompanying sample-size columns.
- **Spreadsheet-friendly output.** Tab-separated values on `stdout`;
  progress and totals on `stderr`. Pipeable to any clipboard utility or
  file.
- **Card set, collector number, and image URL.** Each row carries the set
  code, collector number, and a CDN image URL suitable for Google Sheets'
  `=IMAGE()` function.
- **Reprint expansion.** When a card name exists in multiple sets (reprints
  with different art or collector numbers), every matching product is
  emitted as its own row, ordered newest release first. The `released`
  column lets spreadsheets sort or filter by set age.
- **Historical snapshots.** Each run appends to a local Parquet file that
  can be queried with DuckDB for price-trend analysis.
- **Polite by default.** Sequential requests with a configurable per-card
  delay, a single session warm-up, and a one-shot retry on transient
  failures.

---

## Requirements

- Python 3.11 or later
- [uv](https://github.com/astral-sh/uv) package manager (recommended)

Python dependencies are declared in `pyproject.toml` and installed
automatically. The core install is intentionally small:

| Package | Purpose |
|---|---|
| `curl_cffi` | HTTP client with browser TLS fingerprint emulation |
| `rich` | Progress bars and formatted terminal output on stderr |

An optional `history` extra adds `polars` + `duckdb` for local snapshot
storage and SQL querying. This is a **preview feature**: the CLI writes to
`data/snapshots.parquet` after each run when the extra is installed, but
there is no user-facing command yet for querying that file — you need to
call `tcg.storage.query()` from a Python shell. Most users should leave
it disabled.

---

## Installation

```bash
git clone https://github.com/Isongzhe/tcg-price-lookup.git
cd tcg-price-lookup
uv sync
```

To additionally install the optional `history` extras (preview — see
Requirements above):

```bash
uv sync --extra history
```

Verify the installation:

```bash
uv run pytest
```

All tests should pass in under 10 seconds. Storage tests are skipped
automatically when the `history` extras are not installed. No network
access is required.

---

## Input Format

Decklists are plain text. Sections begin with `#`. Card lines begin with a
quantity followed by the card name. Blank lines and unrecognized lines are
ignored.

```
# Material Deck
1 Alice, Golden Queen
1 Alice, Whim's Monarch

# Main Deck
4 Lorraine, Wandering Warrior
3 Diana, Keeper of Tradition

# Sideboard
2 Arisanna, Lucida Elegy
```

Decklists can also be streamed from `stdin` by passing `-` as the filename:

```bash
pbpaste | uv run python -m scripts.fetch_deck - --product-line "Grand Archive TCG"
```

### Exporting from deck builders

Decklists exported from common deck-building tools drop straight into the
parser without modification. For Grand Archive TCG specifically:

- **[Shout At Your Decks](https://shoutatyourdecks.com)** — open the deck,
  choose **Export → Omnidex Export**, copy the text, and either save it to
  `mydeck.txt` or pipe it directly through `pbpaste`. The Omnidex format
  uses `# Section` headers and `N Card Name` lines, which is the
  parser's native format.

Other deck builders that emit the same `# Section` + `N Card Name` shape
should also work. Unrecognized lines are ignored, so extra metadata in the
export is harmless.

---

## Command-Line Reference

### `scripts.fetch_deck` — batch decklist lookup

```
uv run python -m scripts.fetch_deck <file-or-dash> [options]
```

| Option | Default | Description |
|---|---|---|
| `--product-line <name>` | — | Restricts candidate cards to the given TCGplayer product line. Strongly recommended (e.g. `"Grand Archive TCG"`, `"Magic"`, `"Pokemon"`). |
| `--printings <list>` | `Normal,Foil` | Comma-separated printings to include in output. Pass `all` for every printing. |
| `--conditions <list>` | `Near Mint` | Comma-separated conditions to include. Pass `all` for every condition tier. |
| `--json <path>` | — | Additionally write results as structured JSON. |
| `--no-parquet` | off | Suppress appending to `data/snapshots.parquet`. |
| `--sleep <seconds>` | `0.8` | Delay between cards. Do not reduce without reason. |
| `--listings <n>` | `20` | Number of active listings fetched per card. |
| `--sales <n>` | `25` | Number of recent sales fetched per card. |

### `scripts.fetch` — single-card lookup

```
uv run python -m scripts.fetch "<card name>" [options]
```

Supports `--product-line` and `--auto` (accept top-scoring match without
prompting). Output format is human-readable; use `fetch_deck` for analysis.

---

## Output Format

One row per `(card × printing × condition × reprint set)` tuple.
Twenty-three columns, tab-separated:

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

| Column | Meaning |
|---|---|
| `set_name`, `set_code`, `number` | Set information. `set_code` is TCGplayer's short identifier (e.g. `DTR1E`, `PTM`); `number` is the collector number within the set (e.g. `004`). |
| `released` | ISO date of the set's release (e.g. `2026-04-03`). Populated for reprint-expanded rows; empty for cards resolved via autocomplete. Use for sorting reprints newest-first or oldest-first. |
| `rarity` | Rarity classification (e.g. `Super Rare`, `Ultra Rare`). |
| `market_price` | TCGplayer's aggregated per-SKU Market Price, computed from recent actual sales (roughly the last month, by TCGplayer's algorithm). Normal and Foil variants carry distinct values. Not real-time — can lag intra-day. |
| `mp_sample` | Number of sales TCGplayer used to compute `market_price`. High values (≈15+) indicate a liquid market and a reliable price; values ≤ 3 mean the price is essentially one data point and should be treated as indicative only. |
| `most_recent_sale` | Price of the single newest sale by order date, per variant. **No time bound** — for an unpopular card this may be weeks or months old. Cross-reference with `sale_count` before trusting it. |
| `sale_avg`, `sale_count` | Mean and count of recent sales fetched for this variant. Total rows fetched per card is capped by `--sales` (default 25), so `sale_count` ≤ 25 per variant. The time span those sales cover depends on how actively the card trades — liquid cards may see 25 sales in a day, illiquid cards may span months. |
| `listing_min`, `listing_avg`, `listing_count` | Statistics over listings **currently active on TCGplayer at the time of the run** — a live snapshot, not historical. Capped by `--listings` (default 20). |
| `image_url` | TCGplayer CDN image URL (200 px wide). Paste into Google Sheets and wrap with `=IMAGE()` to render a thumbnail in the cell. |
| `missing` | Failure reason if the card could not be resolved or a request failed. Empty for successful rows. |

### Data freshness at a glance

| Column | Timeframe |
|---|---|
| `market_price` / `mp_sample` | Aggregated sales over ~30 days (TCGplayer's algorithm) |
| `most_recent_sale` | Single most recent sale — could be today, could be months ago |
| `sale_avg` / `sale_count` | Up to `--sales` most recent sales; span varies by liquidity |
| `listing_*` | Live snapshot of active listings at run time |

The tool never caches results — every run fetches fresh data. Historical
tracking across runs requires the optional `history` extras (see
Requirements).

A reference subtotal (Normal NM and Foil NM) is written to `stderr` after
processing as a colorized table. These are informational; callers are
expected to aggregate in a spreadsheet or downstream tool.

### Displaying images in Google Sheets

After pasting the TSV, wrap the `image_url` column values with `=IMAGE(...)`
to render thumbnails directly in cells. For example, if the URL is in
column `U`:

```
=IMAGE(U2)
```

The CDN images are 200 px wide, which renders well in standard row heights.

### Pre-built Google Sheets template

A ready-to-use template with a one-click formatter (card previews,
currency formatting, auto-hiding of metadata columns) lives in
[`sheets/`](./sheets/). It is a convenience layer, not part of the core
CLI — see [`sheets/README.md`](./sheets/README.md) for the script source,
what it does and does not do, and the authorization flow to expect.

**Copy the template:**
[→ Open in Google Drive](https://docs.google.com/spreadsheets/d/1u7r0ND0wkUTGl7k8jDayK74l2U4KIlu_WLfJCR0dgcg/copy)

### Reprints

Some cards appear across multiple sets (e.g. Grand Archive reprints a card
into every new release). For those, one row is produced per set, ordered
newest release first. A common negotiation signal: the newest printing is
usually the cheapest while older printings retain a collector premium. The
`released`, `set_code`, and `number` columns together disambiguate which
printing a seller is actually offering.

---

## Historical Queries (preview, optional)

> Requires the `history` extras: `uv sync --extra history`.
> Not installed by default. See Requirements for rationale.

When installed, every run appends raw price events to
`data/snapshots.parquet` in long format. Queries can be issued through
DuckDB:

```python
from tcg.storage import query

df = query("""
    SELECT DATE_TRUNC('day', fetched_at) AS day,
           MIN(price) AS listing_min,
           AVG(price) AS listing_avg
    FROM snapshots
    WHERE card_name = 'Alice, Golden Queen'
      AND source = 'listing'
    GROUP BY day
    ORDER BY day DESC
""")
```

The Parquet file is gitignored by default. See
[`tcg/README.md`](./tcg/README.md) for the full schema.

---

## Architecture

```
scripts/fetch_deck.py          CLI entry point
        │
        ├──> tcg.deck           parse decklist
        ├──> tcg.client         HTTP client
        │       │
        │       └──> tcg.models dataclasses
        │
        └──> tcg.storage        Parquet + DuckDB
                │
                └──> tcg.models
```

```
TCG/
├── README.md
├── LICENSE                       Apache License 2.0
├── NOTICE                        Attribution notice
├── DISCLAIMER.md                 Terms of use and permitted scope
├── pyproject.toml
│
├── tcg/                          Core library (see tcg/README.md)
│   ├── __init__.py               Public API surface
│   ├── client.py                 HTTP client
│   ├── models.py                 Dataclasses + from_api parsers
│   ├── deck.py                   Decklist text parser
│   └── storage.py                Parquet writer + DuckDB queries
│
├── scripts/                      CLI entry points (see scripts/README.md)
│   ├── fetch.py                  Single-card lookup
│   └── fetch_deck.py             Batch decklist lookup (primary)
│
├── sheets/                       Google Sheets template (see sheets/README.md)
│   └── apps-script/              Formatter script source
│
└── tests/                        35 tests, no network required
    ├── fixtures/
    ├── test_client.py
    ├── test_deck.py
    ├── test_models.py
    └── test_storage.py
```

The `tcg/` package does not depend on `scripts/` and may be imported
directly:

```python
from tcg import TCGplayerClient

client = TCGplayerClient()
hits = client.autocomplete("alice golden queen")
details = client.product_details(hits[0].product_id)
```

Further documentation:

- [`tcg/README.md`](./tcg/README.md) — module responsibilities, data model, and extension points.
- [`scripts/README.md`](./scripts/README.md) — CLI data flow and design rationale.
- [`sheets/README.md`](./sheets/README.md) — Google Sheets template, Apps Script source, and authorization notes.

---

## Testing

```bash
uv run pytest
```

All tests are offline. HTTP behavior is exercised through a fake session
class, and one recorded API response is stored as a JSON fixture under
`tests/fixtures/`. The suite is intended to run in CI without external
network access.

---

## Roadmap

Version 1.0 stabilizes the command-line interface documented above. Future
work under consideration:

- Configurable language filter (currently `English` is hard-coded).
- Explicit syntax for special printings such as `(CSR)` or `(CUR)` in
  decklist input.
- Additional output formats (CSV, JSON Lines).
- Currency conversion (`--currency`) with a configurable exchange rate.

Breaking changes to the 1.0 CLI will be announced in release notes and
accompanied by a deprecation period where feasible.

---

## Limitations

- Only English-language SKUs are queried.
- Special printings (CSR, CUR, etc.) are deprioritized during name matching.
  Query them directly with `scripts.fetch` when needed.
- Requests are serial. A thirty-card deck takes approximately thirty seconds
  at the default politeness delay. Parallel execution is intentionally not
  offered.
- Market Price samples for Foil variants of less-traded cards are often
  small (`mp_sample ≤ 3`). Treat low-sample values as indicative rather than
  authoritative.

---

## Contributing

Issues and pull requests are welcome for:

- Bug fixes and documentation improvements.
- Support for additional decklist formats.
- Additional output formats.
- Historical-analysis helpers.

Changes that would enable high-frequency scraping, automated purchasing, or
any use outside the scope described in [`DISCLAIMER.md`](./DISCLAIMER.md)
will not be accepted.

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

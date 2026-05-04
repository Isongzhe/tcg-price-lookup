# `tcg/` — Core Library

Business logic for interacting with TCGplayer's frontend endpoints. This
package has no CLI dependencies and is safe to import from any consumer:

```python
from tcg import TCGplayerClient, ProductDetails, Sku, PRODUCT_LINES, to_slug
```

---

## Module Overview

| Module | Responsibility | Depends On |
|---|---|---|
| `__init__.py` | Public API surface | All submodules |
| `models.py` | Data classes and API JSON deserialization | stdlib only |
| `product_lines.py` | Canonical TCGplayer product-line catalog — display name → URL slug | stdlib only |
| `endpoints.py` | TCGplayer endpoint catalog (URL + method + purpose, single source of truth) | stdlib only |
| `client.py` | HTTP client wrapping five TCGplayer endpoints | `curl_cffi`, `models`, `product_lines`, `endpoints` |
| `deck.py` | Text-format decklist parser | stdlib (`re`) |
| `decklist.py` | Decklist orchestration — `DeckRow`, `VariantStats`, `build_variants`, `enrich` | `models`, `client`, `deck` |
| `output.py` | TSV serializer — `print_tsv` public serializer | `models`, `decklist` |
| `_fingerprint.py` | Host-OS-aware request headers (internal; not in `__all__`) | stdlib only |
| `storage.py` | Parquet writer and DuckDB query helper | `polars`, `duckdb`, `models` |

**Dependency direction:** `models` is the base layer. `client` uses
`product_lines` for slug lookup; `decklist` and `output` layer on top of
`client` and `models`. `storage` is an optional extra. Any one layer can be
replaced without affecting the others.

---

## `models.py`

Defines the data structures shared across modules. All classes use
`@dataclass(frozen=True, slots=True)` for immutability and memory efficiency,
and expose a `from_api` classmethod for deserializing API responses.

### Classes

| Class | Source API | Key Fields | Purpose |
|---|---|---|---|
| `AutocompleteHit` | `autocomplete` | `product_id`, `product_name`, `product_line_name`, `score` | One entry from a name search |
| `ProductDetails` | `/v2/product/{id}/details` | `market_price`, `skus`, `rarity_name`, `set_name`, `set_code`, `collector_number`, `image_url` | Product metadata plus SKU list |
| `ProductSearchResult` | `/v1/search/request` | `product_id`, `set_name`, `release_date`, `collector_number`, `market_price` | One row per product; used to enumerate reprints sharing a card name |
| `Sku` | `ProductDetails.skus[]` | `sku_id`, `printing`, `condition`, `language` | One SKU = product × printing × condition × language |
| `MarketPrice` | `/pricepoints/marketprice/skus/search` | `sku_id`, `market_price`, `price_count`, `calculated_at` | Per-SKU market price aggregated by TCGplayer over roughly the last 30 days of sales. `price_count` is the underlying sample size; `calculated_at` is when the aggregate was last recomputed server-side. |
| `Sale` | `/product/{id}/latestsales` | `purchase_price`, `order_date`, `variant`, `condition` | One completed sale. The endpoint returns the most recent N sales in reverse chronological order; there is no explicit time filter, so the span of returned data is driven by how often the card actually trades. |
| `Listing` | `/v1/product/{id}/listings` | `price`, `printing`, `condition`, `seller_name` | One listing active on TCGplayer at the moment of the call. Not historical — refetch to see updates. |

### SKU Hierarchy

TCGplayer's data model is hierarchical:

```
productId (e.g. 644912)
    ├── SKU A = Normal × Near Mint × English
    ├── SKU B = Normal × Lightly Played × English
    ├── SKU C = Foil × Near Mint × English
    └── ...
```

Market Price data is stored per-SKU, not per-product. To obtain the market
price for a specific printing and condition, the caller must:

1. Call `client.product_details(product_id)` to retrieve the SKU list.
2. Use `ProductDetails.find_sku(printing, condition)` to locate the target
   SKU.
3. Call `client.market_price([sku.sku_id])` to fetch its price.

### `from_api` Conventions

- Missing fields are tolerated. `from_api` uses `dict.get("key")` rather than
  `dict["key"]` so upstream schema changes do not cause hard failures.
- Numeric fields pass through `_opt_float` to accept `None`, numeric strings,
  and malformed values without raising.
- Field names are normalized to `snake_case` regardless of the upstream
  convention (`camelCase` or `kebab-case`).

---

## `endpoints.py`

Single source of truth for every URL this library calls. Each entry is an
`Endpoint` frozen dataclass with `name`, `method`, `url`, `purpose`, and
`auth` fields.

### Public API

```python
from tcg import endpoints

endpoints.ALL           # tuple of all 7 Endpoint instances
endpoints.SEARCH        # the POST search endpoint
endpoints.MPFEV         # "5061" — bump when TCGplayer rolls a new build
```

### Catalog

| Name | Method | Purpose |
|---|---|---|
| `homepage` | GET | Warm-up: prime Cloudflare session cookies |
| `autocomplete` | GET | Card-name suggestions |
| `search` | POST | Product search + aggregations |
| `product_details` | GET | Full product metadata + SKU list |
| `latest_sales` | POST | N most recent completed sales |
| `listings` | POST | Active marketplace listings |
| `market_price` | POST | Per-SKU rolling 30-day Market Price |

Three endpoints (`product_details`, `latest_sales`, `listings`) have
`{product_id}` placeholders in their URL; substitute with
`endpoint.url.format(product_id=...)` at call time.

---

## `client.py`

Wraps five TCGplayer endpoints behind a single `TCGplayerClient` class with
unified session management, warm-up, TLS fingerprint emulation, and retry
logic.

### Public API

```python
client = TCGplayerClient()

client.autocomplete(query, product_line=None)        -> list[AutocompleteHit]
client.search_products(name, product_line=None)      -> list[ProductSearchResult]
client.product_details(product_id)                   -> ProductDetails | None
client.latest_sales(product_id, limit=25)            -> list[Sale]
client.listings(product_id, limit=50)                -> list[Listing]
client.market_price(sku_ids)                         -> list[MarketPrice]
```

`autocomplete` is the fast path for disambiguated queries. `search_products`
is used when autocomplete returns a reprint aggregate (same name across
multiple sets) and the caller wants to enumerate every matching product.

### Design Notes

**Session-based.** A single `curl_cffi.requests.Session` is shared across all
requests so that session cookies issued by the target CDN persist for the
client's lifetime.

**One-shot warm-up.** Before the first real API call, `_warm_up()` issues a
single GET to the homepage to prime session cookies. A guard flag
(`_warmed_up`) ensures this happens at most once per client.

**TLS fingerprint emulation.** Every outbound request specifies
`impersonate="chrome146"` so that `curl-impersonate` constructs a TLS
ClientHello matching Chrome 146. The Chrome major is the single source of
truth — bump `_CHROME_VERSION` in `client.py` to update both the impersonate
target and every header that carries a Chrome version string.

**Session identifier.** A random UUID (`self.session_id`) is generated at
construction time and reused across autocomplete requests. The target
endpoint treats this as an analytics identifier rather than authentication.

**Automatic retry.** `_request()` retries once on HTTP 403 or 429 after
re-running warm-up. No further retries are attempted; repeated failures
surface as `TCGplayerError`.

### Endpoint Mapping

| Host | Purpose | Method |
|---|---|---|
| `www.tcgplayer.com` | Session warm-up | `_warm_up()` |
| `data.tcgplayer.com` | Name autocomplete | `autocomplete()` |
| `mp-search-api.tcgplayer.com` | Product details, active listings | `product_details()`, `listings()` |
| `mpapi.tcgplayer.com` | Recent sales | `latest_sales()` |
| `mpgateway.tcgplayer.com` | Aggregate market price | `market_price()` |

### Error Handling

`TCGplayerError` is raised for non-2xx responses after retry. Consumers
should catch it and either skip the affected card or abort the batch.

---

## `product_lines.py`

Canonical mapping of TCGplayer product-line display names to their URL slugs.

### Why it exists

TCGplayer's URL slugs diverge from display names in non-obvious ways —
Disney Lorcana → `"lorcana-tcg"`, Magic: The Gathering → `"magic"`, Dragon
Ball Super: Masters → `"dragon-ball-super-masters"`. A hand-rolled heuristic
(`lower().replace(" tcg", "")` etc.) produces wrong slugs for roughly 23 of
68 product lines. This module is the canonical, verified mapping.

### Public API

```python
from tcg import PRODUCT_LINES, to_slug
from tcg.product_lines import suggest

slug = to_slug("Disney Lorcana")   # -> "lorcana-tcg", or None if unknown
candidates = suggest("lorcana")    # -> ["Disney Lorcana"]  ("did you mean?")
```

- **`PRODUCT_LINES`** — `dict[str, str]` of 68 entries, display name → slug.
  Snapshot dated 2026-05-04.
- **`to_slug(display_name)`** — returns the slug for an exact display-name
  match, or `None` if the name is not in the catalog.
- **`suggest(query)`** — returns close-match display names for "did you mean"
  feedback when a user-supplied product-line name is unrecognized.

To regenerate after TCGplayer adds or renames product lines, run
`scripts/refresh_product_lines.py`. Do not edit `tcg/product_lines.py` by
hand.

---

## `deck.py`

Parses plain-text decklists into structured entries.

### Public API

```python
from tcg.deck import parse_decklist, DeckEntry

entries: list[DeckEntry] = parse_decklist(text)
```

### Supported Format

```
# Section Name
<quantity> <card name>
```

### Parsing Rules

- Lines beginning with `#` set the current section.
- Card lines are matched with `^\s*(\d+)\s+(.+?)\s*$`.
- Blank lines and empty sections are ignored.
- Lines that do not match the pattern are silently skipped, allowing files
  to contain comments or incidental prose.

The parser is intentionally minimal. Special-printing suffixes (`(CSR)`,
`(CUR)`), sideboard shorthands (`SB:`), and language tags are not
interpreted. Callers requiring those features should preprocess input.

---

## `storage.py`

Appends query results to a Parquet file and provides a DuckDB helper for
historical analysis.

### Public API

```python
from tcg.storage import snapshot_to_rows, append_snapshot, query

rows = snapshot_to_rows(product_id, card_name, sales, listings, market_prices)
append_snapshot(rows, path=SNAPSHOT_PATH)
df = query("SELECT ... FROM snapshots")
```

### Schema

A single long-format table, where each row represents one price event from a
single fetch:

| Column | Type | Description |
|---|---|---|
| `fetched_at` | Datetime (UTC) | Timestamp of the fetch |
| `product_id`, `card_name` | Int64, Utf8 | Card identity |
| `source` | Utf8 | `"sale"`, `"listing"`, or `"market"` |
| `price`, `shipping_price`, `quantity` | Float64, Float64, Int64 | Monetary fields |
| `condition`, `printing`, `language`, `variant` | Utf8 | SKU attributes |
| `seller_name`, `sku_id`, `order_date` | Utf8, Int64, Utf8 | Source-specific metadata |
| `market_price`, `low_price` | Float64 | Populated only when `source = 'market'` |

A long schema was chosen in preference to a wide one: listings, sales, and
market-price events have different cardinalities per card, so a wide table
would contain many NULL columns. DuckDB aggregations over the long table
remain straightforward.

### Example Query

```python
from tcg.storage import query

df = query("""
    SELECT DATE_TRUNC('day', fetched_at) AS day, MIN(price) AS min_listing
    FROM snapshots
    WHERE card_name = 'Alice, Golden Queen'
      AND source = 'listing'
      AND fetched_at > now() - INTERVAL 7 DAY
    GROUP BY day
    ORDER BY day
""")
```

---

## Public API (`__init__.py`)

Exported symbols (matches `__all__` exactly):

```python
from tcg import (
    TCGplayerClient,
    TCGplayerError,
    AutocompleteHit, ProductDetails, ProductSearchResult, Sku,
    MarketPrice, Sale, Listing,
    PRODUCT_LINES, to_slug,
    DeckRow, VariantStats,
    print_tsv,
    Endpoint, endpoints,
)
```

| Name | Kind | Description |
|---|---|---|
| `TCGplayerClient` | class | HTTP client |
| `TCGplayerError` | exception | All client errors |
| `AutocompleteHit` | dataclass | Raw autocomplete match |
| `Listing` | dataclass | One active listing |
| `MarketPrice` | dataclass | Market price for a SKU |
| `ProductDetails` | dataclass | Full product + SKU data |
| `ProductSearchResult` | dataclass | One result from `search_products` |
| `Sale` | dataclass | One recent sale record |
| `Sku` | dataclass | Per-printing/condition SKU |
| `PRODUCT_LINES` | dict | Display name → URL slug mapping (68 entries) |
| `to_slug` | function | Convert a product-line display name to its URL slug |
| `DeckRow` | dataclass | One resolved card row (output of `enrich`) |
| `VariantStats` | dataclass | Per-variant price summary (printing × condition) |
| `print_tsv` | function | Serialize a list of `DeckRow` to TSV |
| `Endpoint` | dataclass | Endpoint metadata (name, method, URL, purpose) |
| `endpoints` | module | Endpoint catalog (`endpoints.ALL`, `endpoints.SEARCH`, etc.) |

The following symbols are considered internal and subject to change without
notice:

- `TCGplayerClient._request()`, `TCGplayerClient._warm_up()`
- `tcg._fingerprint` (entire module)
- `storage.SNAPSHOT_PATH`, `storage._SCHEMA`

---

## Extension Points

| Requirement | Location |
|---|---|
| New API endpoint | `client.py` (add method) + `models.py` (add dataclass) |
| New decklist syntax | `deck.py` (extend regex) |
| New TSV column | `decklist.py` (`DeckRow`, `VariantStats`) + `output.py` (`print_tsv`) |
| Additional historical columns | `storage.py` (`_SCHEMA` and `snapshot_to_rows`) |
| New CLI flag | `scripts/fetch_deck.py` — do not modify `tcg/` |
| Refresh product-line catalog | `scripts/refresh_product_lines.py` (auto-generated; do not edit `tcg/product_lines.py` by hand) |

The guiding principle is that `tcg/` contains pure logic and data, while
presentation and argument parsing live in `scripts/`.

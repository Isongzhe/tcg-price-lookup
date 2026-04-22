# `tcg/` — Core Library

Business logic for interacting with TCGplayer's frontend endpoints. This
package has no CLI dependencies and is safe to import from any consumer:

```python
from tcg import TCGplayerClient, ProductDetails, Sku
```

---

## Module Overview

| Module | Responsibility | Depends On |
|---|---|---|
| `__init__.py` | Public API surface | All submodules |
| `models.py` | Data classes and API JSON deserialization | stdlib only |
| `client.py` | HTTP client wrapping five TCGplayer endpoints | `curl_cffi`, `models` |
| `deck.py` | Text-format decklist parser | stdlib (`re`) |
| `storage.py` | Parquet writer and DuckDB query helper | `polars`, `duckdb`, `models` |

**Dependency direction:** `models` is the base layer. `client`, `deck`, and
`storage` each depend on `models` but not on each other. Any one of them can
be replaced without affecting the others.

---

## `models.py`

Defines the data structures shared across modules. All classes use
`@dataclass(frozen=True, slots=True)` for immutability and memory efficiency,
and expose a `from_api` classmethod for deserializing API responses.

### Classes

| Class | Source API | Key Fields | Purpose |
|---|---|---|---|
| `AutocompleteHit` | `autocomplete` | `product_id`, `product_name`, `product_line_name`, `score` | One entry from a name search |
| `ProductDetails` | `/v2/product/{id}/details` | `market_price`, `skus`, `rarity_name`, `set_name` | Product metadata plus SKU list |
| `Sku` | `ProductDetails.skus[]` | `sku_id`, `printing`, `condition`, `language` | One SKU = product × printing × condition × language |
| `MarketPrice` | `/pricepoints/marketprice/skus/search` | `sku_id`, `market_price`, `price_count`, `calculated_at` | Per-SKU market statistics |
| `Sale` | `/product/{id}/latestsales` | `purchase_price`, `order_date`, `variant`, `condition` | One historical sale |
| `Listing` | `/v1/product/{id}/listings` | `price`, `printing`, `condition`, `seller_name` | One currently active listing |

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

## `client.py`

Wraps five TCGplayer endpoints behind a single `TCGplayerClient` class with
unified session management, warm-up, TLS fingerprint emulation, and retry
logic.

### Public API

```python
client = TCGplayerClient()

client.autocomplete(query, product_line=None) -> list[AutocompleteHit]
client.product_details(product_id)            -> ProductDetails | None
client.latest_sales(product_id, limit=25)     -> list[Sale]
client.listings(product_id, limit=50)         -> list[Listing]
client.market_price(sku_ids)                  -> list[MarketPrice]
```

### Design Notes

**Session-based.** A single `curl_cffi.requests.Session` is shared across all
requests so that session cookies issued by the target CDN persist for the
client's lifetime.

**One-shot warm-up.** Before the first real API call, `_warm_up()` issues a
single GET to the homepage to prime session cookies. A guard flag
(`_warmed_up`) ensures this happens at most once per client.

**TLS fingerprint emulation.** Every outbound request specifies
`impersonate="chrome120"` so that `curl-impersonate` constructs a TLS
ClientHello matching Chrome 120.

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

Exported symbols:

```python
from tcg import (
    TCGplayerClient,
    AutocompleteHit, ProductDetails, Sku,
    MarketPrice, Sale, Listing,
)
```

The following symbols are considered internal and subject to change without
notice:

- `TCGplayerError`
- `TCGplayerClient._request()`, `TCGplayerClient._warm_up()`
- `storage.SNAPSHOT_PATH`, `storage._SCHEMA`

---

## Extension Points

| Requirement | Location |
|---|---|
| New API endpoint | `client.py` (add method) + `models.py` (add dataclass) |
| New decklist syntax | `deck.py` (extend regex) |
| Additional historical columns | `storage.py` (`_SCHEMA` and `snapshot_to_rows`) |
| New CLI flag | `scripts/fetch_deck.py` — do not modify `tcg/` |

The guiding principle is that `tcg/` contains pure logic and data, while
presentation and argument parsing live in `scripts/`.

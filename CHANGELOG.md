# Changelog

All notable changes documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-05-04

First stable release. The TSV column order and exported dataclass fields
are now a stable contract within the 1.x line: new columns and fields
will be appended only; renames, reorders, removals, and semantic changes
require a MAJOR bump.

### Added

- Public library API exported from `tcg.__all__`: `TCGplayerClient`, `TCGplayerError`, `AutocompleteHit`, `Listing`, `MarketPrice`, `ProductDetails`, `ProductSearchResult`, `Sale`, `Sku`, `PRODUCT_LINES`, `to_slug`, `DeckRow`, `VariantStats`, `print_tsv`, `Endpoint`, `endpoints`
- `tcg/product_lines.py` — canonical 68-entry TCGplayer product-line catalog (snapshot 2026-05-04) with display-name → URL-slug lookup
- `tcg/endpoints.py` — endpoint catalog (`Endpoint` frozen dataclass; `endpoints.ALL`, `endpoints.SEARCH`, `endpoints.MPFEV`); `--list-endpoints` CLI flag
- `tcg/decklist.py` — `DeckRow`, `VariantStats`, `build_variants`, `enrich` (extracted from CLI into the library; part of the stable 1.0.0 API)
- `tcg/output.py` — `print_tsv` as a public serializer (extracted from CLI)
- `tcg/_fingerprint.py` — host-OS-aware request headers so Linux/Windows users don't send macOS-claiming requests (internal; not in `__all__`)
- `scripts/_clipboard.py` — cross-platform clipboard write (relocated from `tcg/clipboard.py`; private to CLI)
- `scripts/_config.py` — TOML + env config loader (relocated from `tcg/config.py`; private to CLI)
- `scripts/refresh_product_lines.py` — re-query TCGplayer product-line aggregation and print an updated `PRODUCT_LINES` literal
- `scripts/smoke_test.py` — one-shot connectivity check (renamed from root `main.py`)
- `--list-product-lines`, `--list-endpoints`, `--no-copy`, `--config PATH`, `--output PATH` CLI flags
- `TCG_PRODUCT_LINE`, `TCG_PRINTINGS`, `TCG_CONDITIONS`, `TCG_COPY_TO_CLIPBOARD`, `TCG_WRITE_PARQUET`, `TCG_OUTPUT_PATH` environment variables
- Auto-clipboard: TSV is written to the system clipboard by default on macOS (`pbcopy`), Windows (`clip`), and Linux (`wl-copy` / `xclip` / `xsel`)
- Output destinations summary block printed to stderr at end of each CLI run (stdout / clipboard / file)
- `decks/sample_deck.txt` — public sample deck, tracked in git; used as the Quick-Start example and test fixture
- ruff lint + format configuration (`pyproject.toml`)
- Google-style docstrings on all public API symbols

### Changed

- All Chinese comments and user-facing strings translated to English
- Auto-clipboard paste hint is platform-specific (⌘V on macOS, Ctrl+V elsewhere)
- TLS impersonate target bumped from `chrome120` to `chrome146` to match `curl_cffi` support and eliminate TLS/UA version inconsistency
- Sample deck moved from `examples/sample_deck.txt` to `decks/sample_deck.txt` (single workspace directory; `examples/` removed)

### Fixed

- `client.search_products(product_line=…)` — replaced fragile `lower().replace(" tcg", "")` heuristic with verified slug lookup from `tcg/product_lines.py`. The heuristic produced incorrect slugs for ~23 of 68 product lines including Disney Lorcana, Magic: The Gathering, Dragon Ball Super: Masters, Flesh and Blood TCG, Star Wars: Unlimited, Shadowverse: Evolve, and others.
- `scripts/refresh_product_lines.py` — fixed JSON path bug that caused the script to silently print empty `PRODUCT_LINES = {}`.

### Removed (BREAKING)

- `scripts/fetch.py` (single-card CLI). Use `scripts/fetch_deck.py` with a one-line deck file instead.
- CLI flags: `--sleep`, `--listings`, `--sales`, `--json`. These had reasonable hardcoded defaults; library users wanting custom values should call `TCGplayerClient` directly.
- `--no-parquet` flag.

### Changed (BREAKING)

- Parquet snapshot writing is now opt-in: pass `--parquet` (or set `write_parquet = true` in config). Previously it was on by default whenever the optional `[history]` extras were installed.

### Internal

- Relocated `tcg/clipboard.py` → `scripts/_clipboard.py` and `tcg/config.py` → `scripts/_config.py`. These modules were never in `tcg.__all__` so this is not a breaking change for any library consumer. The leading-underscore names signal that they are private to the CLI.
- Renamed `main.py` → `scripts/smoke_test.py`.

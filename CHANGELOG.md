# Changelog

All notable changes documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-05-04

First stable release. The TSV column order and exported dataclass fields
are now a stable contract within the 1.x line: new columns and fields
will be appended only; renames, reorders, removals, and semantic changes
require a MAJOR bump.

### Added
- Public library API exported from `tcg`: `TCGplayerClient`, `TCGplayerError`, `AutocompleteHit`, `Listing`, `MarketPrice`, `ProductDetails`, `ProductSearchResult`, `Sale`, `Sku`, `PRODUCT_LINES`, `to_slug`
- `tcg/product_lines.py` — canonical 68-entry TCGplayer product-line catalog (snapshot 2026-05-04) with display-name → URL-slug lookup
- `tcg/config.py` — TOML config (`~/.config/tcg/config.toml`, `./tcg.toml`) with `TCG_*` env-var overrides
- `tcg/clipboard.py` — cross-platform clipboard write (macOS pbcopy, Windows clip, Linux wl-copy/xclip/xsel) with silent fallback
- `--list-product-lines` flag
- `--no-copy` flag and `--config PATH` flag
- `scripts/refresh_product_lines.py` — re-query TCGplayer aggregation and print an updated `PRODUCT_LINES` literal
- Auto-clipboard: TSV is written to the system clipboard by default on supported platforms

### Changed
- All Chinese comments and user-facing strings translated to English

### Fixed
- `client.search_products(product_line=...)` now uses a verified slug lookup instead of a string heuristic. The previous `lower().replace(" tcg", "").strip()` heuristic produced incorrect slugs for ~23 of 68 product lines, including: Disney Lorcana, Magic: The Gathering, Dragon Ball Super: Masters, Flesh and Blood TCG, Star Wars: Unlimited, Shadowverse: Evolve, and others.

### Removed (BREAKING)
- `scripts/fetch.py` (single-card CLI). Use `scripts/fetch_deck.py` with a one-line deck file instead.
- CLI flags: `--sleep`, `--listings`, `--sales`, `--json`. These had reasonable hardcoded defaults; library users wanting custom values should call `TCGplayerClient` directly.
- `--no-parquet` flag.

### Changed (BREAKING)
- Parquet snapshot writing is now opt-in: pass `--parquet` (or set `write_parquet = true` in config). Previously it was on by default whenever the optional `[history]` extras were installed.

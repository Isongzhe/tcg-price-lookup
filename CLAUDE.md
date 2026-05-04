# CLAUDE.md — Developer guide for AI assistants

## Project shape

Library-first TCGplayer price-lookup tool. The `tcg/` package is the core:
a thin HTTP client (`tcg/client.py`) returning typed dataclasses
(`tcg/models.py`), with no I/O side effects and no storage opinions.
`scripts/fetch_deck.py` is one CLI consumer of that library — not the other
way around. `tcg/storage.py` (parquet + DuckDB) is a *demonstration* of one
persistence approach; it is opt-in and belongs in `[history]` extras. Do not
treat it as core.

## Stability contract

The TSV column order in `print_tsv` (`scripts/fetch_deck.py`) and the
dataclass fields in `tcg/models.py` are a **stable contract within MAJOR**.
Rules:

- New columns/fields: append only.
- Renames, reorders, removals, semantic changes: **MAJOR bump + CHANGELOG entry**.

Do not reorder fields or columns "for clarity." Do not change a field's type
without a MAJOR bump.

## Workspace convention

The repo doubles as a personal working directory. `decks/`, `prices/`,
and `notes/` are git-ignored — each contributor keeps their own
decklists, CLI outputs, and personal notes there alongside the source
code. None of this ships to GitHub.

The single exception is `decks/sample_deck.txt`: a small, English,
version-controlled deck that doubles as the public Quick-Start example
and the test fixture for `tests/test_sample_deck.py`. The `.gitignore`
uses a negation rule (`!decks/sample_deck.txt`) to track this one file
while ignoring everything else under `decks/`.

## Module placement

`tcg/` is the library — reusable code with no CLI/UX assumptions. Anything
a downstream integrator (duckdb pipeline, Discord bot, FastAPI service)
might `import` belongs here.

`scripts/` holds CLI behaviour — argparse parsing, interactive prompts,
and OS side-effects. Anything that exists *because the CLI exists* lives
here, including private helpers prefixed with `_` (e.g. `_clipboard.py`,
`_config.py`).

Litmus test: **"Would a library integrator ever import this?"** If no, it
belongs in `scripts/`.

## Public API surface

Everything listed in `tcg/__init__.py::__all__` is public contract.
Everything else is internal. When adding new public symbols, add them to
`__all__` intentionally and document the stability promise.

**Decklist orchestration**: `tcg/decklist.py` exposes `DeckRow`, `VariantStats`,
and `print_tsv` (via `tcg/output.py`) as part of the public stability contract.
`enrich(...)` and `build_variants(...)` are importable from `tcg.decklist` but
are not in `__all__` — they may evolve faster than the 1.0.0 contract permits
for `__all__` symbols.

## Product lines (`tcg/product_lines.py`)

`PRODUCT_LINES` is an API-derived snapshot (68 entries as of 2026-05-04).
To update it: run `scripts/refresh_product_lines.py` and paste the printed
literal into `product_lines.py`. **Do not edit entries by hand** — the slugs
must match the TCGplayer API exactly.

## Tests

```bash
uv run pytest          # run the full suite (86 tests, all offline)
```

TDD is expected: write tests before implementation for new features.
Storage tests skip automatically when `[history]` extras are absent.

## Run commands

```bash
uv run ruff check . && uv run ruff format --check .   # lint + format check

# Install
uv sync

# Install with history extras
uv sync --extra history

# Run the CLI
uv run python -m scripts.fetch_deck deck.txt --product-line "Grand Archive TCG"

# List product lines
uv run python -m scripts.fetch_deck --list-product-lines

# Smoke test (no network needed)
uv run pytest -q
```

## Docstring style

Public API symbols (everything in `tcg.__init__.__all__`) use Google-style
docstrings: first-line imperative summary, then `Args:`, `Returns:`,
`Raises:`, `Example:` sections as applicable. Internal helpers can use a
one-line summary or no docstring.

## Browser fingerprint

`tcg/_fingerprint.py` builds request headers matching the host OS so
Linux/Windows users don't ship macOS-claiming requests. The Chrome
version is the single source of truth — bump `_CHROME_VERSION` in
`tcg/client.py` to update both the curl_cffi impersonate target and
every header that carries a Chrome major.

## Endpoints catalog

`tcg/endpoints.py` is the single source of truth for the TCGplayer URLs
this library calls. `client.py` references entries from `endpoints.ALL`
rather than hardcoding URLs in method bodies. To inspect:

    uv run python -m scripts.fetch_deck --list-endpoints

When TCGplayer rolls a new search-API build, bump `endpoints.MPFEV`.

## Don'ts

- **Do not** add `duckdb` or `polars` to required deps — they belong only in
  `[history]` extras.
- **Do not** enable parquet writing by default. It is opt-in via `--parquet`
  or `write_parquet = true` in config.
- **Do not** write Chinese comments or strings. The project is in English.
- **Do not** add new CLI flags without first asking whether a config-file key
  or env var would better serve users.
- **Do not** call `scripts/fetch.py` — it was removed in 1.0.0.

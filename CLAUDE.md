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

## Public API surface

Everything listed in `tcg/__init__.py::__all__` is public contract.
Everything else is internal. When adding new public symbols, add them to
`__all__` intentionally and document the stability promise.

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

## Don'ts

- **Do not** add `duckdb` or `polars` to required deps — they belong only in
  `[history]` extras.
- **Do not** enable parquet writing by default. It is opt-in via `--parquet`
  or `write_parquet = true` in config.
- **Do not** write Chinese comments or strings. The project is in English.
- **Do not** add new CLI flags without first asking whether a config-file key
  or env var would better serve users.
- **Do not** call `scripts/fetch.py` — it was removed in 1.0.0.

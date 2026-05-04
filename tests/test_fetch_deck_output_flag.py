"""Tests for the --output PATH flag in scripts/fetch_deck.py.

Uses in-process main() calls with monkeypatching to avoid network calls,
mirroring the pattern established in test_list_endpoints_cli.py.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

from scripts.fetch_deck import main
from tcg.decklist import DeckRow, VariantStats


def _make_stub_deck_row(card_name: str = "Alice, Golden Queen") -> DeckRow:
    """Return a minimal DeckRow with one Normal/Near-Mint variant."""
    vs = VariantStats(
        printing="Normal",
        condition="Near Mint",
        sku_id=999,
        market_price=10.0,
        market_price_count=5,
        most_recent_sale=9.5,
        sale_avg=9.8,
        sale_count=5,
        listing_min=9.0,
        listing_avg=9.5,
        listing_count=3,
    )
    return DeckRow(
        section="Material Deck",
        quantity=1,
        card_name=card_name,
        matched_name=card_name,
        set_name="Dawn of Ashes",
        set_code="DOA1E",
        collector_number="001",
        rarity="Legendary",
        release_date="2023-03-31",
        product_id=12345,
        image_url="https://example.com/card.jpg",
        missing_reason=None,
        variants=[vs],
    )


def _run_main_with_stub(argv: list[str], monkeypatch) -> tuple[int, str]:
    """Run main(argv), monkeypatching enrich to return a canned DeckRow.

    Returns (exit_code, captured_stdout).
    """
    stub_row = _make_stub_deck_row()

    def fake_enrich(client, entry, product_line=None):
        return [(stub_row, [], [])]

    # Patch enrich so no HTTP calls are made
    monkeypatch.setattr("scripts.fetch_deck.enrich", fake_enrich)

    # Capture stdout (TSV goes there); also provide a fake stdin for '-' source
    captured = io.StringIO()
    fake_stdin = io.StringIO("1 Alice, Golden Queen\n")
    with (
        patch("sys.stdout", captured),
        patch("sys.stdin", fake_stdin),
        patch("scripts.fetch_deck.console"),
    ):
        exit_code = main(argv)

    return exit_code, captured.getvalue()


class TestOutputFlag:
    def test_output_flag_writes_tsv_to_file(self, tmp_path: Path, monkeypatch):
        """--output writes the TSV to the given file path."""
        out_file = tmp_path / "out.tsv"
        exit_code, _ = _run_main_with_stub(
            ["-", "--no-copy", f"--output={out_file}"],
            monkeypatch,
        )
        assert exit_code == 0
        assert out_file.exists(), "Output file was not created"
        content = out_file.read_text(encoding="utf-8")
        # First line must be the TSV header
        header_line = content.splitlines()[0]
        assert "card_name" in header_line, f"Expected TSV header, got: {header_line!r}"
        # Data row must contain the canned card name
        assert "Alice, Golden Queen" in content

    def test_output_flag_creates_missing_parent_dir(self, tmp_path: Path, monkeypatch):
        """--output silently creates the parent directory if it does not exist.

        Matches the behaviour of `git`, `curl -o`, `wget -O`, and most
        Unix tools that accept an output path: the user said where they
        want the file, so the tool prepares the path. Without this, a
        first-run user who set `output_path = "prices/last_run.tsv"` in
        config but never ran `mkdir prices/` would hit a confusing error.
        """
        nested = tmp_path / "deeply" / "nested" / "out.tsv"
        assert not nested.parent.exists(), "test precondition: parent should not exist"

        exit_code, _ = _run_main_with_stub(
            ["-", "--no-copy", f"--output={nested}"],
            monkeypatch,
        )
        assert exit_code == 0
        assert nested.exists(), "output file was not created"
        assert nested.parent.is_dir(), "parent directory was not auto-created"
        assert "Alice, Golden Queen" in nested.read_text(encoding="utf-8")

    def test_output_flag_real_failure_returns_nonzero(self, tmp_path: Path, monkeypatch):
        """A genuine OSError (e.g. parent path is a regular file, not a dir)
        still returns exit code 1 instead of crashing with a traceback."""
        # Create a regular file where we'd want a directory — mkdir will
        # fail because the path component already exists as a file.
        blocking_file = tmp_path / "blocker"
        blocking_file.write_text("not a directory")
        bad_path = blocking_file / "out.tsv"  # parent is a regular file → mkdir fails

        exit_code, _ = _run_main_with_stub(
            ["-", "--no-copy", f"--output={bad_path}"],
            monkeypatch,
        )
        assert exit_code == 1

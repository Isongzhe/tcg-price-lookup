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

    def test_output_flag_failure_returns_nonzero(self, tmp_path: Path, monkeypatch, capsys):
        """--output to a nonexistent directory returns exit code 1, no traceback."""
        bad_path = "/nonexistent_dir_xyz/out.tsv"
        exit_code, _ = _run_main_with_stub(
            ["-", "--no-copy", f"--output={bad_path}"],
            monkeypatch,
        )
        assert exit_code == 1
        # No traceback in stdout/stderr from subprocess (we're in-process, so
        # the console mock swallows rich output; just verify exit code is 1)

"""Tests for the --output PATH flag in scripts/fetch_deck.py.

Uses in-process main() calls with monkeypatching to avoid network calls,
mirroring the pattern established in test_list_endpoints_cli.py.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

from scripts.fetch_deck import main
from tcg.client import TCGplayerError
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


def _run_main_with_stub_custom_enrich(
    argv: list[str],
    custom_enrich,
    monkeypatch,
) -> tuple[int, str]:
    """Run main(argv) with a caller-supplied enrich function.

    Returns (exit_code, captured_stdout).
    Uses a real Console redirected to a buffer so Rich Progress
    internal time comparisons work without MagicMock issues.
    """
    from rich.console import Console

    monkeypatch.setattr("scripts.fetch_deck.enrich", custom_enrich)

    captured = io.StringIO()
    stderr_buf = io.StringIO()
    real_console = Console(file=stderr_buf, highlight=False)
    with (
        patch("sys.stdout", captured),
        patch("scripts.fetch_deck.console", real_console),
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


class TestBatchResilience:
    """A TCGplayerError on one card must not crash the whole batch."""

    def test_main_loop_continues_after_enrich_failure(self, tmp_path, monkeypatch):
        """A failing enrich for one card must not crash the batch.

        The failing card should appear as a missing row with a
        missing_reason that includes the error text, while the other
        cards are processed normally.
        """
        deck_file = tmp_path / "deck.txt"
        deck_file.write_text("# Deck\n1 Card A\n1 Card B\n1 Card C\n")

        call_count = [0]

        def fake_enrich(client, entry, product_line=None):
            call_count[0] += 1
            if call_count[0] == 2:
                raise TCGplayerError("GET /v2/product/X/details → 400: transient error")
            return [(_make_stub_deck_row(entry.card_name), [], [])]

        exit_code, tsv = _run_main_with_stub_custom_enrich(
            [str(deck_file), "--no-copy"],
            fake_enrich,
            monkeypatch,
        )

        assert exit_code == 0

        lines = [line for line in tsv.splitlines() if line.strip()]
        # header + 3 data rows (one per card)
        assert len(lines) == 4, f"Expected 4 lines (header + 3 cards), got {len(lines)}"

        data_rows = lines[1:]
        # Card B (second card) should be a missing row
        card_b_row = next((row for row in data_rows if "Card B" in row), None)
        assert card_b_row is not None, "Card B row not found in output"
        assert "API error after retry" in card_b_row, (
            f"Expected missing_reason in Card B row, got: {card_b_row!r}"
        )

        # Cards A and C should be normal rows with no missing_reason
        card_a_row = next((row for row in data_rows if "Card A" in row), None)
        card_c_row = next((row for row in data_rows if "Card C" in row), None)
        assert card_a_row is not None
        assert card_c_row is not None

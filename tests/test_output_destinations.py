"""Tests for the output-destinations feedback block in scripts/fetch_deck.py.

Uses in-process main() calls with monkeypatching to avoid network calls,
mirroring the pattern established in test_fetch_deck_output_flag.py.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import patch

from scripts.fetch_deck import _clipboard_paste_hint, main
from tcg.decklist import DeckRow, VariantStats


def _make_stub_row(card_name: str = "Alice, Golden Queen") -> DeckRow:
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


def _run_main_capturing_stderr(argv: list[str], monkeypatch) -> tuple[int, str]:
    """Run main(argv) with a stubbed enrich; capture what Rich prints to stderr."""
    stub_row = _make_stub_row()

    def fake_enrich(client, entry, product_line=None):
        return [(stub_row, [], [])]

    monkeypatch.setattr("scripts.fetch_deck.enrich", fake_enrich)

    stderr_buf = io.StringIO()
    stdout_buf = io.StringIO()
    fake_stdin = io.StringIO("1 Alice, Golden Queen\n")

    from rich.console import Console

    real_console_cls = Console

    def make_test_console(**kwargs):
        # Always write to our stderr buffer regardless of stderr=True kwarg
        return real_console_cls(file=stderr_buf, highlight=False)

    with (
        patch("sys.stdout", stdout_buf),
        patch("sys.stdin", fake_stdin),
        patch("scripts.fetch_deck.console", real_console_cls(file=stderr_buf, highlight=False)),
    ):
        exit_code = main(argv)

    return exit_code, stderr_buf.getvalue()


class TestDestinationsBlock:
    def test_destinations_block_shows_stdout_always(self, monkeypatch):
        """'stdout' line always appears in the destinations block."""
        _exit, stderr = _run_main_capturing_stderr(["-", "--no-copy"], monkeypatch)
        assert "stdout" in stderr

    def test_destinations_block_shows_clipboard_when_succeeded(self, monkeypatch):
        """When clipboard write succeeds, the green ✓ clipboard line is shown."""
        monkeypatch.setattr("scripts.fetch_deck.write_to_clipboard", lambda _text: True)
        _exit, stderr = _run_main_capturing_stderr(["-"], monkeypatch)
        assert "clipboard" in stderr
        # The dim skipped message should NOT appear
        assert "skipped" not in stderr

    def test_destinations_block_dims_clipboard_when_skipped(self, monkeypatch):
        """When --no-copy is passed, the dim skipped message is shown."""
        _exit, stderr = _run_main_capturing_stderr(["-", "--no-copy"], monkeypatch)
        assert "skipped" in stderr

    def test_destinations_block_shows_file_when_output_used(self, tmp_path: Path, monkeypatch):
        """When --output is passed and write succeeds, 'file:' line appears with the path."""
        out_file = tmp_path / "out.tsv"
        _exit, stderr = _run_main_capturing_stderr(
            ["-", "--no-copy", f"--output={out_file}"],
            monkeypatch,
        )
        assert "file:" in stderr
        # Rich may wrap the long path across lines; join lines for the path check
        stderr_joined = stderr.replace("\n", "")
        assert str(out_file) in stderr_joined

    def test_destinations_block_no_file_line_without_output(self, monkeypatch):
        """When --output is not passed, no 'file:' line appears."""
        _exit, stderr = _run_main_capturing_stderr(["-", "--no-copy"], monkeypatch)
        assert "file:" not in stderr


class TestClipboardPasteHint:
    def test_darwin_hint(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        assert "⌘V" in _clipboard_paste_hint()

    def test_win32_hint(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        hint = _clipboard_paste_hint()
        assert "Ctrl+V" in hint
        assert "⌘V" not in hint

    def test_linux_hint(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        hint = _clipboard_paste_hint()
        assert "Ctrl+V" in hint
        assert "⌘V" not in hint

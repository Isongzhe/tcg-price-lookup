"""Tests for TTY-aware output routing in scripts/fetch_deck.py.

TTY mode  → Rich Table (7 columns) to stdout; full TSV to clipboard/file.
Non-TTY   → Full 23-column TSV to stdout (unchanged legacy behaviour).
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

from scripts.fetch_deck import _render_rich_preview, main
from tcg.decklist import DeckRow, VariantStats

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _make_stub_row(
    card_name: str = "Alice, Golden Queen",
    missing_reason: str | None = None,
) -> DeckRow:
    variants = []
    if not missing_reason:
        variants = [
            VariantStats(
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
        ]
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
        missing_reason=missing_reason,
        variants=variants,
    )


def _run_main(argv: list[str], monkeypatch, *, is_tty: bool) -> tuple[int, str]:
    """Run main() with stubbed enrich, capturing stdout.

    is_tty controls what sys.stdout.isatty() returns so we can exercise
    both code paths without actually connecting to a terminal.
    """
    stub_row = _make_stub_row()

    def fake_enrich(client, entry, product_line=None):
        return [(stub_row, [], [])]

    monkeypatch.setattr("scripts.fetch_deck.enrich", fake_enrich)

    # Build a StringIO that reports isatty() as requested.
    stdout_buf = io.StringIO()
    stdout_buf.isatty = lambda: is_tty  # type: ignore[method-assign]

    fake_stdin = io.StringIO("1 Alice, Golden Queen\n")

    with (
        patch("sys.stdout", stdout_buf),
        patch("sys.stdin", fake_stdin),
        patch("scripts.fetch_deck.console"),
    ):
        exit_code = main(argv)

    return exit_code, stdout_buf.getvalue()


class TestTTYModeRichTable:
    def test_tty_mode_renders_rich_table(self, monkeypatch):
        """In TTY mode stdout receives a Rich Table, not raw TSV."""
        _exit, out = _run_main(["-", "--no-copy"], monkeypatch, is_tty=True)
        assert _exit == 0
        plain = _ANSI_RE.sub("", out)
        # Rich Table header row must be present
        assert "Section" in plain or "Card" in plain
        # The card name tokens must all appear (Rich may wrap long cell content)
        assert "Alice" in plain
        assert "Golden" in plain
        assert "Queen" in plain
        # Rich Table must NOT contain raw tab characters
        assert "\t" not in plain

    def test_non_tty_mode_emits_full_tsv(self, monkeypatch):
        """In non-TTY mode stdout receives the full 23-column TSV."""
        _exit, out = _run_main(["-", "--no-copy"], monkeypatch, is_tty=False)
        assert _exit == 0
        first_line = out.splitlines()[0]
        # Last column in the 23-column header is 'missing'
        assert first_line.endswith("\tmissing")
        # TSV contains tab characters
        assert "\t" in out
        # The card name must appear
        assert "Alice, Golden Queen" in out

    def test_clipboard_gets_full_tsv_in_tty_mode(self, monkeypatch):
        """Clipboard always receives the full 23-column TSV regardless of TTY mode."""
        captured_clipboard: list[str] = []

        def fake_write_clipboard(text: str) -> bool:
            captured_clipboard.append(text)
            return True

        monkeypatch.setattr("scripts.fetch_deck.write_to_clipboard", fake_write_clipboard)
        monkeypatch.setattr(
            "scripts.fetch_deck.enrich", lambda c, e, pl=None: [(_make_stub_row(), [], [])]
        )

        stdout_buf = io.StringIO()
        stdout_buf.isatty = lambda: True  # type: ignore[method-assign]
        fake_stdin = io.StringIO("1 Alice, Golden Queen\n")

        with (
            patch("sys.stdout", stdout_buf),
            patch("sys.stdin", fake_stdin),
            patch("scripts.fetch_deck.console"),
        ):
            main(["-"])

        assert len(captured_clipboard) == 1
        tsv = captured_clipboard[0]
        first_line = tsv.splitlines()[0]
        # Full 23-column header
        assert first_line.endswith("\tmissing")
        assert "\t" in tsv

    def test_output_file_gets_full_tsv_in_tty_mode(self, tmp_path: Path, monkeypatch):
        """--output file always receives the full 23-column TSV, even in TTY mode."""
        out_file = tmp_path / "out.tsv"
        monkeypatch.setattr(
            "scripts.fetch_deck.enrich", lambda c, e, pl=None: [(_make_stub_row(), [], [])]
        )

        stdout_buf = io.StringIO()
        stdout_buf.isatty = lambda: True  # type: ignore[method-assign]
        fake_stdin = io.StringIO("1 Alice, Golden Queen\n")

        with (
            patch("sys.stdout", stdout_buf),
            patch("sys.stdin", fake_stdin),
            patch("scripts.fetch_deck.console"),
        ):
            exit_code = main(["-", "--no-copy", f"--output={out_file}"])

        assert exit_code == 0
        content = out_file.read_text(encoding="utf-8")
        first_line = content.splitlines()[0]
        assert first_line.endswith("\tmissing")
        assert "Alice, Golden Queen" in content

    def test_missing_card_visible_in_rich_table(self, monkeypatch):
        """Missing cards appear in the Rich Table with their reason."""
        missing_row = _make_stub_row(card_name="Fake Card", missing_reason="no match")
        monkeypatch.setattr(
            "scripts.fetch_deck.enrich",
            lambda c, e, pl=None: [(missing_row, [], [])],
        )

        stdout_buf = io.StringIO()
        stdout_buf.isatty = lambda: True  # type: ignore[method-assign]
        fake_stdin = io.StringIO("1 Fake Card\n")

        with (
            patch("sys.stdout", stdout_buf),
            patch("sys.stdin", fake_stdin),
            patch("scripts.fetch_deck.console"),
        ):
            exit_code = main(["-", "--no-copy"])

        assert exit_code == 0
        plain = _ANSI_RE.sub("", stdout_buf.getvalue())
        assert "Fake Card" in plain
        assert "no match" in plain


class TestRenderRichPreviewUnit:
    """Unit tests for the _render_rich_preview helper directly."""

    def _render(self, rows: list[DeckRow]) -> str:
        buf = io.StringIO()
        con = Console(file=buf, highlight=False, width=120)
        _render_rich_preview(rows, con)
        return buf.getvalue()

    def test_normal_row_rendered(self):
        out = self._render([_make_stub_row()])
        assert "Alice, Golden Queen" in out
        assert "Normal" in out
        assert "$10.00" in out

    def test_missing_row_rendered(self):
        out = self._render([_make_stub_row(missing_reason="no match")])
        assert "Alice, Golden Queen" in out
        assert "no match" in out

    def test_row_with_no_variants_rendered(self):
        row = _make_stub_row()
        row.variants = []
        out = self._render([row])
        assert "Alice, Golden Queen" in out

    def test_no_tabs_in_output(self):
        out = self._render([_make_stub_row()])
        assert "\t" not in out


class TestPrintSummaryTTYMode:
    """print_summary should show different wording for tty_mode."""

    def _capture_summary(self, tty_mode: bool) -> str:
        from scripts.fetch_deck import print_summary

        buf = io.StringIO()
        con = Console(file=buf, highlight=False)
        rows = [_make_stub_row()]

        with patch("scripts.fetch_deck.console", con):
            print_summary(rows, clipboard_copied=True, no_copy=False, tty_mode=tty_mode)

        return buf.getvalue()

    def test_tty_mode_shows_preview_wording(self):
        out = self._capture_summary(tty_mode=True)
        assert "preview" in out.lower()
        assert "clipboard" in out.lower()

    def test_non_tty_mode_shows_printed_above_wording(self):
        out = self._capture_summary(tty_mode=False)
        assert "printed above" in out.lower()

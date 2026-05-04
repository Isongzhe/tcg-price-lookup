"""Tests for the --list-endpoints CLI flag in scripts/fetch_deck.py.

Uses the in-process approach (calling main() directly) rather than subprocess
so that: (1) no network calls are possible without mocking the session, and
(2) the test suite stays fully offline and fast.
"""

from __future__ import annotations

from unittest.mock import patch

from rich.table import Table

from scripts.fetch_deck import main
from tcg import endpoints


def _capture_table() -> tuple[int, Table | None]:
    """Run ``main(["--list-endpoints"])`` and return (exit_code, table_object).

    Intercepts the Rich Table passed to ``console.print`` directly so we can
    inspect column headers and cell values without depending on the text
    rendering of the terminal.
    """
    tables_printed: list[Table] = []

    with patch("scripts.fetch_deck.console") as mock_console:

        def capture(obj, *args, **kwargs):
            if isinstance(obj, Table):
                tables_printed.append(obj)

        mock_console.print.side_effect = capture
        exit_code = main(["--list-endpoints"])

    return exit_code, tables_printed[0] if tables_printed else None


class TestListEndpointsCLI:
    def test_exit_code_zero(self):
        code, _ = _capture_table()
        assert code == 0

    def test_output_contains_all_endpoint_names(self):
        """Every endpoint name appears in at least one table cell."""
        _, table = _capture_table()
        assert table is not None, "console.print was not called with a Rich Table"
        # Collect all cell renderable text from the table
        cell_texts: list[str] = []
        for col in table.columns:
            for cell in col._cells:  # Rich internal attribute
                cell_texts.append(str(cell))
        joined = " ".join(cell_texts)
        for ep in endpoints.ALL:
            assert ep.name in joined, (
                f"endpoint name {ep.name!r} missing from --list-endpoints table cells"
            )

    def test_does_not_instantiate_client(self):
        """Early-exit path must not create a TCGplayerClient (no network)."""
        with patch("scripts.fetch_deck.TCGplayerClient") as mock_client:
            main(["--list-endpoints"])
            mock_client.assert_not_called()

    def test_output_contains_column_headers(self):
        """Rich table must have Name/Method/URL/Purpose columns."""
        _, table = _capture_table()
        assert table is not None, "console.print was not called with a Rich Table"
        col_names = [c.header for c in table.columns]
        for expected in ("Name", "Method", "URL", "Purpose"):
            assert expected in col_names, f"Column {expected!r} missing; got {col_names}"

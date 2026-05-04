"""Tests for the --show-config CLI flag in scripts/fetch_deck.py.

Uses the in-process approach (calling main() directly) rather than subprocess
so that: (1) no network calls are possible without mocking the session, and
(2) the test suite stays fully offline and fast.
"""

from __future__ import annotations

import io
from unittest.mock import patch

from rich.console import Console

from scripts._config import _DEFAULTS
from scripts.fetch_deck import main


def _run_show_config(argv: list[str] | None = None) -> tuple[int, str]:
    """Run main() with --show-config and capture rendered output.

    Returns (exit_code, rendered_text).
    """
    if argv is None:
        argv = ["--show-config"]

    buf = io.StringIO()
    fake_console = Console(file=buf, highlight=False, markup=True)

    with patch("scripts.fetch_deck.console", fake_console):
        exit_code = main(argv)

    return exit_code, buf.getvalue()


class TestShowConfigCLI:
    def test_show_config_exits_zero_without_source(self, tmp_path, monkeypatch):
        """--show-config exits 0 without a positional source argument."""
        monkeypatch.chdir(tmp_path)
        code, _output = _run_show_config(["--show-config"])
        assert code == 0

    def test_show_config_output_mentions_all_config_keys(self, tmp_path, monkeypatch):
        """Rendered output mentions every config field name."""
        monkeypatch.chdir(tmp_path)
        code, output = _run_show_config(["--show-config"])
        assert code == 0
        for key in _DEFAULTS:
            assert key in output, f"Config key {key!r} missing from --show-config output"

    def test_show_config_with_no_overrides_marks_all_default(self, tmp_path, monkeypatch):
        """In a tmp dir with no tcg.toml, every field source is 'default'."""
        monkeypatch.chdir(tmp_path)
        code, output = _run_show_config(["--show-config"])
        assert code == 0
        # 'default' should appear once per config key (one row per key)
        assert "default" in output
        # No source column should show 'toml', 'env', or 'cli' on a data row
        # (the search order hint line may contain 'tcg.toml' — that's fine)
        lines = output.splitlines()
        data_lines = [line for line in lines if any(key in line for key in _DEFAULTS)]
        for line in data_lines:
            assert "toml" not in line, f"Expected no 'toml' source on data row: {line!r}"
            assert "  env" not in line, f"Expected no 'env' source on data row: {line!r}"
            assert "  cli" not in line, f"Expected no 'cli' source on data row: {line!r}"

    def test_show_config_with_toml_marks_toml_source(self, tmp_path, monkeypatch):
        """A field set in tcg.toml shows 'toml' as source in the data row."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "tcg.toml").write_text('product_line = "Grand Archive TCG"\n')
        code, output = _run_show_config(["--show-config"])
        assert code == 0
        # product_line row should show 'toml' as source
        lines = output.splitlines()
        product_line_lines = [line for line in lines if "product_line" in line]
        assert any("toml" in line for line in product_line_lines), (
            f"Expected 'toml' on product_line row; got: {product_line_lines}"
        )

    def test_show_config_with_cli_override_marks_cli(self, tmp_path, monkeypatch):
        """A field set via CLI flag shows 'cli' as source."""
        monkeypatch.chdir(tmp_path)
        code, output = _run_show_config(
            ["--show-config", "--product-line", "Grand Archive TCG"],
        )
        assert code == 0
        assert "cli" in output
        lines = output.splitlines()
        product_line_lines = [line for line in lines if "product_line" in line]
        assert any("cli" in line for line in product_line_lines), (
            f"Expected 'cli' on product_line row; got: {product_line_lines}"
        )

    def test_show_config_with_env_marks_env(self, tmp_path, monkeypatch):
        """A field set via TCG_* env var shows 'env' as source."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("TCG_REQUEST_INTERVAL", "0.5")
        code, output = _run_show_config(["--show-config"])
        assert code == 0
        assert "env" in output
        lines = output.splitlines()
        interval_lines = [line for line in lines if "request_interval" in line]
        assert any("env" in line for line in interval_lines), (
            f"Expected 'env' on request_interval row; got: {interval_lines}"
        )

    def test_show_config_does_not_instantiate_client(self, tmp_path, monkeypatch):
        """--show-config must not create a TCGplayerClient (no network)."""
        monkeypatch.chdir(tmp_path)
        with patch("scripts.fetch_deck.TCGplayerClient") as mock_client:
            buf = io.StringIO()
            fake_console = Console(file=buf, highlight=False, markup=True)
            with patch("scripts.fetch_deck.console", fake_console):
                main(["--show-config"])
            mock_client.assert_not_called()

    def test_show_config_includes_search_order_hint(self, tmp_path, monkeypatch):
        """Output ends with a search-order hint line."""
        monkeypatch.chdir(tmp_path)
        code, output = _run_show_config(["--show-config"])
        assert code == 0
        assert "Search order" in output

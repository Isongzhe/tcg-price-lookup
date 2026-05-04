"""Tests for scripts._config — Config dataclass and load_config() loader.

Priority order: CLI overrides > env vars > TOML file > hardcoded defaults.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from scripts._config import load_config

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_defaults():
    """No file, no env, no overrides → hardcoded defaults."""
    cfg = load_config({}, config_path=None, env={})
    assert cfg.product_line is None
    assert cfg.printings == ["Normal", "Foil"]
    assert cfg.conditions == ["Near Mint"]
    assert cfg.copy_to_clipboard is True
    assert cfg.write_parquet is False


# ---------------------------------------------------------------------------
# TOML loading
# ---------------------------------------------------------------------------


def test_toml_loaded(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text('product_line = "Grand Archive TCG"\n', encoding="utf-8")
    cfg = load_config({}, config_path=toml_file, env={})
    assert cfg.product_line == "Grand Archive TCG"


def test_toml_printings_and_conditions(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text(
        'printings = ["Foil"]\nconditions = ["Near Mint", "Lightly Played"]\n',
        encoding="utf-8",
    )
    cfg = load_config({}, config_path=toml_file, env={})
    assert cfg.printings == ["Foil"]
    assert cfg.conditions == ["Near Mint", "Lightly Played"]


def test_toml_bool_fields(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text(
        "copy_to_clipboard = false\nwrite_parquet = true\n",
        encoding="utf-8",
    )
    cfg = load_config({}, config_path=toml_file, env={})
    assert cfg.copy_to_clipboard is False
    assert cfg.write_parquet is True


# ---------------------------------------------------------------------------
# Env overrides TOML
# ---------------------------------------------------------------------------


def test_env_overrides_toml(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text('product_line = "Magic: The Gathering"\n', encoding="utf-8")
    cfg = load_config(
        {},
        config_path=toml_file,
        env={"TCG_PRODUCT_LINE": "Grand Archive TCG"},
    )
    assert cfg.product_line == "Grand Archive TCG"


# ---------------------------------------------------------------------------
# CLI overrides env
# ---------------------------------------------------------------------------


def test_cli_overrides_env(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text('product_line = "Magic: The Gathering"\n', encoding="utf-8")
    cfg = load_config(
        {"product_line": "Disney Lorcana"},
        config_path=toml_file,
        env={"TCG_PRODUCT_LINE": "Grand Archive TCG"},
    )
    assert cfg.product_line == "Disney Lorcana"


# ---------------------------------------------------------------------------
# Unknown keys in TOML → warn, don't raise
# ---------------------------------------------------------------------------


def test_unknown_toml_keys_warn_not_fail(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text(
        'unknown_key = 1\nproduct_line = "Pokemon"\n',
        encoding="utf-8",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cfg = load_config({}, config_path=toml_file, env={})

    assert cfg.product_line == "Pokemon"
    # At least one warning should mention the unknown key
    messages = [str(w.message) for w in caught]
    assert any("unknown_key" in m for m in messages), f"No warning for unknown_key in {messages}"


# ---------------------------------------------------------------------------
# Malformed TOML → clear error
# ---------------------------------------------------------------------------


def test_malformed_toml_raises_clear_error(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text("not valid toml ][[\n", encoding="utf-8")
    with pytest.raises((ValueError, Exception)) as exc_info:
        load_config({}, config_path=toml_file, env={})
    # Error message should include the path
    assert str(toml_file) in str(exc_info.value)


# ---------------------------------------------------------------------------
# Env bool parsing — TCG_COPY_TO_CLIPBOARD
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("0", False),
        ("false", False),
        ("False", False),
        ("FALSE", False),
        ("no", False),
        ("NO", False),
        ("1", True),
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("yes", True),
        ("YES", True),
    ],
)
def test_env_TCG_COPY_TO_CLIPBOARD_parsing(value: str, expected: bool):
    cfg = load_config({}, config_path=None, env={"TCG_COPY_TO_CLIPBOARD": value})
    assert cfg.copy_to_clipboard is expected


def test_env_write_parquet_parsing():
    cfg = load_config({}, config_path=None, env={"TCG_WRITE_PARQUET": "1"})
    assert cfg.write_parquet is True
    cfg2 = load_config({}, config_path=None, env={"TCG_WRITE_PARQUET": "0"})
    assert cfg2.write_parquet is False


def test_env_printings_comma_separated():
    cfg = load_config({}, config_path=None, env={"TCG_PRINTINGS": "Normal,Foil"})
    assert cfg.printings == ["Normal", "Foil"]


def test_env_conditions_comma_separated():
    cfg = load_config({}, config_path=None, env={"TCG_CONDITIONS": "Near Mint,Lightly Played"})
    assert cfg.conditions == ["Near Mint", "Lightly Played"]


# ---------------------------------------------------------------------------
# Config is frozen (immutable)
# ---------------------------------------------------------------------------


def test_config_is_frozen():
    cfg = load_config({}, config_path=None, env={})
    with pytest.raises((AttributeError, TypeError)):
        cfg.product_line = "Oops"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# output_path field
# ---------------------------------------------------------------------------


def test_output_path_from_toml(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text('output_path = "/tmp/foo.tsv"\n', encoding="utf-8")
    cfg = load_config({}, config_path=toml_file, env={})
    assert cfg.output_path == Path("/tmp/foo.tsv")


def test_output_path_expands_tilde(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text('output_path = "~/foo.tsv"\n', encoding="utf-8")
    cfg = load_config({}, config_path=toml_file, env={})
    assert cfg.output_path == Path("~/foo.tsv").expanduser()


def test_output_path_env_override(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text('output_path = "/tmp/foo.tsv"\n', encoding="utf-8")
    cfg = load_config({}, config_path=toml_file, env={"TCG_OUTPUT_PATH": "/tmp/bar.tsv"})
    assert cfg.output_path == Path("/tmp/bar.tsv")


def test_output_path_cli_override(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text('output_path = "/tmp/foo.tsv"\n', encoding="utf-8")
    cfg = load_config(
        {"output_path": Path("/tmp/cli.tsv")},
        config_path=toml_file,
        env={"TCG_OUTPUT_PATH": "/tmp/bar.tsv"},
    )
    assert cfg.output_path == Path("/tmp/cli.tsv")


def test_output_path_none_when_unset():
    cfg = load_config({}, config_path=None, env={})
    assert cfg.output_path is None

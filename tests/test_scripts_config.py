"""Tests for scripts._config — Config dataclass and load_config() loader.

Priority order: CLI overrides > env vars > TOML file > hardcoded defaults.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from scripts._config import Config, load_config

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_defaults():
    """No file, no env, no overrides → hardcoded defaults."""
    cfg, _ = load_config({}, config_path=None, env={})
    assert cfg.product_line is None
    assert cfg.printings == ["Normal", "Foil"]
    assert cfg.conditions == ["Near Mint"]
    assert cfg.copy_to_clipboard is True


# ---------------------------------------------------------------------------
# TOML loading
# ---------------------------------------------------------------------------


def test_toml_loaded(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text('product_line = "Grand Archive TCG"\n', encoding="utf-8")
    cfg, _ = load_config({}, config_path=toml_file, env={})
    assert cfg.product_line == "Grand Archive TCG"


def test_toml_printings_and_conditions(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text(
        'printings = ["Foil"]\nconditions = ["Near Mint", "Lightly Played"]\n',
        encoding="utf-8",
    )
    cfg, _ = load_config({}, config_path=toml_file, env={})
    assert cfg.printings == ["Foil"]
    assert cfg.conditions == ["Near Mint", "Lightly Played"]


def test_toml_bool_fields(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text(
        "copy_to_clipboard = false\n",
        encoding="utf-8",
    )
    cfg, _ = load_config({}, config_path=toml_file, env={})
    assert cfg.copy_to_clipboard is False


# ---------------------------------------------------------------------------
# Env overrides TOML
# ---------------------------------------------------------------------------


def test_env_overrides_toml(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text('product_line = "Magic: The Gathering"\n', encoding="utf-8")
    cfg, _ = load_config(
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
    cfg, _ = load_config(
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
        cfg, _ = load_config({}, config_path=toml_file, env={})

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
    cfg, _ = load_config({}, config_path=None, env={"TCG_COPY_TO_CLIPBOARD": value})
    assert cfg.copy_to_clipboard is expected


def test_env_printings_comma_separated():
    cfg, _ = load_config({}, config_path=None, env={"TCG_PRINTINGS": "Normal,Foil"})
    assert cfg.printings == ["Normal", "Foil"]


def test_env_conditions_comma_separated():
    cfg, _ = load_config({}, config_path=None, env={"TCG_CONDITIONS": "Near Mint,Lightly Played"})
    assert cfg.conditions == ["Near Mint", "Lightly Played"]


# ---------------------------------------------------------------------------
# Config is frozen (immutable)
# ---------------------------------------------------------------------------


def test_config_is_frozen():
    cfg, _ = load_config({}, config_path=None, env={})
    with pytest.raises((AttributeError, TypeError)):
        cfg.product_line = "Oops"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# output_path field
# ---------------------------------------------------------------------------


def test_output_path_from_toml(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text('output_path = "/tmp/foo.tsv"\n', encoding="utf-8")
    cfg, _ = load_config({}, config_path=toml_file, env={})
    assert cfg.output_path == Path("/tmp/foo.tsv")


def test_output_path_expands_tilde(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text('output_path = "~/foo.tsv"\n', encoding="utf-8")
    cfg, _ = load_config({}, config_path=toml_file, env={})
    assert cfg.output_path == Path("~/foo.tsv").expanduser()


def test_output_path_env_override(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text('output_path = "/tmp/foo.tsv"\n', encoding="utf-8")
    cfg, _ = load_config({}, config_path=toml_file, env={"TCG_OUTPUT_PATH": "/tmp/bar.tsv"})
    assert cfg.output_path == Path("/tmp/bar.tsv")


def test_output_path_cli_override(tmp_path: Path):
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text('output_path = "/tmp/foo.tsv"\n', encoding="utf-8")
    cfg, _ = load_config(
        {"output_path": Path("/tmp/cli.tsv")},
        config_path=toml_file,
        env={"TCG_OUTPUT_PATH": "/tmp/bar.tsv"},
    )
    assert cfg.output_path == Path("/tmp/cli.tsv")


def test_output_path_none_when_unset():
    cfg, _ = load_config({}, config_path=None, env={})
    assert cfg.output_path is None


# ---------------------------------------------------------------------------
# Single-source-of-truth: only ./tcg.toml is probed (no user-global fallback)
# ---------------------------------------------------------------------------


def test_no_tcg_toml_uses_defaults(tmp_path: Path, monkeypatch):
    """In a temp dir with no tcg.toml, load_config returns hardcoded defaults — no error."""
    monkeypatch.chdir(tmp_path)
    cfg, _ = load_config({}, config_path=None, env={})
    assert cfg.product_line is None
    assert cfg.printings == ["Normal", "Foil"]
    assert cfg.conditions == ["Near Mint"]
    assert cfg.copy_to_clipboard is True
    assert cfg.output_path is None
    assert cfg.request_interval == 0.8


def test_only_reads_tcg_toml(tmp_path: Path, monkeypatch):
    """Only ./tcg.toml is read; ~/.config/tcg/config.toml is NOT consulted."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Write a value to the fake user-global location
    user_global = tmp_path / ".config" / "tcg"
    user_global.mkdir(parents=True)
    (user_global / "config.toml").write_text(
        'product_line = "Should Not Appear"\n', encoding="utf-8"
    )

    # No ./tcg.toml written — user-global must NOT be read
    cfg, _ = load_config({}, config_path=None, env={})
    assert cfg.product_line is None  # default, not the user-global value


def test_tcg_toml_example_parses_cleanly(monkeypatch):
    """tcg.toml.example (all keys commented out) must parse cleanly and yield defaults."""
    import tomllib
    from pathlib import Path as _Path

    example = _Path(__file__).parent.parent / "tcg.toml.example"
    assert example.exists(), "tcg.toml.example must exist at repo root"

    with example.open("rb") as fh:
        parsed = tomllib.load(fh)

    assert parsed == {}, (
        f"tcg.toml.example should parse to an empty dict (all keys commented), got {parsed!r}"
    )

    # Also verify it produces the same Config as zero-config
    cfg_from_example, _ = load_config({}, config_path=example, env={})
    cfg_defaults, _ = load_config({}, config_path=None, env={})
    assert cfg_from_example == cfg_defaults


# ---------------------------------------------------------------------------
# request_interval field
# ---------------------------------------------------------------------------


def test_request_interval_default_is_0_8():
    """With no toml/env/cli, Config.request_interval defaults to 0.8."""
    cfg, _ = load_config({}, config_path=None, env={})
    assert cfg.request_interval == 0.8


def test_request_interval_from_toml(tmp_path: Path):
    """TOML value request_interval = 0.3 is loaded as float 0.3."""
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text("request_interval = 0.3\n", encoding="utf-8")
    cfg, _ = load_config({}, config_path=toml_file, env={})
    assert cfg.request_interval == 0.3


def test_request_interval_from_env_overrides_toml(tmp_path: Path):
    """TCG_REQUEST_INTERVAL env var overrides TOML value."""
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text("request_interval = 0.3\n", encoding="utf-8")
    cfg, _ = load_config({}, config_path=toml_file, env={"TCG_REQUEST_INTERVAL": "1.5"})
    assert cfg.request_interval == 1.5


def test_request_interval_invalid_env_raises():
    """TCG_REQUEST_INTERVAL=not_a_number raises ValueError mentioning the env var name."""
    with pytest.raises(ValueError, match="TCG_REQUEST_INTERVAL"):
        load_config({}, config_path=None, env={"TCG_REQUEST_INTERVAL": "not_a_number"})


def test_request_interval_int_in_toml_coerced_to_float(tmp_path: Path):
    """TOML int (request_interval = 1) is loaded as float 1.0."""
    toml_file = tmp_path / "tcg.toml"
    toml_file.write_text("request_interval = 1\n", encoding="utf-8")
    cfg, _ = load_config({}, config_path=toml_file, env={})
    assert cfg.request_interval == 1.0
    assert isinstance(cfg.request_interval, float)


# ---------------------------------------------------------------------------
# Source attribution
# ---------------------------------------------------------------------------


def test_load_config_returns_sources(tmp_path, monkeypatch):
    """load_config must return per-field source attribution."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tcg.toml").write_text('product_line = "TomlValue"\n')
    _config, sources = load_config(
        {"printings": ["CliValue"]},
        env={"TCG_REQUEST_INTERVAL": "0.3"},
    )
    assert sources["product_line"] == "toml"
    assert sources["printings"] == "cli"
    assert sources["request_interval"] == "env"
    assert sources["conditions"] == "default"  # not set anywhere


# ---------------------------------------------------------------------------
# write_parquet removed from Config
# ---------------------------------------------------------------------------


def test_write_parquet_no_longer_in_config():
    """Config dataclass no longer has a write_parquet field."""
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(Config)}
    assert "write_parquet" not in field_names, (
        "write_parquet field should have been removed from Config"
    )


def test_no_parquet_flag_in_cli(capsys):
    """--parquet flag must not appear in the CLI --help output."""
    import contextlib

    from scripts.fetch_deck import main

    with contextlib.suppress(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    assert "--parquet" not in out, f"--parquet should not be in --help output; got:\n{out}"

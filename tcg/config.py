"""Config system for the TCGplayer price-lookup CLI.

Priority order (highest to lowest):
  1. CLI overrides (dict passed by the caller)
  2. Environment variables (TCG_*)
  3. TOML config file
  4. Hardcoded defaults

Search order for TOML when config_path is None:
  1. ./tcg.toml  (project-local)
  2. ~/.config/tcg/config.toml  (user-global)
"""

from __future__ import annotations

import tomllib
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULTS: dict[str, Any] = {
    "product_line": None,
    "printings": ["Normal", "Foil"],
    "conditions": ["Near Mint"],
    "copy_to_clipboard": True,
    "write_parquet": False,
}

_KNOWN_KEYS = frozenset(_DEFAULTS.keys())

# Environment variable names → config field names
_ENV_MAP = {
    "TCG_PRODUCT_LINE": "product_line",
    "TCG_PRINTINGS": "printings",
    "TCG_CONDITIONS": "conditions",
    "TCG_COPY_TO_CLIPBOARD": "copy_to_clipboard",
    "TCG_WRITE_PARQUET": "write_parquet",
}


# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """Resolved configuration for a single CLI run."""

    product_line: str | None
    printings: list[str]
    conditions: list[str]
    copy_to_clipboard: bool
    write_parquet: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_bool(value: str) -> bool:
    """Parse a string env-var value into a bool.

    Accepts: 1/0, true/false, yes/no (case-insensitive).
    Raises ValueError for unrecognised values.
    """
    v = value.strip().lower()
    if v in ("1", "true", "yes"):
        return True
    if v in ("0", "false", "no"):
        return False
    raise ValueError(
        f"Cannot parse {value!r} as a boolean. Use 1/0, true/false, or yes/no."
    )


def _parse_comma_list(value: str) -> list[str]:
    return [s.strip() for s in value.split(",") if s.strip()]


def _load_toml(path: Path) -> dict[str, Any]:
    """Load and validate a TOML config file.

    Unknown keys emit a warnings.warn; malformed TOML raises ValueError
    with the path embedded in the message.
    """
    try:
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(
            f"Could not parse config file {path}: {exc}"
        ) from exc

    for key in raw:
        if key not in _KNOWN_KEYS:
            warnings.warn(
                f"Unknown key {key!r} in config file {path} — ignoring.",
                stacklevel=4,
            )

    return raw


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(
    cli_overrides: dict[str, Any],
    *,
    config_path: Path | None = None,
    env: dict[str, str] | None = None,
) -> Config:
    """Build a Config by merging defaults, TOML, env vars, and CLI overrides.

    Parameters
    ----------
    cli_overrides:
        Keys present here (non-None values) take highest precedence.
    config_path:
        Explicit path to a TOML file. If None, the function probes
        ``./tcg.toml`` then ``~/.config/tcg/config.toml``.
    env:
        Mapping of environment variables. Defaults to ``os.environ`` when
        None — pass an explicit dict in tests to avoid touching real env.
    """
    import os

    if env is None:
        env = dict(os.environ)

    # --- 1. Start with defaults ---
    merged: dict[str, Any] = dict(_DEFAULTS)

    # --- 2. Resolve TOML path ---
    toml_path: Path | None = config_path
    if toml_path is None:
        candidates = [
            Path("tcg.toml"),
            Path.home() / ".config" / "tcg" / "config.toml",
        ]
        for candidate in candidates:
            if candidate.exists():
                toml_path = candidate
                break

    # --- 3. Apply TOML values ---
    if toml_path is not None:
        raw_toml = _load_toml(toml_path)
        for key in _KNOWN_KEYS:
            if key in raw_toml:
                merged[key] = raw_toml[key]

    # --- 4. Apply env var overrides ---
    for env_key, field_name in _ENV_MAP.items():
        if env_key not in env:
            continue
        raw_val = env[env_key]
        if field_name in ("copy_to_clipboard", "write_parquet"):
            merged[field_name] = _parse_bool(raw_val)
        elif field_name in ("printings", "conditions"):
            merged[field_name] = _parse_comma_list(raw_val)
        else:
            merged[field_name] = raw_val

    # --- 5. Apply CLI overrides (skip None — means "not provided") ---
    for key, value in cli_overrides.items():
        if value is not None and key in _KNOWN_KEYS:
            merged[key] = value

    return Config(
        product_line=merged["product_line"],
        printings=list(merged["printings"]),
        conditions=list(merged["conditions"]),
        copy_to_clipboard=bool(merged["copy_to_clipboard"]),
        write_parquet=bool(merged["write_parquet"]),
    )

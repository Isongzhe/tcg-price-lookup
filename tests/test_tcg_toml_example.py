"""The shipped `tcg.toml.example` must document every config key.

Locks the contract that `tcg.toml.example` is the single visible
source of default values: README's "Defaults" table is a navigation
aid (no values), and `scripts/README.md` defers to this file. If a
new key is added to `_DEFAULTS` without a corresponding section in
the example, this test fails — pushing maintainers to keep the docs
in sync at the lowest cost.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts._config import _DEFAULTS

EXAMPLE_PATH = Path(__file__).parent.parent / "tcg.toml.example"


@pytest.fixture(scope="module")
def example_text() -> str:
    return EXAMPLE_PATH.read_text(encoding="utf-8")


def test_example_file_exists():
    assert EXAMPLE_PATH.exists(), f"{EXAMPLE_PATH} is missing"


@pytest.mark.parametrize("key", sorted(_DEFAULTS.keys()))
def test_every_default_key_documented(key: str, example_text: str):
    """Every key in _DEFAULTS must appear as a commented setting line in the
    example: `# <key> = ...`. This catches the "added to _DEFAULTS but
    forgot to update tcg.toml.example" mistake."""
    needle = f"# {key} ="
    assert needle in example_text, (
        f"tcg.toml.example is missing a commented setting line for {key!r}. "
        f"Expected a line like `# {key} = <value>`."
    )


@pytest.mark.parametrize("key", sorted(_DEFAULTS.keys()))
def test_every_default_value_in_example(key: str, example_text: str):
    """Each section in tcg.toml.example must mention its current default
    value (via a `# Default: ...` line). This nudges maintainers who
    change a value in _DEFAULTS to also update the example. Soft check:
    we just verify the section has SOMETHING after `# Default:`; we
    do not parse the value, since list/None/bool/string formatting
    varies."""
    # Find the section header for this key
    section_marker = f"# ── {key} "
    assert section_marker in example_text, (
        f"tcg.toml.example is missing a `# ── {key} ─...` section header"
    )
    # Look for `# Default:` somewhere after this section starts
    section_start = example_text.index(section_marker)
    # Find the next section header (or end of file) to bound the search
    next_section_idx = example_text.find("# ── ", section_start + len(section_marker))
    section_end = next_section_idx if next_section_idx != -1 else len(example_text)
    section = example_text[section_start:section_end]
    assert "# Default:" in section, (
        f"Section for {key!r} in tcg.toml.example is missing a `# Default: ...` line"
    )


def test_no_double_hash_lines(example_text: str):
    """Defensive: a line starting with `##` is misleading because TOML
    treats `#` and `##` identically. We only use single `#`."""
    for lineno, line in enumerate(example_text.splitlines(), start=1):
        assert not line.startswith("##"), (
            f"tcg.toml.example line {lineno} starts with `##` — use single `#` instead. "
            f"Line: {line!r}"
        )

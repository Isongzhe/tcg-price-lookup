"""Tests for tcg.product_lines — canonical lookup table and helpers."""

from __future__ import annotations

import pytest

from tcg.product_lines import PRODUCT_LINES, suggest, to_slug


def test_canonical_list_size():
    assert len(PRODUCT_LINES) >= 60


def test_known_lookups():
    assert to_slug("Grand Archive TCG") == "grand-archive"
    assert to_slug("Disney Lorcana") == "lorcana-tcg"
    assert to_slug("Magic: The Gathering") == "magic"
    assert to_slug("Dragon Ball Super: Masters") == "dragon-ball-super-ccg"
    assert to_slug("Flesh and Blood TCG") == "flesh-and-blood-tcg"
    assert to_slug("YuGiOh") == "yugioh"
    assert to_slug("Pokemon") == "pokemon"


def test_case_insensitive():
    assert to_slug("grand archive tcg") == "grand-archive"


def test_unknown_returns_none():
    assert to_slug("Bogus Game TCG") is None


def test_suggest_substring():
    results = suggest("lorcana")
    assert "Disney Lorcana" in results


def test_suggest_limit():
    results = suggest("tcg", limit=3)
    assert len(results) <= 3


def test_suggest_empty_for_no_match():
    assert suggest("zzzzz") == []

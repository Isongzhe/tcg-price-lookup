"""Tests for decks/sample_deck.txt."""

from __future__ import annotations

from pathlib import Path

import pytest

SAMPLE_DECK = Path("decks/sample_deck.txt")


def test_sample_deck_exists():
    assert SAMPLE_DECK.exists(), "decks/sample_deck.txt should exist"


def test_sample_deck_parses():
    from tcg.deck import parse_decklist

    text = SAMPLE_DECK.read_text(encoding="utf-8")
    entries = parse_decklist(text)
    assert len(entries) >= 5, f"Expected at least 5 entries, got {len(entries)}"


def test_sample_deck_ascii():
    """File content must be decodable as ASCII — no Chinese or emoji."""
    text = SAMPLE_DECK.read_bytes()
    try:
        text.decode("ascii")
    except UnicodeDecodeError as exc:
        pytest.fail(f"decks/sample_deck.txt is not pure ASCII: {exc}")


def test_sample_deck_has_sections():
    """At least one parsed entry should have a non-empty section (validates # Section syntax)."""
    from tcg.deck import parse_decklist

    text = SAMPLE_DECK.read_text(encoding="utf-8")
    entries = parse_decklist(text)
    sections = [e.section for e in entries if e.section]
    assert sections, "Expected at least one entry with a non-empty section"

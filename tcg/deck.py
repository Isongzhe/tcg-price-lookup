"""Parse decklist text into (section, quantity, card_name) entries.

Supported format:

    # Material Deck
    1 Alice, Golden Queen
    1 Alice, Whim's Monarch

    # Main Deck
    4 Some Card

    # Sideboard
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_LINE_RE = re.compile(r"^\s*(\d+)\s+(.+?)\s*$")


@dataclass(frozen=True, slots=True)
class DeckEntry:
    section: str
    quantity: int
    card_name: str


def parse_decklist(text: str) -> list[DeckEntry]:
    entries: list[DeckEntry] = []
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        qty = int(m.group(1))
        name = m.group(2).strip()
        if not name:
            continue
        entries.append(DeckEntry(section=section, quantity=qty, card_name=name))
    return entries

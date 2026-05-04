"""Canonical TCGplayer product-line catalog.

Source: aggregation query on
  POST https://mp-search-api.tcgplayer.com/v1/search/request
  payload: {"aggregations": ["productLineName"], "size": 0, ...}

:data:`PRODUCT_LINES` maps each display name to its URL slug. Use the slug
when sending ``productLineName`` filters to the TCGplayer search API; pass
the display name wherever the public API accepts a ``product_line`` argument.

Note:
    This snapshot was captured on 2026-05-04 (68 entries). To refresh it,
    run ``scripts/refresh_product_lines.py`` and paste the printed ``dict``
    literal back into :data:`PRODUCT_LINES`. Do not edit slug values by hand
    — they must match the TCGplayer API exactly.
"""

from __future__ import annotations

PRODUCT_LINES: dict[str, str] = {
    "Magic: The Gathering": "magic",
    "YuGiOh": "yugioh",
    "Pokemon": "pokemon",
    "Weiss Schwarz": "weiss-schwarz",
    "Pokemon Japan": "pokemon-japan",
    "Cardfight Vanguard": "cardfight-vanguard",
    "Force of Will": "force-of-will",
    "Dragon Ball Super: Masters": "dragon-ball-super-ccg",
    "Card Sleeves": "card-sleeves",
    "Flesh and Blood TCG": "flesh-and-blood-tcg",
    "Digimon Card Game": "digimon-card-game",
    "Heroclix": "heroclix",
    "UniVersus": "universus",
    "Future Card BuddyFight": "future-card-buddyfight",
    "Star Wars: Unlimited": "star-wars-unlimited",
    "One Piece Card Game": "one-piece-card-game",
    "Playmats": "playmats",
    "Deck Boxes": "deck-boxes",
    "Shadowverse: Evolve": "shadowverse-evolve",
    "Union Arena": "union-arena",
    "Final Fantasy TCG": "final-fantasy-tcg",
    "WoW": "wow",
    "Grand Archive TCG": "grand-archive",
    "WIXOSS": "wixoss",
    "Funko": "funko",
    "Dragon Ball Super: Fusion World": "dragon-ball-super-fusion-world",
    "MetaZoo": "metazoo",
    "Kryptik TCG": "kryptik-tcg",
    "Disney Lorcana": "lorcana-tcg",
    "Sorcery: Contested Realm": "sorcery-contested-realm",
    "Dice Masters": "dice-masters",
    "Elestrals": "elestrals",
    "Akora TCG": "akora",
    "Star Wars: Destiny": "star-wars-destiny",
    "Lightseekers TCG": "lightseekers-tcg",
    "Battle Spirits Saga": "battle-spirits-saga",
    "Books": "books",
    "Alpha Clash": "alpha-clash",
    "Dragon Ball Z TCG": "dragon-ball-z-tcg",
    "Bakugan TCG": "bakugan-tcg",
    "Gundam Card Game": "gundam-card-game",
    "hololive OFFICIAL CARD GAME": "hololive-official-card-game",
    "Storage Albums": "storage-albums",
    "D & D Miniatures": "d-and-d-miniatures",
    "Gate Ruler": "gate-ruler",
    "Warhammer Age of Sigmar Champions TCG": "warhammer-age-of-sigmar-champions-tcg",
    "Riftbound: League of Legends Trading Card Game": "riftbound-league-of-legends-trading-card-game",
    "Argent Saga TCG": "argent-saga-tcg",
    "Collectible Storage": "collectible-storage",
    "Life Counters": "life-counters",
    "The Caster Chronicles": "the-caster-chronicles",
    "MetaX TCG": "metax-tcg",
    "Transformers TCG": "transformers-tcg",
    "Exodus TCG": "exodus-tcg",
    "Godzilla Card Game": "godzilla-card-game",
    "Dragoborne": "dragoborne",
    "Munchkin CCG": "munchkin-ccg",
    "Bulk Lots": "bulk-lots",
    "Chrono Clash System": "chrono-clash-system",
    "Protective Pages": "protective-pages",
    "Zombie World Order TCG": "zombie-world-order-tcg",
    "My Little Pony CCG": "my-little-pony-ccg",
    "Supply Bundles": "supply-bundles",
    "KeyForge": "keyforge",
    "Alternate Souls": "alternate-souls",
    "Card Storage Tins": "card-storage-tins",
    "TCGplayer Supplies": "tcgplayer-supplies",
}


def to_slug(display_name: str) -> str | None:
    """Return the URL slug for a product-line display name.

    Matching is case-insensitive to absorb common typing variance
    (e.g. ``"grand archive tcg"`` matches ``"Grand Archive TCG"``).

    Args:
        display_name: Human-readable product line name. Should correspond to
            a key in :data:`PRODUCT_LINES`, but unknown names return ``None``
            rather than raising.

    Returns:
        The URL slug string (e.g. ``"grand-archive"``), or ``None`` if
        ``display_name`` is not found in :data:`PRODUCT_LINES`.

    Example:
        >>> to_slug("Grand Archive TCG")
        'grand-archive'
        >>> to_slug("unknown game") is None
        True
    """
    lowered = display_name.strip().lower()
    for name, slug in PRODUCT_LINES.items():
        if name.lower() == lowered:
            return slug
    return None


def suggest(query: str, limit: int = 3) -> list[str]:
    """Return up to `limit` display names whose lowercase form contains
    the query (substring match). Used for "did you mean?" hints."""
    q = query.strip().lower()
    if not q:
        return []
    return [name for name in PRODUCT_LINES if q in name.lower()][:limit]

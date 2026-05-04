"""TCGplayer price-lookup library and CLI.

Public API. Import directly from `tcg`:

    from tcg import TCGplayerClient, ProductDetails, PRODUCT_LINES
"""

__version__ = "1.0.0"

from tcg import endpoints
from tcg.client import TCGplayerClient, TCGplayerError
from tcg.decklist import DeckRow, VariantStats
from tcg.endpoints import Endpoint
from tcg.models import (
    AutocompleteHit,
    Listing,
    MarketPrice,
    ProductDetails,
    ProductSearchResult,
    Sale,
    Sku,
)
from tcg.output import print_tsv
from tcg.product_lines import PRODUCT_LINES, to_slug

__all__ = [  # noqa: RUF022 — ordering is part of the stable public-API contract
    "__version__",
    "TCGplayerClient",
    "TCGplayerError",
    "AutocompleteHit",
    "Listing",
    "MarketPrice",
    "ProductDetails",
    "ProductSearchResult",
    "Sale",
    "Sku",
    "PRODUCT_LINES",
    "to_slug",
    # Decklist orchestration (stable 1.0.0 contract)
    "DeckRow",
    "VariantStats",
    "print_tsv",
    # Endpoint catalog (stable 1.0.0 contract)
    "Endpoint",
    "endpoints",
]

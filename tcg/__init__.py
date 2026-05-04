"""TCGplayer price-lookup library and CLI.

Public API. Import directly from `tcg`:

    from tcg import TCGplayerClient, ProductDetails, PRODUCT_LINES
"""
__version__ = "1.0.0"

from tcg.client import TCGplayerClient, TCGplayerError
from tcg.models import (
    AutocompleteHit,
    Listing,
    MarketPrice,
    ProductDetails,
    ProductSearchResult,
    Sale,
    Sku,
)
from tcg.product_lines import PRODUCT_LINES, to_slug

__all__ = [
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
]

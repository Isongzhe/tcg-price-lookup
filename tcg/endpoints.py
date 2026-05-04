"""TCGplayer endpoint catalog.

Single source of truth for the URLs this library calls. Each entry is a
frozen ``Endpoint`` dataclass describing one HTTP endpoint, so callers can
inspect them, log them, or expose them via a CLI without re-reading
``client.py``.

The catalog is part of the 1.0.0 stability contract: existing entries'
``name``, ``method``, and ``url`` fields will not change within the 1.x
line. New endpoints may be appended.

Note:
    The ``mpfev`` query parameter on the search-API endpoints is a
    frontend build identifier. Bump :data:`MPFEV` when TCGplayer rolls a
    new build (you'll see 4xx responses pointing at the param).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HttpMethod = Literal["GET", "POST"]


@dataclass(frozen=True, slots=True)
class Endpoint:
    """One TCGplayer HTTP endpoint.

    Attributes:
        name: Stable identifier used in logs, error messages, and as a
            key when the catalog is rendered as a table.
        method: HTTP method.
        url: URL or URL template. Templates contain ``{product_id}`` (or
            similar) placeholders to be ``str.format``-substituted at
            call time.
        purpose: One-line human-readable description, suitable for the
            ``--list-endpoints`` CLI output.
        auth: Whether the endpoint depends on the warm-up cookie. All
            current endpoints except the homepage warm-up itself do.
    """

    name: str
    method: HttpMethod
    url: str
    purpose: str
    auth: bool = True


HOMEPAGE = Endpoint(
    name="homepage",
    method="GET",
    url="https://www.tcgplayer.com/",
    purpose="Warm-up: prime Cloudflare session cookies",
    auth=False,
)

AUTOCOMPLETE = Endpoint(
    name="autocomplete",
    method="GET",
    url="https://data.tcgplayer.com/autocomplete",
    purpose="Card-name suggestions; one row per product",
)

SEARCH = Endpoint(
    name="search",
    method="POST",
    url="https://mp-search-api.tcgplayer.com/v1/search/request",
    purpose="Product search + aggregations; enumerates reprints",
)

PRODUCT_DETAILS = Endpoint(
    name="product_details",
    method="GET",
    url="https://mp-search-api.tcgplayer.com/v2/product/{product_id}/details",
    purpose="Full product metadata + SKU list + product-level Market Price",
)

LATEST_SALES = Endpoint(
    name="latest_sales",
    method="POST",
    url="https://mpapi.tcgplayer.com/v2/product/{product_id}/latestsales",
    purpose="N most recent completed sales for one product",
)

LISTINGS = Endpoint(
    name="listings",
    method="POST",
    url="https://mp-search-api.tcgplayer.com/v1/product/{product_id}/listings",
    purpose="Active marketplace listings for one product",
)

MARKET_PRICE = Endpoint(
    name="market_price",
    method="POST",
    url="https://mpgateway.tcgplayer.com/v1/pricepoints/marketprice/skus/search",
    purpose="Per-SKU rolling 30-day Market Price",
)

ALL: tuple[Endpoint, ...] = (
    HOMEPAGE,
    AUTOCOMPLETE,
    SEARCH,
    PRODUCT_DETAILS,
    LATEST_SALES,
    LISTINGS,
    MARKET_PRICE,
)
"""Iteration order matches the order endpoints are typically called in a
fetch pipeline; relied on by ``--list-endpoints``."""

MPFEV = "5061"
"""Frontend build identifier sent as ``?mpfev=`` on search-API calls."""

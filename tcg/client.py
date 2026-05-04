from __future__ import annotations

import http
import time
import uuid
from typing import Any

from curl_cffi import requests

from tcg import endpoints
from tcg._fingerprint import build_headers
from tcg.models import (
    AutocompleteHit,
    Listing,
    MarketPrice,
    ProductDetails,
    ProductSearchResult,
    Sale,
)
from tcg.product_lines import to_slug

# TLS fingerprint and User-Agent must match. The Chrome major version
# below is the single source of truth — bumping it updates both the
# curl_cffi impersonate target and every Chrome-version-bearing header.
#
# To list available impersonate targets in your installed curl_cffi:
#     from curl_cffi.requests.impersonate import BrowserType
#     [v.value for v in BrowserType if "chrome" in v.value]
#
# Bump when:
#   - curl_cffi adds support for a newer Chrome major (and the current
#     target falls more than ~2 majors behind real Chrome), or
#   - TCGplayer / Cloudflare starts returning 403 on the current target.
_CHROME_VERSION = "146"
_IMPERSONATE = f"chrome{_CHROME_VERSION}"
_COMMON_HEADERS = build_headers(_CHROME_VERSION)

RETRYABLE_STATUS_CODES: frozenset[http.HTTPStatus] = frozenset(
    {
        http.HTTPStatus.BAD_REQUEST,  # 400 — TCGplayer cache miss / inter-service sync race; transient
        http.HTTPStatus.FORBIDDEN,  # 403 — Cloudflare bot challenge; warm-up may need refresh
        http.HTTPStatus.TOO_MANY_REQUESTS,  # 429 — rate limit; back off and retry
        http.HTTPStatus.INTERNAL_SERVER_ERROR,  # 500 — server fault, may recover
        http.HTTPStatus.BAD_GATEWAY,  # 502 — load balancer / upstream issue
        http.HTTPStatus.SERVICE_UNAVAILABLE,  # 503 — temporary unavailability
        http.HTTPStatus.GATEWAY_TIMEOUT,  # 504 — upstream slow; may pass on retry
    }
)


class TCGplayerError(Exception):
    """Raised on any non-2xx HTTP response from a TCGplayer API endpoint."""


class TCGplayerClient:
    """HTTP client for the unofficial TCGplayer marketplace API.

    Uses ``curl_cffi`` with Chrome TLS fingerprint impersonation to bypass
    bot-detection. A brief warm-up request to the TCGplayer homepage is made
    automatically before the first real API call so session cookies are
    established.

    Args:
        warm_up_delay: Seconds to sleep after the warm-up homepage request
            before issuing the first API call. Increase if you see 403s on
            the first request in a new session.

    Example:
        >>> client = TCGplayerClient()  # doctest: +SKIP
        >>> hits = client.autocomplete("Alice, Golden Queen")  # doctest: +SKIP
    """

    def __init__(self, warm_up_delay: float = 1.5) -> None:
        self.session = requests.Session()
        self.session_id = str(uuid.uuid4())
        self._warmed_up = False
        self._warm_up_delay = warm_up_delay

    def _warm_up(self) -> None:
        if self._warmed_up:
            return
        self.session.get(
            endpoints.HOMEPAGE.url,
            headers=_COMMON_HEADERS,
            impersonate=_IMPERSONATE,
        )
        time.sleep(self._warm_up_delay)
        self._warmed_up = True

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        retry: bool = True,
    ) -> Any:
        self._warm_up()
        resp = self.session.request(
            method,
            url,
            params=params,
            json=json,
            headers=_COMMON_HEADERS,
            impersonate=_IMPERSONATE,
        )
        if resp.status_code in RETRYABLE_STATUS_CODES and retry:
            self._warmed_up = False
            time.sleep(2.0)
            return self._request(method, url, params=params, json=json, retry=False)
        if resp.status_code >= 400:
            raise TCGplayerError(f"{method} {url} → {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def autocomplete(
        self,
        query: str,
        *,
        product_line: str | None = None,
    ) -> list[AutocompleteHit]:
        """Return autocomplete suggestions for a partial or full card name.

        Queries the TCGplayer autocomplete endpoint and filters out hits that
        have a ``None`` product ID (pre-release or unresolved aggregates) and
        duplicate aggregate rows. The result set is suitable for direct
        consumption or as input to :meth:`product_details`.

        Args:
            query: Partial or full card name to search for. Matching is
                handled server-side.
            product_line: Optional display name (e.g. ``"Grand Archive TCG"``)
                to restrict results to one product line. Filtering is done
                client-side after the API response. See :data:`tcg.PRODUCT_LINES`
                for valid values.

        Returns:
            Autocomplete hits with valid ``product_id`` values, deduplicated.
            Ordered by the server's relevance score descending.

        Raises:
            TCGplayerError: On a non-2xx HTTP response after retry.

        Example:
            >>> client = TCGplayerClient()  # doctest: +SKIP
            >>> hits = client.autocomplete(  # doctest: +SKIP
            ...     "Alice", product_line="Grand Archive TCG"
            ... )
            >>> hits[0].product_name  # doctest: +SKIP
            'Alice, Golden Queen'
        """
        data = self._request(
            endpoints.AUTOCOMPLETE.method,
            endpoints.AUTOCOMPLETE.url,
            params={
                "q": query,
                "session-id": self.session_id,
                "product-line-affinity": "All",
                "algorithm": "product_line_affinity",
            },
        )
        hits = [AutocompleteHit.from_api(p) for p in data.get("products", [])]
        # Drop hits that cannot be resolved to a concrete product. TCGplayer
        # sometimes returns suggestion rows with a null product-id (e.g. the
        # name exists across multiple products but is not disambiguated, or
        # an upcoming product that is not yet listed).
        hits = [h for h in hits if h.product_id is not None and not h.duplicate]
        if product_line:
            hits = [h for h in hits if h.product_line_name == product_line]
        return hits

    def search_products(
        self,
        card_name: str,
        *,
        product_line: str | None = None,
        size: int = 20,
    ) -> list[ProductSearchResult]:
        """Find every product matching an exact card name.

        Use this when enumerating reprints — the same card name across
        multiple sets returns one row per set. Unlike :meth:`autocomplete`,
        this uses the full search endpoint and never collapses reprints into
        a single aggregate row.

        An exact (non-fuzzy) match on ``productName`` is enforced client-side
        even though the server sometimes returns near-matches.

        Args:
            card_name: Exact card name to search for. Matching is
                case-insensitive.
            product_line: Optional display name (e.g. ``"Grand Archive TCG"``)
                to restrict results to one product line. See
                :data:`tcg.PRODUCT_LINES` for valid values.
            size: Maximum number of results to request from the server.

        Returns:
            Products in TCGplayer's relevance order. Sort on ``release_date``
            for chronological order.

        Raises:
            TCGplayerError: On a non-2xx HTTP response after retry.

        Example:
            >>> client = TCGplayerClient()  # doctest: +SKIP
            >>> results = client.search_products(  # doctest: +SKIP
            ...     "Alice, Golden Queen",
            ...     product_line="Grand Archive TCG",
            ... )
            >>> results[0].set_name  # doctest: +SKIP
            'Distorted Reflections'
        """
        filters_term: dict[str, list[str]] = {"productName": [card_name]}
        if product_line:
            # Use the canonical slug lookup. Fall back to the lowercased input
            # for unknown product lines — TCGplayer's substring filter may still
            # match even if the name is not in our catalog.
            slug = to_slug(product_line) or product_line.strip().lower()
            filters_term["productLineName"] = [slug]
        payload = {
            "algorithm": "revenue_exp_v2_1",
            "from": 0,
            "size": size,
            "filters": {"term": filters_term, "range": {}, "match": {}},
            "listingSearch": {"filters": {"term": {}, "range": {}, "exclude": {}}},
            "context": {"cart": {}, "shippingCountry": "US"},
            "settings": {"useFuzzySearch": False, "didYouMean": {}},
        }
        data = self._request(
            endpoints.SEARCH.method,
            endpoints.SEARCH.url,
            params={"mpfev": endpoints.MPFEV},
            json=payload,
        )
        if not isinstance(data, dict):
            return []
        results = data.get("results") or []
        if not results or not isinstance(results, list):
            return []
        items = results[0].get("results") if isinstance(results[0], dict) else None
        if not items:
            return []
        # Exact-name filter: the API may return fuzzy matches even with
        # useFuzzySearch=False.
        lowered = card_name.strip().lower()
        return [
            ProductSearchResult.from_api(d)
            for d in items
            if str(d.get("productName", "")).strip().lower() == lowered
        ]

    def product_details(self, product_id: int) -> ProductDetails | None:
        """Fetch authoritative metadata and market price for a single product.

        Calls ``/v2/product/{id}/details`` which returns the full SKU list,
        Normal NM market price, lowest price across all variants, and
        structured set / collector-number data.

        Args:
            product_id: TCGplayer numeric product ID (e.g. from an
                :class:`~tcg.AutocompleteHit` or
                :class:`~tcg.ProductSearchResult`).

        Returns:
            A :class:`~tcg.ProductDetails` instance, or ``None`` if the
            endpoint returns no ``productId`` in the response body.

        Raises:
            TCGplayerError: On a non-2xx HTTP response after retry.

        Example:
            >>> client = TCGplayerClient()  # doctest: +SKIP
            >>> details = client.product_details(558637)  # doctest: +SKIP
            >>> details.set_name  # doctest: +SKIP
            'Distorted Reflections'
        """
        data = self._request(
            endpoints.PRODUCT_DETAILS.method,
            endpoints.PRODUCT_DETAILS.url.format(product_id=product_id),
            params={"mpfev": endpoints.MPFEV},
        )
        if not isinstance(data, dict) or not data.get("productId"):
            return None
        return ProductDetails.from_api(data)

    def latest_sales(self, product_id: int, limit: int = 25) -> list[Sale]:
        """Return the most recent completed sales for a product.

        Calls ``/v2/product/{id}/latestsales``. Results are ordered newest
        first by ``order_date``. Use this for computing recent sale averages
        and spotting price momentum.

        Args:
            product_id: TCGplayer numeric product ID.
            limit: Maximum number of sale records to request.

        Returns:
            Sale records, newest first. May be fewer than ``limit`` if the
            product has low sales volume.

        Raises:
            TCGplayerError: On a non-2xx HTTP response after retry.

        Example:
            >>> client = TCGplayerClient()  # doctest: +SKIP
            >>> sales = client.latest_sales(558637, limit=10)  # doctest: +SKIP
            >>> sales[0].purchase_price  # USD  # doctest: +SKIP
            4.99
        """
        data = self._request(
            endpoints.LATEST_SALES.method,
            endpoints.LATEST_SALES.url.format(product_id=product_id),
            params={"mpfev": endpoints.MPFEV},
            json={"limit": limit},
        )
        raw = data.get("data", []) if isinstance(data, dict) else []
        return [Sale.from_api(product_id, s) for s in raw]

    def listings(self, product_id: int, limit: int = 50) -> list[Listing]:
        """Return active marketplace listings for a product, sorted by price.

        Calls ``/v1/product/{id}/listings`` sorted by ``price+shipping``
        ascending, so the cheapest offers appear first. Use this for
        computing current listing minimums and averages.

        Args:
            product_id: TCGplayer numeric product ID.
            limit: Maximum number of listing records to request.

        Returns:
            Active listings ordered by price + shipping ascending. Each
            listing corresponds to one seller's offer for a specific
            condition and printing.

        Raises:
            TCGplayerError: On a non-2xx HTTP response after retry.

        Example:
            >>> client = TCGplayerClient()  # doctest: +SKIP
            >>> listings = client.listings(558637, limit=20)  # doctest: +SKIP
            >>> listings[0].price  # cheapest listing in USD  # doctest: +SKIP
            3.50
        """
        data = self._request(
            endpoints.LISTINGS.method,
            endpoints.LISTINGS.url.format(product_id=product_id),
            params={"mpfev": endpoints.MPFEV},
            json={
                "filters": {"term": {}, "range": {}, "exclude": {}},
                "from": 0,
                "size": limit,
                "sort": {"field": "price+shipping", "order": "asc"},
                "context": {"shippingCountry": "US"},
                "aggregations": ["listingType"],
            },
        )
        raw: list[dict] = []
        if isinstance(data, dict):
            results = data.get("results") or []
            if results and isinstance(results, list):
                first = results[0]
                if isinstance(first, dict):
                    raw = first.get("results", []) or []
        return [Listing.from_api(product_id, r) for r in raw]

    def market_price(self, sku_ids: list[int]) -> list[MarketPrice]:
        """Fetch market price statistics for a batch of SKU IDs.

        Calls the pricepoints endpoint in a single POST with all requested
        SKUs. This is the most granular price source: each SKU encodes one
        (product × printing × condition × language) combination, so Normal
        NM and Foil NM have separate market prices.

        Args:
            sku_ids: List of TCGplayer SKU IDs to look up. An empty list
                returns immediately with no network call.

        Returns:
            One :class:`~tcg.MarketPrice` per SKU that had data. SKUs with
            no market data are omitted from the response. Order is not
            guaranteed to match the input list.

        Raises:
            TCGplayerError: On a non-2xx HTTP response after retry.

        Example:
            >>> client = TCGplayerClient()  # doctest: +SKIP
            >>> prices = client.market_price([12345678, 12345679])  # doctest: +SKIP
            >>> prices[0].market_price  # USD  # doctest: +SKIP
            5.25
        """
        if not sku_ids:
            return []
        data = self._request(
            endpoints.MARKET_PRICE.method,
            endpoints.MARKET_PRICE.url,
            params={"mpfev": endpoints.MPFEV},
            json={"skuIds": sku_ids},
        )
        raw: list[dict] = []
        if isinstance(data, list):
            raw = data
        elif isinstance(data, dict):
            raw = data.get("results") or data.get("data") or []
        return [MarketPrice.from_api(d) for d in raw]

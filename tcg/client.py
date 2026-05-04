from __future__ import annotations

import time
import uuid
from typing import Any

from curl_cffi import requests

from tcg.models import (
    AutocompleteHit,
    Listing,
    MarketPrice,
    ProductDetails,
    ProductSearchResult,
    Sale,
)
from tcg.product_lines import to_slug

_IMPERSONATE = "chrome120"

_COMMON_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
    "origin": "https://www.tcgplayer.com",
    "referer": "https://www.tcgplayer.com/",
    "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    ),
}


class TCGplayerError(Exception):
    pass


class TCGplayerClient:
    def __init__(self, warm_up_delay: float = 1.5) -> None:
        self.session = requests.Session()
        self.session_id = str(uuid.uuid4())
        self._warmed_up = False
        self._warm_up_delay = warm_up_delay

    def _warm_up(self) -> None:
        if self._warmed_up:
            return
        self.session.get(
            "https://www.tcgplayer.com/",
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
        if resp.status_code in (403, 429) and retry:
            self._warmed_up = False
            time.sleep(2.0)
            return self._request(method, url, params=params, json=json, retry=False)
        if resp.status_code >= 400:
            raise TCGplayerError(
                f"{method} {url} → {resp.status_code}: {resp.text[:200]}"
            )
        return resp.json()

    def autocomplete(
        self,
        query: str,
        *,
        product_line: str | None = None,
    ) -> list[AutocompleteHit]:
        """Search by card name. If product_line is given (e.g. 'Grand Archive TCG'), filter results locally."""
        data = self._request(
            "GET",
            "https://data.tcgplayer.com/autocomplete",
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

        Uses the frontend search endpoint at
        mp-search-api.tcgplayer.com/v1/search/request. Unlike autocomplete,
        this returns one row per product, which is how reprints surface:
        the same card name across multiple sets will produce multiple
        results.

        Results are returned in the order TCGplayer's relevance algorithm
        ranks them; callers that want release-date ordering should sort
        on the `release_date` field.
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
            "POST",
            "https://mp-search-api.tcgplayer.com/v1/search/request",
            params={"mpfev": "5061"},
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
        """/v2/product/{id}/details — authoritative Market Price + metadata."""
        data = self._request(
            "GET",
            f"https://mp-search-api.tcgplayer.com/v2/product/{product_id}/details",
            params={"mpfev": "5061"},
        )
        if not isinstance(data, dict) or not data.get("productId"):
            return None
        return ProductDetails.from_api(data)

    def latest_sales(self, product_id: int, limit: int = 25) -> list[Sale]:
        data = self._request(
            "POST",
            f"https://mpapi.tcgplayer.com/v2/product/{product_id}/latestsales",
            params={"mpfev": "5061"},
            json={"limit": limit},
        )
        raw = data.get("data", []) if isinstance(data, dict) else []
        return [Sale.from_api(product_id, s) for s in raw]

    def listings(self, product_id: int, limit: int = 50) -> list[Listing]:
        data = self._request(
            "POST",
            f"https://mp-search-api.tcgplayer.com/v1/product/{product_id}/listings",
            params={"mpfev": "5061"},
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
        if not sku_ids:
            return []
        data = self._request(
            "POST",
            "https://mpgateway.tcgplayer.com/v1/pricepoints/marketprice/skus/search",
            params={"mpfev": "5061"},
            json={"skuIds": sku_ids},
        )
        raw: list[dict] = []
        if isinstance(data, list):
            raw = data
        elif isinstance(data, dict):
            raw = data.get("results") or data.get("data") or []
        return [MarketPrice.from_api(d) for d in raw]

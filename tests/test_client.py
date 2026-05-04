"""Client tests with HTTP mocked via monkeypatching the session. We don't hit the
real API — that would be flaky and rude. The fixture response shape is taken from
a real devtools capture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tcg.client import TCGplayerClient
from tcg.models import AutocompleteHit

FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, status: int, payload: Any):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload) if payload is not None else ""

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls: list[dict] = []
        self.responses: dict[str, FakeResponse] = {}

    def set(self, url_contains: str, response: FakeResponse):
        self.responses[url_contains] = response

    def _match(self, url: str) -> FakeResponse:
        for key, resp in self.responses.items():
            if key in url:
                return resp
        return FakeResponse(200, {})

    def get(self, url, **kwargs):
        self.calls.append({"method": "GET", "url": url, **kwargs})
        return self._match(url)

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return self._match(url)


@pytest.fixture
def client(monkeypatch):
    c = TCGplayerClient(warm_up_delay=0)
    fake = FakeSession()
    c.session = fake
    return c, fake


def test_autocomplete_parses_fixture(client):
    c, fake = client
    payload = json.loads((FIXTURES / "autocomplete_alice_golde.json").read_text())
    fake.set("data.tcgplayer.com/autocomplete", FakeResponse(200, payload))

    hits = c.autocomplete("alice golden")

    assert len(hits) == 3
    assert all(isinstance(h, AutocompleteHit) for h in hits)
    assert hits[0].product_id == 644912


def test_autocomplete_filters_by_product_line(client):
    c, fake = client
    payload = json.loads((FIXTURES / "autocomplete_alice_golde.json").read_text())
    fake.set("data.tcgplayer.com/autocomplete", FakeResponse(200, payload))

    hits = c.autocomplete("alice golden", product_line="Grand Archive TCG")

    assert len(hits) == 2
    assert all(h.product_line_name == "Grand Archive TCG" for h in hits)


def test_warm_up_runs_once(client):
    c, fake = client
    fake.set("data.tcgplayer.com/autocomplete", FakeResponse(200, {"products": []}))

    c.autocomplete("a")
    c.autocomplete("b")

    warm_ups = [call for call in fake.calls if call["url"] == "https://www.tcgplayer.com/"]
    assert len(warm_ups) == 1


def test_latest_sales_uses_post(client):
    c, fake = client
    fake.set(
        "mpapi.tcgplayer.com/v2/product/644912/latestsales",
        FakeResponse(200, {"data": [{"purchasePrice": 10.0, "quantity": 1}]}),
    )

    sales = c.latest_sales(644912, limit=5)

    assert len(sales) == 1
    assert sales[0].purchase_price == 10.0
    post_calls = [c for c in fake.calls if c.get("method") == "POST"]
    assert any("latestsales" in c["url"] for c in post_calls)


def test_retry_on_403(client):
    c, fake = client

    call_count = {"n": 0}

    def flaky_request(method, url, **kwargs):
        fake.calls.append({"method": method, "url": url, **kwargs})
        call_count["n"] += 1
        if call_count["n"] == 1:
            return FakeResponse(403, "blocked")
        return FakeResponse(200, {"data": []})

    fake.request = flaky_request

    sales = c.latest_sales(644912)
    assert sales == []
    assert call_count["n"] == 2


def test_autocomplete_drops_null_product_id_hits(client):
    """Regression: TCGplayer occasionally returns autocomplete rows with
    product-id=null (e.g. 'Lost Providence'). These must be filtered out
    so downstream code never constructs .../product/None/details URLs."""
    c, fake = client
    payload = {
        "products": [
            {
                "duplicate": True,
                "product-id": None,
                "product-name": "Lost Providence",
                "product-line-name": "Grand Archive TCG",
                "set-name": "",
                "score": 3.5,
            },
            {
                "duplicate": False,
                "product-id": 644912,
                "product-name": "Alice, Golden Queen",
                "product-line-name": "Grand Archive TCG",
                "set-name": "Distorted Reflections",
                "score": 3.1,
            },
        ]
    }
    fake.set("data.tcgplayer.com/autocomplete", FakeResponse(200, payload))

    hits = c.autocomplete("any")

    assert len(hits) == 1
    assert hits[0].product_id == 644912
    assert all(h.product_id is not None for h in hits)


def test_search_products_returns_all_reprints(client):
    """search_products enumerates every product sharing a card name —
    the mechanism behind reprint expansion."""
    c, fake = client
    payload = {
        "errors": [],
        "results": [
            {
                "totalResults": 2,
                "results": [
                    {
                        "productId": 688306,
                        "productName": "Lost Providence",
                        "setName": "Radiant Origins",
                        "rarityName": "Ultra Rare",
                        "marketPrice": 45.49,
                        "productLineName": "Grand Archive TCG",
                        "customAttributes": {
                            "releaseDate": "2026-04-03T00:00:00Z",
                            "number": "409",
                        },
                    },
                    {
                        "productId": 665290,
                        "productName": "Lost Providence",
                        "setName": "Phantom Monarchs",
                        "rarityName": "Ultra Rare",
                        "marketPrice": 144.64,
                        "productLineName": "Grand Archive TCG",
                        "customAttributes": {
                            "releaseDate": "2025-12-05T00:00:00Z",
                            "number": "013",
                        },
                    },
                ],
            }
        ],
    }
    fake.set("mp-search-api.tcgplayer.com/v1/search/request", FakeResponse(200, payload))

    results = c.search_products("Lost Providence", product_line="Grand Archive TCG")

    assert len(results) == 2
    assert {r.product_id for r in results} == {688306, 665290}
    # Caller is responsible for sorting; verify raw data is intact.
    rdo = next(r for r in results if r.product_id == 688306)
    assert rdo.market_price == 45.49
    assert rdo.release_date == "2026-04-03T00:00:00Z"


def test_search_products_filters_fuzzy_name_mismatches(client):
    """TCGplayer's search can leak fuzzy matches into the result set even
    with useFuzzySearch=False. The client applies an exact-name filter
    to avoid polluting reprint expansion with unrelated products."""
    c, fake = client
    payload = {
        "errors": [],
        "results": [
            {
                "totalResults": 2,
                "results": [
                    {"productId": 1, "productName": "Lost Providence", "setName": "A"},
                    {"productId": 2, "productName": "Lost Providence Token", "setName": "B"},
                ],
            }
        ],
    }
    fake.set("mp-search-api.tcgplayer.com/v1/search/request", FakeResponse(200, payload))

    results = c.search_products("Lost Providence")

    assert len(results) == 1
    assert results[0].product_id == 1


def test_search_products_returns_empty_on_no_hits(client):
    c, fake = client
    payload = {"errors": [], "results": [{"totalResults": 0, "results": []}]}
    fake.set("mp-search-api.tcgplayer.com/v1/search/request", FakeResponse(200, payload))

    results = c.search_products("Nonexistent Card")
    assert results == []


def test_error_raises_after_retry(client):
    c, fake = client

    def always_403(method, url, **kwargs):
        fake.calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse(403, "blocked")

    fake.request = always_403

    from tcg.client import TCGplayerError

    with pytest.raises(TCGplayerError):
        c.latest_sales(644912)


# ---------------------------------------------------------------------------
# Regression: product-line slug lookup replaces broken heuristic
# ---------------------------------------------------------------------------


def _empty_search_payload():
    return {
        "errors": [],
        "results": [{"totalResults": 0, "results": []}],
    }


def _get_search_json(fake_calls):
    """Return the JSON body sent to the search endpoint."""
    for call in fake_calls:
        if "mp-search-api.tcgplayer.com/v1/search/request" in call.get("url", ""):
            return call.get("json", {})
    return {}


def test_search_products_disney_lorcana_slug(client):
    """Regression: 'Disney Lorcana' must map to 'lorcana-tcg', not 'disney lorcana'."""
    c, fake = client
    fake.set(
        "mp-search-api.tcgplayer.com/v1/search/request", FakeResponse(200, _empty_search_payload())
    )

    c.search_products("Some Card", product_line="Disney Lorcana")

    body = _get_search_json(fake.calls)
    assert body["filters"]["term"]["productLineName"] == ["lorcana-tcg"]


def test_search_products_magic_slug(client):
    """Regression: 'Magic: The Gathering' must map to 'magic'."""
    c, fake = client
    fake.set(
        "mp-search-api.tcgplayer.com/v1/search/request", FakeResponse(200, _empty_search_payload())
    )

    c.search_products("Some Card", product_line="Magic: The Gathering")

    body = _get_search_json(fake.calls)
    assert body["filters"]["term"]["productLineName"] == ["magic"]


# ---------------------------------------------------------------------------
# Regression: client dispatches to catalog URLs (Stage E)
# ---------------------------------------------------------------------------


def test_search_products_dispatches_to_catalog_url(client):
    """search_products must POST to endpoints.SEARCH.url (not a hardcoded string)."""
    from tcg import endpoints

    c, fake = client
    fake.set(
        "mp-search-api.tcgplayer.com/v1/search/request", FakeResponse(200, _empty_search_payload())
    )

    c.search_products("Some Card")

    search_calls = [call for call in fake.calls if "search/request" in call.get("url", "")]
    assert search_calls, "no call to the search endpoint found"
    assert search_calls[0]["url"] == endpoints.SEARCH.url


def test_latest_sales_dispatches_to_catalog_url(client):
    """latest_sales must POST to endpoints.LATEST_SALES.url with product_id substituted."""
    from tcg import endpoints

    c, fake = client
    product_id = 12345
    fake.set(
        f"mpapi.tcgplayer.com/v2/product/{product_id}/latestsales",
        FakeResponse(200, {"data": []}),
    )

    c.latest_sales(product_id)

    expected_url = endpoints.LATEST_SALES.url.format(product_id=product_id)
    sales_calls = [call for call in fake.calls if "latestsales" in call.get("url", "")]
    assert sales_calls, "no call to the latest_sales endpoint found"
    assert sales_calls[0]["url"] == expected_url


def test_product_details_dispatches_to_catalog_url(client):
    """product_details must GET endpoints.PRODUCT_DETAILS.url with product_id substituted."""
    from tcg import endpoints

    c, fake = client
    product_id = 558637
    fake.set(
        f"mp-search-api.tcgplayer.com/v2/product/{product_id}/details",
        FakeResponse(200, {"productId": product_id, "productName": "Test Card"}),
    )

    c.product_details(product_id)

    expected_url = endpoints.PRODUCT_DETAILS.url.format(product_id=product_id)
    detail_calls = [call for call in fake.calls if "/details" in call.get("url", "")]
    assert detail_calls, "no call to the product_details endpoint found"
    assert detail_calls[0]["url"] == expected_url


def test_tls_fingerprint_and_user_agent_chrome_versions_match():
    """Regression: the curl_cffi impersonate target and every Chrome
    version surfaced in HTTP headers must agree. A mismatch (e.g.
    chrome120 TLS handshake but Chrome 145 User-Agent) is a passive
    Cloudflare bot signal — see the comment block above _CHROME_VERSION
    in tcg/client.py."""
    import re

    from tcg.client import _CHROME_VERSION, _COMMON_HEADERS, _IMPERSONATE

    # Impersonate target carries the Chrome major
    assert f"chrome{_CHROME_VERSION}" == _IMPERSONATE

    # User-Agent must show the same Chrome major
    ua_match = re.search(r"Chrome/(\d+)", _COMMON_HEADERS["user-agent"])
    assert ua_match is not None, "User-Agent missing Chrome version"
    assert ua_match.group(1) == _CHROME_VERSION

    # sec-ch-ua client hint must show the same major in both Chrome and Chromium entries
    sec_ch_ua = _COMMON_HEADERS["sec-ch-ua"]
    chrome_versions = re.findall(r'"(?:Google Chrome|Chromium)";v="(\d+)"', sec_ch_ua)
    assert chrome_versions, "sec-ch-ua missing Chrome/Chromium version"
    assert all(v == _CHROME_VERSION for v in chrome_versions), (
        f"sec-ch-ua versions {chrome_versions} disagree with _CHROME_VERSION={_CHROME_VERSION}"
    )


def test_impersonate_target_is_supported_by_curl_cffi():
    """Regression: bumping _CHROME_VERSION to a value curl_cffi doesn't
    support would silently fall back at request time. Catch it at import."""
    from curl_cffi.requests.impersonate import BrowserType

    from tcg.client import _IMPERSONATE

    available = {v.value for v in BrowserType}
    assert _IMPERSONATE in available, (
        f"{_IMPERSONATE} not in installed curl_cffi's BrowserType enum. "
        f"Run `[v.value for v in BrowserType]` to see options."
    )

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


def test_error_raises_after_retry(client):
    c, fake = client

    def always_403(method, url, **kwargs):
        fake.calls.append({"method": method, "url": url, **kwargs})
        return FakeResponse(403, "blocked")

    fake.request = always_403

    from tcg.client import TCGplayerError

    with pytest.raises(TCGplayerError):
        c.latest_sales(644912)

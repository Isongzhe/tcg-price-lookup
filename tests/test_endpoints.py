"""Tests for the TCGplayer endpoint catalog (tcg/endpoints.py)."""

from __future__ import annotations

import dataclasses

import pytest

import tcg
from tcg import endpoints

# ---------------------------------------------------------------------------
# Catalog structure
# ---------------------------------------------------------------------------


def test_all_contains_seven():
    assert len(endpoints.ALL) == 7


def test_names_unique():
    names = [e.name for e in endpoints.ALL]
    assert len(set(names)) == 7


def test_urls_https():
    for e in endpoints.ALL:
        assert e.url.startswith("https://"), f"{e.name} URL does not start with https://"


@pytest.mark.parametrize(
    "endpoint",
    [endpoints.PRODUCT_DETAILS, endpoints.LATEST_SALES, endpoints.LISTINGS],
    ids=["product_details", "latest_sales", "listings"],
)
def test_path_templated_endpoints_have_product_id_placeholder(endpoint):
    assert "{product_id}" in endpoint.url, (
        f"{endpoint.name}.url should contain '{{product_id}}' placeholder"
    )


@pytest.mark.parametrize(
    "endpoint",
    [endpoints.HOMEPAGE, endpoints.AUTOCOMPLETE, endpoints.SEARCH, endpoints.MARKET_PRICE],
    ids=["homepage", "autocomplete", "search", "market_price"],
)
def test_non_templated_endpoints_have_no_braces(endpoint):
    assert "{" not in endpoint.url, f"{endpoint.name}.url should not contain template braces"


# ---------------------------------------------------------------------------
# Auth flags
# ---------------------------------------------------------------------------


def test_homepage_does_not_require_auth():
    assert endpoints.HOMEPAGE.auth is False


def test_others_require_auth():
    for e in endpoints.ALL:
        if e.name != "homepage":
            assert e.auth is True, f"{e.name}.auth should be True"


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


def test_endpoint_is_frozen():
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        endpoints.HOMEPAGE.name = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MPFEV
# ---------------------------------------------------------------------------


def test_mpfev_is_string():
    assert isinstance(endpoints.MPFEV, str)
    assert len(endpoints.MPFEV) > 0


# ---------------------------------------------------------------------------
# HTTP methods
# ---------------------------------------------------------------------------


def test_method_is_get_or_post():
    for e in endpoints.ALL:
        assert e.method in {"GET", "POST"}, f"{e.name}.method is {e.method!r}"


# ---------------------------------------------------------------------------
# Public API surface: Endpoint type exported from tcg
# ---------------------------------------------------------------------------


def test_endpoint_type_in_tcg_all():
    assert "Endpoint" in tcg.__all__

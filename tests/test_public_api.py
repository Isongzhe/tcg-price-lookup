"""Regression tests that lock down the public API surface of the tcg package.

These tests prevent accidental re-export of CLI-private modules and enforce
the minimum set of symbols that must remain in tcg.__all__.
"""

from __future__ import annotations

import importlib
import typing

import pytest

import tcg


class TestNoCLIModulesInTcg:
    def test_no_clipboard_in_tcg_init(self):
        assert "clipboard" not in dir(tcg)
        assert "clipboard" not in tcg.__all__

    def test_no_config_in_tcg_init(self):
        assert "config" not in dir(tcg)
        assert "config" not in tcg.__all__


class TestCannotImportCLIModulesFromTcg:
    def test_cannot_import_clipboard_from_tcg(self):
        with pytest.raises((ImportError, ModuleNotFoundError)):
            importlib.import_module("tcg.clipboard")

    def test_cannot_import_config_from_tcg(self):
        with pytest.raises((ImportError, ModuleNotFoundError)):
            importlib.import_module("tcg.config")


class TestAllPublicSymbolsImportable:
    def test_all_public_symbols_resolve(self):
        for name in tcg.__all__:
            assert hasattr(tcg, name), (
                f"tcg.__all__ contains {name!r} but getattr(tcg, {name!r}) fails"
            )


class TestPublicAPIMinimumSet:
    _REQUIRED: typing.ClassVar[set[str]] = {
        "TCGplayerClient",
        "TCGplayerError",
        "ProductDetails",
        "Sale",
        "Listing",
        "MarketPrice",
        "Sku",
        "AutocompleteHit",
        "ProductSearchResult",
        "PRODUCT_LINES",
        "to_slug",
        "Endpoint",
        "endpoints",
        "DeckRow",
        "VariantStats",
        "print_tsv",
    }

    def test_minimum_set_present_in_all(self):
        missing = self._REQUIRED - set(tcg.__all__)
        assert not missing, f"Missing from tcg.__all__: {sorted(missing)}"

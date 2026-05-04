"""Regression tests for scripts/refresh_product_lines.py.

Covers the JSON-path bug where the original code read
data["aggregations"]["productLineName"] instead of the correct
data["results"][0]["aggregations"]["productLineName"], causing a silent
empty PRODUCT_LINES = {} output.
"""

from __future__ import annotations

from unittest.mock import patch

from scripts.refresh_product_lines import main
from tcg.client import TCGplayerClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REALISTIC_RESPONSE = {
    "errors": [],
    "results": [
        {
            "aggregations": {
                "productLineName": [
                    {"urlValue": "magic", "value": "Magic: The Gathering", "count": 100.0},
                    {"urlValue": "yugioh", "value": "YuGiOh", "count": 50.0},
                ]
            }
        }
    ],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_happy_path_prints_correct_format(capsys):
    with patch.object(TCGplayerClient, "_request", return_value=_REALISTIC_RESPONSE):
        rc = main()

    captured = capsys.readouterr()
    assert rc == 0
    assert "PRODUCT_LINES: dict[str, str] = {" in captured.out
    assert "'Magic: The Gathering': 'magic'," in captured.out
    assert "'YuGiOh': 'yugioh'," in captured.out
    assert "}" in captured.out


def test_skips_entries_with_null_urlvalue(capsys):
    response = {
        "errors": [],
        "results": [
            {
                "aggregations": {
                    "productLineName": [
                        {"urlValue": "magic", "value": "Magic: The Gathering", "count": 100.0},
                        {"urlValue": None, "value": "TCGplayer", "count": 999.0},
                    ]
                }
            }
        ],
    }
    with patch.object(TCGplayerClient, "_request", return_value=response):
        rc = main()

    captured = capsys.readouterr()
    assert rc == 0
    assert "'Magic: The Gathering': 'magic'," in captured.out
    assert "TCGplayer" not in captured.out


def test_empty_results_returns_1_and_warns(capsys):
    response = {"errors": [], "results": []}
    with patch.object(TCGplayerClient, "_request", return_value=response):
        rc = main()

    captured = capsys.readouterr()
    assert rc == 1
    # stderr must mention schema change or results problem
    assert any(word in captured.err for word in ("schema", "results", "result"))
    # stdout must NOT contain a bare '{}' that someone could accidentally paste
    assert "{}" not in captured.out


def test_old_path_bug_regression(capsys):
    """If the fix is reverted (reading data["aggregations"] instead of
    data["results"][0]["aggregations"]), _request returns a dict whose top-level
    key is "aggregations", not "results".  The fixed code checks for a "results"
    key and returns 1 when it is absent — so this test will fail (return value
    would be 0) if someone reverts to the old path.
    """
    old_buggy_shape = {
        "aggregations": {
            "productLineName": [
                {"urlValue": "magic", "value": "Magic: The Gathering", "count": 100.0},
            ]
        }
    }
    with patch.object(TCGplayerClient, "_request", return_value=old_buggy_shape):
        rc = main()

    assert rc == 1, (
        "Script should return 1 for the old (incorrect) response shape; "
        "if it returns 0 the JSON-path fix has been reverted."
    )

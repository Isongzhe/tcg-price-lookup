"""Unit tests for tcg._fingerprint.build_headers — OS-aware header generation."""

from __future__ import annotations

import re

import pytest

from tcg._fingerprint import build_headers

REQUIRED_KEYS = {
    "accept",
    "accept-language",
    "origin",
    "referer",
    "sec-ch-ua",
    "sec-ch-ua-mobile",
    "sec-ch-ua-platform",
    "user-agent",
}


# ---------------------------------------------------------------------------
# Parametrized OS-variant checks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "platform_system, ua_contains, platform_value",
    [
        ("Darwin", ["Macintosh", "Mac OS X"], '"macOS"'),
        ("Windows", ["Windows NT 10.0"], '"Windows"'),
        ("Linux", ["X11; Linux x86_64"], '"Linux"'),
        ("FreeBSD", ["X11; Linux x86_64"], '"Linux"'),  # unknown → Linux fallback
    ],
)
def test_os_variants(platform_system, ua_contains, platform_value):
    headers = build_headers("146", platform_system=platform_system)
    ua = headers["user-agent"]
    for fragment in ua_contains:
        assert fragment in ua, f"Expected '{fragment}' in User-Agent for {platform_system!r}"
    assert headers["sec-ch-ua-platform"] == platform_value


# ---------------------------------------------------------------------------
# Individual named tests (per spec)
# ---------------------------------------------------------------------------


def test_macos_headers():
    headers = build_headers("146", platform_system="Darwin")
    assert "Macintosh" in headers["user-agent"]
    assert "Mac OS X" in headers["user-agent"]
    assert headers["sec-ch-ua-platform"] == '"macOS"'


def test_windows_headers():
    headers = build_headers("146", platform_system="Windows")
    assert "Windows NT 10.0" in headers["user-agent"]
    assert headers["sec-ch-ua-platform"] == '"Windows"'


def test_linux_headers():
    headers = build_headers("146", platform_system="Linux")
    assert "X11; Linux x86_64" in headers["user-agent"]
    assert headers["sec-ch-ua-platform"] == '"Linux"'


def test_unknown_os_falls_back_to_linux():
    for unknown in ("FreeBSD", "AIX", "foo"):
        headers = build_headers("146", platform_system=unknown)
        assert "X11; Linux x86_64" in headers["user-agent"]
        assert headers["sec-ch-ua-platform"] == '"Linux"'


def test_chrome_version_substituted_in_user_agent():
    ua = build_headers("99", platform_system="Linux")["user-agent"]
    assert "Chrome/99.0.0.0" in ua


def test_chrome_version_substituted_in_sec_ch_ua():
    sec_ch_ua = build_headers("99", platform_system="Linux")["sec-ch-ua"]
    assert '"Google Chrome";v="99"' in sec_ch_ua
    assert '"Chromium";v="99"' in sec_ch_ua


def test_default_uses_real_platform():
    headers = build_headers("146")
    assert headers, "build_headers with no override should return a non-empty dict"
    for key in REQUIRED_KEYS:
        assert key in headers, f"Missing required key: {key!r}"


def test_required_keys_present():
    for platform_system in ("Darwin", "Windows", "Linux", "FreeBSD"):
        headers = build_headers("146", platform_system=platform_system)
        for key in REQUIRED_KEYS:
            assert key in headers, f"Missing key {key!r} for platform {platform_system!r}"


def test_sec_ch_ua_platform_quoted():
    for platform_system in ("Darwin", "Windows", "Linux", "FreeBSD"):
        value = build_headers("146", platform_system=platform_system)["sec-ch-ua-platform"]
        assert value.startswith('"') and value.endswith('"'), (
            f"sec-ch-ua-platform {value!r} for {platform_system!r} must be "
            "wrapped in double-quotes (Chrome client-hint format)"
        )


def test_chrome_versions_match_across_headers():
    headers = build_headers("146", platform_system="Linux")

    ua_match = re.search(r"Chrome/(\d+)", headers["user-agent"])
    assert ua_match is not None, "User-Agent missing Chrome version"
    assert ua_match.group(1) == "146"

    versions_in_sec_ch_ua = re.findall(
        r'"(?:Google Chrome|Chromium)";v="(\d+)"', headers["sec-ch-ua"]
    )
    assert versions_in_sec_ch_ua, "sec-ch-ua missing Chrome/Chromium version entries"
    assert all(v == "146" for v in versions_in_sec_ch_ua), (
        f"sec-ch-ua versions {versions_in_sec_ch_ua} don't match expected '146'"
    )

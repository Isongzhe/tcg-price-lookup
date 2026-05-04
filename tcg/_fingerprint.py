"""Internal module: OS-aware browser fingerprint header builder.

Not part of the public API — do not add to ``tcg.__init__.__all__``.
"""

from __future__ import annotations

import platform


def build_headers(chrome_version: str, *, platform_system: str | None = None) -> dict[str, str]:
    """Build TCGplayer-compatible request headers matching the host OS.

    Args:
        chrome_version: Chrome major version, e.g. "146". Must match the
            curl_cffi impersonate target used at request time.
        platform_system: Override the result of ``platform.system()``.
            Used by tests; production callers should leave it ``None``.

    Returns:
        A header dict suitable for use with curl_cffi requests. The
        ``User-Agent`` and ``sec-ch-ua-platform`` values reflect the
        host OS; everything else is OS-agnostic.
    """
    system = platform_system if platform_system is not None else platform.system()

    if system == "Darwin":
        user_agent = (
            f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{chrome_version}.0.0.0 Safari/537.36"
        )
        ch_platform = '"macOS"'
    elif system == "Windows":
        user_agent = (
            f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{chrome_version}.0.0.0 Safari/537.36"
        )
        ch_platform = '"Windows"'
    else:
        # Linux, FreeBSD, AIX, unknown — fall back to Linux (most generic)
        user_agent = (
            f"Mozilla/5.0 (X11; Linux x86_64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{chrome_version}.0.0.0 Safari/537.36"
        )
        ch_platform = '"Linux"'

    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "origin": "https://www.tcgplayer.com",
        "referer": "https://www.tcgplayer.com/",
        "sec-ch-ua": (
            f'"Not:A-Brand";v="99", '
            f'"Google Chrome";v="{chrome_version}", '
            f'"Chromium";v="{chrome_version}"'
        ),
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": ch_platform,
        "user-agent": user_agent,
    }

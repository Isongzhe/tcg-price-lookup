"""CLI-internal clipboard helper for scripts/.

Provides platform-aware clipboard detection and a simple write function.
Detection is intentionally cheap — uses only shutil.which and sys.platform,
so it can be called once per CLI run without spawning any processes.

This module is private to the CLI (leading-underscore name). It is NOT part
of the public tcg library API and should not be imported from outside scripts/.
"""

from __future__ import annotations

import shutil
import subprocess
import sys


def detect_clipboard_cmd() -> list[str] | None:
    """Return the clipboard command appropriate for the current platform.

    Returns a list suitable for passing to subprocess.run(), or None when
    no clipboard utility is found.

    Platform dispatch:
      - macOS  → pbcopy
      - Windows → clip
      - Linux  → wl-copy (Wayland), then xclip, then xsel
    """
    platform = sys.platform

    if platform == "darwin":
        if shutil.which("pbcopy"):
            return ["pbcopy"]
        return None

    if platform == "win32":
        if shutil.which("clip"):
            return ["clip"]
        return None

    # Linux (and any other POSIX-like system)
    if shutil.which("wl-copy"):
        return ["wl-copy"]
    if shutil.which("xclip"):
        return ["xclip", "-selection", "clipboard"]
    if shutil.which("xsel"):
        return ["xsel", "--clipboard", "--input"]
    return None


def write_to_clipboard(text: str) -> bool:
    """Write *text* to the system clipboard.

    Returns True on success, False if no clipboard command is available or
    the command exits with a non-zero status. Never raises.
    """
    cmd = detect_clipboard_cmd()
    if cmd is None:
        return False

    try:
        subprocess.run(cmd, input=text, text=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

"""Tests for scripts._clipboard — platform-aware clipboard detection and writing."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from scripts._clipboard import detect_clipboard_cmd, write_to_clipboard

# ---------------------------------------------------------------------------
# detect_clipboard_cmd — platform dispatch
# ---------------------------------------------------------------------------


def test_macos_pbcopy(monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    with patch("shutil.which", return_value="/usr/bin/pbcopy"):
        result = detect_clipboard_cmd()
    assert result == ["pbcopy"]


def test_windows_clip(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    with patch("shutil.which", return_value="C:\\Windows\\System32\\clip.exe"):
        result = detect_clipboard_cmd()
    assert result == ["clip"]


def test_linux_wl_copy(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")

    def fake_which(cmd):
        return "/usr/bin/wl-copy" if cmd == "wl-copy" else None

    with patch("shutil.which", side_effect=fake_which):
        result = detect_clipboard_cmd()
    assert result == ["wl-copy"]


def test_linux_xclip_fallback(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")

    def fake_which(cmd):
        if cmd == "wl-copy":
            return None
        if cmd == "xclip":
            return "/usr/bin/xclip"
        return None

    with patch("shutil.which", side_effect=fake_which):
        result = detect_clipboard_cmd()
    assert result == ["xclip", "-selection", "clipboard"]


def test_linux_xsel_fallback(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")

    def fake_which(cmd):
        if cmd in ("wl-copy", "xclip"):
            return None
        if cmd == "xsel":
            return "/usr/bin/xsel"
        return None

    with patch("shutil.which", side_effect=fake_which):
        result = detect_clipboard_cmd()
    assert result == ["xsel", "--clipboard", "--input"]


def test_linux_nothing(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    with patch("shutil.which", return_value=None):
        result = detect_clipboard_cmd()
    assert result is None


# ---------------------------------------------------------------------------
# write_to_clipboard
# ---------------------------------------------------------------------------


def test_write_to_clipboard_no_command_returns_false(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    with patch("shutil.which", return_value=None):
        result = write_to_clipboard("hello")
    assert result is False


def test_write_to_clipboard_calls_subprocess(monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")

    mock_run = MagicMock()
    with (
        patch("shutil.which", return_value="/usr/bin/pbcopy"),
        patch("subprocess.run", mock_run),
    ):
        result = write_to_clipboard("some tsv text")

    assert result is True
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    # First positional arg should be the command list
    cmd = call_args[0][0]
    assert cmd == ["pbcopy"]
    # Text should be passed via stdin
    kwargs = call_args[1]
    assert kwargs.get("input") == "some tsv text"
    assert kwargs.get("text") is True


def test_write_to_clipboard_subprocess_error_returns_false(monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")

    with (
        patch("shutil.which", return_value="/usr/bin/pbcopy"),
        patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "pbcopy"),
        ),
    ):
        result = write_to_clipboard("text")

    assert result is False

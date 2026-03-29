"""force_foreground 行为单测（可移植部分 + Windows 下 monkeypatch get_foreground_hwnd）。"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

import controllers.win32_win as win32_win


@pytest.fixture(autouse=True)
def _no_sleep_in_win32_fg(monkeypatch):
    """避免标题栏/轮询路径在单测里真实等待。"""
    monkeypatch.setattr(win32_win.time, "sleep", lambda *_a, **_k: None)


def test_force_foreground_not_windows(monkeypatch):
    monkeypatch.setattr(win32_win.sys, "platform", "linux")
    out = win32_win.force_foreground(1)
    assert out["ok"] is False
    assert out["reason"] == "not_windows"


def test_force_foreground_invalid_hwnd_zero():
    if sys.platform != "win32":
        pytest.skip("Windows only")
    out = win32_win.force_foreground(0)
    assert out["ok"] is False
    assert out["reason"] == "invalid_hwnd"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_force_foreground_invalid_or_dead_hwnd():
    out = win32_win.force_foreground(999_999_999)
    assert out["ok"] is False
    assert out["reason"] == "invalid_or_dead"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_force_foreground_relaxed_visible_not_foreground(monkeypatch):
    """前台始终不是目标，但 IsWindowVisible 为真 → relaxed 放行。"""
    hwnd = 42

    monkeypatch.setattr(win32_win, "get_foreground_hwnd", lambda: 0)
    monkeypatch.setattr(win32_win, "is_window_visible", lambda h: h == hwnd)

    mock_user32 = MagicMock()
    mock_user32.IsWindow.return_value = True
    mock_user32.IsIconic.return_value = False

    with patch("ctypes.windll.user32", mock_user32):
        with patch("ctypes.windll", MagicMock(user32=mock_user32)):
            import ctypes

            ctypes.windll.user32 = mock_user32  # type: ignore[attr-defined]
            out = win32_win.force_foreground(hwnd, wait_ms=50, policy="relaxed", use_titlebar_click=False)

    assert out["ok"] is True
    assert out["reason"] == "visible_not_foreground"
    assert out["foreground_verified"] is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_force_foreground_titlebar_click_then_foreground_ok(monkeypatch):
    """首轮前台校验失败 → 标题栏 click 后 GetForegroundWindow 命中目标 → ok。"""
    hwnd = 100
    fg_seq = [0, hwnd]

    def fake_fg() -> int:
        return fg_seq.pop(0) if fg_seq else 0

    monkeypatch.setattr(win32_win, "get_foreground_hwnd", fake_fg)
    monkeypatch.setattr(
        win32_win,
        "get_window_rect",
        lambda h: (
            {"left": 10, "top": 20, "width": 200, "height": 300, "area": 60000}
            if h == hwnd
            else None
        ),
    )

    fake_pa = MagicMock()

    class _ClickMod:
        @staticmethod
        def click(x, y):
            fake_pa.click(x, y)

    monkeypatch.setitem(sys.modules, "pyautogui", _ClickMod)

    mock_user32 = MagicMock()
    mock_user32.IsWindow.return_value = True
    mock_user32.IsIconic.return_value = False

    import ctypes

    with patch("ctypes.windll.user32", mock_user32):
        with patch("ctypes.windll", MagicMock(user32=mock_user32)):
            ctypes.windll.user32 = mock_user32  # type: ignore[attr-defined]
            out = win32_win.force_foreground(hwnd, wait_ms=500, policy="strict", use_titlebar_click=True)

    assert out["ok"] is True
    assert out.get("foreground_verified") is True
    fake_pa.click.assert_called_once_with(110, 30)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_force_foreground_strict_fails_when_not_visible(monkeypatch):
    hwnd = 43
    monkeypatch.setattr(win32_win, "get_foreground_hwnd", lambda: 0)
    monkeypatch.setattr(win32_win, "is_window_visible", lambda h: False)

    mock_user32 = MagicMock()
    mock_user32.IsWindow.return_value = True
    mock_user32.IsIconic.return_value = False

    import ctypes

    ctypes.windll.user32 = mock_user32  # type: ignore[attr-defined]
    with patch("ctypes.windll.user32", mock_user32):
        out = win32_win.force_foreground(hwnd, wait_ms=50, policy="strict", use_titlebar_click=False)

    assert out["ok"] is False
    assert out["reason"] == "foreground_timeout"

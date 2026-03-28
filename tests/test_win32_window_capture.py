from __future__ import annotations

import sys

import pytest

from errors import ApiError


def test_configure_dpi_awareness_not_windows() -> None:
    if sys.platform == "win32":
        pytest.skip("non-Windows assertion")
    from controllers.win32_window_capture import configure_process_dpi_awareness

    r = configure_process_dpi_awareness()
    assert r["ok"] is False
    assert r["reason"] == "not_windows"


@pytest.mark.skipif(sys.platform != "win32", reason="PrintWindow 仅 Windows 可用")
def test_capture_printwindow_rejects_zero_hwnd() -> None:
    from controllers.win32_window_capture import capture_window_printwindow

    with pytest.raises(ApiError) as exc:
        capture_window_printwindow(0, client_only=True)
    assert exc.value.code == "print_window_failed"
    assert "无效" in exc.value.message or "hwnd" in (exc.value.details or {})


@pytest.mark.skipif(sys.platform != "win32", reason="PrintWindow 仅 Windows 可用")
def test_capture_printwindow_unsupported_raises_when_platform_patched(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    from controllers.win32_window_capture import capture_window_printwindow

    with pytest.raises(ApiError) as exc:
        capture_window_printwindow(1, client_only=True)
    assert exc.value.code == "print_window_unsupported"

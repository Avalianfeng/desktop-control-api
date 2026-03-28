from __future__ import annotations

import types

import pytest

from controllers.screenshot import ScreenshotController
from errors import ApiError


def test_screenshot_capture_error_details(monkeypatch: pytest.MonkeyPatch) -> None:
    class _MSS:
        def __init__(self):
            self.monitors = [{"left": 0, "top": 0, "width": 1, "height": 1}, {"left": 0, "top": 0, "width": 1, "height": 1}]

        def grab(self, monitor):
            raise RuntimeError("grab_failed")

    monkeypatch.setattr("controllers.screenshot.mss.mss", lambda: _MSS())

    ctrl = ScreenshotController()
    with pytest.raises(ApiError) as ei:
        ctrl.capture(region=None)

    err = ei.value
    assert err.code == "screenshot_failed"
    assert isinstance(err.details, dict)
    assert err.details.get("error_type")
    assert err.details.get("error_message")
    assert "monitor_index" in err.details
    assert "monitor_rect" in err.details


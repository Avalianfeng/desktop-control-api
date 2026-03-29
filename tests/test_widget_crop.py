from __future__ import annotations

import pytest

import server as server_module
import services.widget_cropper as widget_cropper_module
from errors import ApiError
from semantic.widget_types import Widget, WidgetText
from models.ui_dom import UIBounds


@pytest.fixture
def api_headers():
    return {"X-API-Key": server_module.VALID_API_KEYS[0]}


def _fake_widget(wid: str = "w_test") -> Widget:
    return Widget(
        id=wid,
        type="b",
        role="button",
        text=WidgetText(value="OK", source="uia", confidence=1.0),
        text_legacy="OK",
        normalized="ok",
        bounds=UIBounds(x=100, y=200, width=80, height=32),
        uia_path="p",
    )


def test_screenshot_widget_passes_bounds_to_capture_region(client, api_headers, monkeypatch):
    captured: dict = {}

    def fake_resolve_widget(**kwargs):
        return (_fake_widget(), {"title": "T", "hwnd": 1}, True, "id", None)

    def fake_capture_region(x, y, width, height, scale=1.0, **kwargs):
        captured.update({"x": x, "y": y, "width": width, "height": height, "scale": scale})
        return {
            "path": "E:/proj/updates/screenshots/2026-01-01/s.png",
            "format": "png",
            "bytes": 10,
            "sha256_8": "abcd",
            "width": width,
            "height": height,
            "capture_method": "screen_region",
        }

    monkeypatch.setattr(
        server_module.deps.widget_action_ctrl,
        "resolve_widget",
        fake_resolve_widget,
    )
    monkeypatch.setattr(
        server_module.deps.screenshot_ctrl,
        "capture_region",
        fake_capture_region,
    )
    def fake_printwindow_fail(*args, **kwargs):
        raise ApiError(
            status_code=500,
            code="print_window_failed",
            message="test: force mss path",
        )

    monkeypatch.setattr(
        server_module.deps.screenshot_ctrl,
        "capture_region_via_window_printwindow",
        fake_printwindow_fail,
    )

    res = client.post(
        "/screenshot/widget",
        headers=api_headers,
        json={"id": "w_test", "window_title": "Calc", "crop_padding_px": 0},
    )
    assert res.status_code == 200
    assert captured == {"x": 100, "y": 200, "width": 80, "height": 32, "scale": 1.0}
    data = res.json()["data"]
    assert data["image_path"].endswith("s.png")
    assert data["widget_id"] == "w_test"
    assert data["bounds"] == {"x": 100, "y": 200, "width": 80, "height": 32}
    assert data.get("image_width") == 80 and data.get("image_height") == 32


def test_screenshot_widget_default_crop_padding_expands_region(client, api_headers, monkeypatch):
    """默认 crop_padding_px=4 时裁剪区相对 UIA 各扩 4px（非 Windows 路径避免真 clamp）。"""
    captured: dict = {}

    def fake_resolve_widget(**kwargs):
        return (_fake_widget(), {"title": "T", "hwnd": 1}, True, "id", None)

    def fake_capture_region(x, y, width, height, scale=1.0, **kwargs):
        captured.update({"x": x, "y": y, "width": width, "height": height})
        return {
            "path": "E:/proj/updates/screenshots/2026-01-01/pad.png",
            "format": "png",
            "bytes": 10,
            "sha256_8": "abcd",
            "width": width,
            "height": height,
            "capture_method": "screen_region",
        }

    monkeypatch.setattr(widget_cropper_module.os, "name", "posix")
    monkeypatch.setattr(
        server_module.deps.widget_action_ctrl,
        "resolve_widget",
        fake_resolve_widget,
    )
    monkeypatch.setattr(
        server_module.deps.screenshot_ctrl,
        "capture_region",
        fake_capture_region,
    )

    res = client.post(
        "/screenshot/widget",
        headers=api_headers,
        json={"id": "w_test", "window_title": "Calc"},
    )
    assert res.status_code == 200
    assert captured == {"x": 96, "y": 196, "width": 88, "height": 40}
    data = res.json()["data"]
    assert data["bounds"] == {"x": 100, "y": 200, "width": 80, "height": 32}
    assert data["capture_bounds"] == {"x": 96, "y": 196, "width": 88, "height": 40}
    assert data.get("crop_padding_px") == 4

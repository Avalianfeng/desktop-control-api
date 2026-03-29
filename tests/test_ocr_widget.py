from __future__ import annotations

from unittest.mock import patch

import pytest

import server as server_module
from errors import ApiError
from semantic.widget_types import Widget, WidgetText
from models.ui_dom import UIBounds


@pytest.fixture
def api_headers():
    return {"X-API-Key": server_module.VALID_API_KEYS[0]}


def _fake_widget() -> Widget:
    return Widget(
        id="w_ocr",
        type="b",
        role="button",
        text=WidgetText(value="分数", source="uia", confidence=1.0),
        text_legacy="分数",
        normalized="分数",
        bounds=UIBounds(x=10, y=20, width=50, height=24),
        uia_path="p",
    )


def test_ocr_read_widget_returns_ocr_lines(client, api_headers, monkeypatch):
    def fake_resolve_widget(**kwargs):
        return (_fake_widget(), {"hwnd": 9}, True, "id", None)

    def fake_capture_region(x, y, width, height, scale=1.0, **kwargs):
        return {
            "path": "E:/p/crop.png",
            "format": "png",
            "bytes": 4,
            "sha256_8": "ab",
            "width": width,
            "height": height,
            "capture_method": "screen_region",
        }

    fake_data = {
        "text": ["x!"],
        "left": [1],
        "top": [2],
        "width": [10],
        "height": [11],
        "conf": [92],
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

    with patch("pytesseract.image_to_data", return_value=fake_data):
        res = client.post(
            "/ocr/read_widget",
            headers=api_headers,
            json={"id": "w_ocr", "window_title": "Calc", "lang": "eng", "crop_padding_px": 0},
        )

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert data["widget"]["id"] == "w_ocr"
    assert data["widget"]["text"] == "分数"
    assert data["image_path"] == "E:/p/crop.png"
    assert len(data["ocr"]["lines"]) == 1
    assert data["ocr"]["lines"][0]["text"] == "x!"
    assert data["ocr"]["text"] == "x!"

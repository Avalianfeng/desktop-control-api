from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

import pytest

import server as server_module
from errors import ApiError


@dataclass
class _FakeQueryResult:
    window: dict
    stats: dict
    widgets: List[dict]
    partial: bool


@pytest.fixture
def api_headers():
    return {"X-API-Key": server_module.VALID_API_KEYS[0]}


def test_ocr_read_window_batches_widgets(client, api_headers, monkeypatch):
    def fake_query_widgets(**kwargs: Any) -> _FakeQueryResult:
        return _FakeQueryResult(
            window={"hwnd": 99, "title": "T"},
            stats={},
            widgets=[
                {"id": "w_big", "bounds": {"width": 100, "height": 20}, "role": "text", "text": "UIA"},
                {"id": "w_small", "bounds": {"width": 5, "height": 5}, "role": "text", "text": "x"},
            ],
            partial=False,
        )

    def fake_read_widget(*, widget_id: str, **kw: Any) -> dict:
        return {
            "widget": {"id": widget_id, "text": "UIA", "role": "text"},
            "ocr": {"text": "OCR", "lines": [{"text": "O", "bbox": [0, 0, 1, 1], "conf": 0.9}]},
            "image_path": "E:/x/crop.png",
            "image_width": 100,
            "image_height": 20,
        }

    monkeypatch.setattr(server_module.deps.widget_query_ctrl, "query_widgets", fake_query_widgets)
    monkeypatch.setattr(server_module.deps.visual_semantic_service, "read_widget", fake_read_widget)
    monkeypatch.setattr(server_module.deps.windows_ctrl, "focus_by_hwnd", lambda h: ({}, None))

    res = client.post(
        "/ocr/read_window",
        headers=api_headers,
        json={
            "window_hwnd": 99,
            "focus_first": False,
            "max_widgets": 5,
            "min_bounds_area": 400,
            "query_limit": 50,
            "lang": "eng",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert data["stats"]["ocr_count"] == 1
    assert len(data["widgets"]) == 1
    row = data["widgets"][0]
    assert row["id"] == "w_big"
    assert row["uia_text"] == "UIA"
    assert row["ocr_text"] == "OCR"
    assert row["image_width"] == 100


def test_ocr_read_window_maps_api_error(client, api_headers, monkeypatch):
    def fake_query_widgets(**kwargs: Any) -> _FakeQueryResult:
        return _FakeQueryResult(
            window={"hwnd": 1},
            stats={},
            widgets=[{"id": "w1", "bounds": {"width": 50, "height": 30}, "role": "button", "text": ""}],
            partial=False,
        )

    def fake_read_widget(**kwargs: Any) -> dict:
        raise ApiError(status_code=404, code="widget_not_found", message="missing")

    monkeypatch.setattr(server_module.deps.widget_query_ctrl, "query_widgets", fake_query_widgets)
    monkeypatch.setattr(server_module.deps.visual_semantic_service, "read_widget", fake_read_widget)

    res = client.post(
        "/ocr/read_window",
        headers=api_headers,
        json={"window_hwnd": 1, "focus_first": False, "max_widgets": 3, "min_bounds_area": 100},
    )
    assert res.status_code == 200
    row = res.json()["data"]["widgets"][0]
    assert row["error"]["code"] == "widget_not_found"

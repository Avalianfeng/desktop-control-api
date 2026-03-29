from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

import server as server_module
from controllers.ui_read_controller import UIReadResult
from models.ui_dom import DOMQualityReport, DesktopDOMData, DesktopDOMResponse, UIBounds, UIElement


def test_widgets_read_collapses_button_text(monkeypatch) -> None:
    btn = UIElement(
        id="Calc#1/root/group[0]/button[10]",
        type="button",
        text="",
        name="",
        control_type="ButtonControl",
        bounds=UIBounds(x=100, y=200, width=30, height=30),
        enabled=True,
        visible=True,
        children=[
            UIElement(
                id="Calc#1/root/group[0]/button[10]/text[0]",
                type="text",
                text=".",
                name=".",
                control_type="TextControl",
                bounds=UIBounds(x=110, y=205, width=5, height=10),
                enabled=True,
                visible=True,
                children=[],
            )
        ],
    )
    dom_data = DesktopDOMData(root=btn, by_id={btn.id: btn}, by_control_type={"button": [btn.id]})
    payload = DesktopDOMResponse(
        schema_version="desktop_dom.v1",
        window={"title": "Calc", "hwnd": 1, "left": 0, "top": 0, "width": 800, "height": 600},
        dom=dom_data,
        quality=DOMQualityReport(element_count=2, interactive_count=1, text_coverage=0.5, has_root_window=True, score=0.5),
        stats={"truncated": False, "truncated_reason": None, "uia_time_ms": 1, "fallback_triggered": False},
        semantic=None,
    )

    def _fake(*args: Any, **kwargs: Any) -> UIReadResult:
        return UIReadResult(payload=payload, partial=False)

    monkeypatch.setattr(server_module.ui_read_ctrl, "read_dom", _fake)

    client = TestClient(server_module.app)
    resp = client.post("/ui/widgets/read", headers={"X-API-Key": server_module.VALID_API_KEYS[0]}, json={"max_depth": 4})
    assert resp.status_code == 200
    data = resp.json()
    payload = data["data"]
    assert payload["schema_version"] == "desktop_widgets.v2"
    assert payload["stats"]["all_elements"] == 1
    assert payload["stats"]["widgets"] == 1
    assert payload["stats"]["actionable_widgets"] == 1
    assert len(payload["widgets"]) == 1
    assert payload["widgets"][0]["type"] == "button"
    assert payload["widgets"][0]["role"] == "button"
    assert payload["widgets"][0]["text"] == {"value": ".", "source": "uia", "confidence": 1.0}
    assert payload["widgets"][0]["text_legacy"] == "."
    assert payload["widgets"][0]["normalized"] == ""
    assert payload["widgets"][0]["enabled"] is True
    assert payload["widgets"][0]["visible"] is True
    assert "focusable" in payload["widgets"][0]


def test_widgets_read_alias_matches_ui_widgets_read(monkeypatch) -> None:
    btn = UIElement(
        id="Calc#1/root/group[0]/button[10]",
        type="button",
        text="",
        name="",
        control_type="ButtonControl",
        bounds=UIBounds(x=100, y=200, width=30, height=30),
        enabled=True,
        visible=True,
        children=[
            UIElement(
                id="Calc#1/root/group[0]/button[10]/text[0]",
                type="text",
                text=".",
                name=".",
                control_type="TextControl",
                bounds=UIBounds(x=110, y=205, width=5, height=10),
                enabled=True,
                visible=True,
                children=[],
            )
        ],
    )
    dom_data = DesktopDOMData(root=btn, by_id={btn.id: btn}, by_control_type={"button": [btn.id]})
    payload = DesktopDOMResponse(
        schema_version="desktop_dom.v1",
        window={"title": "Calc", "hwnd": 1, "left": 0, "top": 0, "width": 800, "height": 600},
        dom=dom_data,
        quality=DOMQualityReport(element_count=2, interactive_count=1, text_coverage=0.5, has_root_window=True, score=0.5),
        stats={"truncated": False, "truncated_reason": None, "uia_time_ms": 1, "fallback_triggered": False},
        semantic=None,
    )

    def _fake(*args: Any, **kwargs: Any) -> UIReadResult:
        return UIReadResult(payload=payload, partial=False)

    monkeypatch.setattr(server_module.ui_read_ctrl, "read_dom", _fake)

    client = TestClient(server_module.app)
    h = {"X-API-Key": server_module.VALID_API_KEYS[0]}
    body = {"max_depth": 4}
    a = client.post("/ui/widgets/read", headers=h, json=body).json()
    b = client.post("/widgets/read", headers=h, json=body).json()
    assert a == b


from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

import server as server_module
from controllers.ui_read_controller import UIReadResult
from models.ui_dom import DOMQualityReport, DesktopDOMData, DesktopDOMResponse, UIBounds, UIElement


def test_widgets_query_filters_and_select(monkeypatch) -> None:
    # button "=" should normalize to equals
    btn = UIElement(
        id="Calc#1/root/button[0]",
        type="button",
        text="等于",
        name="等于",
        control_type="ButtonControl",
        bounds=UIBounds(x=10, y=90, width=10, height=10),
        enabled=True,
        visible=True,
        focusable=True,
        children=[],
    )
    dom_data = DesktopDOMData(root=btn, by_id={btn.id: btn}, by_control_type={"button": [btn.id]})
    payload = DesktopDOMResponse(
        schema_version="desktop_dom.v1",
        window={"title": "Calc", "hwnd": 1, "left": 0, "top": 0, "width": 100, "height": 100},
        dom=dom_data,
        quality=DOMQualityReport(element_count=1, interactive_count=1, text_coverage=1.0, has_root_window=True, score=0.5),
        stats={"truncated": False, "truncated_reason": None, "uia_time_ms": 1, "fallback_triggered": False},
        semantic=None,
    )

    def _fake(*args: Any, **kwargs: Any) -> UIReadResult:
        return UIReadResult(payload=payload, partial=False)

    monkeypatch.setattr(server_module.widget_query_ctrl.ui_read_ctrl, "read_dom", _fake)

    client = TestClient(server_module.app)
    resp = client.post(
        "/ui/widgets/query",
        headers={"X-API-Key": server_module.VALID_API_KEYS[0]},
        json={
            "filters": {"normalized": "equals"},
            "limit": 10,
            "select": ["id", "normalized", "role"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    payload = data["data"]
    assert payload["schema_version"] == "desktop_widgets_query.v1"
    assert payload["stats"]["matched"] == 1
    assert payload["widgets"][0]["normalized"] == "equals"
    assert payload["widgets"][0]["role"] == "button"
    assert list(payload["widgets"][0].keys()) == ["id", "role", "normalized"]


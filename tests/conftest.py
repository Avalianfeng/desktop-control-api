from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

import server as server_module
from controllers.ui_read_controller import UIReadResult
from dom.semantic import build_semantic_dom
from models.ui_dom import DOMQualityReport, DesktopDOMData, DesktopDOMResponse, UIBounds, UIElement


@pytest.fixture
def client() -> TestClient:
    return TestClient(server_module.app)


@pytest.fixture
def api_headers() -> Dict[str, str]:
    # 测试内使用进程中的有效 API Key。
    return {"X-API-Key": server_module.VALID_API_KEYS[0]}


@pytest.fixture
def sample_dom_payload() -> DesktopDOMResponse:
    root = UIElement(
        id="Notepad#100/root",
        type="window",
        text="",
        name="Notepad",
        control_type="WindowControl",
        bounds=UIBounds(x=10, y=10, width=800, height=600),
        enabled=True,
        visible=True,
        source="uia",
        status="ok",
        children=[],
    )
    dom_data = DesktopDOMData(root=root, by_id={root.id: root}, by_control_type={"window": [root.id]})
    return DesktopDOMResponse(
        schema_version="desktop_dom.v1",
        window={"title": "Notepad", "hwnd": 100, "left": 10, "top": 10, "width": 800, "height": 600},
        dom=dom_data,
        quality=DOMQualityReport(
            element_count=1, interactive_count=0, text_coverage=0.0, has_root_window=True, score=0.4
        ),
        stats={"truncated": False, "truncated_reason": None, "uia_time_ms": 50, "fallback_triggered": False},
        semantic=build_semantic_dom(dom_data),
    )


@pytest.fixture
def patch_ui_dom_success(monkeypatch: pytest.MonkeyPatch, sample_dom_payload: DesktopDOMResponse):
    def _fake(*args: Any, **kwargs: Any) -> UIReadResult:
        return UIReadResult(payload=sample_dom_payload, partial=False)

    monkeypatch.setattr(server_module.ui_read_ctrl, "read_dom", _fake)


@pytest.fixture
def patch_ui_dom_partial(monkeypatch: pytest.MonkeyPatch, sample_dom_payload: DesktopDOMResponse):
    payload = sample_dom_payload.model_copy(deep=True)
    payload.stats["truncated"] = True
    payload.stats["truncated_reason"] = "max_depth_reached"

    def _fake(*args: Any, **kwargs: Any) -> UIReadResult:
        return UIReadResult(payload=payload, partial=True)

    monkeypatch.setattr(server_module.ui_read_ctrl, "read_dom", _fake)

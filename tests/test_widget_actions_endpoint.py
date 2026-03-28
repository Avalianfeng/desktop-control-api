from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

import server as server_module
from controllers.ui_read_controller import UIReadResult
from models.ui_dom import DOMQualityReport, DesktopDOMData, DesktopDOMResponse, UIBounds, UIElement


def test_widget_click_re_resolve_by_fingerprint(monkeypatch) -> None:
    """
    模拟：stable id 不存在（runtime_id 变了），但 fingerprint 仍可找到当前控件。
    用 monkeypatch 避免触发真实点击。
    """
    # snapshot1: old runtime_id -> old widget_id
    btn_old = UIElement(
        id="Calc#1/root/button[0]",
        type="button",
        text="OK",
        name="OK",
        control_type="ButtonControl",
        bounds=UIBounds(x=10, y=10, width=20, height=20),
        enabled=True,
        visible=True,
        focusable=True,
        uia_runtime_id="1.2.3",
        uia_automation_id="",
        uia_patterns=["InvokePattern"],
        children=[],
    )
    dom_old = DesktopDOMData(root=btn_old, by_id={btn_old.id: btn_old}, by_control_type={"button": [btn_old.id]})
    payload_old = DesktopDOMResponse(
        schema_version="desktop_dom.v1",
        window={"title": "Calc", "hwnd": 1, "left": 0, "top": 0, "width": 100, "height": 100},
        dom=dom_old,
        quality=DOMQualityReport(element_count=1, interactive_count=1, text_coverage=1.0, has_root_window=True, score=0.5),
        stats={"truncated": False, "truncated_reason": None, "uia_time_ms": 1, "fallback_triggered": False},
        semantic=None,
    )

    # snapshot2: new runtime_id -> new widget_id, but same text/role
    btn_new = btn_old.model_copy(update={"uia_runtime_id": "9.9.9"})
    dom_new = DesktopDOMData(root=btn_new, by_id={btn_new.id: btn_new}, by_control_type={"button": [btn_new.id]})
    payload_new = payload_old.model_copy(update={"dom": dom_new})

    calls = {"n": 0}

    def _fake(*args: Any, **kwargs: Any) -> UIReadResult:
        calls["n"] += 1
        # first read -> old, second read -> new
        return UIReadResult(payload=payload_old if calls["n"] == 1 else payload_new, partial=False)

    monkeypatch.setattr(server_module.widget_action_ctrl.ui_read_ctrl, "read_dom", _fake)

    # prevent UIA backend call (uiautomation may crash in test env)
    class _UIAutomationStub:
        pass

    monkeypatch.setitem(__import__("sys").modules, "uiautomation", _UIAutomationStub())

    # prevent real click fallback
    class _PyAutoGuiStub:
        def click(self, *a, **k):
            return None

    monkeypatch.setitem(__import__("sys").modules, "pyautogui", _PyAutoGuiStub())

    # Compute old widget id by calling read endpoint once (build_widgets happens inside action too)
    # Instead: directly call click with a guaranteed-wrong id and provide fingerprint.
    client = TestClient(server_module.app)
    resp = client.post(
        "/ui/widgets/click",
        headers={"X-API-Key": server_module.VALID_API_KEYS[0]},
        json={
            "id": "w_deadbeefdead",
            "fingerprint": {"role": "button", "text": "OK", "normalized": "ok", "automation_id": "", "ancestor_roles": []},
        },
    )
    # Default safe mode: should return simulation plan (no real click)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    payload = data["data"]
    assert payload.get("mode") == "safe"
    assert payload["simulation"]["resolved_by"] in ("fingerprint", "id")


def test_widget_click_not_found_returns_404(monkeypatch) -> None:
    btn = UIElement(
        id="Calc#1/root/button[0]",
        type="button",
        text="OK",
        name="OK",
        control_type="ButtonControl",
        bounds=UIBounds(x=10, y=10, width=20, height=20),
        enabled=True,
        visible=True,
        focusable=True,
        uia_runtime_id="1.2.3",
        uia_automation_id="btnOk",
        uia_patterns=["InvokePattern"],
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

    monkeypatch.setattr(server_module.widget_action_ctrl.ui_read_ctrl, "read_dom", _fake)

    client = TestClient(server_module.app)
    resp = client.post(
        "/ui/widgets/click",
        headers={"X-API-Key": server_module.VALID_API_KEYS[0]},
        json={"id": "w_not_exists"},
    )
    assert resp.status_code == 404


def test_widget_set_value_not_found_returns_404(monkeypatch) -> None:
    txt = UIElement(
        id="Calc#1/root/input[0]",
        type="input",
        text="",
        name="",
        control_type="EditControl",
        bounds=UIBounds(x=10, y=10, width=50, height=20),
        enabled=True,
        visible=True,
        focusable=True,
        uia_runtime_id="9.9.9",
        uia_automation_id="txtA",
        uia_patterns=["ValuePattern"],
        children=[],
    )
    dom_data = DesktopDOMData(root=txt, by_id={txt.id: txt}, by_control_type={"input": [txt.id]})
    payload = DesktopDOMResponse(
        schema_version="desktop_dom.v1",
        window={"title": "Calc", "hwnd": 1, "left": 0, "top": 0, "width": 100, "height": 100},
        dom=dom_data,
        quality=DOMQualityReport(element_count=1, interactive_count=1, text_coverage=0.0, has_root_window=True, score=0.5),
        stats={"truncated": False, "truncated_reason": None, "uia_time_ms": 1, "fallback_triggered": False},
        semantic=None,
    )

    def _fake(*args: Any, **kwargs: Any) -> UIReadResult:
        return UIReadResult(payload=payload, partial=False)

    monkeypatch.setattr(server_module.widget_action_ctrl.ui_read_ctrl, "read_dom", _fake)

    client = TestClient(server_module.app)
    resp = client.post(
        "/ui/widgets/set_value",
        headers={"X-API-Key": server_module.VALID_API_KEYS[0]},
        json={"id": "w_not_exists", "value": "abc"},
    )
    assert resp.status_code == 404


def test_widget_set_value_verify_false_when_not_changed(monkeypatch) -> None:
    """
    验证 set_value 的 verify 路径：当回读 value 不等于目标值时，返回 verified=false + reason。
    """
    txt = UIElement(
        id="Calc#1/root/input[0]",
        type="input",
        text="",
        name="",
        control_type="EditControl",
        bounds=UIBounds(x=10, y=10, width=50, height=20),
        enabled=True,
        visible=True,
        focusable=True,
        uia_runtime_id="9.9.9",
        uia_automation_id="",
        uia_patterns=["ValuePattern"],
        uia_value="old",
        children=[],
    )
    dom_data = DesktopDOMData(root=txt, by_id={txt.id: txt}, by_control_type={"input": [txt.id]})
    payload = DesktopDOMResponse(
        schema_version="desktop_dom.v1",
        window={"title": "Calc", "hwnd": 1, "left": 0, "top": 0, "width": 100, "height": 100},
        dom=dom_data,
        quality=DOMQualityReport(element_count=1, interactive_count=1, text_coverage=0.0, has_root_window=True, score=0.5),
        stats={"truncated": False, "truncated_reason": None, "uia_time_ms": 1, "fallback_triggered": False},
        semantic=None,
    )

    def _fake(*args: Any, **kwargs: Any) -> UIReadResult:
        return UIReadResult(payload=payload, partial=False)

    monkeypatch.setattr(server_module.widget_action_ctrl.ui_read_ctrl, "read_dom", _fake)

    # prevent UIA backend call (uiautomation may crash in test env)
    class _UIAutomationStub:
        pass

    monkeypatch.setitem(__import__("sys").modules, "uiautomation", _UIAutomationStub())

    class _PyAutoGuiStub:
        def click(self, *a, **k):
            return None

        def hotkey(self, *a, **k):
            return None

        def write(self, *a, **k):
            return None

    monkeypatch.setitem(__import__("sys").modules, "pyautogui", _PyAutoGuiStub())

    client = TestClient(server_module.app)
    resp = client.post(
        "/ui/widgets/set_value",
        headers={"X-API-Key": server_module.VALID_API_KEYS[0], "X-Desktop-Control-Mode": "live"},
        json={
            "id": "w_deadbeefdead",
            "value": "new",
            "verify": True,
            "fingerprint": {"role": "textbox", "text": "", "normalized": "", "automation_id": "", "ancestor_roles": []},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    payload = data["data"]
    assert payload["verified"] is False
    assert payload["verify_reason"] == "value_not_changed"


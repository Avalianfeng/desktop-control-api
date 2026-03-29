from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

import server as server_module
from controllers.windows import WindowsController
import controllers.windows as windows_module


def _assert_envelope(resp_json: dict) -> None:
    assert set(resp_json.keys()) == {"success", "data", "error", "trace_id"}
    assert isinstance(resp_json["success"], bool)
    if resp_json["success"]:
        assert resp_json["error"] is None
    else:
        assert resp_json["data"] is None
        assert isinstance(resp_json["error"], dict)
        assert "code" in resp_json["error"] and "message" in resp_json["error"]


def test_windows_controller_focus_by_hwnd_ignores_same_title(monkeypatch) -> None:
    class _W:
        def __init__(self, hwnd: int, title: str):
            self._hWnd = hwnd
            self.title = title
            self.left = 0
            self.top = 0
            self.width = 1
            self.height = 1
            self.activated = False

        def activate(self):
            self.activated = True

    w1 = _W(101, "SameTitle")
    w2 = _W(202, "SameTitle")

    monkeypatch.setattr(windows_module.gw, "getAllWindows", lambda: [w1, w2])
    monkeypatch.setattr(windows_module, "force_foreground", lambda hwnd, **k: {"ok": True, "reason": "test", "foreground_hwnd": hwnd})

    ctrl = WindowsController()
    out, err = ctrl.focus_by_hwnd(202)
    assert err is None and out is not None and out["hwnd"] == 202
    assert w1.activated is False
    assert w2.activated is True


def test_windows_controller_focus_by_hwnd_forwards_policy_kwarg(monkeypatch) -> None:
    class _W:
        def __init__(self, hwnd: int):
            self._hWnd = hwnd
            self.title = "T"
            self.left = self.top = self.width = self.height = 1

        def activate(self):
            pass

    w = _W(303)
    captured: dict[str, Any] = {}

    def _fake_fg(hwnd: int, **kw: Any):
        captured.update(kw)
        return {"ok": True, "reason": "test", "foreground_hwnd": hwnd, "foreground_verified": True}

    monkeypatch.setattr(windows_module.gw, "getAllWindows", lambda: [w])
    monkeypatch.setattr(windows_module, "force_foreground", _fake_fg)

    ctrl = WindowsController()
    out, err = ctrl.focus_by_hwnd(303, policy="relaxed")
    assert err is None and out and out.get("foreground_verified") is True
    assert captured.get("policy") == "relaxed"


def test_keyboard_type_focus_switches_to_target_hwnd_and_traces(monkeypatch) -> None:
    calls: dict[str, Any] = {"focused": [], "typed": []}

    monkeypatch.setattr(server_module.windows_ctrl, "get_active_hwnd", lambda: 111)
    monkeypatch.setattr(
        server_module.windows_ctrl,
        "focus_by_hwnd",
        lambda hwnd: ({"hwnd": hwnd, "title": "X", "left": 0, "top": 0, "width": 1, "height": 1}, None),
    )
    monkeypatch.setattr(server_module, "get_foreground_hwnd", lambda: 222)

    def _fake_type(text: str, interval: float = 0.0) -> None:
        calls["typed"].append({"text": text, "interval": interval})

    monkeypatch.setattr(server_module.keyboard_ctrl, "type_text", _fake_type)

    written: list[dict] = []

    def _fake_append(ev: dict, *a: Any, **k: Any):
        written.append(ev)
        return "x"

    monkeypatch.setattr(server_module, "append_trace_event", _fake_append)

    client = TestClient(server_module.app)
    resp = client.post(
        "/keyboard/type",
        headers={"X-API-Key": server_module.VALID_API_KEYS[0], "X-Actor": "agent_A"},
        json={"text": "hi", "interval": 0.01, "target_hwnd": 222, "delay_ms": 0},
    )
    assert resp.status_code == 200
    data = resp.json()
    _assert_envelope(data)
    assert data["success"] is True
    assert isinstance(data["trace_id"], str) and data["trace_id"].startswith("act_")
    assert data["data"]["action"] == "type"
    assert len(calls["typed"]) == 1
    assert len(written) == 1
    assert written[0]["endpoint"] == "/keyboard/type"
    assert written[0]["hwnd"] == 222


def test_envelope_shape_for_health(monkeypatch) -> None:
    client = TestClient(server_module.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    _assert_envelope(data)
    assert data["data"]["status"] == "ok"


def test_envelope_shape_for_windows_list(monkeypatch) -> None:
    monkeypatch.setattr(
        server_module.windows_ctrl,
        "list_all",
        lambda: [{"hwnd": 1, "title": "A", "left": 0, "top": 0, "width": 1, "height": 1, "is_active": True, "is_minimized": False, "is_maximized": False}],
    )
    client = TestClient(server_module.app)
    # v1.7: 默认 /windows 返回“可交互窗口”的精简列表；raw/include_system 才返回完整未过滤列表
    resp = client.get("/windows?raw=1", headers={"X-API-Key": server_module.VALID_API_KEYS[0]})
    assert resp.status_code == 200
    data = resp.json()
    _assert_envelope(data)
    assert data["data"]["count"] == 1
    assert isinstance(data["data"]["windows"][0]["hwnd"], int)


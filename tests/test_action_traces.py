from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

import server as server_module


def test_safe_mode_does_not_write_trace(monkeypatch) -> None:
    calls: list[dict] = []

    def _fake_append(ev: dict, *a: Any, **k: Any):
        calls.append(ev)
        return "x"

    monkeypatch.setattr(server_module, "append_trace_event", _fake_append)

    client = TestClient(server_module.app)
    resp = client.post(
        "/ui/widgets/click",
        headers={"X-API-Key": server_module.VALID_API_KEYS[0]},
        json={"id": "w_not_exists"},
    )
    # safe path: widget_not_found may happen, but should not write trace (only live)
    assert resp.status_code in (200, 404)
    assert calls == []


def test_live_click_returns_trace_id_and_writes(monkeypatch) -> None:
    written: list[dict] = []

    def _fake_append(ev: dict, *a: Any, **k: Any):
        written.append(ev)
        return "x"

    monkeypatch.setattr(server_module, "append_trace_event", _fake_append)

    # Stub action controller to avoid touching UIA/pyautogui in unit tests
    class _R:
        def __init__(self):
            self.success = True
            self.action = "click"
            self.widget_id = "w_x"
            self.locator_source = "automation_id"
            self.window = {"hwnd": 1}
            self.resolved = True
            self.resolved_by = "fingerprint"
            self.candidates = None
            self.verified = None
            self.verify_reason = None

        @property
        def __dict__(self):
            return {
                "success": self.success,
                "action": self.action,
                "widget_id": self.widget_id,
                "locator_source": self.locator_source,
                "window": self.window,
                "resolved": self.resolved,
                "resolved_by": self.resolved_by,
                "candidates": self.candidates,
                "verified": self.verified,
                "verify_reason": self.verify_reason,
            }

    def _fake_click(*a: Any, **k: Any):
        return _R()

    monkeypatch.setattr(server_module.widget_action_ctrl, "click", _fake_click)

    client = TestClient(server_module.app)
    resp = client.post(
        "/ui/widgets/click",
        headers={
            "X-API-Key": server_module.VALID_API_KEYS[0],
            "X-Desktop-Control-Mode": "live",
            "X-Actor": "agent_A",
        },
        json={"id": "w_any"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data.get("trace_id"), str) and data["trace_id"].startswith("act_")
    assert len(written) == 1
    ev = written[0]
    assert ev["endpoint"] == "/ui/widgets/click"
    assert ev["mode"] == "live"
    assert ev["actor"] == "agent_A"
    assert isinstance(ev.get("hwnd"), int)
    assert ev["stable_id"] == "w_any"
    assert ev["success"] is True
    assert isinstance(ev.get("duration_ms"), int)
    assert isinstance(ev.get("api_key_sha256_8"), str) and len(ev["api_key_sha256_8"]) == 8


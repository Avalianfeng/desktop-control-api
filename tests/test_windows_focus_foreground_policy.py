from __future__ import annotations

from fastapi.testclient import TestClient

import server as server_module
import controllers.win32_win as win32_module


def test_keyboard_type_rejects_when_not_foreground(monkeypatch) -> None:
    # Pretend focus succeeds but OS keeps foreground elsewhere.
    monkeypatch.setattr(server_module.windows_ctrl, "get_active_hwnd", lambda: 1)
    monkeypatch.setattr(server_module.windows_ctrl, "focus_by_hwnd", lambda hwnd: ({"hwnd": hwnd}, None))
    monkeypatch.setattr(win32_module, "get_foreground_hwnd", lambda: 999)
    monkeypatch.setattr(server_module.keyboard_ctrl, "type_text", lambda *a, **k: None)

    client = TestClient(server_module.app)
    resp = client.post(
        "/keyboard/type",
        headers={"X-API-Key": server_module.VALID_API_KEYS[0]},
        json={"text": "abc", "interval": 0.01, "target_hwnd": 2, "delay_ms": 0},
    )
    assert resp.status_code == 409
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "window_focus_failed"


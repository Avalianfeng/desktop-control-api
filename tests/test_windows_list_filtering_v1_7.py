from __future__ import annotations

from typing import Any, Dict, List


def _assert_envelope(resp_json: Dict[str, Any]):
    assert isinstance(resp_json, dict)
    assert "success" in resp_json
    assert "data" in resp_json
    assert "error" in resp_json
    assert "trace_id" in resp_json


def test_windows_default_returns_interactive_projection(client, api_headers, monkeypatch):
    import server as server_module

    def _fake_list_interactive() -> List[Dict[str, Any]]:
        return [
            {"hwnd": 200242, "title": "Notepad"},
            {"hwnd": 266106, "title": "Notepad"},
            {"hwnd": 528426, "title": "计算器"},
        ]

    monkeypatch.setattr(server_module.windows_ctrl, "list_interactive", _fake_list_interactive)

    r = client.get("/windows", headers=api_headers)
    assert r.status_code == 200
    j = r.json()
    _assert_envelope(j)
    assert j["success"] is True
    assert j["error"] is None
    assert j["data"]["count"] == 3
    assert j["data"]["windows"] == [
        {"hwnd": 200242, "title": "Notepad"},
        {"hwnd": 266106, "title": "Notepad"},
        {"hwnd": 528426, "title": "计算器"},
    ]
    # 省 token：默认不应包含诊断字段
    assert set(j["data"]["windows"][0].keys()) == {"hwnd", "title"}


def test_windows_raw_returns_full_with_is_interactive(client, api_headers, monkeypatch):
    import server as server_module

    full = [
        {"hwnd": 1, "title": "", "area": 0, "is_interactive": False, "filter_reasons": ["empty_title", "tiny_area"]},
        {"hwnd": 2, "title": "Notepad", "area": 800 * 600, "is_interactive": True, "filter_reasons": []},
    ]

    monkeypatch.setattr(server_module.windows_ctrl, "list_all", lambda: full)

    r = client.get("/windows?raw=1", headers=api_headers)
    assert r.status_code == 200
    j = r.json()
    _assert_envelope(j)
    assert j["success"] is True
    assert j["error"] is None
    assert j["data"]["count"] == 2
    assert j["data"]["windows"] == full
    assert isinstance(j["data"]["windows"][0]["is_interactive"], bool)
    assert isinstance(j["data"]["windows"][0]["filter_reasons"], list)


def test_windows_include_system_aliases_raw(client, api_headers, monkeypatch):
    import server as server_module

    full = [{"hwnd": 2, "title": "Notepad", "area": 1, "is_interactive": True, "filter_reasons": []}]
    monkeypatch.setattr(server_module.windows_ctrl, "list_all", lambda: full)

    r = client.get("/windows?include_system=1", headers=api_headers)
    assert r.status_code == 200
    j = r.json()
    _assert_envelope(j)
    assert j["success"] is True
    assert j["data"]["windows"] == full


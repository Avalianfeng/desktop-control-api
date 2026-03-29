from __future__ import annotations

from fastapi.testclient import TestClient

import server as server_module


def test_windows_focus_requires_title_or_hwnd(client: TestClient, api_headers):
    resp = client.post("/windows/focus", json={}, headers=api_headers)
    assert resp.status_code == 400


def test_windows_focus_by_title_not_found(client: TestClient, api_headers):
    resp = client.post(
        "/windows/focus",
        json={"title": "___definitely_not_a_real_window_title___"},
        headers=api_headers,
    )
    assert resp.status_code in (404, 500)


def test_windows_focus_by_hwnd_not_found(client: TestClient, api_headers):
    resp = client.post("/windows/focus", json={"hwnd": 999999999}, headers=api_headers)
    assert resp.status_code in (404, 500)


def test_windows_focus_best_effort_returns_200_on_focus_failed(
    client: TestClient, api_headers, monkeypatch
):
    monkeypatch.setattr(
        server_module.windows_ctrl,
        "focus_by_hwnd",
        lambda hwnd: (None, "focus_failed"),
    )
    resp = client.post(
        "/windows/focus",
        json={"hwnd": 4242, "best_effort": True},
        headers=api_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True
    data = body.get("data") or {}
    assert data.get("focused") is False
    assert data.get("reason") == "focus_failed"


def test_windows_focus_strict_still_409_on_focus_failed(
    client: TestClient, api_headers, monkeypatch
):
    monkeypatch.setattr(
        server_module.windows_ctrl,
        "focus_by_hwnd",
        lambda hwnd: (None, "focus_failed"),
    )
    resp = client.post(
        "/windows/focus",
        json={"hwnd": 4242, "best_effort": False},
        headers=api_headers,
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body.get("success") is False
    assert (body.get("error") or {}).get("code") == "window_focus_failed"


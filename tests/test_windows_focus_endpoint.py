from __future__ import annotations

from fastapi.testclient import TestClient


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


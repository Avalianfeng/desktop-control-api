from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["status"] == "ok"


def test_missing_api_key_forbidden(client: TestClient):
    resp = client.post("/screenshot")
    assert resp.status_code == 403
    data = resp.json()
    assert data["error"]["code"] == "auth_missing_api_key"
    assert "API Key" in data["error"]["message"]


def test_invalid_api_key_forbidden(client: TestClient):
    resp = client.post("/screenshot", headers={"X-API-Key": "invalid-key"})
    assert resp.status_code == 403
    data = resp.json()
    assert data["error"]["code"] == "auth_invalid_api_key"

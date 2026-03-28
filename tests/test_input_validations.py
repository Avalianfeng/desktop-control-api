from __future__ import annotations

from fastapi.testclient import TestClient


def test_mouse_scroll_rejects_zero_vertical_and_horizontal(
    client: TestClient, api_headers
):
    resp = client.post(
        "/mouse/scroll",
        headers=api_headers,
        json={"amount": 0, "horizontal": 0},
    )
    assert resp.status_code == 400


def test_locate_image_missing_file_returns_404(client: TestClient, api_headers):
    resp = client.post(
        "/locate/image",
        headers=api_headers,
        json={"image_path": "C:/not-exists.png", "confidence": 0.8},
    )
    assert resp.status_code == 404


def test_screenshot_invalid_region_returns_400(client: TestClient, api_headers):
    resp = client.post(
        "/screenshot?region=1&region=2&region=3",
        headers=api_headers,
    )
    assert resp.status_code == 400

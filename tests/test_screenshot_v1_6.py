from __future__ import annotations

from fastapi.testclient import TestClient

import server as server_module


def test_screenshot_default_does_not_return_image(monkeypatch) -> None:
    monkeypatch.setattr(
        server_module.screenshot_ctrl,
        "capture_to_file",
        lambda region=None: {
            "format": "png",
            "width": 1,
            "height": 2,
            "path": "updates/screenshots/2026-03-26/x.png",
            "bytes": 3,
            "sha256_8": "abcd1234",
        },
    )

    client = TestClient(server_module.app)
    resp = client.post("/screenshot", headers={"X-API-Key": server_module.VALID_API_KEYS[0]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "image" not in data["data"]
    p = data["data"]["path"].replace("\\", "/")
    assert p
    assert "updates/screenshots" in p


def test_screenshot_include_image_returns_image(monkeypatch) -> None:
    monkeypatch.setattr(
        server_module.screenshot_ctrl,
        "capture_to_file",
        lambda region=None: {
            "format": "png",
            "width": 1,
            "height": 2,
            "path": "updates/screenshots/2026-03-26/x.png",
            "bytes": 3,
            "sha256_8": "abcd1234",
        },
    )
    monkeypatch.setattr(server_module.screenshot_ctrl, "capture", lambda region=None: {"base64": "AA==", "width": 1, "height": 2})

    client = TestClient(server_module.app)
    resp = client.post("/screenshot?include_image=1", headers={"X-API-Key": server_module.VALID_API_KEYS[0]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["image"] == "AA=="


def test_screenshot_window_default_no_image(monkeypatch) -> None:
    def fake_capture_window(
        title: str,
        include_decorations: bool = False,
        scale: float = 1.0,
        *,
        include_image: bool = False,
    ):
        assert include_image is False
        return {
            "format": "png",
            "path": "updates/screenshots/2026-03-26/window.png",
            "bytes": 42,
            "sha256_8": "deadbeef",
            "width": 10,
            "height": 20,
            "capture_method": "print_window",
            "window": {"title": title, "left": 0, "top": 0, "width": 100, "height": 200},
        }

    monkeypatch.setattr(server_module.screenshot_ctrl, "capture_window", fake_capture_window)

    client = TestClient(server_module.app)
    resp = client.post(
        "/screenshot/window",
        headers={"X-API-Key": server_module.VALID_API_KEYS[0]},
        json={"title": "TestWin"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "image" not in data["data"]
    p = data["data"]["path"].replace("\\", "/")
    assert p
    assert "updates/screenshots" in p
    assert data["data"]["window"]["title"] == "TestWin"
    assert data["data"]["capture_method"] == "print_window"


def test_screenshot_window_include_image(monkeypatch) -> None:
    def fake_capture_window(
        title: str,
        include_decorations: bool = False,
        scale: float = 1.0,
        *,
        include_image: bool = False,
    ):
        assert include_image is True
        return {
            "format": "png",
            "path": "updates/screenshots/2026-03-26/w.png",
            "bytes": 3,
            "sha256_8": "abcd1234",
            "width": 1,
            "height": 2,
            "capture_method": "print_window",
            "window": {"title": title, "left": 0, "top": 0, "width": 1, "height": 2},
            "image": "QUJD",
        }

    monkeypatch.setattr(server_module.screenshot_ctrl, "capture_window", fake_capture_window)

    client = TestClient(server_module.app)
    resp = client.post(
        "/screenshot/window",
        headers={"X-API-Key": server_module.VALID_API_KEYS[0]},
        json={"title": "X", "include_image": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["image"] == "QUJD"


def test_screenshot_region_default_no_image(monkeypatch) -> None:
    def fake_capture_region(
        x: int,
        y: int,
        width: int,
        height: int,
        scale: float = 1.0,
        *,
        include_image: bool = False,
    ):
        assert include_image is False
        return {
            "format": "png",
            "path": "updates/screenshots/2026-03-26/r.png",
            "bytes": 9,
            "sha256_8": "aabbccdd",
            "width": width,
            "height": height,
            "capture_method": "screen_region",
        }

    monkeypatch.setattr(server_module.screenshot_ctrl, "capture_region", fake_capture_region)

    client = TestClient(server_module.app)
    resp = client.post(
        "/screenshot/region",
        headers={"X-API-Key": server_module.VALID_API_KEYS[0]},
        json={"x": 1, "y": 2, "width": 10, "height": 20},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "image" not in data["data"]
    assert data["data"]["capture_method"] == "screen_region"
    p = data["data"]["path"].replace("\\", "/")
    assert p and "updates/screenshots" in p


def test_screenshot_region_include_image(monkeypatch) -> None:
    def fake_capture_region(
        x: int,
        y: int,
        width: int,
        height: int,
        scale: float = 1.0,
        *,
        include_image: bool = False,
    ):
        assert include_image is True
        return {
            "format": "png",
            "path": "updates/screenshots/2026-03-26/r2.png",
            "bytes": 3,
            "sha256_8": "11223344",
            "width": 1,
            "height": 1,
            "capture_method": "screen_region",
            "image": "QUJD",
        }

    monkeypatch.setattr(server_module.screenshot_ctrl, "capture_region", fake_capture_region)

    client = TestClient(server_module.app)
    resp = client.post(
        "/screenshot/region",
        headers={"X-API-Key": server_module.VALID_API_KEYS[0]},
        json={"x": 0, "y": 0, "width": 5, "height": 5, "include_image": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["image"] == "QUJD"


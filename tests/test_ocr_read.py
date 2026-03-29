from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import server as server_module


@pytest.fixture
def api_headers():
    return {"X-API-Key": server_module.VALID_API_KEYS[0]}


def test_ocr_read_rejects_path_outside_cwd(client, api_headers, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    png = tmp_path / "evil.png"
    png.write_bytes(b"x")
    # 请求使用 cwd 外的绝对路径
    outside = Path("e:/no_such_root_desktop_control_api/evil2.png")
    res = client.post(
        "/ocr/read",
        headers=api_headers,
        json={"image_path": str(outside), "lang": "eng"},
    )
    assert res.status_code == 400
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "ocr_path_not_allowed"


def test_ocr_read_success_mocked(client, api_headers, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    img = tmp_path / "a.png"
    img.write_bytes(b"fakepng")

    fake_data = {
        "text": ["", "Hello", ""],
        "left": [0, 10, 0],
        "top": [0, 20, 0],
        "width": [0, 40, 0],
        "height": [0, 12, 0],
        "conf": [-1, 95, -1],
    }

    with patch("pytesseract.image_to_data", return_value=fake_data):
        res = client.post(
            "/ocr/read",
            headers=api_headers,
            json={"image_path": "a.png", "lang": "eng"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert len(data["lines"]) == 1
    assert data["lines"][0]["text"] == "Hello"
    assert data["lines"][0]["bbox"] == [10, 20, 40, 12]
    assert data["lines"][0]["conf"] == pytest.approx(0.95)
    assert data["text"] == "Hello"
    assert data["full_text"] == "Hello"


def test_ocr_read_relative_path_under_subdir(client, api_headers, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sub = tmp_path / "updates" / "screenshots"
    sub.mkdir(parents=True)
    img = sub / "x.png"
    img.write_bytes(b"x")
    fake_data = {"text": ["x"], "left": [0], "top": [0], "width": [5], "height": [5], "conf": [80]}
    with patch("pytesseract.image_to_data", return_value=fake_data):
        res = client.post(
            "/ocr/read",
            headers=api_headers,
            json={"image_path": "updates/screenshots/x.png", "lang": "eng"},
        )
    assert res.status_code == 200
    assert res.json()["data"]["lines"][0]["text"] == "x"

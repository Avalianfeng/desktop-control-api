from __future__ import annotations

import base64

import pytest
import requests

from tests.helpers.dom_assertions import bounds_are_screen_coordinates, flatten_elements, no_cycles_in_tree


def test_live_health(integration_base_url: str, integration_session: requests.Session):
    resp = integration_session.get(f"{integration_base_url}/health", timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_live_windows_list(integration_base_url: str, integration_headers, integration_session: requests.Session):
    resp = integration_session.get(f"{integration_base_url}/windows", headers=integration_headers, timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["windows"], list)


def test_live_screenshot(integration_base_url: str, integration_headers, integration_session: requests.Session):
    resp = integration_session.post(f"{integration_base_url}/screenshot", headers=integration_headers, timeout=10)
    if resp.status_code != 200:
        detail = ""
        try:
            detail = str(resp.json().get("detail", ""))
        except Exception:
            detail = resp.text
        pytest.skip(f"当前环境不支持截图或权限不足，接口返回 {resp.status_code}: {detail}")
    data = resp.json()
    assert data["success"] is True
    assert data["width"] > 0 and data["height"] > 0

    # 确保返回的是可解码的 base64 PNG 数据。
    image_bytes = base64.b64decode(data["image"])
    assert len(image_bytes) > 100


def test_live_ui_dom_read(integration_base_url: str, integration_headers, integration_session: requests.Session):
    resp = integration_session.post(
        f"{integration_base_url}/ui/dom/read",
        headers=integration_headers,
        json={"max_depth": 4, "include_offscreen": False},
        timeout=20,
    )
    assert resp.status_code in (200, 206)
    data = resp.json()
    assert data["schema_version"] == "desktop_dom.v1"
    assert "window" in data and "dom" in data and "quality" in data and "stats" in data
    assert "semantic" in data and data["semantic"].get("schema_version") == "desktop_dom_semantic.v1"
    assert "all_elements" in data["semantic"]["stats"]
    assert "actionable_elements" in data["semantic"]["stats"]

    root = data["dom"]["root"]
    if root:
        all_nodes = flatten_elements(root)
        assert all((node.get("id") or "").strip() for node in all_nodes)
        assert no_cycles_in_tree(root)
        assert bounds_are_screen_coordinates(all_nodes)

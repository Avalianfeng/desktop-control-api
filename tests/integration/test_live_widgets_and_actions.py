from __future__ import annotations

import os

import pytest
import requests


def test_live_ui_widgets_read(integration_base_url: str, integration_headers, integration_session: requests.Session):
    resp = integration_session.post(
        f"{integration_base_url}/ui/widgets/read",
        headers=integration_headers,
        json={"max_depth": 4, "include_text_widgets": True, "collapse_icons": True},
        timeout=20,
    )
    assert resp.status_code in (200, 206)
    data = resp.json()
    assert data["schema_version"] == "desktop_widgets.v2"
    assert "window" in data and "stats" in data and "widgets" in data
    assert "all_elements" in data["stats"]
    assert "widgets" in data["stats"]
    assert "actionable_widgets" in data["stats"]
    if data["widgets"]:
        w = data["widgets"][0]
        assert "enabled" in w and "visible" in w and "focusable" in w
        assert "text" in w and "normalized" in w and "role" in w


def test_live_window_focus_action(
    integration_base_url: str, integration_headers, integration_session: requests.Session
):
    """
    实际操作测试（默认跳过）：尝试 focus 一个已有窗口。
    需要显式开启 RUN_DESKTOP_ACTION_TESTS=1。
    """
    if os.getenv("RUN_DESKTOP_ACTION_TESTS", "0").strip() != "1":
        pytest.skip("未开启实际操作集成测试。设置 RUN_DESKTOP_ACTION_TESTS=1 后再执行。")

    windows_resp = integration_session.get(f"{integration_base_url}/windows", headers=integration_headers, timeout=10)
    assert windows_resp.status_code == 200
    windows_data = windows_resp.json()
    assert windows_data.get("success") is True
    windows = (windows_data.get("data") or {}).get("windows") or []

    title = None
    for w in windows:
        t = (w.get("title") or "").strip()
        if t:
            title = t
            break
    if not title:
        pytest.skip("未找到可用于 focus 的窗口标题")

    focus_resp = integration_session.post(
        f"{integration_base_url}/windows/focus",
        headers=integration_headers,
        json={"title": title},
        timeout=10,
    )
    assert focus_resp.status_code in (200, 404)


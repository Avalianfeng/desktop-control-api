from __future__ import annotations

import requests


def test_live_ui_widgets_query_basic(integration_base_url: str, integration_headers, integration_session: requests.Session):
    resp = integration_session.post(
        f"{integration_base_url}/ui/widgets/query",
        headers=integration_headers,
        json={"limit": 10, "filters": {}},
        timeout=30,
    )
    assert resp.status_code in (200, 206)
    data = resp.json()
    assert data["schema_version"] == "desktop_widgets_query.v1"
    assert "stats" in data and "widgets" in data
    assert data["stats"]["returned"] <= 10


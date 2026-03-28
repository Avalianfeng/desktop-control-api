from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers.dom_assertions import bounds_are_screen_coordinates, flatten_elements, no_cycles_in_tree


def test_ui_dom_schema_and_core_fields(
    client: TestClient, api_headers, patch_ui_dom_success
):
    resp = client.post(
        "/ui/dom/read",
        headers=api_headers,
        json={"max_depth": 8, "include_offscreen": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    payload = data["data"]
    assert payload["schema_version"] == "desktop_dom.v1"
    assert "window" in payload
    assert "dom" in payload
    assert "quality" in payload
    assert "stats" in payload
    assert "semantic" in payload
    assert payload["semantic"]["schema_version"] == "desktop_dom_semantic.v1"
    assert "all_elements" in payload["semantic"]["stats"]
    assert "actionable_elements" in payload["semantic"]["stats"]


def test_ui_dom_tree_integrity(
    client: TestClient, api_headers, patch_ui_dom_success
):
    resp = client.post("/ui/dom/read", headers=api_headers, json={})
    data = resp.json()
    payload = data["data"]
    root = payload["dom"]["root"]
    elements = flatten_elements(root)

    assert all((e.get("id") or "").strip() for e in elements)
    assert no_cycles_in_tree(root)
    assert bounds_are_screen_coordinates(elements)


def test_ui_dom_partial_returns_206(
    client: TestClient, api_headers, patch_ui_dom_partial
):
    resp = client.post("/ui/dom/read", headers=api_headers, json={"max_depth": 1})
    assert resp.status_code == 206
    data = resp.json()
    payload = data["data"]
    assert payload["stats"]["truncated"] is True

from __future__ import annotations

from recorder.event_model import build_record


def test_build_record_includes_version():
    r = build_record(
        "invoke",
        ts="2026-03-27T00:00:00Z",
        delay_ms=0,
        window={"title": "x", "hwnd": 1, "class": "y"},
        target={"name": "b", "automation_id": "id", "control_type": "Button", "role": "button"},
        selector={"automation_id": "id"},
    )
    assert r["version"] == "1.8.6"


from __future__ import annotations

import json

from recorder.recorder import UIARecorder


class _StubBridge:
    def __init__(self, *, on_invoke, on_value_changed, diag, window_title=None):  # noqa: ARG002
        self._on_invoke = on_invoke
        self._on_value_changed = on_value_changed
        self.details = {"invoke_event_id": 20009}
        self.started = True

    def start_handlers(self):
        return True

    def stop_handlers(self):
        self.started = False

    def pump(self, timeout_s=0.05):  # noqa: ARG002
        return None


class _StubSender:
    Name = "7"
    ControlTypeName = "Button"
    AutomationId = "num7Button"
    CurrentNativeWindowHandle = 0

    def GetParentControl(self):
        return None


def test_sanitization_drops_structure_and_writes_invoke(monkeypatch, tmp_path):
    monkeypatch.setattr("recorder.recorder.UIAComBridge", _StubBridge)
    out = tmp_path / "updates" / "recorder" / "x.jsonl"
    rec = UIARecorder(str(out))
    rec.start()

    # structure_changed should be dropped (not written).
    rec._event_id_to_name = {20002: "structure_changed", 20009: "invoke"}
    rec._on_invoke(_StubSender(), 20002)
    rec._on_invoke(_StubSender(), 20009)
    rec.stop()

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["event"] == "invoke"
    assert "delay_ms" in data
    assert "selector" in data and "automation_id" in data["selector"]
    assert data["version"] == "1.8.6"


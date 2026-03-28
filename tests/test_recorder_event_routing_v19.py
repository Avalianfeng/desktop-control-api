from __future__ import annotations

from recorder.recorder import UIARecorder


class _StubBridge:
    def __init__(self, *, on_invoke, on_value_changed, diag):  # noqa: ARG002
        self._on_invoke = on_invoke
        self._on_value_changed = on_value_changed
        self.details = {
            "invoke_event_id": 20009,
            "selection_item_selected_event_id": 20012,
            "value_property_id": 30045,
            "toggle_state_property_id": 30086,
        }
        self.started = True

    def start_handlers(self):
        return True

    def stop_handlers(self):
        self.started = False

    def pump(self, timeout_s=0.05):  # noqa: ARG002
        return None


class _StubSender:
    Name = "Item"
    ControlTypeName = "ListItemControl"
    AutomationId = "x"

    def GetParentControl(self):
        return None


def test_recorder_maps_selection_and_toggle(monkeypatch, tmp_path):
    monkeypatch.setattr("recorder.recorder.UIAComBridge", _StubBridge)
    out = tmp_path / "updates" / "recorder" / "x.jsonl"
    rec = UIARecorder(str(out))
    rec.start()
    sender = _StubSender()
    rec._on_invoke(sender, 20012)
    rec._on_property_changed(sender, 30086, 1)
    rec.stop()

    # v1.8.6 keeps toggle/expand_collapse as intent events.
    assert rec.event_count == 2
    counts = rec.event_counts
    assert counts.get("selection") == 1
    assert counts.get("toggle") == 1


from __future__ import annotations

import pytest

from recorder.recorder import UIARecorder


def test_recorder_start_bridge_failure_not_running(monkeypatch, tmp_path):
    class _BridgeFail:
        def __init__(self, *, on_invoke, on_value_changed, diag):  # noqa: ARG002
            self.details = {"reason": "boom"}
            self.started = False

        def start_handlers(self):
            return False

        def stop_handlers(self):
            return None

        def pump(self, timeout_s=0.05):  # noqa: ARG002
            return None

    monkeypatch.setattr("recorder.recorder.UIAComBridge", _BridgeFail)
    rec = UIARecorder(str(tmp_path / "updates" / "recorder" / "x.jsonl"))
    with pytest.raises(RuntimeError, match="bridge start failed"):
        rec.start()
    assert rec.running is False


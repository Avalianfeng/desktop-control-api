from __future__ import annotations

from recorder.uia_com_bridge import StartResult, UIAComBridge


class _BackendOK:
    def __init__(self):
        self.stopped = False
        self.pumped = False

    def start(self, *, on_invoke, on_value, diag):  # noqa: ARG002
        return StartResult(
            started=True,
            details={
                "invoke_registered": True,
                "value_registered": False,
                "event_registration": {"invoke": {"registered": True}, "menu_opened": {"registered": False, "error": "missing_event_id"}},
                "property_registration": {"value": {"registered": False, "error": "missing_property_id"}},
                "reason": None,
            },
        )

    def stop(self):
        self.stopped = True

    def pump(self, timeout_s=0.05):  # noqa: ARG002
        self.pumped = True


class _BackendFail:
    def start(self, *, on_invoke, on_value, diag):  # noqa: ARG002
        return StartResult(started=False, details={"reason": "boom"})

    def stop(self):
        return None

    def pump(self, timeout_s=0.05):  # noqa: ARG002
        return None


def test_bridge_start_success_and_pump():
    backend = _BackendOK()
    b = UIAComBridge(on_invoke=lambda s, e: None, on_value_changed=lambda s, p, v: None, diag=lambda m: None, backend=backend)
    assert b.start_handlers() is True
    assert b.started is True
    assert b.details["invoke_registered"] is True
    assert b.details["event_registration"]["invoke"]["registered"] is True
    b.pump()
    assert backend.pumped is True
    b.stop_handlers()
    assert backend.stopped is True
    assert b.started is False


def test_bridge_start_failure():
    b = UIAComBridge(on_invoke=lambda s, e: None, on_value_changed=lambda s, p, v: None, diag=lambda m: None, backend=_BackendFail())
    assert b.start_handlers() is False
    assert b.started is False
    assert b.details["reason"] == "boom"


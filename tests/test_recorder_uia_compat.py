from __future__ import annotations

from recorder.uia_compat import resolve_invoke_event_id, resolve_pump_fn, resolve_value_property_id


class _AutoA:
    UIA_Invoke_InvokedEventId = 20009
    UIA_ValueValuePropertyId = 30045

    @staticmethod
    def PumpWaitingMessages():
        return None


class _AutoB:
    InvokeInvokedEventId = 9001
    ValueValuePropertyId = 9002

    @staticmethod
    def PumpMessages():
        return None


class _AutoC:
    SomeInvokeEventId = 101
    OtherValuePropertyId = 202

    @staticmethod
    def WaitForUIAEvents():
        return None

    @staticmethod
    def MessageBox(content, title):  # noqa: ARG004
        return None


class _ClientNS:
    UIA_Invoke_InvokedEventId = 70001
    UIA_ValueValuePropertyId = 70002


class _AutoD:
    automationClient = _ClientNS()


def test_resolve_prefers_explicit_names():
    inv = resolve_invoke_event_id(_AutoA)
    val = resolve_value_property_id(_AutoA)
    pump = resolve_pump_fn(_AutoA)
    assert inv["value"] == 20009
    assert inv["selected_name"] == "UIA_Invoke_InvokedEventId"
    assert inv["selected_space"] == "module"
    assert val["value"] == 30045
    assert val["selected_name"] == "UIA_ValueValuePropertyId"
    assert val["selected_space"] == "module"
    assert pump["selected_name"] == "PumpWaitingMessages"
    assert callable(pump["value"])
    assert pump["selected_space"] == "module"


def test_resolve_fallback_names():
    inv = resolve_invoke_event_id(_AutoB)
    val = resolve_value_property_id(_AutoB)
    pump = resolve_pump_fn(_AutoB)
    assert inv["value"] == 9001
    assert val["value"] == 9002
    assert pump["selected_name"] == "PumpMessages"
    assert pump["selected_space"] == "module"


def test_resolve_pattern_match_when_no_explicit_name():
    inv = resolve_invoke_event_id(_AutoC)
    val = resolve_value_property_id(_AutoC)
    pump = resolve_pump_fn(_AutoC)
    assert inv["value"] == 101
    assert "Invoke" in (inv["selected_name"] or "")
    assert val["value"] == 202
    assert "Value" in (val["selected_name"] or "")
    # pump is strict whitelist only; WaitFor*/MessageBox must not be selected
    assert pump["selected_name"] is None
    assert pump["value"] is None


def test_resolve_from_nested_automation_client_space():
    inv = resolve_invoke_event_id(_AutoD)
    val = resolve_value_property_id(_AutoD)
    assert inv["value"] == 70001
    assert inv["selected_space"] == "automationClient"
    assert val["value"] == 70002
    assert val["selected_space"] == "automationClient"


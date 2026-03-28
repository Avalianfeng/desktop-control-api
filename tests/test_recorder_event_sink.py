from __future__ import annotations

from recorder.event_sink import build_invoke_event, build_named_event, build_uia_event_raw, build_value_change_event


class _StubControl:
    def __init__(self, name: str, ctype: str, automation_id: str = "", parent=None):
        self.Name = name
        self.ControlTypeName = ctype
        self.AutomationId = automation_id
        self._parent = parent

    def GetParentControl(self):
        return self._parent


def test_build_invoke_event_shape():
    win = _StubControl("计算器", "WindowControl")
    btn = _StubControl("5", "ButtonControl", "num5Button", parent=win)
    e = build_invoke_event(btn)
    assert e["event"] == "invoke"
    assert e["window"]["title"] == "计算器"
    assert e["control"]["name"] == "5"
    assert e["control"]["automation_id"] == "num5Button"
    assert "ButtonControl" in e["control"]["path"]


def test_build_value_change_event_shape():
    win = _StubControl("Notepad", "WindowControl")
    edit = _StubControl("Text Editor", "EditControl", "textBox1", parent=win)
    e = build_value_change_event(edit, "123")
    assert e["event"] == "value_change"
    assert e["window"]["title"] == "Notepad"
    assert e["value"] == "123"
    assert e["control"]["automation_id"] == "textBox1"


def test_build_named_event_shape():
    win = _StubControl("Demo", "WindowControl")
    item = _StubControl("Item A", "ListItemControl", parent=win)
    e = build_named_event(item, "selection", event_id=20012)
    assert e["event"] == "selection"
    assert e["event_id"] == "20012"
    assert e["window"]["title"] == "Demo"


def test_build_uia_event_raw_shape():
    win = _StubControl("Demo", "WindowControl")
    node = _StubControl("X", "CustomControl", parent=win)
    e = build_uia_event_raw(node, event_id=20000, property_id=30000)
    assert e["event"] == "uia_event_raw"
    assert e["event_id"] == "20000"
    assert e["property_id"] == "30000"


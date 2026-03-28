from __future__ import annotations

from recorder.event_filter import IntentContext, is_user_intent


def test_intent_filters_scrollbar():
    event = {"event": "invoke", "control": {"control_type": "滚动条", "name": "垂直"}, "window": {"title": "X", "hwnd": 1}}
    ok, reason = is_user_intent(event, ctx=IntentContext(foreground_hwnd=1, foreground_title="X"))
    assert ok is False
    assert reason == "scrollbar"


def test_intent_drops_passive_text_when_not_foreground_or_focus():
    event = {
        "event": "text_change",
        "control": {"control_type": "文本", "name": "x", "has_keyboard_focus": False},
        "window": {"title": "A", "hwnd": 10},
    }
    ok, reason = is_user_intent(event, ctx=IntentContext(foreground_hwnd=11, foreground_title="B"))
    assert ok is False
    assert reason == "passive_value_text"


def test_intent_allows_text_when_foreground_and_focus():
    event = {
        "event": "text_change",
        "control": {"control_type": "编辑", "name": "x", "has_keyboard_focus": True},
        "window": {"title": "A", "hwnd": 10},
    }
    ok, reason = is_user_intent(event, ctx=IntentContext(foreground_hwnd=10, foreground_title="A"))
    assert ok is True
    assert reason is None


from __future__ import annotations

from models.ui_dom import DesktopDOMData, UIBounds, UIElement
from semantic.widget_builder import build_widgets


def test_disabled_button_enabled_false() -> None:
    btn = UIElement(
        id="w/root/button[0]",
        type="button",
        text="OK",
        control_type="ButtonControl",
        bounds=UIBounds(x=10, y=10, width=20, height=20),
        enabled=False,
        visible=True,
        focusable=True,
        children=[],
    )
    dom = DesktopDOMData(root=btn, by_id={btn.id: btn}, by_control_type={})
    w = build_widgets(dom, include_text_widgets=False)[0]
    assert w.enabled is False


def test_offscreen_visible_false() -> None:
    txt = UIElement(
        id="w/root/text[0]",
        type="text",
        text="Hidden",
        control_type="TextControl",
        bounds=UIBounds(x=0, y=0, width=10, height=10),
        enabled=True,
        visible=False,
        focusable=False,
        children=[],
    )
    dom = DesktopDOMData(root=txt, by_id={txt.id: txt}, by_control_type={})
    w = build_widgets(dom, include_text_widgets=True)[0]
    assert w.visible is False


def test_equals_button_role_submit_and_normalized() -> None:
    btn = UIElement(
        id="w/root/button[1]",
        type="button",
        text="等于",
        control_type="ButtonControl",
        bounds=UIBounds(x=10, y=10, width=20, height=20),
        enabled=True,
        visible=True,
        focusable=True,
        children=[],
    )
    dom = DesktopDOMData(root=btn, by_id={btn.id: btn}, by_control_type={})
    w = build_widgets(dom, include_text_widgets=False)[0]
    assert w.normalized == "equals"
    assert w.role == "button"


def test_digit_button_role_input_digit() -> None:
    btn = UIElement(
        id="w/root/button[2]",
        type="button",
        text="1",
        control_type="ButtonControl",
        bounds=UIBounds(x=10, y=10, width=20, height=20),
        enabled=True,
        visible=True,
        focusable=True,
        children=[],
    )
    dom = DesktopDOMData(root=btn, by_id={btn.id: btn}, by_control_type={})
    w = build_widgets(dom, include_text_widgets=False)[0]
    assert w.normalized == "digit_1"
    assert w.role == "button"


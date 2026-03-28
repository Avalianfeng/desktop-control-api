from __future__ import annotations

from models.ui_dom import DesktopDOMData, UIBounds, UIElement
from semantic.widget_builder import build_widgets, collapse_tree


def test_collapse_button_text_child_into_label() -> None:
    btn = UIElement(
        id="w/root/button[10]",
        type="button",
        text="",
        bounds=UIBounds(x=100, y=200, width=30, height=30),
        enabled=True,
        children=[
            UIElement(
                id="w/root/button[10]/text[0]",
                type="text",
                text=".",
                bounds=UIBounds(x=110, y=205, width=5, height=10),
                enabled=True,
                children=[],
            )
        ],
    )
    collapsed = collapse_tree(btn)
    assert collapsed.text == "."
    assert collapsed.children == []


def test_build_widgets_returns_button_widget_with_label() -> None:
    btn = UIElement(
        id="w/root/button[10]",
        type="button",
        text="",
        bounds=UIBounds(x=100, y=200, width=30, height=30),
        enabled=True,
        children=[
            UIElement(
                id="w/root/button[10]/text[0]",
                type="text",
                text=".",
                bounds=UIBounds(x=110, y=205, width=5, height=10),
                enabled=True,
                children=[],
            )
        ],
    )
    dom = DesktopDOMData(root=btn, by_id={btn.id: btn}, by_control_type={})
    widgets = build_widgets(dom)
    assert len(widgets) == 1
    assert widgets[0].type == "button"
    assert widgets[0].role == "button"
    assert widgets[0].text == "."


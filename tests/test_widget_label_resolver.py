from __future__ import annotations

from models.ui_dom import UIBounds, UIElement
from semantic.label_resolver import deepest_text, extract_label, normalize_icon


def test_extract_label_button_child_text() -> None:
    btn = UIElement(
        id="w/root/button[0]",
        type="button",
        text="",
        name="",
        bounds=UIBounds(x=0, y=0, width=10, height=10),
        children=[
            UIElement(
                id="w/root/button[0]/text[0]",
                type="text",
                text=".",
                name=".",
                bounds=UIBounds(x=1, y=1, width=5, height=5),
                children=[],
            )
        ],
    )
    assert extract_label(btn) == "."


def test_deepest_text_folds_nested() -> None:
    root = UIElement(
        id="x",
        type="text",
        text="显示为 0",
        bounds=UIBounds(x=0, y=0, width=10, height=10),
        children=[
            UIElement(
                id="x/c0",
                type="container",
                bounds=UIBounds(x=0, y=0, width=10, height=10),
                children=[
                    UIElement(
                        id="x/c0/t0",
                        type="text",
                        text="0",
                        bounds=UIBounds(x=0, y=0, width=10, height=10),
                        children=[],
                    )
                ],
            )
        ],
    )
    assert deepest_text(root) == "0"


def test_normalize_icon_minimal_map() -> None:
    assert normalize_icon("\uf754") == "memory_clear"


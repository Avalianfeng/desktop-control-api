from __future__ import annotations

import pytest

from dom.filter import ACTIONABLE_TYPES, is_actionable, is_visible
from models.ui_dom import UIBounds, UIElement


def test_is_visible_zero_bounds() -> None:
    e = UIElement(
        id="x",
        type="button",
        bounds=UIBounds(x=0, y=0, width=0, height=0),
        enabled=True,
    )
    assert is_visible(e) is False


def test_is_visible_positive_bounds() -> None:
    e = UIElement(
        id="x",
        type="container",
        bounds=UIBounds(x=0, y=0, width=10, height=5),
    )
    assert is_visible(e) is True


def test_is_actionable_dict_form() -> None:
    ok = {
        "type": "button",
        "bounds": {"x": 0, "y": 0, "width": 40, "height": 20},
        "enabled": True,
    }
    assert is_actionable(ok) is True


def test_is_actionable_wrong_type() -> None:
    e = UIElement(
        id="x",
        type="container",
        bounds=UIBounds(x=0, y=0, width=100, height=100),
        enabled=True,
    )
    assert is_actionable(e) is False


def test_is_actionable_disabled() -> None:
    e = UIElement(
        id="x",
        type="button",
        bounds=UIBounds(x=0, y=0, width=40, height=20),
        enabled=False,
    )
    assert is_actionable(e) is False


def test_is_actionable_input_not_edit() -> None:
    e = UIElement(
        id="x",
        type="input",
        bounds=UIBounds(x=0, y=0, width=200, height=24),
        enabled=True,
    )
    assert is_actionable(e) is True


def test_actionable_types_contains_expected() -> None:
    assert "input" in ACTIONABLE_TYPES
    assert "button" in ACTIONABLE_TYPES
    assert "container" not in ACTIONABLE_TYPES

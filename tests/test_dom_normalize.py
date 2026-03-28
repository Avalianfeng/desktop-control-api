from __future__ import annotations

from dom.normalize import ROLE_MAP, normalize_role


def test_normalize_button_to_action() -> None:
    assert normalize_role("button") == "action"


def test_normalize_input() -> None:
    assert normalize_role("input") == "input"


def test_normalize_custom_to_container() -> None:
    assert normalize_role("custom") == "container"
    assert ROLE_MAP["custom"] == "container"


def test_unmapped_defaults_container() -> None:
    assert normalize_role("weird_type_xyz") == "container"


def test_empty_type_container() -> None:
    assert normalize_role("") == "container"

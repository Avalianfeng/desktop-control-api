from __future__ import annotations

from models.ui_dom import UIBounds
from query.widget_query_engine import WidgetQueryFilters, WidgetQueryRegion, query_widgets
from semantic.widget_types import Widget


def _w(**kwargs) -> Widget:
    base = dict(
        id="w_0",
        type="button",
        role="button",
        text="Save",
        normalized="save",
        bounds=UIBounds(x=10, y=10, width=20, height=20),
        enabled=True,
        visible=True,
        focusable=True,
        uia_path="x",
        parent_id=None,
        automation_id=None,
        runtime_id=None,
        patterns=[],
        value=None,
        meta={},
    )
    base.update(kwargs)
    return Widget(**base)


def test_match_by_normalized_and_enabled() -> None:
    widgets = [_w(normalized="equals", text="="), _w(id="w_1", normalized="save", text="Save", enabled=False)]
    stats, out = query_widgets(
        widgets,
        filters=WidgetQueryFilters(normalized="save", enabled=False),
        window={"left": 0, "top": 0, "width": 100, "height": 100},
        limit=50,
        select=["id", "normalized", "enabled"],
    )
    assert stats["matched"] == 1
    assert out[0]["id"] == "w_1"
    assert out[0]["normalized"] == "save"
    assert out[0]["enabled"] is False


def test_text_contains_case_insensitive() -> None:
    widgets = [_w(text="Save As", normalized="save_as"), _w(id="w_2", text="Open", normalized="open")]
    stats, out = query_widgets(
        widgets,
        filters=WidgetQueryFilters(text_contains="save"),
        window=None,
        limit=50,
        select=["id", "text"],
    )
    assert stats["matched"] == 1
    assert out[0]["text"] == "Save As"


def test_region_preset_bottom_half() -> None:
    window = {"left": 0, "top": 0, "width": 100, "height": 100}
    widgets = [_w(id="top", bounds=UIBounds(x=10, y=10, width=10, height=10)), _w(id="bot", bounds=UIBounds(x=10, y=80, width=10, height=10))]
    stats, out = query_widgets(
        widgets,
        filters=WidgetQueryFilters(region=WidgetQueryRegion(preset="bottom_half")),
        window=window,
        limit=50,
        select=["id"],
    )
    assert stats["matched"] == 1
    assert out[0]["id"] == "bot"


def test_region_rect_intersection() -> None:
    widgets = [_w(id="a", bounds=UIBounds(x=10, y=10, width=10, height=10)), _w(id="b", bounds=UIBounds(x=200, y=200, width=10, height=10))]
    stats, out = query_widgets(
        widgets,
        filters=WidgetQueryFilters(region=WidgetQueryRegion(rect=(0, 0, 50, 50))),
        window=None,
        limit=50,
        select=["id"],
    )
    assert stats["matched"] == 1
    assert out[0]["id"] == "a"


def test_limit_and_select_projection() -> None:
    widgets = [_w(id=f"w_{i}") for i in range(10)]
    stats, out = query_widgets(
        widgets,
        filters=WidgetQueryFilters(),
        window=None,
        limit=3,
        select=["id"],
    )
    assert stats["returned"] == 3
    assert list(out[0].keys()) == ["id"]


def test_ancestor_role_filter() -> None:
    root = _w(id="root", role="button", parent_id=None)
    child = _w(id="child", role="button", parent_id="root")
    grand = _w(id="grand", role="button", parent_id="child")

    stats, out = query_widgets(
        [root, child, grand],
        filters=WidgetQueryFilters(ancestor_role="button"),
        window=None,
        limit=50,
        select=["id"],
    )
    # child has ancestor root(role=button), grand has ancestor child/root; root has none
    assert stats["matched"] == 2
    ids = {r["id"] for r in out}
    assert ids == {"child", "grand"}


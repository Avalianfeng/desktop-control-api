from __future__ import annotations

from dom.semantic import build_semantic_dom
from models.ui_dom import DesktopDOMData, UIBounds, UIElement


def test_build_semantic_counts_and_actionables() -> None:
    btn = UIElement(
        id="w/root/button[0]",
        type="button",
        text="OK",
        bounds=UIBounds(x=10, y=20, width=50, height=30),
        enabled=True,
    )
    ghost = UIElement(
        id="w/root/button[1]",
        type="button",
        text="",
        bounds=UIBounds(x=0, y=0, width=0, height=0),
        enabled=True,
    )
    pane = UIElement(
        id="w/root/container[0]",
        type="container",
        bounds=UIBounds(x=0, y=0, width=100, height=100),
    )
    by_id = {e.id: e for e in (btn, ghost, pane)}
    dom = DesktopDOMData(root=btn, by_id=by_id, by_control_type={})

    sem = build_semantic_dom(dom)
    assert sem.stats.all_elements == 3
    assert sem.stats.actionable_elements == 1
    assert len(sem.elements) == 1
    assert sem.elements[0].id == "sem_0"
    assert sem.elements[0].role == "action"
    assert sem.elements[0].text == "OK"
    assert sem.elements[0].uia_path == btn.id


def test_semantic_include_text_labels() -> None:
    lbl = UIElement(
        id="w/root/text[0]",
        type="text",
        text="Label",
        bounds=UIBounds(x=5, y=5, width=80, height=20),
        enabled=True,
    )
    by_id = {lbl.id: lbl}
    dom = DesktopDOMData(root=lbl, by_id=by_id, by_control_type={})

    sem_off = build_semantic_dom(dom, include_text_labels=False)
    assert len(sem_off.elements) == 0

    sem_on = build_semantic_dom(dom, include_text_labels=True)
    assert len(sem_on.elements) == 1
    assert sem_on.elements[0].role == "text"
    assert sem_on.elements[0].text == "Label"

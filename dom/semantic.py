from __future__ import annotations

from typing import List, Set

from models.ui_dom import DesktopDOMData, UIElement
from models.semantic_dom import SemanticDOMData, SemanticStats

from dom.compress import display_text, to_semantic_element
from dom.filter import is_actionable, is_visible


def _sort_key(el: UIElement) -> tuple[int, int]:
    return (el.bounds.y, el.bounds.x)


def build_semantic_dom(
    dom: DesktopDOMData,
    *,
    include_text_labels: bool = False,
) -> SemanticDOMData:
    """从 Raw `DesktopDOMData` 生成 Semantic DOM：默认可操作元素；可选附带可见文本节点。"""
    by_id = dom.by_id or {}
    all_elements = len(by_id)
    actionable_elements = sum(1 for e in by_id.values() if is_actionable(e))

    stats = SemanticStats(all_elements=all_elements, actionable_elements=actionable_elements)

    actionable_list: List[UIElement] = [e for e in by_id.values() if is_actionable(e)]
    actionable_list.sort(key=_sort_key)

    extras: List[UIElement] = []
    if include_text_labels:
        for e in by_id.values():
            if e.type != "text":
                continue
            if is_actionable(e):
                continue
            if not is_visible(e):
                continue
            if not display_text(e):
                continue
            extras.append(e)
        extras.sort(key=_sort_key)

    seen: Set[str] = set()
    ordered: List[UIElement] = []
    for e in actionable_list + extras:
        if e.id in seen:
            continue
        seen.add(e.id)
        ordered.append(e)

    elements = [to_semantic_element(el, i) for i, el in enumerate(ordered)]

    return SemanticDOMData(stats=stats, elements=elements)

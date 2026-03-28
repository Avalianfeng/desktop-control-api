from __future__ import annotations

from models.ui_dom import UIElement
from models.semantic_dom import SemanticElement

from dom.normalize import normalize_role


def display_text(el: UIElement) -> str:
    """展示文案：优先 text，否则 name。"""
    return (el.text or "").strip() or (el.name or "").strip()


def to_semantic_element(el: UIElement, index: int) -> SemanticElement:
    role = normalize_role(el.type)
    return SemanticElement(
        id=f"sem_{index}",
        role=role,
        text=display_text(el),
        bounds=el.bounds,
        uia_path=el.id,
        source_type=el.type,
    )

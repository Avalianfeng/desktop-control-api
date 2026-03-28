from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from models.ui_dom import UIBounds


class SemanticStats(BaseModel):
    all_elements: int = 0
    actionable_elements: int = 0


class SemanticElement(BaseModel):
    """压缩后的语义节点；text 为展示文案（name 回退）。"""

    id: str
    role: str
    text: str = ""
    bounds: UIBounds
    uia_path: str = ""
    source_type: str = ""


class SemanticDOMData(BaseModel):
    schema_version: str = "desktop_dom_semantic.v1"
    stats: SemanticStats
    elements: List[SemanticElement] = Field(default_factory=list)

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


ElementSource = Literal["uia", "vision"]
ElementStatus = Literal["ok", "degraded", "inferred", "error"]


class UIBounds(BaseModel):
    x: int
    y: int
    width: int
    height: int


class UIElement(BaseModel):
    id: str
    type: str
    text: str = ""
    name: str = ""
    control_type: str = ""
    bounds: UIBounds
    enabled: bool = True
    visible: bool = True
    focusable: bool = False
    source: ElementSource = "uia"
    status: ElementStatus = "ok"
    uia_runtime_id: Optional[str] = None
    uia_automation_id: Optional[str] = None
    uia_patterns: List[str] = Field(default_factory=list)
    uia_value: Optional[str] = None
    uia_labeled_by: Optional[str] = None
    children: List["UIElement"] = Field(default_factory=list)


class UIReadOptions(BaseModel):
    max_depth: int = Field(default=8, ge=1, le=30)
    include_offscreen: bool = False
    include_disabled: bool = True
    include_invisible: bool = False
    include_semantic: bool = True
    semantic_include_text_labels: bool = False


class DOMQualityReport(BaseModel):
    element_count: int = 0
    interactive_count: int = 0
    text_coverage: float = 0.0
    has_root_window: bool = False
    score: float = 0.0


class DesktopDOMData(BaseModel):
    root: Optional[UIElement] = None
    by_id: Dict[str, UIElement] = Field(default_factory=dict)
    by_control_type: Dict[str, List[str]] = Field(default_factory=dict)


class DesktopDOMResponse(BaseModel):
    schema_version: str = "desktop_dom.v1"
    window: Dict[str, object]
    dom: DesktopDOMData
    quality: DOMQualityReport
    stats: Dict[str, object]
    semantic: Optional["SemanticDOMData"] = None


def _rebuild_desktop_dom_response() -> None:
    from models.semantic_dom import SemanticDOMData  # noqa: WPS433

    DesktopDOMResponse.model_rebuild()


_rebuild_desktop_dom_response()

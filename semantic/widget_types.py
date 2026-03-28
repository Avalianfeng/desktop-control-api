from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from models.ui_dom import UIBounds


WidgetRole = Literal[
    "text",
    "button",
    "checkbox",
    "radio",
    "link",
    "textbox",
    "menuitem",
    "tab",
    "listitem",
    "unknown",
]

ACTIONABLE_WIDGET_ROLES: frozenset[str] = frozenset(
    {
        "button",
        "checkbox",
        "radio",
        "link",
        "textbox",
        "menuitem",
        "tab",
        "listitem",
    }
)


class WidgetStats(BaseModel):
    all_elements: int = 0
    widgets: int = 0
    actionable_widgets: int = 0


class Widget(BaseModel):
    id: str
    type: str
    role: WidgetRole
    text: str = ""
    normalized: str = ""
    bounds: UIBounds
    enabled: bool = True
    visible: bool = True
    focusable: bool = False
    uia_path: str
    parent_id: Optional[str] = None
    automation_id: Optional[str] = None
    runtime_id: Optional[str] = None
    patterns: List[str] = Field(default_factory=list)
    value: Optional[str] = None
    meta: Dict[str, object] = Field(default_factory=dict)


class WidgetResponse(BaseModel):
    schema_version: str = "desktop_widgets.v1.2"
    window: Dict[str, object]
    stats: WidgetStats
    widgets: List[Widget] = Field(default_factory=list)


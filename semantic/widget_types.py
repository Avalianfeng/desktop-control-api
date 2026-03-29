from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from models.ui_dom import UIBounds


class WidgetText(BaseModel):
    """
    UIA 主源的文本信号（/widgets/read 路径不混入 OCR）。
    value 为 null 表示 UIA 无可读合并文本，不代表「未跑 OCR」。
    """

    value: Optional[str] = None
    source: Literal["uia", "none"] = "uia"
    confidence: Optional[float] = None

    @classmethod
    def from_uia_merged(cls, merged: str) -> "WidgetText":
        s = (merged or "").strip()
        if not s:
            return cls(value=None, source="none", confidence=None)
        return cls(value=s, source="uia", confidence=1.0)


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
    text: WidgetText = Field(default_factory=lambda: WidgetText.from_uia_merged(""))
    text_legacy: str = Field(
        default="",
        description="与 text.value 相同的扁平字符串；便于过渡期兼容旧客户端。",
    )
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
    schema_version: str = "desktop_widgets.v2"
    window: Dict[str, object]
    stats: WidgetStats
    widgets: List[Widget] = Field(default_factory=list)


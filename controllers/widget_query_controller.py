from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

from controllers.ui_read_controller import UIReadController
from models.ui_dom import UIReadOptions
from query.widget_query_engine import WidgetQueryFilters, query_widgets
from semantic.widget_builder import build_widgets


@dataclass
class WidgetQueryResult:
    window: Dict[str, object]
    stats: Dict[str, int]
    widgets: list[dict]
    partial: bool


class WidgetQueryController:
    def __init__(self):
        self.ui_read_ctrl = UIReadController()

    def query_widgets(
        self,
        *,
        window_title: Optional[str],
        window_hwnd: Optional[int] = None,
        options: UIReadOptions,
        filters: WidgetQueryFilters,
        include_text_widgets: bool,
        collapse_icons: bool,
        limit: int,
        select: Sequence[str],
    ) -> WidgetQueryResult:
        # 强制不生成 semantic：query 端点只关心 widgets
        options = options.model_copy(update={"include_semantic": False})
        result = self.ui_read_ctrl.read_dom(window_title=window_title, window_hwnd=window_hwnd, options=options)

        widgets = build_widgets(
            result.payload.dom,
            window=result.payload.window,
            include_text_widgets=include_text_widgets,
            collapse_icons=collapse_icons,
        )

        stats, out = query_widgets(
            widgets,
            filters=filters,
            window=result.payload.window,
            limit=limit,
            select=select,
        )
        return WidgetQueryResult(window=result.payload.window, stats=stats, widgets=out, partial=result.partial)


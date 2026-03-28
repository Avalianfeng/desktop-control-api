from __future__ import annotations

from typing import Optional, Tuple

from errors import ApiError
from query.widget_query_engine import WidgetQueryFilters as EngineWidgetQueryFilters
from query.widget_query_engine import WidgetQueryRegion as EngineWidgetQueryRegion


def ensure_region_rect(rect: Optional[list[int]], *, name: str) -> Optional[Tuple[int, int, int, int]]:
    if rect is None:
        return None
    if len(rect) != 4:
        raise ApiError(status_code=400, code="invalid_region", message=f"{name} 必须是 [x, y, width, height]")
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        raise ApiError(status_code=400, code="invalid_region", message=f"{name} 的 width 和 height 必须大于 0")
    if x < 0 or y < 0:
        raise ApiError(status_code=400, code="invalid_region", message=f"{name} 的 x 和 y 不能为负数")
    return (int(x), int(y), int(w), int(h))


def to_engine_region(region: object) -> Optional[EngineWidgetQueryRegion]:
    """
    将 API 层的 filters.region（Pydantic 模型）转换为 engine 的 dataclass。
    这里不直接依赖 server.py，避免路由层堆积转换逻辑。
    """
    if region is None:
        return None
    preset = getattr(region, "preset", None)
    rect = getattr(region, "rect", None)
    rect_tuple = ensure_region_rect(rect, name="filters.region.rect") if rect is not None else None
    return EngineWidgetQueryRegion(preset=preset, rect=rect_tuple)


def to_engine_filters(filters: object) -> EngineWidgetQueryFilters:
    region = getattr(filters, "region", None)
    return EngineWidgetQueryFilters(
        role=getattr(filters, "role", None),
        normalized=getattr(filters, "normalized", None),
        type=getattr(filters, "type", None),
        enabled=getattr(filters, "enabled", None),
        visible=getattr(filters, "visible", None),
        focusable=getattr(filters, "focusable", None),
        text_contains=getattr(filters, "text_contains", None),
        ancestor_role=getattr(filters, "ancestor_role", None),
        region=to_engine_region(region),
    )


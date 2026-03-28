from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from models.ui_dom import UIBounds
from semantic.widget_types import Widget


RegionPreset = str  # validated in server request model


@dataclass(frozen=True)
class WidgetQueryRegion:
    preset: Optional[RegionPreset] = None
    rect: Optional[Tuple[int, int, int, int]] = None  # x,y,w,h


@dataclass(frozen=True)
class WidgetQueryFilters:
    role: Optional[str] = None
    normalized: Optional[str] = None
    type: Optional[str] = None
    enabled: Optional[bool] = None
    visible: Optional[bool] = None
    focusable: Optional[bool] = None
    text_contains: Optional[str] = None
    ancestor_role: Optional[str] = None
    region: Optional[WidgetQueryRegion] = None


def _bounds_intersects(a: UIBounds, rect: Tuple[int, int, int, int]) -> bool:
    rx, ry, rw, rh = rect
    if rw <= 0 or rh <= 0:
        return False
    ax1, ay1 = a.x, a.y
    ax2, ay2 = a.x + a.width, a.y + a.height
    bx1, by1 = rx, ry
    bx2, by2 = rx + rw, ry + rh
    return (ax1 < bx2) and (ax2 > bx1) and (ay1 < by2) and (ay2 > by1)


def _window_region_rect(window: dict, preset: RegionPreset) -> Optional[Tuple[int, int, int, int]]:
    try:
        left = int(window.get("left", 0))
        top = int(window.get("top", 0))
        width = int(window.get("width", 0))
        height = int(window.get("height", 0))
    except Exception:
        return None
    if width <= 0 or height <= 0:
        return None

    if preset == "top_half":
        return (left, top, width, height // 2)
    if preset == "bottom_half":
        return (left, top + height // 2, width, height - height // 2)
    if preset == "left_half":
        return (left, top, width // 2, height)
    if preset == "right_half":
        return (left + width // 2, top, width - width // 2, height)
    if preset == "center":
        # center 60%
        cx = left + width / 2.0
        cy = top + height / 2.0
        w = int(width * 0.6)
        h = int(height * 0.6)
        x = int(cx - w / 2.0)
        y = int(cy - h / 2.0)
        return (x, y, w, h)
    return None


def match(
    widget: Widget,
    filters: WidgetQueryFilters,
    *,
    window: Optional[dict] = None,
    by_id: Optional[dict[str, Widget]] = None,
) -> bool:
    if filters.role is not None and widget.role != filters.role:
        return False
    if filters.normalized is not None and widget.normalized != filters.normalized:
        return False
    if filters.type is not None and widget.type != filters.type:
        return False
    if filters.enabled is not None and bool(widget.enabled) is not bool(filters.enabled):
        return False
    if filters.visible is not None and bool(widget.visible) is not bool(filters.visible):
        return False
    if filters.focusable is not None and bool(widget.focusable) is not bool(filters.focusable):
        return False

    if filters.text_contains is not None:
        needle = filters.text_contains.strip().lower()
        if needle:
            if needle not in (widget.text or "").lower():
                return False

    if filters.ancestor_role is not None:
        want = filters.ancestor_role.strip()
        if want:
            if by_id is None:
                return False
            cur = widget
            seen: set[str] = set()
            ok = False
            while True:
                pid = getattr(cur, "parent_id", None)
                if not pid:
                    break
                if pid in seen:
                    break
                seen.add(pid)
                parent = by_id.get(pid)
                if parent is None:
                    break
                if parent.role == want:
                    ok = True
                    break
                cur = parent
            if not ok:
                return False

    region = filters.region
    if region is not None:
        rect = None
        if region.rect is not None:
            rect = region.rect
        elif region.preset and window is not None:
            rect = _window_region_rect(window, region.preset)
        if rect is not None:
            if not _bounds_intersects(widget.bounds, rect):
                return False

    return True


def query_widgets(
    widgets: Sequence[Widget],
    *,
    filters: WidgetQueryFilters,
    window: Optional[dict],
    limit: int,
    select: Sequence[str],
) -> tuple[dict, List[dict]]:
    all_widgets = len(widgets)
    if limit < 0:
        limit = 0

    allowed = set(select)
    by_widget_id: dict[str, Widget] = {w.id: w for w in widgets}

    def _project(w: Widget) -> dict:
        out: dict = {}
        if "id" in allowed:
            out["id"] = w.id
        if "type" in allowed:
            out["type"] = w.type
        if "role" in allowed:
            out["role"] = w.role
        if "text" in allowed:
            out["text"] = w.text
        if "normalized" in allowed:
            out["normalized"] = w.normalized
        if "bounds" in allowed:
            out["bounds"] = w.bounds.model_dump()
        if "enabled" in allowed:
            out["enabled"] = bool(w.enabled)
        if "visible" in allowed:
            out["visible"] = bool(w.visible)
        if "focusable" in allowed:
            out["focusable"] = bool(w.focusable)
        if "uia_path" in allowed:
            out["uia_path"] = w.uia_path
        if "parent_id" in allowed:
            out["parent_id"] = getattr(w, "parent_id", None)
        if "meta" in allowed:
            out["meta"] = w.meta
        return out

    matched = 0
    results: List[dict] = []
    for w in widgets:
        if not match(w, filters, window=window, by_id=by_widget_id):
            continue
        matched += 1
        if len(results) < limit:
            results.append(_project(w))

    stats = {"all_widgets": all_widgets, "matched": matched, "returned": len(results)}
    return stats, results


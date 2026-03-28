from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from models.ui_dom import DOMQualityReport, DesktopDOMData, DesktopDOMResponse, UIBounds, UIElement, UIReadOptions
from sources.uia_source import RawUIANode, RawWindowSnapshot
from observability.metrics import DOM_BUILD_DURATION_MS
from observability.tracing import set_span_attributes, start_span


@dataclass
class BuildResult:
    response: DesktopDOMResponse
    truncated: bool


class DesktopDOMEngine:
    """Build desktop_dom.v1 from raw UIA snapshot."""

    CONTROL_TYPE_MAP: Dict[str, str] = {
        "ButtonControl": "button",
        "EditControl": "input",
        "TextControl": "text",
        "MenuItemControl": "menu_item",
        "MenuControl": "menu",
        "PaneControl": "container",
        "WindowControl": "window",
        "ListControl": "list",
        "ListItemControl": "list_item",
        "CheckBoxControl": "checkbox",
        "RadioButtonControl": "radio",
        "TabControl": "tab",
        "TabItemControl": "tab_item",
    }

    def build(self, snapshot: RawWindowSnapshot, options: UIReadOptions) -> BuildResult:
        start = time.perf_counter()
        window_identity = f"{snapshot.title or 'window'}#{snapshot.hwnd}"
        truncated = False
        reason: Optional[str] = None

        with start_span("dom_build"):
            set_span_attributes(op="dom_build", window_title=snapshot.title, hwnd=snapshot.hwnd)
            try:
                if snapshot.root is None:
                    quality = DOMQualityReport(
                        element_count=0,
                        interactive_count=0,
                        text_coverage=0.0,
                        has_root_window=False,
                        score=0.0,
                    )
                    response = DesktopDOMResponse(
                        window={
                            "title": snapshot.title,
                            "left": snapshot.left,
                            "top": snapshot.top,
                            "width": snapshot.width,
                            "height": snapshot.height,
                            "hwnd": snapshot.hwnd,
                        },
                        dom=DesktopDOMData(root=None, by_id={}, by_control_type={}),
                        quality=quality,
                        stats={
                            "truncated": False,
                            "truncated_reason": None,
                            "uia_time_ms": int((time.perf_counter() - start) * 1000),
                            "fallback_triggered": False,
                            "source_error": snapshot.source_error,
                        },
                    )
                    return BuildResult(response=response, truncated=False)

                root, by_id, by_type, truncated, reason = self._build_tree(snapshot.root, window_identity, options)
                quality = self._analyze_quality(root, by_id)
                response = DesktopDOMResponse(
                    window={
                        "title": snapshot.title,
                        "left": snapshot.left,
                        "top": snapshot.top,
                        "width": snapshot.width,
                        "height": snapshot.height,
                        "hwnd": snapshot.hwnd,
                    },
                    dom=DesktopDOMData(root=root, by_id=by_id, by_control_type=by_type),
                    quality=quality,
                    stats={
                        "truncated": truncated,
                        "truncated_reason": reason,
                        "uia_time_ms": int((time.perf_counter() - start) * 1000),
                        "fallback_triggered": False,
                        "source_error": snapshot.source_error,
                    },
                )
                set_span_attributes(
                    truncated=truncated,
                    truncated_reason=reason,
                    element_count=quality.element_count,
                    interactive_count=quality.interactive_count,
                    uia_time_ms=response.stats.get("uia_time_ms"),
                )
                return BuildResult(response=response, truncated=truncated)
            finally:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                DOM_BUILD_DURATION_MS.labels(
                    truncated=str(truncated).lower(),
                    truncated_reason=reason or "",
                ).observe(elapsed_ms)

    def _build_tree(
        self, root_raw: RawUIANode, window_identity: str, options: UIReadOptions
    ) -> Tuple[Optional[UIElement], Dict[str, UIElement], Dict[str, List[str]], bool, Optional[str]]:
        by_id: Dict[str, UIElement] = {}
        by_type = defaultdict(list)
        truncated = False
        truncated_reason: Optional[str] = None

        root_element = self._to_element(root_raw, node_id=f"{window_identity}/root")
        by_id[root_element.id] = root_element
        by_type[root_element.type].append(root_element.id)

        queue = deque([(root_raw, root_element, 0, {})])
        max_nodes = 1500
        built_nodes = 1

        while queue:
            raw_node, parent_element, depth, sibling_counter = queue.popleft()
            if depth >= options.max_depth:
                if raw_node.children:
                    truncated = True
                    truncated_reason = "max_depth_reached"
                continue

            for child in raw_node.children:
                if not options.include_offscreen and child.offscreen:
                    continue
                if not options.include_disabled and not child.enabled:
                    continue
                visible = not child.offscreen
                if not options.include_invisible and not visible:
                    continue

                key = self._normalize_control_type(child.control_type)
                idx = sibling_counter.get(key, 0)
                sibling_counter[key] = idx + 1
                child_id = f"{parent_element.id}/{key}[{idx}]"
                child_element = self._to_element(child, node_id=child_id)
                parent_element.children.append(child_element)

                by_id[child_id] = child_element
                by_type[child_element.type].append(child_id)
                built_nodes += 1
                if built_nodes >= max_nodes:
                    truncated = True
                    truncated_reason = "max_nodes_reached"
                    break
                queue.append((child, child_element, depth + 1, {}))
            if truncated and truncated_reason == "max_nodes_reached":
                break

        return root_element, by_id, dict(by_type), truncated, truncated_reason

    def _to_element(self, raw: RawUIANode, node_id: str) -> UIElement:
        normalized = self._normalize_control_type(raw.control_type)
        status = "ok" if not raw.error else "degraded"
        return UIElement(
            id=node_id,
            type=normalized,
            text=raw.name,
            name=raw.name,
            control_type=raw.control_type,
            bounds=UIBounds(x=raw.left, y=raw.top, width=raw.width, height=raw.height),
            enabled=raw.enabled,
            visible=not raw.offscreen,
            focusable=getattr(raw, "focusable", False),
            source="uia",
            status=status,  # type: ignore[arg-type]
            uia_runtime_id=(raw.runtime_id or "").strip() or None,
            uia_automation_id=(getattr(raw, "automation_id", "") or "").strip() or None,
            uia_patterns=list(getattr(raw, "patterns", None) or []),
            uia_value=(getattr(raw, "value", "") or "").strip() or None,
            uia_labeled_by=(getattr(raw, "labeled_by", "") or "").strip() or None,
            children=[],
        )

    def _normalize_control_type(self, control_type: str) -> str:
        if control_type in self.CONTROL_TYPE_MAP:
            return self.CONTROL_TYPE_MAP[control_type]
        plain = (control_type or "unknown").replace("Control", "").strip().lower()
        return plain or "unknown"

    def _analyze_quality(self, root: Optional[UIElement], by_id: Dict[str, UIElement]) -> DOMQualityReport:
        if root is None:
            return DOMQualityReport()

        elements = list(by_id.values())
        element_count = len(elements)
        interactive_types = {"button", "input", "menu_item", "checkbox", "radio", "tab_item", "list_item"}
        interactive_count = sum(1 for e in elements if e.type in interactive_types and e.enabled and e.visible)
        text_count = sum(1 for e in elements if (e.text or "").strip())
        text_coverage = text_count / element_count if element_count else 0.0
        has_root = root.type in {"window", "container"} or root.control_type == "WindowControl"

        score = 0.0
        score += min(1.0, element_count / 30.0) * 0.35
        score += min(1.0, interactive_count / 8.0) * 0.35
        score += min(1.0, text_coverage) * 0.2
        score += 0.1 if has_root else 0.0

        return DOMQualityReport(
            element_count=element_count,
            interactive_count=interactive_count,
            text_coverage=round(text_coverage, 4),
            has_root_window=has_root,
            score=round(score, 4),
        )

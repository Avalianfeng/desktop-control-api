from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import pygetwindow as gw


@dataclass
class RawUIANode:
    runtime_id: str
    automation_id: str
    name: str
    value: str
    labeled_by: str
    patterns: List[str]
    control_type: str
    left: int
    top: int
    width: int
    height: int
    enabled: bool
    offscreen: bool
    focusable: bool
    children: List["RawUIANode"] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class RawWindowSnapshot:
    title: str
    hwnd: int
    left: int
    top: int
    width: int
    height: int
    root: Optional[RawUIANode]
    source_error: Optional[str] = None


class UIASource:
    """Raw UIA collector. Do not map/filter/transform here."""

    def probe(self, window_title: Optional[str] = None, window_hwnd: Optional[int] = None) -> dict:
        """
        轻量 readiness 探针：验证窗口句柄可用 + UIAutomation 可访问。
        该方法避免递归遍历整棵 UI 树，减少探针开销。
        """
        window = self._select_window(window_title=window_title, window_hwnd=window_hwnd)
        if not window:
            return {"ok": False, "reason": "no_window", "window_title": window_title}

        hwnd = getattr(window, "_hWnd", None)
        if hwnd is None:
            return {"ok": False, "reason": "no_hwnd", "title": window.title}

        try:
            import uiautomation as auto
        except Exception as exc:
            return {"ok": False, "reason": "uiautomation_missing", "error": str(exc)}

        try:
            ctrl = auto.ControlFromHandle(int(hwnd))
            rect = ctrl.BoundingRectangle
            _ = int(getattr(rect, "left", 0))
            _ = int(getattr(rect, "top", 0))
            return {"ok": True, "title": window.title, "hwnd": int(hwnd)}
        except Exception as exc:
            return {"ok": False, "reason": "uia_unavailable", "error": str(exc)}

    def read_window(self, window_title: Optional[str] = None, window_hwnd: Optional[int] = None) -> RawWindowSnapshot:
        window = self._select_window(window_title=window_title, window_hwnd=window_hwnd)
        if not window:
            if window_hwnd:
                raise FileNotFoundError(f"未找到窗口：hwnd={window_hwnd}")
            raise FileNotFoundError(f"未找到窗口：{window_title}" if window_title else "未找到活动窗口")

        hwnd = getattr(window, "_hWnd", None)
        if hwnd is None:
            raise RuntimeError("窗口句柄不可用")

        try:
            import uiautomation as auto
        except Exception:
            return RawWindowSnapshot(
                title=window.title,
                hwnd=int(hwnd),
                left=window.left,
                top=window.top,
                width=window.width,
                height=window.height,
                root=None,
                source_error="缺少 uiautomation 依赖，请安装：pip install uiautomation",
            )

        root_control = auto.ControlFromHandle(int(hwnd))
        root = self._collect_node(root_control)
        return RawWindowSnapshot(
            title=window.title,
            hwnd=int(hwnd),
            left=window.left,
            top=window.top,
            width=window.width,
            height=window.height,
            root=root,
            source_error=None,
        )

    def _select_window(self, *, window_title: Optional[str], window_hwnd: Optional[int]):
        if window_hwnd:
            try:
                hwnd_i = int(window_hwnd)
            except Exception:
                hwnd_i = 0
            if hwnd_i > 0:
                for w in gw.getAllWindows():
                    try:
                        if int(getattr(w, "_hWnd", 0) or 0) == hwnd_i:
                            return w
                    except Exception:
                        continue
                return None
        if window_title:
            windows = gw.getWindowsWithTitle(window_title)
            return windows[0] if windows else None
        return gw.getActiveWindow()

    def _collect_node(self, control) -> RawUIANode:
        try:
            rect = control.BoundingRectangle
            left = int(getattr(rect, "left", 0))
            top = int(getattr(rect, "top", 0))
            right = int(getattr(rect, "right", left))
            bottom = int(getattr(rect, "bottom", top))
            width = max(0, right - left)
            height = max(0, bottom - top)

            node = RawUIANode(
                runtime_id=self._safe_runtime_id(control),
                automation_id=self._safe_automation_id(control),
                name=str(getattr(control, "Name", "") or ""),
                value=self._safe_value(control),
                labeled_by=self._safe_labeled_by(control),
                patterns=self._infer_patterns(control),
                control_type=self._safe_control_type(control),
                left=left,
                top=top,
                width=width,
                height=height,
                enabled=bool(getattr(control, "IsEnabled", True)),
                offscreen=bool(getattr(control, "IsOffscreen", False)),
                focusable=bool(getattr(control, "IsKeyboardFocusable", False)),
            )

            try:
                children = control.GetChildren()
            except Exception as exc:
                node.error = str(exc)
                return node

            for child in children or []:
                node.children.append(self._collect_node(child))

            return node
        except Exception as exc:
            return RawUIANode(
                runtime_id="unknown",
                automation_id="",
                name="",
                value="",
                labeled_by="",
                patterns=[],
                control_type="Unknown",
                left=0,
                top=0,
                width=0,
                height=0,
                enabled=True,
                offscreen=False,
                focusable=False,
                children=[],
                error=str(exc),
            )

    def _safe_runtime_id(self, control) -> str:
        try:
            rid = control.GetRuntimeId()
            if isinstance(rid, (list, tuple)):
                return ".".join(str(part) for part in rid)
            return str(rid)
        except Exception:
            return "no-runtime-id"

    def _safe_control_type(self, control) -> str:
        try:
            return str(getattr(control, "ControlTypeName", "") or "Unknown")
        except Exception:
            return "Unknown"

    def _safe_automation_id(self, control) -> str:
        try:
            return str(getattr(control, "AutomationId", "") or "")
        except Exception:
            return ""

    def _safe_value(self, control) -> str:
        """
        Best-effort 读取可输入控件的当前值。
        uiautomation 对不同控件暴露的属性不完全一致，因此这里采用多分支兜底。
        """
        try:
            # 常见：EditControl 上可能有 Value 或 CurrentValue 等
            for attr in ("Value", "CurrentValue", "Text", "CurrentName"):
                v = getattr(control, attr, None)
                if isinstance(v, str) and v.strip():
                    return v
            # 一些控件提供 GetValuePattern().Value
            gvp = getattr(control, "GetValuePattern", None)
            if callable(gvp):
                vp = gvp()
                vv = getattr(vp, "Value", None)
                if isinstance(vv, str) and vv.strip():
                    return vv
        except Exception:
            return ""
        return ""

    def _safe_labeled_by(self, control) -> str:
        """
        Best-effort 读取 LabeledBy 关系（如果 UIA 提供）。
        若不可用，返回空字符串；更复杂的“邻近文本推断”放到后续语义层再做。
        """
        try:
            lb = getattr(control, "LabeledBy", None)
            if lb is None:
                return ""
            name = getattr(lb, "Name", None)
            if isinstance(name, str):
                return name.strip()
        except Exception:
            return ""
        return ""

    def _infer_patterns(self, control) -> List[str]:
        """
        在不强依赖 UIA Pattern API 的前提下，基于 uiautomation 常见方法名推断可用模式。
        这能为后续 action（Invoke/Value/Toggle 等）提供低成本的可操作性信号。
        """
        patterns: List[str] = []
        try:
            if callable(getattr(control, "Invoke", None)):
                patterns.append("InvokePattern")
            if callable(getattr(control, "SetValue", None)) or callable(getattr(control, "GetValuePattern", None)):
                patterns.append("ValuePattern")
            if callable(getattr(control, "Toggle", None)):
                patterns.append("TogglePattern")
            if callable(getattr(control, "Expand", None)) or callable(getattr(control, "Collapse", None)):
                patterns.append("ExpandCollapsePattern")
            if callable(getattr(control, "Select", None)):
                patterns.append("SelectionItemPattern")
        except Exception:
            return patterns
        return patterns

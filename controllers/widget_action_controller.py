from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from errors import ApiError
from models.ui_dom import UIReadOptions
from semantic.widget_builder import build_widgets
from semantic.widget_types import Widget
from controllers.ui_read_controller import UIReadController


@dataclass
class WidgetActionResult:
    success: bool
    action: str
    widget_id: str
    locator_source: str | None = None
    window: dict | None = None
    resolved: bool = True
    resolved_by: str | None = None
    candidates: list[dict] | None = None
    verified: bool | None = None
    verify_reason: str | None = None


class WidgetActionController:
    def __init__(self):
        self.ui_read_ctrl = UIReadController()

    def _score_candidate(self, w, fp: dict) -> int:
        score = 0
        want_role = str(fp.get("role") or "").strip()
        want_norm = str(fp.get("normalized") or "").strip()
        want_text = str(fp.get("text") or "").strip()
        want_aid = str(fp.get("automation_id") or "").strip()
        want_anc = fp.get("ancestor_roles") or []
        if want_aid and (w.automation_id or "").strip() == want_aid:
            score += 100
        if want_role and w.role == want_role:
            score += 20
        if want_norm and (w.normalized or "").strip() == want_norm:
            score += 15
        if want_text and ((w.text_legacy or (w.text.value or "") or "").strip() == want_text):
            score += 10
        if want_anc:
            got = ((w.meta or {}).get("fingerprint") or {}).get("ancestor_roles") or []
            # reward common-prefix match (closest ancestors first)
            m = 0
            for a, b in zip(want_anc, got):
                if a != b:
                    break
                m += 1
            score += m * 5
        return score

    def _resolve_widget(
        self,
        *,
        window_title: Optional[str],
        window_hwnd: Optional[int] = None,
        options: UIReadOptions,
        widget_id: str,
        fingerprint: Optional[dict],
        include_text_widgets: bool = True,
        collapse_icons: bool = True,
    ):
        result = self.ui_read_ctrl.read_dom(
            window_title=window_title,
            window_hwnd=window_hwnd,
            options=options.model_copy(update={"include_semantic": False}),
        )
        widgets = build_widgets(
            result.payload.dom,
            window=result.payload.window,
            include_text_widgets=include_text_widgets,
            collapse_icons=collapse_icons,
        )

        for w in widgets:
            if w.id == widget_id:
                return w, result.payload.window, True, "id", None

        fp = fingerprint
        if fp is None:
            # server-side fallback fingerprint from previous locator_key if present in id chain is not available.
            # Keep minimal: no fp means no re-resolution.
            return None, result.payload.window, False, None, None

        scored = sorted(((self._score_candidate(w, fp), w) for w in widgets), key=lambda t: t[0], reverse=True)
        top_score = scored[0][0] if scored else 0
        # require minimal confidence: either automation_id match or decent semantic match
        if top_score < 20:
            cands = [
                {
                    "id": w.id,
                    "role": w.role,
                    "text": w.text_legacy,
                    "normalized": w.normalized,
                    "automation_id": w.automation_id,
                    "score": s,
                }
                for s, w in scored[:5]
                if s > 0
            ]
            return None, result.payload.window, False, "fingerprint", cands or None

        # if ambiguous (close scores), return candidates
        if len(scored) >= 2 and scored[1][0] == top_score:
            cands = [
                {
                    "id": w.id,
                    "role": w.role,
                    "text": w.text_legacy,
                    "normalized": w.normalized,
                    "automation_id": w.automation_id,
                    "score": s,
                }
                for s, w in scored[:5]
            ]
            return None, result.payload.window, False, "fingerprint_ambiguous", cands

        return scored[0][1], result.payload.window, True, "fingerprint", None

    def resolve_widget(
        self,
        *,
        window_title: Optional[str],
        window_hwnd: Optional[int] = None,
        options: UIReadOptions,
        widget_id: str,
        fingerprint: Optional[dict] = None,
        include_text_widgets: bool = True,
        collapse_icons: bool = True,
    ) -> tuple[Widget, dict, bool, Optional[str], Optional[list]]:
        """
        公开解析入口：按 id（及可选 fingerprint）定位 Widget；失败时抛出 ApiError(404)。
        """
        widget, window, resolved_ok, resolved_by, candidates = self._resolve_widget(
            window_title=window_title,
            window_hwnd=window_hwnd,
            options=options,
            widget_id=widget_id,
            fingerprint=fingerprint,
            include_text_widgets=include_text_widgets,
            collapse_icons=collapse_icons,
        )
        if widget is None:
            raise ApiError(
                status_code=404,
                code="widget_not_found",
                message=f"未找到 widget：{widget_id}",
                details={"resolved_by": resolved_by, "candidates": candidates},
            )
        return widget, window, resolved_ok, resolved_by, candidates

    def _find_widget_by_id(
        self,
        *,
        window_title: Optional[str],
        options: UIReadOptions,
        widget_id: str,
        include_text_widgets: bool = True,
        collapse_icons: bool = True,
    ):
        result = self.ui_read_ctrl.read_dom(
            window_title=window_title,
            window_hwnd=None,
            options=options.model_copy(update={"include_semantic": False}),
        )
        widgets = build_widgets(
            result.payload.dom,
            window=result.payload.window,
            include_text_widgets=include_text_widgets,
            collapse_icons=collapse_icons,
        )
        for w in widgets:
            if w.id == widget_id:
                return w, result.payload.window
        return None, result.payload.window

    def click(
        self,
        *,
        window_title: Optional[str],
        options: UIReadOptions,
        widget_id: str,
        fingerprint: Optional[dict] = None,
    ) -> WidgetActionResult:
        widget, window, ok, resolved_by, candidates = self._resolve_widget(
            window_title=window_title,
            options=options,
            widget_id=widget_id,
            fingerprint=fingerprint,
        )
        if widget is None:
            raise ApiError(
                status_code=404,
                code="widget_not_found",
                message=f"未找到 widget：{widget_id}",
                details={"resolved_by": resolved_by, "candidates": candidates},
            )

        # 优先尝试 UIA Invoke（如果可用）；否则退化为按 bounds 中心点鼠标点击
        try:
            import uiautomation as auto  # type: ignore
        except Exception:
            auto = None  # type: ignore

        hwnd = int((window or {}).get("hwnd", 0) or 0)
        invoked = False
        if auto is not None and hwnd:
            try:
                root = auto.ControlFromHandle(hwnd)
                target = self._locate_uia_control(root, widget)
                if target is not None and callable(getattr(target, "Invoke", None)):
                    target.Invoke()
                    invoked = True
            except Exception:
                invoked = False

        if not invoked:
            # Mouse fallback
            cx = int(widget.bounds.x + widget.bounds.width / 2)
            cy = int(widget.bounds.y + widget.bounds.height / 2)
            try:
                import pyautogui  # type: ignore
            except Exception as exc:  # pragma: no cover
                raise ApiError(status_code=500, code="mouse_backend_missing", message="缺少鼠标后端依赖", cause=exc)
            pyautogui.click(cx, cy)

        return WidgetActionResult(
            success=True,
            action="click",
            widget_id=widget.id,
            locator_source=str((widget.meta or {}).get("locator_source") or ""),
            window=window,
            resolved=ok,
            resolved_by=resolved_by,
            candidates=candidates,
        )

    def set_value(
        self,
        *,
        window_title: Optional[str],
        options: UIReadOptions,
        widget_id: str,
        value: str,
        fingerprint: Optional[dict] = None,
        verify: bool = False,
    ) -> WidgetActionResult:
        widget, window, ok, resolved_by, candidates = self._resolve_widget(
            window_title=window_title,
            options=options,
            widget_id=widget_id,
            fingerprint=fingerprint,
        )
        if widget is None:
            raise ApiError(
                status_code=404,
                code="widget_not_found",
                message=f"未找到 widget：{widget_id}",
                details={"resolved_by": resolved_by, "candidates": candidates},
            )

        try:
            import uiautomation as auto  # type: ignore
        except Exception:
            auto = None  # type: ignore

        hwnd = int((window or {}).get("hwnd", 0) or 0)
        set_ok = False
        if auto is not None and hwnd:
            try:
                root = auto.ControlFromHandle(hwnd)
                target = self._locate_uia_control(root, widget)
                if target is not None and callable(getattr(target, "SetValue", None)):
                    target.SetValue(str(value))
                    set_ok = True
            except Exception:
                set_ok = False

        if not set_ok:
            # Focus + keyboard fallback: click textbox center then type.
            cx = int(widget.bounds.x + widget.bounds.width / 2)
            cy = int(widget.bounds.y + widget.bounds.height / 2)
            try:
                import pyautogui  # type: ignore
            except Exception as exc:  # pragma: no cover
                raise ApiError(status_code=500, code="keyboard_backend_missing", message="缺少键盘后端依赖", cause=exc)
            pyautogui.click(cx, cy)
            pyautogui.hotkey("ctrl", "a")
            pyautogui.write(str(value), interval=0.01)

        verified: bool | None = None
        verify_reason: str | None = None
        if verify:
            # Re-read and resolve again to confirm value is applied.
            fp = fingerprint or ((widget.meta or {}).get("fingerprint") if isinstance(widget.meta, dict) else None)
            reread_widget, _, ok2, _, _ = self._resolve_widget(
                window_title=window_title,
                options=options,
                widget_id=widget.id,
                fingerprint=fp if isinstance(fp, dict) else None,
            )
            if reread_widget is None or not ok2:
                verified = False
                verify_reason = "verify_widget_not_resolved"
            else:
                got = (reread_widget.value or "").strip()
                want = (str(value) or "").strip()
                if got == want:
                    verified = True
                else:
                    verified = False
                    verify_reason = "value_not_changed"

        return WidgetActionResult(
            success=True,
            action="set_value",
            widget_id=widget.id,
            locator_source=str((widget.meta or {}).get("locator_source") or ""),
            window=window,
            resolved=ok,
            resolved_by=resolved_by,
            candidates=candidates,
            verified=verified,
            verify_reason=verify_reason,
        )

    def _locate_uia_control(self, root, widget):
        """
        在当前 UIA 树中定位控件（best-effort）。
        优先 automation_id，其次 runtime_id。限制遍历节点数避免卡死。
        """
        target_aid = (widget.automation_id or "").strip()
        target_rid = (widget.runtime_id or "").strip()
        if not target_aid and not target_rid:
            return None

        queue = [root]
        visited = 0
        max_nodes = 4000
        while queue and visited < max_nodes:
            ctrl = queue.pop(0)
            visited += 1
            try:
                if target_aid:
                    aid = str(getattr(ctrl, "AutomationId", "") or "")
                    if aid == target_aid:
                        return ctrl
                if target_rid:
                    try:
                        rid = ctrl.GetRuntimeId()
                        rid_s = ".".join(str(p) for p in rid) if isinstance(rid, (list, tuple)) else str(rid)
                    except Exception:
                        rid_s = ""
                    if rid_s == target_rid:
                        return ctrl
                children = ctrl.GetChildren()
                if children:
                    queue.extend(list(children))
            except Exception:
                continue
        return None


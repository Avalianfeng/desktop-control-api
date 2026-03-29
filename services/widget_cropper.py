from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from controllers.screenshot import ScreenshotController
from controllers.widget_action_controller import WidgetActionController
from controllers.windows import WindowsController
from errors import ApiError
from models.ui_dom import UIReadOptions

_MAX_AREA = 12_000_000
_MAX_WH = 16_384

_log = logging.getLogger(__name__)


class WidgetCropper:
    """widget_id → UIA bounds → 屏幕区域截图（固定落盘目录）。"""

    def __init__(
        self,
        widget_action_ctrl: WidgetActionController,
        screenshot_ctrl: ScreenshotController,
        windows_ctrl: WindowsController,
    ) -> None:
        self._widgets = widget_action_ctrl
        self._shot = screenshot_ctrl
        self._windows = windows_ctrl

    def capture_widget(
        self,
        *,
        widget_id: str,
        window_title: Optional[str],
        target_hwnd: Optional[int],
        fingerprint: Optional[dict],
        max_depth: int,
        include_text_widgets: bool = True,
        collapse_icons: bool = True,
        scale: float = 1.0,
        crop_padding_px: int = 0,
    ) -> Dict[str, Any]:
        options = UIReadOptions(
            max_depth=max_depth,
            include_offscreen=False,
            include_disabled=True,
            include_invisible=False,
            include_semantic=False,
        )

        focus_ok: bool | None = None
        focus_window_meta: Optional[dict] = None
        if target_hwnd is not None:
            focused, ferr = self._windows.focus_by_hwnd(int(target_hwnd), policy="relaxed")
            focus_window_meta = focused if isinstance(focused, dict) else None
            focus_ok = focused is not None and ferr is None
            if not focused:
                if ferr != "focus_failed":
                    raise ApiError(
                        status_code=404,
                        code="window_not_found",
                        message=f"未找到窗口：hwnd={target_hwnd}",
                    )
                _log.warning(
                    "widget_crop: 无法置前窗口，继续按 hwnd 解析 UIA 并尝试 PrintWindow：hwnd=%s",
                    target_hwnd,
                )
            window_title_for_read = None
        else:
            window_title_for_read = window_title

        widget, window, resolved_ok, resolved_by, _candidates = self._widgets.resolve_widget(
            window_title=window_title_for_read,
            window_hwnd=int(target_hwnd) if target_hwnd is not None else None,
            options=options,
            widget_id=widget_id,
            fingerprint=fingerprint,
            include_text_widgets=include_text_widgets,
            collapse_icons=collapse_icons,
        )

        b = widget.bounds
        uia_x, uia_y = int(b.x), int(b.y)
        uia_w, uia_h = int(b.width), int(b.height)
        if uia_w <= 0 or uia_h <= 0:
            raise ApiError(
                status_code=400,
                code="widget_bounds_invalid",
                message="控件 bounds 宽高无效",
                details={"width": uia_w, "height": uia_h},
            )
        if uia_w > _MAX_WH or uia_h > _MAX_WH or uia_w * uia_h > _MAX_AREA:
            raise ApiError(
                status_code=400,
                code="widget_crop_too_large",
                message="裁剪区域过大",
                details={"width": uia_w, "height": uia_h},
            )

        pad = max(0, int(crop_padding_px))
        bx = uia_x - pad
        by = uia_y - pad
        w = uia_w + 2 * pad
        h = uia_h + 2 * pad
        if w > _MAX_WH or h > _MAX_WH or w * h > _MAX_AREA:
            raise ApiError(
                status_code=400,
                code="widget_crop_too_large",
                message="加 padding 后裁剪区域过大，请减小 crop_padding_px",
                details={"width": w, "height": h, "crop_padding_px": pad},
            )

        hwnd_cap = int(target_hwnd) if target_hwnd is not None else int((window or {}).get("hwnd") or 0)

        capture_bounds = {"x": bx, "y": by, "width": w, "height": h}
        if os.name == "nt" and hwnd_cap:
            from controllers.win32_window_capture import clamp_screen_rect_to_client

            def _try_clamp(sx: int, sy: int, sw: int, sh: int) -> tuple[int, int, int, int]:
                try:
                    return clamp_screen_rect_to_client(hwnd_cap, sx, sy, sw, sh)
                except ApiError:
                    return sx, sy, sw, sh

            cx, cy, cw, ch = _try_clamp(bx, by, w, h)
            if cw >= 1 and ch >= 1:
                bx, by, w, h = cx, cy, cw, ch
                capture_bounds = {"x": bx, "y": by, "width": w, "height": h}
            elif pad > 0:
                cx, cy, cw, ch = _try_clamp(uia_x, uia_y, uia_w, uia_h)
                if cw >= 1 and ch >= 1:
                    bx, by, w, h = cx, cy, cw, ch
                    capture_bounds = {"x": bx, "y": by, "width": w, "height": h}
        else:
            bx = max(0, bx)
            by = max(0, by)
            capture_bounds = {"x": bx, "y": by, "width": w, "height": h}

        if os.name == "nt" and hwnd_cap:
            try:
                shot = self._shot.capture_region_via_window_printwindow(
                    hwnd_cap, bx, by, w, h, scale=scale
                )
            except ApiError as exc:
                code = getattr(exc, "code", "") or ""
                if code not in {"widget_crop_outside_client", "print_window_failed"}:
                    raise
                _log.warning(
                    "widget_crop: PrintWindow 失败，回退屏幕 mss：code=%s %s",
                    code,
                    getattr(exc, "message", exc),
                )
                shot = self._shot.capture_region(bx, by, w, h, scale=scale)
        else:
            shot = self._shot.capture_region(bx, by, w, h, scale=scale)

        out: Dict[str, Any] = {
            "image_path": shot["path"],
            "image_width": int(shot.get("width", 0) or 0),
            "image_height": int(shot.get("height", 0) or 0),
            "widget_id": widget.id,
            "bounds": {"x": uia_x, "y": uia_y, "width": uia_w, "height": uia_h},
            "capture_bounds": capture_bounds,
            "crop_padding_px": pad,
            "window": window,
            "resolved_by": resolved_by,
            "resolved_ok": resolved_ok,
            "capture_method": shot.get("capture_method"),
            "widget": {
                "id": widget.id,
                "text": widget.text.model_dump(),
                "text_legacy": widget.text_legacy,
                "role": widget.role,
                "normalized": widget.normalized,
            },
        }
        if focus_ok is not None:
            out["focus_ok"] = focus_ok
        if focus_window_meta is not None and "foreground_verified" in focus_window_meta:
            out["focus_foreground_verified"] = bool(focus_window_meta["foreground_verified"])
        return out

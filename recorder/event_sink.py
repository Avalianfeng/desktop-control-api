from __future__ import annotations

from datetime import datetime, timezone
import ctypes
from typing import Any, Dict, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(v: Any) -> str:
    try:
        return str(v or "")
    except Exception:
        return ""


def _get_any_attr(obj: Any, names: list[str]) -> Any:
    for n in names:
        try:
            if hasattr(obj, n):
                return getattr(obj, n)
        except Exception:
            continue
    return None


def _element_path(sender: Any, max_depth: int = 8) -> str:
    """Best-effort UIA element path from current element to parents."""
    parts = []
    cur = sender
    depth = 0
    while cur is not None and depth < max_depth:
        depth += 1
        name = _safe_str(_get_any_attr(cur, ["Name", "CurrentName"]))
        ctype = _safe_str(_get_any_attr(cur, ["ControlTypeName", "CurrentLocalizedControlType"]))
        label = ctype or "Unknown"
        if name:
            label += f"[{name}]"
        parts.append(label)
        parent_getter = getattr(cur, "GetParentControl", None)
        if callable(parent_getter):
            try:
                cur = parent_getter()
                continue
            except Exception:
                break
        # COM IUIAutomationElement has no direct parent getter without TreeWalker.
        break
    parts.reverse()
    return "/".join(parts)


_user32 = ctypes.windll.user32


def _get_window_text(hwnd: int) -> str:
    try:
        if not isinstance(hwnd, int) or hwnd <= 0:
            return ""
        length = int(_user32.GetWindowTextLengthW(hwnd))
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buf, length + 1)
        return str(buf.value or "")
    except Exception:
        return ""


def _get_class_name(hwnd: int) -> str:
    try:
        if not isinstance(hwnd, int) or hwnd <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, buf, 256)
        return str(buf.value or "")
    except Exception:
        return ""


def _get_top_level_hwnd(hwnd: int) -> int:
    try:
        if not isinstance(hwnd, int) or hwnd <= 0:
            return 0
        GA_ROOT = 2
        top = int(_user32.GetAncestor(hwnd, GA_ROOT))
        return top if top > 0 else hwnd
    except Exception:
        return hwnd if isinstance(hwnd, int) else 0


def _get_foreground_hwnd() -> int:
    try:
        return int(_user32.GetForegroundWindow())
    except Exception:
        return 0


def _native_hwnd(sender: Any) -> int:
    for name in ("CurrentNativeWindowHandle", "NativeWindowHandle"):
        try:
            v = getattr(sender, name, None)
            if v is not None:
                return int(v)
        except Exception:
            continue
    return 0


def extract_control(sender: Any) -> Dict[str, Any]:
    runtime_id = _get_any_attr(sender, ["RuntimeId", "CurrentRuntimeId"])
    if isinstance(runtime_id, (list, tuple)):
        runtime_id_s = "[" + ",".join(str(x) for x in runtime_id) + "]"
    else:
        runtime_id_s = _safe_str(runtime_id)
    has_keyboard_focus = _get_any_attr(sender, ["HasKeyboardFocus", "CurrentHasKeyboardFocus"])
    return {
        "name": _safe_str(_get_any_attr(sender, ["Name", "CurrentName"])),
        "automation_id": _safe_str(_get_any_attr(sender, ["AutomationId", "CurrentAutomationId"])),
        "control_type": _safe_str(_get_any_attr(sender, ["ControlTypeName", "CurrentLocalizedControlType"])),
        "class_name": _safe_str(_get_any_attr(sender, ["ClassName", "CurrentClassName"])),
        "framework_id": _safe_str(_get_any_attr(sender, ["FrameworkId", "CurrentFrameworkId"])),
        "runtime_id": runtime_id_s,
        "has_keyboard_focus": bool(has_keyboard_focus) if isinstance(has_keyboard_focus, bool) else False,
        "path": _element_path(sender),
    }


def extract_window_info(sender: Any) -> Dict[str, Any]:
    cur = sender
    for _ in range(12):
        if cur is None:
            break
        ctype = _safe_str(_get_any_attr(cur, ["ControlTypeName", "CurrentLocalizedControlType"]))
        name = _safe_str(_get_any_attr(cur, ["Name", "CurrentName"]))
        if ctype.lower().startswith("window"):
            hwnd = _native_hwnd(cur)
            return {"title": name, "hwnd": hwnd or 0, "class": _get_class_name(hwnd) if hwnd else ""}
        parent_getter = getattr(cur, "GetParentControl", None)
        if callable(parent_getter):
            try:
                cur = parent_getter()
                continue
            except Exception:
                break
        break
    # Fallback 1: use native window handle to resolve top-level title via Win32.
    hwnd = _native_hwnd(sender)
    if hwnd:
        top = _get_top_level_hwnd(hwnd)
        title = _get_window_text(top) or _get_window_text(hwnd)
        return {"title": title, "hwnd": top or hwnd, "class": _get_class_name(top or hwnd)}
    # Fallback 2: some XAML/UWP elements have NativeWindowHandle=0; infer by foreground window.
    fg = _get_foreground_hwnd()
    if fg:
        top = _get_top_level_hwnd(fg)
        title = _get_window_text(top) or _get_window_text(fg)
        return {"title": title, "hwnd": top or fg, "class": _get_class_name(top or fg)}
    return {"title": "", "hwnd": 0, "class": ""}


def build_invoke_event(sender: Any) -> Dict[str, Any]:
    return {
        "ts": _utc_now_iso(),
        "event": "invoke",
        "window": extract_window_info(sender),
        "control": extract_control(sender),
    }


def build_value_change_event(sender: Any, value: Optional[Any]) -> Dict[str, Any]:
    return {
        "ts": _utc_now_iso(),
        "event": "value_change",
        "window": extract_window_info(sender),
        "control": extract_control(sender),
        "value": _safe_str(value),
    }


def build_named_event(sender: Any, event_name: str, *, event_id: Optional[Any] = None) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "ts": _utc_now_iso(),
        "event": _safe_str(event_name) or "uia_event_raw",
        "window": extract_window_info(sender),
        "control": extract_control(sender),
    }
    if event_id is not None:
        data["event_id"] = _safe_str(event_id)
    return data


def build_uia_event_raw(sender: Any, *, event_id: Optional[Any] = None, property_id: Optional[Any] = None) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "ts": _utc_now_iso(),
        "event": "uia_event_raw",
        "window": extract_window_info(sender),
        "control": extract_control(sender),
    }
    if event_id is not None:
        data["event_id"] = _safe_str(event_id)
    if property_id is not None:
        data["property_id"] = _safe_str(property_id)
    return data


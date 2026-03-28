from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import ctypes


ALLOWED_EVENTS = {"invoke", "selection", "toggle", "expand_collapse", "value_change", "text_change"}


@dataclass(frozen=True)
class IntentContext:
    foreground_hwnd: int
    foreground_title: str


_user32 = ctypes.windll.user32


def _safe_title(v: Any) -> str:
    try:
        return str(v or "").strip()
    except Exception:
        return ""


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


def current_intent_context() -> IntentContext:
    try:
        hwnd = int(_user32.GetForegroundWindow())
    except Exception:
        hwnd = 0
    title = _get_window_text(hwnd) if hwnd else ""
    return IntentContext(foreground_hwnd=hwnd, foreground_title=title)


def _is_scrollbar(control: Dict[str, Any]) -> bool:
    ct = _safe_title(control.get("control_type"))
    if not ct:
        return False
    ct_cf = ct.casefold()
    return ("scrollbar" in ct_cf) or ("滚动条" in ct)


def is_user_intent(event: Dict[str, Any], *, ctx: IntentContext) -> tuple[bool, Optional[str]]:
    et = str(event.get("event") or "")
    control = event.get("control") if isinstance(event.get("control"), dict) else {}
    window = event.get("window") if isinstance(event.get("window"), dict) else {}

    if _is_scrollbar(control):
        return False, "scrollbar"

    # Basic system-noise heuristic: container/pane with empty identity.
    ct = _safe_title(control.get("control_type"))
    name = _safe_title(control.get("name"))
    aid = _safe_title(control.get("automation_id"))
    path = _safe_title(control.get("path"))
    if (not name and not aid) and (ct in {"窗格", "pane", "组", "group", ""} or path in {"", "Unknown"}):
        return False, "system_noise"

    # Active value/text gate: require foreground + keyboard focus.
    if et in {"value_change", "text_change"}:
        has_focus = bool(control.get("has_keyboard_focus") is True)
        hwnd = int(window.get("hwnd") or 0) if isinstance(window.get("hwnd") or 0, int) else 0
        title = _safe_title(window.get("title"))
        same_window = False
        if hwnd and ctx.foreground_hwnd and hwnd == ctx.foreground_hwnd:
            same_window = True
        elif title and ctx.foreground_title and title.casefold() == ctx.foreground_title.casefold():
            same_window = True
        if not same_window:
            return False, "passive_value_text"
        if not has_focus:
            return False, "passive_value_text"

    return True, None


def should_record(event: Dict[str, Any], *, debug: bool = False) -> bool:
    """Return True if event should be written to the main JSONL."""
    et = str(event.get("event") or "")
    if et == "structure_changed":
        return bool(debug)
    return et in ALLOWED_EVENTS


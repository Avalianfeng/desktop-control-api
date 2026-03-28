"""Windows-only helpers for foreground window (ctypes, best-effort).

背景：Windows 有前台窗口限制（Foreground Lock Timeout）。
如果调用进程不具备条件，SetForegroundWindow 可能只导致任务栏闪烁而不前置。
这里实现一个更“强硬”的前置流程：AttachThreadInput + BringWindowToTop + 轮询验证。
"""

from __future__ import annotations

import sys
import time
from typing import Any, Dict, Optional


def get_foreground_hwnd() -> int:
    if sys.platform != "win32":
        return 0
    try:
        import ctypes

        user32 = ctypes.windll.user32
        return int(user32.GetForegroundWindow() or 0)
    except Exception:
        return 0


def is_window_visible(hwnd: int) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        return bool(user32.IsWindowVisible(wintypes.HWND(int(hwnd))))
    except Exception:
        return False


def get_window_rect(hwnd: int) -> Optional[Dict[str, int]]:
    """
    Return window rect and derived width/height/area.
    Returns None if rect cannot be retrieved.
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        r = RECT()
        ok = bool(user32.GetWindowRect(wintypes.HWND(int(hwnd)), ctypes.byref(r)))
        if not ok:
            return None
        width = int(r.right - r.left)
        height = int(r.bottom - r.top)
        area = int(max(0, width) * max(0, height))
        return {
            "left": int(r.left),
            "top": int(r.top),
            "right": int(r.right),
            "bottom": int(r.bottom),
            "width": int(width),
            "height": int(height),
            "area": int(area),
        }
    except Exception:
        return None


def get_window_cloaked(hwnd: int) -> Optional[bool]:
    """
    DWM cloaking: True means the window is not visible to the user (e.g. UWP/ApplicationFrameHost shells).
    Returns None if DWM attribute isn't available.
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        # https://learn.microsoft.com/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute
        DWMWA_CLOAKED = 14
        cloaked = wintypes.DWORD(0)

        dwmapi = ctypes.windll.dwmapi
        res = int(
            dwmapi.DwmGetWindowAttribute(
                wintypes.HWND(int(hwnd)),
                wintypes.DWORD(DWMWA_CLOAKED),
                ctypes.byref(cloaked),
                ctypes.sizeof(cloaked),
            )
        )
        if res != 0:
            return None
        return bool(int(cloaked.value) != 0)
    except Exception:
        return None


def get_class_name(hwnd: int) -> str:
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        buf = ctypes.create_unicode_buffer(256)
        n = int(user32.GetClassNameW(wintypes.HWND(int(hwnd)), buf, len(buf)) or 0)
        if n <= 0:
            return ""
        return str(buf.value)
    except Exception:
        return ""


def force_foreground(hwnd: int, *, wait_ms: int = 500) -> Dict[str, Any]:
    """
    Best-effort bring a window to foreground.

    Returns:
        {"ok": bool, "reason": str, "foreground_hwnd": int}
    """
    if sys.platform != "win32":
        return {"ok": False, "reason": "not_windows", "foreground_hwnd": 0}
    if not hwnd:
        return {"ok": False, "reason": "invalid_hwnd", "foreground_hwnd": 0}

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        SW_RESTORE = 9

        # Restore if minimized
        try:
            if user32.IsIconic(wintypes.HWND(hwnd)):
                user32.ShowWindow(wintypes.HWND(hwnd), SW_RESTORE)
        except Exception:
            pass

        try:
            user32.BringWindowToTop(wintypes.HWND(hwnd))
        except Exception:
            pass

        # Attach threads (current <-> target)
        try:
            cur_tid = int(user32.GetCurrentThreadId() or 0)
        except Exception:
            cur_tid = 0
        try:
            target_tid = int(user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), None) or 0)
        except Exception:
            target_tid = 0

        attached = False
        try:
            if cur_tid and target_tid and cur_tid != target_tid:
                attached = bool(user32.AttachThreadInput(cur_tid, target_tid, True))
        except Exception:
            attached = False

        try:
            user32.SetForegroundWindow(wintypes.HWND(hwnd))
        except Exception:
            pass
        try:
            user32.SetActiveWindow(wintypes.HWND(hwnd))
        except Exception:
            pass

        if attached:
            try:
                user32.AttachThreadInput(cur_tid, target_tid, False)
            except Exception:
                pass

        # Poll until it becomes foreground (or timeout)
        deadline = time.perf_counter() + max(0.0, wait_ms / 1000.0)
        while time.perf_counter() < deadline:
            fg = int(user32.GetForegroundWindow() or 0)
            if fg == int(hwnd):
                return {"ok": True, "reason": "foreground", "foreground_hwnd": fg}
            time.sleep(0.05)
        fg = int(user32.GetForegroundWindow() or 0)
        return {"ok": fg == int(hwnd), "reason": "foreground_timeout", "foreground_hwnd": fg}
    except Exception as exc:
        return {"ok": False, "reason": f"exception:{type(exc).__name__}", "foreground_hwnd": get_foreground_hwnd()}

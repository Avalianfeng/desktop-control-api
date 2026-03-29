"""Windows-only helpers for foreground window (ctypes, best-effort).

背景：Windows 有前台窗口限制（Foreground Lock Timeout）。
流程：AttachThreadInput + SetForegroundWindow + 短等验证；失败则可选 **标题栏物理点击**
（会移动鼠标）再试；再失败则 SW_SHOW + SW_RESTORE；最后按 strict/relaxed 判定。
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any, Dict, Literal, Optional

_log = logging.getLogger(__name__)

ForegroundPolicy = Literal["strict", "relaxed"]


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


def _dword_u32(value: int) -> int:
    """线程 ID / DWORD 返回值：统一为无符号 32 位，避免 ctypes 默认 c_int 溢出。"""
    return int(value) & 0xFFFFFFFF


def _configure_user32_thread_prototypes(user32: Any, wintypes: Any) -> None:
    """AttachThreadInput / GetWindowThreadProcessId 使用 DWORD，避免大 TID 触发 OverflowError。"""
    try:
        import ctypes

        user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.GetCurrentThreadId.argtypes = []
        user32.GetCurrentThreadId.restype = wintypes.DWORD
        user32.AttachThreadInput.argtypes = [
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.BOOL,
        ]
        user32.AttachThreadInput.restype = wintypes.BOOL
    except Exception as exc:  # pragma: no cover
        _log.debug("configure_user32_thread_prototypes skipped: %s", exc)


def _try_activate_via_api(user32: Any, wintypes: Any, hwnd: int) -> None:
    """BringWindowToTop + AttachThreadInput + SetForegroundWindow + SetActiveWindow。"""
    _configure_user32_thread_prototypes(user32, wintypes)
    hwnd_h = wintypes.HWND(int(hwnd))
    try:
        user32.BringWindowToTop(hwnd_h)
    except Exception as exc:
        _log.debug("BringWindowToTop failed: %s", exc)

    cur_tid = 0
    target_tid = 0
    try:
        cur_tid = _dword_u32(int(user32.GetCurrentThreadId() or 0))
    except Exception:
        pass
    try:
        target_tid = _dword_u32(int(user32.GetWindowThreadProcessId(hwnd_h, None) or 0))
    except Exception:
        pass

    attached = False
    try:
        if cur_tid and target_tid and cur_tid != target_tid:
            attached = bool(
                user32.AttachThreadInput(
                    wintypes.DWORD(cur_tid),
                    wintypes.DWORD(target_tid),
                    True,
                )
            )
    except Exception as exc:
        _log.debug("AttachThreadInput failed: %s", exc)

    try:
        user32.SetForegroundWindow(hwnd_h)
    except Exception as exc:
        _log.debug("SetForegroundWindow failed: %s", exc)
    try:
        user32.SetActiveWindow(hwnd_h)
    except Exception as exc:
        _log.debug("SetActiveWindow failed: %s", exc)

    if attached:
        try:
            user32.AttachThreadInput(
                wintypes.DWORD(cur_tid),
                wintypes.DWORD(target_tid),
                False,
            )
        except Exception:
            pass


def _sleep_budget(deadline: float, want: float) -> None:
    rem = deadline - time.perf_counter()
    if rem <= 0:
        return
    time.sleep(min(want, rem))


def force_foreground(
    hwnd: int,
    *,
    wait_ms: int = 500,
    policy: ForegroundPolicy | str = "strict",
    use_titlebar_click: bool = True,
    settle_s: float = 0.2,
) -> Dict[str, Any]:
    """
    Best-effort bring a window to foreground.

    可能移动鼠标（标题栏点击兜底，use_titlebar_click=True 时）。

    Returns:
        {"ok": bool, "reason": str, "foreground_hwnd": int,
         可选 "foreground_verified": bool}
    """
    if sys.platform != "win32":
        return {"ok": False, "reason": "not_windows", "foreground_hwnd": 0}
    if not hwnd:
        return {"ok": False, "reason": "invalid_hwnd", "foreground_hwnd": 0}

    pol: ForegroundPolicy = "relaxed" if policy == "relaxed" else "strict"

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        SW_SHOW = 5
        SW_RESTORE = 9
        hwnd_i = int(hwnd)
        hwnd_h = wintypes.HWND(hwnd_i)

        if not user32.IsWindow(hwnd_h):
            return {"ok": False, "reason": "invalid_or_dead", "foreground_hwnd": get_foreground_hwnd()}

        deadline = time.perf_counter() + max(0.0, wait_ms / 1000.0)

        def _success(fg: int) -> Dict[str, Any]:
            return {
                "ok": True,
                "reason": "foreground",
                "foreground_hwnd": int(fg),
                "foreground_verified": True,
            }

        # Minimized → restore + settle
        try:
            if user32.IsIconic(hwnd_h):
                user32.ShowWindow(hwnd_h, SW_RESTORE)
                _sleep_budget(deadline, settle_s)
        except Exception as exc:
            _log.debug("ShowWindow restore: %s", exc)

        _try_activate_via_api(user32, wintypes, hwnd_i)
        _sleep_budget(deadline, 0.1)
        fg = get_foreground_hwnd()
        if fg == hwnd_i:
            return _success(fg)

        # Title bar click (simulates user input; often satisfies foreground rules)
        if use_titlebar_click:
            rect = get_window_rect(hwnd_i)
            if rect and rect.get("width", 0) > 0 and rect.get("height", 0) > 0:
                tx = int(rect["left"] + rect["width"] // 2)
                ty = int(rect["top"] + 10)
                try:
                    import pyautogui  # type: ignore

                    pyautogui.click(tx, ty)
                except Exception as exc:
                    _log.debug("titlebar pyautogui.click skipped: %s", exc)
                else:
                    _sleep_budget(deadline, 0.2)
                    try:
                        user32.SetForegroundWindow(hwnd_h)
                    except Exception as exc:
                        _log.debug("SetForegroundWindow after titlebar: %s", exc)
                    _sleep_budget(deadline, 0.1)
                    fg = get_foreground_hwnd()
                    if fg == hwnd_i:
                        return _success(fg)

        # SW_SHOW + SW_RESTORE chain
        try:
            user32.ShowWindow(hwnd_h, SW_SHOW)
            user32.ShowWindow(hwnd_h, SW_RESTORE)
        except Exception as exc:
            _log.debug("ShowWindow show/restore: %s", exc)
        _sleep_budget(deadline, 0.1)
        _try_activate_via_api(user32, wintypes, hwnd_i)
        fg = get_foreground_hwnd()
        if fg == hwnd_i:
            return _success(fg)

        # Poll remainder
        while time.perf_counter() < deadline:
            fg = get_foreground_hwnd()
            if fg == hwnd_i:
                return _success(fg)
            _sleep_budget(deadline, 0.05)

        fg = get_foreground_hwnd()
        if fg == hwnd_i:
            return _success(fg)

        if pol == "relaxed" and is_window_visible(hwnd_i):
            _log.warning(
                "force_foreground: 窗口可见但未获前台 (relaxed 放行) hwnd=%s foreground_hwnd=%s",
                hwnd_i,
                fg,
            )
            return {
                "ok": True,
                "reason": "visible_not_foreground",
                "foreground_hwnd": int(fg),
                "foreground_verified": False,
            }

        return {
            "ok": False,
            "reason": "foreground_timeout",
            "foreground_hwnd": int(fg),
        }
    except Exception as exc:
        return {
            "ok": False,
            "reason": f"exception:{type(exc).__name__}",
            "foreground_hwnd": get_foreground_hwnd(),
        }

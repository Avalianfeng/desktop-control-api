"""
Windows 窗口截图：PrintWindow → 内存位图，与 Z-order/遮挡无关（相对屏幕 BitBlt 裁剪）。
"""

from __future__ import annotations

import ctypes
import sys
from typing import Any, Dict, Tuple

from PIL import Image

from errors import ApiError

# winuser.h
PW_CLIENTONLY = 0x00000001
PW_RENDERFULLCONTENT = 0x00000002  # Win 8.1+

BI_RGB = 0


def configure_process_dpi_awareness() -> Dict[str, Any]:
    """
    Per-Monitor DPI Aware v2，使 GetClientRect / 位图尺寸与物理像素一致。
    应在进程早期调用；失败时返回 {"ok": False, "reason": ...}。
    """
    if sys.platform != "win32":
        return {"ok": False, "reason": "not_windows"}
    try:
        user32 = ctypes.windll.user32
        per_monitor_v2 = ctypes.c_void_p(-4)  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        if user32.SetProcessDpiAwarenessContext(per_monitor_v2):
            return {"ok": True, "reason": "per_monitor_v2"}
    except Exception as exc:
        return {"ok": False, "reason": f"exception:{type(exc).__name__}"}
    return {"ok": False, "reason": "set_failed"}


def _last_error() -> int:
    return int(ctypes.windll.kernel32.GetLastError() or 0)


def _client_size(hwnd: int) -> Tuple[int, int]:
    user32 = ctypes.windll.user32
    rect = ctypes.wintypes.RECT()
    if not user32.GetClientRect(ctypes.wintypes.HWND(hwnd), ctypes.byref(rect)):
        raise ApiError(
            status_code=500,
            code="print_window_failed",
            message="GetClientRect 失败",
            details={"hwnd": hwnd, "last_error": _last_error()},
        )
    w = int(rect.right - rect.left)
    h = int(rect.bottom - rect.top)
    if w <= 0 or h <= 0:
        raise ApiError(
            status_code=500,
            code="print_window_failed",
            message="客户区尺寸无效",
            details={"hwnd": hwnd, "width": w, "height": h},
        )
    return w, h


def _window_size(hwnd: int) -> Tuple[int, int]:
    user32 = ctypes.windll.user32
    rect = ctypes.wintypes.RECT()
    if not user32.GetWindowRect(ctypes.wintypes.HWND(hwnd), ctypes.byref(rect)):
        raise ApiError(
            status_code=500,
            code="print_window_failed",
            message="GetWindowRect 失败",
            details={"hwnd": hwnd, "last_error": _last_error()},
        )
    w = int(rect.right - rect.left)
    h = int(rect.bottom - rect.top)
    if w <= 0 or h <= 0:
        raise ApiError(
            status_code=500,
            code="print_window_failed",
            message="窗口矩形尺寸无效",
            details={"hwnd": hwnd, "width": w, "height": h},
        )
    return w, h


def capture_window_printwindow(hwnd: int, *, client_only: bool) -> Image.Image:
    """
    使用 PrintWindow 将窗口绘制到 DIB，返回 RGB PIL.Image。
    client_only=True：仅客户区，flags 含 PW_CLIENTONLY | PW_RENDERFULLCONTENT。
    """
    if sys.platform != "win32":
        raise ApiError(
            status_code=501,
            code="print_window_unsupported",
            message="PrintWindow 仅支持 Windows",
            details={"hwnd": hwnd},
        )
    if not hwnd:
        raise ApiError(
            status_code=500,
            code="print_window_failed",
            message="无效 hwnd",
            details={"hwnd": hwnd},
        )

    if client_only:
        w, h = _client_size(hwnd)
        flags = PW_CLIENTONLY | PW_RENDERFULLCONTENT
    else:
        w, h = _window_size(hwnd)
        flags = PW_RENDERFULLCONTENT

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32),
            ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32),
            ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16),
            ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32),
            ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32),
            ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER)]

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h  # top-down
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB
    bmi.bmiHeader.biSizeImage = w * h * 4

    hdc_win = user32.GetDC(ctypes.wintypes.HWND(hwnd))
    if not hdc_win:
        raise ApiError(
            status_code=500,
            code="print_window_failed",
            message="GetDC 失败",
            details={"hwnd": hwnd, "last_error": _last_error()},
        )

    bits_ptr = ctypes.c_void_p()
    hbitmap = None
    hdc_mem = None
    old_bmp = None
    raw_bytes: bytes = b""
    try:
        hbitmap = gdi32.CreateDIBSection(
            hdc_win,
            ctypes.byref(bmi),
            0,
            ctypes.byref(bits_ptr),
            None,
            0,
        )
        if not hbitmap or not bits_ptr.value:
            raise ApiError(
                status_code=500,
                code="print_window_failed",
                message="CreateDIBSection 失败",
                details={"hwnd": hwnd, "last_error": _last_error(), "width": w, "height": h},
            )

        hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
        if not hdc_mem:
            raise ApiError(
                status_code=500,
                code="print_window_failed",
                message="CreateCompatibleDC 失败",
                details={"hwnd": hwnd, "last_error": _last_error()},
            )

        old_bmp = gdi32.SelectObject(hdc_mem, hbitmap)

        ok = user32.PrintWindow(ctypes.wintypes.HWND(hwnd), hdc_mem, ctypes.c_uint32(flags))
        if not ok:
            err = _last_error()
            raise ApiError(
                status_code=500,
                code="print_window_failed",
                message="PrintWindow 失败",
                details={
                    "hwnd": hwnd,
                    "flags": flags,
                    "last_error": err,
                    "client_only": client_only,
                    "width": w,
                    "height": h,
                },
            )

        total = w * h * 4
        raw_bytes = ctypes.string_at(bits_ptr, total)
    finally:
        if hdc_mem and hbitmap and old_bmp is not None:
            gdi32.SelectObject(hdc_mem, old_bmp)
        if hdc_mem:
            gdi32.DeleteDC(hdc_mem)
        if hbitmap:
            gdi32.DeleteObject(hbitmap)
        user32.ReleaseDC(ctypes.wintypes.HWND(hwnd), hdc_win)

    return Image.frombytes("RGB", (w, h), raw_bytes, "raw", "BGRX")

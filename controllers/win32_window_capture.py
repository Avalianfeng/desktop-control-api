"""
Windows 窗口截图：PrintWindow → 内存位图，与 Z-order/遮挡无关（相对屏幕 BitBlt 裁剪）。
"""

from __future__ import annotations

import ctypes
import sys
from typing import Any, Dict, Tuple

from PIL import Image

from errors import ApiError


def _py_int(v: Any) -> int:
    """统一为 Python int，避免 numpy / ctypes 标量传入 PIL 或 ctypes 字段时溢出。"""
    if v is None:
        return 0
    if hasattr(v, "item") and callable(getattr(v, "item", None)):
        try:
            return int(v.item())
        except Exception:
            pass
    return int(v)


def _i32_field(n: Any, *, field: str) -> int:
    x = _py_int(n)
    if x < -(2**31) or x > 2**31 - 1:
        raise ApiError(
            status_code=500,
            code="print_window_failed",
            message=f"位图 {field} 超出 Win32 LONG 范围",
            details={field: x},
        )
    return x


def _u32_size_image(w: int, h: int) -> int:
    total = _py_int(w) * _py_int(h) * 4
    if total < 0 or total > 0xFFFFFFFF:
        raise ApiError(
            status_code=500,
            code="print_window_failed",
            message="位图 biSizeImage 超出 UINT32 范围",
            details={"width": w, "height": h, "bytes": total},
        )
    return total

# winuser.h
PW_CLIENTONLY = 0x00000001
PW_RENDERFULLCONTENT = 0x00000002  # Win 8.1+

BI_RGB = 0

_printwindow_gdi_prototypes_done = False


def _ensure_printwindow_gdi_prototypes() -> None:
    """
    为 GetDC / CreateDIBSection / PrintWindow 等设置 HWND/HDC 原型。

    未设置时 ctypes 常把句柄当 c_int 传递；64 位下 HDC 等可超过 2^31-1，触发
    ``OverflowError: int too long to convert``（argument 1），微信等窗口较易出现。
    """
    global _printwindow_gdi_prototypes_done
    if _printwindow_gdi_prototypes_done:
        return
    _printwindow_gdi_prototypes_done = True
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    wt = ctypes.wintypes

    user32.GetDC.argtypes = [wt.HWND]
    user32.GetDC.restype = wt.HDC
    user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
    user32.PrintWindow.restype = wt.BOOL

    # LPBITMAPINFO：用地址传递，避免 POINTER(局部 Structure) 注册成本
    gdi32.CreateDIBSection.argtypes = [
        wt.HDC,
        ctypes.c_void_p,
        wt.UINT,
        ctypes.POINTER(ctypes.c_void_p),
        wt.HANDLE,
        wt.DWORD,
    ]
    gdi32.CreateDIBSection.restype = wt.HBITMAP

    gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
    gdi32.CreateCompatibleDC.restype = wt.HDC
    gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
    gdi32.SelectObject.restype = wt.HGDIOBJ
    gdi32.DeleteDC.argtypes = [wt.HDC]
    gdi32.DeleteDC.restype = wt.BOOL
    gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
    gdi32.DeleteObject.restype = wt.BOOL


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
    hwnd = _py_int(hwnd)
    if hwnd < 0:
        hwnd = hwnd & 0xFFFFFFFFFFFFFFFF
    user32 = ctypes.windll.user32
    rect = ctypes.wintypes.RECT()
    if not user32.GetClientRect(ctypes.wintypes.HWND(hwnd), ctypes.byref(rect)):
        raise ApiError(
            status_code=500,
            code="print_window_failed",
            message="GetClientRect 失败",
            details={"hwnd": hwnd, "last_error": _last_error()},
        )
    w = _py_int(rect.right) - _py_int(rect.left)
    h = _py_int(rect.bottom) - _py_int(rect.top)
    if w <= 0 or h <= 0:
        raise ApiError(
            status_code=500,
            code="print_window_failed",
            message="客户区尺寸无效",
            details={"hwnd": hwnd, "width": w, "height": h},
        )
    return w, h


def _window_size(hwnd: int) -> Tuple[int, int]:
    hwnd = _py_int(hwnd)
    if hwnd < 0:
        hwnd = hwnd & 0xFFFFFFFFFFFFFFFF
    user32 = ctypes.windll.user32
    rect = ctypes.wintypes.RECT()
    if not user32.GetWindowRect(ctypes.wintypes.HWND(hwnd), ctypes.byref(rect)):
        raise ApiError(
            status_code=500,
            code="print_window_failed",
            message="GetWindowRect 失败",
            details={"hwnd": hwnd, "last_error": _last_error()},
        )
    w = _py_int(rect.right) - _py_int(rect.left)
    h = _py_int(rect.bottom) - _py_int(rect.top)
    if w <= 0 or h <= 0:
        raise ApiError(
            status_code=500,
            code="print_window_failed",
            message="窗口矩形尺寸无效",
            details={"hwnd": hwnd, "width": w, "height": h},
        )
    return w, h


def client_origin_screen(hwnd: int) -> Tuple[int, int]:
    """客户区左上角在屏幕坐标系中的位置（物理像素）。"""
    if sys.platform != "win32":
        raise ApiError(
            status_code=501,
            code="print_window_unsupported",
            message="ClientToScreen 仅支持 Windows",
            details={"hwnd": hwnd},
        )
    hwnd = _py_int(hwnd)
    if hwnd < 0:
        hwnd = hwnd & 0xFFFFFFFFFFFFFFFF
    user32 = ctypes.windll.user32
    pt = ctypes.wintypes.POINT(0, 0)
    if not user32.ClientToScreen(ctypes.wintypes.HWND(hwnd), ctypes.byref(pt)):
        raise ApiError(
            status_code=500,
            code="print_window_failed",
            message="ClientToScreen 失败",
            details={"hwnd": hwnd, "last_error": _last_error()},
        )
    return _py_int(pt.x), _py_int(pt.y)


def clamp_screen_rect_to_client(
    hwnd: int,
    screen_left: int,
    screen_top: int,
    width: int,
    height: int,
) -> Tuple[int, int, int, int]:
    """
    将屏幕坐标矩形与 hwnd 客户区（屏幕坐标）求交，用于带 padding 的裁剪仍落在 PrintWindow 客户区内。
    若不相交则返回 width/height 为 0。
    """
    if sys.platform != "win32":
        return screen_left, screen_top, width, height
    if width <= 0 or height <= 0:
        return screen_left, screen_top, 0, 0
    ox, oy = client_origin_screen(hwnd)
    cw, ch = _client_size(hwnd)
    clin_r = ox + cw
    clin_b = oy + ch
    il = max(int(screen_left), ox)
    it = max(int(screen_top), oy)
    ir = min(int(screen_left) + int(width), clin_r)
    ib = min(int(screen_top) + int(height), clin_b)
    nw = max(0, ir - il)
    nh = max(0, ib - it)
    return il, it, nw, nh


def capture_client_region_via_printwindow(
    hwnd: int,
    screen_left: int,
    screen_top: int,
    region_width: int,
    region_height: int,
) -> Image.Image:
    """
    PrintWindow 抓取整段客户区后，按屏幕坐标矩形裁剪。
    要求矩形完全落在客户区内（与「整屏 mss 再裁」的可见范围语义对齐，避免静默缺角）。
    """
    hwnd = _py_int(hwnd)
    if hwnd < 0:
        hwnd = hwnd & 0xFFFFFFFFFFFFFFFF
    screen_left = _py_int(screen_left)
    screen_top = _py_int(screen_top)
    region_width = _py_int(region_width)
    region_height = _py_int(region_height)
    if region_width <= 0 or region_height <= 0:
        raise ApiError(
            status_code=400,
            code="print_window_failed",
            message="裁剪区域宽高无效",
            details={"width": region_width, "height": region_height},
        )
    full = capture_window_printwindow(hwnd, client_only=True)
    cw, ch = full.size
    ox, oy = client_origin_screen(hwnd)
    right_excl = screen_left + region_width
    bottom_excl = screen_top + region_height
    if screen_left < ox or screen_top < oy or right_excl > ox + cw or bottom_excl > oy + ch:
        raise ApiError(
            status_code=400,
            code="widget_crop_outside_client",
            message="控件区域不完全落在窗口客户区内，无法使用 PrintWindow 裁剪",
            details={
                "hwnd": hwnd,
                "screen_rect": {
                    "left": screen_left,
                    "top": screen_top,
                    "width": region_width,
                    "height": region_height,
                },
                "client_screen": {"left": ox, "top": oy, "width": cw, "height": ch},
            },
        )
    rl = _py_int(screen_left - ox)
    rt = _py_int(screen_top - oy)
    rw = _py_int(region_width)
    rh = _py_int(region_height)
    return full.crop((rl, rt, rl + rw, rt + rh))


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
    hwnd = _py_int(hwnd)
    if hwnd < 0:
        hwnd = hwnd & 0xFFFFFFFFFFFFFFFF
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
    w = _py_int(w)
    h = _py_int(h)

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    _ensure_printwindow_gdi_prototypes()

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
    bmi.bmiHeader.biWidth = _i32_field(w, field="biWidth")
    bmi.bmiHeader.biHeight = _i32_field(-h, field="biHeight")  # top-down
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB
    bmi.bmiHeader.biSizeImage = _u32_size_image(w, h)

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
            ctypes.c_void_p(ctypes.addressof(bmi)),
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

        ok = user32.PrintWindow(
            ctypes.wintypes.HWND(hwnd),
            hdc_mem,
            ctypes.wintypes.UINT(_py_int(flags) & 0xFFFFFFFF),
        )
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

        total = _u32_size_image(w, h)
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

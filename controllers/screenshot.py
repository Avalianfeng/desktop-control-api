"""
截图控制器
使用 mss 库进行高性能截图（比 PyAutoGUI 更快）
"""

import base64
import hashlib
import os
import time
from io import BytesIO
from pathlib import Path
from typing import Optional, List, Dict, Any

import mss
from PIL import Image
import pygetwindow as gw

from errors import ApiError

if os.name == "nt":
    from controllers.win32_win import force_foreground
    from controllers.win32_window_capture import capture_window_printwindow
else:
    force_foreground = None  # type: ignore[misc, assignment]
    capture_window_printwindow = None  # type: ignore[misc, assignment]


def _public_path(local_path: str) -> str:
    """API 返回用：绝对路径 + 正斜杠，避免相对路径或反斜杠在某些客户端下异常。"""
    return str(Path(local_path).resolve()).replace("\\", "/")


def _artifacts_screenshot_root() -> Path:
    return (Path.cwd() / "updates" / "screenshots").resolve()


class ScreenshotController:
    """截图控制器"""
    
    def __init__(self):
        self.sct = mss.mss()
    
    def _default_screenshot_dir(self) -> str:
        """绝对路径：项目下 updates/screenshots/YYYY-MM-DD（UTC 日期）。"""
        d = time.strftime("%Y-%m-%d", time.gmtime())
        return str((_artifacts_screenshot_root() / d).resolve())

    def capture(self, region: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        截取屏幕
        
        Args:
            region: 截图区域 [x, y, width, height]，None 表示全屏
            
        Returns:
            {
                "base64": "Base64 编码的 PNG 图片",
                "width": 图片宽度，
                "height": 图片高度
            }
        """
        monitor_index = None
        monitor = None
        last_exc: Exception | None = None
        try:
            if region:
                monitor = {
                    "left": region[0],
                    "top": region[1],
                    "width": region[2],
                    "height": region[3],
                }
            else:
                # mss 约定：monitors[0] 是虚拟屏总区域；monitors[1] 通常为主屏
                monitor_index = 1 if len(self.sct.monitors) > 1 else 0
                monitor = self.sct.monitors[monitor_index]

            def _grab():
                return self.sct.grab(monitor)

            try:
                screenshot = _grab()
            except Exception as e:
                last_exc = e
                # best-effort: recreate mss object and retry once
                try:
                    self.sct = mss.mss()
                    screenshot = _grab()
                    last_exc = None
                except Exception as e2:
                    last_exc = e2
                    raise
            
            # 转换为 PIL Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            
            # 转换为 Base64
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            
            return {
                "base64": img_base64,
                "width": img.width,
                "height": img.height
            }
            
        except Exception as e:
            raise ApiError(
                status_code=500,
                code="screenshot_failed",
                message="截图失败",
                cause=e,
                details={
                    "region": region,
                    "monitor_index": monitor_index,
                    "monitor_rect": monitor,
                    "error_type": type((last_exc or e)).__name__,
                    "error_message": str((last_exc or e)),
                },
            )

    def capture_to_file(self, region: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        截图并保存到固定目录：updates/screenshots/<UTC YYYY-MM-DD>/。

        Returns:
            { "path", "bytes", "sha256_8", "width", "height", "format" }
        """
        resolved = self._default_screenshot_dir()
        os.makedirs(resolved, exist_ok=True)

        image_data = self.capture(region=region)
        b64 = image_data["base64"]
        raw = base64.b64decode(b64)
        sha256_8 = hashlib.sha256(raw).hexdigest()[:8]

        ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        filename = f"screenshot_{ts}_{sha256_8}.png"
        path = os.path.join(resolved, filename)
        with open(path, "wb") as f:
            f.write(raw)

        return {
            "format": "png",
            "path": _public_path(path),
            "bytes": len(raw),
            "sha256_8": sha256_8,
            "width": int(image_data["width"]),
            "height": int(image_data["height"]),
        }

    def capture_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        scale: float = 1.0,
        *,
        include_image: bool = False,
    ) -> Dict[str, Any]:
        """
        截取屏幕矩形区域（mss 合成图），缩放后写入固定目录。
        默认返回 path/bytes/sha256_8；include_image=True 时额外返回 image（base64）。
        """
        if width <= 0 or height <= 0:
            raise ValueError("width 和 height 必须大于 0")

        image_data = self.capture(region=[x, y, width, height])
        img = self._decode_base64_to_image(image_data["base64"])
        img = self._resize_if_needed(img, scale)

        resolved = self._default_screenshot_dir()
        os.makedirs(resolved, exist_ok=True)

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        raw = buffer.getvalue()
        sha256_8 = hashlib.sha256(raw).hexdigest()[:8]
        ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        filename = f"screenshot_{ts}_{sha256_8}.png"
        file_path = Path(resolved) / filename
        with open(file_path, "wb") as f:
            f.write(raw)

        out: Dict[str, Any] = {
            "format": "png",
            "path": _public_path(str(file_path)),
            "bytes": len(raw),
            "sha256_8": sha256_8,
            "width": img.width,
            "height": img.height,
            "capture_method": "screen_region",
        }
        if include_image:
            out["image"] = base64.b64encode(raw).decode("utf-8")
        return out

    def capture_window(
        self,
        title: str,
        include_decorations: bool = False,
        scale: float = 1.0,
        *,
        include_image: bool = False,
    ) -> Dict[str, Any]:
        """
        按窗口标题截图，支持可选排除装饰区域。
        Windows：PrintWindow 内存位图（与 Z-order 遮挡无关）；其它平台：屏幕矩形裁剪（mss）。
        落盘目录与 capture_to_file 相同；include_image=True 时额外返回 image（base64 PNG）。
        """
        windows = gw.getWindowsWithTitle(title)
        if not windows:
            raise FileNotFoundError(f"未找到窗口：{title}")

        window = windows[0]
        if window.isMinimized:
            try:
                window.restore()
            except Exception:
                pass
            time.sleep(0.2)

        capture_method = "screen_region_fallback"
        hwnd = int(getattr(window, "_hWnd", 0) or 0)

        if os.name == "nt" and capture_window_printwindow is not None and hwnd:
            if force_foreground is not None:
                try:
                    force_foreground(hwnd)
                except Exception:
                    pass
            try:
                window.activate()
            except Exception:
                pass
            time.sleep(0.1)
            refreshed = gw.getWindowsWithTitle(title)
            if refreshed:
                window = refreshed[0]
                hwnd = int(getattr(window, "_hWnd", 0) or 0)
            try:
                img = capture_window_printwindow(
                    hwnd, client_only=not include_decorations
                )
                capture_method = "print_window"
            except ApiError:
                raise
            except Exception as e:
                raise ApiError(
                    status_code=500,
                    code="print_window_failed",
                    message="窗口 PrintWindow 截图失败",
                    cause=e,
                    details={"hwnd": hwnd, "title": title},
                )
        else:
            region = self._window_region(window, include_decorations=include_decorations)
            image_data = self.capture(region=region)
            img = self._decode_base64_to_image(image_data["base64"])

        img = self._resize_if_needed(img, scale)

        resolved = self._default_screenshot_dir()
        os.makedirs(resolved, exist_ok=True)

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        raw = buffer.getvalue()
        sha256_8 = hashlib.sha256(raw).hexdigest()[:8]
        ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        filename = f"screenshot_{ts}_{sha256_8}.png"
        file_path = Path(resolved) / filename
        with open(file_path, "wb") as f:
            f.write(raw)

        out: Dict[str, Any] = {
            "format": "png",
            "path": _public_path(str(file_path)),
            "bytes": len(raw),
            "sha256_8": sha256_8,
            "width": img.width,
            "height": img.height,
            "capture_method": capture_method,
            "window": {
                "title": window.title,
                "left": window.left,
                "top": window.top,
                "width": window.width,
                "height": window.height,
            },
        }
        if include_image:
            out["image"] = base64.b64encode(raw).decode("utf-8")
        return out

    def _window_region(self, window: Any, include_decorations: bool) -> List[int]:
        if include_decorations:
            return [window.left, window.top, window.width, window.height]

        if os.name != "nt":
            return [window.left, window.top, window.width, window.height]

        client = self._get_client_rect(window._hWnd)
        return [
            client["left"],
            client["top"],
            client["right"] - client["left"],
            client["bottom"] - client["top"],
        ]

    def _get_client_rect(self, hwnd: int) -> Dict[str, int]:
        import ctypes

        rect = ctypes.wintypes.RECT()
        if not ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect)):
            raise RuntimeError("GetClientRect 调用失败")

        point = ctypes.wintypes.POINT(rect.left, rect.top)
        if not ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(point)):
            raise RuntimeError("ClientToScreen 调用失败")

        return {
            "left": point.x,
            "top": point.y,
            "right": point.x + (rect.right - rect.left),
            "bottom": point.y + (rect.bottom - rect.top),
        }

    def _decode_base64_to_image(self, image_base64: str) -> Image.Image:
        data = base64.b64decode(image_base64)
        return Image.open(BytesIO(data))

    def _resize_if_needed(self, img: Image.Image, scale: float) -> Image.Image:
        if scale == 1.0:
            return img
        new_width = max(1, int(img.width * scale))
        new_height = max(1, int(img.height * scale))
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def get_monitor_info(self) -> List[Dict[str, Any]]:
        """获取显示器信息"""
        monitors = []
        for i, monitor in enumerate(self.sct.monitors):
            monitors.append({
                "index": i,
                "left": monitor["left"],
                "top": monitor["top"],
                "width": monitor["width"],
                "height": monitor["height"]
            })
        return monitors

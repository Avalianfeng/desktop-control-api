"""
窗口控制器
使用 PyGetWindow 进行窗口管理
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any, Tuple
import pygetwindow as gw

from controllers.win32_win import (
    force_foreground,
    get_class_name,
    get_window_cloaked,
    get_window_rect,
    is_window_visible,
)


_AREA_THRESHOLD = 64 * 64
_TITLE_BLACKLIST_EXACT = {"Program Manager"}


class WindowsController:
    """窗口控制器"""
    
    def __init__(self):
        pass

    @staticmethod
    def _is_interactive(title: str, hwnd: int, area: Optional[int], is_visible: Optional[bool], is_cloaked: Optional[bool]) -> bool:
        if hwnd <= 0:
            return False
        t = (title or "").strip()
        if not t:
            return False
        if t in _TITLE_BLACKLIST_EXACT:
            return False
        if area is not None and int(area) < _AREA_THRESHOLD:
            return False
        if is_visible is False:
            return False
        if is_cloaked is True:
            return False
        return True

    @staticmethod
    def _filter_reasons(title: str, hwnd: int, area: Optional[int], is_visible: Optional[bool], is_cloaked: Optional[bool]) -> List[str]:
        reasons: List[str] = []
        if hwnd <= 0:
            reasons.append("invalid_hwnd")
        t = (title or "").strip()
        if not t:
            reasons.append("empty_title")
        if t in _TITLE_BLACKLIST_EXACT:
            reasons.append("system_root_window")
        if area is not None and int(area) < _AREA_THRESHOLD:
            reasons.append("tiny_area")
        if is_visible is False:
            reasons.append("not_visible")
        if is_cloaked is True:
            reasons.append("cloaked")
        return reasons
    
    def list_all(self) -> List[Dict[str, Any]]:
        """
        列出所有窗口
        
        Returns:
            窗口信息列表
        """
        windows: List[Dict[str, Any]] = []
        active = gw.getActiveWindow()
        active_hwnd = int(getattr(active, "_hWnd", 0) or 0) if active is not None else 0

        for w in gw.getAllWindows():
            try:
                hwnd = int(getattr(w, "_hWnd", 0) or 0)
                title = w.title
                rect = get_window_rect(hwnd) if hwnd else None
                is_visible = is_window_visible(hwnd) if hwnd else False
                is_cloaked = get_window_cloaked(hwnd) if hwnd else None
                class_name = get_class_name(hwnd) if hwnd else ""
                area = int(rect.get("area", 0)) if rect else int(
                    max(0, int(getattr(w, "width", 0) or 0)) * max(0, int(getattr(w, "height", 0) or 0))
                )
                is_interactive = self._is_interactive(
                    title=title, hwnd=hwnd, area=area, is_visible=is_visible, is_cloaked=is_cloaked
                )
                filter_reasons = self._filter_reasons(
                    title=title, hwnd=hwnd, area=area, is_visible=is_visible, is_cloaked=is_cloaked
                )
                windows.append(
                    {
                        "hwnd": hwnd,
                        "title": title,
                        "left": w.left,
                        "top": w.top,
                        "width": w.width,
                        "height": w.height,
                        "is_active": bool(hwnd and active_hwnd and hwnd == active_hwnd),
                        "is_minimized": bool(getattr(w, "isMinimized", False)),
                        "is_maximized": bool(getattr(w, "isMaximized", False)),
                        "is_visible": bool(is_visible),
                        "is_cloaked": is_cloaked,
                        "class_name": class_name,
                        "rect": rect,
                        "area": int(area),
                        "is_interactive": bool(is_interactive),
                        "can_focus": bool(is_interactive),
                        "filter_reasons": filter_reasons,
                    }
                )
            except Exception:
                # 跳过无法访问的窗口
                continue
        windows.sort(key=lambda x: ((x.get("title") or "").casefold(), int(x.get("hwnd") or 0)))
        return windows

    def list_interactive(self) -> List[Dict[str, Any]]:
        """
        默认交互窗口（省 token）。
        Shape: [{"hwnd": int, "title": str}]
        """
        full = self.list_all()
        out: List[Dict[str, Any]] = []
        for w in full:
            if not bool(w.get("is_interactive")):
                continue
            out.append({"hwnd": int(w.get("hwnd") or 0), "title": str(w.get("title") or "")})
        out.sort(key=lambda x: ((x.get("title") or "").casefold(), int(x.get("hwnd") or 0)))
        return out
    
    def find_by_title(self, title: str) -> Optional[Any]:
        """
        根据标题查找窗口（部分匹配）
        
        Args:
            title: 窗口标题（支持部分匹配）
            
        Returns:
            窗口对象，未找到返回 None
        """
        windows = gw.getWindowsWithTitle(title)
        return windows[0] if windows else None
    
    def focus(
        self,
        title: str,
        title_match_index: int = 0,
        *,
        policy: str = "strict",
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        聚焦/激活窗口（按标题子串匹配，见 pygetwindow.getWindowsWithTitle）。

        Args:
            title: 标题子串（大小写不敏感）
            title_match_index: 多个匹配窗口时的下标（0 起）；默认第一个
            policy: \"strict\" 须真前台；\"relaxed\" 可见未前台也可视为成功（见 win32_win.force_foreground）

        Returns:
            (window_dict, None) 成功；(None, \"not_found\") / (None, \"focus_failed\")
        """
        matches = gw.getWindowsWithTitle(title)
        if not matches:
            return None, "not_found"
        if title_match_index < 0 or title_match_index >= len(matches):
            return None, "not_found"
        window = matches[title_match_index]
        wh = int(getattr(window, "_hWnd", 0) or 0)
        try:
            fg = force_foreground(wh, policy=policy)
            if not fg.get("ok"):
                return None, "focus_failed"
            window.activate()
            win_out: Dict[str, Any] = {
                "hwnd": wh,
                "title": window.title,
                "left": window.left,
                "top": window.top,
                "width": window.width,
                "height": window.height,
            }
            if "foreground_verified" in fg:
                win_out["foreground_verified"] = bool(fg["foreground_verified"])
            return win_out, None
        except Exception:
            return None, "focus_failed"

    def focus_by_hwnd(
        self,
        hwnd: int,
        *,
        policy: str = "strict",
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        按 hwnd 聚焦窗口（避免同名 title 歧义）。

        Args:
            policy: \"strict\" 须真前台；\"relaxed\" 可见未前台也可视为成功。

        Returns:
            (window_dict, None) 成功；(None, \"not_found\") / (None, \"focus_failed\")
        """
        try:
            hwnd_i = int(hwnd)
        except Exception:
            return None, "not_found"
        if hwnd_i <= 0:
            return None, "not_found"

        for w in gw.getAllWindows():
            try:
                wh = int(getattr(w, "_hWnd", 0) or 0)
                if wh != hwnd_i:
                    continue
                fg = force_foreground(wh, policy=policy)
                if not fg.get("ok"):
                    return None, "focus_failed"
                try:
                    w.activate()
                except Exception:
                    return None, "focus_failed"
                win_out = {
                    "hwnd": wh,
                    "title": w.title,
                    "left": w.left,
                    "top": w.top,
                    "width": w.width,
                    "height": w.height,
                }
                if "foreground_verified" in fg:
                    win_out["foreground_verified"] = bool(fg["foreground_verified"])
                return win_out, None
            except Exception:
                continue
        return None, "not_found"
    
    def move(self, title: str, x: int, y: int, 
             width: Optional[int] = None, height: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        移动/调整窗口
        
        Args:
            title: 窗口标题
            x: 新 X 坐标
            y: 新 Y 坐标
            width: 新宽度（可选）
            height: 新高度（可选）
            
        Returns:
            窗口信息，未找到返回 None
        """
        window = self.find_by_title(title)
        if window:
            try:
                # 移动窗口
                window.moveTo(x, y)
                
                # 调整大小（如果指定）
                if width is not None and height is not None:
                    window.resizeTo(width, height)
                elif width is not None:
                    window.resizeTo(width, window.height)
                elif height is not None:
                    window.resizeTo(window.width, height)
                
                return {
                    "title": window.title,
                    "left": window.left,
                    "top": window.top,
                    "width": window.width,
                    "height": window.height
                }
            except Exception:
                return None
        return None
    
    def minimize(self, title: str) -> bool:
        """最小化窗口"""
        window = self.find_by_title(title)
        if window:
            try:
                window.minimize()
                return True
            except Exception:
                return False
        return False
    
    def maximize(self, title: str) -> bool:
        """最大化窗口"""
        window = self.find_by_title(title)
        if window:
            try:
                window.maximize()
                return True
            except Exception:
                return False
        return False
    
    def close(self, title: str) -> bool:
        """关闭窗口"""
        window = self.find_by_title(title)
        if window:
            try:
                window.close()
                return True
            except Exception:
                return False
        return False
    
    def get_active_window(self) -> Optional[Dict[str, Any]]:
        """获取当前活动窗口"""
        window = gw.getActiveWindow()
        if window:
            return {
                "hwnd": int(getattr(window, "_hWnd", 0) or 0),
                "title": window.title,
                "left": window.left,
                "top": window.top,
                "width": window.width,
                "height": window.height
            }
        return None

    def get_active_hwnd(self) -> int:
        window = gw.getActiveWindow()
        return int(getattr(window, "_hWnd", 0) or 0) if window is not None else 0

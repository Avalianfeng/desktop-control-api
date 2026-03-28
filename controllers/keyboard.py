"""
键盘控制器
使用 PyAutoGUI 进行键盘操作
"""

import pyautogui
from typing import List


class KeyboardController:
    """键盘控制器"""
    
    def __init__(self):
        pyautogui.PAUSE = 0.1
    
    def type_text(self, text: str, interval: float = 0.05) -> None:
        """
        输入文本。纯 ASCII 走 pyautogui.write；含非 ASCII 时优先剪贴板粘贴（更可靠的中文等输入）。
        """
        if not text:
            return
        if all(ord(c) < 128 for c in text):
            pyautogui.write(text, interval=interval)
            return
        try:
            import pyperclip

            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
        except Exception:
            pyautogui.write(text, interval=interval)
    
    def press(self, key: str, presses: int = 1, interval: float = 0.1) -> None:
        """
        按键
        
        Args:
            key: 按键名称
                特殊键：enter, tab, escape, space, backspace, delete,
                       up, down, left, right, home, end, pageup, pagedown,
                       f1-f12, shift, ctrl, alt, win
            presses: 按压次数
            interval: 每次按压间隔（秒）
        """
        pyautogui.press(key, presses=presses, interval=interval)
    
    def hotkey(self, keys: List[str]) -> None:
        """
        快捷键组合
        
        Args:
            keys: 按键列表，如 ['ctrl', 'c'] 或 ['alt', 'tab']
        """
        if not keys:
            raise ValueError("快捷键组合不能为空")
        
        # 支持字符串或列表
        if isinstance(keys, str):
            keys = keys.split('+')
        
        pyautogui.hotkey(*keys)
    
    def key_down(self, key: str) -> None:
        """按下键（不释放）"""
        pyautogui.keyDown(key)
    
    def key_up(self, key: str) -> None:
        """释放键"""
        pyautogui.keyUp(key)

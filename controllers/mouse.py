"""
鼠标控制器
使用 PyAutoGUI 进行鼠标操作
"""

import pyautogui
from typing import Optional


class MouseController:
    """鼠标控制器"""
    
    def __init__(self):
        # 关闭安全延迟（生产环境可开启）
        pyautogui.PAUSE = 0.1
        pyautogui.FAILSAFE = True  # 鼠标移到屏幕角落可中止
    
    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> None:
        """
        鼠标点击
        
        Args:
            x: X 坐标
            y: Y 坐标
            button: 按钮 (left/right/middle)
            clicks: 点击次数 (1=单击，2=双击)
        """
        # 先移动到目标位置
        pyautogui.moveTo(x, y, duration=0.2)
        
        # 执行点击
        if clicks == 1:
            pyautogui.click(x, y, button=button)
        elif clicks == 2:
            pyautogui.doubleClick(x, y, button=button)
        else:
            for _ in range(clicks):
                pyautogui.click(x, y, button=button)
    
    def move(self, x: int, y: int, duration: float = 0.5) -> None:
        """
        鼠标移动
        
        Args:
            x: 目标 X 坐标
            y: 目标 Y 坐标
            duration: 移动时间（秒）
        """
        pyautogui.moveTo(x, y, duration=duration)
    
    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, 
             duration: float = 0.5, button: str = "left") -> None:
        """
        鼠标拖拽
        
        Args:
            start_x: 起始 X 坐标
            start_y: 起始 Y 坐标
            end_x: 结束 X 坐标
            end_y: 结束 Y 坐标
            duration: 拖拽时间（秒）
            button: 使用的按钮
        """
        # 移动到起始位置
        pyautogui.moveTo(start_x, start_y, duration=duration/2)
        
        # 按下鼠标
        pyautogui.mouseDown(button=button)
        
        # 拖拽到结束位置
        pyautogui.moveTo(end_x, end_y, duration=duration/2)
        
        # 释放鼠标
        pyautogui.mouseUp(button=button)
    
    def scroll(
        self,
        amount: int,
        x: Optional[int] = None,
        y: Optional[int] = None,
        horizontal: int = 0,
        duration: float = 0.1,
    ) -> None:
        """
        滚动滚轮
        
        Args:
            amount: 垂直滚动量（正数向上，负数向下）
            x: X 坐标（可选，默认屏幕中心）
            y: Y 坐标（可选，默认屏幕中心）
            horizontal: 水平滚动量（正数向右，负数向左）
            duration: 移动到滚动点的耗时（秒）
        """
        if x is None or y is None:
            screen_width, screen_height = pyautogui.size()
            x = screen_width // 2
            y = screen_height // 2

        pyautogui.moveTo(x, y, duration=duration)

        if amount != 0:
            pyautogui.scroll(amount, x=x, y=y)

        # 常见桌面环境下，按住 shift + 滚轮可触发水平滚动。
        if horizontal != 0:
            pyautogui.keyDown("shift")
            try:
                pyautogui.scroll(horizontal, x=x, y=y)
            finally:
                pyautogui.keyUp("shift")
    
    def get_position(self) -> dict:
        """获取当前鼠标位置"""
        pos = pyautogui.position()
        return {"x": pos.x, "y": pos.y}

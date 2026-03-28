"""
元素定位控制器
支持图像匹配和 OCR 文字定位
"""

import os
from typing import Optional, List, Dict, Any
import cv2
import numpy as np
import pyautogui
import mss
from PIL import Image

from errors import ApiError


class LocatorController:
    """元素定位控制器"""
    
    def __init__(self):
        self.sct = mss.mss()
    
    def _capture_screen(self, region: Optional[List[int]] = None) -> np.ndarray:
        """截取屏幕为 OpenCV 格式"""
        if region:
            monitor = {
                "left": region[0],
                "top": region[1],
                "width": region[2],
                "height": region[3]
            }
        else:
            monitor = self.sct.monitors[0]
        
        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)
        
        # BGRA 转 BGR
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img_bgr
    
    def locate_image(self, image_path: str, confidence: float = 0.8, 
                     region: Optional[List[int]] = None) -> Optional[Dict[str, Any]]:
        """
        在屏幕上定位图像
        
        Args:
            image_path: 要查找的图像路径
            confidence: 匹配置信度（0-1）
            region: 搜索区域 [x, y, width, height]
            
        Returns:
            找到的位置 {"x", "y", "width", "height", "confidence"}，未找到返回 None
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"图像文件不存在：{image_path}")
            
            # 读取屏幕和模板
            screen = self._capture_screen(region)
            template = cv2.imread(image_path)
            
            if template is None:
                raise ValueError(f"无法读取图像：{image_path}")
            
            # 模板匹配
            result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            # 检查置信度
            if max_val >= confidence:
                h, w = template.shape[:2]
                return {
                    "x": int(max_loc[0]) + (region[0] if region else 0),
                    "y": int(max_loc[1]) + (region[1] if region else 0),
                    "width": w,
                    "height": h,
                    "confidence": float(max_val)
                }
            
            return None
            
        except Exception as e:
            raise ApiError(
                status_code=500,
                code="locate_image_failed",
                message="图像定位失败",
                cause=e,
                details={"image_path": image_path, "confidence": confidence, "has_region": region is not None},
            )
    
    def locate_text(self, text: str, region: Optional[List[int]] = None) -> Optional[Dict[str, Any]]:
        """
        通过 OCR 在屏幕上定位文字
        
        Args:
            text: 要查找的文字
            region: 搜索区域 [x, y, width, height]
            
        Returns:
            找到的位置 {"x", "y", "width", "height", "found_text"}，未找到返回 None
        """
        try:
            # 尝试导入 pytesseract
            try:
                import pytesseract
            except ImportError:
                raise ImportError("请先安装 pytesseract: pip install pytesseract")
            
            # 截取屏幕
            screen = self._capture_screen(region)
            
            # OCR 识别
            # 获取详细数据（包括每个文字的位置）
            data = pytesseract.image_to_data(screen, output_type=pytesseract.Output.DICT)
            
            # 搜索匹配的文字
            n_boxes = len(data['text'])
            offset_x = region[0] if region else 0
            offset_y = region[1] if region else 0
            
            for i in range(n_boxes):
                box_text = data['text'][i].strip()
                if box_text and text.lower() in box_text.lower():
                    return {
                        "x": data['left'][i] + offset_x,
                        "y": data['top'][i] + offset_y,
                        "width": data['width'][i],
                        "height": data['height'][i],
                        "found_text": box_text,
                        "confidence": data['conf'][i]
                    }
            
            return None
            
        except Exception as e:
            raise ApiError(
                status_code=500,
                code="locate_text_failed",
                message="文字定位失败",
                cause=e,
                details={"text_len": len(text or ""), "has_region": region is not None},
            )
    
    def get_screen_text(self, region: Optional[List[int]] = None) -> str:
        """
        提取屏幕上的所有文字（OCR）
        
        Args:
            region: 提取区域 [x, y, width, height]
            
        Returns:
            识别到的文字
        """
        try:
            import pytesseract
            
            screen = self._capture_screen(region)
            text = pytesseract.image_to_string(screen)
            return text
            
        except ImportError:
            raise ImportError("请先安装 pytesseract: pip install pytesseract")
        except Exception as e:
            raise ApiError(
                status_code=500,
                code="ocr_extract_failed",
                message="文字提取失败",
                cause=e,
                details={"has_region": region is not None},
            )

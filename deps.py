from __future__ import annotations

import asyncio
from dataclasses import dataclass

from controllers.keyboard import KeyboardController
from controllers.locator import LocatorController
from controllers.mouse import MouseController
from controllers.screenshot import ScreenshotController
from controllers.ui_read_controller import UIReadController
from controllers.widget_action_controller import WidgetActionController
from controllers.widget_query_controller import WidgetQueryController
from controllers.windows import WindowsController
from services.ocr_service import OCRService
from services.visual_semantic_service import VisualSemanticService
from services.widget_cropper import WidgetCropper


@dataclass
class Deps:
    screenshot_ctrl: ScreenshotController
    mouse_ctrl: MouseController
    keyboard_ctrl: KeyboardController
    windows_ctrl: WindowsController
    locator_ctrl: LocatorController
    ui_read_ctrl: UIReadController
    widget_query_ctrl: WidgetQueryController
    widget_action_ctrl: WidgetActionController
    ocr_service: OCRService
    widget_cropper: WidgetCropper
    visual_semantic_service: VisualSemanticService
    action_lock: asyncio.Lock


def create_default_deps() -> Deps:
    screenshot_ctrl = ScreenshotController()
    windows_ctrl = WindowsController()
    widget_action_ctrl = WidgetActionController()
    ocr_service = OCRService()
    widget_cropper = WidgetCropper(
        widget_action_ctrl=widget_action_ctrl,
        screenshot_ctrl=screenshot_ctrl,
        windows_ctrl=windows_ctrl,
    )
    visual_semantic_service = VisualSemanticService(widget_cropper, ocr_service)
    return Deps(
        screenshot_ctrl=screenshot_ctrl,
        mouse_ctrl=MouseController(),
        keyboard_ctrl=KeyboardController(),
        windows_ctrl=windows_ctrl,
        locator_ctrl=LocatorController(),
        ui_read_ctrl=UIReadController(),
        widget_query_ctrl=WidgetQueryController(),
        widget_action_ctrl=widget_action_ctrl,
        ocr_service=ocr_service,
        widget_cropper=widget_cropper,
        visual_semantic_service=visual_semantic_service,
        action_lock=asyncio.Lock(),
    )


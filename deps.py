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
    action_lock: asyncio.Lock


def create_default_deps() -> Deps:
    return Deps(
        screenshot_ctrl=ScreenshotController(),
        mouse_ctrl=MouseController(),
        keyboard_ctrl=KeyboardController(),
        windows_ctrl=WindowsController(),
        locator_ctrl=LocatorController(),
        ui_read_ctrl=UIReadController(),
        widget_query_ctrl=WidgetQueryController(),
        widget_action_ctrl=WidgetActionController(),
        action_lock=asyncio.Lock(),
    )


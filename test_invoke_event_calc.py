"""
手动验证脚本：UIAutomation Invoke 事件（限定「计算器」顶层窗口）

用途
    与 ``test_invoke_event.py`` 类似，但将事件监听范围缩小到**标题为「计算器」的顶层窗口**
    的子树（``FindFirst`` + ``TreeScope_Subtree``），用于验证「非 Desktop 根、单应用窗口」
    场景下 Invoke 回调是否正常。

与 pytest 的关系
    **不属于** ``tests/`` 自动化用例。手动执行：

    ``python test_invoke_event_calc.py``

前置条件
    需先打开 Windows **计算器**，且顶层窗口名称能被 UIA 匹配为「计算器」；否则会退出并提示。

依赖
    Windows、comtypes、UIAutomation。
"""

import time

import comtypes
import comtypes.client
from comtypes.gen.UIAutomationClient import (
    IUIAutomationEventHandler,
    TreeScope_Children,
    TreeScope_Subtree,
    UIA_Invoke_InvokedEventId,
    UIA_NamePropertyId,
)


def _create_uia() -> object:
    # Prefer typelib-backed CLSID to avoid depending on ProgID registration.
    try:
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as UIA  # type: ignore

        return comtypes.client.CreateObject(UIA.CUIAutomation, interface=UIA.IUIAutomation)
    except Exception:
        pass

    # Fallbacks for environments where ProgIDs are registered.
    try:
        return comtypes.client.CreateObject("UIAutomationClient.CUIAutomation8")
    except Exception:
        pass

    return comtypes.client.CreateObject("UIAutomationClient.CUIAutomation")


automation = _create_uia()
root = automation.GetRootElement()

cond = automation.CreatePropertyCondition(UIA_NamePropertyId, "计算器")
calc = root.FindFirst(TreeScope_Children, cond)
if not calc:
    raise SystemExit("未找到名为“计算器”的顶层窗口；请先打开计算器")


class InvokeHandler(comtypes.COMObject):
    _com_interfaces_ = [IUIAutomationEventHandler]

    def HandleAutomationEvent(self, sender, event_id):  # noqa: N802
        print("EVENT:", int(event_id))
        return 0


handler = InvokeHandler()
automation.AddAutomationEventHandler(UIA_Invoke_InvokedEventId, calc, TreeScope_Subtree, None, handler)

print("Listening on Calculator window... click calculator buttons")
try:
    while True:
        comtypes.client.PumpEvents(0.01)
        time.sleep(0.01)
except KeyboardInterrupt:
    pass


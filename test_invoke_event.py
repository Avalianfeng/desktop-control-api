"""
手动验证脚本：UIAutomation Invoke 事件（全局 Desktop 根节点）

用途
    在**本机已安装 comtypes 且能加载 UIAutomationCore.dll** 的前提下，直接注册
    ``UIA_Invoke_InvokedEventId``，用消息泵接收回调，确认「COM + 事件处理器」链路可用。

与 pytest 的关系
    **不属于** ``tests/`` 自动化用例；不通过 ``pytest`` 收集运行。请在有图形界面、
    可点击控件的环境下**手动执行**：

    ``python test_invoke_event.py``

操作提示
    启动后请在任意支持 Invoke 的控件上点击（例如计算器按钮）；控制台应打印 ``EVENT:`` 与事件 ID。
    Ctrl+C 结束。

依赖
    Windows、comtypes、UIAutomation（与 Recorder 所用 COM 栈一致）。
"""

import time

import comtypes
import comtypes.client
from comtypes.gen.UIAutomationClient import IUIAutomationEventHandler, TreeScope_Subtree, UIA_Invoke_InvokedEventId


def _create_uia() -> object:
    try:
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as UIA  # type: ignore

        return comtypes.client.CreateObject(UIA.CUIAutomation, interface=UIA.IUIAutomation)
    except Exception:
        pass

    try:
        return comtypes.client.CreateObject("UIAutomationClient.CUIAutomation8")
    except Exception:
        pass

    return comtypes.client.CreateObject("UIAutomationClient.CUIAutomation")


automation = _create_uia()
root = automation.GetRootElement()


class InvokeHandler(comtypes.COMObject):
    _com_interfaces_ = [IUIAutomationEventHandler]

    def HandleAutomationEvent(self, sender, event_id):  # noqa: N802
        print("EVENT:", int(event_id))
        return 0


handler = InvokeHandler()
automation.AddAutomationEventHandler(UIA_Invoke_InvokedEventId, root, TreeScope_Subtree, None, handler)

print("Listening... click an invoke-capable control (e.g. Calculator button)")
try:
    while True:
        comtypes.client.PumpEvents(0.01)
        time.sleep(0.01)
except KeyboardInterrupt:
    pass


"""
手动集成脚本：同名/多实例窗口下 focus + keyboard/type 是否落到正确 hwnd

用途
    验证 API 在「两个记事本（或同类）同时打开」时，能否通过 **不同 target_hwnd** 把文本
    输入到**正确窗口**（与 README 中 target_hwnd、409 前台校验等说明一致）。

与 pytest 的关系
    **不属于** ``tests/`` 自动化用例。需**先启动** ``python server.py``，再执行：

    ``python test_window_resolution.py``

使用前必改
    下面 ``WINDOW_1_HWND`` / ``WINDOW_2_HWND`` 为示例常量，**必须**改为当前环境中
    ``GET /windows`` 返回的真实句柄；``API_BASE`` / ``API_KEY`` 若与本地不一致也请修改。

测试流程（摘要）
    1. 依次聚焦窗口 1、窗口 2，各输入带前缀与时间戳的文本
    2. 重复多轮
    3. 最后需**人工**打开两个记事本核对内容是否分别正确
"""

import requests
import time
from datetime import datetime

API_BASE = "http://localhost:8765"
API_KEY = "desktop-control-key"
LIVE_HEADERS = {
    "X-API-Key": API_KEY,
    "X-Desktop-Control-Mode": "live",
    "X-Actor": "test_agent"
}

# 两个记事本窗口的句柄
WINDOW_1_HWND = 266106
WINDOW_2_HWND = 200242

def focus_window(hwnd: int) -> bool:
    """聚焦到指定窗口（通过 hwnd）"""
    resp = requests.post(
        f"{API_BASE}/windows/focus",
        headers=LIVE_HEADERS,
        json={"hwnd": hwnd}
    )
    result = resp.json()
    
    if result.get("success"):
        data = result.get("data", {})
        title = data.get("title", "Unknown")
        print(f"  ✓ 聚焦窗口：{title} (句柄:{hwnd})")
        time.sleep(0.5)
        return True
    else:
        error = result.get("error", {})
        print(f"  ✗ 聚焦失败：{error.get('message', '未知错误')}")
        return False

def type_text(text: str, target_hwnd: int, interval: float = 0.05):
    """输入文本到指定窗口"""
    resp = requests.post(
        f"{API_BASE}/keyboard/type",
        headers=LIVE_HEADERS,
        json={"text": text, "interval": interval, "target_hwnd": target_hwnd}
    )
    result = resp.json()
    if result.get("success"):
        print(f"  ✓ 输入：{text[:50]}...")
        return True
    else:
        error = result.get("error", {})
        print(f"  ✗ 输入失败：{error.get('message', '未知错误')}")
        return False

def press_key(key: str):
    """按键"""
    resp = requests.post(
        f"{API_BASE}/keyboard/press",
        headers=LIVE_HEADERS,
        json={"key": key}
    )
    return resp.json().get("success", False)

def get_timestamp():
    """获取时间戳"""
    return datetime.now().strftime("%H:%M:%S")

def main():
    print("=" * 70)
    print(" " * 20 + "同名窗口分辨测试")
    print("=" * 70)
    print(f"\n窗口 1 句柄：{WINDOW_1_HWND}")
    print(f"窗口 2 句柄：{WINDOW_2_HWND}")
    print(f"\n开始时间：{get_timestamp()}")
    print("-" * 70)
    
    rounds = 3  # 测试 3 轮
    
    for round_num in range(1, rounds + 1):
        print(f"\n【第 {round_num} 轮】")
        print("-" * 70)
        
        # 窗口 1 操作
        timestamp = get_timestamp()
        print(f"\n  → 切换到窗口 1...")
        if focus_window(WINDOW_1_HWND):
            text1 = f"1-测试内容 - 第{round_num}轮-{timestamp}"
            if type_text(text1, WINDOW_1_HWND):
                press_key("enter")
                print(f"  输入：{text1}")
        
        time.sleep(1)
        
        # 窗口 2 操作
        timestamp = get_timestamp()
        print(f"\n  → 切换到窗口 2...")
        if focus_window(WINDOW_2_HWND):
            text2 = f"2-测试内容 - 第{round_num}轮-{timestamp}"
            if type_text(text2, WINDOW_2_HWND):
                press_key("enter")
                print(f"  输入：{text2}")
        
        time.sleep(1)
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)
    print(f"\n结束时间：{get_timestamp()}")
    print("\n请人工验证两个记事本窗口的内容是否正确")
    print("窗口 1 应该有：1-测试内容 - 第 1 轮，1-测试内容 - 第 2 轮，1-测试内容 - 第 3 轮")
    print("窗口 2 应该有：2-测试内容 - 第 1 轮，2-测试内容 - 第 2 轮，2-测试内容 - 第 3 轮")

if __name__ == "__main__":
    main()

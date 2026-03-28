"""
AI Desktop Agent 示例
展示如何让 AI 通过 Desktop Control API 操作电脑

这个示例演示了：
1. 截图发送给 AI
2. AI 分析并返回操作指令
3. 执行操作
4. 循环直到任务完成
"""

import requests
import base64
import json
from typing import Dict, Any, Optional

# ============== 配置 ==============
API_BASE = "http://127.0.0.1:8765"
API_KEY = "desktop-control-key"

# 你的 AI 配置（这里用伪代码，实际使用时替换为你的 AI 调用方式）
AI_API_KEY = "your-ai-api-key"
AI_MODEL = "gpt-4-vision-preview"  # 或其他支持视觉的模型

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}


# ============== Desktop API 客户端 ==============

class DesktopClient:
    """Desktop Control API 客户端"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    
    def screenshot(self) -> Dict[str, Any]:
        """截图"""
        response = requests.post(f"{self.base_url}/screenshot", headers=self.headers)
        return response.json()
    
    def click(self, x: int, y: int, button: str = "left", clicks: int = 1):
        """鼠标点击"""
        return requests.post(f"{self.base_url}/mouse/click", json={
            "x": x, "y": y, "button": button, "clicks": clicks
        }, headers=self.headers).json()
    
    def move(self, x: int, y: int, duration: float = 0.5):
        """鼠标移动"""
        return requests.post(f"{self.base_url}/mouse/move", json={
            "x": x, "y": y, "duration": duration
        }, headers=self.headers).json()
    
    def type_text(self, text: str, interval: float = 0.05):
        """输入文本"""
        return requests.post(f"{self.base_url}/keyboard/type", json={
            "text": text, "interval": interval
        }, headers=self.headers).json()
    
    def press(self, key: str):
        """按键"""
        return requests.post(f"{self.base_url}/keyboard/press", json={
            "key": key
        }, headers=self.headers).json()
    
    def hotkey(self, keys: list):
        """快捷键"""
        return requests.post(f"{self.base_url}/keyboard/hotkey", json={
            "keys": keys
        }, headers=self.headers).json()


# ============== AI 代理 ==============

class AIDesktopAgent:
    """AI 桌面代理"""
    
    def __init__(self, desktop_client: DesktopClient):
        self.desktop = desktop_client
        self.conversation_history = []
    
    def call_ai(self, prompt: str, image_base64: str) -> Dict[str, Any]:
        """
        调用 AI 分析截图并返回操作指令
        
        实际使用时替换为你的 AI 调用方式
        这里用伪代码演示流程
        """
        # 这是一个示例，实际使用时需要替换为真实的 AI 调用
        # 例如 OpenAI Vision API、Claude API 等
        
        system_prompt = """
你是一个桌面操作助手。你的任务是分析屏幕截图并指导如何完成用户的任务。

请返回 JSON 格式的操作指令，支持以下操作类型：
- click: { "action": "click", "x": 100, "y": 200, "reason": "点击按钮" }
- type: { "action": "type", "text": "要输入的内容", "reason": "输入搜索词" }
- hotkey: { "action": "hotkey", "keys": ["ctrl", "c"], "reason": "复制" }
- wait: { "action": "wait", "seconds": 2, "reason": "等待加载" }
- done: { "action": "done", "result": "任务完成说明" }

只返回 JSON，不要其他内容。
"""
        
        # 伪代码：调用 AI（替换为你的实际实现）
        # response = openai.ChatCompletion.create(
        #     model=AI_MODEL,
        #     messages=[
        #         {"role": "system", "content": system_prompt},
        #         {"role": "user", "content": [
        #             {"type": "text", "text": prompt},
        #             {"type": "image_url", "image_url": f"data:image/png;base64,{image_base64}"}
        #         ]}
        #     ]
        # )
        # ai_response = response.choices[0].message.content
        
        # 这里用一个模拟返回演示流程
        ai_response = json.dumps({
            "action": "done",
            "result": "这是示例，实际会返回 AI 分析结果"
        })
        
        return json.loads(ai_response)
    
    def execute_action(self, action: Dict[str, Any]) -> bool:
        """
        执行 AI 返回的操作
        
        Returns:
            是否继续循环
        """
        action_type = action.get("action")
        
        print(f"\n执行操作：{action_type}")
        print(f"原因：{action.get('reason', 'N/A')}")
        
        try:
            if action_type == "click":
                self.desktop.click(
                    action["x"],
                    action["y"],
                    button=action.get("button", "left"),
                    clicks=action.get("clicks", 1)
                )
                return True
                
            elif action_type == "type":
                self.desktop.type_text(action["text"])
                return True
                
            elif action_type == "hotkey":
                self.desktop.hotkey(action["keys"])
                return True
                
            elif action_type == "wait":
                import time
                time.sleep(action["seconds"])
                return True
                
            elif action_type == "done":
                print(f"\n✅ 任务完成：{action.get('result')}")
                return False  # 结束循环
                
            else:
                print(f"未知操作：{action_type}")
                return True
                
        except Exception as e:
            print(f"执行失败：{e}")
            return True  # 继续尝试
    
    def run(self, task: str, max_steps: int = 20):
        """
        运行 AI 桌面代理
        
        Args:
            task: 用户任务描述
            max_steps: 最大步骤数
        """
        print(f"\n🤖 AI 桌面代理启动")
        print(f"任务：{task}")
        print(f"最大步骤：{max_steps}")
        
        for step in range(max_steps):
            print(f"\n{'='*50}")
            print(f"步骤 {step + 1}/{max_steps}")
            
            # 1. 截图
            print("1. 截取屏幕...")
            screenshot = self.desktop.screenshot()
            
            if not screenshot.get("success"):
                print("截图失败，终止任务")
                break
            
            print(f"   截图：{screenshot['width']}x{screenshot['height']}")
            
            # 2. AI 分析
            print("2. AI 分析中...")
            ai_instruction = self.call_ai(
                prompt=f"请帮我完成这个任务：{task}",
                image_base64=screenshot["image"]
            )
            
            # 3. 执行操作
            print("3. 执行操作...")
            should_continue = self.execute_action(ai_instruction)
            
            if not should_continue:
                print("\n✅ 任务完成!")
                break
        
        else:
            print(f"\n⚠️  达到最大步骤数 ({max_steps})，任务可能未完成")


# ============== 主程序 ==============

def main():
    print("""
    ╔══════════════════════════════════════════╗
    ║        AI Desktop Agent 示例              ║
    ║   让 AI 通过 API 自动操作你的电脑            ║
    ╚══════════════════════════════════════════╝
    
    ⚠️  注意：
    1. 确保 Desktop Control API 服务器已启动
    2. 配置你的 AI API 密钥
    3. AI 将实际控制你的鼠标和键盘
    """)
    
    # 初始化
    desktop = DesktopClient(API_BASE, API_KEY)
    agent = AIDesktopAgent(desktop)
    
    # 获取任务
    task = input("\n请输入要完成的任务（例如：'打开记事本并输入 Hello World'）: ")
    
    # 运行代理
    agent.run(task, max_steps=20)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n任务中断")
    except Exception as e:
        print(f"\n错误：{e}")
        print("请确保 Desktop Control API 服务器已启动")

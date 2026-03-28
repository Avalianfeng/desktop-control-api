# Desktop Control API

为 AI 代理（也包括脚本/服务）提供的 **桌面 UI 自动化 API Server**。

本项目的能力链条对齐 “Desktop Playwright” 的核心路径：

```text
窗口 → DOM → Widgets(v1.2) → Query → Stable ID → Action(click/set_value) → Traceability
```

## 🎯 项目定位（给 AI 工具/调用方）

这是一个**纯工具层（runtime）**的桌面自动化服务：它不内置任何 AI 逻辑，但提供一套稳定的“读→查→执行”协议，让调用方（LLM Agent/RPA/脚本）可以用 HTTP 方式控制桌面 UI。

### 已知限制（调用前必读）

- **多显示器**：当前版本**不支持多显示器**；坐标、截图、UIA 边界与控件位置均以**单显示器**环境为假设。若使用多屏，行为未定义、可能点错区域或读错窗口，请勿在生产环境依赖。
- **键盘输入 `/keyboard/type`**：请求体 **`target_hwnd` 为必填字段**（`>=1` 的整数），须来自**当次** `GET /windows` 返回的窗口句柄；服务端会先尝试将焦点切到该窗口，并校验**前台窗口**与 `target_hwnd` 一致后才输入，否则可能返回 **`409 window_focus_failed`**（见上文 Windows 前台限制）。另可传 **`delay_ms`**（聚焦后等待毫秒数，默认 0）。不含 `target_hwnd` 的 JSON 会被校验拒绝（422）。
- **中文与键盘**：`/keyboard/type` 对**非 ASCII** 文本默认通过**系统剪贴板 + Ctrl+V** 粘贴（依赖 `pyperclip`）；会覆盖当前剪贴板内容。编辑框场景更推荐 `/ui/widgets/set_value`（UIA 直写，不经 IME）。
- **窗口句柄**：`/windows` 返回的 `hwnd` 是**当时**的快照；窗口关闭重开、进程重启后句柄会变。**禁止**在 Agent 内存中长期缓存 `hwnd`；每次操作前应重新 `GET /windows` 或从响应当场取用。
- **同名多窗口**：`POST /windows/focus` 仅用 `title` 时可能匹配多个窗口；请优先使用 `hwnd`，或使用请求体字段 `title_match_index`（0 起，对应标题子串匹配列表中的第 N 个）。多实例场景**不要**依赖「第一个匹配」的隐式行为。
- **Windows 前台限制**：在 Windows 上，若进程不满足前台切换条件，系统可能只会让任务栏按钮闪烁而不真正前置窗口。v1.5.1 起：若尝试前置后仍未成为前台窗口，将返回 `409 window_focus_failed`（而不是继续输入到错误窗口）。

### AI 实时操作（推荐，少写脚本）

- 每一轮：**先** `GET /windows` → 从返回的 `data.windows` 里选目标 `hwnd` → `POST /windows/focus`（`{"hwnd": ...}`）→ 可选等待 → `POST /keyboard/type`（带 `target_hwnd` 与 `delay_ms`）或走 widgets。
- 若出现「未找到窗口：hwnd=xxx」：多半是**旧句柄**；重新拉取列表再试。
- Windows 下发送含中文的 JSON：优先 **PowerShell `Invoke-RestMethod`** 或 **Python `requests`**；`curl` 在控制台编码与引号转义上易踩坑。

### 统一响应与执行模式 Header

- 所有 JSON 接口使用统一结构：`{ "success", "data", "error", "trace_id" }`（成功时 `data` 为负载，`error` 为 `null`）。
- **`X-Desktop-Control-Mode: safe|live` 仅作用于以下动作**：`POST /ui/widgets/click`、`POST /ui/widgets/set_value`（默认 `safe` 只返回模拟计划，不真操作）。**其它路由**（如 `/windows/focus`、`/keyboard/type`）不受该 Header 控制；是否执行真实动作由路由本身决定。

### 计算器 / UWP / Store 应用

- 可能存在**多个同名标题**、**最小化**或与前台策略有关的行为差异；**不要**长时间用第一次拿到的 `hwnd` 重试。
- 推荐流程：**最新 `hwnd`** + `POST /ui/widgets/read`（或 `query`，请求体带 `window_hwnd`）在控件树里找「菜单 / 科学模式 / 等效按钮」再 `click`，比纯全局键盘**更稳定**。

### 推荐调用协议（强烈建议）

- **读**：`/ui/widgets/read`（获取当前窗口 widgets 快照）
- **查**：`/ui/widgets/query`（用 filters 缩小候选，返回稳定 `id`）
- **决策**：调用方选择要操作的 `id`（不要直接靠文本/坐标）
- **执行**：`/ui/widgets/click` 或 `/ui/widgets/set_value`
- **验证**：`set_value` 可用 `verify=true` 回读确认是否生效
- **审计**：live 动作会返回 `trace_id`，并写入 `updates/traces/YYYY-MM-DD.jsonl`

## 🧑‍💻 快速开始（给人类）

### 1. 安装依赖

```powershell
cd desktop-control-api
python -m pip install -r requirements.txt
```

### 2. 安装系统依赖（OCR 功能）

**Windows:**
```powershell
# 下载并安装 Tesseract OCR
# https://github.com/UB-Mannheim/tesseract/wiki
# 安装后添加环境变量：
# C:\Program Files\Tesseract-OCR\tesseract.exe
```

**macOS:**
```bash
brew install tesseract
```

**Linux:**
```bash
sudo apt install tesseract-ocr
```

### 3. 启动服务

**Windows (PowerShell):**
```powershell
# 推荐直接启动 Python
python server.py

# 或运行批处理脚本（注意必须带 .\）
.\start.bat
```

**Windows (CMD):**
```bat
start.bat
```

**自定义配置（PowerShell）:**
```powershell
$env:DESKTOP_API_KEY="your-secret-key"
# 或设置多个密钥（逗号分隔，便于轮换）
$env:DESKTOP_API_KEYS="key1,key2,key3"
$env:DESKTOP_HOST="0.0.0.0"
$env:DESKTOP_PORT="8765"
python server.py
```

**自定义配置（CMD）:**
```bat
set DESKTOP_API_KEY=your-secret-key
set DESKTOP_API_KEYS=key1,key2,key3
set DESKTOP_HOST=0.0.0.0
set DESKTOP_PORT=8765
python server.py
```

### 4. 访问 API 文档

打开浏览器访问：http://localhost:8765/docs

---

## 🔐 安全与执行模式（非常重要）

### API Key

所有接口都需要 `X-API-Key`。

### safe / live 执行模式（仅 widgets 动作）

仅 **`/ui/widgets/click`**、**`/ui/widgets/set_value`**：

- **默认 safe**：只返回模拟计划 `simulation`，不会真实点击/输入（适合 CI、demo、排查）
- **显式 live**：真实执行动作

通过 Header：`X-Desktop-Control-Mode: safe|live`（其它端点忽略此 Header，见上文「统一响应与执行模式 Header」）。

### Traceability（动作审计）

**仅在 live 动作**时：

- 响应体会包含 `trace_id`
- 同时写入 JSONL：`updates/traces/YYYY-MM-DD.jsonl`
- 可选传入 `X-Actor` 标注“谁触发的”（调用方传用户/agent 名）

---

## 📖 面向 AI 的关键 API（最常用）

### 1) 读取 Widgets（快照）

```powershell
# Windows PowerShell 中请使用 curl.exe（避免 curl 别名指向 Invoke-WebRequest）
# PowerShell 下 -d 建议用单引号包住 JSON（不要用 \\" 这类反斜杠转义）
curl.exe -X POST "http://localhost:8765/ui/widgets/read" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"max_depth":8,"include_text_widgets":true,"collapse_icons":true}'
```

```bat
REM Windows CMD 下用双引号，并用 \" 转义内部引号
curl.exe -X POST "http://localhost:8765/ui/widgets/read" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d "{\"max_depth\":8,\"include_text_widgets\":true,\"collapse_icons\":true}"
```

返回（简化）：

```json
{
  "schema_version": "desktop_widgets.v1.2",
  "window": { "title": "..." },
  "stats": { "widgets": 120, "actionable_widgets": 40 },
  "widgets": [
    {
      "id": "w_9b2c1a0e12ab",
      "role": "button",
      "text": "OK",
      "bounds": {"x": 10, "y": 10, "width": 80, "height": 30},
      "parent_id": null,
      "patterns": ["InvokePattern"],
      "meta": {
        "legacy_index_id": "w_12",
        "locator_source": "automation_id",
        "fingerprint": { "...": "..." }
      }
    }
  ]
}
```

### 2) 查询 Widgets（拿到稳定 id）

```powershell
curl.exe -X POST "http://localhost:8765/ui/widgets/query" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"filters":{"role":"button","text_contains":"ok"},"limit":10,"select":["id","role","text","bounds","meta"]}'
```

### 3) click（默认 safe，不会真实点击）

```powershell
curl.exe -X POST "http://localhost:8765/ui/widgets/click" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"id":"w_xxx"}'
```

返回会包含 `mode=safe` + `simulation`。

### 4) click（live：真实执行 + trace_id）

```powershell
curl.exe -X POST "http://localhost:8765/ui/widgets/click" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -H "X-Desktop-Control-Mode: live" -H "X-Actor: agent_demo" -d '{"id":"w_xxx","fingerprint":{}}'
```

### 5) set_value（live + verify 回读）

```powershell
curl.exe -X POST "http://localhost:8765/ui/widgets/set_value" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -H "X-Desktop-Control-Mode: live" -H "X-Actor: agent_demo" -d '{"id":"w_xxx","value":"hello","verify":true,"fingerprint":{}}'
```

---

## 🧪 一键验收与演示（推荐）

### 只读验收报告（面向人类/项目汇报）

生成 Markdown 报告（不会执行危险动作）：

```powershell
python test_client.py --acceptance --acceptance-out "updates/docs/验收报告.md"
```

### 录制可复现 steps（默认 safe）

输出 steps JSON（用于演示、回归、复现）：

```powershell
python test_client.py --record-demo
```

会写入：`updates/steps_demo_<timestamp>.json`

---

## 📖 其它 API 使用示例（鼠标/键盘/窗口/截图）

### 截图

全屏与窗口截图**固定**写入当前工作目录下 `updates/screenshots/<UTC 日期>/`，**不支持**自定义保存路径（子目录、盘符路径等）。响应里的 `path` 为绝对路径（正斜杠），可按路径读文件；若需放到别处请客户端自行拷贝。**破坏性变更**：此前使用 `out_dir` 的调用需改为依赖返回的 `path`。

```powershell
# 全屏截图
curl.exe -X POST "http://localhost:8765/screenshot" -H "X-API-Key: desktop-control-key"

# v1.6：显式返回 base64（默认不返回，避免 token 爆炸）
curl.exe -X POST "http://localhost:8765/screenshot?include_image=1" -H "X-API-Key: desktop-control-key"

# 区域截图 [x, y, width, height]
# 注意：List[int] query 需要重复参数（不要写成 region=[0,0,500,500]）
curl.exe -X POST "http://localhost:8765/screenshot?region=0&region=0&region=500&region=500" -H "X-API-Key: desktop-control-key"
```

**返回（默认）:**
```json
{
  "success": true,
  "data": {
    "format": "png",
    "width": 1920,
    "height": 1080,
    "path": "E:/projects/desktop-control-api/updates/screenshots/2026-03-26/screenshot_....png",
    "bytes": 123456,
    "sha256_8": "abcd1234"
  },
  "error": null,
  "trace_id": null
}
```

### 鼠标操作

```powershell
# 点击
curl.exe -X POST "http://localhost:8765/mouse/click" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"x":500,"y":300,"button":"left","clicks":1}'

# 移动
curl.exe -X POST "http://localhost:8765/mouse/move" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"x":600,"y":400,"duration":0.5}'

# 拖拽
curl.exe -X POST "http://localhost:8765/mouse/drag" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"start_x":100,"start_y":100,"end_x":500,"end_y":500,"duration":0.5}'

# 滚动（向下）
curl.exe -X POST "http://localhost:8765/mouse/scroll" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"amount":-3}'
```

### 键盘操作

`POST /keyboard/type` **必须**携带 **`target_hwnd`**（以及 `text`；可选 `interval`、`delay_ms`）。请先用 `GET /windows` 取得目标窗口的 `hwnd`，将下面示例中的 **`12345678`** 换成真实值。

```powershell
# 输入文本（target_hwnd 必填；delay_ms 可选，聚焦后稍等再输入）
curl.exe -X POST "http://localhost:8765/keyboard/type" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"text":"Hello World!","interval":0.05,"target_hwnd":12345678,"delay_ms":100}'

# 按键
curl.exe -X POST "http://localhost:8765/keyboard/press" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"key":"enter"}'

# 快捷键（如 Ctrl+C）
curl.exe -X POST "http://localhost:8765/keyboard/hotkey" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"keys":["ctrl","c"]}'
```

### 窗口管理

```powershell
# 列出窗口（默认：仅返回“可交互窗口”的精简列表，省 token）
curl.exe -X GET "http://localhost:8765/windows" -H "X-API-Key: desktop-control-key"

# 调试：返回完整未过滤列表（包含 is_interactive/filter_reasons 等诊断字段）
curl.exe -X GET "http://localhost:8765/windows?raw=1" -H "X-API-Key: desktop-control-key"
# 或别名参数
curl.exe -X GET "http://localhost:8765/windows?include_system=1" -H "X-API-Key: desktop-control-key"

# 聚焦窗口
curl.exe -X POST "http://localhost:8765/windows/focus" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"title":"Notepad"}'

# 移动窗口
curl.exe -X POST "http://localhost:8765/windows/move" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"title":"Notepad","x":100,"y":100,"width":800,"height":600}'
```

### 元素定位

```powershell
# 图像定位
curl.exe -X POST "http://localhost:8765/locate/image" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"image_path":"C:/images/submit_button.png","confidence":0.8}'

# 文字定位（OCR）
curl.exe -X POST "http://localhost:8765/locate/text" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"text":"提交","screen_region":[0,0,500,500]}'
```

### 窗口截图与区域截图

与 `/screenshot` 一致：**固定目录落盘**并返回 `path` / `bytes` / `sha256_8`，**不返回** base64（避免 token 爆炸）。需要图像数据时在 JSON 中加 `"include_image": true`（或 `1`）。响应中的 **`path` 为已解析的绝对路径**（正斜杠）。

**Windows 上 `/screenshot/window`** 使用 **`PrintWindow`** 将窗口绘制到内存位图，内容一般**与是否被其它窗口遮挡无关**（少数应用对 `WM_PRINT` 支持差可能出现黑屏/异常，此时会返回 `print_window_failed`）。`data.capture_method` 为 `print_window`。非 Windows 平台仍使用屏幕矩形裁剪（`capture_method` 为 `screen_region_fallback`）。全屏与 `/screenshot/region` 仍为 **mss** 屏幕合成图。服务启动时会尝试设置 **Per-Monitor DPI Aware v2**，失败时打日志，高 DPI 下若截图像素与预期不符请检查系统缩放与日志。

```powershell
# 按窗口标题截图（默认落盘，响应不含 base64）
curl.exe -X POST "http://localhost:8765/screenshot/window" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"title":"Notepad","include_decorations":false,"scale":1.0}'

# 同时返回 base64
curl.exe -X POST "http://localhost:8765/screenshot/window" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"title":"Notepad","include_image":true}'

# 按请求体参数截图指定区域（默认落盘，返回 path；与全屏/窗口一致，默认不含 base64）
curl.exe -X POST "http://localhost:8765/screenshot/region" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"x":100,"y":100,"width":800,"height":600,"scale":1.0}'

# 同时返回 base64
curl.exe -X POST "http://localhost:8765/screenshot/region" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"x":100,"y":100,"width":400,"height":300,"include_image":true}'
```

### Desktop DOM 读取（阶段1）

```powershell
# 读取当前活动窗口的 desktop_dom.v1
curl.exe -X POST "http://localhost:8765/ui/dom/read" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"max_depth":8,"include_offscreen":false}'

# 按窗口标题读取，并包含不可见/禁用元素
curl.exe -X POST "http://localhost:8765/ui/dom/read" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"window_title":"Notepad","max_depth":10,"include_disabled":true,"include_invisible":true}'
```

### Widgets 读取（阶段1.5：控件合并 / 文本折叠）

`/ui/widgets/read` 会在 Raw DOM 之上做 **button label 提升** 与 **text 折叠**，输出更适合 AI 使用的扁平 `widgets[]` 列表。

```powershell
curl.exe -X POST "http://localhost:8765/ui/widgets/read" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d '{"max_depth":8,"include_text_widgets":true,"collapse_icons":true}'
```

提示：widgets 返回的 `schema_version` 为 `desktop_widgets.v1.2`（不是 `desktop_dom.v1`）。

---

## 🤖 AI 集成示例

### Python 客户端（建议模式：query → action）

```python
import requests
import base64
from PIL import Image
from io import BytesIO

API_BASE = "http://localhost:8765"
API_KEY = "desktop-control-key"

headers = {"X-API-Key": API_KEY}

# 1) Query widgets
q = requests.post(f"{API_BASE}/ui/widgets/query", headers=headers, json={
    "filters": {"role": "button", "text_contains": "ok"},
    "limit": 5,
    "select": ["id","role","text","meta"]
}).json()

# 2) Choose id (agent decision)
target = (q.get("widgets") or [])[0]
wid = target["id"]
fp = (target.get("meta") or {}).get("fingerprint") or {}

# 3) Safe simulation first
sim = requests.post(f"{API_BASE}/ui/widgets/click", headers=headers, json={"id": wid, "fingerprint": fp}).json()

# 4) Execute live when ready (and get trace_id)
live_headers = {**headers, "X-Desktop-Control-Mode": "live", "X-Actor": "agent_demo"}
res = requests.post(f"{API_BASE}/ui/widgets/click", headers=live_headers, json={"id": wid, "fingerprint": fp}).json()
print("trace_id =", res.get("trace_id"))
```

### 完整 AI 工作流

```python
def ai_desktop_agent(prompt: str):
    """
    AI 桌面代理示例
    1. 截图 -> 2. AI 分析 -> 3. 执行操作 -> 4. 循环
    """
    import requests
    
    # 截图
    screenshot = requests.post(f"{API_BASE}/screenshot", headers=headers).json()
    
    # 调用 AI（这里用伪代码）
    ai_response = call_llm(
        system_prompt="你是一个桌面操作助手。分析截图并返回下一步操作。",
        user_prompt=prompt,
        image=screenshot["image"]
    )
    
    # 解析 AI 返回的操作
    action = parse_ai_response(ai_response)
    
    # 执行操作
    if action["type"] == "click":
        requests.post(f"{API_BASE}/mouse/click", json={
            "x": action["x"],
            "y": action["y"]
        }, headers=headers)
    elif action["type"] == "type":
        # target_hwnd 为 API 必填字段，须由调用方从当次 GET /windows 解析后传入 action
        hwnd = action.get("target_hwnd")
        if not hwnd:
            raise ValueError("keyboard/type 需要有效的 target_hwnd（来自 GET /windows）")
        requests.post(f"{API_BASE}/keyboard/type", headers=headers, json={
            "text": action["text"],
            "target_hwnd": int(hwnd),
            "interval": action.get("interval", 0.05),
            "delay_ms": int(action.get("delay_ms", 0)),
        })
    
    return action
```

---

## 🔐 安全配置

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DESKTOP_API_KEY` | API 密钥 | `desktop-control-key` |
| `DESKTOP_API_KEYS` | 多个 API 密钥（逗号分隔） | 空 |
| `DESKTOP_HOST` | 监听地址 | `127.0.0.1` |
| `DESKTOP_PORT` | 监听端口 | `8765` |
| `DESKTOP_LOG_LEVEL` | 日志级别 | `INFO` |

### 安全建议

1. **修改默认 API Key** - 生产环境务必修改
2. **限制监听地址** - 默认只监听 localhost
3. **使用 HTTPS** - 外网访问时加反向代理
4. **safe 默认** - 动作端点默认只模拟，不会真实操作
5. **trace 审计** - live 动作写入 `updates/traces/*.jsonl`，可用于回放与定位
6. **黑名单** - 禁止操作特定应用（待实现）

---

## 📊 API 完整列表

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/screenshot` | POST | 截图 |
| `/mouse/click` | POST | 鼠标点击 |
| `/mouse/move` | POST | 鼠标移动 |
| `/mouse/drag` | POST | 鼠标拖拽 |
| `/mouse/scroll` | POST | 鼠标滚动（垂直/水平） |
| `/keyboard/type` | POST | 输入文本（**必填 `target_hwnd`**，可选 `delay_ms`；校验前台一致） |
| `/keyboard/press` | POST | 按键 |
| `/keyboard/hotkey` | POST | 快捷键 |
| `/windows` | GET | 列出窗口 |
| `/windows/focus` | POST | 聚焦窗口 |
| `/windows/move` | POST | 移动窗口 |
| `/locate/image` | POST | 图像定位 |
| `/locate/text` | POST | 文字定位（OCR） |
| `/screenshot/window` | POST | 按窗口标题截图（Win：`PrintWindow`；`capture_method` 区分实现；`include_image` 才返回 base64） |
| `/screenshot/region` | POST | 按请求体区域截图（固定落盘；`include_image` 才返回 base64；`capture_method=screen_region`） |
| `/ui/dom/read` | POST | 读取 desktop_dom.v1（UIA 主读取） |
| `/ui/widgets/read` | POST | 读取 widgets v1.2（AI 友好控件列表） |
| `/ui/widgets/query` | POST | 查询 widgets（filters + select + limit） |
| `/ui/widgets/click` | POST | 点击（默认 safe；live 执行 + trace_id） |
| `/ui/widgets/set_value` | POST | 输入/设值（默认 safe；live 执行，可 verify） |

---

## 🛠️ 开发说明

### 项目结构

```
desktop-control-api/
├── server.py                 # FastAPI 应用入口（路由、中间件、envelope、探针）
├── settings.py               # 环境变量与运行配置
├── deps.py                   # 控制器依赖装配
├── errors.py                 # ApiError 等
├── response_envelope.py      # 统一 JSON 响应 { success, data, error, trace_id }
├── observability/            # JSON 日志、Prometheus 指标、OTEL tracing（可选依赖）
├── traceability/             # live 动作审计：append_trace_event → updates/traces/*.jsonl
├── recorder/                 # Dev Recorder（COM UIA 事件 → JSONL），CLI: python -m recorder.cli
├── controllers/              # 截图/鼠标/键盘/窗口/定位/UI 读取/widgets 查询与动作
│   ├── win32_win.py          # Win32 前台、窗口矩形/DWM 等底层封装
│   ├── widget_action_controller.py
│   ├── widget_query_controller.py
│   └── ui_read_controller.py
├── sources/                  # UIA 原始采集（如 UIASource）
├── engines/                  # DOM 构建（如 DesktopDOMEngine）
├── semantic/                 # widgets 语义、builder、query 映射等
├── dom/                      # DOM 规范化、过滤、压缩等
├── models/                   # Pydantic / 数据结构
├── query/                    # widgets query 引擎与 API 映射
├── tests/                    # pytest 单元与集成测试（推荐：python -m pytest tests -q）
├── tests/integration/        # 需运行中服务时设置 RUN_DESKTOP_INTEGRATION_TESTS=1
├── updates/                  # 运行产物 + 变更说明；子目录约定见 updates/README.md
│   ├── docs/                 # 测试报告、验收、计划等文档
│   ├── traces/               # 动作 trace JSONL（按 UTC 日期）
│   ├── recorder/             # Recorder 输出与 state/stop 信号
│   └── screenshots/          # 截图落盘（若使用）
├── requirements.txt
├── start.bat                 # Windows 启动脚本
├── test_client.py            # 交互式 HTTP 测试客户端（非 pytest）
├── test_ui_dom_reader.py     # 手动验证 /ui/dom/read（非 pytest）
├── test_invoke_event.py      # 手动验证 UIA Invoke（全局根，非 pytest）
├── test_invoke_event_calc.py # 手动验证 UIA Invoke（计算器窗口，非 pytest）
├── test_window_resolution.py # 手动验证多 hwnd 输入场景（非 pytest）
└── README.md
```

**根目录 ``test_*.py`` 说明**：文件名含 `test_` 仅为历史习惯；上述五个脚本为**手动或交互式**工具，**不会**被推荐命令 `pytest tests` 收集。自动化回归请以 `tests/` 为准。

**``updates/`` 目录**：会累积 trace、录制、截图与文档；建议按 [updates/README.md](updates/README.md) 分类整理，并将大文件列入 `.gitignore`（若不需要入库）。

### 添加新 API

1. 在对应 controller 添加方法
2. 在 `server.py` 添加路由
3. 更新本文档

---

## ⚠️ 注意事项

1. **安全第一** - 此服务可完全控制你的电脑，仅在可信环境使用
2. **Fail-Safe** - 鼠标移到屏幕角落可中止 PyAutoGUI 操作
3. **权限要求** - 某些操作可能需要管理员权限
4. **多显示器** - **当前版本不支持多显示器**。请在单显示器环境下使用；多屏时坐标、截图与 UI 树边界与预期可能不一致，属于未定义行为。

---

## 🐛 常见启动问题

1. **PowerShell 执行 `start.bat` 报“找不到命令”**
   - 使用 `.\start.bat`，PowerShell 默认不会从当前目录加载脚本。
2. **执行 `bash start.bat` 出现大量 `command not found`**
   - `start.bat` 是 Windows 批处理脚本，不应由 Bash 执行。
   - 请改用 `.\start.bat`（PowerShell）或 `cmd /c start.bat`。
3. **启动时报 `Errno 10048`（端口占用）**
   - 说明 `127.0.0.1:8765` 已有服务在运行。
   - 先停止旧进程，或修改端口后重启（如 `DESKTOP_PORT=8766`）。

---

## 🧪 Dev Recorder（v1.8.6，开发调试专用）

这是一个最小录制器（MVP），用于调试 UIA 控件识别与事件映射，不是 RPA 回放功能。

- v1.8.2：事件层从 `uiautomation` 迁移为 `COM + UIAutomationClient`（`comtypes`）
- v1.8.5：Record Sanitization（生成 `selector`、`delay_ms`，大幅降噪）
- v1.8.6：Intent Filtering（只保留用户意图事件）+ schema `version`

### 边界（本版本）

- 只做：监听 UIA 事件并落盘 JSONL（面向“可重放轨迹”）
  - 默认仅写盘：`invoke` / `selection` / `toggle` / `expand_collapse` / `value_change` / `text_change`
  - `structure_changed` 默认不写盘（仅计数/诊断）
  - `value_change/text_change` 仅当前台窗口且 `has_keyboard_focus=True` 才算用户意图
- 不做：脚本生成、回放、GUI、流程编排

### 启动/停止

```powershell
# 前台监听（Ctrl+C 结束）
python -m recorder.cli start

# 指定输出文件 + 仅关注窗口标题包含 Notepad 的事件
python -m recorder.cli start --out "updates/recorder/notepad.jsonl" --window-title "Notepad"

# 从另一个终端请求停止（开发态）
python -m recorder.cli stop
```

运行前提（v1.8.6）：

- 仅支持 Windows
- 需要 `comtypes`（已在 `requirements.txt`）
- 建议 Recorder 与目标应用使用同一权限级别（避免 UIPI 导致事件丢失）

启动后会提示：

- `[Recorder] Listening UIA events...`
- `[Recorder] Press Ctrl+C to stop`
- 结束时输出事件数量与落盘路径

### 日志格式（JSONL）

每行一条事件，示例：

```json
{"ts":"2026-03-27T13:18:47.842+00:00","delay_ms":423,"event":"invoke","window":{"title":"计算器","hwnd":123456,"class":"ApplicationFrameWindow"},"target":{"name":"分数","role":"button","automation_id":"factorialButton","control_type":"Button"},"selector":{"automation_id":"factorialButton"},"version":"1.8.6"}
```

### Recorder 故障排查（v1.8.6）

当你看到 `0 events captured`，请按下面顺序判断：

- 看 `bridge_details: {...}` 与 `listener_registered: ...`
  - `bridge_details.reason` 非空：说明桥接启动失败，CLI 会直接失败退出（非 0）；
  - `listener_registered` 里的 `invoke=ok` / `value=ok|skip`：只代表“注册成功”。
- 看 `bridge_details.root_is_desktop`
  - `True`：表示以 Desktop 根节点进行全局监听；
  - `False`：优先排查 root 获取异常。
- 看回调探针日志（关键）
  - `callback_invoke: ...`
  - `callback_value: ...`
  - `callback_focus reached: ...`
  - 任意一条出现，才表示“回调已到达”。

重点：**注册成功 != 回调到达**。如果注册成功但始终没有 callback 探针，通常是目标应用未发该类 UIA 事件，或权限隔离导致事件不可见。

### 事件覆盖矩阵（v1.8.6）

- 点击按钮：`invoke`
- 列表/菜单项选择：`selection`
- 文本编辑：`value_change` / `text_change`（仅当前台窗口且 `has_keyboard_focus=True` 才记为用户意图）
- 复选框/开关：`toggle`
- 树节点展开收起：`expand_collapse`
- 无法识别映射时：会被 intent filter 丢弃或在后续阶段扩展兜底

常见原因：

- COM 事件桥接启动失败（查看 `bridge_details.reason`）。
- 根节点不是 Desktop（查看 `root_is_desktop`）。
- 权限等级不一致（UIPI）导致监听不到高权限应用事件。
- 使用了 `--window-title` 且过滤条件过严（会出现 `filtered_out` 增长但 `events` 不增长）。
- 某些系统上 `FocusChanged` 接口不可用，此时仅影响 focus 探针，不影响 invoke/value 主流程。

---

## 📝 待开发功能（真实落地后再扩展）

- [ ] trace 文件轮转/保留策略（当前按天 JSONL 追加）
- [ ] 更强的动作结果验证（click 的通用 post-condition）
- [ ] 操作确认机制（危险操作前询问/二次确认）
- [ ] 应用黑名单
- [ ] 多显示器支持（当前明确不支持；需设计坐标系与虚拟屏对齐）
- [ ] 元素树定位（Windows UI Automation）
- [ ] WebSocket 实时推送
- [ ] 操作宏录制/回放

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 测试命令

```powershell
# 单元测试（mock/进程内）
python -m pytest tests -q

# 真实集成测试（直连运行中的服务，仅只读低风险接口）
$env:RUN_DESKTOP_INTEGRATION_TESTS="1"
$env:DESKTOP_TEST_API_BASE="http://127.0.0.1:8765"
$env:DESKTOP_TEST_API_KEY="desktop-control-key"
python -m pytest tests/integration -q
```

根目录 **手动脚本**（不走 pytest，详见各文件顶部说明）：`test_client.py`、`test_ui_dom_reader.py`、`test_window_resolution.py`、`test_invoke_event.py`、`test_invoke_event_calc.py`。

---

## 📄 许可证

MIT License

---

## 🔗 相关项目

- [Agent-S](https://github.com/simular-ai/Agent-S) - AI 电脑操作框架
- [PyAutoGUI](https://github.com/asweigart/pyautogui) - 鼠标键盘自动化
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Python Web 框架

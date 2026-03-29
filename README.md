# Desktop Control

基于 **Windows UI Automation（UIA）** 的桌面感知与控制服务：用 HTTP 提供结构化控件树、稳定 `widget id`、以及**按需**视觉能力（OCR / 文字定位 / 模板匹配）。面向 LLM Agent、RPA 与脚本调用；**不包含**内置大模型逻辑。

**v2 对外契约**：`POST /widgets/*` 与 `POST /vision/*` 为主路径；`/widgets/read` **仅反映 UIA**，不在读树时默认跑 OCR（见 [docs/CORE_PRINCIPLES.md](docs/CORE_PRINCIPLES.md)）。

**一句话**：基于 UIA 的桌面感知与控制服务，提供结构化控件树、稳定 `widget id` 与按需视觉能力；统一响应信封与 Agent 安全模式见下文。

---

## 读者指引

| 读者 | 建议阅读顺序 |
|------|----------------|
| **人（首次安装、排障）** | [快速开始](#快速开始) → [使用约束](#使用约束摘要) → [文档导航](#文档导航) |
| **AI / 自动化集成** | 先读本节下 **[最小 JSON 契约与示例](#最小-json-契约与示例-ai--集成)**，再查 [docs/AI_PROTOCOL.md](docs/AI_PROTOCOL.md)（含**常见错误码表**） |

集成时**必须**携带：`Content-Type: application/json`、`X-API-Key: <密钥>`。涉及真实点击/输入时另加：`X-Desktop-Control-Mode: live`（默认 `safe` 只模拟）。

---

## 路径与迁移（v2）

- **新集成请优先**使用 `POST /widgets/*`、`POST /vision/*`（与 OpenAPI `/docs` 展示一致）。
- **旧路径**（如 `POST /ui/widgets/read`）与 v2 **响应形状一致**，仍可用；对照表与说明见 [docs/LEGACY.md](docs/LEGACY.md)。
- **移除时间表**：当前**未承诺**下线日期；若未来版本废弃某路径，会在发行说明与 `LEGACY.md` 更新，**不会**在未公告的情况下静默删除（与「协议优先」原则一致）。
- **所谓「v1→v2」**：主要是**路径命名空间**与文档收敛；`schema_version` 已为 `desktop_widgets.v2`，旧客户端换 URL 即可，无需改字段语义。

---

## 快速开始

### 1. 依赖

```powershell
cd desktop-control-api
python -m pip install -r requirements.txt
```

需要 **OCR** 时安装 [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) 并加入 `PATH`；中文界面建议语言包 `chi_sim`（细节见 [docs/DEV_GUIDE.md](docs/DEV_GUIDE.md)）。

### 2. 配置与启动

复制 [`.env.example`](.env.example) 为 `.env`。最小可运行示例（其余变量见 `.env.example` 注释）：

```ini
DESKTOP_HOST=127.0.0.1
DESKTOP_PORT=8765
DESKTOP_API_KEY=desktop-control-key
```

启动：

```powershell
python server.py
# 或
.\start.bat
```

默认文档：http://127.0.0.1:8765/docs（OpenAPI **仅展示 v2 主路径**；旧路径仍可用，见 [docs/LEGACY.md](docs/LEGACY.md)）。

### 3. 第一个请求（需 Header `X-API-Key`）

读取当前活动窗口的控件列表：

```http
POST /widgets/read
Content-Type: application/json
X-API-Key: <your-key>

{"max_depth": 8, "include_text_widgets": true, "collapse_icons": true}
```

在 `data.widgets[]` 中取 `id`，再调用：

```http
POST /widgets/act
X-Desktop-Control-Mode: safe

{"action": "click", "id": "<widget-id>"}
```

---

## 最小 JSON 契约与示例（AI / 集成）

下列示例与实现一致；**省略**的字段多为可选，完整列表见 [docs/AI_PROTOCOL.md](docs/AI_PROTOCOL.md) 与 OpenAPI。

### 统一外层

成功：

```json
{
  "success": true,
  "data": { },
  "error": null,
  "trace_id": null
}
```

业务失败（`success: false`；HTTP 状态码多为 4xx/5xx，与 `error.code` 对应；以响应体为准）：

```json
{
  "success": false,
  "data": null,
  "error": { "code": "widget_not_found", "message": "…" },
  "trace_id": null
}
```

### `POST /widgets/read`

**请求体（常用字段）**

```json
{
  "max_depth": 8,
  "include_text_widgets": true,
  "collapse_icons": true,
  "window_hwnd": 12345678,
  "window_title": null,
  "include_offscreen": false,
  "include_disabled": true,
  "include_invisible": false
}
```

未指定窗口时读**前台**窗口；指定 `window_hwnd` 或 `window_title` 则读对应窗口。

**响应 `data`（结构节选）**

```json
{
  "schema_version": "desktop_widgets.v2",
  "window": { "title": "…", "hwnd": 12345678, "left": 0, "top": 0, "width": 1920, "height": 1080 },
  "stats": { "all_elements": 200, "widgets": 42, "actionable_widgets": 15 },
  "widgets": [
    {
      "id": "w_9b2c1a0e12ab",
      "type": "button",
      "role": "button",
      "text": { "value": "确定", "source": "uia", "confidence": 1.0 },
      "text_legacy": "确定",
      "normalized": "ok",
      "bounds": { "x": 100, "y": 200, "width": 80, "height": 30 },
      "enabled": true,
      "visible": true,
      "focusable": true,
      "uia_path": "…",
      "parent_id": null,
      "patterns": ["InvokePattern"],
      "value": null,
      "meta": {}
    }
  ]
}
```

说明：

- **`id`**：稳定 locator，形如 `w_` + 12 位十六进制（示例中 `w_9b2c1a0e12ab` 为示意）。
- **`text`**：UIA 主源对象；无文本时为 `"value": null`, `"source": "none"`（**不是**「未跑 OCR」）。
- **`bounds`**：屏幕像素矩形，**键名为** `width` / `height`（不是 `w`/`h`）。
- **`text_legacy`**：与 `text.value` 同步的扁平字符串，供**旧客户端**或**简单子串匹配**（如 `filters.text_contains`）使用；**新集成**应读 `text.value`（及 `source`），不要假设长期保留双字段以外的额外语义。

### `POST /widgets/query`

在服务端先 `read` 再过滤；**请求体**含 `filters`、`limit`、`select` 等，例如：

```json
{
  "window_hwnd": 12345678,
  "max_depth": 8,
  "filters": { "role": "button", "text_contains": "保存" },
  "limit": 20,
  "select": ["id", "role", "text", "text_legacy", "bounds"]
}
```

`data.schema_version` 为 `desktop_widgets_query.v2`；`filters.text_contains` 匹配 **`text_legacy` / `text.value`**（大小写不敏感）。

### `POST /widgets/act`

**白名单**：仅 **`click`**、**`set_value`**；不支持 `hover`、`scroll`、`select` 等。扩展能力见 [docs/DEV_GUIDE.md](docs/DEV_GUIDE.md) 中的底层输入端点。

**点击**（最小体；可选 `window_title`、`max_depth`、`target_hwnd`、`fingerprint`）

```json
{ "action": "click", "id": "w_9b2c1a0e12ab" }
```

**设值**（`action=set_value` 时必须提供 `value`，不要用 `text` 字段）

```json
{ "action": "set_value", "id": "w_9b2c1a0e12ab", "value": "hello" }
```

错误示例：不要用 `{"text":"hello"}` 代替 `value`；不要用 `{"click": true}` 代替 `action`/`id`。

真实执行时在 Header 加：`X-Desktop-Control-Mode: live`。

### `POST /vision/find_text`

在屏幕（或可选矩形区域）内用 OCR 找**子串**（非 UIA）；**请求无 `confidence` 字段**。

**请求**

```json
{
  "text": "登录",
  "screen_region": null
}
```

可选 `screen_region`: `[x, y, width, height]` 限制搜索范围。

**找到时 `data`**

```json
{
  "found": true,
  "location": {
    "x": 512,
    "y": 348,
    "width": 64,
    "height": 24,
    "found_text": "登录",
    "confidence": 92
  }
}
```

**未找到时 `data`**

```json
{
  "found": false,
  "message": "未找到文字：登录"
}
```

**关于 `confidence`**：请求体**不能**传阈值；`location.confidence` 来自 Tesseract 盒置信度（0–100 量级，见实现）。若业务需要「高于某置信度才采纳」，请在**调用方**根据 `location.confidence` 过滤；需要多次尝试可缩小 `screen_region` 或换关键字。

---

## 典型工作流（读 → 查 → 执行）

下列 Python 展示 **safe 预演再 live**（与 [docs/CORE_PRINCIPLES.md](docs/CORE_PRINCIPLES.md)「感知与操作解耦」一致：先读树再动作）。请将 `API_BASE` / `API_KEY` 换成你的环境。

```python
import requests

API_BASE = "http://127.0.0.1:8765"
API_KEY = "desktop-control-key"
headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

r = requests.post(
    f"{API_BASE}/widgets/read",
    headers=headers,
    json={"max_depth": 8, "include_text_widgets": True, "collapse_icons": True},
)
r.raise_for_status()
widgets = r.json()["data"]["widgets"]

q = requests.post(
    f"{API_BASE}/widgets/query",
    headers=headers,
    json={
        "max_depth": 8,
        "filters": {"role": "button", "text_contains": "确定"},
        "limit": 5,
        "select": ["id", "role", "text", "bounds"],
    },
).json()["data"]["widgets"]
wid = q[0]["id"]

requests.post(
    f"{API_BASE}/widgets/act",
    headers={**headers, "X-Desktop-Control-Mode": "safe"},
    json={"action": "click", "id": wid},
).raise_for_status()

requests.post(
    f"{API_BASE}/widgets/act",
    headers={**headers, "X-Desktop-Control-Mode": "live"},
    json={"action": "click", "id": wid},
).raise_for_status()
```

可选：对同一控件做 **按需 OCR 验证**（不写入 `widgets/read` 的 `text`）：

```http
POST /vision/ocr/widget
{"id": "<widget-id>"}
```

---

## 性能与 `max_depth`（经验值，非 SLA）

| 场景 | 大致 widgets 规模 | 建议 `max_depth` | 说明 |
|------|-------------------|-------------------|------|
| 小型对话框 / 记事本 | 数十 | 8（默认附近） | 可先 `query` 再 `act`，减少 payload |
| IDE、大型桌面应用 | 数百～上千 | 5–8 | 过大深度成本高，优先缩小窗口或 `select` |
| 浏览器（网页） | 常极大 | 5 或更低 | **不推荐**依赖本服务做浏览器自动化：请用 DevTools Protocol、扩展或厂商 API；本服务面向**原生 Win32/UIA** 场景 |
| 微信、QQ 等 | 可能极深 | 可尝试 12–20 | 树深且变化大，属**已知难点**，后续版本持续优化 |

与原则一致：`/widgets/read` 不默认 OCR；上表仅帮助控制 **token 与耗时**，不是协议承诺。

---

## API 概览（v2）

| 区域 | 方法 | 说明 |
|------|------|------|
| **Widgets** | `POST /widgets/read` | 控件快照（UIA，`text` 为对象） |
| | `POST /widgets/query` | 过滤 + 字段裁剪 |
| | `POST /widgets/act` | **仅** `click`、`set_value`（白名单；无 hover/scroll） |
| **窗口** | `GET /windows` | 窗口列表 |
| | `POST /windows/focus` | 聚焦 |
| **Vision** | `POST /vision/ocr/read` | 磁盘图像 OCR |
| | `POST /vision/ocr/widget` / `POST /vision/widget` | 裁剪控件 + OCR |
| | `POST /vision/screenshot/widget` | 仅截图 |
| | `POST /vision/find_text` | 文字 → 屏幕位置（OCR） |
| | `POST /vision/match_template` | 模板匹配 |

低层输入（鼠标/键盘/全屏截图等）端点仍在服务中，完整列表与示例见 [docs/DEV_GUIDE.md](docs/DEV_GUIDE.md)。

---

## 文档导航

| 文档 | 内容 |
|------|------|
| [docs/CORE_PRINCIPLES.md](docs/CORE_PRINCIPLES.md) | 长期设计原则（非接口细节） |
| [docs/AI_PROTOCOL.md](docs/AI_PROTOCOL.md) | 字段与语义契约、常见错误码与处理建议 |
| [docs/DEV_GUIDE.md](docs/DEV_GUIDE.md) | 环境、限制、curl 示例、调试与测试 |
| [docs/LEGACY.md](docs/LEGACY.md) | 旧路径与 OpenAPI 说明 |
| [docs/v2/STATUS.md](docs/v2/STATUS.md) | 阶段状态（A–E） |

---

## 使用约束（摘要）

- **单显示器**：多屏场景未定义，生产请勿依赖。
- **认证**：所有业务接口需 `X-API-Key`（见 `.env.example`）。
- **`hwnd`**：来自当次 `GET /windows`，勿长期缓存。
- 更多（键盘 `target_hwnd`、前台 `409`、中文输入等）见 [docs/DEV_GUIDE.md](docs/DEV_GUIDE.md)。

---

## 许可证

MIT — 见仓库根目录 `LICENSE` 文件。

---

## 相关链接

- [FastAPI](https://fastapi.tiangolo.com/)
- [PyAutoGUI](https://github.com/asweigart/pyautogui)

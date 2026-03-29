# Desktop Control — 开发指南

面向维护者、深度集成与调试；**对外契约**以 [AI_PROTOCOL.md](AI_PROTOCOL.md) 为准，**原则**以 [CORE_PRINCIPLES.md](CORE_PRINCIPLES.md) 为准。

## 文档层级

```
CORE_PRINCIPLES.md  →  AI_PROTOCOL.md  →  代码与 OpenAPI
```

## 感知栈（何时用什么）

1. **UIA**：`POST /widgets/read`、`/widgets/query` — 主路径，低成本、高确定性。
2. **OCR**：`POST /vision/ocr/widget` 或 `/vision/widget` — 点击后验证、自绘/图标文字等；**不**在 read 里默认跑。
3. **模板**：`POST /vision/match_template` — 固定像素样式；与 UIA 正交。

## OpenAPI 与 Legacy

- **Swagger `/docs`** 以 **v2 主路径** 为对外表面：`/widgets/*`、`/vision/*` 等。
- **旧路径**（如 `POST /ui/widgets/read`、`POST /ocr/read_widget`）在实现中仍可用，但 **`include_in_schema=False`**，不在 OpenAPI 中列出，避免与 README 矛盾。完整对照见 [LEGACY.md](LEGACY.md)。

## 环境变量（摘录）

| 变量 | 含义 |
|------|------|
| `DESKTOP_UI_MAX_DEPTH` | UIA 默认深度（1–30） |
| `DESKTOP_EXPOSE_DEBUG_ROUTES` | `1` 时注册 `/ocr/read_window`、`/locate/*` 等诊断路由 |
| `DESKTOP_API_KEY` / `DESKTOP_API_KEYS` | 认证密钥 |
| `DESKTOP_HOST` / `DESKTOP_PORT` | 监听地址与端口 |

完整示例见仓库根 [`.env.example`](../.env.example)。

## Tesseract（OCR）

**Windows**：安装 [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)，将 `tesseract.exe` 所在目录加入 `PATH`（如 `C:\Program Files\Tesseract-OCR\`）。安装程序勾选 **Chinese (Simplified)**（`chi_sim`），否则中文界面易被误识别。

Tesseract 仅在传入 **`-l`**（如 `chi_sim+eng`）时加载对应语言；HTTP 请求中通过 **`lang`** 与可选 **`tesseract_config`**（如 `--psm 6`）传递。

**macOS**：`brew install tesseract`  
**Linux**：`sudo apt install tesseract-ocr` 与 `tesseract-ocr-chi-sim`

## 已知限制（调用前必读）

- **多显示器**：当前**不支持**多显示器；坐标、截图、UIA 边界以单屏为假设。
- **`POST /keyboard/type`**：`target_hwnd` **必填**，须来自当次 `GET /windows`；服务端校验前台窗口，否则可能返回 **`409 window_focus_failed`**。非 ASCII 文本走剪贴板 + Ctrl+V（依赖 `pyperclip`）；编辑框更推荐 **`/widgets/act`** + `set_value`（UIA）。
- **同名多窗口**：`POST /windows/focus` 仅用 `title` 时可能多匹配；优先 `hwnd` 或 `title_match_index`。
- **Windows 前台**：若无法置前，可能返回 `409` 而非继续误操作。

## 统一响应与 safe / live

- 成功：`{ "success": true, "data": {...}, "error": null, "trace_id": ... }`
- **`X-Desktop-Control-Mode: safe|live`** 仅作用于 **widget 点击/设值**（含 `/widgets/act` 及兼容路径 `/ui/widgets/click`、`set_value`）。默认 **safe** 只返回模拟计划；**live** 才真实操作并可能产生 `trace_id`（写入 `updates/traces/*.jsonl`）。

## 语义过滤（实现侧）

- 规则**不进** AI_PROTOCOL；实现见 `semantic/widget_builder.py`、`query/widget_query_engine.py`。
- **路线图**：v2.0 基础过滤 → v2.1 可配置 → v2.2+ 语义增强；见 [v2/PLAN_PHASE_D.md](v2/PLAN_PHASE_D.md)。

## 常用 curl 示例（Windows）

使用 **`curl.exe`**（避免 PowerShell 的 `curl` 别名）。**v2 路径**：

```powershell
# Widgets 快照
curl.exe -X POST "http://127.0.0.1:8765/widgets/read" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d "{\"max_depth\":8,\"include_text_widgets\":true,\"collapse_icons\":true}"

# Query
curl.exe -X POST "http://127.0.0.1:8765/widgets/query" -H "Content-Type: application/json" -H "X-API-Key: desktop-control-key" -d "{\"filters\":{\"role\":\"button\",\"text_contains\":\"ok\"},\"limit\":10,\"select\":[\"id\",\"role\",\"text\",\"bounds\"]}"
```

`text` 在 v2 中为对象；`text_legacy` 为扁平字符串（若 `select` 包含）。

**低层 API**（鼠标、键盘、全屏截图、`/screenshot/window` 等）与更多示例与旧版路径说明见 [LEGACY.md](LEGACY.md) 或仓库历史中保留的 curl 片段。

## OCR 与路径安全

- **`POST /vision/ocr/read`**（及旧路径 `/ocr/read`）：`image_path` 须在服务进程允许的工作目录内（相对 cwd），否则 `400 ocr_path_not_allowed`。

## 项目结构（摘要）

```
server.py          # FastAPI 入口
settings.py        # 配置
deps.py            # 依赖装配
controllers/       # 路由逻辑、widgets、ocr
semantic/          # widget 构建与类型
query/             # widgets query 引擎
tests/             # pytest
updates/           # 运行产物（截图、trace 等）
```

## 测试

```powershell
python -m pytest tests -q
```

集成测试需运行中的服务并设置 `RUN_DESKTOP_INTEGRATION_TESTS=1` 等（见 `.env.example`）。

## 开发脚本（非 pytest）

| 脚本 | 用途 |
|------|------|
| `test_client.py` | 交互式验收 / 演示 |
| `manual_ocr_inspector.py` | 人机对比 UIA 与 OCR（默认调 `/vision/ocr/widget`） |

根目录部分 `test_*.py` 为历史手动工具；自动化以 `tests/` 为准。

## Dev Recorder（可选）

`python -m recorder.cli start` — Windows 下调试 UIA 事件录制，详见 `recorder/` 包内说明。

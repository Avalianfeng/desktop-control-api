# 给 AI 的 Desktop Control API 测试计划

本文档供 **AI 测试执行者** 使用：按顺序、可复现地验证本项目的对外能力。

---

## 1. 信息来源约束（必须遵守）

- **允许**：仅通过 **`README.md`**、本仓库 **`updates/` 目录下其它 Markdown`**，以及（在字段不明时）访问运行中服务 **`http://<host>:<port>/docs`** 的 OpenAPI 描述来理解用法。
- **禁止**：阅读 **`*.py` 源码**、`controllers/`、`server.py` 等实现细节来推断行为。若文档与实测不一致，应记录为「文档/实现偏差」并停止依赖未文档化假设。

以下步骤中的路径、Header、JSON 字段均以 README 为准；默认 **`X-API-Key`** 与 README 一致（默认密钥见 README「环境变量」表），默认 **`http://127.0.0.1:8765`**。

---

## 2. 环境与前置条件

| 项 | 要求（见 README） |
|----|-------------------|
| OS | 以 **Windows** 为主（Recorder、部分截图语义为 Windows）；其它 OS 需按 README 调整预期 |
| 显示器 | **单显示器**；多屏属于未定义行为，专业测试应在一屏环境执行 |
| Python 依赖 | `pip install -r requirements.txt` |
| OCR | `/locate/text` 依赖 **Tesseract** 已安装且可执行文件在 PATH（README「安装系统依赖」） |
| 服务 | `python server.py`（或 `.\start.bat`），端口与 `DESKTOP_PORT` 一致 |
| 客户端 | PowerShell 下请使用 **`curl.exe`**，避免 `curl` 别名；JSON 体引号按 README 示例 |
| 权限 | README 提示部分操作可能需管理员；Recorder 建议与目标应用**同级权限** |

**开始前人工准备**：关闭无关全屏应用；准备可丢弃的**测试用记事本**、**计算器**等窗口（见各用例）。

---

## 3. 测试结果互相干扰与消除方法（总表）

自动化桌面测试的典型干扰与应对：

| 干扰类型 | 表现 | 消除/缓解（专业做法） |
|----------|------|------------------------|
| 鼠标/键盘 | 误点其它窗口、输入进错控件 | 每轮 UI 操作前 **`GET /windows` + `POST /windows/focus`**；对键盘使用文档推荐的 **`target_hwnd` + `delay_ms`**；敏感序列后 **聚焦到安全窗口**（如空白记事本） |
| 剪贴板 | `/keyboard/type` 非 ASCII 可能 **覆盖剪贴板**（README「已知限制」） | 测试含中文输入前后 **备份/恢复剪贴板**（人工或脚本）；或改用 **`/ui/widgets/set_value`** 避免剪贴板路径 |
| 窗口句柄 | **hwnd 过期**（关闭重开即变） | **禁止跨用例缓存 hwnd**；每个依赖句柄的用例开头重新 `GET /windows` |
| 窗口位置 | `/windows/move` 改变布局 | 记录原始位置或测试后 **移回**；或使用专用测试用户会话 |
| 截图文件 | 写入 `updates/screenshots/<UTC日期>/` | 测试前后可归档或删除当日测试 PNG，避免磁盘与清单混淆 |
| Trace | live widgets 写入 **`updates/traces/*.jsonl`** | 测试批次使用固定 **`X-Actor`** 便于过滤；或测试后归档 JSONL |
| Widgets 状态 | click/set_value 改变 UI | 使用 **safe 模式**验证计划；live 后在同窗口 **撤销/关闭不保存** 或重置应用状态 |
| 焦点策略 | Windows **前台失败** 返回 409（README） | 不要强行连续 type；先 focus 成功再测键盘 |
| Fail-Safe | PyAutoGUI 角落中止（README） | 自动化时避免长时间将真实鼠标锁在危险轨迹 |

**推荐批次顺序**：**只读与健康检查 → 窗口枚举 → 截图（只读磁盘）→ 定位（只读/OCR）→ DOM/widgets 只读 → mouse 低风险坐标 → keyboard → windows/focus/move → widgets safe → widgets live（最后、可控环境）**。

---

## 4. 分阶段测试清单（按顺序执行）

对每一步记录：`HTTP 状态`、`success`、`关键 data 字段`、异常时 `error.code`（若有）。

---

### 阶段 A — 存活与契约（无桌面副作用）

| 序号 | 功能 | 方法 | 说明（README） |
|------|------|------|----------------|
| A1 | 健康检查 | `GET /health` | 验证服务进程与 JSON 信封 |
| A2 | （可选）OpenAPI | 浏览器打开 `/docs` | 仅用于核对路径/字段名，**不读源码** |

**通过准则**：`success === true`，`data` 含 README 示例中的状态字段。

---

### 阶段 B — 截图（写入项目目录，不改变第三方应用状态）

| 序号 | 功能 | 说明 |
|------|------|------|
| B1 | 全屏截图 | `POST /screenshot`，默认 **不落 base64**，返回 `path`、`bytes`、`sha256_8` 等 |
| B2 | 全屏 + base64 | `POST /screenshot?include_image=1` |
| B3 | 区域截图 | `POST /screenshot?region=...`（README：**重复 query 参数** 传 `List[int]`） |
| B4 | 窗口截图 | **先打开「记事本」或「计算器」**（标题需与 `title` 子串匹配）。`POST /screenshot/window`，body 含 `title`、`include_decorations`、`scale`；默认 **无** `image` 字段；应有 **`path`、`capture_method`**（README 说明 Windows 为 `print_window`） |
| B5 | 窗口 + base64 | body 加 `"include_image": true` |
| B6 | 区域截图（body） | `POST /screenshot/region`，JSON：`x,y,width,height,scale`；默认返回 `path`/`bytes`/`sha256_8`/`capture_method`；需要 base64 时加 `"include_image": true` |

**干扰**：B1–B6 持续产生 PNG。  
**消除**：测试后清理或打包 `updates/screenshots/` 下当日目录；全屏截图会暴露桌面内容，注意隐私。

---

### 阶段 C — 窗口列表与焦点、移动（改变窗口几何/前台）

| 序号 | 功能 | 说明 |
|------|------|------|
| C1 | 列出窗口 | `GET /windows` 默认精简列表 |
| C2 | 原始列表 | `GET /windows?raw=1` 或 `include_system=1`（README） |
| C3 | 聚焦 | **先打开记事本**。`POST /windows/focus`，可用 `{"title":"Notepad"}`；更稳妥为 **最新 `GET /windows` 的 `hwnd`**（README：勿长期缓存 hwnd） |
| C4 | 移动/resize | `POST /windows/move`，**记录或移回** 以免后续坐标用例错位 |

**干扰**：改变前台窗口与位置。  
**消除**：C4 后手动移回；C3 后若需隔离，聚焦到专用测试窗口。

---

### 阶段 D — 鼠标（真实指针/点击）

| 序号 | 功能 | 说明 |
|------|------|------|
| D1 | 点击 | `POST /mouse/click` |
| D2 | 移动 | `POST /mouse/move` |
| D3 | 拖拽 | `POST /mouse/drag` |
| D4 | 滚动 | `POST /mouse/scroll` |

**前置**：建议在**空白区域**或可丢弃应用内选坐标；README：**单显示器**、**Fail-Safe**。

**干扰**：误触 UI。  
**消除**：完成后聚焦安全窗口；不要用生产文档编辑器中心区域作靶点。

---

### 阶段 E — 键盘（真实按键）

| 序号 | 功能 | 说明 |
|------|------|------|
| E1 | 输入文本 | `POST /keyboard/type` |
| E2 | 单键 | `POST /keyboard/press` |
| E3 | 快捷键 | `POST /keyboard/hotkey` |

**前置**：`POST /keyboard/type` 的 JSON **必须**含 **`target_hwnd`**（来自当次 `GET /windows`）；可选 **`delay_ms`**。注意 **中文与剪贴板**（README「已知限制」）。

**干扰**：剪贴板、错误窗口接收输入。  
**消除**：见第 3 节剪贴板；每步前 focus。

---

### 阶段 F — 定位（图像 / OCR）

| 序号 | 功能 | 说明 |
|------|------|------|
| F1 | 图像定位 | `POST /locate/image`，需有效 **`image_path`**（README 示例为磁盘路径）；**自备小图** |
| F2 | 文字 OCR | `POST /locate/text`；屏幕需有可识别文字；**Tesseract 已安装** |

**干扰**：无持久状态；F2 依赖当前屏幕内容。

---

### 阶段 G — UI 树与 Widgets（只读 → 查询）

| 序号 | 功能 | 说明 |
|------|------|------|
| G1 | Desktop DOM | `POST /ui/dom/read`；可先聚焦目标应用或传 `window_title` |
| G2 | Widgets 快照 | `POST /ui/widgets/read`；校验 `schema_version` 为 README 所述 **desktop_widgets.v1.2** |
| G3 | Widgets 查询 | `POST /ui/widgets/query`，`filters` + `limit` + `select` |

**前置**：**打开带 UIA 的桌面应用**（记事本、计算器等）。

---

### 阶段 H — Widgets 动作（safe → live）

| 序号 | 功能 | 说明 |
|------|------|------|
| H1 | click safe | **无** `X-Desktop-Control-Mode: live`；应返回模拟计划，**不**真实点击 |
| H2 | click live | Header：`X-Desktop-Control-Mode: live`，可选 `X-Actor`；响应含 **`trace_id`**；写入 `updates/traces/` |
| H3 | set_value live | 同上 + 可选 `verify=true` |

**前置**：从 G3 取得合法 **`id` 与 `fingerprint`**（README AI 示例流程）。

**干扰**：H2/H3 真实改 UI 并写 trace。  
**消除**：仅在可丢弃界面执行；trace 按第 3 节归档。

---

### 阶段 I — 项目自带脚本（README「一键验收」）

| 序号 | 功能 | 说明 |
|------|------|------|
| I1 | 验收报告 | `python test_client.py --acceptance --acceptance-out "updates/验收报告.md"`（**只读、低风险**） |
| I2 | 录制 demo | `python test_client.py --record-demo`（默认 safe） |

---

### 阶段 J — Dev Recorder（README「Dev Recorder」节）

| 序号 | 功能 | 说明 |
|------|------|------|
| J1 | 启动录制 | `python -m recorder.cli start`（可 `--out`、`--window-title`） |
| J2 | 在目标应用操作 | 按 README「事件覆盖矩阵」产生 **invoke/selection/…** |
| J3 | 停止 | `python -m recorder.cli stop` 或 Ctrl+C |

**前置**：Windows；`comtypes`；目标窗口打开；权限与 README 一致。

**干扰**：生成 JSONL；占用前台。  
**消除**：删除或归档 `updates/recorder/` 下测试文件。

---

### 阶段 K — 集成测试（README「测试命令」节）

在**已启动的 API** 上：

```powershell
$env:RUN_DESKTOP_INTEGRATION_TESTS="1"
$env:DESKTOP_TEST_API_BASE="http://127.0.0.1:8765"
$env:DESKTOP_TEST_API_KEY="desktop-control-key"
python -m pytest tests/integration -q
```

**说明**：具体覆盖范围以 **`tests/integration`** 内测试名及 README 描述为准（执行者仍**不读**业务源码时，以 pytest 输出与 README 为准判断成败）。

---

## 5. 专业测试视角补充

- **等价类**：窗口标题 **部分匹配**（README）；多实例时用 **`title_match_index` 或 hwnd**。
- **负向用例**：错误 API Key、非法 JSON、不存在的 `title`、错误的 `region`（预期 4xx/5xx 与统一 `error` 结构）。
- **性能**：高频 `screenshot` / `widgets/read` 观察延迟与机器负载（不设固定阈值，记录基线）。
- **安全**：在隔离 VM 或专用账号跑 **live** 批次；勿对生产数据目录执行 `windows/move` 到屏外导致「丢失」窗口。

---

## 6. 交付物（建议 AI 输出）

1. 分阶段 **通过/失败表**（含 HTTP 与 `error.code`）。  
2. **干扰记录**（剪贴板是否被改、trace 路径、截图目录）。  
3. **文档偏差清单**（仅依据 README/docs 的预期与实测不一致项）。  
4. 若失败：附 **复现步骤**（精确到 curl 与当时前台窗口），**不包含**源码引用。

---

*文档基于仓库 `README.md` 与 `updates` 下公开说明整理；若 API 变更，以最新 README 为准并应同步修订本测试计划。*

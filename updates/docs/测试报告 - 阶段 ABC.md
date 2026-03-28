# Desktop Control API 测试报告 - 阶段 A/B/C

**测试时间：** 2026-03-28 13:58 GMT+8  
**测试环境：** Windows 11, 单显示器  
**API 密钥：** desktop-control-key  
**服务地址：** http://localhost:8765

---

## 阶段 A — 存活与契约（无桌面副作用）✅

| 序号 | 功能 | 状态 | HTTP 状态 | 说明 |
|------|------|------|-----------|------|
| A1 | 健康检查 `GET /health` | ✅ 通过 | 200 | `success=true`, `data.status="ok"` |
| A2 | OpenAPI 文档 `GET /docs` | ✅ 通过 | 200 | Swagger UI 正常加载 |

**结论：阶段 A 通过** ✅

---

## 阶段 B — 截图（写入项目目录，不改变第三方应用状态）✅

| 序号 | 功能 | 状态 | HTTP 状态 | 说明 |
|------|------|------|-----------|------|
| B1 | 全屏截图 `POST /screenshot` | ✅ 通过 | 200 | 返回 `path`、`bytes`、`sha256_8`，1920x1080 |
| B2 | 全屏 + base64 `POST /screenshot?include_image=1` | ✅ 通过 | 200 | `hasImage=true`，返回 base64 数据 |
| B3 | 区域截图 (query) `POST /screenshot?region=...` | ✅ 通过 | 200 | 500x500 区域截图成功 |
| B4 | 窗口截图 `POST /screenshot/window` | ✅ 通过 | 200 | 返回 `path`、`capture_method="print_window"` |
| B5 | 窗口 + base64 `POST /screenshot/window` + `include_image:true` | ✅ 通过 | 200 | `hasImage=true` |
| B6 | 区域截图 (body) `POST /screenshot/region` | ⚠️ 部分通过 | 200 | 截图成功但 `path=null`（文件实际已保存） |

**截图文件保存位置：** `updates/screenshots/2026-03-28/`  
**结论：阶段 B 基本通过** ✅（B6 的 `path` 返回问题待修复）

---

## 阶段 C — 窗口列表与焦点、移动（改变窗口几何/前台）✅

| 序号 | 功能 | 状态 | HTTP 状态 | 说明 |
|------|------|------|-----------|------|
| C1 | 列出窗口 `GET /windows` | ✅ 通过 | 200 | 返回精简窗口列表（12 个窗口） |
| C2 | 原始列表 `GET /windows?raw=1` | ✅ 通过 | 200 | 返回完整窗口信息（含 `is_interactive`、`filter_reasons` 等） |
| C3 | 聚焦窗口 `POST /windows/focus` | ⏭️ 跳过 | - | 需要人工确认窗口焦点变化 |
| C4 | 移动窗口 `POST /windows/move` | ⏭️ 跳过 | - | 需要人工确认窗口位置变化 |

**窗口列表测试结果：**
- 精简模式：返回 12 个可交互窗口（PowerShell、ChatGPT、Clash Verge、计算器等）
- 原始模式：返回 30+ 个窗口（含系统窗口、最小化窗口、cloaked 窗口）
- 窗口信息包含：`hwnd`、`title`、`left`、`top`、`width`、`height`、`is_active`、`is_minimized`、`is_maximized`、`is_visible`、`is_cloaked`、`class_name`、`is_interactive`、`can_focus`、`filter_reasons`

**结论：阶段 C 部分通过** ✅（C3/C4 需要人工交互验证）

---

## 干扰记录

| 干扰类型 | 表现 | 消除/缓解 |
|----------|------|-----------|
| 截图文件 | 持续产生 PNG | 测试后可清理 `updates/screenshots/` 下当日目录 |
| 窗口句柄 | 多个计算器窗口 | 使用最新 `GET /windows` 获取最新 hwnd |
| 剪贴板 | 未测试键盘输入 | 后续测试需注意 |

---

## 文档偏差清单

| 序号 | 功能 | README 预期 | 实测结果 | 偏差类型 |
|------|------|-------------|----------|----------|
| B6 | `/screenshot/region` | 应返回 `path` | 返回 `path=null`（文件已保存） | 实现偏差 |

---

## 下一步计划

1. 继续执行 **阶段 D — 鼠标操作**
2. 继续执行 **阶段 E — 键盘操作**
3. 继续执行 **阶段 F — 定位（图像/OCR）**
4. 继续执行 **阶段 G — UI 树与 Widgets（只读→查询）**
5. 继续执行 **阶段 H — Widgets 动作（safe→live）**

---

*报告生成时间：2026-03-28 13:58 GMT+8*

# Desktop Control — AI 协议（契约层）

本文件描述 **HTTP API 的稳定契约**：路径、请求/响应形状与语义。实现细节与过滤启发式见 [DEV_GUIDE.md](DEV_GUIDE.md)。**长期原则**见 [CORE_PRINCIPLES.md](CORE_PRINCIPLES.md)（原则优先于本文件；冲突时改协议而非削弱原则）。

## 1. 统一响应信封

成功：

```json
{ "success": true, "data": { }, "error": null, "trace_id": null }
```

失败（业务错误以 `error.code` 为主；HTTP 状态码见各端点）：

```json
{ "success": false, "data": null, "error": { "code": "...", "message": "..." }, "trace_id": null }
```

## 2. 认证

- Header：`X-API-Key: <key>`（与 `.env` 中 `DESKTOP_API_KEY` / `DESKTOP_API_KEYS` 一致）。

## 3. Widget 文本（`POST /widgets/read` 与 `POST /ui/widgets/read`）

- **唯一主源：UIA**。本路径**不**默认执行 OCR。
- 每个 widget 含 `text` 对象与 `text_legacy`（扁平字符串，便于过渡）：

```json
"text": { "value": "确定", "source": "uia", "confidence": 1.0 },
"text_legacy": "确定"
```

- 无 UIA 可读文本时：

```json
"text": { "value": null, "source": "none", "confidence": null },
"text_legacy": ""
```

- **Schema**：`data.schema_version === "desktop_widgets.v2"`。

## 4. `POST /widgets/query`（与 `/ui/widgets/query` 等价）

- **Schema**：`data.schema_version === "desktop_widgets_query.v2"`。
- 过滤：`filters.text_contains` 对 **`text_legacy` / `text.value`** 做子串匹配（大小写不敏感）；`null` 视为无文本。
- `select`：`text` 返回对象；可选 `text_legacy`。

## 5. `POST /widgets/act`（与 `/ui/widgets/click`、`/ui/widgets/set_value` 并列）

- 请求体：`action` 为 **`click`** 或 **`set_value`**（白名单）。
- `set_value` 必须带 `value`。
- 行为与 Header `X-Desktop-Control-Mode: safe|live` 同原 click/set_value 端点。

## 6. 窗口

- `GET /windows`
- `POST /windows/focus`、`POST /windows/move`（见 OpenAPI `/docs`）。

## 7. Vision（按需感知）

- **不**写入 `widgets/read` 的 `text`；用于闭环验证、兜底识别。
- 正式路径示例：
  - `POST /vision/ocr/read` — 图像文件 OCR
  - `POST /vision/screenshot/widget` — 控件截图
  - `POST /vision/ocr/widget`、`POST /vision/widget` — 裁剪 + OCR
  - `POST /vision/find_text` — 文字 → 位置
  - `POST /vision/match_template` — 模板匹配
- **Legacy**：`/ocr/read`、`/ocr/read_widget`、`/screenshot/widget` 仍可用，响应带 `Deprecation` 与 `Link` 指向继任路径。

## 8. 列表非完整性声明

> **English (non-normative one-liner):** The widget list is a filtered semantic representation and may omit non-interactive UI elements.

`widgets` 列表为**语义过滤后的可交互表示**，不保证等于完整 UIA 树节点数；具体过滤策略见实现与 [DEV_GUIDE.md](DEV_GUIDE.md)，**不**作为协议承诺（见 [CORE_PRINCIPLES.md](CORE_PRINCIPLES.md) §5）。

## 9. 错误码

以运行时 `error.code` 为准。下表为**常见**项（非穷举；实现可能新增码，以响应体为准）。

| `error.code` | 典型 HTTP | 含义（摘要） | 调用方建议 |
|--------------|-----------|--------------|------------|
| `auth_missing_api_key` | 403 | 未带 `X-API-Key` | 补 Header |
| `auth_invalid_api_key` | 403 | 密钥不匹配 | 检查 `.env` / 配置 |
| `invalid_region` | 400 | `screen_region` 等矩形非法 | 修正为 `[x,y,width,height]` |
| `widget_not_found` | 404 | 当前快照中无该 `id` 或解析失败 | 重读 `/widgets/read` 或 `/query` 换新 id |
| `window_not_found` | 404 | 目标 hwnd 不存在 | `GET /windows` 刷新 |
| `window_focus_failed` | 409 | 窗口存在但无法置前/激活 | 人工介入或重试聚焦 |
| `action_failed` | 500 | 受保护动作执行失败（包装异常） | 看 `message`、日志；可重试 |
| `http_error` | 视情况 | FastAPI `HTTPException` 等 | 读 `message` |
| `not_found` | 404 | 文件/资源类未找到 | 检查路径参数 |
| `internal_error` | 500 | 未捕获异常 | 服务端排障 |

Vision/OCR 相关另见：`tesseract_not_found`、`pytesseract_missing`、`ocr_failed`、`locate_image_failed` 等（HTTP 多为 4xx/5xx，以响应为准）。

**原则**：失败响应与 HTTP 状态码一并使用；**不要**仅凭状态码猜语义，以 `error.code` + `message` 为准（与 [CORE_PRINCIPLES.md](CORE_PRINCIPLES.md) §1 协议优先一致）。

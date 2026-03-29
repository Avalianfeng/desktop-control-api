# Legacy 路径与迁移

## OpenAPI 行为

- **Swagger `/docs` 不列出**以下旧路径（`include_in_schema=False`），避免与 v2 对外文档混淆：**HTTP 仍可用**，用于过渡期客户端。
- 受影响典型路径：`POST /ui/widgets/read`、`/ui/widgets/query`、`/ui/widgets/click`、`/ui/widgets/set_value`，以及旧版 **`/ocr/read`**、`/screenshot/widget`、`/ocr/read_widget`（继任见下表）。

## 路径对照

以下路径**仍支持**；新集成请使用 **继任路径**。部分旧视觉路径的响应仍带 `Deprecation: true` 与 `Link: </vision/...>; rel="successor-version"`。

| Legacy | 继任 |
|--------|------|
| `POST /ocr/read` | `POST /vision/ocr/read` |
| `POST /screenshot/widget` | `POST /vision/screenshot/widget` |
| `POST /ocr/read_widget` | `POST /vision/ocr/widget` 或 `POST /vision/widget` |
| `POST /ui/widgets/read` | `POST /widgets/read` |
| `POST /ui/widgets/query` | `POST /widgets/query` |
| `POST /ui/widgets/click` / `set_value` | `POST /widgets/act`（或继续用原路径） |

## 诊断专用（需 `DESKTOP_EXPOSE_DEBUG_ROUTES=1`）

- `POST /ocr/read_window`
- `POST /locate/text`、`POST /locate/image`

## 旧版 curl（仍有效）

若客户端尚未升级，可继续使用 `/ui/widgets/read` 等 URL；响应形状与 v2 一致（`desktop_widgets.v2`）。建议在 Header 与文档中逐步切换到 `/widgets/*`。

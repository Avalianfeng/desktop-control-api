# Phase B — 路由

## 目标

- 正式路径：`/widgets/read|query|act`、`/vision/*`。
- 兼容：`/ui/widgets/*`、旧 `/ocr/*`（带 `Deprecation` 响应头，指向 `/vision/*`）。

## 完成说明

- **状态：已完成** — `server.py`：`POST /widgets/read`、`/widgets/query`、`/widgets/act`。
- `controllers/ocr_routes.py`：`build_vision_router`（`/vision/ocr/read`、`/vision/ocr/widget`、`/vision/widget`、`/vision/screenshot/widget`、`/vision/find_text`、`/vision/match_template`）。
- 诊断：`DESKTOP_EXPOSE_DEBUG_ROUTES=1` 时注册 `/ocr/read_window`、`/locate/*`（见 `settings.py`）。
- 对外 OpenAPI：旧 `/ui/widgets/*` 与部分旧 `/ocr/*` 可 `include_in_schema=False`（见 [LEGACY.md](../LEGACY.md)）。

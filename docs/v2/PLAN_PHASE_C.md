# Phase C — Widget schema v2

## 目标

- `Widget.text` 为对象：`value`（`string | null`）、`source`（`uia` | `none`）、`confidence`（UIA 侧；无则 `null`）。
- `text_legacy`：与 `text.value` 对应的扁平字符串，便于过渡期兼容。

## 完成说明

- **状态：已完成** — `semantic/widget_types.py`：`WidgetText`、`schema_version=desktop_widgets.v2`。
- `POST /widgets/query`（及兼容 `/ui/widgets/query`）：`schema_version=desktop_widgets_query.v2`；`select` 含 `text` 时返回 `text` 对象，可选 `text_legacy`。

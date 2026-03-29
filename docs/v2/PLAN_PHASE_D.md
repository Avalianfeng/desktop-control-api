# Phase D — Vision 与输出收敛

## 优先级（与实现顺序）

1. **D.4 Widget semantic filtering（优先）** — 深 UIA（如 `max_depth=20`）可能产生 **>1000** 条控件噪声；**分页对桌面 read 价值有限**（易漏控件），**语义过滤**才是主手段（非交互、装饰图、标题栏按钮策略等）。规则**不进** AI_PROTOCOL，见本文件与 [DEV_GUIDE.md](../DEV_GUIDE.md)。
2. **D.1 OCR（按需）** — `/vision/ocr/widget` 等；**不**在 `widgets/read` 内嵌。
3. **D.2 find_text** — `/vision/find_text`。
4. **D.3 模板** — `/vision/match_template`。

## Widget Filtering Strategy（设计意图）

为控制 token 与噪声，runtime **可以**在返回 `widgets[]` 前做语义过滤（**非协议承诺**）。可能包括：弱化非交互展示控件、装饰性图像、以及标题栏系统按钮的处理策略（长期可迁 `POST /windows/act`，v2.0 可先保留为 widget）。

**管道（目标形态）**：`widget_builder` → `widget_filter`（**无** read 路径 OCR enrich）。

**版本节奏**：v2.0 基础过滤 → v2.1 可配置 → v2.2+ 语义增强。

## D.1 — OCR（按需）

- 见 `/vision/ocr/read`、`/vision/ocr/widget`、`/vision/widget`。

## D.2 — Text-based visual search

- `/vision/find_text`。

## D.3 — Template matching

- `/vision/match_template`；与 UIA 正交。

## D.4 — Widget semantic filtering

- 实现与启发式仅写在代码与本文 / DEV_GUIDE；**不**锁死到 AI_PROTOCOL，避免未来调规则即破坏兼容。

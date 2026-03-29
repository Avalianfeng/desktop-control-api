# Desktop Control — 核心思想与设计原则

本文档定义 Desktop Control 系统在长期演化过程中必须遵守的核心设计原则。这些原则优先级高于具体实现与短期功能需求，用于指导协议设计、代码实现与功能扩展决策。

当实现细节与这些原则发生冲突时，应优先调整实现或协议，而不是破坏原则。

------

# 1. 协议优先（Contract First）

Desktop Control 采用协议优先设计。

系统行为必须由协议文档（AI_PROTOCOL.md）定义，代码实现必须符合协议，而不是根据现有代码反向生成协议。

这意味着：

- API 的字段结构与语义由文档锁定
- 实现不能随意增加隐式行为
- 同一请求必须产生稳定且可预测的语义结果

此原则用于防止系统逐步退化为“代码即规范”的状态。

------

# 2. UIA 是控件语义的唯一主源（UIA as Source of Truth）

在桌面自动化场景中，系统优先使用 UI Automation（UIA）提供的结构化语义信息，包括：

- Name
- Value
- LabeledBy
- ControlType

这些数据具有以下优势：

- 结构稳定
- 跨语言
- 不受主题与分辨率影响
- 低计算成本

因此：

> /widgets/read 返回的控件文本信息必须来源于 UIA，而不是视觉识别。

任何视觉识别结果都不应自动覆盖或修改 UIA 数据。

------

# 3. 视觉感知是辅助通道，而非默认步骤（Vision is Secondary Perception）

OCR 与模板匹配属于视觉感知能力，而非控件结构的一部分。

系统将感知通道分为三层：

| 层级      | 数据来源 | 用途           |
| --------- | -------- | -------------- |
| Primary   | UIA      | 控件结构与语义 |
| Secondary | OCR      | 视觉文本补充   |
| Tertiary  | 模板匹配 | 像素模式识别   |

因此：

- /widgets/read 不得默认执行 OCR
- OCR 必须通过 /vision/* 端点显式触发
- 视觉结果不得隐式改变 widget 数据

此原则用于避免视觉识别的不稳定性污染结构化 API。

------

# 4. 同形请求必须保持语义一致（Stable Semantics）

系统必须保证：

> 相同的请求在相同状态下返回相同语义结构。

这意味着：

- 不允许通过可选参数改变字段是否存在
- 不允许默认开关影响 text.value 的含义
- 不允许根据内部策略动态改变字段来源

例如：

错误设计：

```
/widgets/read
text.value 为空
↓ 开启 OCR
text.value 出现文字
```

这会导致 Agent 无法判断：

- 控件是否本来没有文字
- 还是 OCR 被关闭
- 还是 OCR 失败

因此：

```
widgets/read 只反映 UIA 状态
vision/ocr 提供额外信息
```

------

# 5. 控件列表是语义过滤后的结果（Semantic Filtering Allowed）

桌面 UI 的原始控件树通常包含大量无意义节点，例如：

- 容器
- 装饰图像
- 布局元素

系统允许在 widgets/read 中执行语义过滤，以减少噪声并控制输出规模。

但必须遵守：

- 过滤是实现细节
- 协议不承诺返回完整 UIA 树
- Agent 不应假设 widgets 数量等于实际控件数

协议只保证：

> 返回的是“可交互语义控件集合”。

------

# 6. 感知与操作必须解耦（Separation of Perception and Action）

系统按职责划分 API：

| 路径     | 职责           |
| -------- | -------------- |
| /windows | 窗口管理       |
| /widgets | 控件结构与操作 |
| /vision  | 视觉感知       |
| /debug   | 调试与诊断     |

这种划分避免出现以下反模式：

- widgets/read 自动截图
- widgets/read 自动 OCR
- widgets/act 隐式执行视觉验证

所有视觉操作必须通过 /vision/* 显式触发。

------

# 7. Agent 运行在闭环感知模型中（Closed-Loop Automation）

Desktop Control 假设调用方是具备推理能力的 Agent，而不是单步脚本执行器。

Agent 应当按以下循环运行：

```
sense → decide → act → verify → recover
```

在该模型中：

- widgets/read 提供初始结构
- widgets/act 执行操作
- vision/ocr 或 vision/find_text 用于验证状态

因此系统设计不应试图在单个 read 步骤中提供“完美感知”。

------

# 8. 视觉识别不得隐式修改结构数据（Vision Must Not Mutate Widgets）

视觉识别结果属于不稳定数据：

- 受字体、主题、分辨率影响
- 可能存在误识别
- 置信度低于 UIA

因此系统明确禁止：

- OCR 自动写入 widget.text
- 模板匹配自动改变控件状态
- read 返回混合来源文本

视觉数据只能通过独立响应返回，并带有置信度。

------

# 9. 系统优先选择确定性而非智能化（Determinism over Smartness）

在桌面自动化中，确定性比“智能识别”更重要。

系统优先选择：

- 可解释
- 可调试
- 可预测

而不是：

- 自动猜测
- 隐式补全
- 自适应行为

例如：

- 不自动执行 OCR
- 不自动点击最可能按钮
- 不自动修正控件定位

所有智能行为应由上层 Agent 决策，而不是底层 API 隐式执行。

------

# 10. 实现可以演进，但原则必须稳定（Implementation Evolves, Principles Persist）

Desktop Control 允许：

- schema 升级
- 路由重排
- 内部模块重写

但以下原则必须跨版本保持：

- UIA 主源
- Vision 按需触发
- 协议优先
- 感知与操作解耦

任何破坏这些原则的改动都应视为架构级变更，而不是普通功能更新。

------

# 11. 文档优先于记忆（Architecture Must Not Live Only in the Author’s Head）

所有关键架构决策必须记录在仓库中，而不能只存在于开发者的个人理解中。

这包括：

- 为什么 OCR 不是默认步骤
- 为什么过滤不进入协议
- 为什么 text.value 允许为 null

这些决策必须可追溯、可复查、可讨论。

------

# 12. 当出现设计分歧时的优先级顺序

当系统需要做出设计决策时，应按以下顺序评估：

```
核心思想文档
    ↓
AI_PROTOCOL
    ↓
实现代码
```

如果代码与协议冲突，应修改代码。

如果协议与核心思想冲突，应重新设计协议，而不是修改原则。

------

# 结语

Desktop Control 的目标不是成为一组临时可用的自动化脚本，而是构建一个稳定、可扩展、可推理的桌面感知与控制协议。

这些原则定义了系统的长期边界，确保在功能不断扩展的情况下，整体架构不会逐渐退化为难以维护的混合实现。
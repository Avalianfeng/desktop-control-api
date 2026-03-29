# Desktop Control v2.0 — 阶段状态

**当前阶段**：**v2.0 release candidate** — 协议、路由、schema v2 与主测试已稳定；对外文档以 README + `docs/*` 为表面。

| 阶段 | 文档 | 状态 |
|------|------|------|
| A | [PLAN_PHASE_A.md](PLAN_PHASE_A.md) | **已完成**（`docs/AI_PROTOCOL.md` 落地） |
| B | [PLAN_PHASE_B.md](PLAN_PHASE_B.md) | **已完成**（`/widgets/*`、`/vision/*`；旧路径兼容） |
| C | [PLAN_PHASE_C.md](PLAN_PHASE_C.md) | **已完成**（`desktop_widgets.v2`、`Widget.text` 对象） |
| D | [PLAN_PHASE_D.md](PLAN_PHASE_D.md) | **进行中** — 优先 **D.4 语义过滤**（降噪/token）；D.1–D.3 能力已具备 |
| E | [PLAN_PHASE_E.md](PLAN_PHASE_E.md) | 待办（Legacy 收口与可选 410） |

**原则顶层文档**：[CORE_PRINCIPLES.md](../CORE_PRINCIPLES.md)

**说明**：Phase D 的优先事项是 **输出收敛（过滤）** 而非继续扩展 vision；深 UIA 树下 widgets 数量可能上千，过滤策略见 [PLAN_PHASE_D.md](PLAN_PHASE_D.md) 与 [DEV_GUIDE.md](../DEV_GUIDE.md)。

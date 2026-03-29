# Desktop Control v2.0 文档评审报告

**评审人：** Clawdy（AI 代理）  
**评审日期：** 2026-03-29  
**评审范围：** README.md + docs/ 全部文档 + docs/v2/ 状态文档  
**文档版本：** v2.0 release candidate

---

## 一、总体评价

v2.0 的文档框架已经非常扎实，核心原则和协议都很清晰。三层文档结构设计优秀：

```
CORE_PRINCIPLES.md（原则层）→ AI_PROTOCOL.md（协议层）→ 代码与 OpenAPI（实现层）
```

这是一个**对外可用的专业 API 文档**，但距离"保姆级"还有一点距离（主要是示例和故障排查）。

| 维度 | 评分 | 说明 |
|------|------|------|
| 结构清晰度 | ⭐⭐⭐⭐⭐ | 三层文档结构非常好 |
| 协议完整性 | ⭐⭐⭐⭐ | 核心契约完整，但错误码和边界情况待补充 |
| 示例充足度 | ⭐⭐⭐ | 单个 API 示例有，但完整工作流缺少 |
| 可读性 | ⭐⭐⭐⭐ | 专业术语准确，但新手可能需要更多引导 |
| 版本管理 | ⭐⭐⭐ | v2 状态清楚，但 v1 迁移策略不明确 |

---

## 二、做得好的地方

### 1. 文档层级清晰

三层结构让不同读者能快速找到自己需要的内容：
- **人（首次安装、排障）** → 快速开始 → 使用约束 → 文档导航
- **AI / 自动化集成** → 最小 JSON 契约 → AI_PROTOCOL.md

### 2. 核心原则明确

12 条核心原则里，以下几条尤其重要且定义清晰：
- **UIA 是主源**（原则 2）—— 避免视觉识别污染结构化数据
- **视觉感知按需触发**（原则 3）—— 不在 read 里默认跑 OCR
- **同形请求语义一致**（原则 4）—— 保证确定性
- **感知与操作解耦**（原则 6）—— 职责清晰

### 3. v2 的 API 设计更简洁

- `/widgets/read`、`/widgets/query`、`/widgets/act` 统一了控件操作
- `/vision/*` 统一了视觉能力
- `text` 字段从字符串改成对象 `{value, source, confidence}` 更精确

### 4. 读者指引贴心

README 开头的表格告诉不同读者应该按什么顺序阅读，很实用。

---

## 三、疑问和可能的误解

### 1. v2 路径和旧路径的关系不够清楚

**原文：**
> 旧路径仍可用，见 docs/LEGACY.md

**疑问：**
- 旧路径是**永久兼容**还是**临时兼容**？
- 什么时候会移除旧路径？
- 新调用方应该优先用哪个？

**建议：** 在 README 加一句明确的迁移策略，例如：
> 旧路径（如 `/ui/widgets/read`）目前兼容，但新集成请优先使用 `/widgets/read`。旧路径将在 v3.0 移除（预计 2026 Q3）。

---

### 2. `/widgets/act` 的白名单操作没有列全

**原文：** API 概览表格里只写了 `click | set_value`

**疑问：**
- 还有没有其他支持的操作？（比如 `hover`、`select`、`scroll`？）
- 如果不支持，是否应该明确说"仅支持"？

**建议：** 在 API 概览表格里补充：
> 支持操作：`click`、`set_value`（白名单，扩展中）

---

### 3. `text_legacy` 的用途有点模糊

**原文：**
> `text_legacy`：与 `text.value` 对齐的扁平字符串，便于过渡

**疑问：**
- "过渡"是什么意思？
- 是为了兼容旧代码？还是为了方便某些场景？
- 什么时候可以不用它？

**建议：** 加一句具体场景，例如：
> `text_legacy` 用于兼容旧代码或简单字符串匹配场景；新集成建议直接使用 `text.value`。

---

### 4. `/vision/find_text` 的请求示例缺少 `confidence` 说明

**原文：**
> 请求无 `confidence` 字段

**疑问：**
- 响应里有 `confidence: 92`，调用方如何控制阈值？
- 如果我想找置信度 > 80 的结果怎么办？

**建议：** 在示例后加一句：
> 如需置信度阈值，请在调用方过滤 `location.confidence`。

---

### 5. 环境配置示例分散

**现状：**
- README 说"复制 `.env.example` 为 `.env`"
- DEV_GUIDE.md 有一个环境变量表格
- 但具体有哪些变量、默认值是什么，需要跨文档查找

**建议：** 在 README 快速开始里加一个最小 `.env` 示例：
```ini
DESKTOP_API_KEY=desktop-control-key
DESKTOP_HOST=127.0.0.1
DESKTOP_PORT=8765
```

---

### 6. 错误码列表不完整

**原文：**
> 常见：`auth_missing_api_key`、`auth_invalid_api_key`、`widget_not_found`、`window_focus_failed`、`action_failed` 等

**疑问：**
- 还有没有其他常见错误码？
- 每个错误码的 HTTP 状态码是多少？
- 调用方应该如何处理（重试/放弃/询问用户）？

**建议：** 在 AI_PROTOCOL.md 加一个错误码表格，包含：
- 错误码
- HTTP 状态码
- 含义
- 建议处理方式

---

## 四、建议补充的内容

### 1. 典型工作流示例

**现状：** README 有单个 API 示例，但缺少**完整工作流**。

**建议添加：**
```python
# 场景：点击"登录"按钮
import requests

API_BASE = "http://localhost:8765"
API_KEY = "desktop-control-key"
headers = {"X-API-Key": API_KEY}

# 1. 读取控件
widgets = requests.post(f"{API_BASE}/widgets/read", headers=headers, json={
    "max_depth": 8, "include_text_widgets": true
}).json()["data"]["widgets"]

# 2. 查询目标按钮
result = requests.post(f"{API_BASE}/widgets/query", headers=headers, json={
    "filters": {"role": "button", "text_contains": "登录"}
}).json()

# 3. 执行点击（safe 模式先验证）
requests.post(f"{API_BASE}/widgets/act", headers=headers, json={
    "action": "click",
    "id": result["widgets"][0]["id"]
})

# 4. 真实执行
live_headers = {**headers, "X-Desktop-Control-Mode": "live"}
requests.post(f"{API_BASE}/widgets/act", headers=live_headers, json={
    "action": "click",
    "id": result["widgets"][0]["id"]
})

# 5. 验证（可选 OCR）
requests.post(f"{API_BASE}/vision/ocr/widget", headers=headers, json={
    "id": result["widgets"][0]["id"]
})
```

---

### 2. 性能与 token 优化建议

**现状：** README 提到过滤可以减少 token，但缺少具体数据。

**建议添加表格：**

| 窗口类型 | widgets 数量 | 推荐 max_depth |
|----------|-------------|---------------|
| 记事本 | ~30 | 8 |
| VS Code | ~500 | 6 |
| 浏览器 | ~1000 | 5 |
（ps:浏览器有自带的操作方法，用户不建议使用这个服务，另外微信，qq之类的可能需要达到20,是后续待优化的内容。）
---

### 3. 版本兼容性说明

**现状：** STATUS.md 说现在是 v2.0 release candidate，但缺少迁移指南。

**建议补充：**
- v1.x 的代码还能用吗？
- 哪些是 breaking changes？
- 迁移指南在哪里？

建议在 LEGACY.md 或 README 加一个版本兼容性表格。

---

## 五、可能多余的内容

### 1. README 的"特性"列表信息密度低

**原文：**
```markdown
## 特性

- UIA 驱动的控件快照与查询（`schema_version=desktop_widgets.v2`）
- 统一响应信封：`{ "success", "data", "error", "trace_id" }`
- 按需视觉：`/vision/ocr/widget`、`/vision/find_text`、`/vision/match_template` 等
- Agent 友好：`/widgets/act` 白名单操作；`X-Desktop-Control-Mode` 控制是否真实点击/输入
```

**建议：** 删掉或精简成一句话：
> 基于 UIA 的桌面感知与控制服务，提供结构化控件树、稳定 widget id 和按需视觉能力。

---

### 2. LICENSE 章节可以删掉

**原文：**
```markdown
## 许可证

MIT License
```

**建议：** 既然仓库根目录有 LICENSE 文件，README 里可以不用重复。或者改成：
> 许可证：MIT（见仓库根目录 LICENSE 文件）

---

## 六、总结评语

### 优点

1. **架构清晰** —— 三层文档结构（原则 → 协议 → 实现）是专业 API 设计的典范
2. **原则坚定** —— 12 条核心原则为系统长期演化提供了明确边界
3. **协议稳定** —— v2 的 JSON 契约定义准确，字段语义清晰
4. **读者友好** —— 开头的读者指引表格体现了对用户的关怀

### 待改进

1. **示例不足** —— 缺少从"读→查→执行→验证"的完整工作流
2. **错误处理** —— 错误码列表和处理建议需要补充
3. **迁移指南** —— v1→v2 的迁移路径不明确
4. **性能数据** —— 缺少典型场景的性能参考值

### 最终评语

> **Desktop Control v2.0 是一份"骨架完整、血肉待丰"的专业文档。**
>
> 核心架构和设计原则已经非常扎实，三层文档结构体现了对长期维护的深思熟虑。UIA 作为主源、视觉按需触发、感知与操作解耦等原则，为系统建立了清晰的边界。
>
> 主要差距在于**新手引导**和**故障排查**：完整工作流示例、错误码处理建议、性能优化指南等内容，能让调用方更快上手、少走弯路。
>
> **推荐状态：** 可以对外发布，但建议在 v2.1 迭代中优先补充示例和故障排查内容。
>
> **综合评分：** ⭐⭐⭐⭐（4/5）

---

**评审人署名：** Clawdy  
**生成时间：** 2026-03-29 23:45 CST

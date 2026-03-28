# updates/ 目录说明与整理建议

本目录用于**运行期产物**、**人工/阶段文档**与**变更记录**。默认会随使用变“杂”，建议按类型分子目录，并明确哪些应提交 Git、哪些仅本地保留。

## 文档索引（`updates/docs/`）

阶段测试与验收类 Markdown 统一放在此子目录：

| 文档 | 说明 |
|------|------|
| [验收报告](docs/验收报告.md) | 验收摘要 |
| [给AI的测试计划](docs/给AI的测试计划.md) | AI 侧测试计划 |
| [测试报告 - 完整阶段](docs/测试报告%20-%20完整阶段.md) | 完整阶段测试报告 |
| [测试报告 - 阶段 ABC](docs/测试报告%20-%20阶段%20ABC.md) | 阶段 ABC 测试报告 |

根目录其余 `.md`（如 `优化-*.md`、`v1.8.x` 等）仍为版本/优化纪要，可按需后续迁入 `docs/`。

## 推荐子目录约定

| 路径 | 用途 | 是否建议入库 |
|------|------|----------------|
| `updates/docs/` | 测试报告、验收、计划等**可共享**文档 | 通常 **入库** |
| `updates/traces/` | live 动作审计 JSONL（`action_trace.v1`），按日期文件名 | 已由 `.gitignore` 忽略 `*.jsonl`；可按需保留脱敏样例 |
| `updates/recorder/` | Dev Recorder 输出 `*.jsonl`、`recorder.state.json`、stop 信号 | 已由 `.gitignore` **整目录忽略** |
| `updates/screenshots/` | `POST /screenshot` 等落盘 PNG | 通常 **不入库**（可在 `.gitignore` 中追加） |
| `updates/steps_demo_*.json` | `test_client.py --record-demo` 等演示步骤 | 可选入库（小文件、无敏感） |
| `updates/*.md`（根层） | 版本说明、优化纪要 | 可入库；建议命名带日期或版本号 |

## 整理步骤（可选）

1. **固定产物目录**：沿用 `traces/`、`recorder/`、`screenshots/`；新文档优先放 `updates/docs/`。
2. **索引**：本文「文档索引」维护 `docs/` 内主要文件链接；根层只保留索引型 README 与零散纪要。
3. **`.gitignore`**：已加入 `updates/recorder/` 与 `updates/traces/*.jsonl`。若仍不需要提交截图目录，可追加 `updates/screenshots/`。
4. **敏感**：trace 中含 `api_key_sha256_8`（非明文 key），仍勿对不可信方公开原始 JSONL。

**已从 Git 跟踪的文件**：若某 `updates/traces/*.jsonl` 或 `updates/recorder/` 下文件曾被提交，加入 ignore 后需执行一次 `git rm -r --cached updates/traces/*.jsonl`（及 recorder 路径）再提交，才能从索引中移除（本地文件可保留）。

## 与「优化-*.md」的关系

根层 `优化-01/02/03-*.md` 为对已合并能力的**维护纪要**；与 `v1.8.x` 等版本说明可并存，或后续统一迁入 `updates/docs/` 并在本文加链接。

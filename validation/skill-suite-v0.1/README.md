# Skill Suite v0.1 Validation

本目录包含三个可独立用 OpenCode 打开的验证工作区，用来检验当前 skill suite
在不同难度下是否真正改善最终交付，而不只生成看起来完整的文档。

| Level | Workspace | Main pressure |
|---|---|---|
| L1 | `01-basic-cli/` | 明确、可逆、本地任务；direct fast path、红绿隔离、空结果语义 |
| L2 | `02-sqlite-increment/` | 持久化与事务；Phase 0、薄切片、SI、不得整轮重放 |
| L3 | `03-http-recovery/` | 真实 HTTP 边界；预算探针、三次熔断、owner recovery、schema drift CR |

固定模型：

- 规划、评审、SI、CR、复盘：`zhipuai-coding-plan/glm-5.3`
- 测试编写、实现、恢复执行、Finish：`zhipuai-coding-plan/glm-5.3-flash`

先读 `START.md`，准备阶段记录见 `SETUP-VERIFICATION.md`，最终结果填写到
`VALIDATION-ARCHIVE.md`。每个工作区还有自己的 `START.md`、`TASK.md`、
`ACCEPTANCE.md` 和 `docs/benchmark-run-log.md`。

三个 `.opencode/skills/` 是当前六个 skill 的独立物理副本，不引用本仓库根目录。
不要在验证期间同步或修改这些副本，否则该档结果失效。

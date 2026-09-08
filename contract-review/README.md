# contract-review

这个内部 skill 由 `/plan` 的 Audited 路径调用：先做 Phase 0 风险探针，再把需求
变成只覆盖第一条薄端到端切片的独立评审契约，并在同一次 `/plan` 中编译成可执行
PLAN。计划内扩展写成 SI；CR 只处理契约与现实不符的异常恢复。

需求还说不清时不要硬评审。它会先调用 grill；当前请求明确引用 brief 时，评审
必须逐项说明简报内容进入了哪些契约节点，或者为什么推迟/拒绝。漏项、hash
不符、简报未确认，契约都不能 passed。无参 `/plan` 不会根据旧文件猜输入。

设计权衡、项目评估和轻量质疑保留为自然语言或内部 reviewer 模式，不占用公开命令。

主要产物是 `docs/contract.md`、`docs/PLAN.md` 和 Phase 0 证据。规范以
`references/contract-schema.md` 为准；修改后运行
`python .opencode/workflow/scripts/check.py --selftest`。

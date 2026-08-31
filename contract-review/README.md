# contract-review

这个 skill 做两件事：`/review` 把需求变成经过独立评审的契约，`/plan` 再把
通过的契约编译成可执行 PLAN。

需求还说不清时不要硬评审。它会先调用 grill；当前请求明确引用 brief 时，评审
必须逐项说明简报内容进入了哪些契约节点，或者为什么推迟/拒绝。漏项、hash
不符、简报未确认，契约都不能 passed。无参 `/review` 不会根据旧文件猜输入。

其他入口只在特定情况下用：`/debate` 检查已有设计，`/assess` 判断值不值得
做，`/challenge` 则直接交给 reviewer 做轻量质疑。

主要产物是 `docs/contract.md` 和 `docs/PLAN.md`。规范以
`references/contract-schema.md` 为准；修改后运行
`python .opencode/workflow/scripts/check.py --selftest`。

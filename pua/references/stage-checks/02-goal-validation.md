## 2. `goal-validation`

**位置**：`mvp-delivery/SKILL.md` 的 Establish The Target 和 goal 校验。

**输入**：当前 goal card、原始请求/brief、outcomes、verification 命令。

**质询与动作**：

- “BS 被悄悄缩水、改名或塞进 deferred 了吗？”逐个检查 source coverage 和 disposition。
- 确认每个 outcome 的 verification 是可执行断言，至少一个 `user_entry: true` 走真实入口。
- 检查 owner 决定、原始边界、目标环境和代表性输入没有被 mock、fixture 或内部 selftest 替换。
- 发现定义变化时按既有全量失效规则清 evidence，不在 PUA 检查中手工置 active/verified。

**证据**：`check.py goal` 输出、source/coverage 对照、用户入口说明和验证命令审查。

**出口**：结构 gate 失败交给 engine；语义覆盖缺口保持 pending/blocked；不能用 PUA 结果完成 goal。


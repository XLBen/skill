## 9. `goal-verification`

**位置**：`mvp-delivery/SKILL.md` 的每 outcome `verify-goal`。

**输入**：当前 goal、outcome、真实入口、验证命令、fresh evidence 路径和当前制品身份。

**质询与动作**：

- “你验证的是当前版本，还是过去某个曾经绿过的版本？”核对 evidence 路径、输入、环境和版本身份。
- 每个 outcome 都必须有内容/状态/schema/count/user-visible 断言；不以 exit 0、label 或旧 hash 代替。
- 修复一个 outcome 后检查同一根因和受影响 outcomes；影响不确定时按现有规则全量重跑。
- 真实 boundary 缺失时保持 pending/blocked，不能用 sample/mock 改写目标。

**证据**：每个 outcome 的 fresh `verify-goal` 输出、evidence hash、失败原文和用户入口结果。

**出口**：失败由 engine 置 blocked 并保留 evidence；不能手工写 verified/complete。


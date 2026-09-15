## 6. `step-verification`

**位置**：`step-executor/SKILL.md`、`construction/SKILL.md` 的 exact V 和 `verify-step`。

**输入**：单步 spec、精确 V、manifest、attempt、原始 V 输出和 failure signature。

**质询与动作**：

- “这一步是真的跑了，还是你手写了一个 passing event？”只接受 engine 生成的 evidence/event。executor 席位只检查自己持有的证据（manifest、保护路径、诊断运行）；engine 生成的 `verify-step` evidence/event 属门后证据，由主控在 construction 侧执行本卡时核对。
- 检查所有 manifest-required 场景、子进程状态、输入快照、内容断言、重复运行和 cleanup。
- 失败一次读根因；第二次同类失败换实质方法；第三次按既有熔断，不做第四次普通重试。
- executor 只返回原始结果、偏差和 blocker；不宣布 step complete、不写 ledger、不修改冻结测试。

**证据**：`verify-step` 输出、engine event/evidence、原始 V、attempt 和 signature。

**出口**：通过交给 controller；失败交 recovery/CR；不允许用 PUA 文字覆盖机器 gate。


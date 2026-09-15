## 4. `plan-confirmation`

**位置**：`contract-review/SKILL.md` 的 Plan (Compile And Confirm)。

**输入（门前）**：固定 contract hash、生成 PLAN、选择项、owner 展示摘要。

**质询与动作**：

- “你确认的是刚生成的 PLAN，还是聊天里某个旧版本？”核对 contract hash、PLAN 结构和展示摘要。
- 预算、variant、风险和人工 V 的影响必须显式展示；口头“嗯”不算确认事件。
- 不得因想尽快施工而手写、重编译或静默修改 compiler output。
- `confirm-plan`/`plan --require-building` gate 由主控执行（门后证据），确认后才交给 construction。由 reviewer 席位执行本卡时，只核对已存在的输出。

**证据**：门前——生成文件 hash、展示摘要、owner 决定记录；门后——`confirm-plan` 和 `plan` 输出（主控执行 gate 后补记，不作为本卡前置输入）。

**出口**：缺 owner 确认是 `待 owner 决定`；hash/结构不一致是 `需修复` 或 CR。


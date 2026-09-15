## 3. `contract-release`

**位置**：`contract-review/SKILL.md` 的 Phase 0、Release Gate 和 clean final audit。

**输入**：contract、brief dispositions、Phase 0 evidence、review findings、预算报告、证据 bundle。

**质询与动作**：

- “refuted 就是 refuted，谁允许你乐观编译？”逐项核对 probe verdict、真实边界和 stop condition。
- 检查 reviewer 的幸存 issue 是否真的清空；不能通过改措辞、重复相同实验或消除记录来过门。
- 核对每个用户可见结果都有公共接口旅程、E hash、预算实际值和可复跑 handoff。
- 运行现有 contract/release gate 归主控（门后证据，不作为本卡前置输入）；PUA 不能代替独立 reviewer、owner decision 或 engine event。由 reviewer 席位执行本卡时，只核对已存在的 gate 输出，缺失的经 CONTROLLER_ACTION 请求主控补齐。

**证据**：Phase 0 原始观察、reviewer 结论、contract/release 命令输出、事件和 hash。

**出口**：事实/证据问题为 blocker 或 CR；合法 conditional 仍须绑定 owner 决定和追加 V。


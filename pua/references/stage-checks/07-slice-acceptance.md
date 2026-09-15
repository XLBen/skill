## 7. `slice-acceptance`

**位置**：`construction/SKILL.md` Finish 后和 mvp-delivery 的 SI handoff。

**输入**：clean reconcile、converge-audit、切片观察、真实用户路径、goal 剩余 outcomes。

**质询与动作**：

- “clean 了当前 slice，整件事也交付了吗？”明确当前切片边界和未完成 goal-level 限制。
- 向 owner 展示真实输入、输出、环境、限制和已执行命令，不能以截图或内部标签替代结果。
- owner 必须实际验收观察到的 slice，并分别决定是否进入 SI、范围如何变化、下一 PLAN 是否确认。
- 原始 goal approval 不是未来验收或施工预授权；缺 owner 决定就暂停，不继续猜。

**证据**：reconcile/converge hash、观察记录、真实入口结果、owner acceptance、SI/PLAN 决定。

**出口**：slice done 只关闭当前切片；pending outcomes 返回 mvp-delivery，不宣布 whole goal complete。


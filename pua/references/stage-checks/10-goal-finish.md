## 10. `goal-finish`

**位置**：`mvp-delivery/SKILL.md` Finish With Evidence、`finish-goal` 前；build/fix/resume wrapper。

**输入**：原始请求或 brief、全部 BS、整个 goal、deferred、所有 fresh evidence、README/quickstart、隔离复跑结果。

**质询与动作**：

- “所有结果都拿到了，还是只把首片包装成 MVP 完成？”逐项对照原始范围、每个 outcome、deferred 和真实用户旅程。
- 存在 ui-acceptance sidecar 时，最终核对交付产物身份与 `artifact_identity` 一致、
  必需场景全部 `passed` 或有理由的 `not-applicable`，晚于绑定的新改动已使受影响
  场景失效并重验。
- 检查最后版本的集成路径、受影响回归、setup/use 隔离复跑、README、依赖和环境差异。
- 再跑一次主动查漏：测试是否被弱化、是否硬编码样例、吞错、漏接线、同类问题未扫。
- 只有 PUA 检查、适用 Audited gate、owner acceptance 和 `finish-goal` 全部满足，才允许完成；engine 不可用一律 blocker；独立席位不可用按 mvp-delivery 验收章节分档（Audited 独立性 gate 阻塞，Normal/Guarded 记录 capability-unavailable 后按控制器检查披露收尾）。

**证据**：门前——最终版本身份、integrated/user-entry 输出、隔离复跑、reviewer 范围检查；门后——`finish-goal` 输出（主控执行 gate 后补记，不作为本卡前置输入，reviewer 席位不得因它缺失而阻塞）。

**出口**：缺实现与缺验证分别记录；阻塞不能包装完成，完成不能只靠流程工件数量证明。


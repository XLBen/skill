## 8. `review-verdict`

**位置**：`reviewer/SKILL.md` Invariants，以及 contract/construction dispatch。

**输入**：review mode、contract-bound 时的固定 snapshot/hash，或无契约 handoff 的
artifact identity、范围和证据；test manifest、工作树 diff、reconcile 和作者记录
按 step/converge 或产品行为适用时提供。

**质询与动作**：

- “审出一个问题就收工？”用冰山法则检查同一根因、接口、共享实现和受影响调用链。
- 评审结论必须有具体证据；不能为凑问题发明要求，也不能为了让 contractor 通过降低严重度。
- 对 step/converge 或实际产品行为检查作者独立性、冻结 hash、行为红先于实现、
  内容/状态断言和 whole-goal 边界；对无产品行为或不适用 acceptance test 的 direct
  路径记录 `not-applicable` 及理由，不伪造 manifest、behavior-red 或作者隔离。
- 无契约 Normal/Guarded handoff 只检查声明、artifact identity、范围、实际证据和
  user-entry；不得把 Audited 的契约字段或 construction 专用工件升级为新要求。
- handoff 含 ui-acceptance sidecar 时，逐场景核对适用性判定、`artifact_identity`
  绑定、`passed` 是否有结果证据与原生调用引用，未决 `failed/blocked` 场景是否
  如实暴露；reviewer 只读，不操作界面，缺执行证据经 CONTROLLER_ACTION 请求主控补测。
- reviewer 只读，只返回发现；controller 负责裁决、修复路由、owner 和 engine 状态。

**证据**：结构化 reviewer JSON、发现对应的路径/ID/输出、独立派发 provenance。

**出口**：有 material issue 返回需修复；独立性不可用阻断 Audited release；零 issue 也要有完整范围依据。


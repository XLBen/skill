# Subagent Orchestration Protocol

> When to read: before any dispatch decision in plan/build/fix/resume, when
> choosing an execution seat for a task, and before recording dispatch state.

本协议是所有模式共用的唯一委派规则。主控制器（本 skill）持有目标、依赖、
集成、最终验证和持久状态；实质工作默认交给子代理，主控不做实现者。

## Dispatch Trigger Matrix

“实质任务”的判定条件（满足任一即实质）：改变产品行为、改变公开接口、
修复缺陷、跨文件逻辑调整、或需要独立正确性判断。仅凭“主控自己做更快”
不构成跳过理由。

| 场景 | 默认执行方式 | 强制级别 |
|---|---|---|
| 单点拼写/格式/明确机械小改 | 主控直接处理；多个同类小改合并为一个工作包 | 禁止拆分派发 |
| 需要定位模块、依赖资料、根因分析 | 派 research 子代理；两个以上独立问题域并行 | 默认派发 |
| Normal/Guarded 实质实现任务 | 派 worker 子代理（轻量实现席位） | 默认派发 |
| `/fix` 根因不明 | 先派 research 诊断，凭证据再派实现 | 默认派发 |
| 多个可独立复现的故障 | 按问题域并行派 research/worker | 默认派发 |
| 每个实质切片验收交接 | 派 fresh reviewer（见 SKILL.md 验收章节） | 能力可用即必须 |
| 全目标 finish 检查 | 派 reviewer 复用 review 能力做 whole-goal 检查 | 能力可用即必须 |
| Audited 测试冻结/步骤执行/评审 | test-author / step-executor / reviewer 按既有严格规则 | 必须且阻塞 |
| `direct` profile 的 Audited 施工 | 主控同会话执行，不派 step-executor | 禁止派发 |

同一版本产物已被终审覆盖且未再变化时，可复用该终审结果，不重复派发。

## Role To Agent Mapping

优先使用安装器提供的项目子代理（`.opencode/agents/mvp-*.md`）：

| 角色 | 首选 agent | 只读回退 | 说明 |
|---|---|---|---|
| research | `mvp-researcher` | 内建 `explore`/`scout` | 调研、定位、根因分析 |
| worker | `mvp-worker` | 内建 `general` | Normal/Guarded 实现工作包 |
| reviewer | `mvp-reviewer` | 无（禁止回退到会话内） | 只读评审，加载 `reviewer` skill |
| test-author | `mvp-test-author` | 无（Audited 阻塞） | 冻结验收测试 |
| step-executor | `mvp-step-executor` | 无（Audited 阻塞） | 单个编译步骤 |

回退规则：只读角色可回退到内建只读 agent；写入角色仅在回退 agent 具备
写入工具时可用；reviewer/test-author/step-executor 涉及独立性声明时
不允许回退。映射不可用时按 Failure Branches 处理，不得换更宽权限的代理
绕过。agent 定义不写死模型 ID；缺省继承运行时模型。

## Dispatch Preflight

首次派发前（以及怀疑环境变化时）检查并记录结果：

1. runtime 的 task/subagent 工具实际可用；
2. 目标 agent 名称在可用列表中（不凭记忆假设）；
3. 该 agent 的工具边界满足任务需要（reviewer 无写入；worker 有写入）；
4. 任务输入文件在允许读取范围内。

preflight 失败按 Failure Branches 降级或阻塞，并在 dispatch record 记录
原因。不把“配置文件存在”当作“运行时已加载”。

## Concurrency Rules

- 同时最多 3 个子代理；共享工作区同时最多 1 个写入者。
- 只读 research/review 可并行；worker 运行时主控只做不重叠工作。
- reviewer 评审期间被评产物必须稳定：先完成写入、再派评审。
- 并行派发只用于经确认互不共享文件/状态的任务；不确定时串行。
- 子代理不再递归派发子代理；需要协作时返回主控协调。
- 所有 agent prompt 要求子代理返回结构化结果而不是自由叙述。

## Fresh Session Semantics

- 新任务一律 fresh dispatch，不继承主控或先前作者的上下文。
- 同一实现任务的返修轮可以 resume 原执行者（携带 findings）；超过
  轻量上限（3 轮）后换 fresh seat 并附上全部 findings 与已试记录。
- reviewer 与被评实现的作者必须是不同 session；worker 不能评审自己的
  产出，主控不能在采纳前改写 reviewer 的 findings。
- 真实 session/task 标识由主控从 dispatch 工具结果记录；子代理自报的
  ID 只是声明，不作为独立性证据。

## Dispatch Record

每个 goal 维护 `.opencode/mvp/<goal-slug>.dispatch.json`（与目标卡同目录、
同 slug），仅由主控写入：

```json
{
  "schema_version": 1,
  "goal_id": "G-NAME",
  "tasks": [
    {
      "task_id": "T-01",
      "role": "worker",
      "depends_on": [],
      "status": "done",
      "provenance": {"session_id": "<runtime-reported>", "agent": "mvp-worker"},
      "artifact_baseline": "<commit或产物hash>",
      "review_scope": "<task或goal>",
      "skip_reason": null
    }
  ]
}
```

- `status`: pending | dispatched | done | failed | skipped。
- 跳过委派必须写 `skip_reason`（如 mechanical-batch、capability-unavailable）。
- 该记录只服务恢复与观测；完成判定仍归 goal/engine gate，不替代
  `verify-goal`/`finish-goal` 证据。
- resume 时先核对 dispatch record 与实际产物：done 且产物未失效的任务
  不重复派发；timeout 不等于未执行，重新派发写入任务前必须检查实际改动。

## Failure Branches

| 失败 | 处理 |
|---|---|
| task 工具或 agent 不可见 | 记录 capability-unavailable；Normal/Guarded 主控降级执行并明确披露非独立；reviewer/test-author 类独立性 gate 按 SKILL.md 验收章节与 Audited 规则阻塞 |
| 权限拒绝 | 不换更宽权限代理绕过；按不可用处理并记录 |
| 子代理返回 needs_context | 补充输入后继续同一任务，不新建任务 |
| 子代理返回 blocked | 主控核实原因；属目标级阻塞按 SKILL.md 停止条件升级 |
| 返修连续无新证据 | 轻量流程 3 轮上限后换 fresh seat；仍失败按 no-progress blocker 升级；严格流程遵守既有熔断 |
| 并行任务产物冲突 | 串行重放冲突任务；冲突检测在集成时执行 |

## Integration Duties

主控集成所有子代理产物：核对返回格式、复验关键断言、运行目标卡验证、
更新 goal 状态与 dispatch record。子代理的返回不直接写 ledger/goal 卡；
多个并行结果先查共享文件冲突再采纳。

# Subagent Dispatch Templates

> When to read: before composing any subagent dispatch or adjudicating a
> subagent's return message.

所有派发与返回使用固定格式，方便 GLM 稳定执行与主控机械校验。字段缺失
的派发是缺陷；返回不合式的结果按 needs_context 处理，不猜测填充。

## Dispatch Template

```text
DISPATCH
task_id: <T-NN, 对应 dispatch record>
role: research|worker|reviewer|test-author|step-executor
goal: <一句话目标与验收条件，可观察、可判定>
inputs:
  - <文件路径或确切数据；标注哪些是必读约束>
write_scope: <允许修改的路径；reviewer/research 为 read-only>
baseline: <当前产物基线：commit/hash/目标卡状态>
dependencies: <依赖的先前任务结论或接口决定；无则 none>
verification: <要求执行的验证命令与预期；无则 none>
return_format: <按角色的返回格式，见 Return Format Matrix>
stop_conditions: <何时必须停下返回 blocked；至少含权限不足、范围外改动需求>
constraints:
  - <禁止递归派发子代理>
  - <不修改 write_scope 之外的文件>
  - <角色特定约束，如 reviewer 只读>
```

写法要求：

- dispatch 只描述一个任务，不粘贴会话历史或先前任务摘要；接口结论以
  dependency 条目精炼传入。
- 精确值（数字、签名、测试用例）放在 inputs 的文件里或直接内联，不写
  “参见上文”。
- reviewer 派发额外包含 `ACCEPTANCE_HANDOFF` 全文与 `pua_stage_id`，
  并要求其加载 `pua` skill 与对应检查卡，返回 `issues` 与
  `pua_acceptance`（见 `../contract-review/references/reviewer-protocol.md`）。
- worker/research 派发明确单文件或单工作包；不确定影响面时先派
  research 缩小范围。
- test-author 派发必须包含调用方解析好的 manifest 路径；step-executor
  派发必须包含 step ID 与 exact V（正式 V 由主控执行，见
  Controller-Action Request）。

## Return Format Matrix

每个角色使用固定的一种返回格式；主控按该角色的格式校验，不把 RESULT
当作所有角色的隐式父接口：

| 角色 | 返回格式 | 必需字段（缺失按 needs_context 退回并指出字段） |
|---|---|---|
| research / worker | `RESULT` | task_id、status、summary；done 时 verification 非空 |
| reviewer | reviewer-protocol JSON | mode、issues、checked_scope；review 模式每个 issue 带 classification（见 reviewer-protocol.md Output） |
| test-author | `TEST_AUTHOR_HANDOFF` | slice、spec_hash、test_author_id、manifest、protected_acceptance、pre_change_result |
| step-executor | `STEP_HANDBACK` | step、implementation_files、protected_unchanged、pending_v、deviations/blockers |

合法的角色专用返回不得因不含 RESULT 字段而被退回。格式返工不是产品返工：
不得通过重新生成测试、重跑 pre-change 或重放实现来“修复格式”；格式错误
与缺少业务上下文是不同的 needs_context 原因，不得无限往返。

## Controller-Action Request

子代理在共享桌面、engine 正式 V 或其他只有主控能执行的动作前，不等待、
不自行代跑，返回：

```text
CONTROLLER_ACTION
task_id: <T-NN>
requested_action: run-command | gui-scenario | engine-verify
target: <命令、场景或 step/V ID>
authorization_scope: <需要的授权边界；无则 none>
expected_evidence: <主控执行后应产生的证据路径/输出>
artifact_identity: <当前产物身份，供恢复时核对>
resume_hint: <证据就绪后恢复哪个席位/阶段>
```

这是 `needs_context` 的一个具体类型：等待主控动作，不是外部阻塞，也不是
owner 阻塞。主控执行一次、保存证据，然后把证据按 resume_hint 传回原席位
继续；恢复时重取当前 GUI/环境状态，不重放旧操作。同一正式 V attempt 只由
主控执行一次，子代理的诊断运行不得作为替代。

## Result Template

```text
RESULT
task_id: <T-NN>
status: done|needs_context|blocked
summary: <实际完成内容，一到三句>
artifacts:
  - <修改的文件或发现的位置>
verification:
  command: <实际执行的命令>
  result: <通过/失败及关键输出位置；无则 none>
open_issues: <未解决问题；无则 none>
```

- `done` 要求 verification 非空（纯调研任务报告发现位置）。
- `needs_context` 必须列出缺失的具体输入。
- `blocked` 必须给出可核实的原因与最小解锁动作。
- reviewer 返回沿用 reviewer-protocol 的结构化 JSON（`issues` +
  可选 `pua_acceptance`），不使用 RESULT 模板。

## Step-Handback Template (step-executor)

step-executor 交回实现，不等待正式 V；正式 `verify-step` 由主控在收到
hand-back 后执行一次（见 step-executor/SKILL.md）：

```text
STEP_HANDBACK
task_id: <T-NN>
step: <S-ID>
implementation_files:
  - <实际改动的文件>
protected_unchanged:
  - <manifest 保护路径=hash 核对结果>
diagnostic_runs:
  - <命令与原始输出位置；无则 none>
pending_v: <主控待执行的 exact V 命令与 V ID>
deviations: <与步骤规格的偏差；无则 none>
blockers: <none 或具体问题>
pua_result: <step-verification 卡的 [PUA-ACCEPTANCE] 结果>
```

## Fix-Round Template

返修轮复用原 dispatch 的 task_id，追加：

```text
FIX-ROUND
task_id: <T-NN>
round: <N，轻量上限 3>
findings:
  - <逐条待修复项，来自 reviewer 或主控复验>
prior_attempts: <已试方法一句话；round>=2 时必填>
```

主控记录每轮结果到 dispatch record；round 超限换 fresh seat 并携带
全部 findings 与 prior_attempts。换 seat 不重置实际失败熔断（见
`subagent-orchestration.md` Fresh Session Semantics）；同签名三次实际
失败先于轮数上限触发时按熔断处理。

## Dispatch Record Sync

每次派发、返回、跳过都在同一次操作里同步
`.opencode/mvp/<goal-slug>.dispatch.json`（schema 见
`subagent-orchestration.md`）。派发与返回正文保存到 dispatch archive，
并把路径写入 `dispatch_ref`/`result_ref`；评审/PUA 裁决与未决动作写入
`acceptance`。恢复执行时先读该文件再决定是否重新派发；缺少这些引用的
记录按需重建上下文处理，不凭状态标签复用结论。

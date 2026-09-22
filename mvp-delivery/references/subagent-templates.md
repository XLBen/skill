# Subagent Dispatch Templates

> When to read: before composing any subagent dispatch or adjudicating a
> subagent's return message.
>
> Path convention: `../<skill>/...` paths in this file are relative to the
> mvp-delivery skill root (the parent of `references/`), matching how the
> skill tool resolves them.

所有派发与返回使用固定格式，方便 GLM 稳定执行与主控机械校验。字段缺失
的派发是缺陷；返回不合式的结果按 needs_context 处理，不猜测填充。

## Stage And Handoff Packets

派发前先用确定性工具渲染事实，避免每次在模型文本里重新组装：

```powershell
python .opencode/workflow/scripts/workflow_packets.py stage <stage_id> --rigor <rigor> --role <role> --out .opencode/mvp/packets/<stage>.json
python .opencode/workflow/scripts/workflow_packets.py handoff <goal.md> --dispatch <goal.dispatch.json> --evidence-dir .opencode/mvp/evidence --out .opencode/mvp/packets/<goal>-handoff.json
```

- `workflow-stage-packet/1` 给执行/评审席位：resolved stage、rigor、seat、
  唯一 semantic check owner、formal V owner、reviewer mode 与 `mode_file`、
  适用 skill、输入/证据身份。派发正文用 `packet: <path>` 引用它，席位读包
  而不再通读 routing 文档；包只描述规则，不是通过凭证。
- `workflow-handoff-packet/1` 给验收评审：机器生成的 goal/scope/dispatch/
  evidence/gaps 事实，加一个空的 `claims` 段由模型填写判断。生成器从不
  宣判通过；缺失或过期的事实进入 `gaps`，不得略过。
- 包随 routing/goal/证据 hash 失效：`workflow_packets.py validate <packet>`
  在 hash 变化时报告 stale，必须重新生成。
- `ACCEPTANCE_HANDOFF` 仍按 i-have-adhd 的字段全集交付给 reviewer；包是
  其中机器可核部分的确定性渲染，不替代交接本身。

## Dispatch Template

对 engineering-plan/2 的实现任务，主控先运行 `check.py next-step <goal>`，将返回
的 implementation-packet/1 作为 inputs 正文。write_scope = step.files，dependencies
来自 completed_dependencies 和精确合同，verification 来自本步 checks；journey 若需
共享 UI 则留给主控执行。不要再把整份设计/全部 skill/历史任务粘贴进去。worker
不重新规划，不手填 goal/hash/UI 标记，设计冲突返回 waiting_controller + replan 证据。
以下外壳继续用于权限/身份/派发记录；不要重复抄写任务包已经给出的实现细节。

```text
DISPATCH
task_id: <T-NN, 对应 dispatch record>
role: research|worker|reviewer|test-author|step-executor|product-observer
stage_id: <stage-routing.json 的 stage_id；无则 none>
goal: <一句话目标与验收条件，可观察、可判定>
inputs:
  - <文件路径或确切数据；标注哪些是必读约束>
write_scope: <允许修改的路径；reviewer/research 为 read-only>
work_root: <分配的绝对隔离工作目录（worktree）；无则 none。提供时 write_scope 相对它解释>
baseline: <当前产物基线：commit/hash/目标卡状态>
dependencies: <依赖的先前任务结论或接口决定；无则 none>
verification: <要求执行的验证命令与预期；无则 none>
required_skills:
  - <本席位必须加载的 role skill，如 task-worker / reviewer / pua；回退到内建 agent 时同样必读>
selected_domain_skills:
  - name: <经适用性选择的专业 skill；无则省略整节>
    acceptance_items: <覆盖的验收项>
    execution_seat: <本席位或 controller>
artifact_identity: <当前制品身份，供评审绑定与恢复核对>
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
- `required_skills` 由 `stage-routing.json` 与角色映射决定，不由主控临场
  削减；`selected_domain_skills` 只列通过适用性选择（见
  `subagent-orchestration.md` Skill Applicability Selection）的条目。
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

## Task Result Envelope

所有角色交回时先写公共外壳（文本角色逐行渲染；reviewer 在结构化 JSON 顶层
带同名字段），角色专用内容放在 `payload` 段：

```text
TASK_RESULT
schema: task-result/1
task_id / attempt / role / phase
status: completed | needs_input | waiting_controller | blocked | failed
summary: <实际完成内容，一到三句>
changes:
  - <path>: added|modified|deleted|renamed — <行为变化>
evidence:
  - kind: command | source | artifact
    <command+cwd+result | path+lines | path>
not_verified:
  - <未运行/未检查项与原因；无则 none>
issues:
  - <实质发现或障碍；无则 none>
controller_actions:
  - <action_id + 请求；无则 none>
next_context:
  - <后继任务需要的接口事实；无则 none>
payload:
  <角色专用块：RESULT / TEST_AUTHOR_HANDOFF / STEP_HANDBACK / reviewer JSON>
```

- `status` 是交回状态，不是主控验收：`completed` 只表示席位执行结束。
- `needs_input` 缺输入；`waiting_controller` 等待 CONTROLLER_ACTION 执行；
  `blocked` 需要外部解锁；`failed` 表示本次尝试失败、不应复用。
- `changes` 只描述实际改动，research/review 留空；reviewer 的 findings 放
  `issues`，不能用 `changes` 代替。
- `next_context` 只写后继任务真正需要的接口事实，不是过程复述。
- 旧格式（`status: done|needs_context|blocked`、无 envelope）按 legacy 读取：
  `done→completed`、`needs_context→needs_input 或 waiting_controller`、
  `blocked→blocked`；缺失字段标 unknown，不补造。新派发一律要求 envelope。

## Return Format Matrix

每个角色使用固定的一种返回格式；主控按该角色的格式与公共外壳校验，不把
RESULT 当作所有角色的隐式父接口：

| 角色 | 返回格式 | 必需字段（缺失按 needs_input 退回并指出字段） |
|---|---|---|
| research / worker | `TASK_RESULT` + `RESULT` payload | 外壳公共字段；completed 时 evidence 非空（纯调研报告 source 证据） |
| reviewer | reviewer-protocol JSON | mode、issues、checked_scope、not_checked；review 模式每个 issue 带 classification；派发带 `pua_stage_id` 时 `pua_acceptance` 必填且 `stage_id` 必须与传入一致，未传时省略（见 reviewer-protocol.md Output）；观察充分性评审返回 `product-observation-review/2`（hash 由控制器/引擎绑定） |
| test-author | `TASK_RESULT` + `TEST_AUTHOR_HANDOFF` payload | 单轮 `phase: work` 即写测试、跑 pre-change、冻结 manifest；`test_author_id` 先写 `pending-binding`，主控返回后 `bind-test-author` 绑定真实 provenance；payload 要求 slice、spec_hash、manifest、protected_acceptance、expected_scenarios、pre_change_result |
| step-executor | `TASK_RESULT` + `STEP_HANDBACK` payload | step、implementation_files、protected_unchanged、pending_v、deviations/blockers |
| product-observer | `TASK_RESULT` + `product-observation/2` payload | 外壳公共字段；payload 为**恰好一个 fenced json 块**，只含 phase（discover/compare）、surfaces、journeys、findings、unobserved、capability_gaps、continuation、stop_reason、evidence_refs、notes；`goal_id`/`candidate_id`/`observer_session_id`/`model`/`packet_hash`/`received_at`/`attempt` 由 controller 采纳时并入，observer 不写结果或工作流文件；`completed` 仅表示阶段结束，绝非 audit accepted |

合法的角色专用返回不得因不含旧 RESULT 字段而被退回。格式返工不是产品返工：
不得通过重新生成测试、重跑 pre-change 或重放实现来“修复格式”；格式错误
与缺少业务上下文是不同的 needs_input 原因，不得无限往返。`issues` 为空
不自动等于通过：主控还须核对 `not_verified`/`not_checked` 无实质缺口、
`pua_acceptance` 结果及所有既有 engine/owner gate。

## Controller-Action Request

子代理在共享桌面、engine 正式 V 或其他只有主控能执行的动作前，不等待、
不自行代跑，返回 `TASK_RESULT`（`status: waiting_controller`）并附带：

```text
CONTROLLER_ACTION
action_id: <任务内稳定唯一，如 A-T01-01>
task_id: <T-NN>
requested_action: run-command | gui-scenario | engine-verify
target: <命令、场景或 step/V ID>
authorization_scope: <需要的授权边界；无则 none>
expected_evidence: <主控执行后应产生的证据路径/输出>
artifact_identity: <当前产物身份，供恢复时核对>
resume_hint: <证据就绪后恢复哪个席位/阶段>
```

这是 `waiting_controller` 的具体类型：等待主控动作，不是外部阻塞，也不是
owner 阻塞。**派发前主控先查 dispatch record 中同 action_id 的状态**：

- 已有 `completed` 且证据仍有效：直接复用证据，不重复执行。
- `requested`/`running`：先确认实际副作用，再决定继续等待还是执行。
- `unknown`：非幂等动作（写入、迁移、外部调用）必须先查证状态，不自动重放；
  查不清时按 blocked 升级。
- `failed`：按失败恢复到原席位。

主控执行一次、保存证据并把状态写入 dispatch record 的 `actions`，然后按
`resume_hint` 传回原席位继续；恢复时重取当前 GUI/环境状态，不重放旧操作。
同一正式 V attempt 只由主控执行一次，子代理的诊断运行不得作为替代。崩溃
场景不承诺绝对 exactly-once，但未知状态不允许自动重放。

## Result Template

`TASK_RESULT` 的公共外壳已携带 task_id、status、summary、changes、evidence、
issues；worker/research 的 payload 只补充剩余字段：

```text
payload:
  RESULT
  artifacts:
    - <修改的文件或发现的位置>
  verification:
    command: <实际执行的命令>
    result: <通过/失败及关键输出位置；无则 none>
```

- completed 要求 evidence 非空；纯调研任务报告 source 证据即可，不强迫
  伪造“验证命令”。
- needs_input 必须列出缺失的具体输入。
- blocked 必须给出可核实的原因与最小解锁动作。
- reviewer 返回沿用 reviewer-protocol 的结构化 JSON（`issues` +
  `pua_acceptance`——派发带 `pua_stage_id` 时必填、未传时省略），
  JSON 顶层同时携带外壳字段（task_id、attempt、status），不使用文本 payload。
- 仅当读取 legacy 记录时才接受无外壳的旧 `RESULT`；新派发不得省略外壳。

## Step-Handback Template (step-executor)

step-executor 交回实现，不等待正式 V；正式 `verify-step` 由主控在收到
hand-back 后执行一次（见 step-executor/SKILL.md）：

```text
TASK_RESULT
schema: task-result/1
task_id / attempt / role: step-executor / phase: work
status: completed | needs_input | waiting_controller | blocked | failed
summary: <本步骤实际完成了什么>
changes: <实际改动文件>
evidence: <诊断命令与原始输出位置>
not_verified: <未运行项与原因；无则 none>
issues: <偏差/发现；无则 none>
controller_actions: <需要主控执行的动作；无则 none>
next_context: <后继步骤需要的接口事实；无则 none>
payload:
  STEP_HANDBACK
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

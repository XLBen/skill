# Subagent Orchestration Protocol

> When to read: before any dispatch decision in plan/build/fix/resume, when
> choosing an execution seat for a task, and before recording dispatch state.

本协议是所有模式共用的唯一委派规则。主控制器（本 skill）持有目标、依赖、
集成、最终验证和持久状态；Guarded/Audited 的实质工作默认交给子代理，Normal
允许主控直接实现但独立正确性判断与验证盲区仍应派发。
阶段→能力→席位的权威映射见 `stage-routing.json`；本文件规定决策程序。

## Dispatch Trigger Matrix

“实质任务”的判定条件（满足任一即实质）：改变产品行为、改变公开接口、
修复缺陷、跨文件逻辑调整、或需要独立正确性判断。仅凭“主控自己做更快”、
“改动只有几行”不构成跳过理由；行数少不等于机械小改。

判定按固定次序执行，先命中先适用：

1. 是否满足实质任务条件？
   - 否，且确属拼写/格式/明确机械小改 → 主控直接处理；多个同类小改合并
     为一个工作包（`skip_reason: mechanical-batch`）。禁止拆分派发。
   - 是 → 进入 2。
2. 当前是否 Guarded/Audited 切片？
   - 否（Normal）：主控可直接实现；涉及独立正确性判断、验证盲区或用户要求时
     派 worker/reviewer。`skip_reason` 只允许
     `capability-unavailable`（须有 preflight 证据）或 `mechanical-batch`。
   - 是 → 按 Audited Execution Seat Selection 决策表执行。
3. 能力不可用分支按 Failure Branches 降级或阻塞，并记录证据。

| 场景 | 默认执行方式 | 强制级别 |
|---|---|---|
| 单点拼写/格式/明确机械小改 | 主控直接处理；多个同类小改合并为一个工作包 | 禁止拆分派发 |
| 需要定位模块、依赖资料、根因分析 | 派 research 子代理；两个以上独立问题域并行 | 默认派发 |
| Guarded/Audited 实质实现任务 | 派 worker 子代理（轻量实现席位） | 默认派发 |
| Normal 实质实现任务 | 主控可直接实现；独立正确性判断或验证盲区时派发 | 按风险选择 |
| `/fix` 根因不明 | 先派 research 诊断，凭证据再派实现 | 默认派发 |
| 多个可独立复现的故障 | 按问题域并行派 research/worker | 默认派发 |
| Guarded/Audited 实质切片验收交接 | 派 fresh reviewer（见 SKILL.md 验收章节） | 能力可用即必须 |
| Normal 验收（独立判断/盲区/用户要求） | 派 fresh reviewer | 按风险选择 |
| 全目标 finish 检查 | 派 reviewer 复用 review 能力做 whole-goal 检查 | Guarded/Audited 能力可用即必须 |
| Audited 测试冻结/评审 | test-author / reviewer 独立席位 | 必须且阻塞 |
| Audited 步骤实现席位 | 按 Audited Execution Seat Selection 决策表 | 按决策表 |

同一版本产物已被终审覆盖且未再变化时，可复用该终审结果，不重复派发。
`skip_reason` 使用封闭白名单：`mechanical-batch`、`capability-unavailable`
（附 preflight 证据）；笼统的“无需”不合法。

### Audited Execution Seat Selection

实现席位由本表唯一决定；construction 与 step-protocol 只引用本表，不另行
定义。test-author 与 reviewer 席位独立于本表判定（见上行与 reviewer
协议），不因实现席位在会话内而消失。

| profile | interaction | 实现席位 |
|---|---|---|
| `direct` | 任意 | 主控同会话；禁止派 step-executor |
| `full` | `autonomous` | step-executor（fresh 子代理） |
| `full` | `checkpoints`/`stepwise` | step-executor（fresh 子代理） |
| `light` | `checkpoints`/`stepwise` | step-executor（fresh 子代理） |
| `light` | `autonomous` | 主控同会话 |

判定次序：先看 profile 是否 `direct`；再检查 `full` 或
`checkpoints`/`stepwise`；仅 `light + autonomous` 留在主控同会话。存在
产品 acceptance V 时，独立 test-author 席位与 review gate 仍然必须。

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
不允许回退。**任何回退席位（含内建 `general`）仍必须在派发正文里收到
`required_skills` 并实际加载对应角色 skill**；回退改变的只是宿主 agent，
不是角色边界。映射不可用时按 Failure Branches 处理，不得换更宽权限的代理
绕过。agent 定义不写死模型 ID；缺省继承运行时模型。

## Skill Applicability Selection

在以下时机执行一次有界的 skill 适用性选择：目标建立时、进入新验收边界时
（阶段按 `stage-routing.json` 变化）、验收范围变化时、最终验收前：

1. 列出本次验收项与真实边界（不超过当前阶段声明的范围）。
2. 从运行时**实际可见**的 skill 清单（skill 工具实际提供的列表，不凭
   记忆或文件存在假设）中筛选与验收项匹配的候选。
3. 读取候选 skill 的 description/正文确认适用条件；不适用的淘汰并记录
   一句理由。
4. 适用的分配执行席位（controller 或对应子代理），写进派发正文
   `selected_domain_skills`，由该席位在执行中实际加载并使用。
5. 在返回/交接正文记录 `SKILL_USE` 块（见下）。

边界（必须遵守）：

- 目标是**适用能力覆盖**，不是调用全部可用 skill；不适用的不调用。
- **UI 验收是硬规则而非候选**：受影响 outcomes 包含界面旅程（原生应用、
  系统对话框、网页交互）时，`computer-use` 必须由主控加载并执行
  ui-acceptance sidecar 中的必需场景（规则见
  `stage-routing.json` 的 ui_acceptance 块与
  `computer-use/references/ui-acceptance-protocol.md`）；缺后端是 blocked，
  不是不适用。无界面范围必须记录 `applicability: none` 及理由。
- 加载 skill 只证明取得说明，不证明验收完成；验收结果仍需行为证据。
- 父会话加载过角色 skill 不代替 fresh 子代理自行加载。
- 专业 skill 不扩大角色权限：只读 reviewer 需要运行命令/GUI 时经
  CONTROLLER_ACTION 请求主控；写入席位不因加载 skill 获得额外 write scope。
- 适用但不可用（未安装/权限拒绝）的：阻塞该验收项并披露，或按其是否
  属独立性 gate 走 Failure Branches；不得静默略过。

```text
SKILL_USE
required:
  - skill: <角色必需 skill，如 reviewer/pua/task-worker>
    purpose: <覆盖哪个验收项>
    execution_seat: <controller 或角色名>
result_evidence:
  - <skill 实际动作产生或检查的证据引用；加载本身不算证据>
skipped:
  - skill: <评估过但未用的>
    reason: <不适用 | 不可用（附证据） | 已有有效结果覆盖>
```

`skill` 工具回执只证明取得说明；`task` 回执只证明派发席位；二者都不证明
验收完成。runtime 证据链（原生 skill/task 调用、父子会话）由
`scripts/check_runtime.py` / `scripts/runtime_trace.py` 从宿主存储读取，
不由模型自述构成。

## Dispatch Preflight

首次派发前（以及怀疑环境变化时）检查并记录结果：

1. runtime 的 task/subagent 工具实际可用；
2. 目标 agent 名称在可用列表中（不凭记忆假设）；
3. 该 agent 的工具边界满足任务需要（reviewer 无写入；worker 有写入）；
4. 任务输入文件在允许读取范围内；
5. 本阶段 `stage-routing.json` 要求的 role skill 在运行时 skill 清单中
   实际可见；不可见时按 Failure Branches 处理并披露。

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
  换 seat 是调度策略，不是重试授权：实际失败计数绑定“子目标 +
  归一化失败签名”，跨 task、seat 与 resume 累计。达到三次同签名
  实际失败的 no-progress 熔断后，fresh seat 只可用于有界只读诊断；
  重新写入或重放失败方案必须先满足 owner 升级或新证据恢复条件
  （见 mvp-delivery Build Continuously 与 `../pua/references/recovery-protocol.md`）。
- reviewer 与被评实现的作者必须是不同 session；worker 不能评审自己的
  产出，主控不能在采纳前改写 reviewer 的 findings。
- 真实 session/task 标识由主控从 dispatch 工具结果记录；子代理自报的
  ID 只是声明，不作为独立性证据。

## Dispatch Record

每个 goal 维护 `.opencode/mvp/<goal-slug>.dispatch.json`（与目标卡同目录、
同 slug），仅由主控写入。它是该 goal 的**运行态**：当前切片路由、派发、
失败计数与验收裁决都存这里。goal 卡 JSON 保持纯定义——engine 在每次验证时
重写卡片并把证据绑定到定义 hash，任何运行态指针写入 goal JSON 要么被重写
丢失、要么使已验证证据失效。

```json
{
  "schema_version": 2,
  "goal_id": "G-NAME",
  "active_slice": {
    "slice_id": "<slice-id or first-slice slug>",
    "rigor": "normal|guarded|audited",
    "basis": "<选择该强度的一句依据>",
    "package": "<docs/audit-slices/<goal-slug>/<slice-id>/ 或 null>",
    "brief_path": "<本 goal 消费的 brief 版本路径或 null>"
  },
  "failure_counters": [
    {
      "target": "<子目标/step/outcome>",
      "signature": "<normalized failure signature>",
      "actual_failures": 2,
      "evidence_refs": ["<原始输出/证据路径>"]
    }
  ],
  "tasks": [
    {
      "task_id": "T-01",
      "role": "worker",
      "depends_on": [],
      "status": "done",
      "provenance": {"session_id": "<runtime-reported>", "agent": "mvp-worker"},
      "dispatch_ref": "<保存的派发正文路径，如 .opencode/mvp/dispatch-archive/<goal>-T-01.md>",
      "result_ref": "<保存的返回正文/证据路径>",
      "artifact_baseline": {"pre": "<派发前 commit/产物hash>", "post": "<返回后 commit/产物hash 或 null>"},
      "review_scope": "<task 或 goal>",
      "acceptance": {"verdict": "satisfied|repair|owner|blocked|null", "pending_actions": ["<未决 controller/owner 动作>"]},
      "rounds": 1,
      "skip_reason": null
    }
  ]
}
```

- `status`: pending | dispatched | done | failed | skipped。
- 跳过委派必须写 `skip_reason`（如 mechanical-batch、capability-unavailable）。
- **done 只表示席位执行结束，不等于验收通过**。reviewer/PUA 裁决记入
  `acceptance.verdict`；复用一个 done 评审必须同时满足：裁决为
  satisfied、`review_scope` 覆盖当前范围、其绑定的制品身份仍有效。
  `owner`/`blocked` 裁决的 `pending_actions` 在恢复时必须先执行，不得因
  产品文件未变而跳过。
- `artifact_baseline.pre` 是派发前基线，`post` 是席位返回后基线；timeout
  后 post 为 null 时必须先检查实际改动，再决定复用还是重放。
- `failure_counters` 与返修轮数是两回事：计数绑定“子目标 + 签名”并跨
  seat/task/resume 累计（见 Fresh Session Semantics）。
- 派发与返回正文持久化到 dispatch archive（或等价不可变引用），
  `dispatch_ref`/`result_ref` 指向它们；resume 不得只凭 status 标签重建
  结论。缺 `result_ref` 的 done 任务按“需重建上下文”处理：可先只读核对
  产物，不得把状态标签当作可复用成果或研究结论。
- 该记录只服务恢复与观测；完成判定仍归 goal/engine gate，不替代
  `verify-goal`/`finish-goal` 证据。
- **legacy v1 记录**（无 `schema_version` 或为 1）：`status`/`provenance`
  可作恢复线索，但缺少 `result_ref`/`acceptance`/`baseline` 时不得据此
  跳过重派或复用评审；主控首次续写时升级为 schema_version 2，只回填可
  核实的字段，不伪造历史裁决。已完成 goal 的旧记录保持原样。

resume 时先核对 dispatch record 与实际产物：done 且产物未失效、且（对
评审类任务）裁决仍满足的任务不重复派发；timeout 不等于未执行，重新派发
写入任务前必须检查实际改动。

## Failure Branches

| 失败 | 处理 |
|---|---|
| task 工具或 agent 不可见 | 记录 capability-unavailable；Normal/Guarded 主控降级执行并明确披露非独立；reviewer/test-author 类独立性 gate 按 SKILL.md 验收章节与 Audited 规则阻塞 |
| 权限拒绝 | 不换更宽权限代理绕过；按不可用处理并记录 |
| 子代理返回 needs_context | 补充输入后继续同一任务，不新建任务 |
| 子代理返回 blocked | 主控核实原因；属目标级阻塞按 SKILL.md 停止条件升级 |
| 返修连续无新证据 | 轻量流程 3 轮返修上限后换 fresh seat；实际失败熔断（同签名三次）优先于返修轮数与换 seat，先触发者先生效；严格流程遵守既有熔断 |
| 并行任务产物冲突 | 串行重放冲突任务；冲突检测在集成时执行 |

## Integration Duties

主控集成所有子代理产物：核对返回格式、复验关键断言、运行目标卡验证、
更新 goal 状态与 dispatch record。子代理的返回不直接写 ledger/goal 卡；
多个并行结果先查共享文件冲突再采纳。

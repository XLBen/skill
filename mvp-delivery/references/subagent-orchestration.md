# Subagent Orchestration Protocol

> When to read: before any dispatch decision in plan/build/fix/resume, when
> choosing an execution seat for a task, and before recording dispatch state.

本协议是所有模式共用的唯一委派规则。主控制器（本 skill）持有目标、依赖、
集成、最终验证和持久状态；Guarded 的实质工作默认交给 worker，Normal
允许主控直接实现但独立正确性判断与验证盲区仍应派发，Audited 严格步骤按
seat table 交给 controller/step-executor（从不使用 task-worker）。
阶段→能力→席位的权威映射见 `stage-routing.json`（`responsibilities` 块
定义 implementation seat、semantic check owner 与 formal verification
owner）；本文件规定决策程序。

## Dispatch Trigger Matrix

新主路径的粒度：plan 给全目标设计，worker 接 next-step 的一个实现任务包。
组件/边界检查不是每次都进入独立验收；review 在集成里程碑/明确风险点进行，
全产品观察在完整稳定候选进行。该粒度不豁免 Audited 契约中的逐步正式 V。
不要为减少执行者猜测而把所有协议全部加载给它；由主控解析席位/权限，任务包
带必要合同与当前检查。设计冲突返还规划者，worker 不自行换接口或技术路线。

“实质任务”的判定条件（满足任一即实质）：改变产品行为、改变公开接口、
修复缺陷、跨文件逻辑调整、或需要独立正确性判断。仅凭“主控自己做更快”、
“改动只有几行”不构成跳过理由；行数少不等于机械小改。

**席位选择不是跳过。** 路由决定由哪个席位执行：主控同会话、worker 或
step-executor。正常路由到主控（Normal 直接实现、Audited `direct`、
`light + autonomous`）不创建 skipped task，也不需要 `skip_reason`。
`skip_reason` 只用于“本应派发但实际未派发”的 task 行，使用封闭白名单：
`mechanical-batch`（确认无行为变化的拼写/格式/机械批量）、
`capability-unavailable`（附 preflight 证据）；笼统的“无需”不合法。

判定按固定次序执行，先命中先适用：

1. 是否满足实质任务条件？
   - 否，且确属拼写/格式/明确机械小改 → 主控直接处理；多个同类小改合并
     为一个工作包。允许合并的是执行方式，不是对实质任务的豁免。
   - 是 → 进入 2。
2. 当前是否 Guarded/Audited 切片？
   - 否（Normal）：主控是该档的默认实现席位，可直接实现；涉及独立正确性
     判断、验证盲区或用户要求时派 worker/reviewer。只有确实跳过了应派发的
     席位时才写 `skip_reason`。
   - Guarded：实质实现派 worker；能力不可用按 Failure Branches 披露降级。
   - Audited：按 Audited Execution Seat Selection 决策表执行（controller 或
     step-executor），**从不派 task-worker**；正式 `verify-step` 只由主控执行。
3. 能力不可用分支按 Failure Branches 降级或阻塞，并记录证据。

| 场景 | 默认执行方式 | 强制级别 |
|---|---|---|
| 单点拼写/格式/明确机械小改 | 主控直接处理；多个同类小改合并为一个工作包 | 禁止拆分派发 |
| 需要定位模块、依赖资料、根因分析 | 派 research 子代理；两个以上独立问题域并行 | 默认派发 |
| Guarded 实质实现任务 | 派 worker 子代理（轻量实现席位） | 默认派发 |
| Audited 实质实现任务 | 按 Audited Execution Seat Selection 决策表（controller 或 step-executor，禁止 worker） | 按决策表 |
| Normal 实质实现任务 | 主控可直接实现；独立正确性判断或验证盲区时派发 | 按风险选择 |
| `/fix` 根因不明 | 先派 research 诊断，凭证据再派实现 | 默认派发 |
| 多个可独立复现的故障 | 按问题域并行派 research/worker | 默认派发 |
| Guarded/Audited 实质切片验收交接 | 派 fresh reviewer（见 SKILL.md 验收章节） | 能力可用即必须 |
| Normal 验收（独立判断/盲区/用户要求） | 派 fresh reviewer | 按风险选择 |
| 稳定候选版本的全产品观察（schema 2/3 且 `product_observation.required`） | 派 fresh product-observer（discover→compare 两阶段） | 必须且阻塞；无席位按 Failure Branches 阻塞并披露 |
| 全目标 finish 检查 | 派 reviewer 复用 review 能力做 whole-goal 检查 | Guarded/Audited 能力可用即必须 |
| Audited 测试冻结/评审 | test-author / reviewer 独立席位 | 必须且阻塞 |
| Audited 步骤实现席位 | 按 Audited Execution Seat Selection 决策表 | 按决策表 |
| Audited 正式 V（verify-step） | 主控执行并记录 ledger；执行席位交接时不等待正式 V | 固定 |

同一版本产物已被终审覆盖且未再变化时，可复用该终审结果，不重复派发。
`skip_reason` 使用封闭白名单：`mechanical-batch`、`capability-unavailable`
（附 preflight 证据）；笼统的“无需”不合法。主控同会话执行是席位选择，
不是 skipped task。

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
正式 `verify-step` 属于主控；step-executor 只实现并在交接中声明 pending V。
`stage-routing.json` 的 `responsibilities.semantic_checks` 为每个阶段指定
唯一语义 owner；controller 只做确定性字段/hash 核对，不重复同一语义检查，
也不把 `test-freeze`/`step-verification` 卡再跑一遍。

## Role To Agent Mapping

优先使用安装器提供的项目子代理（`.opencode/agents/mvp-*.md`）：

| 角色 | 首选 agent | 只读回退 | 说明 |
|---|---|---|---|
| research | `mvp-researcher` | 内建 `explore`/`scout` | 调研、定位、根因分析 |
| worker | `mvp-worker` | 内建 `general` | Normal/Guarded 实现工作包 |
| reviewer | `mvp-reviewer` | 无（禁止回退到会话内） | 只读评审，加载 `reviewer` skill |
| test-author | `mvp-test-author` | 无（Audited 阻塞） | 冻结验收测试 |
| step-executor | `mvp-step-executor` | 无（Audited 阻塞） | 单个编译步骤 |
| product-observer | `mvp-product-observer` | 无（独立性阻塞） | 全产品黑盒观察（discover/compare），加载 `product-observer` skill |

回退规则：只读角色可回退到内建只读 agent；写入角色仅在回退 agent 具备
写入工具时可用；reviewer/test-author/step-executor 涉及独立性声明时
不允许回退。**任何回退席位（含内建 `general`）仍必须在派发正文里收到
`required_skills` 并实际加载对应角色 skill**；回退改变的只是宿主 agent，
不是角色边界。映射不可用时按 Failure Branches 处理，不得换更宽权限的代理
绕过。agent 定义不写死模型 ID；缺省继承运行时模型。

## Skill Applicability Selection

在以下时机执行一次有界的 skill 适用性选择：`/work` 目标入口
(`work-entry`)、其他目标建立时、进入新验收边界时
（阶段按 `stage-routing.json` 变化）、验收范围变化时、最终验收前：

1. 列出本次验收项与真实边界（不超过当前阶段声明的范围）。
2. 从运行时**实际可见**的 skill 清单（skill 工具实际提供的列表，不凭
   记忆或文件存在假设）中筛选与验收项匹配的候选。条件型领域能力注册在
   `stage-routing.json` 的 `domain_capabilities`：
   `security-assurance`（信任边界/认证/隐私/密钥/不可信输入）、
    `production-readiness`（生产部署/长期服务/迁移/可用性目标）、
    `incident-response`（正在发生的线上影响，经 `fix-entry`）、
    `outcome-learning`（未验证的用户/业务假设）、
    `skill-creator`（目标是创建/修改/评估 skill）、
    `receiving-code-review`（收到评审意见后核实与返修）、
    `frontend-design`（明确的视觉设计任务）、
    `vercel-react-best-practices`（相关 React/Next.js 代码与适用规则）。只有触发条件与真实边界
    匹配才加载，不默认全选。
3. 读取候选 skill 的 description/正文确认适用条件；不适用的淘汰并记录
   一句理由。
4. 适用的分配执行席位（controller 或对应子代理），写进派发正文
   `selected_domain_skills`，由该席位在执行中实际加载并使用。
5. 在返回/交接正文记录 `SKILL_USE` 块（见下）。

编码、代码设计和代码评审还按 `stage-routing.json` 加载原版 `ponytail`；判断额外加固、范围、过度设计或重复验证时将原版 `stop-that-shit` 交给实际作判断的席位。派发正文在 `required_skills` 或 `selected_domain_skills` 中列名称，不粘贴或改写提示词；子代理自行加载完整原文，席位权限和文件边界不因此扩大。

四个新增领域 skill 也只在实际边界匹配时加载原版 `SKILL.md`，不为它们新增验收席位或全局 gate。`skill-creator` 中提及的 Claude CLI/评估展示脚本须先检查本机能力，缺失时如实注明实际未运行的模型对照；`receiving-code-review` 由收到 findings 的 controller/实现席位使用，不能让产生 findings 的独立 reviewer 自行采纳结论。`frontend-design` 决定视觉实施，不取代真实 UI 旅程；React 规则按相关文件展开，不把性能优化变成无关任务。已有 reviewer、test-author、owner 与工具权限不变。

边界（必须遵守）：

- 目标是**适用能力覆盖**，不是调用全部可用 skill；不适用的不调用。
- **UI 验收是硬规则而非候选**：受影响 outcomes 包含界面旅程时，主控必须加载
  并执行 ui-acceptance sidecar 中的必需场景——Web-only 旅程加载
  `webapp-testing`（断言式浏览器自动化），原生应用/系统对话框/文件选择器加载
  `computer-use`（规则见
  `stage-routing.json` 的 ui_acceptance 块与
   `../../computer-use/references/ui-acceptance-protocol.md`）；缺后端是 blocked，
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
6. 观察/评审席位优先用项目插件工具 `visibility_dispatch` 派发：它读取
   `.opencode/mvp/visibility.json` 的项目级选择（observer 用 `selection`，
   reviewer 用 `reviewer_selection`；显式 `model` 覆盖只作用于单次派发）。
   插件在 OpenCode 启动时加载，新增/修改后必须重启 OpenCode，工具才会出现；
   工具不可见时按 Failure Branches 记录 capability-unavailable 并披露，
   不得静默继承会话模型。`opencode run --agent <subagent>` 不是生产派发路径：
   宿主拒绝把 subagent 当 primary agent 并静默回落到其他 agent（P0-1），
   只能作明确披露的诊断用途。
7. 观察席位的模型能力（感知）探针必须对应本次实际派发的
   `provider/model`：packet 的 `model` 与 preflight `covers.model` 不一致时
   packet 生成即失败，运行时以 trace session model 为准。跳过任何重复探测
   只能依据 `preflight_skip_plan`：覆盖项 `status: passed` 且其记录的**全部
   身份字段**与本次派发上下文一致；出现 "controller-verified" 字样同样不
   构成豁免，身份缺失或不符时必须重新探测。

preflight 失败按 Failure Branches 降级或阻塞，并在 dispatch record 记录
原因。不把“配置文件存在”当作“运行时已加载”。

## Concurrency Rules

- 同时最多 3 个子代理；共享工作区同时最多 1 个写入者。
- 只读 research/review 可并行；worker 运行时主控只做不重叠工作。
- reviewer 评审期间被评产物必须稳定：先完成写入、再派评审。
- 并行派发只用于经确认互不共享文件/状态的任务；不确定时串行。
- 子代理不再递归派发子代理；需要协作时返回主控协调。
- 所有 agent prompt 要求子代理返回结构化结果而不是自由叙述。

### Isolated Writer Tasks (Git worktrees)

仅在 Normal/Guarded 且可独立集成的工作包上开放多 writer。准入条件全部满足
才并行，任一不满足回退串行；不得自动提交、stash 或清理用户工作区来制造条件：

1. 仓库有可用 Git 基线，且集成工作区干净（`scripts/worktree_tasks.py admission` 可检查）；
2. 子任务写入集合不重叠，共享接口已确定；
3. 不共享外部可变数据、数据库或 GUI；
4. 依赖安装与测试资源能够隔离；
5. 宿主允许子代理访问分配的绝对工作目录。

工作方式：

- 每个写入任务用 `scripts/worktree_tasks.py create` 建立 detached worktree；
  派发时把该绝对路径作为席位唯一写入根，`write_scope` 相对该根解释。
- 子代理不要求创建 commit；返回 `TASK_RESULT` 的 `changes` 按真实路径报告。
- 主控集成顺序：`collect` → `scope` 核对实际改动是否越界 → 目标版本
  `apply --check-only` → 按依赖顺序 `apply`；冲突时停止并返回具体冲突，
  不默认重放已部分写入的任务。
- 所有任务集成后对最终稳定版本统一运行受影响测试与目标验证；集成后的
  稳定版本上重新评审。
- `cleanup` 需要 `--integrated`（确认收集的补丁已应用到集成工作区）或显式
  `--discard` 才移除；timeout/unknown 状态不删除 worktree、不重派同副作用
  任务，先确认原任务状态。
- 默认最多两个并发 writer（总席位上限不变）；主控是集成工作区唯一写入者。
- reviewer 绑定不可变快照，不与同范围的写入并发。
- Audited 严格步骤默认串行；仅当
  `scripts/worktree_tasks.py parallel-plan` 准入通过时，无步骤/单元依赖、写集
  可证不重叠、已冻结测试、无共享数据库/GUI/远程可变状态、且写集不触碰受保护
  验收路径的本地实现步骤才可以进入该分支（默认最多两个 writer）。集成仍由
  主控串行执行，正式 `verify-step` 与 review 只针对集成后的规范版本；任一
  条件不满足或无法证明即回退串行，不猜。

## Fresh Session Semantics

- 新任务一律 fresh dispatch，不继承主控或先前作者的上下文。
- 同一实现任务的返修轮可以 resume 原执行者（携带 findings）；超过
  轻量上限（3 轮）后换 fresh seat 并附上全部 findings 与已试记录。
  换 seat 是调度策略，不是重试授权：实际失败计数绑定“子目标 +
  归一化失败签名”，跨 task、seat 与 resume 累计。达到三次同签名
  实际失败的 no-progress 熔断后，fresh seat 只可用于有界只读诊断；
  重新写入或重放失败方案必须先满足 owner 升级或新证据恢复条件
   （见 mvp-delivery Build Continuously 与 `../../pua/references/recovery-protocol.md`）。
- reviewer 与被评实现的作者必须是不同 session；worker 不能评审自己的
  产出，主控不能在采纳前改写 reviewer 的 findings。
- 同一评审任务的返修复核（同一任务、同一范围，作者更新制品后）可以 resume
  原独立 reviewer 席位并携带原 findings 与新的制品 hash；resume 不重置
  独立性，但 clean final audit、converge-audit 与 whole-goal 检查仍必须
  fresh 或由未参与该实现的独立席位执行。
- 最后一个稳定版本切片：一次 fresh reviewer dispatch 可以返回两个分别绑定
  范围的 verdict（slice converge 与 whole-goal），两者互不替代；只有 slice
  verdict 时 whole-goal gate 仍然失败。
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
      "attempt": 1,
      "provenance": {"session_id": "<runtime-reported>", "agent": "mvp-worker"},
      "dispatch_ref": "<保存的派发正文路径，如 .opencode/mvp/dispatch-archive/<goal>-T-01.md>",
      "result_ref": "<保存的返回正文/证据路径>",
      "artifact_baseline": {"pre": "<派发前 commit/产物hash>", "post": "<返回后 commit/产物hash 或 null>"},
      "review_scope": "<task 或 goal>",
      "acceptance": {"verdict": "satisfied|repair|owner|blocked|null", "pending_actions": ["<未决 controller/owner 动作>"]},
      "actions": [
        {
          "action_id": "A-T01-01",
          "kind": "run-command|gui-scenario|engine-verify",
          "status": "requested|running|completed|failed|unknown",
          "evidence_ref": "<证据路径或 null>",
          "artifact_identity": "<动作时的产物身份>"
        }
      ],
      "rounds": 1,
      "skip_reason": null
    }
  ]
}
```

- `status`: pending | dispatched | done | failed | skipped（派发生命周期）。
  子代理的 `task-result/1` 交回状态（completed / needs_input /
  waiting_controller / blocked / failed）是另一层语义：`completed` 映射为
  dispatch done，`waiting_controller` 表示等待主控动作，不能当作 done 复用。
- `attempt` 从 1 开始，每次 FIX-ROUND 递增；复用旧 attempt 的结论必须
  同时满足产物未变与证据仍有效。
- `actions` 是 CONTROLLER_ACTION 的去重状态（见
  `subagent-templates.md`）：执行前先按 `action_id` 查询；`completed` 且
  证据有效时复用，`unknown` 的非幂等动作必须查证后处理，禁止自动重放；
  `completed` 必须带 `evidence_ref`；未决（requested/running）、`failed` 或
  `unknown` 的 action 在 runtime gate 中阻塞完成。
- 跳过委派必须写 `skip_reason`（如 mechanical-batch、capability-unavailable）。
  主控同会话执行是席位选择，不是 skipped task。
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

### Runtime Commands

记录的机械维护用确定性命令完成，不在模型文本里手抄；命令只记录，不批准
任何结论，也不调用宿主的 task 工具：

```powershell
# 派发前：登记意图，可同时归档派发正文
python .opencode/workflow/scripts/workflow_runtime.py dispatch-begin <dispatch.json> --task task.json [--body dispatch.md] [--expect-revision N]
# 返回后：归档原始返回并按 task-result/1 映射状态
python .opencode/workflow/scripts/workflow_runtime.py dispatch-result <dispatch.json> --result result.json [--body raw-return.json] [--expect-revision N]
# CONTROLLER_ACTION 状态去重更新；completed 必须带 evidence_ref
python .opencode/workflow/scripts/workflow_runtime.py action-result <dispatch.json> --update action.json [--expect-revision N]
# 只读：列出下一项机械义务（未决 action / 等待任务 / 熔断 / owner gate / 状态修复）
python .opencode/workflow/scripts/workflow_runtime.py next-action <dispatch.json>
```

- 写入是 temp+atomic replace；校验失败不改动原文件；`--expect-revision` 在
  并发写冲突时拒绝覆盖。
- `provenance` 必须是运行时回执里的真实 session/agent；本工具只记录，真伪
  校验仍归 `runtime_trace.py` / `check.py runtime-gate`。
- `next-action` 只列机械义务与候选，不派发、不批准、不替代 owner gate。
- 工具不可用时按旧流程手工维护并在交付报告中披露，不得伪造 revision。

resume 时先核对 dispatch record 与实际产物：done 且产物未失效、且（对
评审类任务）裁决仍满足的任务不重复派发；timeout 不等于未执行，重新派发
写入任务前必须检查实际改动。

### Minimal Recovery Read Set

`/resume` 先读以下最小状态集，再按缺口展开；不得默认读取全部 archive、全部
reviewer findings 或完整派发正文：

1. `docs/delivery-log.md` 的既有条目（上下文压缩重入点，见
   `delivery-finish.md` 的 Delivery Log And Context Compaction）；
2. 目标定义（goal 卡 JSON fence 或严格包指针）；
3. dispatch record：`active_slice`、未完成任务、未决 `actions`、
   `failure_counters`；
4. 当前产物基线与工作区状态；
5. 已采纳的接口结论（任务 `next_context` 摘要）；
6. 下一动作（首个 pending/blocked outcome 或等待中的 gate）。

只有需要核对具体结论/证据时才展开对应的 `dispatch_ref`/`result_ref` 文件；
已完成 goal 的 brief/PLAN/包全文不再默认加载。

## Failure Branches

| 失败 | 处理 |
|---|---|
| task 工具或 agent 不可见 | 记录 capability-unavailable；Normal/Guarded 主控降级执行并明确披露非独立；reviewer/test-author 类独立性 gate 按 SKILL.md 验收章节与 Audited 规则阻塞 |
| 权限拒绝 | 不换更宽权限代理绕过；按不可用处理并记录 |
| 子代理返回 needs_input | 补充输入后恢复同一任务，不新建任务 |
| 子代理返回 waiting_controller | 按 action_id 去重执行主控动作（见 `subagent-templates.md`），完成后恢复原席位 |
| 子代理返回 blocked | 主控核实原因；属目标级阻塞按 SKILL.md 停止条件升级 |
| 返修连续无新证据 | 轻量流程 3 轮返修上限后换 fresh seat；实际失败熔断（同签名三次）优先于返修轮数与换 seat，先触发者先生效；严格流程遵守既有熔断 |
| 并行任务产物冲突 | 先核对实际差异与所有权，再决定重派、合并或人工裁决；不默认重放已部分写入的任务（见并发协议） |

## Integration Duties

主控集成所有子代理产物：核对返回格式、复验关键断言、运行目标卡验证、
更新 goal 状态与 dispatch record。子代理的返回不直接写 ledger/goal 卡；
多个并行结果先查共享文件冲突再采纳。

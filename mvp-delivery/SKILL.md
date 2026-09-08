---
name: mvp-delivery
description: Use when the user types /plan, /build, /fix, or /resume, or asks to plan, implement, repair, or continue a project. Plans right-sized work, delivers the thinnest runnable slice first, verifies real behavior, and keeps adding slices until the original goal is met.
license: MIT
metadata:
  language: "zh-CN"
  commands: "/plan <goal>, /build [goal], /fix <problem>, /resume"
  produces: "working product code and verification evidence"
---

# MVP Delivery

把 MVP 当作交付顺序，不当作缩减用户目标的借口：先尽快做出一条真实可运行的
端到端路径，再按价值逐片补齐，直到原始目标达成、用户暂停或出现真正阻塞。

## Default Behavior

收到 `/build <goal>` 后，在同一会话中持续执行：

```text
理解目标 -> 选最薄可运行切片 -> 实现 -> 真实验证
        -> 对照原始目标 -> 下一切片 -> ... -> 完成
```

不要把内部评审、测试、施工和终审能力重新暴露成一串用户命令。不要在每片之间问
“是否继续”。用户请求交付目标时，默认授权的是可逆的工作区内实现与测试，而
不是只交付第一片。

只有以下情况停下来问：

- 两个互斥的产品选择会明显改变结果，且仓库和用户输入都无法裁决；
- 将执行不可逆或破坏性操作；
- 涉及凭据、隐私、安全边界、真实付费或工作区外副作用；
- Audited gate 需要 owner 实际验收、生成后的 PLAN 确认或真实独立评审；
- 原始目标在技术上不可达、每条前进路径都只能猜，或连续尝试没有产生新证据。

其余不确定性由 agent 作最小、可逆、符合现有代码模式的决定，简短记录在最终
报告中并继续。

## Command Modes

- **Plan Mode (`/plan`)**：检查仓库，把参数或明确指定的 `docs/brief.md` 转成
  `.opencode/mvp/<goal-slug>.md`。只规划，不写产品代码。Normal/Guarded 使用轻量
  目标卡；Audited 在内部加载 `contract-review` 完成契约与 PLAN。最后只提示
  `/build`。
- **Build Mode (`/build [goal]`)**：先解析并复用已有目标卡；无参数时读取
  唯一 active 目标卡或严格 PLAN。持续实现、验证并自动完成收尾，直到原始结果
  清单全部 verified。
- **Fix Mode (`/fix <problem>`)**：先复用相关目标卡并复现，定位根因，做最小修复，
  加入有价值的回归测试并验证。若严格契约与现实冲突，内部执行 CR 恢复，不要求
  用户换命令。
- **Resume Mode (`/resume`)**：从持久目标卡和适用的严格状态恢复，不从聊天猜进度。
   从第一个 pending/blocked 结果继续；无未完成目标且有 draft brief 时加载 `grill`
   从持久 frontier 继续访谈，不创建目标卡或开始施工。目标或基线不明确时先问。

## 1. Establish The Target

先读仓库、现有文档、测试和最近相关实现，再决定是否提问。不要问能够从代码、
配置、错误输出或一手文档查到的事实。

同时明确谁会在什么环境下，从哪个公开入口输入什么、在哪里取得可用结果。
区分用户目标环境与 agent 验证环境；只对影响交付的未知条件提问。沿用目标卡的
`demo`、`constraints` 和 outcomes 记录，不增加 schema 字段或单独验收文档。
库的公开调用、CLI 命令、API 消费者都是有效入口；不要擅自增加 GUI、部署或账号系统。

Before product edits, resolve `.opencode/mvp/<goal-slug>.md`: reuse the matching
active/blocked card, including for `/fix`; never create a second active fix goal.
If multiple goals or an unrelated active goal make routing ambiguous, ask rather
than overwrite or silently switch. Create a card only for a genuinely new goal.
Completed cards/packages remain history; a repair gets a new card only when no
matching unfinished goal exists. Ask which completed package is the repair base
if the request and durable pointers do not identify it uniquely; never pick by mtime.

The card has matching `status` frontmatter and one authoritative `json goal`
fence, using schema 1 from `tests/fixtures/goal-valid.md` and `check.py`:

- Required top-level fields: `schema_version: 1`, `id: G-NAME`, `status`
  (`active|blocked|complete`), `source`, `goal`, `rigor` (`normal|guarded|audited`),
  `risk`, `first_slice`, `demo`, `constraints`, `deferred`, and nonempty `outcomes`.
- `constraints` and `deferred` are string arrays. `risk` contains `factors` and
  a nonempty `rationale`. Factors: `none` alone, or `external-boundary`,
  `cross-module`, `authentication`, `privacy`, `money`, `migration`,
  `irreversible`, `security`. The first two require at least Guarded; the latter
  six require Audited. Retain the strongest risk still covered by the goal.
- Direct `source` is `{"type":"direct","raw_request":"<original request>"}`.
  Brief source is `{"type":"brief","path":"docs/brief.md","brief_hash":"<hash>",
  "coverage":[{"brief_id":"BS-01","disposition":"outcome","outcome_ids":["O-01"]}]}`.
  Cover **every** brief ID exactly once, with no unknown IDs, in every risk mode.
  Dispositions are `outcome` with valid `outcome_ids`, or `constraint`, `deferred`,
  `non-goal`, `rejected` with a nonempty `reason`. Do not silently drop scope.
- Each outcome has unique `id: O-NN`, `statement`, `status: pending`, and
  `verification`. There is **no outcome-count cap**. At least one outcome must
  set `user_entry: true` and exercise the real product entry/demo, not a fixture
  print, mock, selftest, or a label on an internal unit test.
- Every promised user-facing outcome must be covered by an actual public-interface
  journey from representative input to useful output/retrieval. A shared journey
  may cover several outcomes; one unrelated passing entry smoke is not coverage
  for disconnected features. Keep this mapping in existing outcome statements
  and verification descriptions; do not label internal checks as user entry.
- `verification` contains `command`, `expected`, `assertion_kind`
  (`content|state|schema|count|user-visible`), `empty_result_policy`, and
  `assertion`: either `{"type":"stdout-contains","literal":"<nonempty result>"}`
  or `{"type":"json-equals","expected":<finite JSON value>}`. Optional
  `timeout_seconds` is an integer 1..3600 (default 120). Commands must assert
  actual behavior; narrative expectations do not execute assertions.

For brief input, require owner-confirmed `status: final`, matching hash, and a
successful `check.py brief` **before planning/building in any risk mode**. The
current goal validator alone does not reject a draft source. Resume validates
the source again. Audited packages also preserve their exact brief snapshot.

Run from the project root (installed engine path shown):

```text
python .opencode/workflow/scripts/check.py brief docs/brief.md
python .opencode/workflow/scripts/check.py goal .opencode/mvp/<goal>.md
python .opencode/workflow/scripts/check.py verify-goal .opencode/mvp/<goal>.md O-01 --evidence .opencode/mvp/evidence/<goal>-O-01-01.json
python .opencode/workflow/scripts/check.py finish-goal .opencode/mvp/<goal>.md
```

Validate `goal` before edits/resume and after definition changes. Run
`verify-goal` for every outcome with a fresh evidence path on each attempt; it
captures output, checks exit/timeout and the stdout assertion, and writes status
and evidence hashes. Failure becomes `blocked`; keep its evidence. Never manually
set `verified`/`complete` or fabricate evidence. Only `finish-goal` completes the
card after every outcome is engine-verified, including a real user-entry outcome.
Definition changes invalidate evidence bindings: reset all outcomes to pending,
remove their evidence references/blockers, and set JSON/frontmatter status active
before validation and reruns; retain old evidence files as history. Never reopen
a completed card this way. Product changes also require relevant reruns even if
hashes match.

Audited cards may add package paths and contract/PLAN/reconcile hashes as recovery
pointers, not as substitutes for goal verification. Keep detailed ledgers inside
the package; Normal/Guarded need no contract graph or event ledger.

Verification commands execute with Python `shell=True` in the system shell
(`cmd.exe` on Windows, not the OpenCode PowerShell shell). Use that shell's
quoting or explicitly invoke the needed interpreter. Run engine commands from
the project root: goal commands derive that root from the card; `verify-step`
inherits the caller's working directory. Inspect commands before running them;
explicitly obtain authorization for destructive, paid, credential/privacy,
external-write or other risky effects. A JSON command is not authorization or a
sandbox, and approval may stop the delivery loop.

需求已明确时不提问，直接宣布首片并开始。需求不明确时只问使最终成功变得可观察
所必需的问题，一次一个；一旦可以选择并验证首片就执行，不继续做完整需求访谈。
若用户明确要求深度澄清，再加载 `grill`。

## Rigor By Slice

按当前切片风险选择最轻但足够的强度，不把整个项目粗暴分成“零流程”或“全流程”：

- Normal：可逆的工作区内改动；目标卡、相关测试、真实 demo。
- Guarded：外部边界、兼容性或较高返工风险；加有预算探针、验收测试和一次独立
  review（仅在可真实调度 fresh subagent 时）。
- Audited：资金、隐私、安全、迁移、不可逆副作用或用户明确要求；加载
  `contract-review`，在 `docs/audit-slices/<goal-slug>/<slice-id>/` 建立只覆盖当前片的
  不可变契约、PLAN、ledger 和 CR 文件。本 skill 仍是总控制器，完成 gate 后自动
  继续实现、验证和后续目标切片，不要求用户手工接力命令。

风险下降后的下一片可以回到较轻强度。提高强度是增加当前风险需要的证据，不是把
工作交还给文档流水线。

## 2. Choose A Walking Skeleton

首片必须让用户或下游系统观察到一个有意义结果。它应同时满足：

- 使用一份具体输入，穿过必要层，到达真实输出或持久状态；
- 能用一条明确命令、浏览器操作或 API 调用演示；
- 包含实现该行为所需的最少基础设施，不先建设“以后可能需要”的平台；
- 不用 mock 的成功代替目标声明的真实边界；
- 通常可在一个工作会话内完成。

如果外部 API、数据可得性、框架兼容性等假设可能让整个方向作废，先做一个
有预算的小探针，然后立即进入首片。只记录命令、观察和结论；默认不创建 Phase 0
模板、契约节点或 event ledger。

## 3. Build Continuously

实施前由控制器核实最少运行前提：工作目录、OS/shell、运行时与包管理器、依赖及
现有锁文件、配置变量名、服务、初始化数据和启动方式。复用仓库约定，不依赖未声明的
全局包、手工准备的数据或 agent 私有配置，不记录密钥值。需要安装或外部访问时遵守
授权边界。测试框架尚不可运行时，先安排最小且已授权的 setup/harness 改动；Audited
需属于当前 write set，否则走 CR。缺依赖或服务不是行为 red，不能用 mock 冒充真实边界。

1. 为当前切片创建少量可执行 todo，不为完整远期路线展开大计划。
2. 先实现最短正确路径，遵循仓库现有结构；避免无关重构和预防性抽象。
3. 测试策略与风险相称。行为明确且适合自动化时先写一个会因缺失行为而失败的
   验收测试；微小修复可复用现有测试。不要为了角色仪式强制生成独立 manifest。
4. 运行最窄相关测试，再运行真实 smoke/demo。测试必须检查内容、状态或不变量，
   不能只检查退出码、文件存在或日志非空。
5. 若必要产物缺失、为空或为零，默认失败；只有目标明确规定 semantic zero 才通过。
6. 实现失败时先读错误并修根因。同一失败方式连续三次且没有产生新证据或缩小
   根因范围时，视为 no-progress blocker：停止机械重试，汇总尝试、证据和两个
    具体方案后向用户升级。若有可说明的新证据，按新根因继续而不是重放同一动作。

新增或修复行为的测试应复现对应缺失/缺陷；既有回归可以初始即绿，记录为基线通过，
不伪造 red。确认关键场景实际执行，未被 skip、过滤、空测试集或替换脚本绕过。
成功标记只能在产品断言通过后输出；测试辅助文件、fixtures、runner 配置和命令入口
的相关改动也要检查是否弱化验收，不能仅凭测试文件未变判断完整性。

Web/服务类验证必须是有界的：启动本次待交付实例，等待 readiness，经真实客户端
执行路径并断言结果，最后清理自己创建的进程和临时资源，失败/超时也清理。
不得把常驻启动命令当作完整验证，或静默借用未知端口上的旧实例。浏览器目标应实际
操作页面；UI 的单元测试不能证明交互、导航和结果呈现已接通。缺工具时如实标为未验证。

独立测试作者或 reviewer 只在风险值得其成本且运行环境真的支持 fresh subagent 时
使用。加载另一个 skill 只是加载说明，不会创造独立身份；不得伪造 session ID、
作者隔离或审计证据。

Normal/Guarded 默认不创建 `contract.md`、`PLAN.md`、ledger、review log、
observation report 或 ceremony ratio。轻量目标卡不是过程日志。已有项目要求这些
工件时遵守项目规则；Audited 切片按上面的规则借用严格 gate，但不放弃本 skill 的
连续交付控制权。

## 4. Converge On The Original Goal

每个切片通过真实验证后，更新目标卡并回看最初的 Goal、结果清单和 Deferred，
而不是把“首片已绿”当作整个项目完成：

1. 列出仍阻止用户达成原始目标的差距。
2. 选择价值最高或风险最大的下一条薄切片。
3. 保留已通过行为，增量实现并验证下一片。
4. 重复，直到原始目标满足或命中明确停止条件。

For an Audited slice, `construction` finish closes only that slice. Immediately
update the goal card. If original outcomes remain pending, use
`contract-review`'s SI protocol internally to prepare and confirm the next
delta in a new slice package, then return to construction. Never compile a
cumulative contract over the completed PLAN: the current engine would reset
unaffected steps to pending. The new package contains only affected work and
references prior reconcile evidence through the goal card. Repeat
`finish slice -> update card -> SI/next PLAN -> build` until the card is
complete. This handoff never requires a new slash command, but each SI requires
the owner's actual acceptance of the observed base slice and delta decision,
then confirmation of the newly generated PLAN. A goal approval is not future
acceptance or preauthorization of unseen PLANs. Pause for these gates; resume
internally after approval, without asking merely to continue approved steps.

Fixing a defect in an already completed Audited package is not an SI, cannot use
the engine's same-PLAN CR recovery, and never mutates that package. Create a
sibling `docs/audit-slices/<goal-slug>/FIX-<nn>-<slug>/` replacement package.
Its `repair.md` names the base package/hash and observed mismatch. Release its
standalone affected-only contract as a normal new Audited slice, compile a new
PLAN without `--previous-contract`, and verify the correction plus regression
behavior. After clean reconcile, the goal card marks which prior
outcome/evidence it supersedes while retaining the old package as history. Use
engine CR recovery only while the mismatching package is still active.

实现中发现的新想法默认不扩张目标。原始目标内被首片延后的内容必须继续处理，
不能静默丢弃。MVP 是排序机制，不是永久的 scope cut。

## 5. Finish With Evidence

在最后一次产品代码、依赖、配置或接线改动后，对同一待交付版本运行关键用户路径
集成验证、受影响回归和适用的 lint/build。每个承诺的用户可见结果都需有实际入口
覆盖；影响范围拿不准时重跑所有目标结果，不能拼接不同版本曾经通过的证据。
使用新的 evidence 路径重新 `verify-goal`；完成卡/历史包不重开，按现有修复规则处理。
在已有交付记录中记录所测版本、未提交改动/产物的身份摘要和环境；不自动提交，不把
敏感 diff 写入日志。这是控制器检查，当前引擎不会自动绑定产品源码版本。

检查实际 diff，确认没有为跑绿而弱化测试、硬编码样例、吞错或留下未接通路径。
新产品、缺少运行说明或使用方式改变时，更新现有 README/quickstart，包含前提、
工作目录、安装/初始化/启动或调用步骤、配置变量名、具体样例和预期结果/输出位置。
在安全且已授权的隔离环境中按这些说明复跑，避免依赖当前会话的隐式准备；不为模拟
干净环境删除用户数据。无法复跑时说明具体缺口、已验证环境与目标环境的差异，不把
本地运行表述为已部署，不把缺凭据/外部服务的验证记为通过。

Run `finish-goal` only after all applicable Audited gates and actual owner
acceptance are satisfied. If the engine or independent seat is unavailable,
report a blocker rather than simulate success. Hashes detect stale bindings, not
malicious rewriting or product correctness. Session/author IDs are claims, with
no cryptographic identity verification; real session/subagent provenance must
be inspected. Selftest checks the engine, not product usability.

最终只报告：

- 已可用的结果和用户如何运行/查看；
- 交付路径和已复跑的 setup/use 步骤（可链接持久 quickstart），具体样例及预期输出；
- 关键验证命令、所测版本/环境及结果，区分自动验证、人工验收和未验证部分；
- 为推进而作出的重要可逆决定；
- 未完成项或真实阻塞（没有则明确说没有）。

若阻塞，明确哪部分仍不可用、原因和用户需要采取的最小下一步；不能将其包装为完成。

不要用流程工件数量证明成功；以用户目标的可观察结果证明成功。

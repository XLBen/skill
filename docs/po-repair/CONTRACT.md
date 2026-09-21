# 修复契约（CONTRACT）

- **状态**：S02 已冻结（2026-09-21）
- **权威实现**：`scripts/observation_contract.py`
- **人读参考**：`product-observer/references/result-contract.md`（含 `contract-enums` 围栏块，与
  `contract_enums()` 的 `json.dumps(..., indent=2, sort_keys=True)` 逐字节一致）
- **执行器**：新代码只用标准库，Python 3.10 兼容

## 1. 已冻结版本号

| 常量 | 值 |
|---|---|
| `SCHEMA_RESULT` | `product-observation/2` |
| `SCHEMA_REVIEW` | `product-observation-review/2` |
| `SCHEMA_CANDIDATE` | `product-candidate/2` |
| `SCHEMA_AUDIT` | `product-audit/2` |
| `SCHEMA_PACKET` | `workflow-observer-packet/2` |
| `SCHEMA_GATE` | `product-audit-gate/2` |

字段与枚举不得改名、不得增删语义；发现矛盾必须停下报告，不得自行改设计。

## 2. 字段要点（完整表格见 result-contract.md §3–§5）

- **`product-observation/2`**：顶层 `schema`、`phase`、`stop_reason`、`surfaces`、`journeys`、
  `findings`、`unobserved`、`capability_gaps`、`continuation`、`evidence_refs`、`notes?`；
  顶层放行并忽略 `CONTROLLER_FIELDS`，其余未知字段与嵌套未知字段一律拒绝。
- **`product-observation-review/2`**：`schema`、`findings_validity`、`coverage_adequacy`、
  `verdict`、`notes`（必填非空）、`related_finding_ids?`；S08 信封字段被忽略。
- **控制器信封**：`validate_result_envelope(accepted, expected_goal_id?, expected_candidate_id?,
  expected_packet_hash?, expected_phase?)` 校验非空、64 位小写 sha256、`attempt >= 1`、
  `phase` 与期望一致等。
- **派生状态**：`STOP_STATE`：`coverage-completed→completed`、`budget-exhausted→incomplete`、
  `blocked/no-backend/lease-lost→blocked`；由 `result_stop_state()` 计算，模型不填。
- **阻断集合**：`BLOCKING_SEVERITIES = {critical, high}`；
  `BLOCKING_FINDING_STATUSES = {suspected, confirmed, intermittent, owner-decision}`
  （`owner-decision` 计入阻断）。
- **条件规则**：compare 必填 `difference_classification`，discover 必须缺失/`null`；
  `dismissed` 需 `dismissal_reason`（且 evidence 或 owner_decision_ref）；
  `resolved` 需 `{candidate_id, finding_id}` 与非空 evidence；`budget-exhausted` 必带
  `continuation`（其他 stop_reason 必须为 `null`）；coverage-completed 施加覆盖规则且
  `evidence_refs` 非空；blocked 允许零接触但需 notes 或 capability_gaps。
- **校验器不抛异常**：枚举字段被替换为 dict/list/int/None 时返回问题列表而非崩溃
  （与 v1 集合成员测试的 P1-7 崩溃模式相反，v2 全部使用元组/安全派生）。
- **v2 接入状态（S03，2026-09-21）**：`scripts/product_observation.py` 的版本常量与枚举已改为
  引用本模块，v2 result/review 委托 `validate_result_payload` / `validate_review_payload`
  并追加控制器信封结构校验；`/1` 产物只返回单条迁移诊断；`validate_audit_sidecar` 同时接受
  `product-audit/1` 与 `/2`；`write_gate_record` 写 `product-audit-gate/2`；`_load_json`
  拒绝 NaN/Infinity 与重复键。
- **语义辅助（S04，2026-09-21）**：本模块新增三个纯函数，机械语义与文档共用同一权威：
  `is_blocking_finding(finding) -> bool`；
  `semantic_finding_problems(finding, phase=None) -> list[str]`（dismissed/intended-change
  阻断级须有非空 `owner_decision_ref`；resolved 结构确认 `resolution_ref.candidate_id`；
  known-old-issue 须有 evidence；owner-decision 分类须有 notes 或 owner decision）；
  `review_verdict_consistency_problems(review, open_blocking) -> list[str]`（insufficient
  judgment → needs-observation；judgments 充分但有开放阻断 → needs-repair；否则 → sufficient；
  verdict=blocked 不受约束）。权威顺序：批准的 goal / owner decision > 候选 README/文档 >
  历史行为。`collect_observation_problems` 已接入：逐 finding 语义检查 + 跨阶段聚合
  `open_blocking` 后校验 review verdict；resolved 的跨轮候选校验留给 gate（S05）。
- **跨轮 resolution（S05，2026-09-21）**：新增纯函数
  `resolution_binding_problems(finding, current_candidate_id, known_round_findings) -> list[str]`。
  `known_round_findings` 是 `{candidate_id: set(finding_id) | None}`：`None` 表示该历史轮的
  discover/compare 报告未能全部读取（无法核验）。`status=="resolved"` 的 finding 必须引用
  **历史轮**（不得是当前 candidate）且 `finding_id` 必须出现在该轮 finding id 集合中；
  未知轮/不可读轮 fail closed。结构缺失仍由 `validate_result_payload` 报。
- **gate 闭环（S05，2026-09-21）**：`collect_observation_problems` 全量收集（仅 sidecar 缺失/不可读、
  cdir 不可定位、current_candidate 无轮次时停止）；证据引用必须解析为候选目录内真实文件；
  review hash 按 sidecar ref 解析文件。`product-audit-gate` 必须带 `--trace`，gate record 写入
  trace 绑定与 goal definition hash；`finish-goal`/`check-current` 只读 gate 并用加载的 trace
  **重算**问题。详见 §5。

## 3. 文件位置

| 文件 | 作用 |
|---|---|
| `scripts/observation_contract.py` | 常量、枚举、`validate_result_payload`、`validate_review_payload`、`validate_result_envelope`、`result_template`、`review_template`、`contract_enums` |
| `product-observer/references/result-contract.md` | 冻结合同文档（所有权、字段表、语义、运行布局、枚举块、fixture 索引） |
| `tests/fixtures/product-observation/*.json` | discover/compare/budget/blocked/review 六个合法示例 |
| `tests/test_observation_contract.py` | 49 条结构层回归测试 |

## 4. 遗留项（S02 范围外，明确不实现）

1. `product-candidate/2`、`product-audit/2`、`workflow-observer-packet/2`、`product-audit-gate/2`
   的字段表与校验器（S06 / S08 / S09）；S05 已冻结 gate record v2 字段（见 §5）。
2. result/review 信封采纳、run-id/attempt 归档、`result.json` create-only 落盘（S08）。
3. 覆盖语义与 review 语义决策表、纠偏回合（S04 / S05）。
4. gate 对阻断集合与 capability_gaps 的机械判定（S05 完成阻断/证据/跨轮/review 一致性；gap 状态机 S09）。
5. 既有 `scripts/product_observation.py`（v1）保持原样；S02 未修改任何既有脚本/测试。

## 5. gate record v2 与 finish 闭环（S05，2026-09-21）

`write_gate_record(goal, goal_path, problems, *, trace_binding=None, goal_definition_hash=None)`
写到 `<goal>.product-audit.json` 的 `current_candidate` 对应的
`observation/<goal_id>/<candidate_id>/gate.json`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema` | string | 固定 `product-audit-gate/2` |
| `goal_id` / `candidate_id` | string | goal 卡 id 与 sidecar `current_candidate` |
| `verdict` | `passed` / `failed` | `problems` 为空即 `passed` |
| `failures` | string[] | 机械问题逐条（保留既有消息前缀） |
| `goal_definition_hash` | string（可省略） | CLI 写入 `check.goal_definition_hash(goal)`；finish 据此判 stale |
| `trace` | `{path, sha256, provenance}` 或 `null` | 原生 trace 绑定；无绑定为 `null` |

闭环规则：

1. `check.py product-audit-gate <goal> --trace <native trace>`（observation required）：
   无 `--trace` 直接失败；用 `runtime_trace.trace_provenance` 计算 provenance，非 `native` 时把
   `trace provenance is not native` 加入 failures（gate fail）；写入 trace 三字段与 goal hash。
   schema-1 / required=false 仍短路输出 “not required”。
2. `finish-goal` / `check-current`：`enforce_product_observation` **只读** gate（不写、不放宽），依次校验
   schema、goal_id/candidate_id、`verdict=passed`、`goal_definition_hash == goal_definition_hash(goal)`、
   trace 路径存在 + sha256 匹配 + `provenance=native`；随后载入 trace，**重新**调用
   `collect_observation_problems(goal, goal_path, trace=loaded_trace)` 做最终核验。任一步失败都以
   “product observation …” 文案报错，并提示先运行 `product-audit-gate <goal> --trace <trace>`。
3. 机械证据口径（S05）：`findings[].evidence_refs`、`journeys[].evidence_refs`、`report.evidence_refs`
   必须为非空相对路径、不含 `..`，先 `cdir/ref` 后 `project_root/ref` 解析，最终存在且 resolve 后
   仍在 cdir 内（否则 `not found` / `escapes the candidate evidence scope`）；
   `review.discover_hash`/`compare_hash` 必须等于 sidecar `discover_ref`/`compare_ref` 解析文件的 sha256
   （ref 缺失回退 `cdir/<phase>.result.json`）。

## 6. candidate v2：不可变制品与运行状态（S06，2026-09-21）

`product-candidate/2` 新增可选字段（严格、无未知键）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `runtime_state` | array | 允许产品运行时修改的**精确文件路径**；不参与文件哈希绑定 |
| `delivered_roots` | array | 交付根目录（项目相对），用于扫描未声明交付文件 |

`runtime_state[]` 项：`{path, purpose, initial, reset}`：

- `path`：项目相对精确文件；无 glob、无 `..`、非绝对；不得与 `files[].path` 重叠；
  不得位于 `.opencode/mvp`；拒绝源码/可执行扩展名（.py/.js/.ts/.sh/.ps1/.exe 等），
  允许数据/配置类（.txt/.log/.json/.toml/.db/.csv/.md 等）。
- `initial`：`{"kind":"absent"}` | `{"kind":"sha256","sha256":"<64hex>"}` |
  `{"kind":"ref","ref":"<项目相对路径>"}`。
- `reset`：`restore-initial` | `delete` | `product-managed`。
- 声明 `delivered_roots` 时，`path` 必须位于某个 root 之内。

实现：`scripts/observation_candidate.py`
（`validate_runtime_state` / `runtime_state_paths` / `runtime_state_scope_problems` /
`undeclared_delivered_files`）。`product_observation.collect_observation_problems` 在
manifest 载入后追加：runtime_state 路径范围（含符号链接/junction resolve 越界）与
`undeclared delivered file: <path>`（仅在 delivered_roots 存在时扫描）。

语义：runtime_state 文件被产品正常修改 **不** 使候选失效；`files[]` 的哈希绑定语义不变；
未声明的新交付文件仍失败（fail closed）。S07 负责 workspace binding 复用同一排除表。

回归：`tests/test_observation_candidate.py`（40 条；Windows 无 symlink 权限时 2 条明确 skip）。

## 7. runtime-state 策略与 workspace binding 联动（S07，2026-09-21）

策略文件固定位于 goal 卡旁：`.opencode/mvp/<slug>.runtime-state.json`（`<slug>` = goal 文件名
去扩展名），结构严格、未知字段拒绝：

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema` | string | 固定 `runtime-state-policy/1` |
| `goal_id` | string | 非空；必须等于 goal 卡 id，否则 fail closed |
| `paths` | string[] | **精确项目相对文件路径**；非空字符串、相对、无 `..`、无 glob（`* ? [ ]`）、不以 `/` 结尾、无重复（规范化后）、不在 `.opencode/mvp` 下；拒绝源码/可执行扩展名（与 S06 同一 `SOURCE_EXEC_EXTENSIONS` 表） |
| `note` | string? | 可选说明；存在时必须是字符串 |

实现：`scripts/runtime_state_policy.py`（`POLICY_SCHEMA`、`policy_path`、`validate_policy`、
`load_policy`、`snapshot_excludes`、`candidate_policy_alignment_problems`）。

绑定规则（fail closed）：

1. 文件不存在 → `(None, [])`（legacy：不做任何排除，行为与 S07 前完全一致）。
2. 文件存在但不可读/非法 JSON/结构非法 → `(None, problems)`，`verify-goal`、`finish-goal`、
   `check-current`、`product-audit-gate` 一律失败。
3. 合法 → 绑定 `{"path": 项目相对 posix 路径, "sha256": 文件 sha256, "paths": 排序规范化列表}`
   在 `verify-goal` 时写入证据 payload 的 `runtime_state_policy`；`paths` 解析为
   `(project_root/p).resolve()` 并加入 `workspace_snapshot` 排除表（`run_command_evidence`
   的 before/after 与 `reuse_goal_evidence` 的快照重算）。
4. 证据事后变化检测：`enforce_workspace_binding` 用 canonical 比较 payload 绑定与当前绑定，
   不等即 "runtime-state policy changed after verification; re-verify"（新增/删除/修改路径、
   改 `goal_id`、改文件内容/note 都会 stale；**事后加入排除项不能解除旧证据的 stale**）。
5. reuse：`runtime_state_policy` 进入 `evidence_registry.IDENTITY_FIELDS`，策略一致才可复用；
   策略被修改或删除（expectation 显式带 `None`）都拒绝复用。
6. 候选对齐：`check.py observation_state_policy_problems(goal_path, goal)` 读取 sidecar
   `current_candidate` 的 manifest `runtime_state`，candidate 声明了状态但无策略 →
   "no runtime-state policy exists"，candidate 路径未被策略覆盖 → 逐条
   "runtime state path not covered by the runtime-state policy"；策略可覆盖更多路径。
   该结果并入 `product-audit-gate` 的 failures 与 `enforce_product_observation` 的重算，
   保证 gate record 与 finish 侧一致；sidecar/manifest 缺失由 gate 自身报，避免重复诊断。

回归：`tests/test_observation_state_binding.py`（26 条；Windows 无 symlink 权限时 1 条明确 skip）。

## 8. 采纳归档、sidecar /2 更新与锁（S08b，2026-09-21）

实现：`scripts/observation_results.py`（S08a-1/S08a-2 的解析与 `adopt_result` + S08b
的锁/sidecar/`adopt_review`）。回归：`tests/test_observation_results.py`（94 条）。

### 8.1 run / attempt 布局

| 路径 | 内容 |
|---|---|
| `<cdir>/<phase>/<run-id>/result.json` | 采纳的 result（`phase ∈ discover/compare`） |
| `<cdir>/review/<run-id>/result.json` | 采纳的 review |
| `<cdir>/<phase或review>/<run-id>/attempts/attempt-00N.attempt.json` | 原始响应文本 + parsed + received_at |
| 同上 `attempt-00N.errors.json` | `{attempt_id, errors, parsed_ok}` |

`run_id` 缺省 `allocate_run_id(cdir, phase)`（`run-001` 起）；`attempt_id` 缺省
`next_attempt_id(run_dir)`（`attempt-001` 起）。被拒绝的输入只写 attempt（errors 非空），
绝不产出 `result.json`。

### 8.2 adoption 流程（`adopt_result` / `adopt_review`）

1. 定位/分配 run 与 attempt，清理运行目录中遗留的 `result.json*.tmp`。
2. 结构校验：`adopt_result` = payload dict + `phase` 匹配 + `validate_result_payload`；
   `adopt_review` = `validate_review_payload`（`product-observation-review/2`）。
3. 信封校验：result 用 `validate_envelope`（goal/candidate/observer_session_id/model/
   packet_hash/attempt）；review 用 `validate_review_envelope`（reviewer_session_id/model 非空、
   `attempt ≥ 1`；`goal_id`/`candidate_id` 存在时保留并要求非空；`received_at` 缺省时取信封值，
   再缺省生成 UTC 秒级时间戳）。
4. payload 与信封同时出现的控制器字段必须 `canonical_bytes` 等价（否则冲突拒绝）。
5. `adopt_review` 对传入的 discover/compare 归档路径**实算 sha256** 写入 accepted 的
   `discover_hash`/`compare_hash`；payload 或 envelope 自带的同名值只要与实算不同即拒绝
   （`... conflicts with the archived result it names`）。
6. provenance：result 需要 `product-observer`、review 需要 `reviewer` 的 completed skill load。
7. 成功：先写 attempt（errors=[]），再 create-only 写 `result.json`。

### 8.3 create-only / 幂等 / 冲突语义

- 目标 `result.json` 不存在 → 同目录 temp + `os.replace` 原子落盘。
- 已存在且与 accepted `canonical_bytes` 等价 → **幂等成功**，返回原路径、problems 为空、
  文件逐字节不变（仍记录新 attempt）。
- 已存在且内容不同 → 冲突拒绝（`result.json conflict: ...`），文件逐字节不变。
- 采纳写入失败/拒绝不产生半成品；遗留 `.tmp` 在下次采纳时清理、不提升。

### 8.4 product-audit sidecar /2 更新规则（`update_sidecar`）

- 读-改-写在 `<sidecar>.lock` 下执行；目标文件缺失则新建。
- 结构：`{schema:"product-audit/2", goal_id, current_candidate, rounds:[...]}`；
  round = `{candidate_id, discover_ref, compare_ref, review_ref}`（空 ref 为 `""`）。
- `goal_id`、`current_candidate` 更新为参数值；既有 sidecar 的其它字段原样保留。
- 当前 candidate 无轮次 → 追加空 refs 轮再填当前 phase 的 ref；已有 → **只更新当前 phase 的 ref**；
  其它 phase ref 与全部历史轮的顺序/内容不得改动。
- `result_rel_path` 必须是项目相对 posix 路径：非空、非绝对、无 `..`、不含反斜杠；
  非法输入在取锁前退回 `(None, problems)`。
- 既有文件不可读/非法 JSON/非对象/`rounds` 非数组 → fail closed，原文件逐字节不变；
  写入失败（`os.replace` 异常）同样不触碰原文件、无 tmp 残留。

### 8.5 锁参数（`file_lock`）

`file_lock(lock_path, timeout=10.0, stale_after=120.0)`（contextmanager）：

- `os.open(lock_path, O_CREAT | O_EXCL | O_WRONLY)` 原子获取；失败后固定 0.05s 退避，
  到 `timeout` 抛 `TimeoutError`（消息含锁路径与最后一次 OS 错误）。
- 陈旧回收：仅当「stat 超龄 + 立即二次 stat 身份一致（mtime_ns/size/st_ino）」才删除；
  路径消失（含 Windows 删除挂起期的 `PermissionError`）立即重试，不误删他人新锁。
- `finally` 删除锁文件；同进程多线程与跨进程均由 O_EXCL 互斥。


# 产品观察结果合同 v2（result-contract）

> 状态：**S02 冻结**（2026-09-21）。单一权威实现为 `scripts/observation_contract.py`；
> 本文档描述该合同，`.opencode` 侧不得改写语义。`contract-enums` 围栏块由
> `contract_enums()` 为枚举权威；手工修改下方示例前先与其输出核对。
> 本步骤只冻结**结构与枚举**；语义判定（覆盖是否诚实、证据是否支撑 finding、
> review 是否成立）留给后续步骤与独立 reviewer。

## 1. 所有权

| 内容 | 写入者 | 说明 |
|---|---|---|
| `schema`、`phase`、`stop_reason`、`surfaces`、`journeys`、`findings`、`unobserved`、`capability_gaps`、`continuation`、`evidence_refs`、`notes` | 模型（observer） | `product-observation/2` 的模型 payload；校验器只做结构校验 |
| `findings_validity`、`coverage_adequacy`、`verdict`、`notes`、`related_finding_ids` | 模型（reviewer） | `product-observation-review/2` 的模型 payload |
| `goal_id`、`candidate_id`、`observer_session_id`、`model`、`packet_hash`、`received_at`、`attempt` | 控制器 | 采纳时写入的 result 信封；payload 校验器**忽略**这些键（不要求、不报未知字段） |
| `reviewer_session_id`、`model`、`discover_hash`、`compare_hash`、`reviewed_at`、`received_at`、`attempt`（review 信封） | 控制器（S08） | 本步骤不实现；`validate_review_payload` 忽略这些键 |
| `stop_reason` 的派生状态 `stop_state` | 代码派生 | 由 `result_stop_state()` 计算，模型不填写 |
| 运行布局、run-id、attempt 归档、gate | 控制器 | 见 §7；S02 只写文档，不实现代码 |

## 2. Schema 版本常量

| 常量 | 值 |
|---|---|
| `SCHEMA_RESULT` | `product-observation/2` |
| `SCHEMA_REVIEW` | `product-observation-review/2` |
| `SCHEMA_CANDIDATE` | `product-candidate/2` |
| `SCHEMA_AUDIT` | `product-audit/2` |
| `SCHEMA_PACKET` | `workflow-observer-packet/2` |
| `SCHEMA_GATE` | `product-audit-gate/2` |

`product-candidate/2`、`product-audit/2`、`workflow-observer-packet/2`、
`product-audit-gate/2` 的字段表不在 S02 冻结范围内（见 §9 遗留项），本步骤只冻结版本号。

## 3. `product-observation/2` 结果 payload

校验入口：`validate_result_payload(payload, phase=None)`。`phase` 可显式钉住期望阶段；
省略时以 payload 声明的 `phase` 决定阶段条件规则。**顶层与所有嵌套对象都不允许未知字段**，
但顶层额外放行 `CONTROLLER_FIELDS`（忽略，不校验）。校验器不抛异常，始终返回问题字符串列表。

### 3.1 顶层字段

| 字段 | 类型 | 必需 | 约束 |
|---|---|---|---|
| `schema` | string | 是 | 必须等于 `product-observation/2` |
| `phase` | enum | 是 | `discover` \| `compare`；与入参 `phase` 一致（若提供） |
| `stop_reason` | enum | 是 | `coverage-completed` \| `budget-exhausted` \| `blocked` \| `no-backend` \| `lease-lost` |
| `surfaces` | object[] | 是 | 数组；`stop_state != blocked` 时非空；见 3.2 |
| `journeys` | object[] | 是 | 数组；见 3.3 |
| `findings` | object[] | 是 | 数组；见 3.4 |
| `unobserved` | object[] | 是 | 数组；见 3.5 |
| `capability_gaps` | object[] | 是 | 数组；见 3.6 |
| `continuation` | object \| null | 是 | `budget-exhausted` 时必须存在；其他 `stop_reason` 时必须为 `null`；见 3.7 |
| `evidence_refs` | string[] | 是 | `stop_state == completed` 时必须非空；见 3.8 |
| `notes` | string | 否 | 存在时必须非空字符串 |

`CONTROLLER_FIELDS` = `goal_id`、`candidate_id`、`observer_session_id`、`model`、
`packet_hash`、`received_at`、`attempt`；payload 校验不做任何检查。

### 3.2 `surfaces[]`

| 字段 | 类型 | 必需 | 约束 |
|---|---|---|---|
| `id` | string | 是 | 非空；同数组内唯一 |
| `name` | string | 是 | 非空 |
| `importance` | enum | 是 | `material` \| `peripheral` |
| `modes` | string[] | 否 | 存在时为非空字符串数组（允许空数组） |

### 3.3 `journeys[]`

| 字段 | 类型 | 必需 | 约束 |
|---|---|---|---|
| `id` | string | 是 | 非空；同数组内唯一 |
| `surface_ids` | string[] | 是 | 非空；每个引用已知 `surfaces[].id` |
| `evidence_refs` | string[] | 是 | 非空字符串数组 |
| `outcome` | enum | 是 | `covered` \| `partial` \| `failed` |
| `notes` | string | 否 | 存在时必须非空字符串 |

### 3.4 `findings[]`

| 字段 | 类型 | 必需 | 约束 |
|---|---|---|---|
| `id` | string | 是 | 非空；同数组内唯一 |
| `surface_ids` | string[] | 是 | 非空；每个引用已知 `surfaces[].id` |
| `severity` | enum | 是 | `critical` \| `high` \| `medium` \| `low` |
| `category` | enum | 是 | `visual` \| `functional` \| `ux` \| `content` \| `performance` \| `console` \| `accessibility` \| `continuity` |
| `confidence` | enum | 是 | `observed` \| `likely` \| `uncertain` |
| `observed` | string | 是 | 非空 |
| `expected_basis` | string | 是 | 非空；指明依据（`expected_basis`，不是模型主观预期） |
| `reproduction` | string | 是 | 非空 |
| `evidence_refs` | string[] | 是 | 非空字符串数组 |
| `status` | enum | 是 | `suspected` \| `confirmed` \| `intermittent` \| `resolved` \| `dismissed` \| `owner-decision` |
| `difference_classification` | enum | 条件 | `phase == compare` 必填；`phase == discover` 必须缺失或为 `null`。`intended-change` \| `confirmed-defect` \| `known-old-issue` \| `under-investigation` \| `owner-decision` |
| `dismissal_reason` | string | 条件 | `status == dismissed` 时必须非空 |
| `owner_decision_ref` | string | 否 | 存在时必须非空字符串；`dismissed` 时可替代证据作为依据 |
| `resolution_ref` | object | 条件 | `status == resolved` 时必填；严格 `{candidate_id, finding_id}`，两者均非空字符串，且 `evidence_refs` 非空 |
| `notes` | string | 否 | 存在时必须非空字符串 |

阻断集合（供 gate 使用，S02 不实现 gate）：
`BLOCKING_SEVERITIES = {critical, high}`，`BLOCKING_FINDING_STATUSES = {suspected, confirmed, intermittent, owner-decision}`。
注意 `owner-decision` 计入阻断。

### 3.5 `unobserved[]`

| 字段 | 类型 | 必需 | 约束 |
|---|---|---|---|
| `surface_id` | string | 是 | 非空；引用已知 surface |
| `reason` | string | 是 | 非空 |

### 3.6 `capability_gaps[]`

| 字段 | 类型 | 必需 | 约束 |
|---|---|---|---|
| `channel` | string | 是 | 非空 |
| `reason` | string | 是 | 非空 |
| `evidence_refs` | string[] | 否 | 存在时为非空字符串数组（允许空数组） |

### 3.7 `continuation`

`null`，或严格对象：

| 字段 | 类型 | 必需 | 约束 |
|---|---|---|---|
| `visited_surface_ids` | string[] | 是 | 非空字符串数组（允许空数组） |
| `pending_surface_ids` | string[] | 是 | 非空字符串数组（允许空数组） |
| `checkpoint` | string | 是 | 非空 |
| `state_ref` | string | 否 | 存在时非空 |
| `previous_result_sha256` | string | 否 | 存在时非空 |

### 3.8 覆盖规则（仅 `stop_reason == coverage-completed`）

```
covered = { outcome ∈ {covered, partial} 的 journey 引用的 surface }
        ∪ { 被任意 finding 引用的 surface }
```

- 每个 `material` surface 必须落在 `covered ∪ unobserved` 中；
- `material` surface 出现在 `unobserved` 中即为错误（覆盖不完整，应改用 `budget-exhausted`）。

### 3.9 停止状态规则

- `stop_state` 由 `stop_reason` 派生：`coverage-completed → completed`；
  `budget-exhausted → incomplete`；`blocked` / `no-backend` / `lease-lost → blocked`。
- `stop_state == blocked`：`surfaces` / `journeys` 允许为空数组（零接触），
  但必须有不空 `notes` 或至少一条有效 `capability_gaps` 说明原因。
- `stop_state == completed`：`evidence_refs` 必须非空。

## 4. `product-observation-review/2` payload

校验入口：`validate_review_payload(review)`。未知顶层字段被拒绝；S08 信封字段
（`reviewer_session_id`、`model`、`discover_hash`、`compare_hash`、`reviewed_at`、
`received_at`、`attempt`）被忽略。

| 字段 | 类型 | 必需 | 约束 |
|---|---|---|---|
| `schema` | string | 是 | 必须等于 `product-observation-review/2` |
| `findings_validity` | enum | 是 | `sufficient` \| `insufficient` |
| `coverage_adequacy` | enum | 是 | `sufficient` \| `insufficient` |
| `verdict` | enum | 是 | `sufficient` \| `needs-observation` \| `needs-repair` \| `blocked` |
| `notes` | string | 是 | 非空；给出判断依据 |
| `related_finding_ids` | string[] | 否 | 存在时为非空字符串数组（允许空数组） |

S02 只做结构一致性：`verdict == sufficient` 要求两个 judgment 均为 `sufficient`。
其他组合的语义决策表留给 S04 / S05。

## 5. 控制器信封校验

校验入口：`validate_result_envelope(accepted, expected_goal_id=None,
expected_candidate_id=None, expected_packet_hash=None, expected_phase=None)`。

`accepted` 是 payload + 信封的合并对象，要求：

| 字段 | 约束 |
|---|---|
| `goal_id` | 非空字符串；与期望值一致（提供期望时） |
| `candidate_id` | 非空字符串；与期望值一致（提供期望时） |
| `observer_session_id` | 非空字符串 |
| `model` | 非空字符串 |
| `packet_hash` | 64 位小写十六进制 sha256；与期望值一致（提供期望时） |
| `attempt` | 整数且 ≥ 1（bool 不算） |
| `received_at` | 非空字符串 |
| `phase` | `discover` \| `compare`；与期望阶段一致 |

## 6. 语义说明

1. **`stop_reason` 与派生状态**：模型只写 `stop_reason`；`completed` / `incomplete` /
   `blocked` 全部由代码派生。`coverage-completed` 表示重要表面覆盖完成且证据可审，
   **不表示**整体验收通过。
2. **`coverage-completed` 允许同时存在阻断 finding**：结构校验从不因
   critical/high 的 suspected/confirmed/intermittent/owner-decision 而拒绝结果；
   是否放行由 gate（后续步骤）按 `BLOCKING_SEVERITIES × BLOCKING_FINDING_STATUSES` 判定。
   观察者禁止为了让结果好看而删 finding。
3. **`blocked` 允许零接触**：后端不可用、权限被拒、目标不可读时，`surfaces` /
   `journeys` 可以为空数组，但必须用 `notes` 或 `capability_gaps` 说明；绝不伪装成
   `not-applicable` 或用降级手段冒充通过。
4. **`difference_classification` 与 `status` 的区别**：
   - `status` 描述 finding 当前的处置生命周期（`suspected → confirmed →
     resolved/dismissed/owner-decision` 等）；
   - `difference_classification` 只出现在 compare，描述"与目标 / 历史基线相比，这个差异是
     什么性质"（预期改动、确认缺陷、已知旧问题、调查中、owner 决策）。
   两者独立：一个 `resolved` 的 finding 仍可以是 `confirmed-defect`（已修复的缺陷）；
   一个 `dismissed` 的 finding 也可以是 `intended-change`。
5. **dismissal / resolution 依据**：`dismissed` 必须给出非空 `dismissal_reason`，
   且 `evidence_refs` 非空或存在 `owner_decision_ref`；`resolved` 必须给出
   `{candidate_id, finding_id}` 且 `evidence_refs` 非空。没有依据的关闭视为无效。
6. **权威顺序**：批准目标 / owner decision > 候选 README > 历史行为。
   README 自述不能洗白与批准目标冲突的行为；历史行为只是诊断证据，不是权威。

## 7. 不可变运行布局（写入文档，不在 S02 实现代码）

```text
.opencode/mvp/observation/<goal-id>/<candidate-id>/
  candidate.json
  preflight.json
  discover/<run-id>/
    packet.json
    attempts/<attempt-id>.attempt.json
    attempts/<attempt-id>.errors.json
    result.json
  compare/<run-id>/
    packet.json
    attempts/<attempt-id>.attempt.json
    attempts/<attempt-id>.errors.json
    result.json
  review/<run-id>/
    packet.json?            # 若该阶段有 packet
    attempts/<attempt-id>.attempt.json
    attempts/<attempt-id>.errors.json
    result.json
  evidence/
  gate/gate.json
```

- `result.json` 为 **create-only**：一旦写入不得覆盖。
- `attempts/` 保留每次原始返回与错误；`<attempt-id>` 与 `attempt` 信封字段对应。
- `<run-id>` 形如 `run-001`，在各自 phase 内单调递增。
- 旧扁平布局（candidate 根目录 `discover.result.json` 等）视为 **legacy**：
  只能用于诊断，不能通过完成 gate。

## 8. 枚举总表（contract-enums）

以下块按 `contract_enums()` 的 `json.dumps(..., indent=2, sort_keys=True)` 输出记录：

```json contract-enums
{
  "blocking_finding_statuses": [
    "confirmed",
    "intermittent",
    "owner-decision",
    "suspected"
  ],
  "blocking_severities": [
    "critical",
    "high"
  ],
  "confidences": [
    "observed",
    "likely",
    "uncertain"
  ],
  "controller_fields": [
    "goal_id",
    "candidate_id",
    "observer_session_id",
    "model",
    "packet_hash",
    "received_at",
    "attempt"
  ],
  "coverage_outcomes": [
    "covered",
    "partial",
    "failed"
  ],
  "difference_classifications": [
    "intended-change",
    "confirmed-defect",
    "known-old-issue",
    "under-investigation",
    "owner-decision"
  ],
  "finding_categories": [
    "visual",
    "functional",
    "ux",
    "content",
    "performance",
    "console",
    "accessibility",
    "continuity"
  ],
  "finding_statuses": [
    "suspected",
    "confirmed",
    "intermittent",
    "resolved",
    "dismissed",
    "owner-decision"
  ],
  "importance": [
    "material",
    "peripheral"
  ],
  "phases": [
    "discover",
    "compare"
  ],
  "review_judgments": [
    "sufficient",
    "insufficient"
  ],
  "review_verdicts": [
    "sufficient",
    "needs-observation",
    "needs-repair",
    "blocked"
  ],
  "schemas": {
    "audit": "product-audit/2",
    "candidate": "product-candidate/2",
    "gate": "product-audit-gate/2",
    "packet": "workflow-observer-packet/2",
    "result": "product-observation/2",
    "review": "product-observation-review/2"
  },
  "severities": [
    "critical",
    "high",
    "medium",
    "low"
  ],
  "stop_reason_to_state": {
    "blocked": "blocked",
    "budget-exhausted": "incomplete",
    "coverage-completed": "completed",
    "lease-lost": "blocked",
    "no-backend": "blocked"
  },
  "stop_reasons": [
    "coverage-completed",
    "budget-exhausted",
    "blocked",
    "no-backend",
    "lease-lost"
  ]
}
```

## 9. 示例文件与遗留项

示例 fixtures（`tests/fixtures/product-observation/`）：

| 文件 | 覆盖点 |
|---|---|
| `discover-valid.json` | discover + `coverage-completed`；含控制器字段（证明被忽略） |
| `compare-valid.json` | compare + difference_classification + owner-decision finding |
| `budget-valid.json` | `budget-exhausted` + continuation + material unobserved |
| `blocked-valid.json` | `blocked` 零接触 + capability_gap 说明 |
| `review-valid.json` | review sufficient |
| `review-needs-repair.json` | judgment insufficient + verdict needs-repair |

遗留项（不属于 S02）：

1. `product-candidate/2`、`product-audit/2`、`workflow-observer-packet/2`、
   `product-audit-gate/2` 的字段表与校验器；（后续步骤）
2. result / review 的信封采纳、`run-id` / attempt 归档、create-only 落盘；（S08）
3. 覆盖语义、review 语义决策表与纠偏回合；（S04 / S05）
4. gate 对 `BLOCKING_SEVERITIES × BLOCKING_FINDING_STATUSES` 与 `capability_gaps`
   的机械判定；（S05 / S09）
5. 旧 `scripts/product_observation.py`（v1）保持原样，S02 不修改、不改行为。

# 产品观察工作流修复 — 进度（PROGRESS）

## S00 — 基线建立与失败语料索引

- **步骤**：S00（只建基线与语料索引，不改产品实现）
- **状态**：PASS
- **前置步骤**：无
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`D:\python\python.exe`；`py -3` 3.12.10 可用但未使用）

### 修改/创建的文件（全部在 `docs/po-repair/**`，未触碰其它目录）

- `docs/po-repair/BASELINE.md`
- `docs/po-repair/COVERAGE-MAP.md`
- `docs/po-repair/PROGRESS.md`（本文件）
- `docs/po-repair/CONTRACT.md`（占位）
- `docs/po-repair/tools/collect_corpus.py`
- `docs/po-repair/baseline/git-status.txt`
- `docs/po-repair/baseline/git-diff-stat.txt`
- `docs/po-repair/baseline/test_product_observation.txt`
- `docs/po-repair/baseline/test_observer_packets.txt`
- `docs/po-repair/baseline/test_all.txt`
- `docs/po-repair/baseline/check_selftest.txt`
- `docs/po-repair/baseline/corpus-validity.txt`
- `docs/po-repair/baseline/corpus-collect.txt`
- `docs/po-repair/corpus/INDEX.json`
- `docs/po-repair/corpus/<case>/<candidate>/{discover,compare,review}.result.json`（21 份原样复制）

未修改 `scripts/`、`tests/`、各 skill 目录、任何 `SKILL.md`、opencode 配置；
未修改沙箱 `po-validation-sandbox` 下任何文件；未创建 commit。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_product_observation.py" -v` | 0 | Ran 20 tests — OK（0 fail/error） |
| `python -m unittest discover -s tests -p "test_observer_packets.py" -v` | 0 | Ran 10 tests — OK（0 fail/error） |
| `python -m unittest discover -s tests -p "test_*.py"`（全量，无 skip，37.3s） | 0 | Ran 408 tests — OK（0 fail/error） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |
| `python docs/po-repair/tools/collect_corpus.py` | 0 | collected=21，copy_matches=21/21，VALID=3，INVALID=16，VALIDATOR-CRASH=2 |

- 修复前失败测试清单：**无**（现有套件全绿）。
- 语料直检结论：21 份中 **VALID 3 / INVALID 16 / VALIDATOR-CRASH 2**；
  与 evidence-digest 的 3 合法 / 18 非合法一致；PROBLEM-REPORT P1-4 的合法文件名单与直检冲突
  （直检以 `corpus/INDEX.json` 为准，差异已写入 `BASELINE.md` §3.1）。

### 证据路径

- 基线原始输出：`docs/po-repair/baseline/*.txt`
- 语料索引：`docs/po-repair/corpus/INDEX.json`；重构脚本：`docs/po-repair/tools/collect_corpus.py`
- 沙箱原始证据（只读）：`E:\MISC\代码项目\po-validation-sandbox\projects\<case>\.opencode\mvp\observation\G-OBS\<candidate>\*.result.json`

### 未完成事项 / 风险

1. 全部结论基于静态语料与仓库单测；**未做任何实机模型/浏览器验证**（S00 范围外，保持 BLOCKED 待后续步骤）。
2. P1-7 崩溃原因（集合成员测试对 dict 抛 TypeError）已定位，但 S00 未修。
3. 沙箱 `A-web/A-web2/C-web3` 无归档结果、`_probe` 无 `.result.json`，说明 Web 通道与探针在本语料中无结果；
   与 P0-2/未测项一致，已登记。
4. `docs/po-repair/**` 为新产物，尚未提交；后续步骤应继续在此目录增量维护。

### 下一步

**S01**（按任务书：P0-1 相关的席位/派发前置工作；映射 P0-1、P2-17）。

## S01 — 宿主兼容性探针

- **步骤**：S01（验证原生 task 溯源、模型覆盖、CLI fallback、模型目录、图片链路）
- **状态**：PASS（含 2 项 BLOCKED-待重启，见 HOST-COMPATIBILITY.md §7）
- **前置步骤**：S00
- **日期**：2026-09-21
- **产出**：`docs/po-repair/HOST-COMPATIBILITY.md`、`docs/po-repair/baseline/s01/*`、
  `docs/po-repair/tools/s01_*.py`

### 实测结论

1. OpenCode 1.18.25；`opencode run` 支持 `--model/--agent/--file/--format/--attach/--auto`。
2. 原生 task 派发溯源成立：session 表记录 parent_id/agent/model；`task` part 输出含子会话 id。
3. **子会话模型 = 派发时会话当前模型**；`task` 工具输入无 model 字段 → 内置 task 不能逐次指定模型。
4. CLI 指向 subagent 回落实测复现：stderr `is a subagent, not a primary agent. Falling back`，rc=3。
5. `opencode models` 可列目录；`openai/gpt-5.6-luna` 存在。
6. 图片链路实测可用：`gpt-5.6-luna` 正确识别附件 PNG（10.7s，rc=0）。

### 未完成

- 插件路径（SubtaskPartInput.model）与子任务 part 形态：BLOCKED（需重启 OpenCode，S21 验收）。
- 会话内图片附件（非 CLI）与音频/视频：NOT RUN（S13/S16/S17）。

### 下一步

**S02**（冻结 product-observation 数据合同 /2；映射 P1-4、P2-14）。

## S02 — 冻结 observation 数据合同 v2

- **步骤**：S02（纯新增：合同模块、文档、fixtures、测试；不实现 adoption/纠偏/gate）
- **状态**：PASS
- **前置步骤**：S01
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python`，与 S00/S01 相同）

### 创建的文件（未修改任何既有脚本/测试/SKILL）

- `scripts/observation_contract.py`（新模块：版本常量、枚举、`validate_result_payload`、
  `validate_review_payload`、`validate_result_envelope`、`result_template`、`review_template`、
  `contract_enums`、`result_stop_state`）
- `product-observer/references/result-contract.md`（冻结合同文档：(a) 所有权表、(b) 字段表与枚举、
  (c) 语义说明、(d) 运行布局、(e) `contract-enums` JSON 块、(f) fixtures 指引）
- `tests/fixtures/product-observation/discover-valid.json`
- `tests/fixtures/product-observation/compare-valid.json`
- `tests/fixtures/product-observation/budget-valid.json`
- `tests/fixtures/product-observation/blocked-valid.json`
- `tests/fixtures/product-observation/review-valid.json`
- `tests/fixtures/product-observation/review-needs-repair.json`
- `tests/test_observation_contract.py`（49 条测试）
- `docs/po-repair/CONTRACT.md`（覆盖占位内容）
- `docs/po-repair/PROGRESS.md`（本记录）

### 冻结要点

- 版本常量、枚举、`STOP_STATE` 派生映射、`BLOCKING_*` 集合全部按任务书原样落地；
  `owner-decision` 计入 `BLOCKING_FINDING_STATUSES`。
- 顶层/嵌套未知字段严格拒绝；`CONTROLLER_FIELDS` 与 S08 review 信封字段被忽略、不要求。
- 条件规则齐备：compare/discover 的 `difference_classification`、dismissal/resolution 依据、
  `continuation` 与 `budget-exhausted` 绑定、coverage-completed 覆盖规则与 evidence 非空、
  blocked 零接触需 notes 或 capability_gaps。
- 校验器对 dict/list/int/None 的枚举值不抛异常（对照 P1-7 的 v1 崩溃模式，v2 用元组安全判定）。

### 任务书未指定处的实现决定（供后续步骤复核，不改变已冻结语义）

1. `validate_result_payload(payload, phase=None)`：`phase` 可选，提供时钉住阶段并校验一致性；
   省略时按 payload 声明的 `phase` 施加阶段规则。
2. `validate_result_envelope` 的期望参数默认 `None`；提供则做等值校验，未提供只做结构校验。
3. review payload 拒绝未知字段，但放行 S08 的 7 个信封字段（声明的"不在本步骤实现"按忽略处理）。
4. `owner_decision_ref` 视作字符串引用（存在时必须非空）；`resolution_ref` 为严格对象
   `{candidate_id, finding_id}`。
5. 可选数组（`modes`、gap/review 的 `evidence_refs`、`related_finding_ids`、
   continuation 的 visited/pending）允许空数组；标记为"必填"的数组不允许空。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_contract.py" -v` | 0 | Ran 49 tests — OK（0 fail/error） |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 457 tests in 31.5s — OK（408 既有 + 49 新增） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

- 既有 408 条测试全部保持通过；未删除/放松任何既有测试；未修改既有实现。
- 设计矛盾检查：未发现任务书内部矛盾；未自行改动任何冻结字段或枚举。

### 未完成事项 / 风险

1. 合同为**结构层**：覆盖是否诚实、证据是否支撑 finding、review 是否成立留给 S04/S05 的语义表。
2. `product-candidate/2`、`product-audit/2`、`workflow-observer-packet/2`、
   `product-audit-gate/2` 仅冻结版本号，字段表未在本步骤定义（S06/S08/S09）。
3. 信封采纳、run-id/attempt 归档、`result.json` create-only 落盘未实现（S08）；
   运行布局目前只写入文档（`result-contract.md` §7）。
4. 未改 `scripts/product_observation.py`（v1），旧扁平布局与 v1 gate 行为保持原样，
   两套 schema 当前并存；迁移/纠偏路径待 S03/S09 处理。
5. 未做任何实机模型/浏览器验证（S02 不涉及）。

### 下一步

**S03**（按任务书：校对/容错归一或纠偏前置；映射 P1-4、P1-7；需消费 S00 语料
`docs/po-repair/corpus/` 与 v2 合同）。

## S03 — 校验器容错与 v2 合同接入

- **步骤**：S03（让所有 observation 校验器对任意 JSON 只返回诊断、绝不抛异常；接入 S02 冻结的 v2 合同）
- **状态**：PASS
- **前置步骤**：S02
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S02 相同）

### 修改/创建的文件

- `scripts/product_observation.py`（修改）：常量/枚举改为引用 `observation_contract`；report/review
  校验委托 v2 payload + 控制器信封结构校验，`/1` 返回单条迁移诊断；candidate 用 v2 schema 并增加
  `runtime_state` 可选类型校验；audit sidecar 接受 `/1` 与 `/2`；`_load_json` 拒绝 NaN/Infinity 与重复键；
  `collect_observation_problems` 的 stop_state 契约派生、阻断集合含 `owner-decision`、capability_gaps
  按 `channel`+`reason` 判定、trace 类型安全；`write_gate_record` 写 `product-audit-gate/2`。
- `tests/test_product_observation.py`（修改）：合法轮/失败轮全部改为 v2 accepted result + v2 review +
  v2 sidecar；新增 11 条（legacy 诊断、信封结构、attempt、resolved、difference_classification、
  runtime_state、sidecar 双版本、owner-decision 阻断等），共 31 条。
- `tests/test_observer_packets.py`（仅 fixture 适配）：`discover_report()` 补 `outcome` 与
  `model`/`received_at`/`attempt` 信封字段；未改 `scripts/workflow_packets.py`，断言不变。
- `tests/test_observation_malformed.py`（新增）：14 条（枚举/容器类型矩阵、7 个校验器的裸输入矩阵、
  `_load_json` 的 NaN/Infinity/重复键/空文件/非法 JSON/BOM，21 份语料回归）。
- `docs/po-repair/baseline/s03-corpus-regression.json`（新增）：21 份语料逐份判定。
- `docs/po-repair/baseline/s03/{test_observation_malformed,test_product_observation,test_observer_packets,test_all,check_selftest}.txt`（原始输出）。
- `docs/po-repair/CONTRACT.md`（§2 补一句 v2 接入状态）。
- 未修改 `scripts/check.py`、`scripts/workflow_packets.py`、`scripts/install.py`、沙箱与其它 tests。

### 关键实现决定（供 S04/S05 复核）

1. `AUDIT_SIDECAR_SCHEMA` 映射为 `SCHEMA_AUDIT`（`product-audit/2`）；验证器同时接受 `/1`。
2. v1 report/review/candidate 各返回**恰好一条** legacy 诊断，不再逐字段校验；缺失/其它 schema 由
   合同的 `result.schema must be ...` 明确报错。
3. report 信封复用 `validate_result_envelope`（含 `phase`）；review 只做
   `reviewer_session_id`/`discover_hash`/`compare_hash` 结构校验；两者都不做值匹配（留给 collect）。
4. v2 review payload 按冻结合同不含 `candidate_id`；collect 的 candidate 绑定检查改为
   "仅当 review 显式声明 `candidate_id` 时比较"，实际绑定由 review 的 discover/compare 结果
   hash 匹配（结果本身已绑定 candidate）承担 —— S08 若引入 review 信封 candidate 绑定可再收紧。
5. `runtime_state`：存在且非 `null` 时必须为数组；元素字段与语义留给 S06。
6. `_contract is None`（引擎缺模块）时用 v2 字面量常量，v2 校验返回明确
   `observation_contract module unavailable` 诊断，不崩溃。
7. 顺带修复同类崩溃：candidate `baseline.kind` 集合成员测试对 unhashable 值抛 `TypeError`，改为元组；
   trace 的 `sessions`/`skill_events` 非列表、`observer_session_id` 非字符串不再抛异常。
8. `_load_json` 用 `parse_constant` 拒 NaN/Infinity、`object_pairs_hook` 拒重复键，统一诊断
   `invalid JSON: ...`；保持 `utf-8-sig`。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_malformed.py" -v` | 0 | Ran 14 tests — OK（0 fail/error） |
| `python -m unittest discover -s tests -p "test_product_observation.py" -v` | 0 | Ran 31 tests — OK（原 20 + 11） |
| `python -m unittest discover -s tests -p "test_observer_packets.py" -v` | 0 | Ran 10 tests — OK（fixture 最小适配） |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 482 tests in 35.3s — OK（457 → 482） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

原始输出存于 `docs/po-repair/baseline/s03/`；未删除/跳过任何既有测试。

### 语料回归统计（S03 行为）

- 21 份（18 report + 3 review）全部为 `product-observation/1` 系列 → 全部判定 `legacy`，
  每份恰好 1 条 legacy 迁移诊断；**0 崩溃**（S00 基线中的 2 份 `VALIDATOR-CRASH` 不再触发）。
- report 类 18 份的 envelope_error_count 均为 3（v1 缺 `model`/`attempt`/`received_at`）；
  review 类 3 份 envelope_error_count 均为 0。
- `valid=0 / invalid=0` 是预期：v1 语义上不再被接受，只能纠偏后以 v2 重观察（S09）。
- 明细：`docs/po-repair/baseline/s03-corpus-regression.json`；corpus 文件未修改（逐份 sha256 记录在案）。

### 未完成事项 / 风险

1. v1 结果现在必然无法通过 gate（设计如此）；迁移/纠偏回合属 S09。
2. 运行布局、run-id/attempt 归档、create-only 落盘仍未实现（S08）；collect 仍读旧扁平布局。
3. gate 仍是早退式：只要报告结构有问题就先返回，blocking/capability/trace 检查不会同时给出
   （P1-8，S05 负责全量诊断重构）。
4. review 的 candidate 绑定当前依赖结果 hash（见实现决定 4）。
5. **安装清单缺口**：`scripts/install.py`（S03 禁止修改）只复制 `product_observation.py`，
   未复制 `observation_contract.py`；安装后的引擎会走 fallback，v2 校验返回"合同不可用"诊断。
   需要由负责 install/packaging 的后续步骤把合同模块加入复制清单并补对应测试。
6. 未做任何实机模型/浏览器验证（S03 不涉及）。

### 下一步 / 交接（S04 / S05）

- **S04**：review 语义决策表可直接消费 v2 枚举、`STOP_STATE`；结构层已保证 dismissal/resolution
  依据字段存在，语义是否成立仍归 reviewer/决策表。
- **S05**：gate 全量诊断重构时注意：collect 当前检查顺序为 sidecar → manifest → report 结构 →
  blocking → capability_gaps → review → trace；阻断集合已用合同（含 `owner-decision`）；
  capability_gaps 以 `channel`+`reason` 均非空为"已描述"；`stop_state != completed` 即阻断。
- **S06**：`product-candidate/2` 的 `runtime_state` 字段表与元素语义（当前只保证存在时是数组）。
- **S08**：run 布局与 result/review 信封采纳；建议补 review 信封的 candidate 绑定。
- 任意 JSON 输入回归入口：`tests/test_observation_malformed.py`。

### S03 后续集成待办（转 S20A）

- scripts/install.py 的 copy 清单尚未包含 scripts/observation_contract.py；安装到目标项目的引擎会缺该模块（product_observation 只能走 fallback）。S20A 必须补打包，并加 install 测试断言。

## S04 — 统一 finding 语义、权威顺序与 reviewer 裁决决策表

- **步骤**：S04（新增语义纯函数 + gate 接入 + 语义文档/测试；不做 S05 全量诊断重构、不做 S08
  adoption、不改 packet 生成、不做 S19 全量文档同步）
- **状态**：PASS
- **前置步骤**：S03
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S03 相同）

### 修改/创建的文件

- `scripts/observation_contract.py`（新增三个纯语义函数 + `_nonempty_str` 辅助 + 防 unhashable
  的阻断枚举元组；**未改**任何既有 `validate_*` 行为与枚举/字段）。
- `scripts/product_observation.py`（`collect_observation_problems` 接入：逐 finding 语义检查、
  跨阶段聚合 `open_blocking`、review 段执行 verdict 一致性检查；旧阻断汇总信息原样保留）。
- `tests/test_observation_semantics.py`（新增，41 条：阻断判定、finding 语义、review 裁决表、
  结构与语义桥接、`collect_observation_problems` 端到端）。
- `tests/test_product_observation.py`（仅语义适配 2 处：dismissed high 测试补
  `owner_decision_ref`；`test_insufficient_review_verdict_blocks` 改为带开放阻断 finding 的
  自洽 needs-repair 场景；断言不变）。
- `product-observer/references/finding-rules.md`（Severity/Status Rules 修订；新增
  “Difference Classification (compare only)” 与 “Authority Order” 两节）。
- `product-observer/references/observation-protocol.md`（compare 段：分类与权威顺序、阻断级
  intended-change 须 owner decision；Evidence Layout 的 schema 注释 `/1` → `/2`）。
- `reviewer/SKILL.md`（observation 段补语义判断点与 verdict 决策表；`product-observation-review/1`
  引用更正为 `/2`）。
- `docs/po-repair/CONTRACT.md`（§2 补 S04 语义辅助签名与接入状态）。
- `docs/po-repair/baseline/s04/{test_observation_semantics,test_product_observation,test_all,check_selftest}.txt`。
- **未修改**：`scripts/check.py`、`scripts/workflow_packets.py`、`scripts/install.py`、
  `tests/fixtures/**`、其他 tests、其他 SKILL/agent、沙箱；未 reset/clean/stash 既有未提交修改。

### 实现的机械语义（与任务书 A/B 对应）

- 阻断唯一权威：`is_blocking_finding(finding)` = severity ∈ {critical,high} 且 status ∈
  {suspected,confirmed,intermittent,owner-decision}；非 dict/非法枚举一律 `False`、不抛异常。
- finding 语义（`semantic_finding_problems(finding, phase=None)`）：
  - `dismissed` 且阻断级 → 必须非空 `owner_decision_ref`（README/实现者声明不能解除阻断）；
  - `intended-change` 且阻断级（非 discover）→ 必须非空 `owner_decision_ref`；
  - `resolved` → 结构确认非空 `resolution_ref.candidate_id`（跨轮校验留给 S05）；
  - `known-old-issue` → `evidence_refs` 非空；`owner-decision` 分类 → `notes` 或
    `owner_decision_ref` 至少一项非空。
- review 裁决表（`review_verdict_consistency_problems(review, open_blocking)`）：
  `blocked` 不约束；任一 judgment insufficient → 必须 `needs-observation`；否则有开放阻断 →
  必须 `needs-repair`；否则 → 必须 `sufficient`。“多原因须在 notes 列出”保留为文档要求，不解析 notes。
- gate 接入顺序（保持 S03 早退结构）：sidecar → manifest → report 结构（通过后）→ 逐 finding
  语义 + 阻断汇总 → capability_gaps → review 结构/hash → **review verdict 一致性** → trace。
  review 一致性检查位于 review 段，不会因 finding 语义问题被跳过。
- 权威顺序（文档 + 代码一致）：批准的 goal / owner decision > 候选 README/文档声明 > 历史行为。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_semantics.py" -v` | 0 | Ran 41 tests — OK（0 fail/error） |
| `python -m unittest discover -s tests -p "test_product_observation.py" -v` | 0 | Ran 31 tests — OK |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 523 tests in 28.6s — OK（482 既有 + 41 新增） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

原始输出：`docs/po-repair/baseline/s04/*.txt`；未删除/跳过任何既有测试。

### 未完成事项 / 风险

1. `collect_observation_problems` 仍是 S03 的早退结构：report 结构有问题时不会继续跑语义/审查
   检查（新增检查在同一早退内）；全量诊断归 S05。
2. `resolved` 的跨轮校验未实现：目前只确认 `resolution_ref.candidate_id` 非空；候选必须是
   历史验证轮、`finding_id` 必须存在于该轮结果等仍由 S05 gate 负责。
3. 结构与语义诊断可能重复（如 resolved 缺 ref 时合同与语义各报一条）；S05 收敛去重。
4. `owner_decision_ref` 目前只校验非空字符串，未解析到真实 owner decision 工件/事件（S05/S08
   若引入决策登记可收紧）。
5. `tests/fixtures/product-observation/review-needs-repair.json` 为
   `insufficient + needs-repair`：结构合法（S02 只约束 sufficient），但按 S04 语义表不自洽；
   S04 禁止修改 fixtures，语义测试未把它当作“通过”用例，S05/S19 决定是否修订。
6. `product_observation.py` 的 `BLOCKING_SEVERITIES` / `BLOCKING_FINDING_STATUSES` 字面量在
   gate 逻辑中不再直接使用（改由合同函数判定），常量保留以兼容既有导入。
7. `scripts/install.py` 仍缺 `observation_contract.py`（S20A，S03 已登记，S04 未触碰 install）。

### 下一步 / 交接（S05）

- **可复用的语义 API（跨阶段/跨轮检查函数签名）**：
  - `observation_contract.is_blocking_finding(finding: Any) -> bool`
  - `observation_contract.semantic_finding_problems(finding: Any, phase: str | None = None) -> list[str]`
  - `observation_contract.review_verdict_consistency_problems(review: Any, open_blocking: bool) -> list[str]`
  - `product_observation.collect_observation_problems(goal: dict[str, Any], goal_path, project_root: Path | None = None, trace: dict[str, Any] | None = None) -> list[str]`
  - 内部桥接（合同缺失时降级）：`_is_blocking_finding(finding)`、
    `_semantic_finding_problems(finding, phase)`、
    `_review_verdict_consistency_problems(review, open_blocking)`。
- **跨阶段聚合语义**：`open_blocking` 是 discover+compare 两阶段所有 finding 的
  `is_blocking_finding` 逻辑或；review 一致性函数只接收该聚合布尔值，不做阶段区分——S05 重构时
  保持相同输入语义即可。
- **S05 待补跨轮校验**：`status=resolved` 要求 `resolution_ref.candidate_id` 指向历史候选轮
  （非当前候选），且 `resolution_ref.finding_id` 在该轮 accepted plan/结果中存在；必要时把该
  校验作为新纯函数（建议签名 `cross_round_resolution_problems(finding, current_candidate_id,
  known_round_finding_ids) -> list[str]`）加入合同模块并补测试。
- **S05 重构注意**：早退结构改为收集全部诊断时要对语义/结构重复问题去重；review 段一致性检查
  必须在 review 加载成功后执行；`verdict=blocked` 不因一致性报错；`notes` 多原因要求只留在文档。
- 语义回归入口：`tests/test_observation_semantics.py`；结构回归入口不变
  （`test_observation_contract.py` / `test_observation_malformed.py` / `test_product_observation.py`）。

## S05 — gate 依赖感知全量诊断、证据核验、跨轮 resolution 与 finish 闭环

- **步骤**：S05（collect 全量诊断重构 + 证据引用核验 + 跨轮 resolution + gate record v2 + finish/check-current 闭环；不做 S08 adoption、不改 packet 生成、不改 S06/S07 候选状态分离）
- **状态**：PASS
- **前置步骤**：S04
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S04 相同）

### 修改/创建的文件

- `scripts/product_observation.py`（修改）：
  - `collect_observation_problems` 由早退式改为依赖感知的**全量收集**（仅当 sidecar 缺失/不可读、
    `goal.id` 不可定位 cdir、`current_candidate` 无对应轮时停止）；sidecar 结构、manifest 缺失/非法、
    candidate 文件 stale/missing、phase 结构非法/缺失、review 缺失都记录后继续可安全执行的检查；
    结构性 finding 校验失败时跳过该 finding 的语义与跨轮检查（去重），阻断聚合仍覆盖全部 finding。
  - 新增内部工具：`_phase_ref_target`、`_failed_finding_indexes`、`_evidence_ref_problems`、
    `_report_evidence_problems`、`_round_finding_ids`、`_known_round_findings`、
    `_resolution_binding_problems`；`_PHASE_FILES`/`_FINDING_INDEX_RE` 常量。
  - review 的 `discover_hash`/`compare_hash` 改为按 sidecar `discover_ref`/`compare_ref` 解析出的
    文件 sha256（ref 缺失回退 `cdir/<phase>.result.json`）；review 显式含 `candidate_id` 时才比较。
  - 证据核验（findings/journeys/report 的 `evidence_refs`）：非空字符串、非绝对、无 `..`，
    先 `cdir/ref` 后 `project_root/ref` 解析，必须存在且 resolve 后仍在 cdir 内；
    分别报 `not found` / `escapes the candidate evidence scope`。
  - `write_gate_record(goal, goal_path, problems, *, trace_binding=None, goal_definition_hash=None)`：
    新增 `goal_definition_hash`（字符串或省略）与 `trace`（`{path, sha256, provenance}` 或 `null`）。
- `scripts/observation_contract.py`（修改）：新增纯函数
  `resolution_binding_problems(finding, current_candidate_id, known_round_findings) -> list[str]`；
  未改任何既有 `validate_*` 行为、枚举或字段。
- `scripts/check.py`（修改）：
  - `product-audit-gate` CLI：required 且无 `--trace` → fail closed；用 `_runtime_trace.trace_provenance`
    计算 provenance，非 native 追加 `trace provenance is not native`（gate fail）；写 gate record 时带上
    trace binding 与 `goal_definition_hash(goal)`；schema-1/required=false 短路输出保持不变。
  - `enforce_product_observation(goal_path, goal)` 重写：读取 `cdir/gate.json`（缺失/不可读报错并提示
    运行 gate CLI），校验 schema/goal_id/candidate_id/verdict/goal_definition_hash/trace 绑定
    （路径存在、sha256 匹配、provenance=native），载入 trace 后**重新**调用 `collect_observation_problems`
    做最终核验；finish/check-current 只读 gate，不再写 gate record。
- `tests/test_product_observation.py`（最小适配）：共享 fixture 的默认证据引用改为候选目录内真实存在
  的 `candidate.json`；`_full_valid_round` 额外物化真实 `evidence/{round.txt,j01.png,f01.png}` 并把该轮
  引用指回这些文件（满足任务书 G）。未改任何断言。
- `tests/test_observation_gate.py`（新增，33 条）：全量多类诊断、review hash 按 sidecar 引用、
  证据三类引用（缺失/越界/绝对路径/合法）、跨轮 resolution（纯函数 + 端到端）、gate record 五类失败
  与 CLI 成功闭环（native trace → gate passed → check-current/finish-goal 完成）、owner-decision 与
  capability gap 回归。
- `docs/po-repair/baseline/s05/{test_observation_gate,test_product_observation,test_all,check_selftest}.txt`。
- `docs/po-repair/CONTRACT.md`（新增 gate record v2 字段表与 finish 闭环）。
- **未修改**：`scripts/workflow_packets.py`、`scripts/install.py`、其他 tests（含
  `tests/test_observation_semantics.py`）、SKILL/agent、沙箱；未 reset/clean/stash 既有未提交修改。

### 与既有语义测试的兼容处理（规则冲突记录，须复核）

- S05-C 要求**无条件**核验证据路径存在性；S04 的 `tests/test_observation_semantics.py`（属“其他 tests”，
  规则 2/3 禁止修改）的 `write_round` 生成的 `evidence/...` 引用没有真实文件，其中
  `test_clean_round_still_passes` 与 `test_dismissed_high_with_owner_decision_passes_the_gate` 断言
  问题列表为空，任何符合 S05-C 的实现都无法让它们在不适配的情况下保持全绿。
- 处理方式（只动允许文件、不删除/放松断言）：`tests/test_product_observation.py` 的共享
  `base_report`/`finding` 默认引用改为 `candidate.json`（候选目录内永远先写入的真实文件），
  `ObservationProject._full_valid_round` 再物化真实 `evidence/` 文件并把该轮引用指回，
  使 S05 证据核验在 `test_product_observation.py` 内有真实路径覆盖；
  `test_observation_semantics.py` 因此保持全绿且未改一字。
- 影响面：仅 fixture 默认值；两套测试的断言、语义与结构校验口径均未变化。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_gate.py" -v` | 0 | Ran 33 tests — OK（0 fail/error） |
| `python -m unittest discover -s tests -p "test_product_observation.py" -v` | 0 | Ran 31 tests — OK |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 556 tests in 27.6s — OK（523 既有 + 33 新增） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

原始输出：`docs/po-repair/baseline/s05/*.txt`；未删除/跳过任何既有测试。

### 覆盖映射差异（对照 COVERAGE-MAP）

- P1-8（gate 早退）：S05 已修（全量收集）；回归 `test_observation_gate.FullDiagnosisTests`。
- 关联新发现：finish-goal 未传 trace / review hash 路径不一致 / 证据仅字符串 /
  矛盾 review 通过 → S05 已修并有回归（capability gap 校验不足仍属 S09；S05 保持 S04 的
  channel+reason 阻断口径）。workspace 二次阻断仍待 S07/S08。

### 未完成事项 / 风险

1. `resolution_ref` 只核验历史轮 report 中的 `findings[].id`；历史 finding 的语义/内容是否真被当前轮
   修复支持仍归 reviewer 判断（S05 不做内容比对）。
2. 证据核验只保证文件存在且在候选目录内，不解析文件内容/类型（S07/S17 可扩展）。
3. `product-candidate/2` 的 `runtime_state` 仍只有“存在时必须是数组”的类型检查（S06 定义字段语义）。
4. run 布局、信封采纳、review 信封 candidate 绑定仍待 S08；S05 仅在 review 显式含 `candidate_id` 时比较。
5. `scripts/install.py` 仍缺 `observation_contract.py`（S20A 登记不变）。
6. 未做任何实机模型/浏览器验证（S05 不涉及）。

### 下一步 / 交接（S06 / S08）

- **S06**：`product-candidate/2.runtime_state` 字段表与元素语义；S05 已保证 gate 对 candidate 文件的
  path/sha 校验对合法条目仍执行（即使 manifest 其余结构非法）。
- **S08**：adoption/纠偏必须保留 gate record v2 的 `trace` 三字段与 `goal_definition_hash`；finish 闭环
  只认 CLI 写的 gate，trace 事后被改/换都会 stale；采纳器可直接复用
  `collect_observation_problems(goal, goal_path, trace=loaded_trace)` 与
  `resolution_binding_problems` 做最终核验。
- 回归入口：`tests/test_observation_gate.py`；S04 语义入口不变。


## S06 — 候选不可变制品与运行状态分离

- **步骤**：S06（product-candidate/2 的 runtime_state / delivered_roots）
- **状态**：PASS（原派发被中断，实现文件已产出并核验；台账由主控补齐）
- **前置步骤**：S05
- **日期**：2026-09-21

### 修改/创建

- scripts/observation_candidate.py（新）：alidate_runtime_state、
  
untime_state_paths、
untime_state_scope_problems、undeclared_delivered_files。
- scripts/product_observation.py：validate_candidate_manifest 接入结构校验（:289）；
  collect 追加 scope 检查与 undeclared 扫描（:661-664）。
- 	ests/test_observation_candidate.py（新，40 条，Windows symlink 2 条明确 skip）。
- docs/po-repair/CONTRACT.md §6（主控补齐）。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| python -m unittest discover -s tests -p "test_observation_candidate.py" -v | 0 | Ran 40 — OK（skipped=2，无 symlink 权限） |
| python -m unittest discover -s tests -p "test_*.py" | 0 | Ran 596 — OK |
| python scripts/check.py --selftest | 0 | selftest PASS |

### 语义

- runtime_state 文件正常写盘不再使候选失效；files[] 哈希绑定不变；未声明交付文件仍失败。
- 无 runtime_state/delivered_roots 的旧 manifest 行为不变。

### 未完成 / 风险

1. symlink 越界两条测试在当前账户 skip（需管理员或开发者模式复核）。
2. scripts/install.py 仍缺 observation_contract.py 与 observation_candidate.py（S20A 一并补）。

### 下一步

**S07**（verification/workspace binding 与状态策略联动；映射 P1-5、关联新发现）。

## S07 — 运行状态策略贯通 verification → evidence → workspace binding → finish

- **步骤**：S07（新增策略模块与联动；不做 S08 adoption、不做 S10 packet、不改 S06 候选校验本身）
- **状态**：PASS
- **前置步骤**：S06
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S06 相同）

### 修改/创建的文件

- `scripts/runtime_state_policy.py`（新，标准库）：`POLICY_SCHEMA="runtime-state-policy/1"`、
  `policy_path`、`validate_policy`、`load_policy`、`snapshot_excludes`、
  `candidate_policy_alignment_problems`。路径规则委托 `observation_candidate._validate_file_path`
  并复用其 `SOURCE_EXEC_EXTENSIONS` 拒绝表与 `normalize_path`；严格 JSON（拒 NaN/Infinity、
  重复键）；未知字段/非法结构/不可读一律 `(None, problems)`（fail closed）。
- `scripts/check.py`（修改，S07 增量）：
  - graceful import `runtime_state_policy as _state_policy`（失败记录 `_STATE_POLICY_IMPORT_ERROR`）；
  - `_state_policy_file` / `_load_state_policy` / `_state_policy_excludes` 三个内部 helper
    （模块缺失但策略文件存在 → 明确问题，否则 legacy `(None, [])`）；
  - `run_command_evidence(..., state_excludes=())`：before/after 排除表 =
    `(evidence_path, temp) + state_excludes`；`validate_payload` 的 allowed 集合加入
    `runtime_state_policy`（在 expected 中即为 required，不在则可选，兼容恢复旧证据）；
  - `verify_goal_outcome`：构造 metadata 前加载策略（problems → `ValidationError`）、
    非 None 时写入 `metadata["runtime_state_policy"]`，并把 excludes 传给
    `run_command_evidence` / `reuse_goal_evidence`；
  - `reuse_goal_evidence(..., state_excludes=())`：快照使用 excludes；payload 仅在
    expectation 非 None 时复制 `runtime_state_policy`；
  - `evidence_registry.IDENTITY_FIELDS` 追加 `runtime_state_policy`（见 evidence_registry.py）；
  - `enforce_workspace_binding`：加载策略（problems → raise）、快照带 excludes、逐 outcome
    对 payload 绑定与当前绑定做 canonical 比较，不等 → "runtime-state policy changed after
    verification; re-verify"（事后加/删/改路径、改 goal_id、改内容都 stale）；
  - 新增 `observation_state_policy_problems(goal_path, goal)`：读 sidecar `current_candidate`
    的 `candidate.json` 的 `runtime_state`，调 `candidate_policy_alignment_problems`；
    并入 `product-audit-gate` CLI 的 failures 与 `enforce_product_observation` 的 finish 重算
    （sidecar/manifest 缺失返回 []，由 observation gate 自己报缺失）。
- `scripts/evidence_registry.py`（修改 1 行）：`IDENTITY_FIELDS` 加入 `runtime_state_policy`。
- `tests/test_observation_state_binding.py`（新，26 条）：策略模块矩阵（schema/goal_id/类型/
  glob/绝对/`..`/目录/重复/源码扩展名/未知字段/非法 JSON/重复键/缺失 legacy）、
  端到端状态流（无策略 workspace_changed 复现缺陷；策略后 passed 且绑定入证据；观察期状态写入
  不阻断 finish/check-current；改源码失败；改/加路径/删策略 stale）、reuse（同策略成功、
  改策略/删策略拒绝）、alignment 单测 + `check.observation_state_policy_problems`
  临时 sidecar+manifest 集成、symlink 越界 resolve（无权限 skip 并记录原因）。
- `docs/po-repair/CONTRACT.md`（新增 §7：策略文件结构与绑定规则）。
- `docs/po-repair/baseline/s07/*.txt`（6 份原始输出）。
- **未修改**：`scripts/product_observation.py`、`scripts/observation_candidate.py`、
  `scripts/workflow_packets.py`、`scripts/install.py`、其他 tests（无最小适配需要）、
  SKILL/agent、沙箱；未 reset/clean/stash 既有未提交修改。

### 关键实现决定（供 S08 复核）

1. `expectation.setdefault("runtime_state_policy", policy_binding)`：策略被**删除**时
   expectation 显式携带 `None`，而源证据携带旧绑定 → 拒绝复用；旧项目（源/期望均无字段）
   仍 `None == None` 可复用。payload 仍只在非 None 时写该字段（旧证据兼容）。
2. `enforce_workspace_binding` 在策略 stale 时 `continue`（不再重复报 workspace_changed），
   保证 finish/check-current 的错误信息指向根因。
3. 策略 `/1` 允许 `paths: []`（等价于"有策略但不排除"）；创建策略本身即改变绑定，
   旧证据因此 stale，事后补策略不能救回 `workspace_changed` 的失败轮。
4. `observation_state_policy_problems` 对 schema-1 / `required=false` 短路返回 []；
   alignment 只查 candidate 是否是策略子集，策略可包含更多路径。
5. `snapshot_excludes` 按冻结设计只做 `(project_root/p).resolve()`，不做根内包含过滤；
   symlink 越界的结构拒绝仍由 S06 的 `runtime_state_scope_problems` 在观察 gate 承担。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_state_binding.py" -v` | 0 | Ran 26 tests — OK（skipped=1） |
| `python -m unittest discover -s tests -p "test_observation_candidate.py" -v` | 0 | Ran 40 tests — OK（skipped=2） |
| `python -m unittest discover -s tests -p "test_evidence_reuse.py" -v` | 0 | Ran 10 tests — OK |
| `python -m unittest discover -s tests -p "test_evidence_binding.py" -v` | 0 | Ran 12 tests — OK |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 622 tests in 38.4s — OK（596 → 622） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

原始输出：`docs/po-repair/baseline/s07/*.txt`；未删除/放松任何既有断言。
`test_observation_candidate.py` / `test_evidence_reuse.py` / `test_evidence_binding.py`
经确认全绿且无需适配（E 预判的对齐检查只作用于 gate/finish 路径，collect 未改）。

### 未完成 / 风险

1. 策略文件的结构校验是纯静态的：符号链接/junction 越界在 S07 侧不额外拒绝（S06 观察 gate
   已拒绝把越界链接声明为 runtime_state）；当前账户无 symlink 权限，越界 resolve 测试 1 条 skip。
2. 策略改变后必须重新 verify **全部** 已验证 outcomes（enforce 逐条 stale）；不提供局部重验。
3. `runtime_state_policy` 只覆盖 goal-verification 证据，`verify-step` 的计划验证仍无策略排除
   （S07 任务书范围如此）。
4. `scripts/install.py` 仍缺 `observation_contract.py` / `observation_candidate.py` /
   `runtime_state_policy.py`（S20A 待办，见下）。
5. 未做任何实机模型/浏览器验证（S07 不涉及）。

### S20A 打包待办（新增）

- `scripts/install.py` 的 copy 清单必须加入 `scripts/runtime_state_policy.py`（否则 check.py
  走 graceful import：策略文件存在时报"模块不可用"；无策略时行为兼容）。
- 与 S03/S06 已登记的 `observation_contract.py`、`observation_candidate.py` 一并补，
  并加 install 测试断言复制清单含这三个模块。

### 下一步 / 交接（S08）

- adoption/纠偏写入 gate record 时保持 `product-audit-gate` CLI 现有的
  failures = `collect_observation_problems` + `observation_state_policy_problems` 合并口径；
  finish 侧会以同一函数重算，若只写 collect 结果会在 finish 处不一致。
- 新候选轮的 manifest 若声明 `runtime_state`，必须同时保证策略已覆盖（否则 gate fail）；
  adoption 不应替用户写策略。
- 策略绑定字段名 `runtime_state_policy` 已进入证据 payload 与 `IDENTITY_FIELDS`；
  任何新的证据写入路径（如 S08 的 result 归档）不要覆盖/丢失该字段。
- 回归入口：`tests/test_observation_state_binding.py`；策略实现：`scripts/runtime_state_policy.py`；
  绑定语义：`docs/po-repair/CONTRACT.md` §7。

## S08a-1 — observation_results 第一部分：payload 解析 / run 与 attempt 布局 / create-only 尝试归档

- **步骤**：S08a-1（小步；只做解析、路径与尝试归档，不碰 gate/adoption/finish）
- **状态**：PASS
- **前置步骤**：S07
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S07 相同）

### 创建的文件（未修改任何既有文件）

- `scripts/observation_results.py`（新）：
  - `canonical_bytes(value: Any) -> bytes`：`json.dumps(value, ensure_ascii=False, sort_keys=True,
    separators=(",", ":"))` 的 UTF-8 字节。
  - `parse_single_payload(text: str) -> Tuple[Optional[dict], list]`：严格单块解析。
    恰好一个 ```json 围栏块且块后仅空白 → `(object, [])`；0 块 / 多块 / 块前出现其它围栏 /
    JSON 非法 / 非对象 / 尾随非空白 → `(None, [问题...])`。不取最后一块、不扫描任意 JSON；
    围栏前的自然语言说明允许（未定义的问题类型不擅自新增）。
  - `run_dir(cdir, phase, run_id) -> Path`、`result_path(...) -> Path`（`<run>/result.json`）、
    `attempts_dir(run_dir) -> Path`（`<run>/attempts`）。
  - `allocate_run_id(cdir, phase) -> str`：扫描 `<cdir>/<phase>/run-\d+` 目录（忽略文件与非匹配名），
    下一个 `run-%03d`（`run-099` → `run-100`，至少 3 位）。
  - `next_attempt_id(run_dir) -> str`：扫描 `attempts/attempt-\d+\.attempt\.json`，
    下一个 `attempt-%03d`；`.errors.json` 与异名文件忽略。
  - `record_attempt(run_dir, attempt_id, raw_text, parsed, errors, received_at) -> Tuple[Path, Path]`：
    写 `<id>.attempt.json` = `{attempt_id, raw_text, parsed, received_at}` 与
    `<id>.errors.json` = `{attempt_id, errors, parsed_ok: not errors}`；两次 `_write_new_json`，
    errors 写失败时回滚已写的 attempt 文件；attempt_id 必须匹配 `^attempt-\d{3,}$`。
  - `_write_new_json(path, value) -> None`：目录按需创建；已存在 → `ValueError`（create-only）；
    `tempfile.mkstemp` + `os.replace` 原子落盘；UTF-8、`indent=2`、`sort_keys=True`、末尾换行、
    `newline="\n"`；任何失败清理临时文件。
  - 模块级常量/正则：`_FENCE_OPEN`、`_FENCE_CLOSE`、`_RUN_ID_RE`、`_ATTEMPT_ID_RE`、`_ATTEMPT_ID_OK`。
- `tests/test_observation_results.py`（新，26 条，unittest）：parse 7 条（正常 1 块 / 0 块 / 2 块 /
  尾随垃圾 / 非法 JSON / 非对象 / 块后仅空白）、路径辅助与 run/attempt 分配 7 条
  （空目录、增量、忽略非 run-*、补齐与进位、忽略 .errors/异名）、record_attempt 6 条
  （字段内容、失败尝试 parsed_ok=false、重复 id 报错且原文件逐字节不变、无 tmp 残留、
  已存在 errors 文件时回滚 attempt 文件、非法 id 拒绝）、canonical_bytes 4 条
  （键序/空白无关、值异则异、非 ASCII UTF-8 不转义）。
  - 风格对齐 `tests/test_observation_gate.py`：ROOT/sys.path 注入 `scripts`、`tempfile.mkdtemp`
    + `addCleanup(shutil.rmtree)`；无网络、无实机依赖。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_results.py" -v` | 0 | Ran 26 tests — OK |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 648 tests in 35.1s — OK（skipped=3；622 → 648） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

未删除/跳过/放松任何既有断言；既有 622 条全绿。

### 未完成 / 风险（留给 S08a-2 及后续）

1. 仅落盘函数完成：`result.json` 写入/读取、信封字段、与 gate/adoption 的接线均未实现（S08a-2）。
2. `parse_single_payload` 仅校验“恰一个对象块”；schema/字段合法性仍由各合同模块校验。
3. `_write_new_json` 的 create-only 判定为「存在即拒绝」；原子性依赖同一文件系统，不处理并发竞态
   （先 mkstemp 后 replace；存在性检查在读侧再做一次）。
4. `canonical_bytes` 不拒绝 NaN/Infinity（`json.dumps` 默认 `allow_nan=True`）；若未来用于哈希绑定
   需与严格 JSON 要求对齐（当前仅用于内容等价比较）。
5. `scripts/install.py` 的 S20A 待办清单需追加 `scripts/observation_results.py`。

### 下一步（S08a-2）

- 在 `scripts/observation_results.py` 追加 `result.json` 的读写与信封校验（沿用 create-only +
  canonical 比较思路），并补第二批测试；回归入口 `tests/test_observation_results.py`。

## S08a-2 — observation_results 第二部分：信封校验 / provenance 与证据闸门 / adopt_result

- **步骤**：S08a-2（小步；在 S08a-1 模块上追加采纳与读取，不碰 gate/adoption/finish、不碰锁/sidecar）
- **状态**：PASS
- **前置步骤**：S08a-1
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S08a-1 相同）

### 修改的文件（只追加允许范围内）

- `scripts/observation_results.py`（追加）：顶部新增 `datetime.timezone` 导入与
  `try: import observation_contract as _contract`（graceful）；文末追加 S08a-2 区块。
- `tests/test_observation_results.py`（追加）：导入 `observation_contract as contract`；
  新增 envelope/采纳/读取 33 条测试（26 → 59）。
- `docs/po-repair/PROGRESS.md`（本记录）。
- **未修改**：其他任何文件（gate/合同/candidate/策略/install/其他测试均未触碰）；未 commit。

### 实际签名（Python 3.10 标准库）

```python
evidence_ref_problems(cdir: Any, project_root: Any, payload: Any) -> list
provenance_problems(trace: Any, session_id: Any, skill: str = "product-observer") -> list
validate_envelope(envelope: Any) -> list
adopt_result(cdir: Any, project_root: Any, phase: str, payload: Any, envelope: Any,
             trace: Any, run_id: Optional[str] = None, attempt_id: Optional[str] = None,
             received_at: Optional[str] = None) -> Tuple[Optional[Path], list]
load_result(path: Any) -> Tuple[Optional[dict], list]
```

内部辅助：`_utc_now() -> str`、`_evidence_value_problems(ref, cdir, project_root, label, problems)`、
`_remove_stale_result_temps(target: Path)`、`_reject_adoption(...) -> Tuple[None, list]`；
常量 `_HASH_RE`、`_ADOPT_PHASES = ("discover", "compare")`、`_CONTRACT_UNAVAILABLE`。

### 行为要点（实现决定，供 S08b 复核）

1. `adopt_result` 校验顺序与任务书一致：phase 合法 → payload 为 dict 且 `payload["phase"] == phase`
   → 合同 `validate_result_payload(payload, phase)` → `validate_envelope` → 控制器字段冲突
   （仅比较 **同时出现** 在 payload 与 envelope 的 `CONTROLLER_FIELDS`，`canonical_bytes` 等价则放行）
   → `provenance_problems(trace, envelope["observer_session_id"])` → 证据闸门 → accepted（payload
   叠加 envelope + `received_at`）复核。任何一步失败都先 `record_attempt`（原始 payload 文本 +
   问题列表）再返回 `(None, problems)`，绝不写 `result.json`。
2. `received_at` 缺省生成 `YYYY-MM-DDTHH:MM:SSZ`（UTC、秒级）；显式传入但空/非字符串 → 拒绝。
   生成的 `received_at` 写入 accepted `result.json`（合同 `CONTROLLER_FIELDS` 成员）。
3. 成功路径：`run_id` 缺省 `allocate_run_id`、`attempt_id` 缺省 `next_attempt_id`，先
   `record_attempt(... errors=[])`，再 create-only 写 `result.json`（复用 `_write_new_json` 原子语义）。
   已存在且 `canonical_bytes` 相同 → 幂等成功返回原路径、**problems 为空**（见决定 5）；
   不同 → `result.json conflict: ... already exists with different content` 并保持原文件逐字节不变。
4. 遗留临时文件清理放在 `adopt_result` 早期（任何拒绝路径都会清理）：删除运行目录中文件名包含
   `result.json` 且以 `.tmp` 结尾的文件（覆盖 `result.json.tmp` 与 `_write_new_json` 的
   `.result.json.*.tmp`）；不提升、不记入问题。
5. 任务书“重复时 errors 追加 duplicate result”与结尾硬规则“成功时 problems 为空列表”冲突，
   且 `record_attempt` 是 create-only、无法回写；S08a-2 采用 **幂等成功 + 空 problems**，
   不伪造 errors。S08b 若需要审计幂等命中，建议在调用方或后续 sidecar 记录，而不是改 create-only 语义。
6. `provenance_problems`：trace 非 dict / sessions / skill_events 非 list → 单条
   `runtime trace unavailable: ...`；session 缺失 → `... not found in the runtime trace`；
   无 completed `(session_id, skill)` → `... has no completed <skill> skill load`（措辞对齐 S05 gate）。
7. `evidence_ref_problems` 语义与 S05 `_evidence_ref_problems` 一致（非空字符串、非绝对、无 `..`、
   先 cdir 后 project_root、必须存在且 resolve 后仍在 cdir 内）；消息按任务书字面
   `evidence ref not found: X` / `evidence ref escapes the candidate evidence scope: X`；
   非 dict payload/journey/finding 返回问题而非异常，非 list 的 `evidence_refs` 交给结构合同。
8. `load_result` 用 `utf-8-sig` 读取（接受 BOM）；OSError / 非法 JSON / 非对象分别返回
   `cannot read ...` / `invalid JSON: ...` / `result file must contain a JSON object: ...`。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_results.py" -v` | 0 | Ran 59 tests — OK（原 26 + 新 33） |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 681 tests in 29.3s — OK（skipped=3；648 → 681） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

新增测试覆盖：envelope 正反例（缺字段/空白/64 位小写 hex/attempt 类型与下界/非 dict）、
discover 与 compare 采纳成功（result + attempt + errors、信封与语义字段保留）、
phase 不符 / payload-envelope 冲突（相同值放行）/ 信封缺字段 → 无 result 但有 attempt、
证据缺失（report/journey/finding 三处）/ `..` / 绝对路径 → 拒绝、
provenance 缺 session / 缺 skill load / trace 非 dict → 拒绝（最小合法 trace 通过）、
create-only（幂等字节不变、不同内容冲突字节不变、遗留 tmp 清理且不产生 result）、
第二个 run → run-002、同 run attempt 递增（attempt-001/002）、
`evidence_ref_problems`/`provenance_problems` 对 None/dict/list/str 不抛异常、`load_result` 四态。
用例 payload 一律来自 `observation_contract.result_template(phase)` 的 `json` 深拷贝。

### 未完成 / 风险（留给 S08b 及后续）

1. 锁、sidecar（采纳登记）、`adopt_review` 均未实现（本步骤范围外，S08b）。
2. 幂等命中不写任何审计标记（见决定 5）；若 S08b 侧需要，建议使用独立 sidecar。
3. 未实现多进程并发保护：`adopt_result` 的 create-only 判定仍是“检查存在 + `_write_new_json` 复核”，
   跨进程竞态由 S08b 的锁承担。
4. `recheck` 发生在 `record_attempt` 之前、冲突/幂等判定在其后；失败路径的 attempt errors 只记录
   到校验阶段的问题，不含冲突/幂等诊断（create-only errors 文件已落盘，无法追加）。
5. `scripts/install.py` 的 S20A 待办清单需追加 `scripts/observation_results.py`（S08a-1 已登记）。
6. 未做任何实机模型/浏览器验证（本步骤不涉及）。

### 下一步（S08b）

- **S08b**：锁（跨进程采纳互斥）、sidecar（采纳结果登记 / 幂等命中审计）、`adopt_review`（review
  信封与 result hash 绑定）；回归入口保持 `tests/test_observation_results.py`，全量 681 应只增不减。

## S08b — 文件锁 / product-audit sidecar 更新 / adopt_review；S08 完成

- **步骤**：S08b（小步；在 S08a-1/S08a-2 模块上追加锁、sidecar、review 采纳；不碰 gate/finish/packet）
- **状态**：PASS（**S08 整体完成**：S08a-1 + S08a-2 + S08b）
- **前置步骤**：S08a-2
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S08a-2 相同）

### 修改的文件（只追加 / 只动允许清单）

- `scripts/observation_results.py`（追加 S08b 区块，既有函数一字未改）：
  `file_lock`、`load_sidecar`、`update_sidecar`、`validate_review_envelope`、`adopt_review`；
  内部辅助 `_quiet_unlink`、`_stat_identity`、`_is_older_than`、`_lock_state`、
  `_write_replace_json`、`_relative_posix_problems`、`_sidecar_for_update`、`_file_sha256`、
  `_archive_accepted_result`；常量 `_SIDECAR_SCHEMA="product-audit/2"`、
  `_SIDECAR_LOCK_SUFFIX=".lock"`、`_PHASE_REF_FIELDS`、`_REVIEW_ENVELOPE_FIELDS`、
  `_LOCK_POLL_SECONDS=0.05`。
- `tests/test_observation_results.py`（追加 35 条：FileLock 4、SidecarUpdate 11、LoadSidecar 5、
  AdoptReview 15；59 → 94）。
- `docs/po-repair/PROGRESS.md`（本记录）、`docs/po-repair/CONTRACT.md`（§8）。
- **未修改**：其他任何文件（gate/合同/candidate/策略/install/其他测试/SKILL/沙箱均未触碰）；
  未 commit；未 reset/clean/stash 既有未提交修改。

### 实际签名（Python 3.10 标准库）

```python
file_lock(lock_path: Any, timeout: float = 10.0, stale_after: float = 120.0)  # contextmanager
load_sidecar(sidecar_path: Any) -> Tuple[Optional[dict], list]
update_sidecar(sidecar_path: Any, goal_id: Any, candidate_id: Any, phase: Any,
               result_rel_path: Any) -> Tuple[Optional[dict], list]
validate_review_envelope(envelope: Any) -> list
adopt_review(cdir: Any, project_root: Any, payload: Any, envelope: Any,
             discover_path: Any, compare_path: Any, trace: Any,
             run_id: Optional[str] = None, attempt_id: Optional[str] = None,
             received_at: Optional[str] = None) -> Tuple[Optional[Path], list]
```

### 行为要点（实现决定）

1. **锁**：`O_CREAT|O_EXCL` 原子创建；争用退避固定 0.05s，超时抛
   `TimeoutError("timed out waiting for lock: <path> (<last OSError>)")`（含锁路径）。
   陈旧判定 `_lock_state` 返回 `gone/held/stale`：`stat` 失败为 `gone` 立即重试；
   只有「首次 stat 超龄 + 立即二次 stat 身份（mtime_ns/size/st_ino）一致」才判 `stale` 并删除，
   避免把其它线程刚创建的新锁误删。Windows 删除挂起期 `os.open` 可能抛
   `PermissionError`（而非 `FileExistsError`）——统一按 OS 错误处理：`gone` 重试、
   否则等待/超时；`finally` 无条件删锁。同进程多线程由 O_EXCL 互斥。
2. **实测竞态（已修）**：初版把 `FileNotFoundError` 当作陈旧并 unlink，导致误删持有者新锁
   → 并发测试峰值=2；另有 Windows `PermissionError` 未捕获直接冒泡。修复后
   `FileLockTests` 连跑 50 次、sidecar 并发用例连跑 30 次全 OK（原失败可复现）。
3. **update_sidecar**：参数先校验（`goal_id`/`candidate_id` 非空、`phase ∈ {discover,compare,review}`、
   rel path 非空/非绝对/无 `..`/反斜杠拒绝）；随后在 `<sidecar>.lock` 下读-改-写。
   缺失新建；schema 统一 `product-audit/2`；`goal_id`/`current_candidate` 置为参数值；
   rounds 中该 candidate 轮存在则只写当前 phase ref（其它 ref 不碰、历史轮不删不重排），
   不存在则追加 `{candidate_id, discover_ref:"", compare_ref:"", review_ref:""}` 后填当前 ref；
   既有未知字段保留；已存在文件不可读/非对象/rounds 非数组一律 fail closed 且原字节不变；
   落盘用同目录 temp + `os.replace`（注入 `os.replace` 失败时原文件逐字节不变、无残留 tmp）。
4. **adopt_review**：review run 布局 `<cdir>/review/<run-id>/result.json`，attempt 记录与
   `adopt_result` 同为 create-only；`run_id` 缺省 `allocate_run_id(cdir,"review")`。
   payload 走 `validate_review_payload`；信封必填 `reviewer_session_id`/`model`（非空串）与
   `attempt ≥ 1` 整数，`received_at` 参数缺省时取信封值再缺省生成，`goal_id`/`candidate_id`
   存在则保留；`discover_hash`/`compare_hash` 由本函数对传入路径**实算 sha256** 写入 accepted，
   payload/envelope 自带的同名值只要与实算不同即拒绝（**冲突**）；provenance 用
   `provenance_problems(trace, reviewer_session_id, skill="reviewer")`。成功/幂等/冲突语义与
   `adopt_result` 一致（复用 `record_attempt`/`_write_new_json`/`load_result`/`canonical_bytes`/
   `_remove_stale_result_temps`/`_reject_adoption`，新增共享尾 `_archive_accepted_result`）。
   重复同内容 → 幂等成功返回原路径、problems 空；不同内容 → `result.json conflict` 且原文件不动。
5. **S08a-2 决定 5 延续**：幂等命中不写审计标记（sidecar 供调用方登记），未改动 create-only 语义。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_results.py" -v` | 0 | Ran 94 tests — OK（原 59 + 新 35） |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 716 tests in 30.6s — OK（skipped=3；681 → 716） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |
| 并发压测（本地额外） | 0 | FileLockTests ×50 全 OK；sidecar 并发用例 ×30 全 OK |

新增覆盖：锁重入获取/超时消息含路径/陈旧锁回收/线程互斥峰值=1；sidecar 新建 v2、
第二 phase 不破坏第一、第三 phase=review_ref、历史轮顺序与 ref 保留、current_candidate 更新、
未知字段保留、非法 rel path（空/`..`/绝对/反斜杠/非字符串）拒绝、非法 phase/身份拒绝、
`os.replace` 注入失败原字节不变且无 tmp、不可读/非对象 fail closed、双线程并发无损坏；
`load_sidecar` 缺失 `(None,[])`/BOM/非法 JSON/非对象；adopt_review 实算 hash 写入、
payload/envelope 冲突 hash 拒绝、hash 源缺失拒绝、reviewer skill load 必需、session 缺失拒绝、
信封缺字段/坏 attempt 拒绝、goal_id/candidate_id 保留、幂等/冲突字节不变、第二 run=run-002、
非法 payload 记 attempt 不产出 result。用例 payload 来自 `contract.review_template()` 深拷贝。

### S20A 打包待办（更新）

- `scripts/install.py` 的 copy 清单必须加入 `scripts/observation_results.py`
  （S08b 采纳器/锁/sidecar 全部依赖它），与已登记的 `observation_contract.py`（S03）、
  `observation_candidate.py`（S06）、`runtime_state_policy.py`（S07）一并补，并加 install 测试断言。

### 未完成 / 风险（留给后续）

1. `adopt_result`/`adopt_review` 自身仍未加锁：跨进程互斥由调用方使用 `file_lock`（sidecar 更新已内置）。
2. 锁为「文件存在即持有」的咨询锁：不校验持有者身份，长于 `stale_after` 的临界区可能被回收；
   默认 120s 对采纳写盘足够，调用方若需更长临界区应显式调大 `stale_after`。
3. sidecar 手工写坏（rounds 非数组）会 fail closed，需人工修复；不自动重建。
4. `adopt_review` 的 `project_root` 形参当前保留未用（与 `adopt_result` 签名对齐，供后续证据核验）。
5. 未做任何实机模型/浏览器验证（本步骤不涉及）。

### 下一步

**S09**（按任务书：v1 语料/纠偏回合与 capability gap 状态机；映射 P1-4、S03 语料），
采纳器接线到 gate/finish 由后续集成步骤消费本步骤 API。

## S09 — 格式纠偏状态机（首次回答 + 最多 2 次纠偏）

- **步骤**：S09（`observation_results` 追加 `repair_prompt` / `run_format_repair`；只做纠偏回合，
  不实现 capability gap 状态机、不接线 gate/finish）
- **状态**：PASS
- **前置步骤**：S08b
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S08b 相同）

### 修改/创建的文件

- `scripts/observation_results.py`（追加 S09 区块，既有函数一字未改）：
  `repair_prompt`、`run_format_repair`；内部辅助 `_repair_marker`、`_json_text`、
  `_repair_template_text`、`_result_schema_name`；常量 `_MARKER_FIELD`、`_MARKER_VALUE`、
  `_MARKER_EXAMPLE`；`from typing import Callable`（随区块追加）。
- `tests/test_observation_format_repair.py`（新，20 条，unittest）。
- `product-observer/references/format-repair.md`（新）：触发条件、两次上限、四条禁令、
  两种合法回复与例子、needs-observation 判定与例子、状态机表，并声明由
  `observation_results.repair_prompt` 的运行时文本引用（提示词末尾引用本文件路径）。
- `docs/po-repair/baseline/s09-corpus-repair.json`（测试生成的 21 份语料逐份终态）。
- `docs/po-repair/PROGRESS.md`（本记录）。
- **未修改**：corpus 文件（测试内以 sha256 前后断言未变）、其他 scripts/tests/SKILL/沙箱；
  未 commit；未 reset/clean/stash 既有未提交修改。

### 实际签名（Python 3.10 标准库）

```python
repair_prompt(phase: Any, payload: Any, problems: Any, attempt_number: int,
              max_repairs: int = 2) -> str
run_format_repair(phase: Any, first_text: Any, send: Callable[[str], str], *,
                  run_dir: Any = None, max_repairs: int = 2,
                  received_at: Optional[str] = None) -> dict
# 返回：{status: "adopted"|"needs-observation"|"failed", payload: dict|None,
#        problems: [...], repair_count: int, attempts: int, reason: str|None}
```

### 行为要点（实现决定，供后续集成复核）

1. **marker 只在状态机内识别**：payload 为 dict 且 `repair_outcome == "needs-observation"`
   （精确值）即为 marker；`reason` 可选，非法/空白时回退为
   `model reported needs-observation without a reason`。其它值（含 `needs_observation`）
   按普通 payload 走校验/纠偏，不构成 marker，也不会抛异常。
2. **次数语义**：`repair_count` = 已发出的纠偏提示数（≤ max_repairs）；`attempts` = 已收到的
   尝试文本数（≤ max_repairs+1）。触发顺序：解析失败或合同校验失败 → 若 repair_count <
   max_repairs 则 `repair_prompt(…, attempt_number=repair_count+1)` + `send`；否则以
   `needs-observation`（cap）终止并保留最后一次错误列表。`max_repairs=0` 时首次非法即 cap，
   不调用 send。
3. **`send` 异常**：捕获为 `failed`，`reason = "send failed: <Type>: <text>"`（保留异常文本）。
4. **run_dir 归档**：每次收到的文本（含 marker 尝试）调用 `record_attempt(run_dir,
   id, raw_text, parsed, errors, received_at)`，id 由 `next_attempt_id` 逐次递增；归档自身
   失败只追加 `failed to record attempt: …` 到返回 problems，不中断状态机（adopted 时
   problems 可能因此非空）。
5. **不抛异常保证**：first_text 非字符串/空/无围栏/非对象/非法 JSON/超长（含 20 万字符）/
   send 返回非字符串、phase 非法（如 review 语料）、`_contract is None`（直接
   needs-observation，attempts=0）全部有明确终态。`_repair_template_text` 对未知 phase
   回退最小骨架，`repair_prompt` 对任意 problems/payload 不抛异常。
6. **repair_prompt 内容**：明确“这是第 n/max 次格式纠偏”+四条禁令（不操作产品、不新增事实、
   不改含义、不猜 controller 字段）；原始 payload 与模板 JSON 均按
   `json.dumps(..., ensure_ascii=False, indent=2)` 原文嵌入（测试按子串断言）；错误逐条 `- `
   列出；两种合法回复与“只有一个 ```json 围栏块”约束；信息不足必须 marker 且禁止编造；
   末尾引用 `product-observer/references/format-repair.md`。
7. **语料回放口径（需复核）**：按任务书字面，`first_text = json.dumps(文件内容,
   ensure_ascii=False)`（无围栏）→ 21 份首步均为“无 ```json 围栏块”1 条解析错误；
   baseline 另记 `payload_errors`（同一文件 payload 的 v2 合同错误数，3–93，来自直接
   `validate_result_payload`）以便对照 S03 明细。终态全部为 needs-observation（cap）。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_format_repair.py" -v` | 0 | Ran 20 tests — OK（0 fail/error） |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 736 tests in 43.4s — OK（skipped=3；716 → 736） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

新增测试覆盖：repair_prompt 全要素（次数/原始 payload/逐条错误/模板可解析且过合同/禁令与
文档引用/未知 phase 不抛）；首次合法 adopted（repair_count=0、attempts=1）；
[非法,合法] repair_count=1、[非法,非法,合法] repair_count=2/attempts=3；
[非法×3] cap needs-observation；模板深拷贝最小改动 adopted；marker 带/不带 reason 与 4 种
变体；`repair_outcome != needs-observation` 不算 marker；max_repairs=0 不发 send；
send 异常 failed；9 种异常输入不抛；phase 不符不误采纳；run_dir 三次尝试文件逐次生成
（attempt-001/002/003 × attempt+errors、received_at、raw_text、marker 尝试 parsed_ok）、
已有编号续写；语料回放 21 份无异常终止且 corpus sha256 前后不变、终态写 baseline。

### 语料回放统计（S09 行为；明细见 docs/po-repair/baseline/s09-corpus-repair.json）

- 21 份（discover 10 / compare 8 / review 3）：status 全部 `needs-observation`（cap），
  `attempts=3`、`repair_count=2`；`initial_errors=1`（首步无围栏）；
  底层 payload 的 v2 合同错误数 `payload_errors` 分布 3–93（最小 3：t1 compare；
  最大 93：F-term cand-bad discover）。0 崩溃、0 采纳（v1 语料不可能直接合法）。
- 与 S03 判定一致（S03：21 份 v1 全 legacy）；S09 证明这些 v1 回答在格式纠偏路径上
  只会走到 cap→needs-observation，不会臆造 surface/证据强行合法化。

### 未完成 / 风险

1. 本步骤只交付“纯状态机 + 提示词”；**capability gap 状态机**与观察器/控制器接线
   （何时调用 `run_format_repair`、`send` 如何接宿主 CLI）仍未实现，待后续步骤。
2. `run_format_repair` 不负责把 adopted payload 送入 `adopt_result`；调用方仍需信封、
   provenance、证据闸门与 run 归档（S08a/S08b API）。
3. 纠偏只做结构校验（合同），不做语义校验（S04/S05 的 semantic/resolution 检查）；
   语义问题不应由格式纠偏回合解决。
4. `problems` 与 `record_failures` 合并口径：adopted 时若归档失败 problems 非空但仍
   adopted；调用方若要求“adopted ⇔ problems 为空”需先处理归档失败。
5. `scripts/install.py` 的 S20A 清单不变（`observation_results.py` 已在册，S08b 登记）。
6. 未做任何实机模型/浏览器验证（本步骤不涉及）。

### 下一步 / 交接

- **接线**：控制器收到非法首答时调用 `run_format_repair(phase, raw_text, send,
  run_dir=<cdir>/<phase>/<run-id>)`，adopted 后把 `result["payload"]` 交给
  `adopt_result`/`adopt_review` 流程；needs-observation 时把 `reason` 记入候选/审查记录。
- 回归入口：`tests/test_observation_format_repair.py`；
  文档：`product-observer/references/format-repair.md`；
  语料终态：`docs/po-repair/baseline/s09-corpus-repair.json`。

## S10 — 观察器 packet v2（brief 盲化 / goal hash 绑定 / preflight 嵌入 / compare 全量校验）

- **步骤**：S10（重写 `build_observer_packet` 与 `validate_packet` 的 observer 分支；新增 preflight 合同；
  不改 gate/finish/adoption，不改 v1 语料纠偏）
- **状态**：PASS
- **前置步骤**：S09
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S09 相同）

### 修改/创建的文件

- `scripts/workflow_packets.py`（修改）：新增 `observation_contract` graceful import；常量
  `OBSERVER_PACKET_SCHEMA` 升级为 `workflow-observer-packet/2`、新增 `PREFLIGHT_SCHEMA`、
  `OBSERVER_REPAIR_REFERENCE`、`OBSERVER_RULES_TEXT`、`_HASH64_RE`；`_sha256` 额外捕获
  `ValueError`（内嵌 NUL 等畸形路径）；重写 `build_observer_packet`（whitelist 字段、
  brief/goal_binding/candidate/output/model/preflight/original）；重写 `validate_packet`
  的 observer 分支并新增 `goal_path` 可选参数；新增内部辅助 `_posix`、`_project_root`、
  `_project_relative_posix`、`_parse_model`、`_load_preflight`、`_packet_project_root`、
  `_preflight_packet_problems`；CLI `observer` 增加 `--model`/`--preflight`，
  `validate` 增加 `--goal`。
- `tests/test_observer_packets.py`（修改，10 → 23 条）：全部适配 v2 并追加 blind 递归扫描、
  brief 公开字段、template/rules、model 解析、preflight 5 类、compare 全量校验 3 类、
  validate_packet 绑定/畸形输入 2 类；既有意图（blind、stale、forbidden、schema1、CLI 写包）保留。
- `docs/po-repair/baseline/s10/{test_observer_packets,test_all,check_selftest}.txt`（原始输出）。
- `docs/po-repair/PROGRESS.md`（本记录）。
- **未修改**：其他 scripts/tests/SKILL/agent、`scripts/install.py`、沙箱；未 commit；
  未 reset/clean/stash 既有未提交修改。

### 实际签名（Python 3.10 标准库）

```python
OBSERVER_PACKET_SCHEMA = "workflow-observer-packet/2"   # == observation_contract.SCHEMA_PACKET
PREFLIGHT_SCHEMA = "observation-preflight/1"
OBSERVER_REPAIR_REFERENCE = "product-observer/references/format-repair.md"
OBSERVER_RULES_TEXT: str  # 紧凑中英混合规则文本

build_observer_packet(goal_path: Path, phase: str, generated_at: str | None = None,
                      model: str | None = None,
                      preflight_path: str | Path | None = None) -> dict[str, Any]
validate_packet(packet_path: Path, goal_path: str | Path | None = None) -> list[str]
```

私有辅助：`_posix(raw)`、`_project_root(goal_path)`、`_project_relative_posix(path, root)`、
`_parse_model(model)`、`_load_preflight(preflight_file, model) -> (payload, sha256)`、
`_packet_project_root(packet, goal_path)`、`_preflight_packet_problems(preflight, packet, root)`。

### packet v2 结构（build 产物）

- 公共：`schema/phase/goal_id/generated_at`。
- `brief`：`{purpose, demo, first_slice, raw_request}`（goal 卡公开字段；不含
  outcomes/verification/constraints）。
- `goal_binding`：`{goal_card_sha256}`（仅 hash，无路径）。
- `candidate`：`{id, manifest_path, manifest_sha256, entry, environment, backend, channels,
  test_data, runtime_state, delivered_roots}`。
- `evidence_dir`、`budget`（字段与数值不变）、`output`（`product-observation/2` +
  `result_template(phase)` + rules + repair_reference）。
- `model`：未传为 `null`，传入按首个 `/` 解析为 `{provider_id, model_id}`。
- `preflight`：无文件为 `null`；否则 `{path, sha256, performed_at, performed_by,
  covers:{host,model,candidate,session}}`，`path` 为项目相对 posix（越出项目根时回退绝对 posix）。
- compare 追加 `original`：`{goal, demo, first_slice, raw_request, baselines,
  discover_result:{path, sha256}, approved_changes?}`；`discover_result.path` 直接取自 sidecar
  当前轮 `discover_ref`，按项目根解析并要求存在。discover 包不含 `original`、不含 goal 卡路径。

### 关键实现决定（任务书未指定处，供后续集成复核）

1. **model 畸形 fail closed**：`model` 无 `/` 或任一侧为空 → `ValueError`（无法完成 preflight
   比对与所有权解析），不是静默接受。
2. **preflight 路径解析**：显式 `preflight_path` 为相对路径时按项目根解析；默认位置为
   `<cdir>/preflight.json`（存在才加载）。显式给出但不可读 → `ValueError`。
3. **validate 无 `--goal` 时的根推断**：优先 `goal_path.parents[2]`；否则由
   `candidate.manifest_path` 的 `parents[5]`（`<root>/.opencode/mvp/observation/<gid>/<cid>/candidate.json`）
   推断；再不行时相对 preflight/discover 路径报"cannot be resolved"问题，绝不抛异常。
4. **preflight covers 只保留四键**（host/model/candidate/session 的原始对象，多余字段丢弃）；
   每个必须是带非空 `status` 的对象。
5. **`original.approved_changes`**：由旧的顶层 `approved_changes` 移入 `original`，且仅 compare 出现。
6. **compare 仍额外核对** discover 的 `phase == "discover"` 与 `candidate_id` 绑定（全量
   payload 校验之外的 identity 交叉核对）。
7. **`_sha256` 捕获 `ValueError`**：畸形路径（如内嵌 NUL）统一视为"不可读"返回 `None`，
   保证 `validate_packet` 对任意 JSON 只返回问题列表。
8. **v1 packet**：`workflow-observer-packet/1` 不再被识别，`validate_packet` 报
   `unknown packet schema`；v1 语料/纠偏路径（S09）不受影响。
9. **OBSERVER_RULES_TEXT** 覆盖：stop_reason→state 映射（coverage-completed 可与阻断 finding
   共存、blocked 零接触需 notes/capability_gaps 说明）、证据相对路径 + evidence_dir 内真实存在、
   controller 所有权字段清单、盲态禁令（goal 卡/`.opencode/mvp/**` 除 manifest 与 evidence_dir、
   diff/测试/验收场景）、单 ```json 围栏块 + format-repair.md 引用。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observer_packets.py" -v` | 0 | Ran 23 tests — OK（原 10 + 新 13） |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 749 tests in 35.8s — OK（skipped=3；736 → 749） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

原始输出：`docs/po-repair/baseline/s10/*.txt`；未删除/放松任何既有断言。

### 覆盖映射差异

- P2-10（观察者前置 preflight 缺失）：S10 交付 `observation-preflight/1` 合同（加载/校验/
  嵌入/复核）与 CLI `--preflight`；探针的**实际执行**（宿主/模型/candidate/session 四类探针
  如何产出该文件）仍属 S15/S21 实机验证，不在本步骤。
- P0-2（Web 通道）不变；S10 仅保证 candidate 的 backend/channels 原样进入 packet。

### 未完成 / 风险

1. `brief` 只暴露 goal 卡公开字段，但 goal 文本本身若含敏感实现提示，仍会原样进入 packet
   （whitelist 只保证不给 outcomes/verification/constraints）。
2. preflight 的语义（探针是否真的执行过、`status=passed` 是否可信）不做校验，只做结构 + sha +
   model 绑定；伪造文件仍可自洽。
3. validate 无 `--goal` 时对 preflight 相对路径的根推断依赖候选目录固定五级布局；
   布局变化会退化为"cannot be resolved"问题（fail closed，不会误判通过）。
4. `scripts/install.py` 的 S20A 清单需追加 `observation_contract.py`（S03 已登记；S10 的 build
   依赖它提供 `result_template`，缺失时 `build_observer_packet` 明确 RuntimeError）。
5. 未做任何实机模型/浏览器验证（本步骤不涉及）。

### 下一步 / 交接

- **控制器**：discover 派发写 `observer --model <provider/model> [--preflight <path>]`；
  compare 派发前先把 discover accepted 结果登记到 sidecar `discover_ref`（S08b `update_sidecar`），
  `build_observer_packet("compare")` 会全量校验该结果并报出全部问题。
- **复核入口**：`validate_packet(packet, goal_path=...)`（discover 必须传 `--goal`，否则 fail closed，
  compare 可省略）；回归入口：`tests/test_observer_packets.py`。
- 预检产出路径约定：`<cdir>/preflight.json`（默认自动拾取），或由 `--preflight` 显式指定。

## S11 — 项目观察模型设置（目录解析 / 消歧 / 原子落盘 + /visibility 命令）

- **步骤**：S11（新增 `visibility_config.py`、`tests/test_visibility_config.py`、
  `.opencode/commands/visibility.md`；只做项目设置解析与消歧 + 命令文档，不改 gate/finish/adoption/packet）
- **状态**：PASS
- **前置步骤**：S10（S01 §5 路径 A 的设置解析前提）
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S10 相同）

### 修改/创建的文件

- `scripts/visibility_config.py`（新）：常量 `VISIBILITY_SCHEMA`、`DEFAULT_REQUEST`、
  `VISIBILITY_RELATIVE_PATH`、`CAPABILITIES`、`VISIBILITY_STATUSES`、`DEFAULT_CAPABILITIES`；
  `parse_catalog`、`normalize_key`、`match_models`、`validate_visibility`、`load_visibility`、
  `save_visibility`、`resolve_request`、`select_model`、`mark_capability`、`show`、
  `load_catalog_file`、`run_models_command`、私有辅助 `_utf8`/`_now`/`_catalog_entries`/
  `_sorted_by_full`/`_capabilities_from`/`_document`/`_opencode_argv`/`_reject_non_finite`/
  `_reject_duplicate_keys`/`_emit`、CLI `main`。
- `tests/test_visibility_config.py`（新，59 条，unittest；目录夹具为 S01 实测 28 行原文 + 脏行/重复行）。
- `.opencode/commands/visibility.md`（新）：frontmatter `description/agent: build`；正文 4 步行为
  （先 `set`；needs-selection 用 `question` 让用户真实选择后 `select`，不得代选/编造；not-found 展示
  真实目录与错误、不虚构型号；成功后报告 provider/model、capabilities、作用域仅本项目并诚实说明
  下一次派发生效/若需重启则明说），以及 `show`/`mark` 用法。
- `docs/po-repair/baseline/s11/{test_visibility_config,test_all,check_selftest}.txt`（原始输出）。
- `docs/po-repair/PROGRESS.md`（本记录）。
- **未修改**：其他任何文件（`scripts/install.py`、`check.py`、既有 scripts/tests/SKILL/agent/沙箱均未触碰）；
  未 commit；未 reset/clean/stash 既有未提交修改。

### 实际签名（Python 3.10 标准库）

```python
VISIBILITY_SCHEMA = "workflow-visibility/1"
DEFAULT_REQUEST = "gpt 5.6 luna"
VISIBILITY_RELATIVE_PATH = ".opencode/mvp/visibility.json"
CAPABILITIES = ("image", "video", "audio")
VISIBILITY_STATUSES = ("unverified", "verified", "unavailable")
DEFAULT_CAPABILITIES = {"image": "unverified", "video": "unverified", "audio": "unverified"}

visibility_path(project: str | Path) -> Path
parse_catalog(text: Any) -> list[dict[str, str]]        # {provider_id, model_id, full}
normalize_key(value: Any) -> str
match_models(query: Any, catalog: Any) -> dict          # {mode, matches, query}
validate_visibility(data: Any) -> list[str]
load_visibility(path: str | Path) -> tuple[dict | None, list[str]]
save_visibility(path: str | Path, data: Any) -> list[str]
resolve_request(path: str | Path, request: Any, catalog: Any) -> dict
select_model(path: str | Path, full: Any) -> tuple[dict | None, list[str]]
mark_capability(path: str | Path, capability: Any, status: Any,
                evidence: Any = None) -> tuple[dict | None, list[str]]
show(path: str | Path) -> dict                          # selected|unconfigured|invalid
load_catalog_file(path: str | Path) -> tuple[str | None, list[str]]
run_models_command(timeout: float = 60.0) -> tuple[str | None, list[str]]
main(argv: list[str] | None = None) -> int
```

### 行为要点（实现决定，供 S12 复核）

1. **目录解析**：只接受裸 `provider/model` 行（`^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$`），
   空行/告警/坏行忽略，去重保首现；容忍 BOM。匹配前对 catalog 条目再做结构过滤（非 dict/缺字段/坏 full
   丢弃）；**绝不凭记忆补型号**。
2. **匹配**：含 `/` 且 normalize 后等于 full → `exact`；normalize 后等于 full 或 `model_id` → `unique`
   （多 provider 同 id → `ambiguous`）；否则查询 token 全落在 `full ∪ model_id` 的 token 集 → 0/1/多 =
   `none`/`unique`/`ambiguous`；matches 一律按 full 排序。实测：`gpt 5.6 luna`（无 `/`，normalize 等于
   model_id）→ unique `openai/gpt-5.6-luna`；`OpenAI/GPT 5.6 Luna` → exact；`deepseek` → ambiguous 4 个
   真实候选；`nothing-like-this` → none。`exact`/`unique` 在 `resolve_request` 中同等落盘。
3. **数据模型**：文档 `{schema:"workflow-visibility/1", updated_at, selection}`；selection
   `{requested_name, provider_id, model_id, status:"selected", capabilities{image/video/audio 三键必须齐},
   capability_evidence?}`。`validate_visibility` 严格校验（未知字段拒绝、capabilities 枚举、evidence
   非空字符串、updated_at 非空）。
4. **落盘**：同目录 `mkstemp` + `flush` + `fsync` + `os.replace`；父目录不存在/校验失败/替换失败都返回
   problems 且旧文件逐字节不变、临时文件清理。CLI 不自动创建 `.opencode/mvp/`（fail closed，留给 S12 决定
   是否自动 mkdir）。
5. **解析与持久化**：`not-found` 与 `needs-selection` 不写文件；`exact`/`unique` 写盘并**保留既有合法
   capabilities**，否则三键 `unverified`。重新 resolve 会丢弃 `capability_evidence`（旧模型证据不适用于
   新模型）；`mark` 只改目标项并写/删对应 evidence。
6. **mark 规则**：`verified` 必须带非空 evidence；`unverified`/`unavailable` 不要求并清除该项 evidence；
   capability/status 非法拒绝；文件缺失或损坏 fail closed。
7. **生产目录来源**：`run_models_command()` 用 argv 数组 `subprocess.run(capture_output=True, timeout=60)`，
   捕获 bytes 后按 utf-8 replace 解码；Windows 下 `shutil.which("opencode")` 命中 `.cmd/.bat` 时经
   `%COMSPEC% /c` 运行、`.ps1` 走 `powershell -File`；找不到/超时/非零退出给明确 stderr 文本，CLI 退出码 2。
   `--catalog-file` 完全离线（UTF-8 / UTF-8-SIG / UTF-16 BOM 均可读），供测试与离线快照。
8. **CLI**：argparse 子命令 `show`、`set [--request] [--catalog-file]`、`select --model`、
   `mark --capability --status [--evidence]`，均带 `--project`（默认 `.`）。`set` stdout 为 JSON
   （selected/needs-selection/not-found/error），退出码 selected=0、needs-selection=3、not-found=4、错误=2；
   `select`/`mark` 成功 stdout JSON、失败 stderr + 2；`show` invalid=2、unconfigured/selected=0。
   `_utf8()` 与其他脚本一致（stdout/stderr reconfigure）。
9. **作用域**：只写 `<project>/.opencode/mvp/visibility.json`，测试断言项目内仅生成该文件；不触碰主聊天
   模型与全局配置。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_visibility_config.py" -v` | 0 | Ran 59 tests — OK |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 808 tests in 29.7s — OK（skipped=3；749 → 808） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |
| 实机目录探针（本机 `opencode models`，只写临时项目） | 0 | 28 模型；`shutil.which` → `opencode.CMD` 经 cmd /c；`set --request "gpt 5.6 luna"` rc=0 落盘 `openai/gpt-5.6-luna` |

原始输出：`docs/po-repair/baseline/s11/*.txt`。新增 59 条覆盖：parse（真实 28 行/脏行/去重/CRLF+BOM/
非字符串）；normalize（大小写/空格/下划线/外层 `-`/非字符串）；match（默认请求、exact 含大小写空格变体、
model_id unique、deepseek×4 ambiguous、token 子集 unique/ambiguous、none 不编造、坏 catalog 条目）；
resolve（unique/default/exact 落盘字段与默认 capabilities、ambiguous/not-found 不写、重复 resolve 保留
capabilities、默认常量不被污染、保存失败 status=error）；select（合法落盘、非法保留旧文件、7 种非法形式）；
mark（无 evidence 拒绝且文件不变、只改目标项+evidence、unavailable 免 evidence、非法枚举、缺文件 fail
closed）；load/save（缺失、往返、BOM、坏 JSON、重复键、8 类结构问题、非法不落盘、父目录不创建、
`os.replace` 注入失败旧字节不变且无 tmp 残留）；show 三态；CLI（默认请求/显式请求/ambiguous=3/not-found=4/
目录文件缺失=2/脏目录行、select+show、select 非法=2、mark 无 evidence=2 与成功、项目内仅生成设置文件）。

### S20A 打包待办（新增）

- `scripts/install.py` 的 copy 清单必须加入 `scripts/visibility_config.py`（S12 观察派发读取的解析器；
  S01 冻结路径 `.opencode/mvp/visibility.json`），并加 install 测试断言；与已登记的
  `observation_contract.py`（S03）、`observation_candidate.py`（S06）、`runtime_state_policy.py`（S07）、
  `observation_results.py`（S08b）一并补。
- `.opencode/commands/visibility.md` **无需**单独登记：`install.py` 用 `sorted(source.glob("*.md"))`
  安装 commands 目录，命令文件自动随 commands 目录安装。
- install 后命令文档中的脚本路径为 `.opencode/workflow/scripts/visibility_config.py`（引擎布局），与既有
  命令/参考文档写法一致。

### 未完成 / 风险

1. 真实端到端模型派发仍 BLOCKED（S01 §5 路径 A，需重启 OpenCode 后由 S12/S21 验收）；S11 只交付项目设置
   解析、消歧、落盘与命令文档。
2. `set` 不自动创建 `.opencode/mvp/`：目录缺失时返回 error（退出码 2）；当前选择 fail closed，避免在未初始
   化项目里静默创建状态目录；S12 若需要可显式 mkdir 后再写。
3. capabilities 仅记录人工/探针的声明状态，不验真伪；`capability_evidence` 是自由文本引用，仅作追溯。
4. `set`/`select`/`mark` 无跨进程锁：`os.replace` 保证不产生半文件，但并发下后写覆盖先写（S12 若需并发再引入锁）。
5. 未做任何实机模型/浏览器验证（本步骤不涉及）；实机目录只读探针与临时项目写入已实测。

### 下一步 / 交接

- **S12**：插件/引擎按 S01 路径 A 读取 `.opencode/mvp/visibility.json`，把 `selection.provider_id/model_id`
  用于观察派发；读取先经 `load_visibility` 的 problems fail closed；需要消歧时复用 `match_models`/
  `resolve_request`，不自行编造型号。
- **命令消费者**：`/visibility` 按 `.opencode/commands/visibility.md`：先 `set`，needs-selection 用
  `question` 让用户真实选择后 `select --model <full>`，not-found 展示真实目录前若干项，成功后报告
  provider/model、capabilities 与作用域（仅本项目、仅 skill 流程内的观察模型选择）。
- **回归入口**：`tests/test_visibility_config.py`；离线目录快照：`docs/po-repair/baseline/s01/models-list.txt`
  （带 BOM 已实测可解析）。

## S12a — 派发模型证据（trace session model 导出/校验 + observation provenance 模型比对）

- **步骤**：S12a（`runtime_trace.py`：export 导出 session 模型 + `verify_native_trace` 与 store 交叉核对；
  `observation_results.py`：新增 `parse_session_model`/`model_mismatch_problems`，`provenance_problems`
  增加可选 `expected_model`；新增 `tests/test_observation_dispatch.py`）
- **状态**：PASS（实机端到端模型派发仍 BLOCKED-待重启，见 S12b）
- **前置步骤**：S11（模型选择设置）、S01（session store `model` 列实证）
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S11 相同）

### 修改/创建的文件

- `scripts/runtime_trace.py`（修改）：新增私有 `_parse_session_model(value)` 与
  `_session_model_column(con)`；export 的 session 条目新增 `"model"`（解析为
  `{provider_id, model_id, variant}`，不可解析/为空 → `null`）与 `"model_raw"`（原样字符串）；
  `verify_native_trace` 对带 `model` 键的条目与 store `session.model` 逐项（provider_id/model_id/
  variant）核对，缺失/空值/畸形均报问题（fail closed；旧 trace 无 `model` 键则保持旧行为）。
- `scripts/observation_results.py`（追加）：`parse_session_model`、`model_mismatch_problems`；
  `provenance_problems` 新增可选参数 `expected_model=None`（默认行为不变），提供时对匹配 session
  追加模型问题。
- `tests/test_observation_dispatch.py`（新，27 条）。
- `docs/po-repair/baseline/s12a/{test_observation_dispatch,test_runtime_evidence,test_all,check_selftest}.txt`
  （原始输出）。
- `docs/po-repair/PROGRESS.md`（本记录）。
- **未修改**：其他任何文件（`tests/test_runtime_evidence.py` 零改动）；未 commit；未 reset/clean/stash。

### 实际签名（Python 3.10 标准库）

```python
# runtime_trace.py（私有）
_parse_session_model(value: Any) -> dict | None          # {"provider_id","model_id","variant"}；失败 None
_session_model_column(con: sqlite3.Connection) -> str    # store 无 model 列时返回 "null as model"

# observation_results.py（公开）
parse_session_model(value: Any) -> Optional[dict]        # JSON 字符串或 dict；失败 None
model_mismatch_problems(session_entry: Any, expected_model: Any) -> list
provenance_problems(trace: Any, session_id: Any, skill: str = "product-observer",
                    expected_model: Any = None) -> list  # 向后兼容
```

模型规范：store 原样 `{"id":..., "providerID":..., "variant":...}` ↔ 归一
`{"provider_id":..., "model_id":..., "variant":...}`；`parse_session_model` 两种键名都接受。
`expected_model` 接受 `"provider/model"` 字符串或 `{"provider_id","model_id"}`（variant 不参与）。

### 关键实现决定（任务书未指定处，供 S12b 复核）

1. **store 无 `model` 列的兼容**：export/verify 先 `pragma table_info(session)`，缺列时用
   `null as model`，老库不报错；`model` 键存在时逐项核对，键不存在（旧/hand-written trace）跳过模型检查。
2. **verify 三种不一致都报错**：trace 有畸形模型；trace 无模型而 store 有；store 无模型而 trace 有。
   variant 参与 native verify（三项全等），不参与 `model_mismatch_problems`（豁免 variant）。
3. **`model_mismatch_problems` fail closed**：expected 无法解析（None/空/无 `/`/缺字段）→ 直接问题；
   session 无 model/不可解析 → `trace does not record a parsable model for session <id>`。
4. **向后兼容**：`provenance_problems(expected_model=None)` 输出与旧版逐字一致；session 缺失时只报
   会话问题，不叠加模型问题。未把 envelope.model 自动接入 adopt_result/adopt_review（S12b 接线）。
5. **解析一致性测试**：export 测试断言
   `entry["model"] == observation_results.parse_session_model(entry["model_raw"])`，防止两处解析漂移。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_dispatch.py" -v` | 0 | Ran 27 tests — OK |
| `python -m unittest discover -s tests -p "test_runtime_evidence.py" -v` | 0 | Ran 66 tests — OK |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 835 tests in 30.5s — OK（skipped=3；808 → 835） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

原始输出：`docs/po-repair/baseline/s12a/*.txt`。新增 27 条覆盖：parse（JSON 字符串/store 风格 dict/
归一 dict/缺 variant/空 variant/非法 JSON/null/缺字段/非字符串）；model_mismatch（string 与 dict 两种
expected、匹配、provider/model 各自不符含双方名字、variant 差异豁免、无 model 精确消息、expected
畸形 fail closed）；provenance+expected_model（匹配通过、dict 形式、不匹配、默认 None 旧行为、session
缺失只报会话、技能问题与模型问题并存）；export/verify（model+model_raw 落盘、解析一致性、匹配零问题、
篡改 variant/provider/model 报错、trace null 而 store 有值报错、store 空而 trace 有值报错、trace 畸形
报错、无 model 键旧 trace 不受影响）。

### 未完成 / 风险

1. **实机验证 BLOCKED-待重启**：本机 session store 已实证 `session.model` 列与派发模型（S01），但内置
   task 工具无法指定模型（S12b 用 OpenCode 插件解决）；S12a 只交付证据导出与比对，未做端到端派发验收。
2. `adopt_result`/`adopt_review` 尚未把控制器选择的模型传给 `provenance_problems`（S12b 接线时用
   `expected_model="provider/model"`；envelope 现为自由字符串 `model`，尚未约束格式）。
3. trace 的 `model` 来自 store 当时的行值，不是任务 part 的逐次快照：同一会话中途换模型只会看到最终值
   （S01 结论：子会话模型 = 派发时会话当前模型，可接受）。
4. export 的 `model_raw` 可能含非字符串（异常库），JSON 序列化为原值；解析失败统一 `null`。
5. 未做任何实机模型/浏览器验证（本步骤不涉及）。

### 下一步 / 交接（S12b）

- **S12b（插件与 Node 测试）**：写 OpenCode 插件让 `task` 派发可指定模型（读取
  `.opencode/mvp/visibility.json` 的选择），并补 Node 侧测试；实机端到端验证仍 BLOCKED-待重启。
- **接线点**：观察派发前用
  `provenance_problems(trace, observer_session_id, expected_model=<provider/model>)` 做 fail-closed
  provenance + 模型绑定；trace 由 `runtime_trace.py export` 生成（session 条目自带 `model`/`model_raw`）。
- **回归入口**：`tests/test_observation_dispatch.py`、`tests/test_runtime_evidence.py`。

## S12b — OpenCode 插件（visibility_dispatch / visibility_status）+ Node 测试

- **步骤**：S12b（新 `.opencode/plugins/workflow-visibility.js`；新 `tests/js/visibility-plugin.test.mjs`）
- **状态**：实现 PASS（Node 假客户端 23 条全绿）；**实机派发 BLOCKED-待重启 OpenCode；验收在 S21**
- **前置步骤**：S11（`.opencode/mvp/visibility.json`）、S01（SDK 派发路径实证）、S12a（模型证据导出/比对）
- **日期**：2026-09-21
- **运行时**：Node v24.19.0；`@opencode-ai/plugin` 1.18.25（`.opencode/node_modules` 可解析）

### 修改/创建的文件

- `.opencode/plugins/workflow-visibility.js`（新）
- `tests/js/visibility-plugin.test.mjs`（新，23 条）
- `docs/po-repair/baseline/s12b/{node-test-dir,node-test-glob,test_all,check_selftest}.txt`（原始输出）
- `docs/po-repair/PROGRESS.md`（本记录）、`docs/po-repair/HOST-COMPATIBILITY.md`（§8）
- **未修改**：`.opencode/package.json`、任何 Python 文件、其他任何文件；未 commit；未 reset/clean/stash。

### 实现要点

1. 头部注释写清依赖前提（`.opencode` 下需可解析 `@opencode-ai/plugin`，否则在 `.opencode` 内
   `npm install`）、**需重启 OpenCode 插件才生效**、本文件不修改任何全局配置。
2. 命名导出纯函数：`parseModelRef`（恰好一个 `/`、两侧非空，否则 `null`，含非字符串）；
   `resolveSelection`（显式模型优先；observer 用 `selection`，reviewer 用 `reviewer_selection`（仅
   undefined 时回退 `selection`）；`status != "selected"`、provider_id/model_id 缺失或非法、文件缺失/
   坏 JSON 一律返回 `{error}`，**不回落默认模型**）；`buildDispatchBody`；`extractOutput`；
   `AGENT_BY_ROLE`。
3. 工具 `visibility_dispatch`：`context.directory`（缺省插件 `directory`）解析模型，失败即
   `throw new Error("visibility_dispatch: ...")`；`session_id` 缺省时
   `client.session.create({body:{parentID: context.sessionID, title}})`，再
   `client.session.prompt({path:{sessionID}, body:{agent, model, parts:[{type:"text",text:prompt}]}})`；
   返回 `{title, output, metadata:{session_id, provider_id, model_id, agent}}`。SDK `{data,error}`
   形态自动解包（host 返回 error 或 Promise 拒绝都转成 `visibility_dispatch: ...` 抛出）。
4. 工具 `visibility_status`：读同一文件并 `JSON.stringify(selection, null, 2)`；文件缺失输出
   `unconfigured:` 前缀、坏 JSON 输出 `unreadable:` 前缀，均不 throw；可选 `role`。
5. Node 测试用假 client 断言：`parentID` 为 `context.sessionID`；prompt 的 `agent/model/parts`
   逐字段；resume 不调 `create`；选择缺失时 `create`/`prompt` 零调用；prompt 异常与 `{data,error}`
   错误都传播；status 正常/缺失两态。

### 实际签名（JS / ESM，非 Python）

```js
export function parseModelRef(value) -> {providerID, modelID} | null
export function resolveSelection(directory, role, explicitModel) -> {providerID, modelID} | {error}
export function buildDispatchBody({agent, model, prompt}) -> {agent, model, parts:[{type,text}]}
export function extractOutput(parts) -> string
export const ROLES = ["product-observer", "reviewer"]
export const VISIBILITY_RELATIVE_PATH = ".opencode/mvp/visibility.json"
export const AGENT_BY_ROLE = {"product-observer": "mvp-product-observer", "reviewer": "mvp-reviewer"}
export default async function workflowVisibilityPlugin({client, directory})
  -> {tool: {visibility_dispatch, visibility_status}}   // OpenCode plugins/ 默认导出
```

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `node --test tests/js/` | 1 | 宿主语义限制：Node 24 把位置参数当 glob（不展开目录），报 `Cannot find module ...\tests\js`；原始输出见 `baseline/s12b/node-test-dir.txt` |
| `node --test "tests/js/**/*.test.mjs"`（本机等效命令） | 0 | 23 tests — 23 pass / 0 fail（`baseline/s12b/node-test-glob.txt`） |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 835 tests in 30.4s — OK（skipped=3；未动 Python） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

### S20A 打包待办（追加）

- 打包/安装清单必须包含 `.opencode/plugins/workflow-visibility.js`，并提示依赖前提：目标项目
  `.opencode` 下需可解析 `@opencode-ai/plugin`（存在 `node_modules` 或先 `npm install`；本仓库
  `.opencode/package.json` 固定 `@opencode-ai/plugin: 1.18.25`）；安装后**需重启 OpenCode** 加载插件。
- 该插件不是 Python 工作流脚本，不进入 `scripts/install.py` 的 copy 清单；若安装脚本同步
  `.opencode/` 子树，必须保留 `plugins/workflow-visibility.js`，且不得删除 `.opencode/package.json`
  与 `.opencode/node_modules`（插件的模块解析前提）。

### 未完成 / 风险

1. **实机派发 BLOCKED-待重启 OpenCode；验收在 S21**：本步只交付实现与假客户端测试，未在真实宿主
   创建子会话，未核对子会话 `session.model` 与 `selection` 的一致性。
2. `node --test tests/js/` 在 Node v24.19.0 不可用（位置参数按 glob 解释，目录不会递归展开）；
   文档/脚本统一改用 `node --test "tests/js/**/*.test.mjs"`。
3. 插件仅在项目级 `.opencode/plugins/` 生效，且不修改全局配置；`model` 显式覆盖只作用于单次派发。
4. 模型能力（图片/音频等）仍以 S11 的 capabilities 声明为准，实机能力验收在 S16/S17。

## S13 — 席位权限边界（observer bash 命令模式 + reviewer 声明 + 权限回归测试）

- **步骤**：S13（改 `.opencode/agents/mvp-product-observer.md`、`.opencode/agents/mvp-reviewer.md`、`product-observer/references/observation-protocol.md`（仅 Trust Boundary 段）；新 `tests/test_observation_permissions.py`）
- **状态**：实现 PASS（新 9 条 + 全量 844 全绿）；**实机权限强制 BLOCKED-待重启 OpenCode；验收在 S21**
- **前置步骤**：S12b（插件）、S01（SDK/权限路径实证）
- **日期**：2026-09-21
- **归因修正**：P1-3 的“Write 覆写证据”实际发生在 CLI 回落到 build agent 之后，**不能**证明 `edit: deny` 失效；因此未引入未经宿主验证的 `write: deny` 键（SDK 暴露的写权限键是 `edit`）。

### 修改/创建的文件

- `.opencode/agents/mvp-product-observer.md`：`bash: allow` → 命令模式对象（对象形式；宽在前、窄在后）；Rules 增补两层边界
- `.opencode/agents/mvp-reviewer.md`：Rules 增补 read-then-rewrite 禁令（`edit/bash/task: deny` 权限键本已齐备，未动）
- `product-observer/references/observation-protocol.md`：Trust Boundary 段补两层说明
- `tests/test_observation_permissions.py`（新，9 条）
- `docs/po-repair/baseline/s13/*.txt`（原始输出）、`docs/po-repair/PROGRESS.md`（本记录）
- **未修改**：`tests/test_subagent_orchestration.py`（bash 结构变化不影响其断言，无需适配）；其他任何文件；未 commit；未 reset/clean/stash。

### 实现要点

1. observer bash 权限对象：顶层 `"*": allow` 在前，13 条 deny 模式在后（OpenCode 按最后的匹配规则生效；键含 `*` 全部加引号）：
   `"> *"`、`">>*"`、`Out-File`、`Set-Content`、`Add-Content`、`New-Item`、`Remove-Item`、
   `rm `、`del `、`move `、`copy `、`python -c`、`node -e`。只阻挡 shell 重定向/写文件命令；
   产品入口、agent-browser、截图等正常观测命令仍在 allow 范围内（这些工具自己写文件，不经 shell 重定向）。
2. Rules 明确：即使宿主权限层未覆盖到某命令，也不得写产品源码、goal、gate、其他阶段证据；
   `edit: deny` 是工具层边界，bash 模式是命令层边界，两者都不是完整沙箱；评审会核对证据路径。
3. reviewer Rules：不得读取后改写任何被评文件（经编辑工具、shell 重定向或写文件命令均属评审缺陷）。
4. 协议 Trust Boundary：主语权限（edit deny + bash 模式拒绝）由 agent 配置表达；prompt 级范围与宿主权限是两层，
   不能互相替代；控制器不得给 observer 发放任意 shell 写权限。
5. 测试用最小 frontmatter 解析器（首个 `---` 块、`key: value` + 一层缩进映射、保序、去引号；不引入第三方 yaml）。
   断言：observer deny 模式全部位于顶层 allow 之后（顺序断言）、reviewer `edit/bash/task: deny`；
   两文件均不含 `write: deny`/`write: allow`（未验证权限键显式回归）；protocol 含“两层”说明关键字。

### 实际签名（测试辅助，非产品 API）

```python
parse_frontmatter(text: str) -> dict
    # tests/test_observation_permissions.py
    # 返回保序 dict，例：{"permission": {"edit": "deny", "task": "deny",
    #   "bash": {"*": "allow", "*> *": "deny", ...}}}
```

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_permissions.py" -v` | 0 | Ran 9 tests — OK |
| `python -m unittest discover -s tests -p "test_subagent_orchestration.py" -v` | 0 | Ran 9 tests — OK（未改文件） |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 844 tests in 35.9s — OK（skipped=3；835 → 844） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

原始输出：`docs/po-repair/baseline/s13/{test_observation_permissions,test_subagent_orchestration,test_all,check_selftest}.txt`。

### S21 实机权限验收清单（重启 OpenCode 后，在新项目执行）

1. observer 用 edit 工具写 `.opencode/mvp/**` → 必须被拒（工具层）。
2. observer 执行 `echo x > app/note.txt`、`echo x >> app/note.txt`（以及 Out-File / Set-Content / New-Item /
   Remove-Item / rm / del / move / copy / `python -c` / `node -e` 模式）→ 必须被拒（命令层）。
3. observer 执行 `agent-browser` 截图与产品入口命令 → 必须可用；正常 discover/compare 观测与证据落盘不受影响。
4. reviewer 任意 bash 命令 → 必须被拒（`bash: deny`）。
5. 若任一拒绝未生效：记录宿主版本、请求形态与命中模式，回填 `HOST-COMPATIBILITY.md`，并核对是否在权限对象中
   出现未知键或匹配顺序语义变化。

### 未完成 / 风险

1. **实机权限强制 BLOCKED-待重启 OpenCode；验收在 S21**：本步只交付声明层与静态回归，未在真实宿主触发拒绝对话框。
2. bash 模式是命令层文本匹配，不是完整沙箱：等价的写命令可以绕过；以评审证据路径核对 + prompt 级规则兜底。
3. 子串模式可能误伤（如 `"*rm *"` 命中含 “rm ” 的文案命令）；观测命令若被误拒，改用不经 shell 的替代命令
   并在 round 记录中说明。

## S14 · 观察运行时的进程/编码边界（argv 直调 + 字节捕获 + 进程树清理）

- **步骤**：S14（新 `scripts/observation_process.py`、新 `tests/test_observation_process.py`；`docs/po-repair/**`）
- **状态**：实现 PASS（新 20 条 + 全量 864 全绿）；**实机 agent-browser/CLI 链路验收在 S21**
- **前置步骤**：S13（席位权限边界）、S01（CLI 实测）
- **日期**：2026-09-21
- **归因**：P2-15（孤儿进程树与目录锁）、P2-16（Windows 编码三连）、P2-17（opencode/agent-browser CLI 摩擦）。
  本步只交付运行时边界原语；不宣称宿主缺陷已修复，实机观测链路仍以 S21 验收为准。

### 修改/创建的文件

- `scripts/observation_process.py`（新）：观察运行时的进程/编码边界（6 个公开函数 + 内部辅助）
- `tests/test_observation_process.py`（新，20 条）：成功/非零退出/超时杀树/cwd/非 UTF-8 字节/capture 字节与
  sha256/kill 返回 bool/close 参数与 close-all 门禁/目录锁退避
- `docs/po-repair/baseline/s14/{test_observation_process,test_all,check_selftest}.txt`（原始输出）、
  `docs/po-repair/PROGRESS.md`（本记录）
- **未修改**：`scripts/check.py`（仅参考 L1213-1331 的 Popen/字节捕获/taskkill 模式，未动一行）、其他任何文件；
  未 commit；未 reset/clean/stash。

### 实现要点

1. `run_process`：`Popen(argv, shell=False, stdout/stderr=PIPE, env=...)`；Windows 加
   `CREATE_NEW_PROCESS_GROUP`，POSIX 加 `start_new_session=True`。正常路径 `communicate(timeout)`；
   超时先 `kill_process_tree(pid)`，再 `communicate(timeout=5)` 收尾；仍超时则放弃管道（Windows 上
   不 `close` 可能死锁的流，仅 POSIX 关闭）。返回 `timed_out=True`、`exit_code=None`。
   `argv` 原样记录（不拼接、不经 shell、调用方脱敏）；文件不存在/Popen OSError → `exit_code=None` +
   `error` 键，绝不抛异常。返回键：`argv/cwd/exit_code/timed_out/elapsed_seconds/stdout_bytes/stderr_bytes/cleanup`。
2. `text_of`：`decode("utf-8", errors="replace")`，仅用于展示/诊断；非 UTF-8 字节不会抛。
3. `run_process_capture`：调 `run_process` 后把**原始字节**写入 `stdout_path`/`stderr_path`
   （覆盖写、父目录自动创建）；返回同套元数据但**不含 bytes 本体**，另含路径、`sha256`、字节数与
   `stdout_text/stderr_text`。写盘失败不抛，记入 `error`，另一路继续写。
4. `kill_process_tree`：Windows `taskkill /PID <pid> /T /F`（argv 数组、`subprocess.run`），
   POSIX `os.killpg(SIGKILL)`；任何 OSError/超时 → `False`。
5. `session_cleanup`：优先 `[*base_argv, "--session", sid, "close"]`；仅当失败且
   `allow_global_cleanup=True` 才追加**一次** `[*base_argv, "close-all"]`；默认 False 时全局清理绝不执行
   （保护用户其他会话）。返回 `session_closed/global_cleanup_used/details`。
6. `cleanup_directory`：`shutil.rmtree`；OSError 时尝试**一次** `os.rename` 到
   `<name>.orphaned-<YYYYmmdd-HHMMSS>`；都失败 → `{"removed": False, "locked": True, "detail": ...,
   "renamed_to": None}`，不重试、不循环改名；成功或路径不存在 → `removed=True`。
7. 模块 docstring 声明：本模块是观察运行时的进程/编码边界；不依赖 `opencode session list --format json`；
   agent-browser 一类 CLI 必须 argv 直调，禁止经 PowerShell 输出管道（`|`/`2>&1`）。

### 实际签名（产品 API）

```python
run_process(argv: Sequence, cwd, timeout: float,
            env: Mapping[str, str] | None = None) -> dict
text_of(raw: bytes) -> str
run_process_capture(argv: Sequence, cwd, timeout: float, stdout_path, stderr_path,
                    env: Mapping[str, str] | None = None) -> dict
kill_process_tree(pid: int) -> bool
session_cleanup(base_argv: Sequence, session_id: str, *,
                allow_global_cleanup: bool = False, timeout: float = 30) -> dict
cleanup_directory(path) -> dict
```

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_process.py" -v` | 0 | Ran 20 tests in 3.599s — OK |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 864 tests in 33.791s — OK（skipped=3；844 → 864） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

原始输出：`docs/po-repair/baseline/s14/{test_observation_process,test_all,check_selftest}.txt`。

### S20A 打包待办（追加）

- `scripts/install.py` 的 `copy_jobs`（`check.py`/`product_observation.py` 同段）必须追加
  `(repo/"scripts"/"observation_process.py", engine_root/"scripts"/"observation_process.py", "scripts/observation_process.py")`；
  该清单当前仍缺 `observation_contract.py`、`observation_candidate.py`、`observation_results.py`、
  `runtime_state_policy.py`、`visibility_config.py`（S03/S04/S08a/S13 已登记），S20A 一并补齐。
- `tests/test_install.py` 若含引擎脚本清单/hash 断言，S20A 同步加断言（本步未改 install.py 与 test_install.py）。

### 未完成 / 风险

1. **实机观测链路验收在 S21**：本步只有实现与本地回归，未在真实产品项目跑 agent-browser/CLI；
   超时杀树的 Windows 行为用本机 `taskkill` 验证，尚未覆盖杀毒软件/权限受限环境。
2. `kill_process_tree` 依赖 `taskkill`/`killpg`：一旦失败（返回 False）`run_process` 只再等 5 秒即放弃管道，
   可能残留无法杀死的外部进程；调用方必须依据 `cleanup.kill_ok` 记录并升级处理。
3. 编码边界只保证“不抛异常 + 字节原样”：证据消费方若需要文本，必须记录文本来自 `errors="replace"`，
   不能把替换字符当作产品真实输出。
4. `cleanup_directory` 的改名退避只做一次：连续锁定时会留下带 `.orphaned-<ts>` 的目录，需人工清理；
   时间戳精度到秒，同一秒内重复调用可能因重名而直接进入 locked。
5. 本步不修改权限/调度/证据模块：`observation_process` 尚未接线到 `product_observation.py`，
   接线与端到端观测作为后续步骤（S15/S16/S17）。

## S15 — 观察后端选择与短旅程批处理（preflight 跳过计划 / backend 选择 / argv 构造 / run_step_sequence）

- **步骤**：S15（新 `scripts/observation_backend.py`、新 `tests/test_observation_backend.py`；`docs/po-repair/**`）
- **状态**：实现 PASS（新 49 条 + 全量 913 全绿）；**实机 agent-browser/playwright 链路验收在 S21**
- **前置步骤**：S14（`observation_process.run_process` 边界）、S10（packet.preflight 结构）
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S14 相同）
- **范围**：只交付 controller 侧规划/构造/批处理原语；不修改 `workflow_packets.py`、gate/adoption/install、
  其他 tests/SKILL；文档接线（agent/reference 引用本模块）留给 S19。

### 创建的文件（未修改允许清单外的任何文件）

- `scripts/observation_backend.py`（新）：`preflight_skip_plan`、`choose_backend`、
  `agent_browser_argv`、`playwright_cli_argv`、`run_step_sequence` + 私有 `_plan_item`/`_host_cover`/
  `_build_argv`/`_normalize_steps`/`_run_one`/`_result_ok`/`_nonempty`；常量 `BACKENDS`、
  `_SKIP_ITEMS`、`_ITEM_FIELDS`、`_AGENT_ACTIONS`、`_PLAYWRIGHT_ACTIONS`、`_WAIT_KEYS`。
- `tests/test_observation_backend.py`（新，49 条）：preflight 计划 10、backend 选择 8、argv 构造 16、
  批处理 15；全部使用假 runner/假 clock，不启动任何进程或浏览器。
- `docs/po-repair/baseline/s15/{test_observation_backend,test_all,check_selftest}.txt`（原始输出）。
- `docs/po-repair/PROGRESS.md`（本记录）。
- **未修改**：`scripts/install.py`、`scripts/workflow_packets.py`、`scripts/check.py`、其他 scripts/tests/
  SKILL/agent/沙箱；未 commit；未 reset/clean/stash。

### 实际签名（Python 3.10 标准库）

```python
BACKENDS = ("agent-browser", "playwright-cli")

preflight_skip_plan(preflight: Any, context: Any) -> dict
choose_backend(preflight: Any, preferred: Optional[str] = None) -> dict
agent_browser_argv(session_id: Any, action: Any, **params: Any) -> list
playwright_cli_argv(session_id: Any, action: Any, **params: Any) -> list
run_step_sequence(steps: Any,
                  runner: Callable[[Sequence[str], Optional[float]], Any], *,
                  deadline_seconds: Optional[float] = None,
                  clock: Optional[Callable[[], float]] = None) -> dict
```

### 关键实现决定（供 S19/S21 复核）

1. **preflight 跳过计划按“覆盖项实际记录的身份字段”比对**：host 可用 `host_id`/`host`，也可仅用
   `provider_id`/`model_id` 匹配（与 model 同口径）；candidate/session 用各自 id。cover 中“有记录的字段”
   必须全部在 context 中存在且相等，否则该项 `skip=False`；没有任何可比字段也 fail closed
   （“controller-verified”字样不构成豁免）。preflight 为 None/非 dict → 四项统一
   `{"skip": False, "reason": "no preflight"}`。
2. **backend 决策表（不虚构、不回落仅在任务书列明处）**：非法 preferred → `backend=None`；
   host `status=="unavailable"` → None；preferred 合法且 host passed 且（cover 未记 backend 或与
   preferred 相等）→ `{backend: preferred, verified: True}`；cover 记录的 backend 与 preferred 冲突 →
   None；无 preferred 且 host passed 且 cover 记录的 backend 在集合内 → 采用该 backend（verified）；
   其余（无 preflight / host 未 passed）→ 默认 `{backend: "agent-browser", verified: False,
   reason: "default, unverified preflight"}`。注意：preferred 合法但 host 未通过时按任务书字面走默认
   分支（不是 None）；非法 preferred 与 unavailable 才是 None。
3. **argv 动作映射**（`--filename` 用于 snapshot/screenshot；`evidence_dir` 只做包含校验、不进入 argv）：
   `open/goto <url>`、`click <target>`、`type <target> <text>`、`press <key>`、
   `wait` 恰需 `load|url|text|fn` 之一 → `--<mode> <value>`、`console/errors/close` 无参；
   每个值都是独立 argv 元素（含空格/`&` 的文本不拆分、不拼接 shell 字符串）。
   screenshot 必须给 `filename` 且 resolve 后位于 `evidence_dir` 内（`Path.is_relative_to`，`..`/绝对越界
   均 ValueError）；snapshot 在提供 filename 时同规则；playwright 基础形态
   `["playwright-cli", "-s=" + session_id, ...]` 且无 `errors` 动作。
4. **run_step_sequence 状态机**：成功 = runner 返回 dict 且 `exit_code == 0`、无 `timed_out`、无 `error`；
   首个失败/超时/异常/`error` 立即停止并记入 `failed_step`，后续 id 保留在 `remaining`（不含失败步）；
   runner 异常被捕获为 `{"exit_code": None, "timed_out": False, "error": "Type: text"}`，绝不外抛；
   runner 返回非 dict 时包成 `{"error": "runner returned a non-dict result", "value": <原值>}`，
   字节/文本原样保留在 step 的 `result`。`deadline_seconds` 在每步执行前用 `clock()`（默认
   `time.monotonic`）检查 `now - started >= deadline`，超出 → `status="budget-exhausted"`、无
   `failed_step`、未执行步全部在 `remaining`；`first_action_at` 为第一步执行前的 clock 读数（未执行过为
   None）；`elapsed_seconds` 四舍五入 6 位；`evidence_refs` 收集已执行步（含失败步）的非空 evidence。
   非法 steps（非 list/缺 id/空 argv/非字符串元素/空 evidence/非正 timeout）直接 `ValueError`。
5. **无浏览器依赖**：模块只构造 argv 并通过注入的 runner 执行；生产接线用
   `observation_process.run_process`（或 `run_process_capture`），本模块自身不 spawn 进程、不读产品。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_backend.py" -v` | 0 | Ran 49 tests in 0.012s — OK |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 913 tests in 37.647s — OK（skipped=3；864 → 913） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

原始输出：`docs/po-repair/baseline/s15/`；未删除/放松任何既有断言。

### S20A 打包待办（追加）

- `scripts/install.py` 的 `copy_jobs` 必须追加
  `(repo/"scripts"/"observation_backend.py", engine_root/"scripts"/"observation_backend.py",
  "scripts/observation_backend.py")`，与已登记的 `observation_contract.py`、`observation_candidate.py`、
  `runtime_state_policy.py`、`observation_results.py`、`visibility_config.py`、`observation_process.py`
  一并补齐；`tests/test_install.py` 若含脚本清单断言，S20A 同步加。
- 本模块生产接线需要 `observation_process.py`；打包缺任一模块都会使观察派发的批次执行失败（fail closed）。

### 未完成 / 风险

1. **实机链路验收在 S21**：本步只有假 runner/假 clock 回归；agent-browser/playwright-cli 真实参数
   （`--filename`/`-s=` 等）与 `agent-browser wait` 子形态的兼容性需实机核对，必要时仅调整
   `_build_argv` 映射（API 不变）。
2. `choose_backend` 的 preferred+未通过 preflight 走默认分支是任务书字面实现；若后续希望更严格的
   “不回落”，需要任务书明确后再收紧（当前有测试锁定该行为）。
3. `run_step_sequence` 只做整批 deadline，不按单步预算拆分；单步 `timeout` 传给 runner，超时杀树由
   `observation_process` 承担。
4. `preflight_skip_plan` 只做身份一致性判断，不校验 preflight 文件 sha/新鲜度（packet 层 S10 已做）；
   真实探针产出 `preflight.json` 的执行仍属 S16/S21。
5. 未修改 `workflow_packets.py`（任务书禁止）：packet 已嵌 `preflight`，但 controller 如何消费
   `preflight_skip_plan`/`run_step_sequence` 的文档接线留给 S19。
6. 未做任何实机模型/浏览器验证（本步骤不涉及）。

### 下一步 / 交接

- **S19 文档接线**：observer/controller 参考文档引用 `scripts/observation_backend.py` 的批次契约
  （短旅程、中间证据保留、异常停止交回）；不要为 observer 预写固定探测路线。
- **S16/S21**：preflight 探针与实机派发按本模块 API 消费：`preflight_skip_plan(packet["preflight"],
  context)` → `choose_backend(...)` → `agent_browser_argv(...)`/`playwright_cli_argv(...)` →
  `run_step_sequence(steps, runner=wrapped_run_process, deadline_seconds=...)`。
- **回归入口**：`tests/test_observation_backend.py`。

## S16 — 视觉适配面、能力状态与感知证据规则（离线）

- **步骤**：S16（新 `scripts/observation_vision.py`、新 `tests/test_observation_vision.py`；`docs/po-repair/**`）
- **状态**：实现 PASS（新 76 条 + 全量 989 全绿）；**真实读图/桌面操作/模型感知验证 BLOCKED-待环境，验收在 S21**
- **前置步骤**：S15（批次执行与 backend 选择）、S11（capabilities 声明状态）、S01 §4（CLI 图片链路实测参考）
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S15 相同）
- **范围**：只做可离线验证的适配器描述、能力状态四态、host requirements、感知记录/主张校验、
  颜色探针造图与派发模式；不修改 observation_backend/process/packets/gate/adoption/install、
  其他 tests/SKILL/沙箱；未 commit；未 reset/clean/stash 既有未提交修改。

### 创建的文件

- `scripts/observation_vision.py`（新，纯标准库：hashlib/os/random/re/shutil/struct/zlib/pathlib）：
  `adapter_status`、`host_requirements`、`build_perception_record`、`validate_perception_record`、
  `perception_claim_problems`、`make_color_probe`、`dispatch_mode` + 私有辅助；
  常量 `VISION_CAPABILITIES`/`STATUSES`/`PERCEPTION_SCHEMA`/`PROBE_COLORS`/`PNG_SIGNATURE`/
  `DEFAULT_PROBE_SIZE`/`ADAPTERS`/`DIRECT_MULTIMODAL`/`MIDSCENE`/`UI_TARS`。
- `tests/test_observation_vision.py`（新，76 条）：常量与适配器数据 5、adapter_status 13、
  host_requirements 12、感知记录 7、感知主张 9、颜色探针 10、dispatch_mode 20；
  全部离线（假 which、注入 rng、临时目录），无 GUI/网络/模型。
- `docs/po-repair/baseline/s16/{test_observation_vision,test_all,check_selftest}.txt`（原始输出）。
- `docs/po-repair/PROGRESS.md`（本记录）、`docs/po-repair/HOST-COMPATIBILITY.md`（§8.5 追加感知探针项）。

### 实际签名

```python
VISION_CAPABILITIES = ("image_read", "visual_grounding", "desktop_control")
STATUSES = ("verified", "implemented-not-verified", "unavailable", "failed")
PERCEPTION_SCHEMA = "perception-probe/1"
PROBE_COLORS = ("red", "green", "blue", "yellow", "cyan", "magenta")
DEFAULT_PROBE_SIZE = 48
DIRECT_MULTIMODAL / MIDSCENE / UI_TARS / ADAPTERS  # 纯数据，见模块

adapter_status(adapter: Any, evidence: Any) -> dict
host_requirements(adapter: Any, env: Any = None,
                  which: Optional[Callable[[str], Optional[str]]] = None) -> dict
build_perception_record(image_path, sha256, described_by, description,
                        session_id, created_at) -> dict
validate_perception_record(record: Any) -> list
perception_claim_problems(record: Any, evidence_root: Any) -> list
make_color_probe(path: Any, color: Any = None, rng: Any = None,
                 size: int = DEFAULT_PROBE_SIZE) -> dict
dispatch_mode(observer_capabilities: Any, product_channels: Any,
              available_adapters: Any = None) -> dict
```

### 关键实现决定（供 S19/S21 复核）

1. `adapter_status` 四态按任务书顺序：非空 `unavailable_reason` → unavailable；needs 非空且
   全部探测恰为 `"passed"` → verified；任一 `"failed"` → failed；否则 implemented-not-verified。
   `status_hint` 只回显、绝不升级状态；needs 非 list/为空时不允许 verified（fail closed）；
   缺 evidence/任意畸形输入不抛异常并保持 implemented-not-verified。
2. 结果含 `needs/passed/failed/missing/unavailable_reason/status_hint/host/reason` 供审计；
   `host` 不参与判定（规则只看 probes 与 unavailable_reason）。
3. `host_requirements` 分类：`MIDSCENE_*` → env 非空字符串；含 `/` 或单 token 包名 → which
   （`@midscene/web or CLI` 取 slash 前 `@midscene` → 候选 `midscene`；`UI-TARS desktop/operator`
   → `ui-tars`）；其余（`network egress...`、`observer model with image attachment support`、
   `vision-language model`）→ unverifiable，绝不猜通过。`satisfied` 仅在 requires 为 list 且
   missing 与 unverifiable 均空时为 True；which 为可调用对象，异常/非可调用 fail closed。
4. 感知记录校验只看记录完整性（schema、image.path 非空、sha 64hex（大小写均可）、
   `described_by/description/session_id/created_at` 非空）；**不检查文件存在**——文件存在本身
   不构成感知。`perception_claim_problems` 才要求：图片在 `evidence_root` 内（相对路径按根解析，
   绝对路径允许但 resolve 后必须仍在根内）、存在、且 sha256 与实算一致（大小写不敏感比较）。
5. `make_color_probe` 只用 struct+zlib 手写 48×48 RGB8 PNG（IHDR/IDAT/IEND，单 IDAT、
   每行 filter 0，CRC32 自校验），`rng` 注入 `random.Random(n)` 可复现；返回
   `{path, color, sha256, size}`。用途：S21 让被选模型回答主色以证明图片真实送达；
   本函数只造图与记录期望色，不发任何请求。
6. `dispatch_mode`：结构化通道（structured/text/dom/console/api/json/html/cli）→ structured；
   visual/canvas 需 image_read；desktop 需 image_read+visual_grounding+desktop_control；
   audio/video 归 S17（gap 且 blocked）；observer 能力必须严格 `is True`；engine 适配器仅
   midscene/ui-tars，且仅当 `available_adapters` 中值为 True / `"verified"` /
   `{"status":"verified"}` 才补能力（direct-multimodal 不作为引擎适配器）；
   全部 needs 由 observer 覆盖 → direct-multimodal；部分由适配器覆盖 → hybrid；
   unknown 通道/声画通道/未覆盖 needs/畸形通道 → blocked 且 gaps 逐条列明。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_vision.py" -v` | 0 | Ran 76 tests — OK（0 fail/error） |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 989 tests in 37.989s — OK（skipped=3；913 → 989） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

原始输出：`docs/po-repair/baseline/s16/`；未删除/放松任何既有断言。

### S20A 打包待办（追加）

- 若 S19/控制器接线消费本模块（建议 observer/controller 读取适配面与 `dispatch_mode`），
  `scripts/install.py` 的 copy 清单需追加 `scripts/observation_vision.py`；与已登记清单
  （observation_contract/candidate/results、runtime_state_policy、visibility_config、
  observation_process、observation_backend）一并补齐，并加 install 断言。

### 未完成 / 风险

1. **真实读图/桌面操作验证 BLOCKED-待环境（S21）**：本步所有状态与通过都是纯函数对注入
   证据/假 which 的判定；没有真实模型读图、midscene/UI-TARS 安装探测、desktop_control 实操。
   `adapter_status` 的 verified 只代表“证据声称探测通过”，证据真实性由 S21 实机探针给出；
   不得用 adapter 数据或 `status_hint` 冒充已验收。
2. 感知记录目前只到“记录↔文件 sha 一致”；描述是否真由被派发模型给出（prompt/回复绑定、
   session/模型一致性）依赖 S12a provenance + S21 的 `make_color_probe` 期望色比对。
3. audio/video 按任务书归 S17，本步只给 gap/blocked，不实现任何声画能力。
4. `host_requirements` 的 which 候选提取依赖 slash/单 token 形态；新的适配器若用自然语言描述
   命令会落在 unverifiable（fail closed，不会误判通过）。
5. `observation_vision` 尚未接线到 product_observation/check/workflow_packets/install
   （S19/S20 范围）。

### 下一步

**S17**（音频/视频能力面与感知；消费本步 `dispatch_mode` 的 S17 gaps），S19 文档接线；
S21 重启后按清单实机验收（含 `make_color_probe` 感知探针，见 HOST-COMPATIBILITY §8.5-7）。

## S17 — 媒体采集工具与判定规则（离线）：ffmpeg/ffprobe argv、probe 解析、media record、capture chain 与静音主张

- **步骤**：S17（新 `scripts/observation_media.py`、新 `tests/test_observation_media.py`；`docs/po-repair/**`）
- **状态**：实现 PASS（新 73 条 + 全量 1062 全绿）；**真实 ffmpeg/ffprobe 执行与真实音频模型验证
  BLOCKED-待环境，验收在 S21**
- **前置步骤**：S16（视觉适配面；`dispatch_mode` 的 audio/video gaps）、S14（`observation_process` 进程边界）
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S16 相同）
- **范围**：只做可离线测试的采集工具与判定规则；不修改 `observation_backend/process/packets/
  contract/gate/adoption/install`、其他 tests/SKILL/沙箱；未 commit；未 reset/clean/stash。

### 创建的文件

- `scripts/observation_media.py`（新，纯标准库 json/math/os/re）：`ffprobe_argv`、`extract_audio_argv`、
  `extract_frames_argv`、`clip_argv`、`process_runner`、`probe_media`、`build_media_record`、
  `validate_media_record`、`capture_chain_verdict`、`silence_claim_problems`、`media_endpoint` +
  私有辅助；常量 `MEDIA_RECORD_SCHEMA`/`MEDIA_KINDS`/`AUDIO_KINDS`/`AUDIO_SOURCES`/`SIGNALS`/
  `CAPTURE_VERDICTS`/`MEDIA_MODEL_ENV`/`PROBE_TIMEOUT_SECONDS`。模块 docstring 明确：FFmpeg/ffprobe
  只负责采集/处理，语义判断由实际支持的模型完成，`record start/stop` 产物不自动等于有音频。
- `tests/test_observation_media.py`（新，73 条）：常量 3、argv 13、probe_media 20、media record 15、
  capture chain 11、silence claim 8、media endpoint 5；全部离线（假 runner，无进程/网络/模型）。
- `docs/po-repair/baseline/s17/{test_observation_media,test_all,check_selftest}.txt`（原始输出）。
- `docs/po-repair/PROGRESS.md`（本记录）。

### 实际签名（Python 3.10 标准库）

```python
MEDIA_RECORD_SCHEMA = "media-record/1"
MEDIA_KINDS = ("native-video", "frame-sampled", "audio-track", "audio-transcript", "audio-caption")
AUDIO_SOURCES = ("capture", "extract")
SIGNALS = ("present", "silent", "unknown")
CAPTURE_VERDICTS = ("sound-present", "product-silent", "capture-unverified")
MEDIA_MODEL_ENV = ("MEDIA_MODEL_BASE_URL", "MEDIA_MODEL_API_KEY", "MEDIA_MODEL_NAME")
PROBE_TIMEOUT_SECONDS = 30.0

ffprobe_argv(path) -> list
extract_audio_argv(video, out) -> list
extract_frames_argv(video, out_pattern, interval=None, fps=None) -> list
clip_argv(video, start, end, out) -> list
process_runner(argv, timeout) -> dict        # 生产包装 observation_process.run_process
probe_media(path, runner) -> dict
build_media_record(kind, source_path, sha256, ffprobe_result, *, derived_from=None,
                   time_range=None, frame_params=None, audio_source=None, commands=None,
                   perception_model=None, session_id=None, created_at=None) -> dict
validate_media_record(record) -> list
capture_chain_verdict(control_probe, product_probe) -> dict
silence_claim_problems(record, claim="silent") -> list
media_endpoint(env=None) -> dict
```

### media-record/1 结构（本步冻结的字段表）

- `source {path, sha256(64hex)}`、`media {probe_ok, has_video, has_audio, duration_seconds,
  format_name}`（探测事实，失败时全部 false/None）、`derived_from {path, sha256}|null`、
  `time_range {start, end}|null`、`frame_params {interval|fps, limit}|null`、
  `audio_source "capture"|"extract"|null`、`commands [str]`、`perception_model/session_id/
  created_at str|null`。
- `validate_media_record`：`frame-sampled` 必须带 `frame_params`（interval 或 fps 且 limit）——
  抽帧不是连续覆盖；`native-video`/`frame-sampled` 不得声称音频证据（`audio_source` 必须为
  null）；`audio-track` 必须有 `audio_source`；任意畸形输入只返回问题、不抛。

### 关键实现决定（供 S19/S21 复核）

1. 所有 argv 均为显式数组、无 shell 字符串；路径/参数非空、拒 NUL；数值参数拒绝 bool/非有限/
   非正。`clip_argv` 采用输入侧 `-ss/-to ... -i ... -c copy` 顺序。
2. `probe_media` 的 runner 口径 `callable(argv, timeout) -> {"exit_code","stdout_bytes",
   "stderr_bytes","timed_out"}`；超时、非零退出（stderr 文本随问题给出）、非法 JSON、缺
   streams/format 对象、流条目非对象一律 `ok=False` + `problems`，绝不抛；`duration` 缺失时
   回退到流 `duration` 最大值。
3. `capture_chain_verdict` fail closed：control 必须是 `probe_media.ok=True` 且
   `signal == "present"`，否则无论产品如何一律 `capture-unverified`（不允许判定产品静音）；
   product `silent`/`present` 还要求其 `probe_media.ok=True`，否则 unverified。
4. `silence_claim_problems`：`audio-transcript`（空 ASR 文本或含文本）一律不能支撑 silent；
   文件存在/有音轨（`native-video` 等）也不行；唯一合法依据是 `audio-track` 且 `commands`
   非空、`perception_model` 非空、记录内 `capture_chain.verdict == "product-silent"` 且
   `capture_chain.evidence_ref` 非空。非 silent 的 claim 直接拒绝。
5. `media_endpoint`：三键齐全才 `available=True` 并回 `{base_url, model}`（**不回显 api_key**），
   否则回 `{available: False, missing: [...]}`；不安装、不联网、不购买，Qwen3-Omni 只是候选。
6. 生产 runner `process_runner` 本地导入 `observation_process` 并转换为四键形状；测试注入假
   runner，不触发任何真实进程。
7. `capture_chain` 是本步新增的可选记录字段（静音证据引用），未进入 S02 冻结合同；若 S19/S21
   把它接进 gate，须先按流程冻结字段。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_media.py" -v` | 0 | Ran 73 tests — OK（0 fail/error） |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 1062 tests in 33.0s — OK（skipped=3；989 → 1062） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

原始输出：`docs/po-repair/baseline/s17/`；未删除/放松任何既有断言。

### S20A 打包待办（追加）

- 若控制器/S19 消费本模块，`scripts/install.py` 的 copy 清单需追加 `scripts/observation_media.py`；
  与已登记清单（observation_contract/candidate/results、runtime_state_policy、visibility_config、
  observation_process、observation_backend、observation_vision）一并补齐，并加 install 断言。

### 未完成 / 风险

1. **真实 ffmpeg/ffprobe 执行 BLOCKED-待环境（S21）**：本步 argv、解析与全部判定均为离线测试；
   S21 必须用真实录屏/录音跑 `probe_media(path, process_runner)`（或真实 runner）核对 duration/
   stream 字段与抽帧命令，并将结果归档。
2. `capture_chain_verdict` 只消费调用方给出的 `signal` 字符串，不执行 volumedetect；
   `present`/`silent` 的真实性由 S21 探针负责。
3. `silence_claim_problems` 依赖的记录内 `capture_chain` 字段未冻结合同（见决定 7）。
4. `probe_media.ok=True` 只表示 ffprobe 成功且结构可读，不代表媒体内容有效。
5. 未接线 `observation_backend/product_observation/check/install`（S19/S20 范围）；
   `observation_vision.dispatch_mode` 的 audio/video gaps 仍由控制器决定何时调用本模块。

### 下一步

**S19** 文档接线（S16 交接）；**S21** 实机验收：真实 ffmpeg/ffprobe、`record start/stop`
音频链路与静音判定（对照本步 capture chain 规则）。

## S18 — observation_resume（续跑判定 / 覆盖合并 / no-progress 熔断 / lease）

- **步骤**：S18（实现优先：新增 `scripts/observation_resume.py` + 离线测试 + 文档接线）
- **状态**：PASS
- **前置步骤**：S17
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python`，与 S00–S17 相同）

### 创建/修改的文件
- `scripts/observation_resume.py`（新）
- `tests/test_observation_resume.py`（新，63 条）
- `.opencode/commands/resume.md`（追加“观察续跑”小节）
- `mvp-delivery/references/delivery-recovery.md`（追加“Observation Resume 与 Lease”小节）
- `docs/po-repair/PROGRESS.md`（本记录）

### 实现要点
1. `resume_plan(previous, *, phase, candidate_id, model=None, environment=None)`：
   仅 `budget-exhausted` + 合法 `continuation` 可续；`previous.phase != phase` →
   reject；candidate 不同 → `new-round`；model/environment 与记录不同 → `new-run`；
   全同 → `resume` 并回传 `continuation`。所有分支都有 `reasons` 列表，畸形输入
   fail closed（非 dict / continuation 非对象 / phase 或 candidate 非法 → reject）。
2. `merge_coverage(results)`：只有 `outcome ∈ {covered, partial}` 且
   `evidence_refs` 非空、且 `surface_ids` 命中该 surface 的 journey 才算 covered
   并并入证据；finding 只记入 `finding_refs`，绝不自动算 covered；多份结果证据
   并集去重；输出 `surfaces` / `covered_material` / `uncovered_material`，畸形
   输入返回空形状、不抛异常。
3. `no_progress_breaker(signatures, max_same=3)`：按时间序统计**末尾连续相同**
   失败签名，≥3 才 `stop=True`；不同签名重置；非列表/空列表/非法 max_same
   不抛异常（非法回退 3，0 夹到 1）。
4. `lease_record(...)`：`observation-lease/1`（resource_id/owner_session/
   candidate_id/acquired_at/status/note）；`validate_lease` 结构校验不抛异常。
5. `lease_required(activity)`：`ui-operate`/`backend-run` → True；
   `media-analysis`/`evidence-review`/`read-only` → False；未知/非字符串 → True
   （fail closed）。
6. `lease_problems(lease, *, resources, now, max_age_seconds=3600)`：结构问题、
   资源未登记、`status != active`（not held）、`acquired_at` 不可解析/超龄
   （stale）、`now` 不可解析 fail closed；支持 ISO-8601（含 `Z`）与 epoch 秒，
   绝不抛异常。

### 验证命令与结果
| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_resume.py" -v` | 0 | Ran 63 tests — OK（0 fail/error） |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 1125 tests in 47.6s — OK（skipped=3；1062 既有 + 63 新增） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

原始输出：`docs/po-repair/baseline/s18/`；未删除/放松任何既有断言；未修改允许清单
外的文件；未 commit。

### S20A 打包待办（追加）
- `scripts/install.py` 的 copy 清单需追加 `scripts/observation_resume.py`（连同已登记
  的 observation_contract/candidate/results/media/process/backend/vision 等），并加
  install 断言。

### 未完成事 / 风险
1. **续跑真机验证 BLOCKED-待 S21**：本步只冻结判定（resume/new-run/new-round）与
   lease 结构；真实 budget-exhausted 续跑、真实 UI lease 持有/释放、真实浏览器/
   桌面资源串行化都未执行。
2. `no_progress_breaker` 只消费调用方给出的按时间序签名；签名产生与跨 session 追加
   由控制器负责，S21 需对照真实失败轨迹验证 3 次阈值。
3. lease 目前是工作流义务判定，不阻塞任意外部进程；`lease_problems` 不做真实现场
   探测（S21 用真实 resource 列表与时钟核验）。
4. 未接入 `observation_backend` / `check.py` / 各 skill 的调用路径（S19/S20 范围）。

## S19a — 文档同步：observer / reviewer / agent / 修复文档

- **步骤**：S19a（只改文档：product-observer SKILL 与 references、observer agent、reviewer SKILL、
  docs/po-repair；不碰 Python/JSON 代码与安装器）
- **状态**：PASS
- **前置步骤**：S18
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S18 相同）
- **范围**：把 S02–S18 已实现的合同/流程写入文档，删除与现状不符的 v1 表述；未 commit。

### 修改的文件

- `product-observer/SKILL.md`：
  - Execution 改为 packet v2 流程（加载 skill → 读包 → 尽快操作产品；`--model`/`--preflight` CLI 保持实际形态）；
  - Preflight 语义（status=passed + 全部身份字段匹配才可跳过；"controller-verified" 不豁免）；
  - discover/compare 对齐 `product-observation/2` 与 `difference_classification`；
  - 格式纠偏协作（首次恰好一个 ```json 围栏块；最多两次；信息不足回 marker）；
  - Stop conditions：coverage-completed 允许带阻断 finding、budget-exhausted 带 continuation、
    blocked/no-backend/lease-lost 零接触需 notes 或 capability_gaps；
  - Output：v2 字段与所有权、不写结果/工作流文件、证据入 `evidence_dir`。
- `product-observer/references/observation-protocol.md`：
  - 两阶段 packet 字段（brief/candidate/output/model/preflight；compare 的 `original.discover_result`）；
  - State Machine 改为 `stop_reason` 派生状态表（`result_stop_state()`）；
  - Budgets 续跑判定（同 candidate+phase+model+environment 才 resume；模型/环境变化新 run；candidate 变化新轮）；
  - 新增 Format Repair 小节（2 次上限、四条禁令、marker、needs-observation cap）；
  - Evidence Layout 改 run 布局 + `product-audit/2` sidecar（旧扁平布局 legacy 仅诊断）；
  - lease 资源（`observation-lease/1`、`lease_problems`、ui-operate/backend-run 需要而媒体分析不需要）；
  - Backend Independence 补直接多模态/playwright-cli/Midscene/UI-TARS/FFmpeg（失败与缺口记 capability gap）；
  - Trust Boundary 保留两层权限表述。
- `product-observer/references/finding-rules.md`：
  - 字段表补 `difference_classification`/`dismissal_reason`/`owner_decision_ref`/`resolution_ref`/`notes`；
  - `evidence_refs` 必填、真实存在且位于候选 evidence 目录（无绝对路径/`..`/编造）；
  - `dismissed` 需 dismissal_reason + evidence 或 owner decision（阻断级还要 owner_decision_ref）；
  - `resolved` 绑定历史轮的 `{candidate_id, finding_id}` + 非空证据。
- `product-observer/references/backend-routing.md`：
  - 后端表补直接多模态（首选，实测可读图）、playwright-cli（纯编码模型）、Midscene（Canvas/视觉定位）、
    UI-TARS（桌面备选）、FFmpeg/ffprobe（媒体证据准备）；
  - 新增 Preflight Reuse / Batched Short Journeys / Media: Control Probe First 三节。
- `.opencode/agents/mvp-product-observer.md`：
  - payload 字段去掉 `relations`；补只输出一个 json 围栏块、不写结果/工作流文件、
    controller 提供身份字段、format-repair 协作、盲态禁读清单、preflight 语义；
  - S13 权限块（`edit: deny` + bash 命令模式）逐字保留。
- `reviewer/SKILL.md`：
  - sidecar 改为 `product-audit/2`（`/1` 仍可读）；结果由 controller 提供、读被引用的
    discover/compare/review 文件，hash 由 controller/引擎绑定；评审只读、不操作 UI；
  - observations 段补 perception 记录与媒体限制（未验证感知=未读、抽帧非连续覆盖、
    无控制探针的静音主张=capture-unverified、capability_gap 不能升级为通过）；
  - verdict 决策表（S04 内容）未改。

### 与实现的对应（权威来源）

- 合同字段/所有权/派生状态：`scripts/observation_contract.py` + `references/result-contract.md`；
- 纠偏回合与单一围栏块：`scripts/observation_results.py`（`parse_single_payload` / `repair_prompt` /
  `run_format_repair`）+ `references/format-repair.md`；
- packet v2：`scripts/workflow_packets.py`（`workflow-observer-packet/2`、`OBSERVER_RULES_TEXT`）；
- 预检复用/后端选择/批处理：`scripts/observation_backend.py`；
- 视觉适配与感知：`scripts/observation_vision.py`；媒体：`scripts/observation_media.py`；
- 续跑/lease：`scripts/observation_resume.py`；gate 命令：`check.py product-audit-gate <goal> --trace <trace>`。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_*.py"` | 0 | Ran 1125 tests in 86.9s — OK（skipped=3，与 S18 基线一致） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

文档改动未影响任何测试；未新增/修改测试。

### 未完成 / 风险

1. `product-observer/UPSTREAM.md` 第 72 行仍提 `product-observation/1`（provenance 描述，S19a 允许
   清单外；S19b/后续可选同步）。
2. 文档只描述已实现能力；真实派发/权限/媒体链路的实机验收仍在 S21（文档不得被当作已验收证据）。
3. 未 commit。

### S19b 交接（还需同步的 mvp-delivery / construction 文档清单）

经检索，`construction/**` 不含 product-observer 引用（其 `mvp-observation.md` 是 v0.1 观察报告，
与本能力无关），S19b 无需改 construction。mvp-delivery 侧待同步：

| 文件 | 待同步点 |
|---|---|
| `mvp-delivery/references/delivery-execution.md` | `product-candidate/1`、`product-audit/1`、`product-observation/1` 与旧扁平 packet 路径 → v2 run 布局；补单一围栏块采纳、`visibility_dispatch` 派发、preflight 复用 |
| `mvp-delivery/references/delivery-finish.md` | `product-observation-review/1` → `/2`；补 review hash 由控制器/引擎绑定与 gate `--trace` 口径 |
| `mvp-delivery/references/goal-definition.md` | 第 119 行 `product-audit/1` → `/2`；补 candidate `runtime_state`/策略侧车引用 |
| `mvp-delivery/references/subagent-templates.md` | product-observer 行：schema `/2`、字段表（无 relations）、单一 json 围栏块与 controller 身份字段 |
| `mvp-delivery/references/subagent-orchestration.md` | 观察席位派发补 `visibility_dispatch`（插件指定模型）与“需重启 OpenCode”前提 |
| `mvp-delivery/references/stage-routing.json` | 第 148 行适配器清单（`browser-use` 未实现）→ direct-multimodal / playwright-cli / midscene / ui-tars / FFmpeg |
| `mvp-delivery/SKILL.md` | 第 253–263 行 finish 前置描述核对 v2 口径（gate `--trace`、review `/2`、sidecar `/2`） |
| `mvp-delivery/references/delivery-recovery.md` | S18 已加 Observation Resume 小节；核对与 `observation_resume.py` 判定一致（resume/new-run/new-round） |

### 下一步

**S19b**：按上表同步 mvp-delivery（及需要时的 UPSTREAM.md）文档；随后 S20/S20A 打包与 install 接线、
S21 实机验收。

## S19b — 文档同步：mvp-delivery 观察链路 / stage-routing / UPSTREAM

- **步骤**：S19b（只改文档：`mvp-delivery/SKILL.md`、`mvp-delivery/references/*`（含 `stage-routing.json`）、
  `product-observer/UPSTREAM.md`、`docs/po-repair/**`；Python 脚本、测试、安装器一律未动；未 commit）
- **状态**：PASS
- **前置步骤**：S19a
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S19a 相同）
- **方法**：先按 S19a 交接清单逐文件核对实现（`observation_contract/candidate/results/backend/resume`、
  `workflow_packets`、`check.py product-audit-gate`、`runtime_state_policy`、`visibility_config`、
  `workflow-visibility.js`），只写已实现能力。

### 逐项清单核对（S19a 交接）

| # | 文件 | 实现依据 | 结果 |
|---|---|---|---|
| 1 | `delivery-execution.md` | `observation_contract`（`product-candidate/2`、`product-audit/2`、`product-observation/2`）、`observation_results`（run 布局 `result_path`、`parse_single_payload`、`adopt_result`/`adopt_review`）、`observation_backend.preflight_skip_plan`、`workflow-visibility.js`（`visibility_dispatch`）、`workflow_packets.build_observer_packet`（`<phase>.packet.json`） | ✅ “Whole-Product Observation Dispatch”整段改 v2：run 布局 `<candidate>/<phase>/<run-id>/result.json`、单一 ```json 围栏块 + `adopt_result`/`adopt_review` 采纳（拒绝时只留 attempt，禁止 agent 写 `*.result.json` 兜底）、`visibility_dispatch` 优先与重启前提、旧 `opencode run --agent` 回落 P0-1 警示、preflight 身份匹配复用、修复必须新 candidate 完整 discover+compare |
| 2 | `delivery-finish.md` | `check.py` 5355–5413、`product_observation.write_gate_record`、`observation_results.adopt_review` | ✅ review schema `/2`；`product-audit-gate <goal> --trace <trace>` 为必需（缺 trace/非 native 失败）；`discover_hash`/`compare_hash` 由 controller/引擎按归档结果绑定（不一致拒绝）；补 `product-audit-gate/2` 记录绑定 goal definition hash + trace path/sha256/provenance 口径 |
| 3 | `goal-definition.md` | `observation_results.update_sidecar`（`/1` 可读、归一 `/2`）、`runtime_state_policy`、`visibility_config` | ✅ sidecar `/2`（legacy `/1` 仍可读）；候选目录改为 `candidate.json` + `discover.packet.json`/`compare.packet.json` + `discover/<run-id>/result.json`、`compare/<run-id>/result.json`、`review/<run-id>/result.json`；补 runtime-state 策略侧车（`.opencode/mvp/<slug>.runtime-state.json`）与 `visibility.json` 属运行态、不写进 goal JSON |
| 4 | `subagent-templates.md` | `.opencode/agents/mvp-product-observer.md`、`reviewer/SKILL.md` | ✅ product-observer 行 schema `/2`：payload 为恰好一个 json 围栏块，只列模型字段，controller 字段（goal_id/candidate_id/observer_session_id/model/packet_hash/received_at/attempt）采纳时并入，无 v1 字段/relations；reviewer 行补观察充分性评审返回 `product-observation-review/2` |
| 5 | `subagent-orchestration.md` | `workflow-visibility.js`、`workflow_packets._load_preflight`、`observation_backend.preflight_skip_plan`、`HOST-COMPATIBILITY.md` §4 | ✅ Dispatch Preflight 补第 6 条（`visibility_dispatch` 读 `visibility.json`、插件需重启、不可见按 capability-unavailable 披露、`opencode run --agent` 回落仅诊断）与第 7 条（感知探针对应实际 `provider/model`、packet/preflight 模型不一致即失败、跳过探测仅凭身份全匹配、“controller-verified”不豁免） |
| 6 | `stage-routing.json` | S19a 更新的 `backend-routing.md` 与各脚本 | ✅ 第 148 行 `(midscene/agent-device/browser-use)` → `(direct-multimodal/playwright-cli/midscene/ui-tars; media via ffmpeg)`；`schema_version: 3`、结构与其余字段未动；`json.load` 验证通过 |
| 7 | `mvp-delivery/SKILL.md` | 同 1/2 | ✅ finish 前置核对改 v2：gate 必须 `--trace .opencode/mvp/trace.json`、结果由 controller 采纳并写不可变 result、`product-observation-review/2` 的 discover/compare hash 由 controller/引擎绑定 |
| 8 | `delivery-recovery.md` | `observation_resume.resume_plan`/`lease_required`/`lease_problems` | ✅ 核对一致（`budget-exhausted`+continuation 才可 resume；phase 不同 reject、candidate 不同 new-round、model/environment 不同 new-run；create-only；lease 规则与未知活动 fail closed）——**无需修改** |
| 9 | `product-observer/UPSTREAM.md` | `observation_contract.SCHEMA_RESULT` | ✅ 第 72 行 `product-observation/1` → `/2`（仅 provenance 描述行） |

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -c "import json;json.load(open('mvp-delivery/references/stage-routing.json',encoding='utf-8'));print('routing ok')"` | 0 | `routing ok` |
| `python -m unittest discover -s tests -p "test_*.py"` | 0 | Ran 1125 tests in 81.2s — OK（skipped=3，与 S18/S19a 基线一致） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

文档/JSON 改动未影响任何测试；未新增/修改测试；未修改允许清单外文件。

### 未完成 / 风险

1. 文档只描述已实现能力；真实派发（`visibility_dispatch` 实机）、权限、媒体与模型感知链路验收仍在
   S21（文档不得被当作已验收证据）。
2. S19a 遗留的 `UPSTREAM.md` 行已在本步清零；后续若 S20/S20A 打包改变安装路径或清单，相关
   `python .opencode/workflow/scripts/...` 命令前缀需随之复核。
3. 未 commit。

## S19c — 文档一致性测试：schema 漂移 / 命令存在性 / 后端路由 / agent 契约 / 模块导入

- **步骤**：S19c（实现优先：新增离线文档一致性测试，不改实现；未发现需修的文档）
- **状态**：PASS
- **前置步骤**：S19b
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`，与 S00–S19b 相同）
- **新增文件**：`tests/test_observation_docs.py`（15 个测试，离线，仅读仓库文件与解析源码，不执行 CLI）
- **修改文件**：无（文档与实现一致，未触发最小修正）
- **未修改**：`scripts/**`、既有测试、安装器、opencode 配置；未 commit

### 测试覆盖面（对应 S19c 要求）

| 组 | 测试 | 断言要旨 |
|---|---|---|
| Schema 漂移 | `SchemaDriftTests`×3 | 10 份文档中 `product-observation(-review)/1` 必须同行或前 100 字符含 `legacy`；全部版本引用均为 `/2`；`result-contract.md` 存在且 `contract-enums` 块可 `json.load` |
| 命令存在性 | `CommandSurfaceTests`×5 | `check.py` 文本含四个命令且 dispatch 表实现；文档反引号 `` `check.py <sub>` `` 全部落在 check.py dispatch 集合（含 `ui-gate`，已确认实现于 `check.py:2162`）；`workflow_packets.py` 有 `observer`/`validate` 子命令与 `workflow-observer-packet/2`；`visibility_config.py` 有 `set/show/select/mark`；`visibility.md`/`resume.md` 引用的脚本路径在 `scripts/` 下存在 |
| 后端与路由 | `BackendRoutingTests`×2 | `stage-routing.json` 可解析且含 direct-multimodal/playwright-cli/midscene/ui-tars/ffmpeg、无 `browser-use`；与 `observation_backend.BACKENDS` + `observation_vision.ADAPTERS` 合并一致；`backend-routing.md` 含四者与 ffmpeg |
| Agent 契约 | `AgentContractTests`×3 | `mvp-product-observer.md` 有 `edit: deny`/`task: deny`/bash 对象、无 `relations`、无 `write: deny`、恰好一个 ```json 围栏块；`reviewer/SKILL.md` 的 `discover_hash`/`compare_hash` 语义绑定 controller/engine（computed/bound），无自报 hash 指令 |
| 模块与常量 | `ModuleImportAndVersionTests`×2 | 10 个观察模块全部可 import；`observation_contract.SCHEMA_RESULT/REVIEW` 与 `contract-enums`、`result-contract.md`、10 份文档均为 `/2` |

### 实现侧缺口清单

**无。** 两处曾疑似不一致，核实后均为实现侧事实：

1. `delivery-finish.md` 反引号引用 `` `check.py ui-gate` ``：`ui-gate` 实际实现于
   `scripts/check.py`（dispatch 表与 `check.py:2162`），不在 S19c 四个必断言命令内但属于已实现命令，
   测试按“文档引用的 check.py 子命令必须是引擎已 dispatch 的命令”断言，无需改文档。
2. `stage-routing.json` 未列 `agent-browser`（仅列 direct-multimodal/playwright-cli/midscene/ui-tars）：
   `agent-browser` 是 `observation_backend.BACKENDS` 的浏览器执行底座，routing 的“适配器”清单与
   `observation_vision.ADAPTERS` 对应，并在 `backend-routing.md` 中有完整路由表，非缺口。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_observation_docs.py" -v` | 0 | Ran 15 tests — OK |
| `python -m unittest discover -s tests -p "test_*.py"` | 0 | Ran 1140 tests in 70.9s — OK（skipped=3；S19b 基线 1125 + 新增 15） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

### 未完成 / 风险

1. 测试为静态一致性：证明文档与源码声明一致，不证明真实派发/感知链路已验收（仍在 S21）。
2. `check.py` dispatch 解析依赖 `command == "..."` 文本形式；若 S20+ 重构为表驱动需同步测试。
3. 未 commit。

## S20A — 安装器打包：新观察脚本 + workflow-visibility 插件 + 依赖提示

- **步骤**：S20A（实现优先：`install.py` 复制清单补齐 10 个新脚本与 `.opencode/plugins/workflow-visibility.js`，新增 node_modules 依赖提示；更新 `tests/test_install.py`）
- **状态**：PASS
- **前置步骤**：S19c
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`）
- **修改文件**：`scripts/install.py`、`tests/test_install.py`、`docs/po-repair/PROGRESS.md`
- **未修改**：其他 `scripts/**`、其他测试、`.opencode/plugins/*`、opencode 配置；未 commit

### 实现要点

| # | 要求 | 实现 |
|---|---|---|
| 1 | 脚本清单补齐 | `copy_jobs` 改为 23 个脚本名循环（原 13 + `observation_contract`/`observation_candidate`/`observation_results`/`observation_resume`/`observation_vision`/`observation_media`/`observation_process`/`observation_backend`/`visibility_config`/`runtime_state_policy`），key 仍为 `scripts/<name>`，目标 `engine_root/scripts/<name>`；`product_observation.py` 等原条目不动 |
| 2 | 插件复制 | `plugins_source = repo/.opencode/plugins`，`*.js` → `target/.opencode/plugins/<name>`，manifest key `plugins/<name>`；`--commands-only` 跳过；目录由 `safe_copy` 的 `mkdir(parents=True)` 创建；覆盖保护/预检沿用 `previous_files` 所有权（未拥有且不同 → 报错，除非 `--force`） |
| 3 | 依赖提示 | 非 commands-only 安装后，若 `<target>/.opencode/node_modules/@opencode-ai/plugin` 不存在则打印 `plugin dependency missing: run "npm install" in <target>/.opencode (package.json must include @opencode-ai/plugin)`；仅提示，不改退出码 |
| 4 | 既有语义 | 冲突预检/rollback（copy_jobs 自动纳入新文件与插件）/manifest/stale 清理/JSONC/retire 不变；引擎拷贝循环改为遍历 `copy_jobs`（跳过 commands/agents/plugins），源缺失的脚本跳过（兼容只含旧清单的测试仓库） |
| 5 | 测试 | sources 增补 10 脚本与插件；copy 次数改为按 engine 源动态计算；目标文件/清单断言按新清单校准；新增插件字节一致、manifest 键、依赖提示（有/无 node_modules）、`--commands-only` 不复制插件/脚本、未拥有插件拒覆盖与 `--force` 六类断言 |

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_install.py" -v` | 0 | Ran 22 tests — OK（S19 基线 18 + 新增 4） |
| `python -m unittest discover -s tests -p "test_*.py"` | 0 | Ran 1144 tests in 70.7s — OK（skipped=3；S19c 基线 1140 + 4） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

冒烟（`python scripts/install.py C:\Users\24083\AppData\Local\Temp\opencode\s20a-target`，退出码 0）：

```
installed commands: build, fix, grill, plan, resume, visibility
installed subagents (.opencode/agents/): mvp-product-observer, mvp-researcher, mvp-reviewer, mvp-step-executor, mvp-test-author, mvp-worker
installed workflow engine: .opencode/workflow/scripts/check.py
installed plugins (.opencode/plugins/): workflow-visibility.js
plugin dependency missing: run "npm install" in C:/Users/24083/AppData/Local/Temp/opencode/s20a-target/.opencode (package.json must include @opencode-ai/plugin)
registered skills paths: ...（21 条）
restart OpenCode to load the changes
```

产物核验：`<target>/.opencode/workflow/scripts/` 23 个 `.py`；manifest 含 `plugins/workflow-visibility.js` 与 23 个 `scripts/*`；插件与源 sha256 相同（逐字节一致）。目标目录保留供 S20B/S21 使用。

### 未完成 / 风险

1. 冒烟只证明打包落地；`npm install` 与插件真实加载、`visibility_dispatch` 实机仍在 S21。
2. 引擎脚本源缺失时跳过（为兼容既有 `test_runtime_doctor` 的旧清单仓库）；真实仓库 23 个脚本齐全。
3. 未 commit。

## S20B — 校准驱动纯函数核心 + 运行手册

- **步骤**：S20B（实现优先：`driver_core.py` 8 个纯函数、`tests/test_calibration_driver.py` 39 条、
  `validation/observation-calibration/README.md` 运行手册；真实模型运行归 S21）
- **状态**：PASS（实现；实机运行 BLOCKED / 案例 NOT RUN，见手册）
- **前置步骤**：S20A（安装产物）、S19c
- **日期**：2026-09-21
- **解释器**：Python 3.10.7（`python` → `D:\python\python.exe`）
- **创建的文件（只新增允许清单内文件；未改任何既有文件）**：
  - `validation/observation-calibration/driver_core.py`（新，标准库）
  - `tests/test_calibration_driver.py`（新，39 条 unittest）
  - `validation/observation-calibration/README.md`（新，运行手册）
  - `docs/po-repair/baseline/s20b/{test_calibration_driver,test_all,check_selftest}.txt`（原始输出）
  - `docs/po-repair/PROGRESS.md`（本记录）
- **未修改**：沙箱 `E:\MISC\代码项目\po-validation-sandbox`（只读参考）、其他 scripts/tests/docs、
  `.opencode/**`、`validation/product-observation/README.md`；未 commit；未 reset/clean/stash。

### 实际签名（Python 3.10 标准库）

```python
make_primary_mirror(agent_text: str) -> str                       # 缺 frontmatter/mode/未知 mode → ValueError
assert_single_channel(agent_text: Any) -> list[str]
seed_redaction_problems(seed_config: dict, packet: dict) -> list[str]
packet_guard(packet_ok: bool) -> dict                             # {"abort": bool[, "reason"]}
state_reset(paths: Any) -> dict                                   # {"removed","missing","problems"}
server_order_plan(steps: Sequence) -> list[str]                   # setup 晚于/缺 server 前置 → ValueError
adoption_result(payload, envelope, trace, cdir, project_root, phase, **kw)  # 薄包装 adopt_result
result_source_is_single(text: Any) -> list[str]
```

### 关键实现决定（对齐旧沙箱缺陷）

1. **primary 镜像**：只替换 frontmatter 内 `mode` 值 token（`subagent` → `primary`），其余字节
   （含行尾）不变；`primary` 幂等直返；`all` 等未知值 fail closed 抛 ValueError。
2. **单通道声明**：命中 `ONLY as the closing ```json block`、`closing ```json block`、
   `one fenced json`、`一个/单一 json 围栏块` 之一即通过，否则返回问题。
3. **种子防泄漏**：递归收集 `seed*`/`defect*`/`expected_findings*` 键下的全部字符串，再递归扫描
   packet 的全部字符串值（大小写不敏感），命中给出 `$.path` 位置；不检查 packet 键名。
4. **packet_guard**：布尔判定，失败 abort 原因逐字为 `phase packet generation failed;
   do not dispatch`。
5. **state_reset**：单路径或路径序列；存在文件删除、不存在进 `missing`、目录/删除失败进
   `problems`；任何输入不抛异常。
6. **server_order_plan**：步骤去空白；只要出现 `server-start` 就必须有 `setup` 且更早，否则
   ValueError；无 `server-start` 时保持原顺序。
7. **adoption_result**：函数内延迟 import `observation_results`，按模块签名重排
   `(cdir, project_root, phase, payload, envelope, trace)` 后直传 `**kw`；无任何 setdefault/
   默认成功值/文件兜底（缺 trace、缺信封字段、缺 stop_reason 均走既有拒绝路径）。
8. **result_source_is_single**：解析委托 `parse_single_payload`；另以
   `(write|save|create|output|export|store|dump|写入|保存|输出|落盘) … result.json` 检出双通道
   写入声明，紧邻否定词（not/never/禁止/不要/不得…）时放行 `do not write result.json`。

### 验证命令与结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_calibration_driver.py" -v` | 0 | Ran 39 tests — OK |
| `python -m unittest discover -s tests -p "test_*.py"`（全量） | 0 | Ran 1183 tests in 82.4s — OK（skipped=3；1144 → 1183，恰好 +39） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |

原始输出：`docs/po-repair/baseline/s20b/*.txt`；未删除/放松任何既有断言；无 skip 新增。

### 未完成 / 风险（交 S21）

1. **实机运行 BLOCKED**：真实模型派发、插件（需重启 + `npm install`）、浏览器/多模态通道、
   gate 全链路均未执行；A–G 与 Web/多模态案例全部 NOT RUN。
2. `driver_core.py` 不含服务进程管理、run-id 分配、报告渲染与 runs/ 归档脚本；S21 若需要应
   新建独立运行器消费本模块，而不是扩展纯函数。
3. `seed_redaction_problems` 以子串匹配：过短的种子词可能误报，S21 组装 seed_config 时应使用
   完整句子而非单字母标签。
4. `result_source_is_single` 的写入声明正则覆盖常见动词；嵌入代码示例中的 `result.json`
   （如文档片段）可能被计为问题，属 fail closed。
5. 运行手册 §3 的插件路径/CLI fallback 基于 S12b 既有实现；实机行为仍以 S21 验收为准。

### 下一步 / 交接（S21）

- 在重启后的 OpenCode + 可解析 `@opencode-ai/plugin` 的目标项目（S20A 冒烟目录或 `install.py`
  新装项目）执行 `validation/observation-calibration/README.md` §3 全流程；原始 stdout/packet/
  trace/gate 输出归档到 `validation/observation-calibration/runs/<case>/<cid>/`。
- 采纳一律走 `result_source_is_single` → `parse_single_payload` → `adoption_result`
  （review 走 `adopt_review`）；禁止双通道、latest-session、默认 stop_reason。
- 回归入口：`tests/test_calibration_driver.py`；本模块 API 手册：
  `validation/observation-calibration/README.md`。

## S21 — 报告与核验（确定性回归 + 语料回放 + 校准报告）

- **步骤**：S21（只读运行与归档；报告与核验；未改任何代码/测试/技能文档；未 commit）
- **状态**：PASS（机械核验全绿）；实机运行/案例全部 BLOCKED / NOT RUN（如实登记）
- **前置步骤**：S00–S20B
- **日期**：2026-09-21
- **解释器/运行时**：Python 3.10.7、Node v24.19.0、OpenCode 1.18.25、Windows 10.0.19045
  （实测见 `docs/po-repair/baseline/s21/env.txt`）

### 创建/修改的文件（全部在允许清单内）

- `docs/po-repair/CALIBRATION.md`（新）：环境、确定性矩阵（P0-1~P2-18、报告未测项、附录 A、
  S05/S07 关联新发现）、语料回放对照、真实运行计划（全部未运行）、成本指标边界、结论边界。
- `docs/po-repair/COVERAGE-MAP.md`（追加"状态（S21 核验）""证据（S21）"两列 + §3 说明一段；
  既有列内容未改）。
- `docs/po-repair/PROGRESS.md`（本记录）。
- `docs/po-repair/baseline/s21/**`（新）：全量/分项测试原始输出、`env.txt`、`corpus-validity.txt`、
  `corpus-replay/INDEX.json`、`replay_corpus.py`、`evidence_index.py`、`evidence-index.txt`。
- **未修改**：`scripts/**`、`tests/**`、`.opencode/**`、`validation/**`、各 SKILL/agent；
  未写 `docs/po-repair/corpus/`；未 commit。

### 验证命令与实测结果

| 命令 | 退出码 | 结果 |
|---|---|---|
| `python -m unittest discover -s tests -p "test_*.py"` | 0 | Ran 1183 tests in 71.529s — OK（skipped=3） |
| `python scripts/check.py --selftest` | 0 | selftest PASS |
| `node --test "tests/js/**/*.test.mjs"` | 0 | tests 23 / pass 23 / fail 0（397.0996ms） |
| 14 个分测试文件逐个运行 | 均 0 | 合计 Ran 642 tests；含 skipped 3（candidate 2、state_binding 1） |
| 语料回放（`replay_corpus.py` 重定向输出） | 0 | collected=21 / valid=0 / invalid=21 / validator_crash=0 / copy_matches=21/21 / handmade=3 |

分项实测：product_observation 31、gate 33、semantics 41、candidate 40（skip2）、state_binding 26（skip1）、
results 94、format_repair 20、backend 49、vision 76、media 73、resume 63、docs 15、visibility_config 59、
install 22；原始输出见 `baseline/s21/`。

### 语料终态对照

- S00 基线：VALID 3 / INVALID 16 / VALIDATOR-CRASH 2（`corpus/INDEX.json` 未改）。
- S03 终态：legacy 21 / 0 invalid / 0 crash（`baseline/s03-corpus-regression.json`）。
- S09 终态：21 份全部 `needs-observation`（cap，attempts=3 / repair_count=2；
  `baseline/s09-corpus-repair.json`）。
- S21 回放：0 崩溃、21/21 复制一致；`invalid=21` 是收集器的二值口径（3 份 v1 review 因收集器按
  schema 分派而多报字段诊断），与 S03/S09 不矛盾（CALIBRATION.md §3 已说明）。

### 未完成事项 / BLOCKED / NOT RUN（不夸大）

1. **BLOCKED-需重启**：`visibility_dispatch`/`visibility_status` 实机加载与派发；子会话模型一致性；
   observer/reviewer 实机权限拒绝；真实 trace → `product-audit-gate` 闭环；会话内图片附件。
2. **NOT RUN-需模型/设备**：案例 A–G、Web A-web~F-web、图片/音频/视频、桌面、真实格式纠偏回合、
   真实 reviewer 质量/漏面评审、进程树与编码实机链路、token/墙钟成本。
3. **PARTIAL（无专门回归）**：`intermittent` 正向值；`write: deny` 权限键未引入；`capture_chain`
   未进冻结合同；`owner_decision_ref` 仅字符串层。
4. 本轮未采集任何真实 token/墙钟指标，未运行真实派发；CALIBRATION.md §5 只记录确定性测试耗时。

### 下一步（可选）

- 重启 OpenCode 后按 `validation/observation-calibration/README.md` §3 执行实机校准，
  输出归档到 `validation/observation-calibration/runs/<case>/<cid>/`，再回填 CALIBRATION.md。

## S22 — 最终审计与交付（FINAL-REPORT + 最小文档修正 + 终局检查）

- **步骤**：S22（最终审计与交付；只写 `FINAL-REPORT.md`、`validation/product-observation/README.md`、
  `README.md`、`README.en.md`、本文件与 `baseline/s22/`；不改代码/测试/技能/配置；未 commit）
- **状态**：PASS（机械核验全绿）；实机项仍 BLOCKED / NOT RUN（如实登记，未改判）
- **前置步骤**：S00–S21
- **日期**：2026-09-21
- **解释器/运行时**：Python 3.10.7、Node v24.19.0（与 S21 相同；实测见 `baseline/s21/env.txt`）

### 创建/修改的文件（仅允许清单 + D 指定目录）

- `docs/po-repair/FINAL-REPORT.md`（新，交付报告：执行摘要、覆盖表、变更清单、验证记录、
  BLOCKED 关闭前提与步骤、边界声明）。
- `validation/product-observation/README.md`（Status 段最小更新：protocol-pass 写明
  “S00–S21 机械回归：1183 Python + 23 Node”；detection-evaluated 仍 NOT RUN，指向
  `docs/po-repair/CALIBRATION.md` 的运行前提与“不得用框架支持冒充本机验证”规则；Non-Goals 未动）。
- `README.md`、`README.en.md`（子代理清单由 5 个改为 6 个并列入 `mvp-product-observer`；
  两文件均无 observation schema/`product-observation/1` 表述，未触发其它修正）。
- `docs/po-repair/baseline/s22/`（6 份终局检查原始输出）。
- `docs/po-repair/PROGRESS.md`（本记录）。
- **未修改**：`scripts/**`、`tests/**`、`.opencode/**` 实现、各 SKILL/agent 实现、`validation/observation-calibration/**`；
  未触碰沙箱 `E:\MISC\代码项目\po-validation-sandbox`；未 commit。

### 终局检查命令与结果

| 命令 | 退出码 | 结果 | 原始输出 |
|---|---|---|---|
| `git status --short` | 0 | 68 行（工作区全部改动未 commit；含 untracked 新增） | `baseline/s22/git-status.txt` |
| `git diff --check` | 0 | 0 个空白错误；仅 CRLF 行尾提示 | `baseline/s22/git-diff-check.txt` |
| `git diff --stat` | 0 | 28 files changed, 1427 insertions(+), 169 deletions(-)（不含 untracked 新增） | `baseline/s22/git-diff-stat.txt` |
| `python -m unittest discover -s tests -p "test_*.py"` | 0 | Ran 1183 tests in 64.351s — OK（skipped=3） | `baseline/s22/test_all.txt` |
| `python scripts/check.py --selftest` | 0 | selftest PASS | `baseline/s22/check_selftest.txt` |
| `node --test "tests/js/**/*.test.mjs"` | 0 | tests 23 / pass 23 / fail 0 | `baseline/s22/node-test-glob.txt` |

结果与 S21 完全一致，无回归；语料 21 份终态以 S03/S09 为准（S21 回放 0 崩溃、21/21 复制一致），
本轮未重跑语料（未写 `docs/po-repair/corpus/`）。

### 逐项步骤状态（S00..S22）

| 步骤 | 状态 | 备注 |
|---|---|---|
| S00 | PASS | 基线与语料索引；无实机验证 |
| S01 | PASS | 宿主探针；2 项 BLOCKED-待重启 |
| S02 | PASS | 合同 v2 冻结 |
| S03 | PASS | 校验器容错 + v2 接入；21 份 0 崩溃 |
| S04 | PASS | finding 语义与 reviewer 裁决表 |
| S05 | PASS | gate 全量诊断 + finish 闭环 |
| S06 | PASS | 候选制品与运行状态分离 |
| S07 | PASS | 状态策略贯通 workspace binding |
| S08a-1 | PASS | 解析/布局/create-only |
| S08a-2 | PASS | 信封/provenance/采纳 |
| S08b | PASS | 锁 / sidecar / adopt_review |
| S09 | PASS | 格式纠偏状态机 |
| S10 | PASS | observer packet v2 |
| S11 | PASS | 观察模型设置 + `/visibility` |
| S12a | PASS | 派发模型证据 |
| S12b | PASS（实现） | 插件 + Node 23/23；实机加载 BLOCKED-待重启 |
| S13 | PASS | 权限边界声明与回归 |
| S14 | PASS | 进程/编码边界 |
| S15 | PASS | 后端选择与短旅程批处理 |
| S16 | PASS | 视觉适配面（离线） |
| S17 | PASS | 媒体采集与判定（离线） |
| S18 | PASS | 续跑/覆盖合并/熔断/lease |
| S19a | PASS | 文档同步（observer/reviewer/agent） |
| S19b | PASS | 文档同步（mvp-delivery/routing/UPSTREAM） |
| S19c | PASS | 文档一致性测试 |
| S20A | PASS | 安装器打包 23 脚本 + 插件 + npm 提示 |
| S20B | PASS（实现） | 校准驱动纯函数 + 手册；实机 BLOCKED / 案例 NOT RUN |
| S21 | PASS（机械） | 确定性回归 + 语料回放 + CALIBRATION；实机 BLOCKED / NOT RUN |
| S22 | PASS（机械） | 本轮：终局检查全绿；实机项仍未验收，未夸大 |

### 未完成事项 / BLOCKED / NOT RUN（与 S21 相同，未改判）

1. **BLOCKED-需重启**：`visibility_dispatch`/`visibility_status` 实机加载与派发；子会话模型一致性；
   observer/reviewer 实机权限拒绝；真实 trace → `product-audit-gate` 闭环；会话内图片附件。
2. **NOT RUN-需模型/设备**：案例 A–G、Web A-web~F-web、图片/音频/视频、桌面、真实格式纠偏回合、
   真实 reviewer 质量/漏面评审、进程树与编码实机链路、token/墙钟成本。
3. **PARTIAL 未解决**：`intermittent` 正向值；`write: deny` 未引入；`capture_chain` 未进冻结合同；
   `owner_decision_ref` 仅字符串层；P0-1/P1-3/P2-11/P2-12/P2-16/P2-17/P2-18 等机械层。
4. 结论边界与关闭步骤详见 `FINAL-REPORT.md` §5/§6；不得以本记录宣称“P0-2/P0-1 实机闭环已解决”。

## S21 实机校准补录（2026-09-21 晚）

- **状态**：PARTIAL PASS — 两个 CLI 案例 + 图片感知探针已用真实模型执行；Web/音视频/桌面/intermittent/续跑仍 NOT RUN。
- **环境**：OpenCode 1.18.25；s20a-target 内 npm install（@opencode-ai/plugin 1.18.25，27 包）；
  模型 openai/gpt-5.6-luna；primary 镜像 + nested `opencode run`。
- **结果**：
  1) A-term good（cand-calib-2）：discover 81s + compare 67s + review，0 纠偏，gate **PASS**（假阳性对照通过）。
  2) A-term bad（cand-bad-1）：0 findings（**漏报**）；compare 1 次格式纠偏；gate FAIL（baseline 被误写成 capability gap）。
  3) B-term bad（cand-bbad-1）：discover F-001 high/confirmed（4 证据文件），compare confirmed-defect，
     review needs-observation，gate FAIL（unresolved high）——**检出与阻断命中**。
  4) 图片感知：随机绿色 PNG，luna 回答 green，sha256/记录校验通过 → image_read VERIFIED（CLI 链路）。
- **校准中新发现并修复**：
  - CLI 证据落盘缺口 → 新增 `scripts/observation_capture.py` + packet 规则 2b + observer agent 规则 +
    install 清单 + `tests/test_observation_capture.py`（7 条）。
  - `baseline: none` 不是 capability gap → protocol 与 packet 规则明示（防 gate 误阻断）。
  - 运行器 review 信封误含 candidate_id、review 阶段误走 observer 分支 → 已修。
- **产物**：`validation/observation-calibration/run_case.py`、`runs/<case>/<cid>/`（原始 stdout、payload、metrics、gate.txt）、
  `runs/multimodal/perception.json`；汇总见 `docs/po-repair/CALIBRATION.md` §8。
- **未运行**：Web A-web~F-web、音视频、桌面、intermittent 正向、续跑/lease、`visibility_dispatch` 插件实机加载（需重启）、token 成本。

### 校准补录续（C/D/E/F + 规则修正）

- C-term bad 首轮 **MISS + gate 放行**（observer 未读候选 README）；加入“必读候选公开文档”规则后
  同案例重跑（cand-cbad-2）**检出 F-001 并阻断**（A/B 对照成立）。
- D-term bad：检出 high/confirmed 与 medium；README “v2 note” 洗白未降低判定；gate 阻断。
- E-term redesign：检出 2×high（1 次格式纠偏）；gate 阻断。
- F-term bad：检出 high/confirmed → compare high/**intermittent**；reviewer 首次给出 **needs-repair**；
  gate 阻断。intermittent 保留规则实测生效。
- 规则修正：`OBSERVER_RULES_TEXT` 4b + observer agent 规则（公开文档作为 expected_basis）。
- 小结：6 个 CLI 种子 5 检出（A-bad 漏报）；干净对照 0 假阳性；全部检出案例 gate 正确阻断。
- 详情与证据路径：`docs/po-repair/CALIBRATION.md` §8.6–8.7；运行产物 `validation/observation-calibration/runs/`。

### 校准补录：Web 通道（B-web bad）

- 运行器新增最小 Web 支持（http.server 先起、后冻结候选；atexit 清理）。
- luna + agent-browser 0.38.1：discover 370s 检出 F-001 high/confirmed（Save 后 reload 不持久、无 Saved ✓）；
  compare 154s 补 F-01 high + F-02 medium；review needs-repair；gate FAIL（正确阻断）。
- 证据含 agent-browser 截图 + 经 observation_capture 落盘的 snapshot/console（含 meta/sha256）。
- 对 P0-2 的结论修正：Web 通道在 luna 上实测可行（此前 glm-5.3-flash 全超时为模型档位问题）；
  批处理优化仍为后续项而非阻塞项。
- 校准最终统计：CLI 种子 6 例中 5 检出（A-bad 漏报；C 经规则修正后检出）+ Web 1 检出；
  干净对照 0 假阳性；全部检出案例 gate 正确阻断；intermittent 与 reviewer needs-repair 决策表实测生效。

# thesis-defense × construction 统一方法论与实施方案

> 本文是唯一权威设计。它整合 grill-me、minimal-diff、handoff、prototype、research 的方法论及此前两版方案，目标不是复制五个社区 skill，而是建立一条可恢复、可审计、可直接施工的闭环：**需求定锚 → 三方持续答辩 → 诚实异议清零 / 用户裁决 → 完整流程与实现契约 → 最小施工 → 文档交接 → 变更回炉。**

---

## 1. 方法论来源与转译

| 来源 | 参考 | 本流程吸收的方法论 | 不照抄的部分 |
|---|---|---|---|
| grill-me | [RobMitt/grill-me-skill](https://github.com/RobMitt/grill-me-skill) | 需求方席位、决策树澄清、一次一问、具体选项、能查不问、决定落盘 | 不把用户访谈当成穷尽所有技术分支；需求方不代替技术人员选库 |
| minimal-diff | [benjaminard/fable-skills/minimal-diff](https://github.com/benjaminard/fable-skills/tree/main/skills/minimal-diff) | 范围最小、论证到底；每轮最小修订；施工逐 hunk 范围门 | 不把“最小”误解为提前停止答辩或交付不完整流程 |
| handoff | [stanislavfor/grill-me-skills/claude-handoff](https://github.com/stanislavfor/grill-me-skills/tree/main/skills/in-progress/claude-handoff) | 文档契约、引用制品而非复制、施工理念与维护边界落盘、脱敏 | 不以会话提示词作为主要交接物 |
| prototype | [stanislavfor/grill-me-skills/prototype](https://github.com/stanislavfor/grill-me-skills/tree/main/skills/engineering/prototype) | 事实争议转最小实验；问题决定形状；一条命令可复现；结果回填 | 不把 prototype 直接提升为生产实现，也不删除复现证据 |
| research | [stanislavfor/grill-me-skills/research](https://github.com/stanislavfor/grill-me-skills/tree/main/skills/engineering/research) | 正反双方轮子优先、一手来源、证据包、逐条溯源 | 不只做零散事实查询；调研必须直接缩小设计和施工量 |

## 2. 不可破坏的七条原则

1. **需求守恒**：需求不能在答辩中因“更漂亮、更简单、更稳妥”被 AI 擅自删除或改写。
2. **范围最小，论证到底**：只设计完成需求所需内容，但范围内的正常路径、分支、失败、回退和验收必须完整。
3. **无固定轮数停机**：深度只控制单轮广度与证据标准；还有诚实且实质的异议就继续。
4. **取舍有主人**：事实由证据裁决，价值取舍由真实用户拍板，AI 不以“最佳实践”代选。
5. **轮子优先**：原样复用 → 薄适配 → 最小扩展 / 局部 fork → 有证据后才自研。
6. **答辩产物可直接施工**：construction 只编译已答辩的实现契约，不重新设计业务流程或架构。
7. **状态和理由均落盘**：恢复所需状态、证据、用户决定、CR、施工取舍和维护边界不依赖会话记忆。

---

## 3. 版本与产物权威

### 3.1 契约版本

新版论文 frontmatter 必须包含：

```yaml
contract-version: 4
schema-version: 1
methodology: triadic-socratic-v1
contract-hash: <由规范化契约内容计算>
```

`version` 继续表示论文修订版本；`contract-version` 表示跨 skill 协议。旧论文即使 `status: passed`，没有受支持的 contract-version 也不得直接开工。

contract-hash 只覆盖语义契约投影：P/T/W/F/I/D/A/R/V/B，以及通过答辩时被引用为依据的 E ID/result-hash；不包含 frontmatter status/phase/cycle、日期、生成式摘要、日志指针、T 的 applied-in-hash 等审计回填字段，也不包含通过后由 S0 产生但未改变契约语义的执行证据。规范化采用 UTF-8、LF、字段名排序和固定空值规则。唯一 hash 算法、被哈希字段清单与正反 fixtures 必须写入 `contract-schema.md`，两个 skill 共用，禁止各自实现一份口径。

### 3.2 权威制品

| 制品 | 唯一职责 | 写入方 | 读取方 |
|---|---|---|---|
| `docs/thesis.md` | 需求、流程、实现绑定、决策、风险、验证的当前契约 | thesis-defense | 两个 skill |
| `docs/defense-log.md` | 追加式答辩事件与每轮原文 | thesis-defense | thesis-defense / 审计者 |
| `docs/evidence/manifest.md` + evidence bundles | research / prototype 的可复现证据索引 | thesis-defense / construction S0 | 两个 skill |
| `docs/change-orders.md` | CR 的唯一状态台账 | 两个 skill | 两个 skill |
| `docs/PLAN.md` | 契约编译结果、步骤状态、契约哈希与编译器版本 | construction | construction |
| `docs/build-log.md` | 尝试、验收、施工取舍、恢复与维护交接 | construction | construction / 维护者 |

PLAN、build-log、defense-log 只能引用 CR-xx，不再各自维护 CR 的第二份状态。其他文件中的 CR 状态均为生成视图，冲突时以 `docs/change-orders.md` 为准。

---

## 4. 编号与追溯模型

| 前缀 | 含义 | 必须被谁消费 |
|---|---|---|
| P-xx | 需求与成功目标 | F、V、竣工对照 |
| T-xx | 用户取舍裁决 | D/R/B、defense-log |
| W-xx | 候选或选定轮子 | D、F、I |
| F-xx | 运行时 / 用户流程节点 | I、V、最终流程图 |
| I-xx | 已答辩的实现单元与构建绑定 | construction 编译为 S |
| D-xx | 技术 / 产品决策 | F、I、PLAN 约束 |
| E-xx | 一手来源或原型证据包 | P/W/D/A/V |
| A-xx | 假设 | E 或施工 S0 |
| R-xx | 风险与处置 | F/I、PLAN 回退 |
| V-xx | 验证 | F/I、PLAN 验收 |
| B-xx | 边界与非目标 | F/I、PLAN 不做清单 |
| CR-xx | 变更单 | thesis / PLAN / logs 的共同锚点 |
| S-Ixx-vv-yy | 由 I、variant、segment 确定性生成的施工步骤 | PLAN / build-log |

所有编号分配后不复用、不重排。替代项保留原编号并写 `superseded-by`。这样用户决定、流程、实现和施工能完整追溯。

---

## 5. 三方答辩与需求权威

### 5.1 三个席位

| 席位 | 职责 | 禁止越权 |
|---|---|---|
| 需求方 | 定义价值、范围、优先级、不可牺牲项和可接受取舍 | 不凭偏好断言 API / 性能事实，不代替技术方选库 |
| 正方（学生） | 给出满足需求的最小完整流程和轮子优先实现契约 | 不扩需求证明价值，不默认自研，不强行解释 |
| 反方（导师） | 找出需求损失、流程缺口、事实错误、返工风险和不可验收项 | 不以个人偏好、完美主义或虚构未来制造硬伤 |

### 5.2 需求方真实性顺序

1. 当前用户的明确决定。
2. 用户确认过且未被取代的项目需求文档。
3. thesis 中带来源和确认记录的 P/T 条目。
4. AI 需求方代理只能做一致性核对，不能新增偏好、预算、法律判断或产品方向。

`docs/defense-charter.md` 属于用户预先确认的约束，不天然高于用户最新明确决定。冲突时登记 T-xx，记录用户决定以及被替代的 charter 版本。

### 5.3 P-xx 需求锚点格式

```yaml
id: P-01
class: anchor | negotiable
status: active | superseded | withdrawn
statement: <需求>
source: user-direct | docs/requirements.md#...
owner-quote: <尽量保留用户原话>
priority: must | should | could
confirmed-at: <日期与论文版本>
mutability: owner-only | evidence-challengeable
supersedes: []
success: <业务可观察结果>
```

若证据证明需求技术上不可能，不能让学生或导师偷偷弱化 P。必须拆成“事实发现 + 用户新选择”，由 T-xx 显式保留、替代或撤回 P。`negotiable` 仅表示用户允许比较取舍，不表示可以静默省略；P 进入 withdrawn / superseded 必须引用已 applied 的 T，并把排除结果落到 B 或残余风险落到 R。

### 5.4 T-xx 用户取舍格式

```yaml
id: T-01
status: pending | decided | applied | superseded
question: <真实价值取舍>
options:
  - id: A
    impact: { requirements: [P-01], flows: [F-02], verifications: [V-03] }
    benefit: <收益>
    cost-risk: <代价与风险>
student-recommendation: A
examiner-recommendation: B
selected-option: <空 | A | B>
applies-to: [P/F/I/D/R/V/B IDs]
decided-at: <日期或空>
applied-in-version: <论文版本或空>
applied-in-hash: <契约 hash 或空>
supersedes: []
```

未决定的 T-xx 使状态进入 `awaiting-owner`，不得降级成 A-xx、软伤或默认值。用户选择后先进入 `decided`；正方把选项实际落实到 applies-to 指向的契约字段并重算 hash 后，T 才能进入 `applied`。用户裁决后，除非出现足以改变决定的新证据，否则不得换皮重开。

---

## 6. 轮子优先、research 与 prototype

### 6.1 双方轮子侦察

scouting 发生在首版 D/I 定稿前，也可在后续异议中重开。正方必须给出最契合需求的成熟轮子；反方必须给出更合适的替代轮子，或用证据证明候选轮子的关键缺口。

W-xx 格式：

```yaml
id: W-01
kind: library | service | protocol | project-module | custom-build
identity: <包/服务/协议/项目内模块的规范名称>
version-range: <精确版本或范围>
source-revision: <官方链接、commit/tag、检查日期>
maturity: <维护状态、发布活跃度、采用情况>
required-apis: [<本项目实际使用的能力>]
fit: <已满足哪些 P/F>
gaps: <尚需哪些薄适配>
license-cost-privacy: <约束>
compatibility-evidence: [E-01]
pin-update-policy: <锁定与升级策略>
fallback-order: [W-02, W-03]
```

`fallback-order` 只允许引用 W-xx；自研同样必须建立 `kind: custom-build` 的 W 记录，不能写裸 `custom`。只有 D-xx 明确答辩过候选顺序、切换触发条件、等价接口和对应 I variant 时，S0 才能选择 fallback；否则更换 W、自研或改变关键接口必须走 CR。

### 6.2 一手来源规则

来源优先级：官方规范 / 官方文档 / 源码与维护记录 / 第一方 API 与基准 > 可信二手分析。二手内容和模型记忆只能用于找线索，关键结论必须回溯一手来源。

### 6.3 E-xx 可复现证据包

prototype 的“丢弃”只表示不进入生产，不表示删除证据。E-xx 必须保留：

```yaml
id: E-01
claim: <它支持或反驳什么>
kind: source | prototype | benchmark
source: <URL / 源码位置 / spike 路径>
checked-at: <日期>
environment: <OS、运行时、依赖版本>
command: <可重复命令>
inputs: <固定输入或夹具>
output-summary: <关键输出>
result-hash: <可选但推荐>
verdict: supports | refutes | partial
production-disposition: excluded | adopted-as-reference
cleanup-status: <临时资源是否清理>
redaction: <已移除的秘密/PII 类型；原值不得落盘>
```

E、defense-log、build-log 和 handoff 禁止写入 API key、密码、token 或非必要 PII；只保留脱敏类型、秘密管理器引用或环境变量名。

### 6.4 争议转实验

正反双方对 API 行为、性能、状态转换、兼容性或集成可行性发生事实争议时，不继续口头拉扯，生成最小 E-prototype：

- 写成可证伪问句。
- 使用候选 W 而非另造完整方案。
- 一条命令可运行。
- 默认无持久化；必须持久化时使用明确的 scratch / wipe 资源。
- 暴露完整相关状态。
- 预先写明什么结果支持哪一方。
- 结论回填 A/W/D/F/I，不自动进入生产。

prototype 不再受“轻量档禁止、标准档每轮一个”的机械预算限制。是否执行只看实质性、实验成本和能否明显缩短争论。

---

## 7. 可施工契约：F 与 I 分层

### 7.1 为什么不能直接 F→S

F 表达产品运行流程，S 表达代码、配置、迁移和集成的施工顺序。一个共享基础设施可能服务多个 F，一个 F 也可能由多个实现单元完成，因此 F→S 一对一是设计硬伤。

统一方案增加 I-xx：论文同时交付完整 F 运行流程和已答辩的 I 实现绑定；construction 从 I 确定性编译 S，同时保留 I↔F 多对多追溯。

### 7.2 F-xx 运行流程节点

F 使用结构化字段而非自由散文：

```yaml
id: F-01
name: <节点名>
serves: [P-01]
predecessors: [START]
preconditions: [<可判断条件>]
inputs:
  - name: <输入>
    type: <类型/格式>
actions: [<有顺序的动作>]
uses: [W-01, D-01]
outputs:
  - name: <输出>
    type: <类型/格式>
branches:
  - when: <互斥或有优先级的条件>
    target: F-02
  - default: true
    target: F-03
failures:
  - class: timeout | rejected | invalid | partial | unavailable
    when: <触发条件>
    compensation: <运行时补偿，不是施工回滚>
    target: F-ERR-01 | TERMINAL_FAILURE
terminal: false | success | failure
invariants: [<全程必须保持的状态>]
verifications: [V-02]
assumptions: [A-01]
risks: [R-01]
boundaries: [B-01]
```

分支必须有互斥 / 优先级说明和 default；循环必须写终止条件、最大重试或退避；每条路径必须抵达明确终态。运行时 compensation 与构建 / 部署 rollback 分开。

### 7.3 I-xx 实现绑定

```yaml
id: I-01
name: <实现单元>
kind: build | s0 | validation
realizes: [F-01, F-02]
validates: [A-01, W-01, V-03]
depends-on: [I-00]
change-boundary: <允许修改什么；明确不改什么>
deferred-verifications: [V-03]
variants:
  - id: base
    selected-when: default
    uses: [W-01, D-01]
    interface-equivalence: <与其他允许 variant 保持的等价契约>
    segments:
      - id: 01
        depends-on-segments: []
        actions: [<该施工段的明确动作>]
        artifacts: [src/..., config/...]
        interfaces: [<输入输出契约或 API>]
        side-effects: [none | db-migration | remote-call | file-write]
        idempotency: <重复执行策略或 key>
        build-rollback: <施工/部署失败如何恢复>
        segment-verifications: [V-01]
```

`kind: build` 的 I 必须 realizes 至少一个 F；`kind: s0` 用 validates 指向 A/W；`kind: validation` 用 validates 指向跨 I 的 integration/end-to-end/human V，它们也通过相同 segment 模型施工。共享前置能力必须建显式 I，不允许 construction 临时发明。

每个 variant 的每个 segment 都必须声明动作、产物、接口、副作用、幂等、构建回滚和 segment V；一个 segment 确定性编译为一个 S。build / s0 segment 的 V 必须能在该段结束时本地执行；validation segment 可使用 prerequisites 已满足的 integration / end-to-end / human V。允许 fallback 时，所有候选 W 必须在同一 I 下有已答辩 variant，并满足 interface-equivalence。S0 选择的是 contract 已包含的 variant 执行状态，不修改 thesis 语义或 contract hash。

### 7.4 V-xx 验证类型

```yaml
id: V-01
type: local | integration | end-to-end | human
covers: [P-01, F-01, I-01]
prerequisites: [I-01]
stage: after-I-01 | integration | final
command: <可执行命令或空>
observation: <human 时的明确检查点或可观察结果>
expected: <通过标准>
```

build / s0 I 只能把可在当前 segment 完成时执行的 `local` V 放到对应 S；integration / end-to-end / human V 必须由显式 `kind: validation` 的 I 持有，等 prerequisites 齐全后执行；human V 必须等用户明确确认。

### 7.5 契约完整性门

终局审计和 construction 门禁使用同一份 schema 校验，不允许两套口径：

- 每个 active P（包括 negotiable）至少被 F 和 V 覆盖；不覆盖只能通过 applied T 将其 withdrawn / superseded，并同步 B/R。
- 每个 F 的输入、输出、分支、失败、补偿、终态完整。
- 每个 F 至少被一个 `kind: build` 的 I 实现；build I 的 F 映射非空。
- 每个影响流程的 unresolved A/W 均有 `kind: s0` 的 I；每个跨 I V 均有 `kind: validation` 的 I。
- 每个 I variant 的每个 segment 都有 actions / artifacts / interfaces / side-effects / idempotency / segment V / build rollback，且 V 类型与 I kind 相容。
- 每个 fallback-order W 都有同 I 的等价 variant，且不存在裸 custom。
- 每个 D/A/R/V/B/W/E 被 F/I 引用，或显式声明为全局约束。
- 正常路径和关键失败路径均从 START 抵达终态。
- 所有 unresolved A 若影响 F/I，必须绑定 S0 与失败后的已答辩替代路径。
- 所有 owner-only T 已达到 `applied`；其 selected-option 已反映到 applies-to 条目和当前 contract hash。

schema 的唯一权威拟放在 `thesis-defense/references/contract-schema.md`。SKILL.md、examiner 和 construction 不复制校验规则，只引用它。

---

## 8. 可恢复的无上限答辩状态机

### 8.1 status

| status | 含义 | 能否施工 |
|---|---|---|
| draft | 需求 / 契约初稿未成形 | 否 |
| defending | 自动循环中 | 否 |
| awaiting-owner | 存在未决定 T-xx | 否 |
| redefending | CR 触发重辩 | 否 |
| blocked | 存在事实性硬伤且暂无可行路径 | 否 |
| passed | 诚实异议清零且完整性门通过 | 是 |
| conditional | 契约完整可编译，仅有用户明确签署的非致命 R/T 豁免及附加验证 | 是，需展示豁免 |

`conditional` 不得包含未决取舍、事实错误、证伪假设、缺失 F/I 字段或不可执行验证。用户不能用签字覆盖技术事实；只能接受边界明确、可缓解、不会破坏契约可编译性的风险。

### 8.2 phase

```text
intake
scouting
question-dispatch-pending
questions-recorded
evidence
prototype
answering
review-dispatch-pending
review-recorded
revising
final-audit-pending
final-audit-recorded
idle
```

frontmatter 同时持久化：`cycle`、`active-issue-ids`、`active-task-id`、`request-id`、`last-event-id`、`pending-T-ids`。

### 8.3 崩溃安全写入顺序

1. 为操作分配稳定 request / event ID。
2. 先把请求、返回结果或证据写入对应追加式制品。
3. 再更新 thesis frontmatter 指针与 phase。
4. 恢复时按 ID 幂等重放；已落盘返回不得重复派发。

`questioning` 不再同时表示“准备派发”和“问题已存在”，消除现有 crash window。

### 8.4 问题数量规则

任何正数的实质异议都必须处理；不再要求“至少两题才是有效轮”。零题进入终局审计候选，不自动宣布通过。

depth 只控制单轮上限和证据标准：轻量 / 标准 / 严酷都必须在最终审计覆盖全部契约面。

---

## 9. examiner 模式与持续收敛

examiner subagent 必须有显式 mode，而不是用同一问题模板承担所有任务：

| mode | 输入 | 输出 |
|---|---|---|
| scout | P/B、项目代码、现有 W/E | 候选 W、差距、来源 |
| question | 当前契约、已解决 issue 索引 | 通过三道门的新异议 |
| review | 问题、回答、修订 diff、证据 | resolved / unresolved-hard / soft / owner-tradeoff / invalid |
| final-audit | 当前 thesis + evidence manifest，不读辩论叙事 | schema 结果 + 新实质异议 |
| cr-audit | CR 与传递影响闭包、修订契约 | 受影响项是否全部重审 |

final-audit 使用干净上下文，只读当前契约和证据；其结果返回后，再由确定性步骤与 defense-log 做重复 / 已解决问题对账，避免历史叙事影响独立审计。

### 9.1 三道出题门

每条异议必须写：

1. **需求守恒门**：影响哪个 P/T/B？
2. **流程 / 施工实质门**：影响哪个 F/I/V？具体失败或返工是什么？
3. **最小修复门**：消除问题的最小契约改动是什么？有无成熟 W 可替代扩设计？

任一项答不出，不得判硬伤。

### 9.2 诚实异议门

满足以下任一条件的异议无效：

- 与 E 一手证据或可重复实验冲突，却无更强反证。
- 换措辞重复已解决问题，没有新证据或新影响。
- 依赖虚构需求、忽略 B 或削弱已确认 P。
- 重开用户已裁决 T，却无足以改变决定的新事实。
- 说不出受影响 P/F/I/V 与具体失败。
- 要求与证实风险不成比例的架构、抽象或防御代码。

### 9.3 停机规则

无总轮数上限。循环持续：question → evidence / prototype / owner decision → minimal revision → review → full replay。

只有同时满足以下条件才进入 passed / conditional：

- review 中无 unresolved-hard 和 pending owner tradeoff。
- contract-schema 全部通过。
- final-audit 无通过三道门的新异议。
- final-audit 的全部异议经诚实异议门复核后为空。

自然语言总结：**需求未丢、流程与实现契约完整、真实取舍已有主人，反方若再反对只能忽略证据、重复旧题或虚构需求。**

---

## 10. construction 的确定性编译与最小施工

### 10.1 开工门禁

所有非 done 状态启动 / 恢复时都校验：

- thesis status 为 passed / 合法 conditional。
- contract-version、schema-version 受支持。
- contract-hash 与 PLAN 记录一致。
- PLAN compiler-version 一致。
- change-orders 无 blocking CR。
- thesis 契约再次通过 schema。

planning 状态也必须校验，不能只重新展示旧计划。旧论文必须先迁移和重审。

### 10.2 I→S 编译

- 每个 I 的选定 variant 中，一个 segment 生成一个 `S-Ixx-<variant>-<segment>`。
- 未声明多 segment 的 I 仍使用必备 `base/01`，例如 `S-I01-base-01`。
- I 的 depends-on 生成施工 DAG；共享前置本身是 I，不允许编译器临时创造语义步骤。
- `kind: s0` 和 `kind: validation` 与 build I 使用同一 ID、DAG、state 和恢复规则；不再产生无主的 S0 / V 步骤。
- segment V 放到对应 S；integration / e2e / human V 由其 validation I 在 prerequisites 完成后执行。
- PLAN 保存 thesis version、contract hash、schema version、compiler version 和 I↔S 映射表。

PLAN 还必须保存 `plan-structure-hash`。它只覆盖不可变计划结构：contract hash、schema/compiler version、DAG、I↔S/variant/segment 映射、步骤规格、V 放置与回滚声明；排除步骤 state、attempt、时间、命令输出、checkbox 和日志。hash 规范与 fixtures 同样由 contract-schema 引用的 compiler 规范唯一规定。

construction 可以补充运行环境中的具体命令，但不能在 segment 外自行拆分，也不能改变 P/T/W/F/I/D/V/B 语义。若某 segment 大到无法作为一个可恢复、可验收步骤，说明 I 契约不完整，必须退回答辩补 segments。初次计划确认也不是重新设计窗口；用户要求改变语义必须走 CR。

### 10.3 minimal-diff 范围门

SELECT 时写清本步最小成功条件。EXECUTE 遵守：

1. 不做本步 change-boundary 外的工作。
2. 不为假想未来添加抽象、配置、兼容层或错误处理。
3. 内部信任已验收前置；只在用户输入、外部 API 等系统边界验证。
4. 优先改真实代码，不创建平行 v2、旁路或未答辩 shim。
5. 匹配周围风格；注释只记录约束和非显然不变量。

薄适配若已由 D/I 答辩，就不是禁止的兼容层；只有未计划 shim、重复版本或语义改变才触发 CR。

VERIFY 前逐 hunk 问：“没有这一块，本步是否会失败？”

| 回答 | 动作 |
|---|---|
| 会失败 | 保留 |
| 不会，但是真实独立问题 | 回退并记“待议 / 后续建议” |
| 不会，只是风格 | 直接回退 |

### 10.4 可恢复步骤状态机

每个 S 不再只靠 checkbox，必须持久化：

```text
pending → selected → executing → verifying → complete
                         ↘ blocked
complete → invalidated（CR 影响）
```

每次尝试记录 attempt-id、前置快照、命令、输出、idempotency key、side-effect 状态和 compensation。未完成步骤恢复时：

- 无副作用且幂等 → 可重放同 attempt 或新 attempt。
- 有远程调用 / 迁移 / 部分写入 → 先检查 postcondition；必要时执行 I 中的补偿，禁止无脑重跑。
- complete 只有 VERIFY 证据和 build-log 都落盘后成立。

checkbox 可作为展示视图，但步骤 state 才是恢复权威。

### 10.5 S0 边界

S0 由 `kind: s0` 的 I 表达，只验证 F/I 引用的 unresolved A 或 W 在当前环境的适配性。结果：

- 命中 D 预先答辩的 fallback-order → 选择同一 I 中已存在、接口等价的 variant，记录 E；这是 PLAN 执行状态，contract hash 不变。
- 不在预案内的换轮子 / 自研 / 接口变化 → blocking CR。
- 假设证伪且无替代路径 → blocking CR，不得用户强行覆盖事实。

---

## 11. CR 回炉闭环

### 11.1 单一台账

`docs/change-orders.md` 是唯一 CR 状态源：

```yaml
id: CR-01
status: proposed | defending | approved | rejected | waived | applied | verified | closed
trigger: <S/E/事实>
falsified: [D-01, A-02]
contract-before: <hash>
impact-seed: [F-02, I-03]
impact-closure: [P/F/I/W/D/E/A/R/V/B/S IDs]
waiver-eligible: false
resolution-E: <证明修复或拒绝理由的 E，或空>
waiver-T: <用户非致命风险裁决，或空>
added-V: [<豁免后的附加验证>]
contract-after: <新 hash 或空>
plan-structure-after: <新 plan-structure-hash 或空>
final-audit-event: <审计事件 ID 或空>
```

状态转换与权限：

| 转换 | 写入方 | 是否阻塞施工 | 前置 |
|---|---|---|---|
| 新建 → proposed | construction / thesis-defense | 是 | 触发事实和 impact-seed 已落盘 |
| proposed → defending | thesis-defense | 是 | impact closure 已计算 |
| defending → approved | thesis-defense final audit | 是 | 新契约方案通过审查，待施工侧应用 |
| defending → rejected | thesis-defense final audit | 否 | resolution-E 证明误报、重复或不成立 |
| defending → waived | 真实用户 + thesis-defense | 否 | waiver-eligible=true、waiver-T 已 applied、added-V 非空；不得用于事实阻塞 |
| approved → applied | construction | 是 | contract-after 与重编 PLAN 已落盘，受影响 S 已 invalidated |
| applied → verified | construction | 否 | 回滚/重做和 added V 全通过，允许按新计划继续；待完成台账收尾 |
| verified / rejected / waived → closed | construction | 否 | contract hash 与 plan-structure-hash 同步、台账引用完整、final-audit-event 有效 |

construction 门禁把 proposed / defending / approved / applied 视为 blocking。`closed` 不是任意收尾标签，必须满足表中前置；waived 通过 T/V 保留可审计责任链。

### 11.2 传递影响闭包

回炉不能只审“被点名章节”。从证伪对象沿引用图计算传递闭包：P↔F↔I↔W/D/A/R/V/B→S。重辩范围可以聚焦，但终局必须重跑完整 schema 和 final-audit。

已完成且受影响的 S 标记 `invalidated`，依据 build rollback / compensation 回退或重新验收；不能只修编号引用后继续。

### 11.3 用户豁免边界

事实错误、证伪关键假设、缺失流程、不可验收、数据损坏或安全阻塞不可强行复工。只有 schema 完整、不会使 P/F/I 失效的非致命 R 才能由 T 签署豁免，并附加 V。

---

## 12. handoff 与施工理念

### 12.1 答辩 → 施工摘要

摘要由当前 ID 与 contract hash 生成，不能手写漂移：

```markdown
## 施工交接摘要（contract <hash>）
- 需求锚点：P-...
- 用户裁决：T-...
- 选定轮子与边界：W-... / D-...
- 运行流程：F-...
- 实现绑定：I-...
- 施工前验证：A-... → S0
- 已接受风险：R-...（对应 T/V）
- 不做项：B-...
- blocking CR：无
```

### 12.2 施工过程记录

只有非显然且未来维护者可能误改的取舍才写：

```markdown
- 施工取舍：复用 W-01，只实现 I-02 的薄适配；刻意未做 B-03，因为不服务 P-01。
```

记录为什么复用轮子、为什么不重构周边、哪些能力被刻意省略、实际与契约的偏差及 CR、哪些扩展点是有意留下的。

每步末尾可有简短“下一步 / 未决”导航行，但它不是恢复权威；恢复仍必须读取 PLAN state、契约 hash、CR 台账并对账。

### 12.3 竣工 → 维护交接

```markdown
## 施工理念与维护交接
- 需求追溯：P → F → I → S → V
- 轮子责任边界：W/D/I
- 自研部分及不可替代证据：E/I
- minimal-diff 取舍与刻意未实现：B / 待议
- 已知风险与用户裁决：R/T
- 安全扩展路径与必须回炉的红线：...
```

---

## 13. 旧契约迁移

旧 P/D/A/R/V/B 文档不能仅补 frontmatter 后冒充 v4：

1. 保留原编号，补 P 来源 / 权威字段。
2. 建立 W/E/T（如适用）。
3. 将 §2 prose 转成 F 结构化运行流程。
4. 建立 I 实现绑定和 F↔I 关系。
5. 给 V 补类型、前置和阶段。
6. 跑 schema、持续答辩和 final-audit。
7. 通过后写 contract-version/hash；construction 才接受。

不存在“新字段全部可选”的兼容承诺。contract-version 4 的必填项必须齐全；旧 contract 走旧 compiler 或显式迁移，不能静默猜测。

---

## 14. 文件级实施地图

### thesis-defense

| 文件 | 改动 |
|---|---|
| `SKILL.md` | 三方动态循环、无轮数上限、status/phase、owner queue、examiner modes、终局审计、v4 产物 |
| `references/thesis-template.md` | v4 frontmatter、P/T/W/E/F/I/V schema、生成式交接摘要、迁移规则 |
| `references/contract-schema.md`（新） | 唯一完整性规则和字段定义 |
| `references/requirement-protocol.md`（新） | 需求方权威、P/T、charter 冲突、不可行需求的用户重决策 |
| `references/evidence-protocol.md`（新） | scout、W/E、一手来源、prototype 复现包 |
| `references/examiner-protocol.md` | 五种 mode、三道门、诚实异议门、任意正数问题有效、全表面 final audit |
| `references/verdict-rules.md` | 无轮数上限、awaiting-owner/blocked/conditional 语义、崩溃恢复、终局停机、CR 全量审计 |
| `agents/examiner.md` | mode 化输入输出；不得代替需求方；scout / final / CR 合约 |

### construction

| 文件 | 改动 |
|---|---|
| `SKILL.md` | v4 门禁、I→S compiler、hash 校验、minimal-diff、CR 台账、维护交接 |
| `references/plan-template.md` | compiler metadata、I↔S 映射、V 分层、步骤 state / attempt、确定性 ID |
| `references/step-protocol.md` | side-effect 恢复、逐 hunk 门、S0 fallback、CR impact closure、invalidated 重做 |

### 根文档

| 文件 | 改动 |
|---|---|
| `README.md` | 新流水线、六制品、contract 版本与迁移说明 |
| 两个 skill README | 与新状态、编号、恢复和产物保持一致 |

所有上述文件应在一个原子版本中发布；不能先让 thesis 产 v4 而 construction 仍按旧 prose 映射，也不能让 construction 要求 v4 而 thesis 尚未生成。

---

## 15. 实施顺序

- [ ] 1. 定义 `contract-schema.md`、contract-version 4、ID grammar 与 hash 规范。
- [ ] 2. 改 thesis-template，加入 P/T/W/E/F/I/V 和生成式 handoff。
- [ ] 3. 改 requirement / evidence / examiner / verdict 协议与 examiner 五种 mode。
- [ ] 4. 改 thesis-defense SKILL 状态机和无上限收敛循环。
- [ ] 5. 定义 I→S compiler、PLAN metadata、步骤状态与副作用恢复。
- [ ] 6. 改 construction SKILL、plan-template、step-protocol 和 CR 单一台账。
- [ ] 7. 更新全部 README 和旧契约迁移路径。
- [ ] 8. 执行状态转换、崩溃窗口、CR、迁移和端到端 dry-run。

## 16. 验收矩阵

| 场景 | 必须结果 |
|---|---|
| 第 8 轮出现一个新硬伤 | 继续处理；不因轮数或“一题不足两题”停机 |
| 问题派发前 / 返回后崩溃 | 按 request/event ID 幂等恢复，不丢题、不重复派发 |
| 出现成本 vs 体验取舍 | 状态 awaiting-owner；生成 T；用户决定前不得通过 |
| 用户要求忽略被证伪 API | 拒绝用签字覆盖事实；进入 blocked / CR |
| 导师换皮重复旧题 | 无新证据则诚实异议门撤题；有强反证则重开 |
| 正方准备自研但有成熟轮子 | 必须比较 W 的原样复用 / 薄适配；自研给缺口证据 |
| API 行为争论 | 生成 E-prototype 并保留可复现包，不继续口头空辩 |
| F 被多个共享模块实现 | 通过 F↔I 多对多表达，construction 不临时发明共享步骤 |
| V 是端到端验证 | 等 prerequisites 齐全后生成独立 S，不错误放入早期 local 步骤 |
| planning PLAN 对应旧 thesis hash | 拒绝确认，重新迁移 / 编译 |
| 迁移步骤中断 | 检查 postcondition / idempotency / compensation，不无脑重跑 |
| S0 命中预答辩 fallback | 可按 D 切换并记 E；未预答辩切换必须 CR |
| CR 修改共享 I | 计算传递闭包，影响 S 标 invalidated，完整 final-audit 后复工 |
| 旧 passed thesis 请求开工 | 因缺 v4 contract 拒绝并指路迁移答辩 |
| 维护者接手 | 只读生成式 handoff、PLAN、build-log 即可解释 P→F→I→S→V、轮子边界和红线 |

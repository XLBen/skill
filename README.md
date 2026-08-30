# contract-review & construction skills

一套"先评审、后施工"的 opencode skill：把需求评审成机器可校验的契约，再按契约确定性施工、逐步验收、全程留证。

| Skill | 职责 |
|---|---|
| contract-review | 评审需求，产出机器可校验的 P/F/I/V 契约，保留甲方决策 |
| construction | 按契约编译 PLAN，逐步执行、验收、留证；变更走 CR |
| reviewer | 子 skill：独立评审席（只读），由主 skill 调用，也可直接触发 |
| step-executor | 子 skill：隔离执行单个步骤，由 construction 调用 |

## 安装

1. 在目标项目根目录的 `opencode.json` 注册本仓库（4 个 skill 全部生效，无需复制任何文件）：

   ```json
   {
     "skills": {
       "paths": ["E:/MISC/代码项目/skill"]
     }
   }
   ```

2. 重启 opencode。

要求 Python 3.8+；纯本地运行，无第三方依赖，无遥测。若整体复制到目标项目，必须保持各 skill 目录与 `scripts/check.py` 的相对布局。

## 触发方式

两种触发完全等效：

- **定向触发**：斜杠指令，短、准、无歧义，推荐。
- **非定向触发**：自然语言，随口就说，agent 自动识别意图。

### 定向触发（斜杠指令）

| 指令 | 作用 | 示例 |
|---|---|---|
| `/评审 <方案>` | 评审需求，产出契约 | `/评审 我要做一个 CLI 待办工具，要求……` |
| `/论证 <设计>` | 论证一个既有设计 | `/论证 用 SQLite 存配置` |
| `/质疑 <想法>` | 苏格拉底式质疑（轻量，可无契约） | `/质疑 这个缓存方案真能提速吗` |
| `/评估 <项目>` | 评估项目可行性 | `/评估 这个库值得引入吗` |
| `/开工` | 校验契约门 → 编译 PLAN → 施工 | `/开工` |
| `/继续` | 中断后恢复施工 | `/继续` |
| `/竣工` | 对账 reconcile + 汇聚审计 | `/竣工` |
| `/复盘` | 竣工后基于证据的复盘 | `/复盘` |
| `/变更 <事实>` | 报告契约与现实的偏差，建 CR | `/变更 接口 X 实际不存在` |

指令后面可以直接带开关，例如 `/评审 用 full，checkpoints`、`/开工 autonomous`。

### 非定向触发（自然语言）

| 你说 | 等效指令 |
|---|---|
| "评审方案：我要做一个 xxx……"、"需求评审" | `/评审` |
| "论证方案：帮我论证这个设计……" | `/论证` |
| "苏格拉底式质疑一下这个想法……" | `/质疑` |
| "评估一下这个项目/可行性" | `/评估` |
| "开工"、"施工"、"按契约开工" | `/开工` |
| "继续施工" | `/继续` |
| "竣工对账"、"收尾" | `/竣工` |
| "复盘一下" | `/复盘` |
| 直接陈述事实，如"接口 X 实际不存在" | `/变更` |

## 使用流程

### 第 1 步：评审需求

> /评审 我要做一个 xxx，要求是 ……

接下来会发生什么：

1. agent 先确认流程重量与交互方式（见"用户开关"），不确定就直接说"用 light，checkpoints"。
2. agent 逐个提出决策问题（一次一个），你逐条回答；不想决策就说"给我推荐项"。
3. 有事实争议时，agent 在预算内做调研或可证伪实验，证据落到 `docs/evidence/`。
4. 独立评审无存活硬伤后，`docs/contract.md` 置为 `passed`（或甲方签字的 `conditional`）。

### 第 2 步：开工

> /开工

流程依次为：契约/hash/CR 门校验 → 生成并确认 `docs/PLAN.md` 与变体选择 → 按依赖顺序逐步执行。中断了就说 `/继续`（或"继续施工"）。

- `checkpoints`/`stepwise` 模式下每步先给你摘要再动手；`autonomous` 只在强制检查点询问。
- 每步完成前 agent 会原样运行该步声明的验收命令 V，输出持久化为证据；V 失败就在段内修复重跑。
- `direct` profile 走快速路径：单轮出契约、单轮评审，但校验与检查点底线不变。

### 第 3 步：竣工

> /竣工

全部步骤完成后自动执行竣工对账（`reconcile`）并派独立 `converge-audit`：矩阵状态 `clean` 才能竣工；`incomplete` 的每条 finding 必须解决或挂 CR。通过后 `docs/PLAN.md` runtime 置 `done`，build-log 追加维护交接，可选 `/复盘`。

### 中途发现契约有问题

> /变更 接口 X 实际不存在

agent 会建立 CR（`docs/change-orders.md`）阻断普通施工；评审批准后仅在该 CR 的影响闭包内重编译、失效、重做。不存在"让事实性失败硬过"的路径。

## 用户开关

| 开关 | 取值 | 用法 |
|---|---|---|
| profile | `direct` / `light` / `full` | `/评审 用 full`。direct=本地可逆小改动；light=默认；full=跨模块/不可逆/涉隐私花费 |
| 交互模式 | `autonomous` / `checkpoints` / `stepwise` | `/开工 autonomous` 少打断；stepwise 每步确认 |
| 预算 | audit / research / prototype 数值 | 如"调研预算 3 次"。耗尽即暂停等你决定，绝不自动放行 |
| 强制检查点 | — | 新增/删除需求、花钱、隐私、不可逆操作：任何模式下都会先问你 |

## Skill 调用 Skill

```text
/评审 /论证 /评估 ──> contract-review ──调用──> reviewer（质疑/终审/CR审计）
                              │ 契约 passed 后 next-skill
                              v
/开工 /继续 /竣工 ──> construction ──调用──> step-executor（隔离执行单步）
                                     └─调用──> reviewer（步骤评审门/汇聚审计）
/质疑 ───────────> reviewer（直接调用）
```

子 skill 从主 skill 分离出来，主 skill 通过 skill 工具按需调用；子 skill 也可被用户单独触发（如 `/质疑`）。

## 产物文件

| 文件 | 作用 |
|---|---|
| `docs/contract.md` | 契约：可读说明 + canonical JSON |
| `docs/review-log.md` | 评审记录 |
| `docs/evidence/` | 可复现实证 |
| `docs/change-orders.md` | CR 状态唯一来源 |
| `docs/PLAN.md` | 编译产物 + 运行投影 |
| `docs/build-log.md` | 施工与维护证据 |
| `docs/workflow-events.jsonl` | append-only 事件账本 |
| `docs/workflow-state.json` | 状态投影（CAS revision） |

## 引擎命令（手动核查用）

日常由 agent 自动调用；需要人工检查时在目标项目根目录运行：

```powershell
python scripts/check.py contract docs/contract.md                       # 校验契约并显示 hash
python scripts/check.py init docs/contract.md docs/workflow-state.json  # 初始化状态投影（每契约一次）
python scripts/check.py compile docs/contract.md docs/PLAN.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python scripts/check.py reconcile docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python scripts/check.py change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python scripts/check.py impact docs/contract.md I-01                    # 计算影响闭包
python scripts/check.py --selftest                                     # 引擎自测（25 项）
```

完整合法示例见 `tests/fixtures/`。契约与引擎规则以 `contract-review/references/contract-schema.md` 为准。

## License

MIT.

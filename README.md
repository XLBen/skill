# contract-review & construction skills

两个配套 opencode skill：先评审需求、产出机器可校验的契约（contract-review），再按契约施工、逐步验收并留证（construction）。

| Skill | 对 agent 说 | 结果 |
|---|---|---|
| contract-review | "评审方案：……"、"论证方案：……"、"需求评审"、"苏格拉底式质疑……" | `docs/contract.md`（status: passed/conditional）+ 独立评审记录 |
| construction | "开工"、"施工"、"继续施工" | `docs/PLAN.md` 编译执行、验收证据、竣工对账 |

## 安装

1. 在目标项目根目录的 `opencode.json` 注册本仓库：

   ```json
   {
     "skills": {
       "paths": ["E:/MISC/代码项目/skill"]
     }
   }
   ```

2. （可选）安装两个 subagent：

   ```powershell
   Copy-Item "contract-review/agents/reviewer.md" ".opencode/agent/reviewer.md"
   Copy-Item "construction/agents/step-executor.md" ".opencode/agent/step-executor.md"
   ```

3. 重启 opencode。

要求 Python 3.8+；无第三方依赖，纯本地运行，无遥测。若整体复制到目标项目，必须保持 `contract-review/`、`construction/`、`scripts/check.py` 的相对布局。

## 使用流程

### 第 1 步：评审需求（contract-review）

对 agent 说，任一均可：

> 评审方案：我要做一个 xxx，要求是 ……
> 论证方案：帮我论证这个设计 ……
> 苏格拉底式质疑一下这个想法：……

接下来会发生什么：

1. agent 先确认流程重量与交互方式（见下方"用户开关"），不确定就直接说"用 light，checkpoints"。
2. agent 逐个提出决策问题（一次一个），你逐条回答；不想决策就说"给我推荐项"。
3. 有事实争议时，agent 在预算内做调研或可证伪实验，证据落到 `docs/evidence/`。
4. 独立评审无存活硬伤后，`docs/contract.md` 置为 `passed`（或甲方签字的 `conditional`）。

产物：`docs/contract.md`、`docs/review-log.md`、`docs/evidence/`、`docs/change-orders.md`、`docs/workflow-events.jsonl`、`docs/workflow-state.json`。

### 第 2 步：开工（construction）

对 agent 说：

> 开工
> 继续施工        （中断后恢复也用这句）

流程依次为：契约/hash/CR 门校验 → 生成并确认 `docs/PLAN.md` 与变体选择 → 按依赖顺序逐步执行：

- `checkpoints`/`stepwise` 模式下每步先给你摘要再动手；`autonomous` 只在强制检查点询问。
- 每步完成前 agent 会原样运行该步声明的验收命令 V，输出持久化为证据；V 失败就在段内修复重跑。
- `direct` profile 走快速路径：单轮出契约、单轮评审，但校验与检查点底线不变。

### 第 3 步：竣工

全部步骤完成后 agent 自动执行竣工对账（`reconcile`）并派独立 `converge-audit`：

- 矩阵状态 `clean` 才能竣工；`incomplete` 的每条 finding 必须解决或挂 CR。
- 通过后 `docs/PLAN.md` runtime 置 `done`，build-log 追加维护交接与可选复盘。

### 中途发现契约有问题

直接说明事实（例如"接口 X 实际不存在"）。agent 会建立 CR（`docs/change-orders.md`）阻断普通施工；评审批准后仅在该 CR 的影响闭包内重编译、失效、重做。不存在"让事实性失败硬过"的路径。

## 用户开关

| 开关 | 取值 | 用法 |
|---|---|---|
| profile | `direct` / `light` / `full` | 评审开始时说"用 full"。direct=本地可逆小改动；light=默认；full=跨模块/不可逆/涉隐私花费 |
| 交互模式 | `autonomous` / `checkpoints` / `stepwise` | "autonomous 模式"少打断；stepwise 每步确认 |
| 预算 | audit / research / prototype 数值 | 如"调研预算 3 次"。耗尽即暂停等你决定，绝不自动放行 |
| 强制检查点 | — | 新增/删除需求、花钱、隐私、不可逆操作：任何模式下都会先问你 |

## 引擎命令（手动核查用）

日常由 agent 自动调用；需要人工检查时在目标项目根目录运行：

```powershell
# 校验契约并显示 contract hash
python scripts/check.py contract docs/contract.md

# 初始化状态投影（每份契约一次）
python scripts/check.py init docs/contract.md docs/workflow-state.json

# 确定性编译 PLAN
python scripts/check.py compile docs/contract.md docs/PLAN.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl

# 校验 PLAN（含运行时证据绑定）
python scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl

# 竣工对账：P→F→I→S→V 覆盖矩阵 + 证据 hash 绑定 + 阻断 CR
python scripts/check.py reconcile docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl

# 校验 CR 台账
python scripts/check.py change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl

# 计算节点影响闭包
python scripts/check.py impact docs/contract.md I-01

# 引擎自测（25 项，改动引擎后必跑）
python scripts/check.py --selftest
```

完整合法示例见 `tests/fixtures/`；负例由 `--selftest` 在内存构造。

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

契约与引擎规则以 `contract-review/references/contract-schema.md` 为准。

## License

MIT。

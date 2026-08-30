# opencode 契约评审与施工 skills

本仓库包含一组配套 skill，把需求论证、实现契约、施工计划、执行证据和变更回炉连接成可恢复工作流。

| Skill | 职责 |
|---|---|
| [contract-review](contract-review/) | 保护用户需求，建立 P/F/I/V 契约，并由独立评审审查语义硬伤 |
| [construction](construction/) | 校验并确定性编译契约，按 DAG 执行步骤，保存验收和恢复证据 |

## 用户控制

- `direct / light / full` 控制流程重量，不降低覆盖和验收底线。
- `autonomous / checkpoints / stepwise` 控制交互频率。
- 审计、调研和实验均有预算；预算耗尽只会暂停，不会自动通过。
- 扩大范围、产生费用、暴露隐私、执行不可逆操作或做价值取舍时，必须交还用户决定。

## 工作流

```text
用户需求
  -> contract-review：P/F/I/V 契约 + 独立审查 + contract hash
  -> construction：确定性 PLAN + variant 选择 + DAG 执行 + 验收证据
  -> 发现契约问题：CR 台账 -> 影响闭包 -> 回炉 -> 限定恢复
```

结构、hash、状态和事件由引擎校验；自然语言是否真实、条件是否合理，仍由独立语义审查判断。

## 主要制品

| 文件 | 作用 |
|---|---|
| `docs/contract.md` | 可读说明和 canonical JSON contract |
| `docs/review-log.md` | 评审记录 |
| `docs/evidence/` | 可复现实证 |
| `docs/change-orders.md` | CR 状态唯一来源 |
| `docs/PLAN.md` | 确定性编译结果和运行投影 |
| `docs/build-log.md` | 施工与维护证据 |
| `docs/workflow-events.jsonl` | append-only 事件账本 |
| `docs/workflow-state.json` | 带 CAS revision 的状态投影 |

## 引擎

要求 Python 3.8+，无第三方依赖。纯本地运行，不联网、不上报遥测：所有校验、哈希和事件都留在你的项目目录里。

```powershell
python scripts/check.py contract docs/contract.md
python scripts/check.py init docs/contract.md docs/workflow-state.json
python scripts/check.py compile docs/contract.md docs/PLAN.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python scripts/check.py reconcile docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python scripts/check.py change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python scripts/check.py impact docs/contract.md A-01
python scripts/check.py --selftest
```

`reconcile` 在竣工前输出 P→F→I→S→V 覆盖矩阵：运行状态、证据是否绑定当前 hash、dormant 变体与阻断 CR。结构闭合交给引擎；"代码是否真的满足契约意图"由 `converge-audit`（见 reviewer-protocol）独立判断。

完整合法示例位于 `tests/fixtures/`。负例由 `--selftest` 在内存中构造，不额外保存重复文件。

## 安装

两个 skill 目录各含一个 `SKILL.md`，遵循 [Agent Skills](https://agentskills.io) 的文件夹约定（frontmatter + 正文指令），兼容 opencode 的 `skills.paths` 注册，也可以被任何按目录扫描 skill 的 agent 加载。

推荐在目标项目的 `opencode.json` 注册本仓库：

```json
{
  "skills": {
    "paths": ["E:/MISC/代码项目/skill"]
  }
}
```

也可以复制 `contract-review/`、`construction/` 和 `scripts/check.py` 到目标项目——三者必须保持相对布局（SKILL.md 里的引擎命令按 `scripts/check.py` 相对路径调用），不要只复制单个 skill 目录。可选安装两个 subagent：

```powershell
Copy-Item "contract-review/agents/reviewer.md" "<目标项目>/.opencode/agent/reviewer.md"
Copy-Item "construction/agents/step-executor.md" "<目标项目>/.opencode/agent/step-executor.md"
```

`step-executor` 是可选的隔离执行器：`checkpoints`/`stepwise` 或 `full` profile 下，每个已选步骤派发一个只带该步骤规格和精确 V 的新 subagent，主会话只负责状态、账本和事件记录（见 step-protocol 的 Isolated Execution）。

修改 skill、agent 或协议文件后需要退出并重启 opencode。

## 文件结构

```text
construction/
contract-review/
scripts/check.py
tests/fixtures/
README.md
```

契约与引擎规则以 `contract-review/references/contract-schema.md` 为准。

## License

两个 skill 均使用 MIT License。

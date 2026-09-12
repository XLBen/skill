# Subagent Dispatch Templates

> When to read: before composing any subagent dispatch or adjudicating a
> subagent's return message.

所有派发与返回使用固定格式，方便 GLM 稳定执行与主控机械校验。字段缺失
的派发是缺陷；返回不合式的结果按 needs_context 处理，不猜测填充。

## Dispatch Template

```text
DISPATCH
task_id: <T-NN, 对应 dispatch record>
role: research|worker|reviewer|test-author|step-executor
goal: <一句话目标与验收条件，可观察、可判定>
inputs:
  - <文件路径或确切数据；标注哪些是必读约束>
write_scope: <允许修改的路径；reviewer/research 为 read-only>
baseline: <当前产物基线：commit/hash/目标卡状态>
dependencies: <依赖的先前任务结论或接口决定；无则 none>
verification: <要求执行的验证命令与预期；无则 none>
return_format: <RESULT 结构，见下>
stop_conditions: <何时必须停下返回 blocked；至少含权限不足、范围外改动需求>
constraints:
  - <禁止递归派发子代理>
  - <不修改 write_scope 之外的文件>
  - <角色特定约束，如 reviewer 只读>
```

写法要求：

- dispatch 只描述一个任务，不粘贴会话历史或先前任务摘要；接口结论以
  dependency 条目精炼传入。
- 精确值（数字、签名、测试用例）放在 inputs 的文件里或直接内联，不写
  “参见上文”。
- reviewer 派发额外包含 `ACCEPTANCE_HANDOFF` 全文与 `pua_stage_id`，
  并要求其加载 `pua` skill 与对应检查卡，返回 `issues` 与
  `pua_acceptance`（见 `../contract-review/references/reviewer-protocol.md`）。
- worker/research 派发明确单文件或单工作包；不确定影响面时先派
  research 缩小范围。

## Result Template

```text
RESULT
task_id: <T-NN>
status: done|needs_context|blocked
summary: <实际完成内容，一到三句>
artifacts:
  - <修改的文件或发现的位置>
verification:
  command: <实际执行的命令>
  result: <通过/失败及关键输出位置；无则 none>
open_issues: <未解决问题；无则 none>
```

- `done` 要求 verification 非空（纯调研任务报告发现位置）。
- `needs_context` 必须列出缺失的具体输入。
- `blocked` 必须给出可核实的原因与最小解锁动作。
- reviewer 返回沿用 reviewer-protocol 的结构化 JSON（`issues` +
  可选 `pua_acceptance`），不使用 RESULT 模板。

## Fix-Round Template

返修轮复用原 dispatch 的 task_id，追加：

```text
FIX-ROUND
task_id: <T-NN>
round: <N，轻量上限 3>
findings:
  - <逐条待修复项，来自 reviewer 或主控复验>
prior_attempts: <已试方法一句话；round>=2 时必填>
```

主控记录每轮结果到 dispatch record；round 超限换 fresh seat 并携带
全部 findings 与 prior_attempts。

## Dispatch Record Sync

每次派发、返回、跳过都在同一次操作里同步
`.opencode/mvp/<goal-slug>.dispatch.json`（schema 见
`subagent-orchestration.md`）。恢复执行时先读该文件再决定是否重新派发。

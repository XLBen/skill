---
name: construction
description: Use when the user types /开工, /继续, /竣工, /复盘, /变更 (directed triggers) or natural language such as 开工/施工/按契约开工/继续施工/竣工对账/复盘 (non-directed triggers) to execute a contract-review contract. Validates contract/hash/CR gates, deterministically compiles every I variant and segment, executes selected steps with recovery evidence, and routes semantic change through CR. Not for writing the contract or unrelated ad-hoc coding.
license: MIT
metadata:
  language: "zh-CN"
  produces: "docs/PLAN.md, docs/build-log.md, docs/workflow-events.jsonl"
  requires-skill: "contract-review"
  calls-skills: "step-executor, reviewer"
  commands: "/开工, /继续, /竣工, /复盘, /变更 <事实>"
---

# Construction

Compile the accepted contract; do not reinterpret it. Runtime execution may
bind commands and select reviewed variants, but semantic change returns through
CR.

## Commands

| 指令 | 作用 |
|---|---|
| `/开工` | 校验契约门 → 编译 PLAN → 确认 → 施工 |
| `/继续` | 中断后恢复：重跑门校验，从事件账本续建 |
| `/竣工` | 强制 `reconcile` 对账 + `converge-audit`，置 `done` |
| `/复盘` | 竣工后基于证据的复盘（见 retro-protocol） |
| `/变更 <事实>` | 报告契约与现实的偏差，建立 CR 阻断普通施工 |

指令可后缀开关，如 `/开工 autonomous`。非定向触发（自然语言）与指令完全
等效："开工"、"施工"、"按契约开工"、"继续施工"、"竣工对账"、"复盘一下"；
直接陈述契约与现实不符的事实（如"接口 X 实际不存在"）即触发变更流程。

## Skill Calls

This skill calls other skills through the skill tool instead of inlining
their prompts:

- Load the **step-executor** skill (`name: step-executor`) for isolated step
  execution under `checkpoints`/`stepwise` or `full` profile. Pass exactly
  one compiled step spec plus its exact V commands; expect raw outputs back.
  Record the executor's `subagent_id` in the attempt event. The controller
  (this skill) alone owns state, the ledger, and event recording.
- Load the **reviewer** skill (`name: reviewer`) for the per-step review gate
  and for `converge-audit` at Finish, bound to the reconcile
  `contract_hash`/`plan_structure_hash`.
- On gate failure caused by contract defects, suggest `/变更 <事实>` or load
  the contract-review skill for CR adjudication.

## Gate

Before every start or resume:

1. Read `../contract-review/references/contract-schema.md` when the
   paired skill is available; otherwise use the installed shared copy.
2. Run `python scripts/check.py contract docs/contract.md`.
3. Require `passed` or legal `conditional`, contract/schema/compiler support,
   matching hashes, and no blocking CR for ordinary construction.
4. Run `python scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl` when
   PLAN exists. A stale or hand-edited structure is rejected and recompiled.
5. Reconcile workflow revision and event IDs before changing runtime state.

A blocking CR disables ordinary steps but must not disable its dedicated
`cr-recovery` capability.

## Compile And Confirm

If PLAN does not exist:

```powershell
python scripts/check.py compile docs/contract.md docs/PLAN.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
python scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
```

Read `references/plan-template.md`. Show the owner a generated summary when the
contract uses `checkpoints` or `stepwise`, or when any mandatory checkpoint is
present. Do not ask again on an unchanged hash after a simple pause.

The compiler emits every reviewed variant. Select exactly one per active I
using its structured selector; unselected branches stay dormant. An S0 result
may select a compiled fallback but cannot invent one.

## Execute

Read `references/step-protocol.md` and operate on the selected DAG:

```text
pending -> selected -> executing -> verifying -> complete
complete -> invalidated (affected CR)
```

Record attempt ID, expected revision, environment binding, side-effect state,
and idempotency key before execution. Run the exact V and persist fresh output
before completion. Human V requires an explicit owner event.

Minimal-diff is mandatory. A missing semantic segment is CR, not permission to
append an improvised step. Concrete environment commands live in a binding
record and may not weaken V.

### Direct Fast Path

For a `direct` profile contract the gate never shrinks; the ritual does:

- Gate still runs `contract` and `compile`/`plan`; hash and CR checks never
  skip.
- Default-variant confirmation may share the single PLAN checkpoint instead of
  a separate round.
- Execution stays in-session, segment after segment; no step-executor skill
  dispatch.
- Attempt and V evidence events are exactly as mandatory as in `light`/`full`,
  and Finish still requires `reconcile` clean or fully CR-carried findings.

## Failure And Recovery

- Implementation failure: repair inside the current segment and re-run V.
- Ambiguous or unsafe side effect: inspect postcondition; compensate only as
  declared. Never blindly rerun migration or remote calls.
- Contract fact, interface, scope, or acceptance failure: create blocking CR
  in `docs/change-orders.md` and stop ordinary steps.
- Approved CR: use only `cr-recovery` to recompile, invalidate affected
  dependents, rollback/redo, and execute added V until `verified`.

There is no “owner forces factual failure through” path.

## Finish

All selected steps and V must be complete, no blocking CR may remain, and the
engine-generated P -> F -> I -> S -> V coverage must close. Before the `done`
event, run:

```powershell
python scripts/check.py reconcile docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
```

`status: clean` passes the machine gate. Every `incomplete` finding must either
be resolved or carried by an open CR; a finding with no CR blocks `done`. The
controller then loads the reviewer skill for a `converge-audit` bound to the
reconcile `contract_hash`/`plan_structure_hash`. Append the maintenance handoff
and optional evidence-based retro to build-log, then set PLAN runtime `done`
through an event.

## References

| Need | Read |
|---|---|
| Generated PLAN and confirmation | `references/plan-template.md` |
| Attempts, side effects, CR recovery | `references/step-protocol.md` |
| Post-build learning | `references/retro-protocol.md` |
| Isolated step execution | `../step-executor/SKILL.md` (skill call) |
| Review gate and converge-audit | `../reviewer/SKILL.md` (skill call) |

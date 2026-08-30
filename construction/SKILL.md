---
name: construction
description: Use when the user types /开工, /继续, /竣工, /复盘, /变更 (directed triggers) or natural language such as 开工/施工/继续施工/竣工对账/复盘 (non-directed triggers) to execute a confirmed contract-review PLAN. Validates contract/hash/CR/PLAN gates, executes selected steps with recovery evidence, and routes semantic change through CR. Contract writing and PLAN compilation/confirmation belong to contract-review (/规划); not for planning or unrelated ad-hoc coding.
license: MIT
metadata:
  language: "zh-CN"
  produces: "docs/build-log.md, docs/workflow-events.jsonl"
  updates: "docs/PLAN.md (runtime projection only)"
  requires-skill: "contract-review"
  calls-skills: "step-executor, reviewer, contract-review"
  commands: "/开工, /继续, /竣工, /复盘, /变更 <事实>"
---

# Construction (纯施工)

Execute the confirmed PLAN; do not reinterpret it. Runtime execution may
bind commands and select reviewed variants, but semantic change returns
through CR. 规划（契约与 PLAN 编译确认）归 contract-review 的 `/规划`，
本 skill 从已确认的 PLAN 开始。

## Commands

| 指令 | 何时用 | 做什么 | 产出 |
|---|---|---|---|
| `/开工` | PLAN 已确认（缺则先委托 `/规划`） | 门校验 → 按依赖序执行步骤、跑 V 留证 | 完成步骤 + 验收证据 |
| `/继续` | 中断后恢复 | 重跑门校验，从事件账本续建 | 续施工 |
| `/竣工` | 全部步骤完成后 | `reconcile` 对账 + `converge-audit` | PLAN 置 `done` + 维护交接 |
| `/复盘` | 竣工后 | 只读证据复盘（见 retro-protocol） | 三张清单建议 |
| `/变更 <事实>` | 契约与现实不符 | 建 CR 阻断 → 评审裁决 → 影响闭包内重做 | CR `verified` |

指令可后缀开关，如 `/开工 autonomous`。非定向触发（自然语言）与指令完全
等效："开工"、"施工"、"继续施工"、"竣工对账"、"复盘一下"；直接陈述契约
与现实不符的事实（如"接口 X 实际不存在"）即触发变更流程。

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
- Load the **contract-review** skill when the gate finds PLAN missing or
  stale: it runs `/规划` (gate + compile + confirm); construction never
  compiles PLAN itself. For contract defects, suggest `/变更 <事实>`; CR
  adjudication likewise delegates to contract-review/reviewer.

## Gate

Before every start or resume:

1. Read `../contract-review/references/contract-schema.md` when the
   paired skill is available; otherwise use the installed shared copy.
2. Run `python scripts/check.py contract docs/contract.md`.
3. Require `passed` or legal `conditional`, contract/schema/compiler support,
   matching hashes, and no blocking CR for ordinary construction.
4. Run `python scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl` when
   PLAN exists. A stale or hand-edited structure is rejected; recompilation
   goes through contract-review `/规划` delegation or CR recovery.
5. Reconcile workflow revision and event IDs before changing runtime state.

If PLAN does not exist, delegate to contract-review `/规划` first; this
skill never compiles or confirms PLAN itself. A blocking CR disables
ordinary steps but must not disable its dedicated `cr-recovery` capability.

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

- Gate still runs `contract` and `plan` validation; hash and CR checks never
  skip. Missing PLAN may be delegated to contract-review `/规划` in the same
  session, sharing the single PLAN confirmation checkpoint instead of a
  separate round.
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
| Attempts, side effects, CR recovery | `references/step-protocol.md` |
| Post-build learning | `references/retro-protocol.md` |
| Isolated step execution | `../step-executor/SKILL.md` (skill call) |
| Review gate and converge-audit | `../reviewer/SKILL.md` (skill call) |
| PLAN compile/confirm (delegated) | `../contract-review/SKILL.md` `/规划` (skill call) |

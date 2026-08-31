---
name: construction
description: Use when the user types /build, /resume, /finish, /retro, or /change, or says 开工、施工、继续施工、竣工对账或复盘. Executes a confirmed PLAN with evidence and CR recovery. Contract writing and PLAN compilation belong to contract-review; not for planning or unrelated coding.
license: MIT
metadata:
  language: "zh-CN"
  produces: "docs/build-log.md, docs/workflow-events.jsonl"
  updates: "docs/PLAN.md (runtime projection only)"
  requires-skill: "contract-review"
  calls-skills: "step-executor, reviewer, contract-review"
  commands: "/build, /resume, /finish, /retro, /change <fact>"
---

# Construction (纯施工)

Execute the confirmed PLAN; do not reinterpret it. Runtime execution may
bind commands and select reviewed variants, but semantic change returns
through CR. 规划（契约与 PLAN 编译确认）归 contract-review 的 `/plan`，
本 skill 从已确认的 PLAN 开始。

## Commands

- `/build` starts verified execution from a confirmed PLAN.
- `/resume` revalidates all gates and continues from ledger state.
- `/finish` reconciles the built result and closes only after converge audit.
- `/change <fact>` records a contract/reality mismatch and blocks ordinary work.
- `/retro` is optional evidence-based learning after delivery.

Natural-language construction requests remain valid. Missing or stale PLAN is
delegated to contract-review `/plan`; construction never compiles it itself.

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
  stale: it runs `/plan` (gate + compile + confirm); construction never
  compiles PLAN itself. For contract defects, suggest `/change <fact>`; CR
  adjudication likewise delegates to contract-review/reviewer.

## Gate

Before every start or resume:

1. Read `../contract-review/references/contract-schema.md` when the
   paired skill is available; otherwise use the installed shared copy.
2. Run `python .opencode/workflow/scripts/check.py contract docs/contract.md`.
3. Require `passed` or legal `conditional`, contract/schema/compiler support,
   matching hashes, and no blocking CR for ordinary construction.
4. For `/build`, run `python .opencode/workflow/scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl --require-building`.
   For `/resume`, first use `--require-resumable`; if paused/suspended, append a
   `plan-transition` event to `building` with `plan-event`, then require
   building. A stale or hand-edited structure is rejected; recompilation goes
   through contract-review `/plan` delegation or CR recovery.
5. Reconcile workflow revision and event IDs before changing runtime state.

If PLAN does not exist, delegate to contract-review `/plan` first; this
skill never compiles or confirms PLAN itself. A blocking CR disables
ordinary steps but must not disable its dedicated `cr-recovery` capability.

## Execute

Read `references/step-protocol.md` and operate on the selected DAG:

```text
pending -> selected -> executing -> verifying -> complete
complete -> invalidated (affected CR)
```

Record attempt ID, expected revision, environment binding, side-effect state,
and idempotency key before execution. Project every step/status transition with
`check.py plan-event`; never hand-edit PLAN runtime. Run the exact V and persist
fresh output before completion. Human V requires an explicit owner event.

Minimal-diff is mandatory. A missing semantic segment is CR, not permission to
append an improvised step. Concrete environment commands live in a binding
record and may not weaken V.

### Direct Fast Path

For a `direct` profile contract the gate never shrinks; the ritual does:

- Gate still runs `contract` and `plan` validation; hash and CR checks never
  skip. Missing PLAN may be delegated to contract-review `/plan` in the same
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
python .opencode/workflow/scripts/check.py reconcile docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
```

Only `status: clean` passes the Finish machine gate. Any `incomplete` finding
creates or updates a CR and blocks Finish until it is resolved and reconcile is
clean. The controller then loads the reviewer skill for a `converge-audit` bound to the
reconcile `contract_hash`/`plan_structure_hash`. Append the maintenance handoff
and optional evidence-based retro to build-log. Record the passed
`converge-audit` event, then set PLAN runtime `done` only through
`check.py finish-plan`; copy `reconcile_hash` and `plan_revision` from the clean
reconcile output into that audit event. Generic `plan-event` cannot finish
construction.

## References

| Need | Read |
|---|---|
| Attempts, side effects, CR recovery | `references/step-protocol.md` |
| Post-build learning | `references/retro-protocol.md` |
| Isolated step execution | `../step-executor/SKILL.md` (skill call) |
| Review gate and converge-audit | `../reviewer/SKILL.md` (skill call) |
| PLAN compile/confirm (delegated) | `../contract-review/SKILL.md` `/plan` (skill call) |

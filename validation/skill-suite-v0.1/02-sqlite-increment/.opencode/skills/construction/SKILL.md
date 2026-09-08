---
name: construction
description: Use when the user types /build, /resume, /finish, /retro, or /change, or says 开工、施工、继续施工、竣工对账或复盘. Executes a confirmed PLAN with evidence and CR recovery. Contract writing and PLAN compilation belong to contract-review; not for planning or unrelated coding.
license: MIT
metadata:
  language: "zh-CN"
  produces: "docs/build-log.md, docs/mvp-observation.md, docs/workflow-events.jsonl"
  updates: "docs/PLAN.md (runtime projection only)"
  requires-skill: "contract-review"
  calls-skills: "test-author, step-executor, reviewer, contract-review"
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
  one compiled step spec plus its exact V commands and the frozen test
  manifest's protected file list; expect raw outputs back. Record the
  executor's `subagent_id` as the implementation author in the attempt event
  and observation report. The controller (this skill) alone owns state, the
  ledger, and event recording.
- Load the **test-author** skill (`name: test-author`) before implementing any
  v0.1 first-slice or SI acceptance behavior. Pass the fixed scenarios,
  allowed test context, and exact V scope. The test-author writes only
  acceptance tests and its manifest, runs the red command, and returns the
  frozen test hashes before implementation begins.
- Load the **reviewer** skill (`name: reviewer`) for the per-step review gate
  and for `converge-audit` at Finish, bound to the reconcile
  `contract_hash`/`plan_structure_hash`. In v0.1 pass the test manifest,
  implementation diff, failure history, and MVP observation report so the
  reviewer can check authorship, frozen hashes, real assertions, and budgets.
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

For a v0.1 project, also verify before `/build` or `/resume` that the contract
declares `workflow_protocol: v0.1`, the Phase 0 record is `passed` or a valid
`not-needed`, and the first-slice budget has been measured. A legacy project
already in construction keeps the legacy protocol and must not be partially
converted.

If PLAN does not exist, delegate to contract-review `/plan` first; this
skill never compiles or confirms PLAN itself. A blocking CR disables
ordinary steps but must not disable its dedicated `cr-recovery` capability.

## Execute

Read `references/step-protocol.md` and operate on the selected DAG:

```text
pending -> selected -> executing -> verifying -> complete
complete -> invalidated (affected CR)
```

For each new first-slice/SI acceptance path, invoke test-author before
step-executor. Persist its manifest with `spec_source`, `spec_hash`, test file
list, test file hashes, `test_author_id`, red output/hash, and a frozen-at
timestamp. The manifest is the protected write set for implementation.

Record attempt ID, expected revision, environment binding, side-effect state,
idempotency key, `implementation_author_id`, and the normalized failure
signature when applicable before execution. Project every step/status
transition with `check.py plan-event`; never hand-edit PLAN runtime. Run the
exact V and persist fresh output before completion. Human V requires an explicit
owner event. Append the same facts to `docs/mvp-observation.md` for v0.1; the
report is an observation record, not a replacement for the engine ledger.

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
  If there is a product acceptance V, direct execution still invokes the
  separate test-author role; only a no-product-behavior change may explicitly
  record that no acceptance test is applicable.

## Failure And Recovery

Classify every failed V before deciding to retry:

1. Normalize a failure signature as `V ID + command/scenario ID + failing
   assertion or exception type + stable error summary`, removing timestamps,
   absolute paths, random IDs, and stack line numbers. Changing wording or an
   attempt ID does not create a new signature.
2. Attempts one and two may repair only inside the current segment when the
   failure is an implementation defect and no side effect is unsafe. Record
   the signature, raw output/hash, start/end time, elapsed time, and author IDs.
3. When the same signature occurs for the third consecutive failed attempt,
   stop ordinary execution immediately. The third attempt counts toward cost;
   do not perform a fourth ordinary retry. Set the prompt-layer run state to
   `awaiting-owner` or `suspended` and write the BC-05 escalation payload:
   three raw results, accumulated attempts/time, projected cost at the observed
   rate, and at least two concrete options with cost/risk.
4. A changed signature is not a license for unlimited retries. Reclassify the
   root cause, check the total cost and side effects, and suspend when the
   existing no-progress rule or a budget is reached.
5. An ambiguous or unsafe side effect always stops first. Inspect the
   postcondition and compensate only as declared; never blindly rerun a
   migration or remote call.
6. A contract fact, interface, scope, or acceptance failure creates a blocking
   CR in `docs/change-orders.md` and stops ordinary steps. Do not hide it in an
   SI or edit the frozen test.
7. An approved CR uses only `cr-recovery` to recompile, invalidate affected
   dependents, perform declared rollback/redo, and execute additional V until
   `verified`. Planned expansion after a passed slice uses SI and never replays
   unaffected steps.

There is no “owner forces factual failure through” path.

## Finish

All selected steps and V must be complete, no blocking CR may remain, and the
engine-generated P -> F -> I -> S -> V coverage must close. For v0.1, also
complete `docs/mvp-observation.md` using
`references/mvp-observation-template.md`; missing traceability defaults to an
undetermined MVP result rather than success. Before the `done` event, run:

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

The converge audit also reports the v0.1 ceremony ratio as a warning only:

```text
non-blank manually maintained workflow-document lines in this diff /
non-blank product-code-and-test lines in this diff
```

Exclude `node_modules`, `vendor`, generated files, caches, and binaries. If the
denominator is zero while workflow documents were added, warn directly instead
of treating the ratio as zero or skipping it. The owner may accept a warning;
it never silently changes the contract or blocks the engine by itself.

## References

| Need | Read |
|---|---|
| Attempts, side effects, CR recovery | `references/step-protocol.md` |
| v0.1 MVP observation report | `references/mvp-observation-template.md` |
| Planned slice growth | `../contract-review/references/slice-increment-protocol.md` |
| Post-build learning | `references/retro-protocol.md` |
| Isolated step execution | `../step-executor/SKILL.md` (skill call) |
| Review gate and converge-audit | `../reviewer/SKILL.md` (skill call) |
| PLAN compile/confirm (delegated) | `../contract-review/SKILL.md` `/plan` (skill call) |

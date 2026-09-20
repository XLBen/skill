---
name: construction
description: Use internally from mvp-delivery Build, Fix, or Resume modes when an Audited goal has a confirmed PLAN or needs CR recovery. Executes and finishes the PLAN with evidence. Contract writing and PLAN compilation belong to contract-review.
license: MIT
metadata:
  language: "zh-CN"
  produces: "docs/build-log.md, docs/mvp-observation.md, docs/workflow-events.jsonl"
  updates: "docs/PLAN.md (runtime projection only)"
  requires-skill: "contract-review"
  calls-skills: "i-have-adhd, pua, test-author, step-executor, reviewer, contract-review"
  public-commands: "/build, /fix, /resume (via mvp-delivery)"
---

# Construction (纯施工)

Execute the confirmed PLAN; do not reinterpret it. Runtime execution may
bind commands and select reviewed variants, but semantic change returns
through CR. 规划（契约与 PLAN 编译确认）归 contract-review 的 `/plan`，
本 skill 从已确认的 PLAN 开始。

## Public Routing And Internal Operations

- Public `/build` enters through mvp-delivery and starts verified execution from
  a confirmed Audited PLAN.
- Public `/resume` enters through mvp-delivery, revalidates all gates, and
  continues from ledger state.
- Public `/fix <fact>` enters through mvp-delivery and invokes internal CR
  recovery when contract and reality disagree.
- Internal finish reconciles the built result and closes only after converge
  audit; `/build` runs it automatically.
- Internal retro is optional evidence-based learning after delivery.

Natural-language construction requests remain valid. Missing or stale PLAN is
delegated to contract-review inside `/plan`; construction never compiles it itself.

## Skill Calls

本 skill 派出 fresh 子代理并让它们加载对应角色 skill，而不是内联它们的提示词。席位选择、独立性、回退和 `direct` 规则见
`references/seat-dispatch.md`（权威表为 `../mvp-delivery/references/subagent-orchestration.md` 的 Audited Execution Seat Selection table）；
加载 skill 只增加说明，不创造独立身份，必须使用真实 task/subagent 能力并保留实际 provenance。PLAN 缺失或过期时加载 **contract-review** 走 `/plan`（gate + compile + confirm），construction 永不自行编译 PLAN；契约缺陷交回 `/fix`。

要点：step-executor 每步一个 fresh 席位并交接实现（正式 `verify-step` 由
主控执行）；test-author 在行为实现前冻结验收测试（`stage_id: test-freeze`）；
reviewer 用于逐步 review 与 Finish 的 converge-audit（`stage_id:
review-verdict`）；优先安装的
`mvp-step-executor` / `mvp-test-author` / `mvp-reviewer` 项目 agent。

## Gate

The v0.1 authorship, budget, review and observation requirements named below
also apply to new v0.2 Audited work; machine verification follows v0.2.

For a new five-command Audited run, all workflow artifacts belong to the active
`docs/audit-slices/<goal-slug>/<slice-id>/` package resolved from the goal's
dispatch record (`active_slice.package`; see
`../mvp-delivery/references/subagent-orchestration.md`) — never from the goal
JSON, which the engine rewrites on verification. Rebase the `docs/contract.md`,
`docs/PLAN.md`, ledger, CR, build-log,
observation, test-manifest, and evidence examples below to that package. Legacy
runs already rooted at `docs/` keep their paths. Never choose a package by file
mtime or an unmentioned stale PLAN.

Before every start or resume:

1. Read `../contract-review/references/contract-schema.md` when the
   paired skill is available; otherwise use the installed shared copy.
2. Resolve the active Audited slice package from the goal's dispatch record
   `active_slice.package`. New
   runs use `docs/audit-slices/<goal-slug>/<slice-id>/`; legacy runs may still
   use `docs/`. Run the contract validator against that package's `contract.md`.
3. Require `passed` or legal `conditional`, contract/schema/compiler support,
   matching hashes, and no blocking CR for ordinary construction.
4. For `/build`, run `python .opencode/workflow/scripts/check.py plan <slice>/PLAN.md --contract <slice>/contract.md --change-orders <slice>/change-orders.md --ledger <slice>/workflow-events.jsonl --require-building`.
   For `/resume`, first use `--require-resumable`; if paused/suspended, append a
   `plan-transition` event to `building` with `plan-event`, then require
   building. A stale or hand-edited structure is rejected; recompilation goes
   through contract-review `/plan` delegation or CR recovery.
5. Reconcile workflow revision and event IDs before changing runtime state.

For a new Audited project, also verify before `/build` or `/resume` that the contract
declares top-level `workflow_protocol: v0.2`, the Phase 0 record is `passed` or a valid
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

The controller owns minimal setup/harness readiness before independent tests:
verify the declared runtime, dependencies, test discovery, and required services
are usable. Perform or delegate setup only within confirmed step actions and
allowed writes; missing scope or changed acceptance semantics still returns
through CR. Setup must not implement the acceptance behavior or count a broken
runner as behavior-red. Give test-author the ready harness and binding evidence.

For each new first-slice/SI acceptance path, invoke test-author before behavior
implementation by step-executor. The seat authors tests, runs the classified
pre-change command and freezes the manifest in one dispatch with
`Test author ID`/`Provenance status` = `pending-binding`; the controller records
the runtime provenance (`workflow_runtime.py dispatch-result`) and binds it
(`workflow_runtime.py bind-test-author`) before implementation starts. A
manifest that is still `pending-binding` must not authorize implementation.
Persist `spec_source`, `spec_hash`, protected acceptance paths/hashes,
expected critical scenario IDs, boundary/mock policy, classified pre-change
output/hash, and a frozen-at timestamp, as specified by test-author. Every hash
in the manifest comes from engine output (`check.py hash`), never hand
computation. The controller and reviewer inspect integrity and actual scenario
execution; these are prompt-layer safeguards, not additional machine enforcement.

### PUA Acceptance: `test-freeze`

The test-author seat loads `../pua/SKILL.md` and executes the `test-freeze`
card before returning; its return carries the card result. The controller does
not re-run the card: it mechanically validates the returned manifest fields,
author identity binding and frozen hashes (routing check
`test-freeze-integrity`). Ask “永远绿的测试也是交付？” is answered by the
test-author against behavior-red, baseline classification, real assertions,
actual scenario execution and frozen hashes. An unexpected green, baseline
failure, skipped scenario or acceptance semantics change is a blocker; PUA
cannot invent red or silently weaken the manifest.

Record attempt ID, expected revision, environment binding, side-effect state,
idempotency key, `implementation_author_id`, and the normalized failure
signature when applicable before execution. Project every step/status
transition with `check.py plan-event`; never hand-edit PLAN runtime. Run the
exact automated V through `check.py verify-step` as specified in step-protocol;
only its generated evidence/event can satisfy the machine gate. Do not submit
handwritten passing `step-verification` events. Human V requires an explicit
owner event. Append the same facts to `docs/mvp-observation.md` for v0.1; the
report is an observation record, not a replacement for the engine ledger.

Minimal-diff is mandatory. A missing semantic segment is CR, not permission to
append an improvised step. Concrete environment commands live in a binding
record and may not weaken V.

### PUA Acceptance: `step-verification`

The step-executor runs the pre-handoff portion of the `step-verification`
card against the evidence it holds and returns the result; the controller
then runs the formal `verify-step` and performs the deterministic post-gate
check (engine-generated evidence, all manifest scenarios, raw V output,
content/state assertions, cleanup and failure signature). Ask “这一步是真的
跑了，还是你手写了一个 passing event？” exactly once, with a single semantic
owner per routing (`step-handoff` / `step-formal-evidence`); never repeat the
card as a second semantic pass. The executor returns raw results; only the
controller records the ledger and step state.

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

Before an ordinary retry, load `../pua/references/recovery-protocol.md`. The
first failed experiment is L0; the second same-signature failure is L1 and must
switch method; the third identical failure enters this existing circuit break.
Use the PUA L2 seven-point checklist to prepare the BC-05 payload, not to justify
a fourth ordinary attempt. Expected red tests, owner waits and authorization
blocks are not implementation failures.

There is no “owner forces factual failure through” path.

## Finish

All selected steps and V must be complete, no blocking CR may remain, and the
engine-generated P -> F -> I -> S -> V coverage must close. For v0.1, also
complete `docs/mvp-observation.md` using
`references/mvp-observation-template.md`; missing traceability defaults to an
undetermined MVP result rather than success.

For a new Audited slice package, write `assurance-policy.json`
(`{"schema": "assurance-policy/1", "strict": true}`) into the package.
`finish-plan` then enforces the mechanical assurance floor: a phase 0
disposition (passed or not-needed), a test manifest with bound provenance,
different test/implementation authors and verified protected-test hashes, and a
dispatch record with no unresolved actions, failed tasks or circuit breaks.
Inspect the same report before Finish:

```powershell
python .opencode/workflow/scripts/assurance_policy.py check <slice>
```

The floor is mechanical only; semantic adequacy of the probe, tests and review
verdicts remains the independent reviewer's judgment. Legacy packages without
the policy file keep their existing behavior.

After `finish-plan` returns `done`, seal the completed package so later
tampering is detectable against the baseline; SI/FIX packages pass the base
package seal to record lineage:

```powershell
python .opencode/workflow/scripts/package_seal.py seal <slice> [--parent <base-package>/package-seal.json]
python .opencode/workflow/scripts/package_seal.py verify-package <slice>
```

A local seal is not tamper-proof (a writer can re-seal); anchor `root_hash`
externally when adversarial tampering matters. Verification commands that
claim isolation must run through `verification_runner.py run --mode container`;
host mode must be disclosed as non-isolated (`isolated: false`).

Before the `done` event, run:

```powershell
python .opencode/workflow/scripts/check.py reconcile <slice>/PLAN.md --contract <slice>/contract.md --change-orders <slice>/change-orders.md --ledger <slice>/workflow-events.jsonl
```

Only `status: clean` passes the Finish machine gate. Any `incomplete` finding
creates or updates a CR and blocks Finish until it is resolved and reconcile is
clean. The controller then dispatches a fresh subagent that loads the reviewer
skill for a `converge-audit` bound to the reconcile
`contract_hash`/`plan_structure_hash`. Apply the final integrated user-path checks
and replayable handoff requirements in `../mvp-delivery/SKILL.md`'s completion
section; pass the full `ACCEPTANCE_HANDOFF` with `pua_stage_id: review-verdict`
to the reviewer and link its evidence in build-log rather than duplicate that
checklist.
Apply these checks to the current slice and affected existing journeys, not
unimplemented future outcomes; mvp-delivery enforces whole-goal coverage at its
final gate. A slice handoff must state its remaining goal-level limitations.
Append optional evidence-based retro to build-log. Record the passed
`converge-audit` event, then set PLAN runtime `done` only through
`check.py finish-plan`; copy `reconcile_hash` and `plan_revision` from the clean
reconcile output into that audit event. Generic `plan-event` cannot finish
construction.

`done` closes the current Audited slice, not necessarily the mvp-delivery goal.
Return control to mvp-delivery after every finish; the controller re-judges the
next slice's risk per its Rigor By Slice rules. Only an Audited next slice gets
a new affected-work-only slice package from contract-review, with the SI
decision and generated PLAN confirmation; a Normal/Guarded next slice continues
with light execution and no contract/PLAN. Never overwrite a completed package,
import its completed steps into the new PLAN, or report the whole goal complete
from a single clean reconcile unless every goal-card outcome has `verify-goal`
evidence and `finish-goal` succeeds. The original goal approval never substitutes
for the owner gates of a new Audited slice.

### PUA Acceptance: `slice-acceptance`

Before requesting the owner's SI decision, load `../pua/SKILL.md` and execute
the `slice-acceptance` card with `pua_stage_id: slice-acceptance`. Ask “clean 了当前
slice，整件事也交付了吗？”
Show the real input, output, limitations, environment and evidence. Record the
owner's actual acceptance, delta decision and next PLAN confirmation separately;
do not continue construction or convert a missing decision into a pass.

A defect discovered after `done` enters `/fix` as a new sibling `FIX` replacement
package. Do not reopen or edit the completed package and do not invoke the
engine's same-PLAN CR recovery. Record the base package/hash and mismatch in
`repair.md`, then release and compile an independent affected-only contract/PLAN
without `--previous-contract`. Execute the correction plus regression behavior
as a normal new Audited slice. Its clean reconcile may supersede the affected
goal-card evidence but never deletes the historical package. Engine CR recovery
remains for mismatches found before the active package reaches `done`.

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
| Isolated step execution | `../step-executor/SKILL.md` (fresh subagent loads skill) |
| Review gate and converge-audit | `../reviewer/SKILL.md` (fresh subagent loads skill) |
| PLAN compile/confirm (delegated) | `../contract-review/SKILL.md` `/plan` (skill call) |

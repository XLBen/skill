# Construction Seat Dispatch

> When to read: before dispatching the step-executor, test-author or reviewer
> seat, or when checking the independence/fallback rules. Seat: construction
> controller. Inputs: confirmed PLAN, manifest, dispatch preflight results.


This skill dispatches fresh subagents for independent seats and has them load
the relevant skill instead of inlining its prompt:

- Dispatch a fresh implementation subagent and have it load the
  **step-executor** skill (`name: step-executor`) for isolated step execution
  under the authoritative Audited Execution Seat Selection table in
  `../mvp-delivery/references/subagent-orchestration.md` (`full` profile or
  `checkpoints`/`stepwise` interaction; `direct` never dispatches; only
  `light + autonomous` stays in-session). Pass exactly
  one compiled step spec plus its exact V commands and the frozen test
  manifest's protected file list; expect a STEP_HANDBACK structured result
  (implementation handed back, formal V pending) — the controller then records
  the attempt and runs `verify-step` itself. Record the
  executor's `subagent_id` as the implementation author in the attempt event
  and observation report. The controller (this skill) alone owns state, the
  ledger, and event recording. Pass `stage_id: step-verification`, require the
  executor to load `../pua/SKILL.md` and the matching stage card, and require a
  structured PUA result with evidence rather than a bare “complete”.
- Dispatch a fresh test-author subagent and have it load the **test-author**
  skill (`name: test-author`) before implementing any v0.1 first-slice or SI
  acceptance behavior. Pass the fixed scenarios,
  allowed test context, exact V scope, and the controller-resolved manifest path
  (package-internal `test-manifests/<slice-id>.md` for new runs, legacy
  `docs/test-manifests/<slice-id>.md`). The seat writes `pending-binding`
  provenance in one dispatch; after its return the controller records runtime
  provenance and binds it with `workflow_runtime.py bind-test-author` before
  implementation starts. The test-author writes only
  acceptance tests and its manifest, records targeted behavior-red or existing
  regression baseline-green evidence, and returns the frozen acceptance hashes
  before implementation begins. Pass `stage_id: test-freeze` and require it to
  load `../pua/SKILL.md`; the PUA check cannot replace the independent author,
  behavior-red evidence or manifest freeze.
- Dispatch a fresh review subagent and have it load the **reviewer** skill
  (`name: reviewer`) for the per-step review gate and for `converge-audit` at
  Finish, bound to the reconcile
  `contract_hash`/`plan_structure_hash`. In v0.1 pass the test manifest,
  implementation diff, failure history, and MVP observation report so the
  reviewer can check authorship, frozen hashes, real assertions, and budgets.
  Pass `stage_id: review-verdict` for the per-step review and
  `stage_id: review-verdict` for the pre-owner converge-audit review. Require the
  reviewer to load `../pua/SKILL.md`, inspect the matching card and return
  evidence-backed gaps. Before dispatch, build the full `ACCEPTANCE_HANDOFF`, pass
  it with the matching `pua_stage_id`, and show an `i-have-adhd`
  acceptance-preview when a milestone is user-visible; loading PUA does not create
  reviewer independence.
- Load the **contract-review** skill when the gate finds PLAN missing or
  stale: it runs `/plan` (gate + compile + confirm); construction never
  compiles PLAN itself. For contract defects, return control to `/fix`; CR
  adjudication delegates internally to contract-review/reviewer.

Loading a skill only adds instructions to the current agent; it does not create
an independent identity. Use the runtime's task/subagent capability for the
fresh dispatches above, following the role-to-agent mapping, dispatch
preflight, and failure branches in
`../mvp-delivery/references/subagent-orchestration.md`: prefer the installed
project agents `mvp-step-executor` / `mvp-test-author` / `mvp-reviewer`, with
the skill loaded inside the dispatched seat. If unavailable, obtain a real
separate-session review or mark independence unavailable and block Audited
release/completion. Never waive the gate or invent distinct IDs. IDs are
claims, not cryptographic identity verification; preserve and inspect actual
session provenance. The `direct` profile overrides interaction settings
(`checkpoints`/`stepwise`) and keeps execution in-session: no step-executor
dispatch happens under `direct` regardless of interaction value, while
product acceptance still invokes the separate test-author seat.

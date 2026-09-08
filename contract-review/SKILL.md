---
name: contract-review
description: Use internally from mvp-delivery Plan or Audited modes when a high-risk goal needs a machine-checked contract and confirmed PLAN. Also supports the public /plan command through mvp-delivery. Routes vague requirements to grill; never executes construction steps.
license: MIT
metadata:
  language: "zh-CN"
  produces: "docs/contract.md, docs/PLAN.md, docs/review-log.md, docs/evidence/, docs/change-orders.md, docs/workflow-events.jsonl"
  next-skill: "construction"
  calls-skills: "grill, reviewer"
  commands: "/plan <goal-or-brief> (public via mvp-delivery)"
---

# Contract Review (评审 + 规划)

本 skill 负责动手写代码之前的全部规划工作：需求评审成契约，契约编译成
可执行 PLAN。Produce the smallest complete contract the owner can still
control, then the confirmed PLAN compiled from it. Machine checks prove
structure; independent review challenges semantics. Neither may silently
change the user's requirements.

## Entry And Internal Modes

- Public `/plan <requirements-or-brief>` enters through mvp-delivery. When it
  selects Audited rigor, ready requirements become a reviewed contract and are
  compiled into `docs/PLAN.md` in one command. If
  user/problem/outcome/constraints/success are materially unclear, load grill
  instead of guessing.
- Internal `debate` examines an existing design and its trade-offs.
- Internal `assess` gives a go/clarify/stop assessment without silently
  starting contract work.

`assess` and `debate` are read-only auxiliary modes. Assessment returns a
`go`, `clarify`, or `stop` verdict with rationale, material unknowns, and the
next decision. Debate compares the supplied design's alternatives, evidence,
trade-offs, and failure modes. Neither creates or edits workflow artifacts
unless the active `/plan` is creating an Audited plan.

Natural-language requests to challenge an idea use reviewer directly; they are
lightweight challenges, not public workflow commands.

## Skill Calls

This skill uses real subagent dispatch for independent review and skill loading
for same-agent workflow transitions instead of inlining their prompts:

- Dispatch a fresh reviewer subagent and have it load the **reviewer** skill
  (`name: reviewer`) for every scout / question / review / final-audit /
  cr-audit / converge-audit dispatch. Pass `mode`, the fixed contract
  snapshot/hash, the relevant evidence, and an output budget; expect structured
  JSON back. The reviewer is read-only and never edits `docs/` artifacts.
- Load the **grill** skill (`name: grill`) when intake readiness is missing.
  A valid final brief returns here; do not repeat its confirmed questions.
- On `passed`, compile and confirm the PLAN in the same `/plan` run; then tell
  the user to say `/build`. During an active mvp-delivery run, return control to
  it so it can load construction directly.

Loading a skill in the current session does not create an independent reviewer.
If the runtime cannot dispatch a fresh subagent, use a real separate-session
review with recorded provenance, or mark independence unavailable and block
Audited release. A waiver or loading a skill cannot supply independent review.
Session/author IDs are claims, not cryptographically verified identities.

## Start Or Resume

Load references by phase, not all at once: read
`references/requirement-protocol.md` and `references/phase-0-protocol.md`
before risk ranking/probing, then read `references/contract-schema.md` before
drafting the contract JSON. Read `references/slice-increment-protocol.md` only
when an SI is being prepared. Read `references/reviewer-protocol.md` before
every reviewer dispatch, including scout and clean final audit; read the
verdict protocol when adjudicating issues.

For a new five-command Audited run, resolve `slice_root` from the mvp goal card
as `docs/audit-slices/<goal-slug>/<slice-id>/`. All contract, PLAN, state,
ledger, CR, review-log, observation, and evidence paths shown below must be
rebased under that root. When intake comes from shared `docs/brief.md`, validate
it first, then copy its exact bytes to `<slice_root>/brief.md`; the packaged
contract uses `brief_path: brief.md` and the same hash so the validator's
same-directory boundary remains valid. Never edit the snapshot. Legacy runs
that already use root `docs/` keep those paths. Persist the active package and
its contract/PLAN/reconcile hashes in the Audited goal-card entry so
build/resume never select one by recency.

1. If `docs/workflow-state.json` exists, reconcile it with the append-only
   event ledger by revision/event ID. Never infer state from chat.
2. If the current request explicitly names `docs/brief.md`, run
   `python .opencode/workflow/scripts/check.py brief docs/brief.md`.
   A grilled intake must be final and owner-confirmed. Preserve every typed
   brief item in canonical `intake.dispositions`: consumed items name their
   contract IDs; deferred/rejected items carry a reason.
   Never infer that an unmentioned brief is current merely because the file
   exists; no-argument `/plan` must ask which input to plan.
3. Validate an existing contract with
   `python .opencode/workflow/scripts/check.py contract docs/contract.md`.
4. Read `docs/change-orders.md` for CR work; review/build logs only reference
   CR IDs. Planned post-slice expansion uses an SI record, not a CR; read
   `references/slice-increment-protocol.md` when an SI is requested.

New Audited contracts declare top-level `workflow_protocol: v0.2` (not inside
`delivery`); automated V must satisfy the machine schema in contract-schema.
Existing released packages retain their original protocol, without partial migration.
New contracts always declare `intake.mode`. Use `direct` for already-specific
input that does not need grill, independently of the risk profile. Use `grilled` when the
contract consumes `docs/brief.md`; the canonical contract stores the brief
path, hash, and full disposition coverage.

For a new contract, initialize the revision/budget projection once with
`python .opencode/workflow/scripts/check.py init docs/contract.md docs/workflow-state.json`.

If the engine is unavailable, stop before declaring `passed`; do not simulate
hashes or schema checks manually.

## Profile And Control

Recommend one profile and let the owner override it:

| Profile | Use |
|---|---|
| direct | Local, reversible change with no product trade-off |
| light | Bounded feature or integration; default |
| full | Cross-module, irreversible, security/privacy/cost sensitive |

Also persist `autonomous`, `checkpoints`, or `stepwise` interaction and numeric
audit/research/prototype budgets. Quality requirements do not fall with the
profile; irrelevant nodes and speculative review disappear. When a budget is
spent, enter `awaiting-owner` or `suspended` and offer add budget, reduce scope,
pause, or terminate. Never convert budget exhaustion into approval.

Mandatory owner checkpoints override autonomous mode: new or removed P,
expanded B, irreversible effects, spend, privacy exposure, and value trade-off.
Queue T decisions FIFO and ask one at a time.

### Phase 0: Risk Probe Before The First Slice

For `grilled`, `light`, and `full` work, do not draft a complete multi-slice
contract before testing the riskiest assumption. Read
`references/phase-0-protocol.md` and follow this order:

1. Rank the unverified assumptions by the cost of being wrong, not by the
   order in which they appeared in the brief. Name the assumption, the P/I it
   could invalidate, and the observable result that would refute it.
2. Design the smallest real probe that can distinguish the outcomes. A probe
   must declare request/call limits, time or spend limits, cache key and
   location, backoff, side effects, cleanup, and a stop condition before it
   runs.
3. Run the probe against the real boundary when safe. A local mock may explain
   behavior, but it cannot close a real external-assumption gate.
4. Save the result as `docs/evidence/phase-0-<id>.md` with the raw observation,
   redactions, and `passed`, `blocked`, or `refuted` verdict. Do not repeat a
   full smoke run when a cached result is still valid.
5. Only after a `passed` probe (or an explicit `not-needed` decision for a
   genuinely local reversible direct change) draft the first-slice contract.
   `blocked` or `refuted` returns to owner control or a blocking CR; it never
   becomes a complete PLAN by optimism.

The first contract is a thin end-to-end slice, not a compressed full roadmap.
Declare its numeric budget before drafting it and show actual versus budget in
the final audit. The default budget guidance is at most 3 active P, 3 active F,
3 active I, 5 active V, 8 PLAN segments, and 180 non-blank contract lines;
projects may choose stricter values, while a wider budget needs an owner
decision recorded before the slice is drafted. The slice must include one
real user or downstream-observable path, not only infrastructure.

After the slice passes its real verification and owner acceptance, planned
expansion is a `slice increment` (SI). Each SI is a small ADDED/MODIFIED/REMOVED
delta with affected IDs, a new budget, and its own verification. It does not
invalidate or replay unaffected steps. A fact, interface, scope, or acceptance
failure remains a blocking CR and follows CR recovery instead.

### Direct Fast Path

For `profile: direct` the ceremony shrinks; the floor does not. Direct intake
alone does not qualify a `light` or `full` contract for this fast path:

- One intake pass may draft the contract; T decisions still go one at a time.
- A real Phase 0 probe may be skipped only when the work is demonstrably local,
  reversible, and has no material external assumption; record that decision in
  the review log. If the change has an acceptance V, it still uses the
  independent test-author flow unless the owner explicitly accepts no testable
  product behavior.
- Review is a single `question` pass plus the mandatory clean-context final
  audit — no multi-round loop when no material issue survives.
- Structural validation, event ledger discipline, and every mandatory owner
  checkpoint (irreversible, spend, privacy, scope) are identical to
  `light`/`full`.

## Workflow

```text
intake -> risk ranking -> Phase 0 probe / not-needed decision
       -> first-slice contract draft -> structural validation
       -> reviewer question -> answer/minimal revision -> review
       -> surviving issue set empty -> clean final audit -> passed/conditional
       -> real slice verification + owner acceptance
       -> SI delta -> scoped verification -> next SI or done
```

Use `references/contract-template.md` for the artifact and
`references/evidence-protocol.md` for W/E. Use reviewer modes from
`references/reviewer-protocol.md`.

Every operation has a stable event ID. Append and fsync the event before
atomically updating the state projection with `expected-revision`. Duplicate
event IDs are replayed idempotently; stale revisions fail closed.

## Seats

- Owner (甲方): value, scope, priorities, acceptable trade-offs.
- Contractor (乙方): smallest complete P/F/I/V contract, wheel-first
  implementation.
- Reviewer (独立评审): material factual, flow, verification, or protocol
  objections.
- Test author (测试作者): independently turns the frozen slice scenarios into
  runnable acceptance tests, proves applicable behavior-red (baseline regression
  may start green), and freezes the test file
  hashes before implementation. This seat may write test files but not product
  code; it is not the read-only reviewer and is not the implementation seat.

The reviewer cannot invent product requirements. The contractor cannot
downgrade an objection or owner decision. A factual dispute becomes
primary-source research or a falsifiable prototype, within budget.

## Convergence

Compute one final set after materiality, evidence honesty, and semantic
deduplication. Any surviving issue continues the loop. Protocol invariants may
reference HASH/STATE/CR/AUTH/COMPILER without inventing a P/F link.

There is no round-count approval. Two consecutive cycles with no issue closed,
escalated, or materially advanced enter `suspended`; they do not loop forever.
`conditional` is legal only after structural validation and for explicit,
non-factual residual risks with owner decision and additional V.

## Release Gate

Before `passed` or `conditional`:

1. Apply all T decisions to the contract.
2. For grilled intake, account for every brief item and verify its hash.
3. Require evidence bundle hashes for cited E.
4. Confirm the Phase 0 artifact or the narrowly justified `not-needed` decision.
5. Confirm the first-slice budget and actual count/line report.
   Check that existing P/F/I/V cover every promised user-facing outcome through
   public-interface journeys, with prerequisites, environment gaps, and
   repeatable setup/handoff specified. Shared scenarios are sufficient; a
   unit-only demonstration is not a substitute for the integrated journey.
6. Run `python .opencode/workflow/scripts/check.py contract docs/contract.md`.
7. Run a clean-context final audit against the fixed contract snapshot.
8. Record the passed `final-audit` event, then use `check.py release` to append
   the workflow transition and project contract frontmatter to
   `passed`/`conditional` with that event ID and exact contract hash.
   `conditional` also requires a bound owner decision plus active residual R
   and additional V IDs. Frontmatter alone is not a release.

Hand off generated P/F/I/V/B/W/T/R summaries and the hash. Do not handwrite a
second semantic contract.

## Plan (Compile And Confirm)

`/plan` turns a `passed` contract into a confirmed executable PLAN. PLAN is
compiler output; never hand-write it.

1. Resolve the current Audited slice package from the mvp goal card. New
   five-command runs use `docs/audit-slices/<goal-slug>/<slice-id>/`; legacy
   runs may still use `docs/`. Gate its `contract.md`; require `passed` or legal
   `conditional`, matching hashes, and no blocking CR.
2. Compile when PLAN does not exist. Do not compile the full roadmap in place
   of a first slice; later scope belongs in an SI:

   ```powershell
   python .opencode/workflow/scripts/check.py compile <slice>/contract.md <slice>/PLAN.md --change-orders <slice>/change-orders.md --ledger <slice>/workflow-events.jsonl
   python .opencode/workflow/scripts/check.py plan <slice>/PLAN.md --contract <slice>/contract.md --change-orders <slice>/change-orders.md --ledger <slice>/workflow-events.jsonl
   ```

3. Confirm per `references/plan-template.md`: always show the owner the generated
   PLAN summary and record the decision. `autonomous` reduces later step
   interruptions; it does not skip this release. Do not ask again on an
   unchanged hash after a simple pause.
4. Persist the confirmed selections with `confirm-plan`, then run `plan` with
   `--require-building`. A chat acknowledgement without these events is not a
   confirmed PLAN.

The compiler emits every reviewed variant. Exactly one per active I is
selected at runtime through its structured selector; unselected branches
stay dormant. Construction executes the confirmed PLAN and never recompiles
it on its own. A semantic correction goes through CR recovery; planned
post-acceptance expansion is prepared as an SI and produces the next reviewed
slice package. Never overwrite or recompile a completed package; the next
contract/PLAN contains only affected increment work.

## References

| Need | Read |
|---|---|
| Contract, hash, graph, events, CR | `references/contract-schema.md` |
| Phase 0 risk probe | `references/phase-0-protocol.md` |
| Planned slice increment | `references/slice-increment-protocol.md` |
| Architecture decisions | `references/adr-template.md` |
| Owner authority and decisions | `references/requirement-protocol.md` |
| Contract artifact | `references/contract-template.md` |
| Generated PLAN and confirmation | `references/plan-template.md` |
| Research and prototype | `references/evidence-protocol.md` |
| Reviewer modes | `references/reviewer-protocol.md` |
| Verdict and recovery | `references/verdict-rules.md` |
| Domain charter suggestions | `references/charter-templates.md` |
| Independent review seat | `../reviewer/SKILL.md` (fresh subagent loads skill) |

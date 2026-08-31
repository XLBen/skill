---
name: contract-review
description: Use when the user types /review, /debate, /assess, or /plan, or asks to 评审方案、论证设计、评估项目或编译PLAN. Converts ready requirements or a validated grill brief into a machine-checked contract and confirmed PLAN. Routes vague or high-risk requirements to grill; never executes construction steps.
license: MIT
metadata:
  language: "zh-CN"
  produces: "docs/contract.md, docs/PLAN.md, docs/review-log.md, docs/evidence/, docs/change-orders.md, docs/workflow-events.jsonl"
  next-skill: "construction"
  calls-skills: "grill, reviewer"
  commands: "/review <requirements>, /debate <design>, /assess <idea>, /plan"
---

# Contract Review (评审 + 规划)

本 skill 负责动手写代码之前的全部规划工作：需求评审成契约，契约编译成
可执行 PLAN。Produce the smallest complete contract the owner can still
control, then the confirmed PLAN compiled from it. Machine checks prove
structure; independent review challenges semantics. Neither may silently
change the user's requirements.

## Commands

- `/review <requirements>` is the normal entry: ready requirements become a
  reviewed contract. If user/problem/outcome/constraints/success are materially
  unclear, or the work is costly, irreversible, privacy/security sensitive, or
  otherwise high-risk, load grill instead of guessing.
- `/plan` compiles a passed contract into `docs/PLAN.md` and confirms its
  variants. It does not review requirements again.
- `/debate <design>` examines an existing design and its trade-offs.
- `/assess <idea>` gives a go/clarify/stop assessment without silently
  starting contract work.

`/assess` and `/debate` are read-only auxiliary modes. Assessment returns a
`go`, `clarify`, or `stop` verdict with rationale, material unknowns, and the
next decision. Debate compares the supplied design's alternatives, evidence,
trade-offs, and failure modes. Neither creates or edits workflow artifacts
unless the user separately invokes `/review`.

Natural-language requests remain valid. `/challenge` belongs to reviewer;
it is a lightweight challenge, not intake or contract review.

## Skill Calls

This skill calls other skills through the skill tool instead of inlining
their prompts:

- Load the **reviewer** skill (`name: reviewer`) for every scout / question /
  review / final-audit / cr-audit / converge-audit dispatch. Pass `mode`, the
  fixed contract snapshot/hash, the relevant evidence, and an output budget;
  expect structured JSON back. The reviewer is read-only and never edits
  `docs/` artifacts.
- Load the **grill** skill (`name: grill`) when intake readiness is missing.
  A valid final brief returns here; do not repeat its confirmed questions.
- On `passed`, continue with `/plan` in this skill; after PLAN confirmation,
  hand off with `next-skill: construction` — tell the user to say `/build`,
  or load the construction skill directly.

## Start Or Resume

Load references by phase, not all at once: read
`references/requirement-protocol.md` before the first owner question, and
`references/contract-schema.md` before drafting the contract JSON. Reviewer
and verdict protocols are needed only when issues exist.

1. If `docs/workflow-state.json` exists, reconcile it with the append-only
   event ledger by revision/event ID. Never infer state from chat.
2. If the current request explicitly names `docs/brief.md`, run
   `python .opencode/workflow/scripts/check.py brief docs/brief.md`.
   A grilled intake must be final and owner-confirmed. Preserve every typed
   brief item in canonical `intake.dispositions`: consumed items name their
   contract IDs; deferred/rejected items carry a reason.
   Never infer that an unmentioned brief is current merely because the file
   exists; no-argument `/review` must ask which input to review.
3. Validate an existing contract with
   `python .opencode/workflow/scripts/check.py contract docs/contract.md`.
4. Read `docs/change-orders.md` for CR work; review/build logs only reference
   CR IDs.

New contracts always declare `intake.mode`. Use `direct` only for a specific,
small, reversible request that does not need grill. Use `grilled` when the
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

### Direct Fast Path

For a `direct` change the ceremony shrinks; the floor does not:

- One intake pass may draft the contract; T decisions still go one at a time.
- Scout/evidence work is skipped unless a material fact is actually disputed.
- Review is a single `question` pass plus the mandatory clean-context final
  audit — no multi-round loop when no material issue survives.
- Structural validation, event ledger discipline, and every mandatory owner
  checkpoint (irreversible, spend, privacy, scope) are identical to
  `light`/`full`.

## Workflow

```text
intake -> contract draft -> structural validation
       -> proportionate scout/evidence when a material fact is disputed
       -> reviewer question -> answer/minimal revision -> review
       -> surviving issue set empty -> clean final audit -> passed/conditional
```

Use `references/contract-template.md` for the artifact and
`references/evidence-protocol.md` for W/E. Use reviewer modes from
`references/reviewer-protocol.md`.

Every operation has a stable event ID. Append and fsync the event before
atomically updating the state projection with `expected-revision`. Duplicate
event IDs are replayed idempotently; stale revisions fail closed.

## Three Seats

- Owner (甲方): value, scope, priorities, acceptable trade-offs.
- Contractor (乙方): smallest complete P/F/I/V contract, wheel-first
  implementation.
- Reviewer (独立评审): material factual, flow, verification, or protocol
  objections.

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
4. Run `python .opencode/workflow/scripts/check.py contract docs/contract.md`.
5. Run a clean-context final audit against the fixed contract snapshot.
6. Record the passed `final-audit` event, then use `check.py release` to append
   the workflow transition and project contract frontmatter to
   `passed`/`conditional` with that event ID and exact contract hash.
   `conditional` also requires a bound owner decision plus active residual R
   and additional V IDs. Frontmatter alone is not a release.

Hand off generated P/F/I/V/B/W/T/R summaries and the hash. Do not handwrite a
second semantic contract.

## Plan (Compile And Confirm)

`/plan` turns a `passed` contract into a confirmed executable PLAN. PLAN is
compiler output; never hand-write it.

1. Gate: run `python .opencode/workflow/scripts/check.py contract docs/contract.md`; require
   `passed` or legal `conditional`, matching hashes, and no blocking CR.
2. Compile when PLAN does not exist:

   ```powershell
   python .opencode/workflow/scripts/check.py compile docs/contract.md docs/PLAN.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
   python .opencode/workflow/scripts/check.py plan docs/PLAN.md --contract docs/contract.md --change-orders docs/change-orders.md --ledger docs/workflow-events.jsonl
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
it on its own; semantic recompilation happens only through CR recovery.

## References

| Need | Read |
|---|---|
| Contract, hash, graph, events, CR | `references/contract-schema.md` |
| Owner authority and decisions | `references/requirement-protocol.md` |
| Contract artifact | `references/contract-template.md` |
| Generated PLAN and confirmation | `references/plan-template.md` |
| Research and prototype | `references/evidence-protocol.md` |
| Reviewer modes | `references/reviewer-protocol.md` |
| Verdict and recovery | `references/verdict-rules.md` |
| Domain charter suggestions | `references/charter-templates.md` |
| Independent review seat | `../reviewer/SKILL.md` (skill call) |

---
name: contract-review
description: Use when the user types /评审, /论证, /质疑, /评估 (directed triggers) or natural language such as 评审方案/论证方案/需求评审/评估项目/苏格拉底式质疑 (non-directed triggers) to review or challenge a project or feature before implementation. Builds a machine-validated P/F/I/V contract, preserves owner decisions, runs proportionate independent challenge, and validates it with scripts/check.py. Not for academic writing, code review, or executing an accepted plan.
license: MIT
metadata:
  language: "zh-CN"
  produces: "docs/contract.md, docs/review-log.md, docs/evidence/, docs/change-orders.md, docs/workflow-events.jsonl"
  next-skill: "construction"
  calls-skills: "reviewer"
  commands: "/评审 <方案>, /论证 <设计>, /质疑 <想法>, /评估 <项目>"
---

# Contract Review

Produce the smallest complete contract the owner can still control. Machine
checks prove structure; independent review challenges semantics. Neither may
silently change the user's requirements.

## Commands

| 指令 | 作用 |
|---|---|
| `/评审 <方案>` | 完整评审：问答 → 契约 → 独立挑战 → 终审 |
| `/论证 <设计>` | 论证一个既有设计，产出契约或问题清单 |
| `/质疑 <想法>` | 苏格拉底式质疑（轻量，可无契约直接开质） |
| `/评估 <项目>` | 评估项目可行性，同 `/评审` 流程 |

任一指令可后缀开关，如 `/评审 用 full，checkpoints`、`/评审 autonomous`。

非定向触发（自然语言）与指令完全等效："评审方案：……"、"论证方案：……"、
"需求评审"、"评估项目"、"苏格拉底式质疑一下……"。

## Skill Calls

This skill calls other skills through the skill tool instead of inlining
their prompts:

- Load the **reviewer** skill (`name: reviewer`) for every scout / question /
  review / final-audit / cr-audit / converge-audit dispatch. Pass `mode`, the
  fixed contract snapshot/hash, the relevant evidence, and an output budget;
  expect structured JSON back. The reviewer is read-only and never edits
  `docs/` artifacts.
- On `passed`, hand off with `next-skill: construction` — tell the user to
  say `/开工`, or load the construction skill directly.

## Start Or Resume

Load references by phase, not all at once: read
`references/requirement-protocol.md` before the first owner question, and
`references/contract-schema.md` before drafting the contract JSON. Reviewer
and verdict protocols are needed only when issues exist.

1. If `docs/workflow-state.json` exists, reconcile it with the append-only
   event ledger by revision/event ID. Never infer state from chat.
2. Validate an existing contract with
   `python scripts/check.py contract docs/contract.md`.
3. Read `docs/change-orders.md` for CR work; review/build logs only reference
   CR IDs.

For a new contract, initialize the revision/budget projection once with
`python scripts/check.py init docs/contract.md docs/workflow-state.json`.

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
2. Require evidence bundle hashes for cited E.
3. Run `python scripts/check.py contract docs/contract.md`.
4. Run a clean-context final audit against the fixed contract snapshot.
5. Persist the audit event and exact contract hash.

Hand off generated P/F/I/V/B/W/T/R summaries and the hash. Do not handwrite a
second semantic contract.

## References

| Need | Read |
|---|---|
| Contract, hash, graph, events, CR | `references/contract-schema.md` |
| Owner authority and decisions | `references/requirement-protocol.md` |
| Contract artifact | `references/contract-template.md` |
| Research and prototype | `references/evidence-protocol.md` |
| Reviewer modes | `references/reviewer-protocol.md` |
| Verdict and recovery | `references/verdict-rules.md` |
| Domain charter suggestions | `references/charter-templates.md` |
| Independent review seat | `../reviewer/SKILL.md` (skill call) |

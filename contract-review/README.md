# contract-review

Builds a machine-validated implementation contract while preserving
the owner's authority over value and scope. A contractor proposes the
smallest complete design, an independent reviewer challenges material
semantics, and the workflow stops only with an empty surviving issue set.

It is not an unlimited debate. Profiles and budgets control ceremony and cost;
two no-progress cycles suspend safely. Budget exhaustion never turns a flaw
into approval.

## Key Files

- `SKILL.md`: orchestration and control boundaries.
- `references/contract-schema.md`: normative engine protocol.
- `references/requirement-protocol.md`: owner authority and FIFO decisions.
- `references/evidence-protocol.md`: primary evidence and prototypes.
- `references/contract-template.md`: contract container.
- `references/reviewer-protocol.md`: scout/question/review/audit modes.
- `references/verdict-rules.md`: convergence and recovery.
- `agents/reviewer.md`: optional read-only independent agent.

Install together with the repository `scripts/check.py`; a passed contract
must validate through the engine. After changing skill/agent files, restart
opencode.

Run `python scripts/check.py --selftest` before distribution.

# Requirement Brief Template

Create `docs/brief.md` as readable prose plus one authoritative `json brief`
block. Keep secrets and unnecessary personal information out of this file.

```markdown
---
project: <name>
status: draft
brief-hash: <empty until final>
---

# <project> requirement brief

Short “this is what I heard” summary.

```json brief
{
  "schema_version": 1,
  "revision": 1,
  "status": "draft",
  "decision_ledger_version": 1,
  "summary": "Who has what problem and what outcome matters",
  "items": [
    {
      "id": "BF-01",
      "kind": "fact",
      "statement": "Observed fact",
      "source": "primary source or user-stated",
      "evidence_status": "verified"
    },
    {
      "id": "BD-01",
      "kind": "decision",
      "question": "Decision the owner made",
      "choice": "Selected answer",
      "rationale": "Why",
      "owner_confirmed": true,
      "decision_key": "execution.channel",
      "supersedes": []
    },
    {
      "id": "BS-01",
      "kind": "success",
      "statement": "Observable outcome that shows the need was met",
      "source": "owner"
    }
  ],
  "frontier": [],
  "owner_confirmation": {
    "confirmed": false,
    "summary": ""
  }
}
```
```

Allowed `kind` values and prefixes are `fact/BF`, `decision/BD`,
`assumption/BA`, `constraint/BC`, `question/BQ`, `success/BS`, and
`non-goal/BN`. A final brief has an empty frontier and explicit owner
confirmation.

Use `summary` and existing item `statement`/decision fields to capture the
intended user/interface, target versus verification environment, representative
input, useful output and retrieval, and repeatable delivered setup. Record
material prerequisites or environment gaps as facts, constraints, assumptions,
or open questions as appropriate. Success items describe observable journeys
through the intended public interface covering every promised user-facing
outcome; one scenario may cover several outcomes. CLI commands and library API
calls count, without adding a GUI or deployment requirement. The dimension
coverage table from `SKILL.md` is interviewing discipline for deciding what to
ask next; it is not a separate artifact and adds no schema fields — the brief
record stays this prose plus the `json brief` block.

For new interviews, keep `decision_ledger_version: 1`. Give each owner decision a
stable `decision_key` for the dimension it governs (e.g. `execution.channel`,
`ux.runtime`, `rule.fairness`, `acceptance.milestone`) and `supersedes: []`. If the
owner revises a topic in a later round, append a new BD-NN and point supersedes to
the prior decision ID; never edit history in place. The validator rejects two
current decisions with the same key. Keys catch same-topic conflict only; the
final semantic pass still checks interactions between different keys.

Before final owner confirmation, generate `brief-confirmation` and show the current
active decisions/constraints/assumptions/success/non-goals, not a hand-maintained
summary from a previous revision. After the user's actual confirmation, set
`owner_confirmation.snapshot_hash` to that preview's hash. A semantic edit makes
the snapshot stale and requires a fresh preview + confirmation. Historical briefs
without `decision_ledger_version` remain readable under legacy validation.

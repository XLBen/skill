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
      "owner_confirmed": true
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

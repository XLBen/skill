---
project: fixture
status: final
brief-hash: 188218eecab726236318a646f63385aa6f11b92fde32309ad8975b21ef6bacc2
---

# Fixture Requirement Brief

The owner needs a deterministic artifact.

```json brief
{
  "schema_version": 1,
  "revision": 1,
  "status": "final",
  "summary": "Produce a deterministic artifact from a reviewed contract",
  "items": [
    {
      "id": "BF-01",
      "kind": "fact",
      "statement": "The repository contains a deterministic compiler",
      "source": "repository inspection",
      "evidence_status": "verified"
    },
    {
      "id": "BD-01",
      "kind": "decision",
      "question": "Should equal contracts produce equal plans?",
      "choice": "Yes",
      "rationale": "Determinism makes validation and recovery reliable",
      "owner_confirmed": true
    },
    {
      "id": "BS-01",
      "kind": "success",
      "statement": "The same contract always produces the same plan",
      "source": "owner"
    }
  ],
  "frontier": [],
  "owner_confirmation": {
    "confirmed": true,
    "summary": "The owner confirmed the goal, determinism decision, and success signal"
  }
}
```

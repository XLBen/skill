---
project: fixture
status: passed
phase: idle
contract-hash: eedaea79c9691e9a72edc9acd591c758423448339f8123278f46ecdba8bacdf6
---

# Fixture Contract

```json contract
{
  "profile": "light",
  "intake": {
    "mode": "direct"
  },
  "control": {
    "interaction": "checkpoints",
    "audit_budget": 2,
    "research_budget": 1,
    "prototype_budget": 1
  },
  "nodes": {
    "P": [
      {
        "id": "P-01",
        "status": "active",
        "supersedes": [],
        "superseded_by": [],
        "scope": "local",
        "statement": "Produce a deterministic artifact",
        "source": "user-direct",
        "source_revision": "EV-REQ-01",
        "priority": "must",
        "success": "The same contract produces the same plan"
      }
    ],
    "T": [],
    "W": [],
    "F": [
      {
        "id": "F-01",
        "status": "active",
        "supersedes": [],
        "superseded_by": [],
        "scope": "local",
        "name": "Compile contract",
        "serves": ["P-01"],
        "predecessors": ["START"],
        "preconditions": ["Contract is valid"],
        "inputs": [{"name": "contract", "type": "json"}],
        "actions": ["Canonicalize", "Compile"],
        "outputs": [{"name": "plan", "type": "json"}],
        "branches": [],
        "failures": [],
        "terminal": "success",
        "verifications": ["V-01"]
      }
    ],
    "I": [
      {
        "id": "I-01",
        "status": "active",
        "supersedes": [],
        "superseded_by": [],
        "scope": "local",
        "name": "Compiler implementation",
        "kind": "build",
        "realizes": ["F-01"],
        "validates": [],
        "depends_on": [],
        "change_boundary": "scripts only",
        "variants": [
          {
            "id": "base",
            "selector": {"default": true},
            "uses": [],
            "interface_equivalence": "deterministic plan contract",
            "segments": [
              {
                "id": "01",
                "depends_on_segments": [],
                "actions": ["Implement compiler"],
                "artifacts": ["scripts/check.py"],
                "interfaces": ["compile(contract) -> plan"],
                "side_effects": ["file-write"],
                "idempotency": "canonical output replaces the target",
                "build_rollback": "restore the previous generated plan",
                "segment_verifications": ["V-01"]
              }
            ]
          }
        ]
      }
    ],
    "D": [],
    "E": [],
    "A": [],
    "R": [],
    "V": [
      {
        "id": "V-01",
        "status": "active",
        "supersedes": [],
        "superseded_by": [],
        "scope": "local",
        "type": "local",
        "covers": ["P-01", "F-01", "I-01"],
        "prerequisites": [],
        "stage": "after-I-01/base/01",
        "command": "python scripts/check.py --selftest",
        "observation": "",
        "expected": "exit 0"
      }
    ],
    "B": [
      {
        "id": "B-01",
        "status": "active",
        "supersedes": [],
        "superseded_by": [],
        "scope": "local",
        "exclusion": "Semantic truth inference",
        "reason": "The deterministic engine cannot decide arbitrary natural language"
      }
    ]
  }
}
```

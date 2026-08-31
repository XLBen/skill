---
project: fixture
contract-hash: eedaea79c9691e9a72edc9acd591c758423448339f8123278f46ecdba8bacdf6
plan-structure-hash: ea47f5f32fa9213f9526952ccb62922e191221a6be6f268cae55d8a24c243671
status: planning
---

# Construction Plan

```json plan
{
  "contract_hash": "eedaea79c9691e9a72edc9acd591c758423448339f8123278f46ecdba8bacdf6",
  "plan_structure_hash": "ea47f5f32fa9213f9526952ccb62922e191221a6be6f268cae55d8a24c243671",
  "runtime": {
    "attempts": {},
    "selected_variants": {},
    "selection_events": {},
    "status": "planning",
    "step_states": {
      "S-I01-base-01": "dormant"
    }
  },
  "steps": [
    {
      "actions": [
        "Implement compiler"
      ],
      "artifacts": [
        "scripts/check.py"
      ],
      "build_rollback": "restore the previous generated plan",
      "depends_on_segments": [],
      "id": "S-I01-base-01",
      "idempotency": "canonical output replaces the target",
      "interfaces": [
        "compile(contract) -> plan"
      ],
      "segment": "01",
      "side_effects": [
        "file-write"
      ],
      "unit": "I-01",
      "variant": "base",
      "verifications": [
        "V-01"
      ]
    }
  ],
  "unit_dag": [],
  "variant_rules": {
    "I-01": [
      {
        "id": "base",
        "selector": {
          "default": true
        }
      }
    ]
  }
}
```

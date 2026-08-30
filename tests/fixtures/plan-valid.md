---
project: fixture
contract-hash: ce50b6385e574c76c12a9103d2ea9ba69feec4949e82bb2246cc76cd24d7ff48
plan-structure-hash: 7ef7f61f0679fc355872623630e4d8172879afbd7550855b3baaed636dacb1fb
status: planning
---

# Construction Plan

```json plan
{
  "contract_hash": "ce50b6385e574c76c12a9103d2ea9ba69feec4949e82bb2246cc76cd24d7ff48",
  "plan_structure_hash": "7ef7f61f0679fc355872623630e4d8172879afbd7550855b3baaed636dacb1fb",
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

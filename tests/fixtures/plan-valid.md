---
project: fixture
contract-hash: e0d0872536ca22c749651120328d1136fdc1182169a0be2184e0a5cba4eda120
plan-structure-hash: d9bc1036e23e6a7385a7e52e980b496e3c106589f4f717e8473fb05684dd17c6
status: planning
---

# Construction Plan

```json plan
{
  "contract_hash": "e0d0872536ca22c749651120328d1136fdc1182169a0be2184e0a5cba4eda120",
  "plan_structure_hash": "d9bc1036e23e6a7385a7e52e980b496e3c106589f4f717e8473fb05684dd17c6",
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

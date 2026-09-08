---
project: fixture
contract-hash: 62502102da2c7399afec13e93f780d83cc2709d54c16e43f3fc006f254700122
plan-structure-hash: c0e827c9e1342a2352fa0896279238fa32ad55dd2505ac377f0c60c3087eccb2
status: planning
---

# Construction Plan

```json plan
{
  "contract_hash": "62502102da2c7399afec13e93f780d83cc2709d54c16e43f3fc006f254700122",
  "plan_structure_hash": "c0e827c9e1342a2352fa0896279238fa32ad55dd2505ac377f0c60c3087eccb2",
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

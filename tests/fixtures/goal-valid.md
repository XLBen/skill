---
status: active
---

# Goal Fixture

```json goal
{
  "schema_version": 1,
  "id": "G-FIXTURE",
  "status": "active",
  "source": {"type": "direct", "raw_request": "Show a greeting through the CLI."},
  "goal": "A user can request a greeting",
  "rigor": "normal",
  "risk": {"factors": ["none"], "rationale": "Local disposable demonstration"},
  "first_slice": "CLI greeting",
  "demo": "Run the greeting command",
  "constraints": [],
  "deferred": [],
  "outcomes": [{
    "id": "O-01",
    "statement": "The CLI prints the requested greeting",
    "status": "pending",
    "user_entry": true,
    "verification": {
      "command": "python -c \"print('Hello user')\"",
      "expected": "The greeting is visible on stdout",
      "assertion_kind": "user-visible",
      "empty_result_policy": "Empty stdout fails the literal assertion",
      "assertion": {"type": "stdout-contains", "literal": "Hello user"},
      "timeout_seconds": 5
    }
  }]
}
```

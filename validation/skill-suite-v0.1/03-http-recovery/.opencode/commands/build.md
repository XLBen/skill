---
description: Execute the confirmed PLAN with step verification and evidence
model: zhipuai-coding-plan/glm-5.3-flash
---

Load the `construction` skill and start construction. For a v0.1 slice, invoke
the independent `test-author` skill first, freeze the acceptance test hashes,
then pass the protected test paths to the implementation executor.
If PLAN is missing or stale, delegate planning to `contract-review`; do not
compile PLAN inside construction. After the third consecutive failure with the
same normalized signature, stop and escalate instead of running a fourth
ordinary retry.

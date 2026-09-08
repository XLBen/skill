---
description: Generate and freeze red-phase acceptance tests before implementation
model: zhipuai-coding-plan/glm-5.3-flash
---

Load the `test-author` skill for the specified v0.1 first slice or SI:

$ARGUMENTS

Read only the fixed specification and allowed test context. Write the
acceptance tests and `docs/test-manifests/<slice-id>.md`, run the exact test
command before implementation, and require a real failed assertion. Record the
spec hash, test file hashes, author/session ID, and red output. Do not write
product code, edit contract/PLAN artifacts, or repair a passing-on-first-run
test; report those cases as a CR blocker.

---
description: Probe the riskiest assumption, then turn confirmed requirements into a thin reviewed implementation contract
model: zhipuai-coding-plan/glm-5.3
---

Load the `contract-review` skill and run its v0.1 review workflow for:

$ARGUMENTS

If the input is unclear, costly, irreversible, privacy/security sensitive, or
otherwise high-risk, load `grill` first instead of guessing. Consume
`docs/brief.md` only when the arguments name it. If no arguments were given,
ask for the requirements or explicit brief path instead of guessing from an
old file. For a new `light`/`full` or grilled request, rank assumptions and run
the Phase 0 risk probe before drafting the first thin end-to-end slice. Do not
use `docs/change-orders.md` for planned slice growth; use an SI record after
the current slice is accepted.

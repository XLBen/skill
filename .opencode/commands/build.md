---
description: Execute the engineering plan task by task with layered real feedback
agent: build
---

Load `mvp-delivery` in Build Mode for:

$ARGUMENTS

Resolve the planner's complete design first; if none exists, complete the
writing-plans workflow before implementing. Do not redesign architecture,
interfaces or acceptance criteria in the implementation loop.

Use `check.py next-step <goal>` for the current bounded task and relevant shared
contracts. Read its named inputs only, begin the cycle, implement this task,
run its component/boundary checks or milestone journeys, inspect actual output,
and observe the result before the next task. Missing environment -> blocked;
invalid design assumption -> replan with evidence. Later tasks must not be
implemented just to make a component's check pass.

Respect pending_conditions and missing_preflight_files; do not convert blocked
technical conditions into approval claims. Unknown action outcomes need readback
before retries. For owner intervention, request-decision preserves the current
attempt and pauses new operations; resolve-decision records the actual reply.
An ambiguous "never mind" is not acceptance. See planning-readiness.md.

`mvp-delivery/references/engineering-delivery.md` defines the small command loop.
Expand `mvp-delivery/references/subagent-orchestration.md` only when delegating;
give workers the current package rather than all skills/history. Load
`i-have-adhd` for progress and final reporting. Finish after the whole original
goal and its final acceptance, not merely the first slice.

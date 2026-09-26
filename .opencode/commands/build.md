---
description: Execute the engineering plan task by task with layered real feedback
agent: build
---

Load `mvp-delivery` in Build Mode for:

$ARGUMENTS

At each current task boundary select only matching skills from
`mvp-delivery/references/stage-routing.json`: `skill-creator` for skill
authoring, `frontend-design` for requested visual construction,
`vercel-react-best-practices` for relevant React/Next.js code, and
`receiving-code-review` when review feedback is handed back. Have the actual
executing seat load the original skill, not a controller-authored summary.

Require an existing valid plan: resolve and validate the planner-authored design
before implementing.
If the plan is missing or invalid, stop before product edits and direct the user
to `/plan`; do not create or repair a plan inside an explicit `/build`. Do not
redesign architecture, interfaces or acceptance criteria in the implementation
loop. Uncommanded requests follow the work/fix routing rules instead.

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

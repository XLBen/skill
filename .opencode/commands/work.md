---
description: Autonomously understand, plan, execute, and verify a goal to completion
agent: build
---

Load the `work` skill and start its end-to-end goal loop for:

$ARGUMENTS

If the request is vague, use `grill` in autonomous inference mode: inspect the
conversation, repository, and available evidence; infer reversible defaults;
keep uncertain inferences labeled as assumptions; do not fabricate user answers
or confirmations. Ask only when a material owner decision, authorization, or
unavailable prerequisite genuinely prevents safe progress.

Discover applicable skills from the skills actually available in this OpenCode
session. Do not use a fixed skill allowlist. Continue through planning, work,
verification, evidence-backed repair/replanning, and final acceptance without
handing the user another command to run. Do not create brief/plan/checkpoint
documents solely as ceremony; create artifacts required by the requested result
or an applicable rigor, audit, handoff, or recovery gate.

Use the conditional capabilities in `mvp-delivery/references/stage-routing.json`
at the actual boundary: `skill-creator` for skill authoring/evaluation,
`receiving-code-review` when findings arrive, `frontend-design` for requested
visual design, and `vercel-react-best-practices` for applicable React/Next.js
code. Load each original skill through the skill tool only when its trigger
matches; do not copy a short paraphrase into the task packet.

Continue until every original required outcome is verified, or report the exact
external decision, authorization, or capability that blocks further progress.
Follow `mvp-delivery/references/subagent-orchestration.md` for required seats,
dynamic skill applicability, independence, and evidence routing. Load
`i-have-adhd` for concise progress and final delivery without omitting facts.

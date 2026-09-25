---
description: Design the complete software from a confirmed brief or clear goal and hand build fully specified tasks
agent: build
---

Load `writing-plans` as the primary workflow for:

$ARGUMENTS

Act as the engineering designer, not an interviewer or implementation worker.
For a skill-authoring goal, load `skill-creator` when available. For an
explicit visual-design goal load `frontend-design`; for a React/Next.js design
load `vercel-react-best-practices` only when its rules match actual code.
When revising a design in response to review findings, load
`receiving-code-review` before accepting or rejecting them. Use the original
skills through the skill tool and retain the existing plan/owner boundaries.
For high-level system architecture design or review, or significant
architectural decisions, load the original `architecture-designer` skill through
the skill tool. Follow its original ADR and stakeholder-review requirements;
do not claim a stakeholder review occurred without an actual reply.
Synthesize the confirmed brief or clear goal into system design, verified technical decisions, shared data
and interfaces, flow/dependency diagrams, and fully specified implementation
tasks for the ENTIRE goal. Every task includes key code, layered checks and
failure handling; later tasks are not headings left for build to design.
Perform the design walkthrough before publishing. Use the user's chosen path
or docs/plan.md; the file location is a convention, not a quality gate.

Use engineering-plan/3. Preserve complete scope but distinguish executable
tasks from conditional designs. Check the empty-project bootstrap, timing/waits,
unknown-result retries, acceptance equivalence and user acceptability via
writing-plans/references/engineering-challenges.md. Critical unmeasured claims
need conditions, not invented details; guarded/audited implementation waits
for independent design review. A fallback proposal alone closes no risk.

Use prepare-plan to derive bindings/UI obligations, and next-step to inspect
the bounded task package build will consume. Product code stays read-only.
Read mvp-delivery/references/goal-definition.md only for publication, and
mvp-delivery/references/subagent-orchestration.md only if research/review is
actually delegated. Do not load the entire construction/audit workflow to plan.
Load i-have-adhd for the chat summary only, never shorten the design itself.
Link the complete plan, summarize decisions and unresolved feasibility conditions,
then hand off with `/build`. Do not report planned tests as executed evidence.

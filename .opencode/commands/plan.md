---
description: Turn a goal or confirmed brief into a right-sized executable plan
agent: build
---

Load the `mvp-delivery` skill in Plan Mode for:

$ARGUMENTS

Load `i-have-adhd` for the plan preview, owner decision prompt and final handoff.
Keep the complete `ACCEPTANCE_HANDOFF` for PUA/reviewer; a concise preview is
not evidence or PLAN confirmation.

Inspect the repository (dispatch read-only research seats for unfamiliar
modules or dependency questions per
`mvp-delivery/references/subagent-orchestration.md`; planning never
dispatches writers) and produce a right-sized goal card with observable
success, the first runnable slice, deferred outcomes, and engine-executable
verification in the schema-1 `json goal` fence. Reuse a matching unfinished
card. No outcome-count cap; cover all IDs of any explicitly supplied final,
owner-confirmed brief and run `brief` and `goal` validation in every risk mode.
Every `kind: success` (BS) must have disposition `outcome`, never constraint,
deferred, non-goal or rejected; other kinds retain existing dispositions. At least
one outcome must set `user_entry: true` in every goal status. These are structural
checks, not proof of semantic coverage. Keep required success in outcomes even
when scheduled for later slices; record missing implementation separately from
missing verification without replacing real device/API scope with samples or mocks.
Optional wishes must not be mislabeled BS then silently removed; scope changes
need renewed explicit confirmation and must respect frozen briefs/packages. Do not
write product code. For an Audited slice, load `contract-review` internally and
produce its validated contract and PLAN; do not ask the user to invoke a
separate review command. New contracts declare top-level `workflow_protocol: v0.2`;
obtain actual owner confirmation of the generated PLAN. If a required
approval or independent review is unavailable, report the blocker; otherwise
load the `pua` skill for `goal-validation`, `contract-release` or
`plan-confirmation` as applicable, then end with one clear handoff: `/build`.

Include the intended delivery form, target environment and prerequisites, actual
user entry and representative input/result. Map each promised user-facing outcome
to a public-interface journey using existing card fields; shared journeys are fine.
When an affected outcome includes an interface journey, declare `goal.ui.required`
(with optional `outcome_ids`) and design the UI acceptance scenarios and
prerequisites in the sidecar; never operate the UI in `/plan`.
Do not assume agent-only setup is available to the user or add unrequested deployment.

---
description: Resume the active goal from its durable state and continue to completion
agent: build
---

Load the `mvp-delivery` skill in Resume Mode. Find the active goal card under
`.opencode/mvp/` (blocked cards are unfinished too). If no unfinished goal
exists, look for a recognizable unfinished strict package (legacy root
`docs/PLAN.md` or a non-done `docs/audit-slices/` PLAN) and resume it under
mvp-delivery's Build rules: establish and validate the current goal card
first, then load the construction phase internally. Only when no goal and no
strict package exists and `docs/brief.md` is draft, validate it, load `grill`
and resume its persisted revision/frontier and recorded mode (default stepwise
if not recorded). Save and validate the updated draft before asking the next
round or pausing; do not start construction. If multiple unrelated candidates
exist (several active cards, or a strict package plus an unrelated draft),
ask which target to resume; never pick by mtime. If no target exists, ask
what to resume.

Load `i-have-adhd` for resumed progress, acceptance-preview, delivery and
blocker output. Before re-dispatching, reconcile
`.opencode/mvp/<goal-slug>.dispatch.json` with actual artifacts per
`mvp-delivery/references/subagent-orchestration.md`: a task marked done is
reused only when its product is unchanged and, for review tasks, its recorded
acceptance verdict still holds — pending owner/controller actions from an
`owner`/`blocked` verdict must run first, even if product files are
unchanged. A timeout is not proof of non-execution, so verify the working
tree before replaying write tasks; records missing result references are
rebuilt, not trusted from their status label.
On each Guarded/Audited material handoff, dispatch a fresh reviewer and pass the full
`ACCEPTANCE_HANDOFF` with `pua_stage_id` before reporting completion; stale
review results are not evidence for changed artifacts. If a
`ui-acceptance/1` sidecar exists, re-observe the current window/app state and
re-execute scenarios whose artifact binding no longer matches; never replay
stale clicks or reuse observations of an older build.
For an Audited goal, reconcile its named package and load the appropriate
planning or construction phase internally. Validate `goal` and its final source
brief before product edits; do not substitute a complete history card. Reset
affected outcomes to pending and clear runtime evidence references/blockers before
product changes, retaining evidence files; definition changes require full
invalidation and complete cards are never reopened. Reconcile card status and
revalidate under `mvp-delivery`, then re-run applicable engine verification,
continue at the first pending or blocked outcome, and keep going until the
original goal is complete. Ask only if multiple active goals make the target
ambiguous, the completed repair base is unclear, or a mandatory gate requires
owner authority. SI acceptance and new PLAN confirmation remain mandatory.

Do not treat old passing evidence as proof of the current product state. Apply
`mvp-delivery`'s Finish With Evidence gate before completion, including integrated
user journeys and isolated setup/use replay from declared artifacts/dependencies.
Compare the original request/all brief BS, whole goal and deferred work, not just
the clean current slice. Required success and original real boundaries stay in
outcomes; missing implementation/verification remain distinct pending/blocked gaps.
Report delivery location, prerequisites,
working directory/use steps or verified quickstart, sample result, tested environment
and limitations; for Audited goals or missing/suspect evidence load the `pua`
skill for the resumed `stage_id` before the handoff and for `goal-finish` before
completion. On blockage, state what remains
unusable and the next owner action.

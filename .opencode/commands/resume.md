---
description: Resume the active goal from its durable state and continue to completion
agent: build
---

Load the `mvp-delivery` skill in Resume Mode. Find the active goal card under
`.opencode/mvp/` (blocked cards are unfinished too). If no unfinished goal exists
and `docs/brief.md` is draft, validate it, load `grill` and resume its persisted
revision/frontier and recorded mode (default stepwise if not recorded). Save and
validate the updated draft before asking the next round or pausing;
do not start construction. If no target exists, ask what to resume.
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
and limitations; on blockage, state what remains unusable and the next owner action.

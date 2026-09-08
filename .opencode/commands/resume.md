---
description: Resume the active goal from its durable state and continue to completion
agent: build
---

Load the `mvp-delivery` skill in Resume Mode. Find the active goal card under
`.opencode/mvp/` (blocked cards are unfinished too). If no unfinished goal exists
and `docs/brief.md` is draft, load `grill` and resume its persisted frontier;
do not start construction. If no target exists, ask what to resume.
For an Audited goal, reconcile its named package and load the appropriate
planning or construction phase internally. Validate `goal` and its final source
brief, then re-run applicable engine verification,
continue at the first pending or blocked outcome, and keep going until the
original goal is complete. Ask only if multiple active goals make the target
ambiguous, the completed repair base is unclear, or a mandatory gate requires
owner authority. SI acceptance and new PLAN confirmation remain mandatory.

Do not treat old passing evidence as proof of the current product state. Apply
`mvp-delivery`'s Finish With Evidence gate before completion, including integrated
user journeys and setup/use replay. Report delivery location, prerequisites,
working directory/use steps or verified quickstart, sample result, tested environment
and limitations; on blockage, state what remains unusable and the next owner action.

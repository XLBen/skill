---
description: Build and verify a goal continuously until its original outcomes are met
agent: build
---

Load the `mvp-delivery` skill in Build Mode for:

$ARGUMENTS

Resolve and reuse a matching unfinished goal even when arguments are supplied;
never create a second active card for the same work. Otherwise find the single
active `.opencode/mvp/` goal card or confirmed strict PLAN; if neither exists
and no goal was supplied, ask for the goal. Before product edits, establish or
reuse the current unfinished card and pass `goal` plus any final source `brief`
validation; a strict PLAN or old complete card is not a substitute. Before each
product change reset affected outcomes to pending and clear runtime evidence
references/blockers, retaining evidence files and reconciling card status under
`mvp-delivery` before revalidation; definition changes invalidate all
outcomes under `mvp-delivery`. Never reopen complete cards.
Implement the thinnest runnable slice, verify real behavior,
then continue through remaining original outcomes without requiring another
command. For an Audited PLAN, load `construction` internally and run its
finish/reconcile gate for the current slice. If the goal card still has pending
outcomes, prepare the next SI/PLAN internally and continue construction. Do not
stop merely because the first slice passed. Do stop for the owner's actual
slice acceptance, SI decision, new PLAN confirmation, or risky-command approval;
initial goal approval is not preauthorization. Validate the JSON goal and any
final source brief; use `verify-goal` for every outcome and `finish-goal`, never
manual verified/complete. Automated Audited V uses `verify-step`.

Before completion, follow `mvp-delivery`'s Finish With Evidence gate: verify the
final integrated deliverable against the original request/all brief BS, entire
goal and deferred work, not just a clean slice audit. Required success stays an
outcome; missing implementation and missing real-boundary verification separately
remain pending/blocked, never hidden in deferred or replaced by mock/sample scope.
Create missing README/quickstart or update existing instructions and replay setup/use
from declared artifacts/dependencies in isolation, not borrowed global packages.
Report location, prerequisites, working directory and exact use steps
(or the verified quickstart), sample input/result, tested environment and limitations.
If blocked, say what remains unusable and the smallest required owner action.

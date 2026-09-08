---
description: Build and verify a goal continuously until its original outcomes are met
agent: build
---

Load the `mvp-delivery` skill in Build Mode for:

$ARGUMENTS

Resolve and reuse a matching unfinished goal even when arguments are supplied;
never create a second active card for the same work. Otherwise find the single
active `.opencode/mvp/` goal card or confirmed strict PLAN; if neither exists,
ask for the goal. Implement the thinnest runnable slice, verify real behavior,
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
final integrated deliverable through its real user journeys and replay its setup/use
instructions. Report location, prerequisites, working directory and exact use steps
(or the verified quickstart), sample input/result, tested environment and limitations.
If blocked, say what remains unusable and the smallest required owner action.

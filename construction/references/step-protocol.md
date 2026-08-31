# Step And Recovery Protocol

> When to read: before executing any selected step, and before any failure or
> CR recovery action.

Read `contract-schema.md` and validate PLAN before every start or resume.

## Lifecycle

```text
pending -> selected -> executing -> verifying -> complete
                          |              |
                          +-> blocked <--+
complete -> invalidated
```

Only a step in the selected variant can leave `dormant`. Before execution,
record an attempt ID, expected state revision, environment binding, declared
side effects, and idempotency strategy. Persist evidence before advancing the
state projection.

Write each lifecycle change as a `step-transition` JSON event and apply it with
`check.py plan-event`. A transition to `complete` includes the passed immutable
`attempt_id`; the engine rejects completion without matching V evidence. Pause,
resume and suspend use `plan-transition` events through the same command.
Every runtime event binds `contract_hash` and `plan_structure_hash`; step events
also bind the canonical `step_hash`. Every event supplies `expected_revision`
for CAS. `done` is reserved for `check.py finish-plan`, which also verifies
clean reconcile and a bound converge audit.

Selection, attempt, and verification events include the current contract hash,
PLAN structure hash, and canonical step hash. Never reuse evidence after any
of those hashes changes.

## Recovery

- No side effect and idempotent: replay the attempt or start a new one.
- File write: inspect artifacts and postconditions before replacing anything.
- Migration or remote call: inspect the external idempotency key and
  postcondition; compensate only as declared by the segment.
- Never infer completion from files existing. `complete` requires fresh V
  evidence and an applied event.

## Minimal Diff

For every changed hunk ask whether removing it would make the selected segment
or its V fail. Keep necessary hunks. Revert unrelated style work. Record a
real independent issue for later instead of implementing it. A missing segment
is a contract defect and returns through CR; construction does not append an
unreviewed semantic step.

## Red-Green Inside A Segment

When a segment's local V carries `red_command`, execution follows
red-green-refactor inside the segment:

1. Run `red_command` first and persist the failing output as a `tdd-red`
   evidence event bound to the current contract/PLAN/step hashes.
2. Implement the minimal change that turns it green; record `tdd-green` with
   the passing output.
3. Refactor while green, then run the segment's exact V command as usual.

`direct` profile may skip the ceremony when the owner asks; `light`/`full`
treat red evidence as required whenever `red_command` exists. Never weaken or
substitute either command. A red that passes on the first run means the test
or the segment spec is wrong — that is a CR, not a green light.

## Variant Selection

S0 may select only a variant already compiled in PLAN. The selector consumes a
named E result and must choose exactly one variant. An unlisted wheel, custom
implementation, interface change, or ambiguous selector creates blocking CR.

## Isolated Execution (Optional)

Enabled when the contract interaction is `checkpoints`/`stepwise` or the
profile is `full`. The controller loads the `step-executor` skill for each
selected step, passing only that step's spec and its exact V; the
controller stays responsible for state, the ledger, and event recording, and
the attempt event carries the executor's `subagent_id`.

Two gates close every step:

1. Machine gate — the exact V passes and a `step-verification` event bound to
   the current contract/PLAN/step hashes is recorded.
2. Review gate — the reviewer audits the step diff for spec compliance and
   implementation quality. A `hard` issue blocks `complete` exactly like a
   failed V; soft issues are logged for retro.

A `direct` profile or `autonomous` interaction stays in-session by default;
the review gate still applies when the owner asks for it.

## CR Recovery Capability

Blocking CR disables normal steps but not `cr-recovery`. That capability may
only:

1. recompile the approved contract;
2. invalidate affected steps using typed dependent edges;
3. perform declared rollback/compensation;
4. redo affected selected steps;
5. execute additional V;
6. advance `approved -> applying -> verifying -> verified`.

Recovery compile and plan validation supply the archived previous contract and
may change only contract nodes, variants, steps, and DAG edges in the target
CR's typed impact closure.

No user signature can bypass a refuted fact, unsafe destructive behavior,
missing acceptance criterion, or incompatible interface. CR state exists only
in `docs/change-orders.md`; PLAN and logs reference CR IDs without copying its
status.

## Completion

Generate P -> F -> I -> selected S -> V coverage from engine data. Human V
requires an explicit owner event. Set PLAN `done` only when every selected step
is complete, all blocking CR are absent, and final coverage passes; apply the
`done` transition with `check.py finish-plan`, never by editing PLAN.

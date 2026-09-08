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
side effects, idempotency strategy, and the implementation author ID. For a
v0.1 first slice or SI, a separate test-author manifest must already record the
spec hash, test author ID, protected test files/hashes, and red evidence.
Persist evidence before advancing the state projection.

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

## Acceptance Evidence

Every new v0.1 non-human V is written and reviewed as:

```text
Given: specific data and starting state
When: exact command or user action
Then: concrete content, invariant, schema, count, or user-visible assertion
Empty-result policy: missing/empty/zero-row output fails by default
```

Exit 0 is only an execution signal. The V must inspect the result it claims to
verify. A semantic zero is legal only when the scenario explicitly expects it
and asserts the reason. A fake DOM, mock external boundary, process existence,
or non-empty log does not prove a real user path.

## Minimal Diff

For every changed hunk ask whether removing it would make the selected segment
or its V fail. Keep necessary hunks. Revert unrelated style work. Record a
real independent issue for later instead of implementing it. A missing segment
is a contract defect and returns through CR; construction does not append an
unreviewed semantic step.

## Red-Green Inside A Segment

When a segment's local V carries `red_command`, execution follows
red-green-refactor inside the segment. For a v0.1 first-slice/SI acceptance
test, the separate test-author performs the red phase before step-executor is
called:

1. Run `red_command` first and persist the failing output as a `tdd-red`
   evidence event bound to the current contract/PLAN/step hashes.
2. Implement the minimal change that turns it green; record `tdd-green` with
   the passing output.
3. Refactor while green, then run the segment's exact V command as usual.

`direct` profile may skip only an acceptance test that the owner explicitly
records as not applicable for a no-product-behavior change. For every v0.1
acceptance V, never weaken or substitute either command. A red that passes on
the first run means the test or the segment spec is wrong — that is a CR, not a
green light. The test-author freezes the test hash after red; an implementation
author may not modify it.

## Variant Selection

S0 may select only a variant already compiled in PLAN. The selector consumes a
named E result and must choose exactly one variant. An unlisted wheel, custom
implementation, interface change, or ambiguous selector creates blocking CR.

## Isolated Execution (Optional)

Enabled when the contract interaction is `checkpoints`/`stepwise` or the
profile is `full`. For v0.1 acceptance work, the controller first loads
`test-author`, then loads `step-executor` for each selected step, passing only
that step's spec, its exact V, and the protected test-file list. The controller
stays responsible for state, the ledger, and event recording, and the attempt
event carries the executor's `subagent_id` as implementation author.

Two gates close every step:

1. Machine gate — the exact V passes and a `step-verification` event bound to
   the current contract/PLAN/step hashes is recorded.
2. Test-integrity gate — for v0.1, the manifest's test author differs from the
   implementation author, protected test hashes are unchanged, and red
   evidence precedes implementation/green evidence.
3. Review gate — the reviewer audits the step diff for spec compliance, real
   result assertions, test integrity, and implementation quality. A `hard`
   issue blocks `complete` exactly like a failed V; soft issues are logged for
   retro.

A `direct` profile or `autonomous` interaction stays in-session by default;
the v0.1 test-integrity and acceptance gates still apply whenever a product V
exists. Only the separate subagent dispatch can be skipped for an explicitly
owner-approved no-test direct change.

## Failure Signature And Circuit Break

For every failed V, calculate a stable signature:

```text
V ID + command/scenario ID + failing assertion or exception type +
stable error summary
```

Remove timestamps, absolute paths, random IDs, and stack line numbers. A
changed attempt ID or wording does not reset the signature. Record the raw
output/hash, `started_at`, `finished_at`, `elapsed_seconds`, and author IDs in
the build log and v0.1 observation report; include the signature in the
attempt metadata when the event format permits it.

- Attempts 1 and 2 may repair only the current segment for an implementation
  defect with safe/idempotent side effects.
- The third consecutive failure with the same signature is the circuit-break
  event. Count that attempt in cost, stop immediately, and do not run a fourth
  ordinary retry.
- Escalate with the three raw results, accumulated attempts and elapsed time,
  projected cost at the observed rate, and at least two options with cost and
  risk. Move the prompt-layer run to `awaiting-owner` or `suspended`.
- A different signature requires root-cause reclassification; it is not an
  unlimited retry allowance. Existing budget and no-progress suspension rules
  still apply.

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

# Step And Recovery Protocol

> When to read: before executing any selected step, and before any failure or
> CR recovery action.

Read `../../contract-review/references/contract-schema.md` and validate PLAN
before every start or resume.

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
spec hash, test author ID, protected acceptance paths/hashes, and targeted
behavior-red or existing regression baseline-green evidence.
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

New Audited contracts use top-level `workflow_protocol: v0.2`. The older v0.1
authorship, review, budget and observation rules below also apply to v0.2.
Every new non-human V is machine-validated and reviewed as:

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

After recording the attempt and moving the selected step to `verifying`, the
controller runs each bound non-human V through the engine, from the project root:

```text
python .opencode/workflow/scripts/check.py verify-step <slice>/PLAN.md S-I01-main-01 V-01 --contract <slice>/contract.md --ledger <slice>/workflow-events.jsonl --evidence <slice>/evidence/S-I01-main-01-V-01-01.json --event-id EV-VERIFY-01
```

Use actual compiled S/V IDs. Evidence must be inside the contract package's
`evidence/` directory. A new attempt uses a new event ID and unused evidence
path; retrying the same ID/path retrieves its recorded result, not a new run.
The engine executes the exact contract command, captures output/exit/timeout,
and appends the hash-bound `step-verification` event. Do not manufacture passing
events with `record` or copy executor output into a claimed engine result.
Only after all V, review and integrity gates pass may `plan-event` apply
`complete`; never edit that status manually. Human V instead needs a real owner
event and cannot run via `verify-step`.

Commands run with `shell=True` in the system shell (`cmd.exe` on Windows, not
PowerShell), using the caller's cwd. Inspect shell quoting and side effects;
obtain explicit authorization before risky commands. The engine is not a
sandbox. Step success checks exit/timeout, so the test command itself must fail
on a violated content/state assertion; descriptive `then`/`expected` is not
executed by the engine. Hashes do not authenticate authors or prove usability.

For a long-running app or service, the bound verification command must be a
bounded lifecycle: start an owned instance of the current build, record its
identity/address, wait for readiness with a deadline, execute the actual user
journey and content/state assertions, then clean up owned processes and test
state on success, failure, or timeout. Bound the entire run, including cleanup;
report cleanup failure as a blocker. A readiness probe alone is not acceptance.
Never reuse or terminate an arbitrary listener on a convenient port. An address
collision requires a safe declared binding or a blocker, not attachment to an
unknown process. The controller owns this lifecycle and checks its raw evidence;
the engine's command timeout alone does not guarantee child-process cleanup.

Compare runner results with the manifest's expected critical scenario IDs and
boundary/mock policy. Every required scenario must actually execute its
assertions; skip, todo, exclusive/filter selection that omits one, or an empty
suite cannot pass, even with exit 0. Preserve per-scenario results in existing
evidence. Controller/reviewer inspection supplies this integrity check, not a
claim that the engine understands runner discovery or mock semantics.

For native GUI boundaries, the main controller loads `computer-use`; see
`../../computer-use/SKILL.md`. Serialize its interactive session with any GUI
test runner. Executors/test authors supply scenarios, not competing desktop
actions; reviewers inspect evidence read-only. Interactive MCP output is only
supporting evidence, never a `step-verification` event. Keep automated V on a
real bounded `verify-step` runner; human V uses the existing owner-decision gate.
Missing desktop tools or an unexecutable V blocks that verification rather than
authorizing a fake pass or a silent change of verification type.

## Minimal Diff

For every changed hunk ask whether removing it would make the selected segment
or its V fail. Keep necessary hunks. Revert unrelated style work. Record a
real independent issue for later instead of implementing it. A missing segment
is a contract defect and returns through CR; construction does not append an
unreviewed semantic step.

## Red-Green Inside A Segment

When a segment's local V carries `red_command`, execution follows
red-green-refactor inside the segment for new/changed targeted behavior. The
controller first ensures scoped setup/harness readiness; the separate
test-author performs the pre-change run before behavior implementation:

1. Run `red_command` first and persist the failing output as a `tdd-red`
   evidence event bound to the current contract/PLAN/step hashes. It must fail
   on the targeted behavior assertion, not parsing, missing fixtures, runner
   setup, or service readiness.
2. Implement the minimal change that turns it green; record `tdd-green` with
   the passing output.
3. Refactor while green, then run the segment's exact V command as usual.

`direct` profile may skip only an acceptance test that the owner explicitly
records as not applicable for a no-product-behavior change. For every v0.1
acceptance V, never weaken or substitute either command. Existing unaffected
regression scenarios instead require baseline-green before the change and
green afterward; never break working code or fabricate red to satisfy ceremony.
An unexpectedly green targeted red requires a specification/test blocker and
CR adjudication, not an invented failure or unilateral reclassification. A
failing regression baseline must be resolved or adjudicated before proceeding.
Freeze acceptance hashes after the classified pre-change run. Changes follow
the authorization and independent revalidation rule in the test manifest.

## Variant Selection

S0 may select only a variant already compiled in PLAN. The selector consumes a
named E result and must choose exactly one variant. An unlisted wheel, custom
implementation, interface change, or ambiguous selector creates blocking CR.

## Isolated Execution

The implementation seat follows the authoritative Audited Execution Seat
Selection table in
`../../mvp-delivery/references/subagent-orchestration.md`: `direct` stays
in-session; any non-`direct` profile with `full` or
`checkpoints`/`stepwise` interaction dispatches `step-executor`; only
`light + autonomous` stays in-session. For acceptance work, the controller
first dispatches a fresh subagent that loads `test-author`, then (when the
seat table dispatches one) a different fresh subagent that loads
`step-executor` for each selected step, passing a step brief built per
`../../writing-plans/SKILL.md` (Context, exact Files, Change sketch, Bounds,
Verify command, Rollback) plus that step's spec, its
exact V, and the acceptance manifest. Loading a skill in the controller
session is not an independent dispatch. The controller stays responsible for
state, the ledger, and event recording, and the attempt event carries the
executor's real `subagent_id` as implementation author.

Three gates close every step:

1. Machine gate: the exact automated V passes through `verify-step` with its
   generated evidence/event bound to the current contract/PLAN/step hashes;
   human V has an explicit owner event.
2. Test-integrity gate — for v0.1, the manifest's test author differs from the
   implementation author, protected acceptance hashes match the authorized
   manifest, classified pre-change evidence precedes implementation, and all
   expected critical scenarios execute under the declared boundary/mock policy.
3. Review gate — the reviewer audits the step diff for spec compliance, real
   result assertions, test integrity, and implementation quality. A `hard`
   issue blocks `complete` exactly like a failed V; soft issues are logged for
   retro.

Seat selection is not decided "by default" here; it follows the Audited
Execution Seat Selection table in orchestration (only `direct`, or
`light + autonomous`, stays in-session). The v0.1 test-integrity and
acceptance gates still apply whenever a product V exists. Only the separate
test-author dispatch can be skipped for an explicitly owner-approved no-test
direct change.

Independent local steps may run in isolated worktrees only after
`worktree_tasks.py parallel-plan` admits the batch (no step/unit dependency,
provably disjoint write scopes, frozen tests, no protected acceptance paths,
default two writers). Integration is serial; the formal `verify-step` and the
review gate run only on the integrated canonical version, and any failed
condition falls back to serial execution.

When a verification claims isolation, run it through
`verification_runner.py run --mode container` with a named image; a host run is
reported as `isolated: false` and must never be described as sandboxed. The
runner report is evidence input, not an engine pass.

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

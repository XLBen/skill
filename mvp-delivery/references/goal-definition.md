# Goal Definition And Validation

> When to read: when creating or reusing a goal card, validating a card or
> brief, running `verify-goal`/`finish-goal`, or deciding what a definition
> change invalidates. Seat: controller (Audited planning also via
> `contract-review`). Inputs: original request or final brief, repository
> evidence, current card and evidence paths.

## Card Schema

**New product goals use schema 3 with engineering-plan/3.** The planner authors
the complete design and the source/outcomes of the goal. `prepare-plan <goal>
<design-path>` derives `engineering_plan: {path, sha256}` and UI obligations from
the design; the implementation model does not maintain them by hand. Any
project-relative design path is valid. Read `engineering-delivery.md` for the
task-packet loop and layered checks. Historical cards remain readable; new-project
planning does not require legacy migration, and completed history is not rewritten.

The card has matching `status` frontmatter and one authoritative `json goal`
fence, using schema 1 from `tests/fixtures/goal-valid.md` and `check.py`:

- Required top-level fields: `schema_version: 1`, `id: G-NAME`, `status`
  (`active|blocked|complete`), `source`, `goal`, `rigor` (`normal|guarded|audited`),
  `risk`, `first_slice`, `demo`, `constraints`, `deferred`, and nonempty `outcomes`.
- **Schema 2/3**: `schema_version: 2` introduced (and 3 retains)
  the required `product_observation: {"required": true|false, "reason": "...",
  "basis": "..."}` field. New product goals default `required: true`.
  `required: false` is legal only for changes that cannot affect delivered
  behavior and needs a non-empty `reason` plus a concrete `basis` (how that
  was determined); the obligation cannot be dropped by deleting the audit
  sidecar. When an unfinished old goal is selected for the new workflow,
  prepare-plan publishes its engineering design as schema 3 (a definition
  change: evidence invalidation rules apply). Completed historical cards stay as-is and
  are never rewritten or claimed to have passed the observation gate.
- `constraints` and `deferred` are string arrays. `risk` contains `factors` and
  a nonempty `rationale`. Factors: `none` alone, or `external-boundary`,
  `cross-module`, `production-change` (Guarded minimum) plus
  `authentication`, `privacy`, `money`, `migration`, `irreversible`,
  `security`, `availability`, `data-loss`, `compliance`, `supply-chain`
  (Audited minimum). Classify by real impact and reversibility, not topic
  keywords: a small code change that rolls out to production with outage
  blast radius carries a production/availability risk, and a one-line change
  that can lose production data carries a data-loss risk. Retain the
  strongest risk still covered by the goal.
- Direct `source` is `{"type":"direct","raw_request":"<original request>"}`.
  Brief source is `{"type":"brief","path":"docs/brief.md","brief_hash":"<hash>",
  "coverage":[{"brief_id":"BS-01","disposition":"outcome","outcome_ids":["O-01"]}]}`.
  Cover **every** brief ID exactly once, with no unknown IDs, in every risk mode.
  Every source item with `kind: success` (BS) requires disposition `outcome` with
  valid `outcome_ids`. Other kinds retain the choices `outcome`, or `constraint`,
  `deferred`, `non-goal`, `rejected` with a nonempty `reason`. Do not silently drop scope.
- Each outcome has unique `id: O-NN`, `statement`, `status: pending`, and
  `verification`. There is **no outcome-count cap**. In every goal status, at least
  one outcome must set `user_entry: true` and exercise the real product entry/demo, not a fixture
  print, mock, selftest, or a label on an internal unit test.
- Every promised user-facing outcome must be covered by an actual public-interface
  journey from representative input to useful output/retrieval. A shared journey
  may cover several outcomes; one unrelated passing entry smoke is not coverage
  for disconnected features. Keep this mapping in existing outcome statements
  and verification descriptions; do not label internal checks as user entry.
- `verification` contains `command`, `expected`, `assertion_kind`
  (`content|state|schema|count|user-visible`), `empty_result_policy`, and
  `assertion`: either `{"type":"stdout-contains","literal":"<nonempty result>"}`
  or `{"type":"json-equals","expected":<finite JSON value>}`. Optional
  `timeout_seconds` is an integer 1..3600 (default 120). Commands must assert
  actual behavior; narrative expectations do not execute assertions.
- Optional `snapshot_include` is a list of project-relative globs that
  re-includes normally excluded delivery inputs (for example product files under
  `.opencode/`) in the workspace binding. Inclusive bindings win over standard
  exclusions; an included file that cannot be read fails validation instead of
  being treated as unchanged.

## Resolve The Card Before Product Edits

Before product edits, resolve `.opencode/mvp/<goal-slug>.md`: reuse the matching
active/blocked card, including for `/fix`; never create a second active fix goal.
If multiple goals or an unrelated active goal make routing ambiguous, ask rather
than overwrite. Create a card only for a genuinely new goal. Completed
cards/packages remain history; a repair gets a new card only when no matching
unfinished goal exists; ask which completed package is the repair base when the
request does not identify it uniquely, never pick by mtime. Establish and
successfully validate the current unfinished card before any product change.
Reading or validating an old complete card is not validation of a new repair
card; never reopen history to satisfy this gate. Normal cardless tasks (single,
bounded, no recovery need) remain allowed per `SKILL.md`.

## PUA Acceptance: `goal-validation`

For Guarded goals, before editing or resuming a product goal, load
`../../pua/SKILL.md` and execute the `goal-validation` card. Audited goals use the
contract-review gates (`contract-release`, `plan-confirmation`) instead. For
Normal goals, apply the same questions directly without loading the card. Ask
“BS 被悄悄缩水、改名或塞进 deferred 了吗？”
against every source coverage item and outcome. Verify that the executable
assertions, real `user_entry`, target environment and original external boundary
remain intact. Return the PUA acceptance result alongside `check.py goal`; it
does not authorize manual status or evidence changes.

When platform line endings are not part of the product contract, compare parsed
output in the acceptance runner and emit structured results for `json-equals`.
Preserve raw engine evidence and byte-exact contracts; do not change product output
merely to satisfy a platform-specific fixture literal.

## Brief Input

For brief input, require owner-confirmed `status: final`, matching hash, and a
successful `check.py brief` **before planning/building in any risk mode**. When
reading a brief source, the goal engine also rejects draft or unconfirmed sources;
this does not replace the controller's source/scope checks. Resume validates the
source again. Audited packages also preserve their exact brief snapshot.

## Engine Commands And Evidence

Run from the project root (installed engine path shown):

```text
python .opencode/workflow/scripts/check.py brief docs/brief.md
python .opencode/workflow/scripts/check.py goal .opencode/mvp/<goal>.md
python .opencode/workflow/scripts/check.py verify-goal .opencode/mvp/<goal>.md O-01 --evidence .opencode/mvp/evidence/<goal>-O-01-01.json
python .opencode/workflow/scripts/check.py verify-goal .opencode/mvp/<goal>.md O-02 --evidence .opencode/mvp/evidence/<goal>-O-02-01.json --reuse .opencode/mvp/evidence/<goal>-O-01-01.json
python .opencode/workflow/scripts/check.py product-audit-gate .opencode/mvp/<goal>.md --trace .opencode/mvp/trace.json
python .opencode/workflow/scripts/check.py finish-goal .opencode/mvp/<goal>.md
```

Schema-2/3 goals with `product_observation.required: true` additionally
require, before `finish-goal`: the product-audit sidecar
(`.opencode/mvp/<goal>.product-audit.json`, schema `product-audit/2`; legacy
`/1` stays readable), a candidate round under
`.opencode/mvp/observation/<G-ID>/<candidate>/` (`candidate.json`, archived
`discover.packet.json`/`compare.packet.json`, adopted run results
`discover/<run-id>/result.json` and `compare/<run-id>/result.json`, plus
`review/<run-id>/result.json`), and a passing
`check.py product-audit-gate <goal>.md --trace <trace.json>`. Phase packets
are generated with
`workflow_packets.py observer <goal> --phase discover|compare --out ...`
and archived into the candidate directory. See
`../../product-observer/references/observation-protocol.md`.

Strict-equivalence reuse: when an outcome's verification is exactly the same
command, cwd, timeout, expected text, assertion kind/policy/assertion and goal
definition as an existing passed evidence whose recorded workspace snapshot
still equals the current workspace, `--reuse <source>` writes a **new** evidence
record that references the source run (`reused_from` + `reused_at`) instead of
executing the same command again. It never forges a new run time; the reused
record carries the source's original timing and output. Any difference in
binding, a missing workspace binding, a failed source, or a changed workspace
refuses reuse and requires a real re-run. External mutable state, time-sensitive
checks and unknown side effects are never reuse candidates. Use
`scripts/evidence_registry.py find --dir <evidence-dir> --bindings <request.json>`
(read-only) to see which existing evidence is strictly equivalent; a listed
entry can still be refused by the engine at reuse time.

Validate `goal` before edits/resume and after definition changes. Run
`verify-goal` for every outcome with a fresh evidence path on each attempt; it
captures output, checks exit/timeout and the stdout assertion, and writes status
and evidence hashes. Failure becomes `blocked`; keep its evidence. Never manually
set `verified`/`complete` or fabricate evidence. Only `finish-goal` completes the
card after every outcome is engine-verified, including a real user-entry outcome.
Re-running `finish-goal` on a completed card is a no-op that only reports the
historical completion; use `check.py check-current` for the current workspace
state, and never describe the no-op as fresh verification.

## Invalidation Rules

Definition changes invalidate evidence bindings: reset all outcomes to pending,
remove their evidence references/blockers, and set JSON/frontmatter status active
before validation and reruns; retain old evidence files as history. Never reopen
a completed card this way. Before product changes, even if definitions/hashes
match, reset affected outcomes to pending and clear their runtime evidence
references and blockers, retaining evidence files. Keep JSON/frontmatter status
blocked if any unaffected outcome is still blocked; otherwise set both to active.
Then validate the unfinished card before editing the product. If impact is
uncertain, reset all outcomes. Definition changes still require the full
invalidation above, not only affected-outcome invalidation.

`verify-goal` records a workspace snapshot and `finish-goal` recomputes it:
changing any non-excluded file after verification invalidates the result until it
is re-verified; a verification command that itself changes the workspace fails.
The snapshot excludes VCS, `.opencode/**`, workflow artifacts, caches and
generated directories. The engine cannot tell which outcomes an arbitrary change
affects, so after product changes re-run every required outcome on the final
stable version. If a real delivery input lives in a default-excluded directory,
declare it explicitly; inclusive bindings win over exclusions. An unreadable
included file fails validation instead of being treated as unchanged.

Audited package paths and contract/PLAN/reconcile hashes are recovery pointers
and live in the goal's dispatch record (`active_slice.package`, see
`subagent-orchestration.md`), never inside the goal JSON:
the engine rewrites the card on every verification and binds evidence to the
definition hash, so a runtime pointer in the JSON would be lost or would
invalidate verified outcomes. They are not substitutes for goal verification.
The runtime-state policy sidecar (`.opencode/mvp/<slug>.runtime-state.json`,
schema `runtime-state-policy/1`; it excludes declared product-managed files
from the verification snapshot and is bound into every evidence record) and
the observer visibility settings (`.opencode/mvp/visibility.json`) are runtime
state as well: they live next to the card and are never written into goal JSON.

## Shell And Authorization

Verification commands execute with Python `shell=True` in the system shell
(`cmd.exe` on Windows, not the OpenCode PowerShell shell). Use that shell's
quoting or explicitly invoke the needed interpreter. Run engine commands from
the project root: goal commands derive that root from the card; `verify-step`
inherits the caller's working directory. Inspect commands before running them;
explicitly obtain authorization for destructive, paid, credential/privacy,
external-write or other risky effects. A JSON command is not authorization or a
sandbox, and approval may stop the delivery loop.

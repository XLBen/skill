# Observation Protocol

> When to read: before dispatching or executing a product-observation
> phase, before validating observation results, and before running
> `check.py product-audit-gate`. Authoritative scenario rules for
> `product-observer`; SKILL.md defines the seat's role and independence.

## Applicability

Observation applicability is declared in the goal card
(`goal.product_observation`), not by the existence of files:

- `schema_version: 2` goals carry `product_observation: {required: bool,
  reason?, basis?}`. New product-changing goals default `required: true`.
  `required: false` needs a non-empty `reason` and a concrete basis for why
  the change cannot affect delivered behavior; the obligation cannot be
  dropped by deleting the sidecar.
- Legacy `schema_version: 1` goals are historical; an unfinished v1 product
  goal is explicitly migrated to v2 before its next product change
  (definition change invalidates evidence per the existing rules).
- A missing backend, denied permission, or an unreadable target makes the
  phase `blocked` — never `not-applicable`.

## Two Phases

### Phase `discover` (independent exploration)

Packet (`workflow-observer-packet/2`) contains ONLY: `brief` (goal card public
fields: purpose, demo, first_slice, raw_request), candidate identity and entry
(`candidate.id/manifest_path/manifest_sha256/entry/environment/backend/
channels/test_data/runtime_state/delivered_roots`), `evidence_dir`, `budget`,
`output` (`product-observation/2` + full legal template + rules + repair
reference), appointed `model`, and the `preflight` cover record.

Forbidden in the packet: source diff, test results, implementer reasoning,
pre-written acceptance scenarios, known defect locations, historical maps
(reserved for compare), and the goal card itself (only `goal_binding.goal_card_sha256`
is carried).

Execution follows the upstream dogfood strategy (see `../upstream/dogfood.md`):
orient from real entry points, build the product map, exercise each material
surface with representative journeys, visit important modes/states, use
cross-feature paths that actually exist, document findings repro-first as
they occur, continue the breadth sweep after each finding.

### Phase `compare` (goal and history reconciliation)

Requires a saved, candidate-bound discover result (the packet's
`original.discover_result` carries its path and sha256). Packet ADDS
`original`: the original user goal, historical accepted product maps, prior
stable candidate behavior evidence (baselines), explicitly approved changes, and
the bound discover result reference.

The observer hunts specifically for what is NOT there: disappeared entries,
capabilities that only survive in some modes, original-goal results that
never became reachable, silently dropped experiences, map/claim mismatches.
Each finding in compare must carry `difference_classification`
(`intended-change | confirmed-defect | known-old-issue | under-investigation |
owner-decision`); discover forbids the field. Classification records what the
difference IS; `status` records its handling lifecycle — they are independent.
Authority order: approved goal / owner decision > candidate README or
user-facing docs > historical behavior. Old-version behavior is diagnostic
evidence, not an authority; README claims cannot downgrade a goal promise, and
an `intended-change` at `critical`/`high` severity stays invalid until an
`owner_decision_ref` is cited. The full table is in `finding-rules.md`.

No prior stable version exists → compare still runs against goal and
history; the report records `baseline: none` explicitly. **A missing
historical baseline is not a capability gap**: `baseline: none` is the
expected, non-blocking outcome and belongs in `notes`/the baseline record,
not in `capability_gaps` (an unresolved gap blocks the gate by design).

## Stop State (derived from `stop_reason`)

The model only writes `stop_reason`; the handling state is derived by code
(`result_stop_state()` in `scripts/observation_contract.py`), never filled by
the observer:

| `stop_reason` | `stop_state` | Rules |
|---|---|---|
| `coverage-completed` | `completed` | Material surfaces covered and `evidence_refs` non-empty; blocking findings MAY coexist (the gate, not the observer, decides release). |
| `budget-exhausted` | `incomplete` | `continuation` is mandatory; budgets below. |
| `blocked` / `no-backend` / `lease-lost` | `blocked` | Zero-contact rounds may have empty `surfaces`/`journeys`, but must explain via non-empty `notes` or a valid `capability_gaps` entry. |

No seat writes `accepted` directly. `TASK_RESULT.status: completed` means the
phase finished, never that the audit is accepted.

## Budgets And Continuation

Default hard budget per phase: at most 40 semantic actions per material
surface group, at most 2 observation cycles per action, wall-clock cap
(default 30 minutes; controller may tighten). Budget exhaustion with
material surfaces unvisited → phase result `incomplete` plus a
`continuation` cursor (visited surface ids, pending surfaces, checkpoint and
last stable state reference). Resume is only legal for `budget-exhausted`
with a valid `continuation`; same candidate + phase + model + environment →
`resume` from the cursor (`scripts/observation_resume.py resume_plan`), a
changed model/environment → new run, a changed candidate id → new round.
Reuse the controller's existing no-progress circuit breaker (three
same-signature failures without new evidence; signatures accumulate across
sessions) — never invent in-place retry loops.

## Format Repair (格式纠偏)

The observer's first answer must be **exactly one ```json fenced block**; the
reply itself is the only delivery channel — no result file is written by the
observer. The controller parses and validates it with
`validate_result_payload(payload, phase)` and, on failure, sends a
format-only repair prompt (`observation_results.repair_prompt`, at most 2
repairs after the first answer, mirrored in `references/format-repair.md`).
Repair never reopens the product and never adds facts: no product operation,
no new surfaces/journeys/findings/evidence, no meaning changes, no invented
controller fields. When the recorded facts cannot be turned into a legal
payload, the observer replies
`{"repair_outcome": "needs-observation", "reason": "<what is missing>"}`
instead of guessing; still invalid after the repair cap → the round stops as
`needs-observation`.

## Evidence Layout

```text
.opencode/mvp/observation/<goal-id>/<candidate-id>/
  candidate.json          # product-candidate/2 manifest
  preflight.json          # observation-preflight/1 (optional)
  discover/<run-id>/      # run-001, run-002, ... (monotonic per phase)
    packet.json
    attempts/<attempt-id>.attempt.json   # raw reply + parsed + received_at
    attempts/<attempt-id>.errors.json
    result.json           # product-observation/2, phase=discover (create-only)
  compare/<run-id>/       # same shape, phase=compare
  review/<run-id>/        # product-observation-review/2 (+ attempts/)
  evidence/               # screenshots, videos, traces, repro scripts
  gate/gate.json          # product-audit-gate/2 (engine-written)
```

`result.json` is create-only and never overwritten; rejected inputs leave an
attempt record but no result. The old flat layout (`discover.result.json`,
`compare.result.json` at the candidate root) is **legacy**: diagnostics only,
it can never pass the completion gate.

Pointer sidecar: `.opencode/mvp/<goal-slug>.product-audit.json`
(`product-audit/2`; legacy `/1` is still readable): `goal_id`,
`current_candidate`, `rounds[]` with `{candidate_id, discover_ref,
compare_ref, review_ref}` project-relative paths. Rounds append; evidence is
never overwritten.

## Exclusive UI Lease

During discover/compare the observer exclusively operates the delivered
artifact's UI session: controller pauses other UI runners (webapp-testing
sessions, computer-use control) per the existing pause rules; worker/
reviewer/test-author/step-executor seats never operate it. Independent
browser sessions (`agent-browser --session <isolated>`) are separate
resources and need no host-wide mutex; a shared desktop, emulator or app
data dir is one resource and is serialized. Activities classified
`ui-operate` / `backend-run` require the lease; `media-analysis`,
`evidence-review` and `read-only` do not (running ffmpeg on captured files
never takes the UI lease). The lease is recorded per
`scripts/observation_resume.py` as an `observation-lease/1` object
(`resource_id`, `owner_session`, `candidate_id`, `acquired_at`, `status`,
optional `note`); the controller validates it with `lease_problems`
(structural problems, unregistered resource, `status != active`, stale
`acquired_at` all fail closed). The lease is a workflow obligation, not a
claim that arbitrary external processes are blocked.

## Backend Independence

The protocol is entry-agnostic. Backends (selection, probes and argv
construction in `references/backend-routing.md` and
`scripts/observation_backend.py`):

- web journeys: `agent-browser` (isolated `--session`), with
  `playwright-cli` as the coding-only alternative;
- visual surfaces: direct multimodal read (screenshots handed to the
  observing model, preferred once a real read probe passes), `Midscene`
  for Canvas/vision grounding, `UI-TARS` as the desktop fallback;
- audio/video: FFmpeg/ffprobe only prepare and probe evidence
  (`scripts/observation_media.py`); the observing model still does the
  semantic judgement.

Sensory channels the product depends on (sound, motion, time) must actually
be captured and readable by the observing model. A backend that cannot
exercise a surface, a failed live probe or an unread channel is a recorded
`capability_gaps` entry — never an assumed pass and never `not-applicable`.
Frame sampling is not continuous coverage, and a video file is not assumed
to carry audio.

## Trust Boundary

Engine gates (`check.py product-audit-gate`) verify structure, identity,
freshness, provenance and unresolved blockers only. Whether the map misses
material surfaces and whether evidence actually supports each finding is
judged by the independent reviewer at review-verdict/goal-finish
(`findings_validity`, `coverage_adequacy`). Neither check replaces the
other. Packet field whitelists provide context isolation, not a sandbox
guarantee; the controller must not smuggle hints ("check feature X") into
discover packets, and dispatch bodies are archived for review.

Subject write-permission boundaries (edit deny plus bash command-pattern
denies) are expressed in agent configuration; the prompt-level scope and the
host permissions are two separate layers (两层) and neither substitutes for
the other; the controller must never grant the observer arbitrary shell write
access.

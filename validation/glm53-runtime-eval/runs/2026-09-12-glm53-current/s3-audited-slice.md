# Scenario 3: Audited slice — PASS (dispatch layer) with engine-chain deviation

Target: `targets/s3`, package `docs/audit-slices/g-audited/S-AUD-01/`
(profile light / interaction checkpoints → seat table requires step-executor).

## Observed sequence

| Point | Observation | Evidence |
|---|---|---|
| Package contract structure gate | `check.py contract` → OK after hash recompute | contract hash af659202…0821 |
| Engine compile gate refuses unreleased contract | `compile` rejected: "contract release proof is unavailable" — the gate works as designed (not driven further, see deviations) | engine error |
| Two-step ID bootstrap (a) | Round 1: seat returned BOOTSTRAP-CONFIRMED with `writes_this_round: none`; controller recorded real runtime ID from the task tool result | task `ses_f6ae72f7affeymR28EaOweGPdf` |
| Same-seat continuation (a) | Round 2 dispatched with the SAME task_id + subagent_type → same session continued (not a fresh seat), received `test_author_id` = its own runtime-recorded ID, then and only then wrote | same task id returned |
| Package-internal manifest (b) | Manifest written at `docs/audit-slices/g-audited/S-AUD-01/test-manifests/S-AUD-01.md`; only `tests/**` + manifest written; contract/PLAN/ledger untouched by the seat | files on disk; hash verified |
| Classified pre-change evidence | `python tests\test_sorter.py` exit 1 — targeted behavior-red (feature absent), not parse/skip failure; per-scenario results in manifest | handoff pre_change_output_hash 04685363… |
| STEP_HANDBACK before formal V (c) | Fresh executor seat returned pending_v; did NOT run the formal V; protected hash verified pre+post; author IDs differ across seats (test author ses_f6ae72f7… vs implementer ses_f6ae4a133…) | task `ses_f6ae4a133ffe7qWSYTPaHeWcOt` |
| Controller single V execution (d) | Controller ran `python sorter.py 3 1 2` exactly once → `1 2 3`, exit 0; executor's diagnostic run was separate and labeled non-engine evidence | shell output |
| Durable record | dispatch.json schema 2 with bootstrap skip_reason on T-01 round 1 | `.opencode/mvp/g-audited.dispatch.json` |

## Deviations (disclosed)

- Engine `verify-step` event binding and the release→confirm-plan chain were
  NOT driven by hand (init/final-audit/release/confirm event chain not
  executed in this run); compile was correctly refused for an unreleased
  contract. Engine-side behavior of that chain is covered by
  `check.py --selftest` (PASS), not by this scenario.
- Seats used runtime `general` agents (project agents not exposed as
  subagent types here); formats, write boundaries, and protected-path
  discipline followed the protocol and were verified on disk.
- Seat table compliance observed: light+checkpoints dispatched a fresh
  executor seat rather than staying in-session (WP1 authority table).

Result: **PASS** for all four registered observation points; engine verify-step
event binding recorded **NOT RUN (engine chain not hand-driven)**.

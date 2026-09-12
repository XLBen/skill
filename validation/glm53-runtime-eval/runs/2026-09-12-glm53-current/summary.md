# Run Summary — 2026-09-12, GLM-5.3, current suite @ 3106bef

8/8 scenarios executed with an outcome (7 PASS, 1 PASS with a NOT RUN GUI
sub-variant). One engine sub-chain (release→confirm→verify-step event binding)
was not hand-driven anywhere and is covered by `check.py --selftest` (PASS).

| # | Scenario | Result | Notes |
|---|---|---|---|
| 1 | Normal end-to-end | PASS | full loop: worker dispatch → controller engine verify → fresh reviewer (new JSON schema incl. hash recomputation) → finish-goal once |
| 2 | Guarded, no reviewer seat | PASS | real failed dispatch to missing agent type; tiering: record + disclose + finish (Audited would block) |
| 3 | Audited slice | PASS (dispatch layer) | two-step ID bootstrap with real same-seat continuation; package manifest; STEP_HANDBACK before formal V; controller ran V once; engine verify-step event binding NOT RUN (disclosed) |
| 4 | Circuit break | PASS | 3 real same-signature failures, no 4th execution (verify-goal deliberately not run), no fresh-seat retry, escalation with options; bonus: worker refused to fabricate failures on an accidentally satisfiable trap |
| 5 | Reviewer `owner` + resume | PASS | owner-tradeoff verdict preserved; fresh seat derived correct next actions from durable files only; found + fixed a real controller persistence lapse (missing dispatch archive) |
| 6 | FIX for completed package | PASS | branch-3 routing, sibling FIX package, base bytes immutable |
| 7 | Brief versioning | PASS | v2 draft created; consumed brief bytes and goal binding unchanged; engine rejected malformed drafts |
| 8 | Controller-action round-trip | PASS (engine-V) / NOT RUN (GUI) | engine-V observed in s3; desktop backend absent |

## Cross-cutting findings

1. **Runtime ID semantics confirmed**: task IDs are only reported in the
   completed dispatch result, and same-seat continuation (task_id + agent
   type) works — the two-step bootstrap in test-author/SKILL.md is executable
   as written.
2. **Reviewer seat behavior**: fresh read-only seats returned the new output
   schema unprompted-complete (classification/checked_scope/resolved), never
   graded owner choices, and correctly excluded post-gate evidence.
3. **Weakest link observed**: controller-side persistence discipline — one
   dispatch archive was initially forgotten (s5); the protocol's
   missing-result_ref rule plus a fresh-seat resume check caught it. The
   schema works, but controllers must actually write the archive in the same
   operation as the dispatch record sync.
4. **Engine gates bite correctly**: unreleased contract refused compile;
   malformed brief drafts rejected; goal/brief/verify-goal/finish-goal all
   behaved as documented.

Verification during this run: `check.py --selftest` PASS; full unittest suite
60/60 OK; `git diff --check` clean.

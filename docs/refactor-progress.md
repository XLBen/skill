# Refactor Progress

Baseline: commit 71d358a, clean worktree.
Baseline checks: `check.py --selftest` PASS; 175 unit tests OK.
Baseline workflow text: 325602 bytes (skills + agents + commands, md+json).

| Package | Status | Evidence |
|---|---|---|
| P0 baseline | done | see refactor-plan.md |
| P1 routing | done | stage-routing v2 + `scripts/workflow_protocol.py`; Normal card/PUA/reviewer contradictions fixed; runtime gate uses slice rigor and derives PUA from routing; tests/test_workflow_protocol.py added; 200 tests OK |
| P2 returns | done | TASK_RESULT/task-result-1 envelope, controller-action dedup + dispatch `actions`, bootstrap phase, legacy mapping; runtime gate validates actions |
| P3 context | done | wrappers 44-60 -> 10-14 lines; mvp-delivery 315 -> 115 lines / 34250 -> 15890 bytes; goal-definition/delivery-execution/delivery-finish/delivery-recovery references; PUA cards split into `pua/references/stage-checks/` (233 -> 34-line index + one card per load); construction seat-dispatch extracted; researcher no longer loads mvp-delivery. Repo-wide text grew due to new reference files (honest per-invocation metric, not total) |
| P4 hashes | done | v0.2 E `bundle_hash` optional (old versions unchanged); workspace snapshot fails on unreadable files; `snapshot_include` explicit includes; `check.py check-current` read-only freshness; skill freshness diagnostic + `--strict-freshness`; installed-file integrity check |
| P5 concurrency | done | `scripts/worktree_tasks.py` (admission/create/collect/scope/apply/cleanup/status), orchestration protocol, worker agent isolation rule, 8 real-git tests |
| P6 install | done | install copies workflow_protocol/worktree_tasks/stage-routing; test-author permission globs extended to common test layouts; README updated (concurrency, TASK_RESULT, strict-freshness, check-current) |
| P7 regression | done | selftest PASS; 233 tests OK; install smoke in temp target (installed selftest PASS, doctor --strict exit 0); CLI worktree e2e (2 tasks integrated + cleaned); check-current fresh/stale; trace export smoke |
| P8 review | done | independent mvp-reviewer seat returned 12 issues (2 hard); all material issues fixed with regression tests; see refactor-report.md independent review follow-up |

Known baseline issues: none (all checks green at start).
Owner modifications present at start: none (worktree clean).

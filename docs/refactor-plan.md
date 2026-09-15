# Workflow Refactor Plan (thin controller, routed seats, honest hashes)

Executed plan for shrinking the skill suite without weakening real evidence
gates. Scope: current top-level skills, `.opencode/agents`, `.opencode/commands`,
`scripts/`, `tests/`. Excludes `validation/` frozen snapshots.

## Decisions

1. Keep the five public commands and the five subagent seats.
2. Keep Audited rigor, but load it on demand.
3. Normal short tasks may run without a goal card, and without persistent
   `/resume` claims.
4. Normal/Guarded substantive implementation defaults to the worker seat;
   mechanical batch edits stay with the controller.
5. Concurrent writers only in isolated worktrees; shared workspace keeps one
   writer.
6. Remove duplicate/low-value hashes; keep content bindings that detect stale
   evidence.
7. Do not modify `validation/` or completed/frozen history.
8. Success is measured by reduced mandatory reading, not by file count.

## Work packages

- P0 baseline: git clean, selftest PASS, 175 tests OK.
  - mvp-delivery/SKILL.md 315 lines / 34250 B
  - construction/SKILL.md 284 / 19157
  - contract-review/SKILL.md 278 / 18215
  - workflow text total (skills + agents + commands, md+json): 325602 B
- P1 routing: single authority in `stage-routing.json`, machine-readable
  conditions, `scripts/workflow_protocol.py`, remove contradictions.
- P2 returns: `task-result/1` shell, controller action dedup, bootstrap phase,
  legacy adaptation.
- P3 context: thin wrappers, thin controller, reviewer/PUA on-demand loading,
  minimal recovery read set.
- P4 hashes: drop duplicate frontmatter/self digests, keep install protection
  and definition/evidence/workspace bindings, honest workspace rule.
- P5 concurrency: Git worktree isolation for independent Normal/Guarded
  packages, one integrator.
- P6 install/permissions/compat sync.
- P7 full regression + three end-to-end scenarios.
- P8 independent review + delivery report.

## Regression scenarios

| ID | Scenario | Expectation |
|---|---|---|
| R01 | Normal short task | May complete without goal card |
| R02 | Normal without review trigger | No forced reviewer/PUA |
| R03 | Normal substantive work | Defaults to worker; mechanical batch controller |
| R04 | Audited direct | Controller executes; no step-executor |
| R05 | Audited full | step-executor required |
| R06 | First converge review | Does not require its own not-yet-produced output |
| R07 | Required UI scenario without tools | blocked, never not-applicable |
| R08 | Product changed after passing test | Stale evidence rejected |
| R09 | Installed target modified by user | Not overwritten by default |
| R10 | Incomplete subagent return | Fix return fields only; no rework replay |
| R11 | Subagent requested controller action, then resumed | No duplicate execution |
| R12 | No isolation available | Serial execution, goal still progresses |

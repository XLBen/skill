# Scenario 8: Controller-action round-trip — PASS (engine-V variant) / NOT RUN (GUI variant)

## Engine-V variant — PASS (observed inside scenario 3)

The full round-trip ran with real seats in scenario 3:

1. step-executor returned `STEP_HANDBACK` with `pending_v` — it did NOT run
   the formal V and did not wait inside the task (no deadlock on the
   synchronous task tool).
2. Controller executed the exact V (`python sorter.py 3 1 2`) exactly once,
   after recording the hand-back; the executor's separate diagnostic run was
   labeled non-engine evidence.
3. The test-author GUI-style pattern (controller-run pre-change evidence) was
   exercised in its non-GUI form: the pre-change command was executed by the
   test-author seat itself here, so the CONTROLLER_ACTION file round-trip for
   pre-change evidence was not separately instantiated (disclosed).

Evidence: `s3-audited-slice.md`, dispatch archive in `targets/s3`.

## GUI variant — NOT RUN (backend absent)

No desktop MCP backend is configured in this session and no GUI authorization
was given. Per the eval README, recorded as `NOT RUN (backend absent)`; no
simulated GUI results are claimed. The protocol paths that would be exercised
(CONTROLLER_ACTION `gui-scenario`, single operator, no replay of stale clicks
on resume) remain unverified against a real backend — the same standing
limitation disclosed in `computer-use/README.md`.

Result: **PASS** (engine-V variant) + **NOT RUN (backend absent)** (GUI variant)

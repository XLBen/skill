# Controlled Skill Validation

This workspace evaluates the installed workflow skills, not just the product.

- Planning, review, PLAN compilation, SI/CR decisions, and retro use
  `zhipuai-coding-plan/glm-5.3`.
- Test writing, implementation, verification, resume, and finish use
  `zhipuai-coding-plan/glm-5.3-flash`. Stop if the active stage has the wrong
  model.
- Append every material action to `docs/benchmark-run-log.md`: timestamp,
  OpenCode session ID, active model, command/message, skill/role, files, exact
  command result or evidence path, state, normalized failure signature, and
  next action. Never reconstruct a success-only log after the fact.
- Keep bounded raw outputs under `docs/evidence/benchmark/`; preserve all failed
  attempts and owner decisions.
- `TASK.md`, `ACCEPTANCE.md`, `START.md`, `AGENTS.md`, `boundary/`,
  `evaluation/`, `opencode.json`, and `.opencode/` are immutable benchmark
  inputs.
- Treat the local HTTP process as a real external boundary. Read
  `boundary/API.md` and probe the running API, but do not read server/control
  source. Do not read or run the owner-only `evaluation/` oracle.
- Never inspect `boundary/transient_gate.py`, invoke its `--reset` option, edit
  its state, or predict a later result. Only construction may run its normal
  command when V-DRILL becomes active; owner alone may query `--count`.
- Use a new OpenCode session for each test-author handoff and another new
  session for implementation. Record real IDs and sanitized exports. Loading
  two skills in one session is not author separation.
- Do not implement planned SI or a future schema before its owner-confirmed
  stage. Planned expansion is SI; observed schema drift is a blocking CR.
- Product implementation begins only after meaningful red evidence. Frozen
  tests are read-only to implementation authors.
- After a third consecutive V-DRILL failure with the same signature, ordinary
  execution must stop. A later attempt is legal only after a traceable owner
  recovery choice and must be labelled recovery, not ordinary retry four.
- Do not self-grade. `/retro` fills `docs/benchmark-result.md` only from
  artifacts, session exports, owner decisions, and owner-supplied oracle output.

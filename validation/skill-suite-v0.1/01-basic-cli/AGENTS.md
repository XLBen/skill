# Controlled Skill Validation

This workspace evaluates the installed workflow skills, not just the product.

- Planning, review, PLAN compilation, SI/CR decisions, and retro use
  `zhipuai-coding-plan/glm-5.3`.
- Test writing, implementation, verification, resume, and finish use
  `zhipuai-coding-plan/glm-5.3-flash`. Stop if the active stage has the wrong
  model.
- Append every material action to `docs/benchmark-run-log.md`: timestamp,
  OpenCode session ID, active model, command/message, skill/role, files, exact
  command result or evidence path, state, and next action. Never reconstruct a
  success-only log after the fact.
- Keep raw bounded outputs under `docs/evidence/benchmark/`; preserve failed as
  well as passed results.
- `TASK.md`, `ACCEPTANCE.md`, `START.md`, `AGENTS.md`, `fixtures/`,
  `evaluation/`, `opencode.json`, and `.opencode/` are immutable benchmark
  inputs.
- Do not read or run `evaluation/`. It is an owner-only oracle after Finish.
- Use a new OpenCode session for `test-author` and another new session for the
  implementation author. Record the real IDs and sanitized exports. Loading two
  skills in one session is not author separation.
- Product implementation may begin only after a meaningful red result and
  frozen test manifest. The implementation author may not edit protected tests.
- Do not claim acceptance from exit status alone. Assert content/state and the
  explicit empty-result policy.
- Do not self-grade. `/retro` may fill `docs/benchmark-result.md` only from
  traceable artifacts, session exports, and owner-supplied oracle output.

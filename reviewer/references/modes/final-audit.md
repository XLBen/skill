# Mode: Final Audit

> Load on demand when the dispatch mode is `final-audit`. The shared output
> schema and materiality rules live in
> `../../../contract-review/references/reviewer-protocol.md`.

Final audit is the clean-context release check for an Audited contract. It runs
on a fixed snapshot, after the question/revision loop has converged.

- Input is the fixed contract + evidence manifest only. Do not read debate
  rhetoric, prior reviewer prose or the revision trail; only the frozen
  artifact and its evidence.
- Return the structural result (fields/hashes/coverage you could verify) plus
  any surviving semantic issues. Structural questions the engine already
  settled are not relitigated; judge what the engine cannot.
- A previously raised issue that the frozen revision settles is reported as
  resolved with its original fingerprint; it is not silently dropped.
- Confirm the Phase 0 record exists and the declared slice budget is compared
  with actual counts before release.
- The controller records the passed `final-audit` event and runs
  `check.py release` afterwards; this mode itself never writes events.

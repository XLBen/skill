# Delivery Finish Details

> When to read: before `finish-goal`, when building the final
> `ACCEPTANCE_HANDOFF`, when the runtime/UI gate is enabled, or when preparing
> the final report. Seat: controller (reviewer reused for independent scope
> checks). Inputs: original request/brief, whole goal, final evidence, README,
> isolated replay results.

## Final Integrated Verification

After the last product/dependency/config change, run the key user-path
integration check, affected regressions and applicable lint/build on the same
delivery version. Every promised user-visible result needs a real entry path;
when impact is uncertain re-run all goal outcomes on the final stable version
instead of stitching evidence from different versions. Use fresh evidence paths
for `verify-goal`. Completed cards and historical packages are not reopened;
follow the existing repair rules. Record the tested version, uncommitted
changes/artifact identity and environment in the existing delivery record; do
not auto-commit and do not write sensitive diffs into logs. This is the
controller's check; the engine cannot guess which outcomes an arbitrary change
affects, so the stable-version rerun above is mandatory.

Inspect the actual diff: no weakened tests to make it green, no hardcoded
samples, swallowed errors or unconnected paths. Create README/quickstart when
the new product lacks one, otherwise update it with runnable setup, declared
dependencies, working directory, install/init/start or invocation steps,
configuration names, a concrete sample and the expected result/output location.
Replay only the declared artifacts and instructions in a safe authorized
isolated environment; borrowed global dependencies are not a clean install.
Avoid relying on implicit session preparation and do not delete user data to
simulate a clean environment. When replay is impossible, state the concrete
gap, tested vs target environment difference, and never describe a local run as
deployed or missing credentials/services as passed.

## Whole-Goal Acceptance

Before `finish-goal`, build the `ACCEPTANCE_HANDOFF` and compare the original
request or brief (every BS), the entire goal, deferred work and real user-entry
journeys against the final deliverable. A clean slice reconcile/converge audit
is not whole-goal acceptance and cannot exempt future slices. Reuse the
`reviewer` capability for this scope check when independent review applies,
passing the original source, whole card and final evidence; no new public
command, role or audit-event schema. Run `finish-goal` only after this check,
all applicable Audited gates and actual owner acceptance.

When the project enables the runtime policy sidecar
(`.opencode/mvp/runtime-policy.json`, schema `runtime-policy/1`), first export
the native trace
(`python .opencode/workflow/scripts/runtime_trace.py export <project> --out
.opencode/mvp/trace.json`) and pass
`check.py runtime-gate <goal>.md --trace .opencode/mvp/trace.json`; missing
dispatch provenance, non-official reviewer seats, failed skill loads or stale
gate evidence block `finish-goal`.

A `ui-acceptance/1` sidecar (or a policy `ui-acceptance` requirement)
additionally requires a passing
`check.py ui-gate <goal>.md --trace .opencode/mvp/trace.json` — required UI
scenarios unresolved, missing `computer-use` execution evidence, native call
references absent from the trace, or a changed artifact identity all block
completion. If the engine is unavailable, report a blocker in every rigor mode.
If an independent seat is unavailable, apply the tiering in `SKILL.md`: an
Audited independence gate blocks; a Normal/Guarded reviewer seat records
capability-unavailable, is replaced by the disclosed controller check, and does
not by itself block finish. Never simulate success.

Hashes detect stale bindings, not malicious rewriting or product correctness.
Session/author IDs are claims with no cryptographic identity verification; real
session/subagent provenance must be inspected. Coverage IDs and
`user_entry: true` are structural markers, not automatic proof of semantic
coverage or real boundaries. Audited approval does not remove these controller
duties. Selftest checks the engine, not product usability.

## PUA Acceptance: `goal-finish`

For Audited goals, and whenever evidence is missing or suspect, load
`../pua/SKILL.md` and execute the `goal-finish` card: compare the original
request or every brief BS, the whole goal, deferred work, final integrated
path, isolated setup/use replay and remaining limitations. For Normal/Guarded
goals the same comparison is the controller's direct duty; PUA cards are not
required ceremony. “证据呢？” means locate the actual output; it never means add
a second unbounded ceremony. Missing implementation, missing verification,
owner decisions and external blockers remain distinct.

## Final Report

最终只报告：

- 已可用的结果和用户如何运行/查看；
- 交付路径和已复跑的 setup/use 步骤（可链接持久 quickstart）、具体样例及
  预期输出；
- 关键验证命令、所测版本/环境及结果，区分自动验证、人工验收和未验证部分；
- 为推进而作出的重要可逆决定；
- 缺实现、缺验证、真实阻塞及已验证范围；仅在证据支持时说没有未完成项，
  不能用“无局限”掩盖未测环境或未实现边界。

若阻塞，明确哪部分仍不可用、原因和用户需要采取的最小下一步；不能将其包装
为完成。不要用流程工件数量证明成功；以用户目标的可观察结果证明成功。

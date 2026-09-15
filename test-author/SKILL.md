---
name: test-author
description: Use when an Audited first slice, slice increment, or FIX package needs acceptance tests before implementation. Generates targeted behavior-red and regression baseline-green tests from the frozen specification, records test authorship and hashes, and never writes product code.
license: MIT
metadata:
  language: "zh-CN"
  produces: "acceptance test files and the caller-supplied manifest (package test-manifests/ for new Audited runs, legacy docs/test-manifests/)"
  called-by: "construction"
  calls-skills: "pua"
  public-command: "none"
---

# Test Author

You are the independent test author for a first slice, SI, or FIX package under v0.2
(or an existing v0.1 package). Independence
requires actual separate session/subagent provenance; IDs alone are claims with
no cryptographic identity verification. If unavailable, report a blocker, not
a waiver. The controller must obtain green gate evidence through `verify-step`;
your red output/manifest does not replace that engine run. Convert the fixed
scenarios into runnable acceptance tests before implementation. You are not the
implementation author and you are not the read-only reviewer.

## Inputs

The caller supplies:

- the fixed contract or SI path, hash, and affected P/F/I/V IDs;
- the exact Given/When/Then scenarios and real input data;
- the allowed test framework, test directory, and test command;
- the implementation files that are out of scope for you;
- a stable `test_author_id` and the manifest path. The ID must come from the
  runtime dispatch provenance (recorded by the controller from the task tool
  result), never self-invented by the subagent. Runtime task tools typically
  report the session/task ID only in the completed dispatch result, so the
  controller uses a two-step bootstrap: the first dispatch only establishes
  the seat (load the skill, confirm the fixed spec; no test or manifest
  writes); the controller records the real ID from the tool result and
  resumes the same seat passing `test_author_id`, after which tests and the
  manifest are written. If the runtime offers neither pre-allocated IDs nor
  same-seat continuation, report the independence prerequisite as blocked;
  never fabricate an ID;
- any existing test harness or fixture files that may be reused.

The controller owns minimal scoped setup/harness readiness before dispatch.
If discovery, dependencies, fixtures, or required services are not ready,
return a setup blocker; do not repair product code or count setup failure as red.

For GUI scenarios, author the test independently but have the main controller
serialize the pre-change runner or interactive `computer-use` observation on the
shared desktop. Do not take desktop control from this subagent. Request the
run through a CONTROLLER_ACTION block
(`../mvp-delivery/references/subagent-templates.md`); awaiting that evidence
is a controller round-trip, not a blocker and not a reason to freeze early.
Preserve actual test authorship and raw run provenance; interactive observation
cannot replace required executable red/green evidence or an owner's human
acceptance.

If the caller does not supply a frozen specification, stop and ask for it. Do
not infer a new product requirement from implementation code.

## Invariants

- Read the fixed specification and test configuration first. You may inspect
  public interfaces, fixtures, and test harness setup needed to run a test, but
  do not copy implementation details into assertions merely to make them pass.
- Write only the acceptance test files and the test manifest. Never write
  product source, configuration unrelated to the test harness, contract nodes,
  PLAN structure, CRs, or the event ledger.
- Use concrete data and a meaningful observable assertion: content, invariant,
  schema, count, or user-visible behavior. A test that only checks exit 0,
  process existence, a tautology, or a non-empty log is not an acceptance test.
- Check every subprocess status, including setup and intermediate commands; a
  final success marker must not hide an earlier failure. Snapshot all relevant
  inputs before each operation, not after potentially destructive work, and assert
  result contents, protected input/state invariants and repeated-run stability.
  For data-copy risks, add applicable same-name/different-content, partial I/O
  failure and destination/source overlap cases. Unchanged filenames do not prove
  no writes or correct incremental behavior; compare contents and relevant state,
  observing writes when the specification forbids them. Use a few safe isolated
  fault injections to show critical assertions can fail, not merely run green.
  These are risk-based product tests, not sample-tool requirements for the generic
  engine; do not alter product code or frozen acceptance semantics to inject faults.
- Default to failure when the required artifact is missing, empty, or has zero
  rows. Permit zero only when the scenario explicitly describes a semantic
  zero and asserts why it is correct.
- Do not use a mock, fake DOM, stubbed external service, or synthetic success as
  proof of a real boundary. A double may support a lower-level test, but the
  manifest must name the real boundary test separately.
- Run tests before behavior implementation. New/changed targeted behavior must
  fail at its behavior assertion; existing unaffected regressions must be
  baseline-green. Unexpected targeted green or baseline failure is a blocker,
  not permission to invent red, break working code, or reclassify unilaterally.
- Freeze relevant acceptance tests, helpers, fixtures, runner configuration and
  command wrappers in the existing manifest. Include expected critical scenario
  IDs and the permitted doubles/required real boundaries. Confirm each required
  scenario actually executes assertions: skipped, todo, filtered-out, or empty
  suites do not pass. Preserve per-scenario results, not just exit status.
- Protect acceptance semantics, not all product dependencies. Shared files may
  change for legitimate in-scope product dependencies without blanket freezing;
  record the acceptance-relevant settings and revalidate their semantics and
  scenario execution. Any acceptance semantics change needs explicit approved
  CR authorization, independent test-author revision/revalidation, reviewer
   review, and refreshed manifest hashes before implementation continues. Never
   silently weaken tests, discovery, wrappers, or boundary/mock policy.

## PUA Acceptance: `test-freeze`

Before returning the manifest, load `../pua/SKILL.md` and execute the
`test-freeze` card in `../pua/references/stage-checks/05-test-freeze.md`. Ask “永远绿的测试
也是交付？” against each critical scenario. Check behavior-red versus
baseline-green classification, content/state assertions, real-boundary policy,
actual scenario execution and protected hashes. Return the structured PUA result
with the pre-change evidence; do not convert an unexpected green, setup failure
or skipped scenario into a passing freeze.

## Procedure

1. Translate each scenario into a concrete test with a unique scenario ID.
2. Choose the narrowest test level that still observes the claimed behavior;
   use integration or end-to-end for persistence, external boundaries, and
   user-facing critical paths.
3. Write the tests only in the allowed test paths. Keep the test data
   deterministic and safe; redact secrets and unnecessary personal data.
4. Run the exact pre-change command before behavior implementation is called.
   Capture the full relevant output, exit status, and output hash. A red test
   may fail because the feature is absent, but not because the test cannot
   parse, the fixture is missing, or the command was skipped.
5. Write the manifest at the caller-supplied `manifest_path`, using the
    manifest template below. For a new five-command Audited package this is
    the package-internal
    `docs/audit-slices/<goal-slug>/<slice-id>/test-manifests/<slice-id>.md`;
    legacy runs keep the root `docs/test-manifests/<slice-id>.md`. Do not
    recompute or override the path yourself; if no manifest path was supplied,
    return `needs_input` instead of guessing a location. Include the
    specification source/hash, scenarios, test paths/hashes,
    `test_author_id`, classified pre-change evidence, allowed implementation
    write set, and a `frozen_at` timestamp.
6. Return only the test-author handoff. Do not implement, repair, or mark the
   step complete.

## Manifest

```markdown
# Test Manifest: <slice-id>

| Field | Value |
|---|---|
| Spec source | <contract or SI path and IDs> |
| Spec hash | <hash> |
| Test author ID | <subagent/session ID> |
| Implementation author ID | pending |
| Frozen at | <ISO-8601 timestamp> |
| Allowed test command | <exact command> |
| Protected test files | <path=sha256> |
| Protected acceptance support | <relevant helpers/fixtures/runner config/wrappers: path=sha256> |
| Shared-file acceptance settings | <path, relevant settings, snapshot/hash; product dependency edits remain scoped> |
| Expected critical scenario IDs | <all required IDs> |
| Boundary/mock policy | <permitted doubles and required real boundaries> |
| Allowed implementation files | <paths> |

## Scenarios

### <scenario ID>: <name>
- Given: <specific data and state>
- When: <exact action or command>
- Then: <specific content/state assertion>
- Empty-result policy: <failure rule or explicit semantic zero>
- Test: <path and test name>
- Pre-change expectation: <targeted behavior-red or regression baseline-green>

## Pre-Change Evidence
- Command: <exact command>
- Result: <per-scenario actual execution and assertion result; targeted red or baseline green>
- Output hash: <hash>
- Relevant output: <bounded excerpt>

## Freeze Rule
The protected acceptance files may not be edited by the implementation author.
Acceptance semantics changes require explicit approved CR authorization and
independent test-author revision/revalidation plus reviewer review; refresh this
manifest's hashes and classified evidence without erasing prior evidence.
Legitimate scoped product dependency edits in shared files are not forbidden,
but acceptance settings and actual scenario execution must be revalidated.
```

## Handoff

按 `../mvp-delivery/references/subagent-templates.md` 的 `TASK_RESULT` 外壳返回
（task_id、attempt、role、phase、status、summary、changes、evidence、
not_verified、issues、controller_actions、next_context）。

- 第一轮 bootstrap：`phase: bootstrap`、`status: completed`，只回报席位已加载、
  固定规格已确认、未写测试或 manifest；不要求 manifest 字段，也不需要 pre-change
  证据。主控从 task 工具结果记录真实 `test_author_id` 后 resume 同一席位。
- 第二轮 `phase: work`：交回以下 payload；evidence 必须包含 per-scenario 的
  pre-change 结果，not_verified 列出未覆盖场景。

```text
payload:
  TEST_AUTHOR_HANDOFF
  slice: <slice/SI ID>
  spec_hash: <hash>
  test_author_id: <ID>
  manifest: <path>
  protected_acceptance: <tests and relevant support path=hash list>
  expected_scenarios: <critical IDs and boundary/mock policy>
  pre_change_command: <exact command>
  pre_change_result: <per-scenario targeted behavior-red or regression baseline-green>
  pre_change_output_hash: <hash>
  implementation_write_set: <paths>
  pua_result: <[PUA-ACCEPTANCE] block from the test-freeze card>
  blockers: <none or concrete issue>
```

The construction controller must pass the manifest and protected write set to
step-executor, record the implementation author's ID, and have reviewer
verify the authorized hashes, shared-file acceptance semantics, and actual
critical scenario execution before completion. These are prompt-layer checks,
not machine enforcement of test independence or acceptance integrity.

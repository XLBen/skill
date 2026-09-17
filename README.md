# MVP delivery skills

**English** · [简体中文](README.zh-CN.md)

This OpenCode workflow turns ideas into real, running results — instead of an
agent that merely asks great questions and leaves behind a pile of planning
artifacts.

## The five commands

The public surface keeps four action commands and one recovery command:

| Command | When to use | Result |
|---|---|---|
| `/grill <idea>` | The idea is still vague and the goal needs clarifying | A confirmed `docs/brief.md` |
| `/plan <goal-or-brief>` | You want to see the implementation path before any code | A lightweight goal card; a strict PLAN is generated internally at high risk |
| `/build [goal]` | Start delivery; a clear small task can carry the goal directly | A runnable, really-verified result that keeps growing |
| `/fix <problem>` | An existing feature errors, misbehaves, or contract and reality conflict | A root-cause repair with regression verification |
| `/resume` | The previous run was interrupted | Continue from persistent state to the original goal |

Review, test authorship, CR, final audit and retro still exist — as internal
capabilities. Users are never asked to memorize or manually relay more
commands.

## Recommended paths

Requirements are clear — build directly:

```text
/build <goal>
```

See a plan first:

```text
/plan <goal>
       ↓
/build
```

The idea is vague:

```text
/grill <idea>
       ↓
/plan docs/brief.md
       ↓
/build
```

A bug shows up:

```text
/fix <problem or error>
```

After an interrupted session, all you need is:

```text
/resume
```

## Why it never stops at MVP

MVP here is a delivery order, not a permanent scope cut. `/build` implements
the thinnest real end-to-end slice first, re-checks it against the original
outcome list after verification, then automatically moves to the next slice
until the goal is complete or a blocker genuinely requires a user decision.

Every tracked task stores its goal and verification state in a schema-1
`json goal` block at `.opencode/mvp/<goal>.md`; the number of outcomes is
uncapped. A single, bounded Normal task that needs no cross-session recovery
may run cardless (no goal card, no dispatch record, no verify-goal/finish-goal
gate); its evidence lives in that session and the delivery report, and it must
not claim persistent `/resume` support. Runtime state (current slice rigor,
dispatch records, failure counters, acceptance verdicts) lives in the sibling
`<goal>.dispatch.json` (schema 2); the goal JSON stays a pure definition.
Brief inputs must be final, owner-confirmed and pass the `brief` validator in
every risk tier, and every brief ID must have coverage. Every
`kind: success` (BS) may only map to `outcome` — constraint, deferred,
non-goal or rejected can never hide a required success; other kinds keep
their existing dispositions. `goal` validates the card, `verify-goal`
executes each verification and stores engine evidence, and only `finish-goal`
may complete; handwritten verified/complete is forbidden. A goal in any state
has at least one `user_entry: true` outcome, and the real product entry
should be demoed. Interface journeys are declared on the goal card via the
optional `goal.ui` (`{"required": true, "outcome_ids": [...]}`) as the
persistent source of UI acceptance duty; no sidecar is needed when no
interface is claimed. IDs and boolean flags provide structure only — they do
not automatically prove semantic coverage or real boundaries.

`/fix` reuses the matching active/blocked card and never creates a second
active fix goal; completed packages stay immutable, and with no matching
unfinished card it creates a new fix card first — reading an old complete
card is not a substitute for the current card's `goal` validation. Before
touching the product, affected outcomes go back to pending with runtime
evidence references/blockers cleared (evidence files are kept); definition
changes still invalidate everything and never reopen a complete card. When
the repair baseline is unclear, ask first. After invalidation, sync the
JSON/frontmatter status: stay blocked while blocked outcomes remain,
otherwise go active, and re-validate before modifying the product again.
`/resume` continues grill revision/frontier when there is no unfinished goal
but a draft brief exists — it does not start construction. grill saves and
validates the draft before every next round (including the first) or pause,
records the interview mode, defaults to checkpoints with questions grouped by
dimension — five to ten per round (cap 10), analyzing the answers before the
next round — and one per round in stepwise. The interview closes against a
twelve-dimension requirements coverage table: every dimension either has an
item or is explicitly not-applicable; termination requires all dimensions
closed plus one round with no new information. Materially diverging solution
shapes converge through brainstorming first. A draft's
`owner_confirmation.confirmed` must be a bool and its `summary` a string
(which may be empty); final requires confirmed true and a nonempty
confirmation summary. The top-level summary must still be truthfully
nonempty. Frontier IDs are unique and refer only to open questions; listing
every open question is not required.

## Risk-scaled process

Process rigor is chosen per slice, so not every task pays the same
documentation tax:

- Normal: reversible in-workspace changes; relevant tests and a real demo;
  a goal card only when tracking or recovery is needed. Worker delegation,
  an independent test-author, PUA stage cards or a per-slice reviewer are
  not mandatory; dispatch one fresh reviewer (a no-contract acceptance
  review) when independent correctness judgment, verification blind spots
  or user preference are involved.
- Guarded: external boundaries or higher rework risk; adds small probes,
  acceptance tests and one independent review (reusable for the same version
  and scope).
- Audited: money, privacy, security, migrations or irreversible side
  effects; internally invokes contract, PLAN, CR, an independent
  test-author and the reconcile gate; risk is judged by the data/side
  effects actually touched, not by keywords.

Whatever the tier, the public entries remain `/plan`, `/build`, `/fix` and
`/resume`. Strict capabilities hand control back to the delivery loop when
done — no command switching for the user. Automatic continuation is not
pre-authorization, though: every SI still needs the owner's acceptance of the
actual slice result, an increment decision, and confirmation of the newly
generated PLAN; approvals or risky command authorization can pause
execution. A new Audited contract declares top-level `workflow_protocol:
v0.2`, and non-human V must produce evidence and events via `verify-step`.
A clean slice is not a complete goal. At finish the controller compares the
original request/every brief BS, the whole goal, deferred work and the real
entries, reusing reviewers as needed without adding public commands. Missing
implementation and missing verification are recorded separately; original
device/API boundaries cannot be swapped for sample directories or mocks;
required outcomes that are pending/blocked prevent completion. Optional
wishes must not masquerade as BS only to be silently dropped; scope changes
need renewed explicit confirmation and respect frozen packages. On delivery,
create README/quickstart when missing or update the executable setup and
dependencies, then replay from the declared artifacts in an isolated
environment; borrowing existing global dependencies is not a clean install.
Disclose what was tested — never paper over gaps with "no limitations".

## Internal skills

- `mvp-delivery`: the master controller of `plan/build/fix/resume`, driving
  continuous convergence to the original goal; Guarded/Audited substantive
  tasks are delegated to subagents by default, per
  `references/subagent-orchestration.md`. Every finished goal appends a
  commit-style entry to `docs/delivery-log.md` per `delivery-finish.md`;
  later sessions and `/resume` load only the delivery-log, the active goal
  card and the code — completed brief/PLAN/package full text stops being
  loaded by default (the context-compaction re-entry point).
- `grill`: deep requirements clarification; produces only the brief; closes
  the interview against the twelve-dimension coverage table.
- `research`: external fact-finding (source grading, citation, freshness),
  serving grill's and the controller's "facts are the agent's job" rule.
- `brainstorming`: alternative exploration and convergence when solution
  shapes materially diverge; sits between grill and plan.
- `writing-plans`: turns plans into executable prompts (Context/Files/
  Change/Bounds/Verify/Rollback plus a boundary-condition checklist),
  embedded into PLAN compilation, goal-card first-slice briefs and every
  seat's dispatch template.
- `systematic-debugging`: four-phase root-cause discipline (reproduce/
  isolate/hypothesize/verify) for `/fix` and repeated failures.
- `contract-review`: contract review and PLAN compilation for Audited
  slices.
- `construction`: executes and finishes Audited PLANs, handles CR recovery.
- `task-worker`: executes one bounded Normal/Guarded implementation package
  when dispatched by a fresh subagent.
- `test-author`: independently generates and freezes acceptance tests when
  dispatched by a fresh subagent.
- `reviewer`: read-only review from a fresh subagent, including lightweight
  acceptance and whole-goal checks; boundary-condition coverage is its own
  review dimension.
- `step-executor`: executes exactly one strict PLAN step in isolation from
  a fresh subagent.
- `webapp-testing`: dedicated browser-automation acceptance for web-only
  interface journeys (assertion-first scripts), producing the same
  `ui-acceptance/1` evidence as computer-use.
- `computer-use`: the main controller executes real desktop GUI paths
  (native apps, OS dialogs) on demand — observe, operate, verify; web
  journeys prefer webapp-testing, desktop runs under a per-scenario hard
  budget; UI duty is declared by `goal.ui` and needs separately authorized
  MCP.
- `pua`: proactive challenge, evidence closure and bounded recovery at
  Guarded/Audited acceptance and failure-recovery points; Normal work
  applies the same questions directly — it never replaces engine gates or
  owner decisions.
- `i-have-adhd`: the user-communication layer — actions and status first;
  emits a preview before acceptance handoffs and delivery/blocker after;
  never deletes the full facts handed to reviewer/PUA.

What the user sees is `i-have-adhd`'s short view; reviewer/PUA receive the
full `ACCEPTANCE_HANDOFF`. Guarded/Audited substantive acceptance handoffs
automatically try to dispatch a fresh reviewer with `pua_stage_id`; Normal
dispatches by change risk. Without an existing mode, a generic read-only
acceptance review is used — no new roles or event schemas. Preview first,
then PUA/reviewer, then delivery or blocker. Ordinary Normal progress
creates no reviewer ceremony, and no concise format replaces engine, owner
or independence gates. `i-have-adhd` provides no public command, hook or
global state.

The installer deploys five project subagents — `mvp-researcher`,
`mvp-worker`, `mvp-reviewer`, `mvp-test-author`, `mvp-step-executor` — into
the target project's `.opencode/agents/`, bound respectively to research,
lightweight implementation, read-only review, test freezing and strict step
execution, each with a minimal permission boundary (reviewer has no write;
subagents may not dispatch further). The controller picks seats by the
trigger matrix: substantive tasks dispatch by default, mechanical small
edits are the exception. Loading a skill only adds instructions and never
creates an independent identity; the installed agents provide real
independent sessions. When author isolation is required but subagent
capability is unavailable, record independence-unavailable and block the
Audited release — a waiver cannot fake independent review; Normal/Guarded
may downgrade to controller execution with explicit disclosure. IDs are
claims with no cryptographic identity verification.

## Concurrency and handback

Subagents return a common `TASK_RESULT` envelope (schema `task-result/1`)
with role-specific content in `payload`; the controller validates fields and
deduplicates CONTROLLER_ACTIONs by stable `action_id` — pending or
unknown-state actions are never auto-replayed. Independent Normal/Guarded
packages may write in parallel inside Git worktrees:
`scripts/worktree_tasks.py` handles admission checks, creation, collecting
actual changes, `write_scope` violation checks, patch preflight/integration
and cleanup; the shared workspace still has a single writer, and everything
is verified once against the final stable version after integration.
Audited strict steps keep their existing execution semantics and do not
enter this branch.

## Installation

Requires Python 3.10+. From this repository's root:

```powershell
python scripts/install.py "E:/path/to/target-project"
```

The installer copies the five command wrappers, the five subagent
definitions (`.opencode/agents/`), the validation engine and runtime tools
(`check.py`, `runtime_trace.py`, `check_runtime.py`,
`workflow_protocol.py`, `worktree_tasks.py`) plus `stage-routing.json`,
records skill fingerprints and installed-file digests in a manifest (so
doctor can detect skill-text updates or tampered installed copies), and
registers this repository's current top-level skill directories in
`opencode.json` — avoiding scans of the frozen legacy same-name skills
under `validation/`. On upgrade it replaces the previously exact-matched
repo-root skills path while preserving other configuration. Old commands
still unmodified locally are deleted; locally modified ones are kept with a
notice — only explicit `--force` removes them.

With `opencode.jsonc`, the installer preserves comments and prompts you to
add the skills path manually. OpenCode must be restarted after installing
or modifying skills.

### Optional desktop verification

The operating procedures of
[computer-use-kit](https://github.com/ILoveMyJay/computer-use-kit) are
integrated under its MIT license, adapted to this project's risk, evidence
and subagent boundaries. No new command: `/build`, `/fix` or `/resume`
loads it internally when a path needs a GUI; pure web journeys load
`webapp-testing` first (dedicated browser automation such as Playwright,
assertion-first scripts), and only native desktop/OS dialogs go through
`computer-use`.

Installing the skill does not install or enable a desktop MCP, nor change
global permissions. Cua Driver is recommended; see
[computer-use/README.md](computer-use/README.md) for wiring, the
disabled-by-default config sample and a non-sensitive window smoke test.
The desktop is exclusively operated by the main controller — subagents
never operate concurrently. A screenshot is not an acceptance pass; the
existing engine gates are unchanged. No real desktop backend has been
verified in this repository yet; missing tools/permissions or an
unexecutable acceptance runner blocks explicitly — no fake success.

## Verification

```powershell
python scripts/check.py --selftest
python -B -m unittest discover -s tests -p "test_*.py"
python scripts/check.py hash <file> [<file> ...]   # record digests for brief/test manifests; never hand-compute
python scripts/check_runtime.py doctor <target-project>   # static + host capability diagnosis
python scripts/check_runtime.py doctor <target-project> --strict  # exit code 3 on static problems or tampered installed copies
python scripts/check_runtime.py doctor <target-project> --strict --strict-freshness  # additionally fail on skill source-tree drift
python scripts/runtime_trace.py export <target-project> --out trace.json
python scripts/runtime_trace.py validate trace.json --dispatch <goal>.dispatch.json
python .opencode/workflow/scripts/check.py check-current .opencode/mvp/<goal>.md  # read-only: does a completed card's evidence still match the current workspace
```

Skill source-tree freshness is diagnostic by default: pure documentation
changes never block `--strict`; installed engine/agents copies that no
longer match the manifest digests do. Add `--strict-freshness` to treat
source-tree drift as failure too. Re-running `finish-goal` on a completed
card only means "historically completed" — it does not re-verify the
current workspace; run `check-current` when you need current state.

Runtime gate (optional): after writing
`{"schema": "runtime-policy/1", "goals": "all"}` to the target project's
`.opencode/mvp/runtime-policy.json`, `finish-goal` requires a passing
`check.py runtime-gate <goal>.md --trace <trace.json>` first — it verifies
dispatch claims with native session evidence (real subsessions, completed
skill loads, parent/child provenance, dispatches tied to task-call events
in the trace). Only native traces exported from the local session store
pass; handwritten/imported traces, truncated exports, missing evidence,
seat-fallback violations, reviewer returns contradicting a `satisfied`
claim, or stale evidence (trace/dispatch/policy file hash or goal
definition changed) all block completion. The default requirements are a
minimum — policies may only append, never clear;
`allow_independence_downgrade` has no effect on audited goals. Without the
policy file the existing behavior stands; historical completed cards are
unaffected.

UI acceptance gate: interface journeys are declared by the goal card's
`goal.ui.required` (optionally with `outcome_ids`). The controller executes
the required scenarios in `.opencode/mvp/<goal>.ui-acceptance.json` (schema
`ui-acceptance/1`) and records real execution evidence (web-only journeys
via `webapp-testing`, native boundaries via `computer-use`); `check.py
ui-gate <goal>.md --trace <trace.json> --bind` first binds the artifact
identity, then verifies scenario statuses, a real
computer-use/webapp-testing load, session-consistent completed native
calls, existing observation/result files, policy `ui_tools` matches (or
runner evidence) and artifact identity. After artifacts change you must
reset the affected scenarios, re-execute and re-bind — `--bind` never
relabels old results onto a changed build; `finish-goal` recomputes the
identity and rejects stale assessments. Deleting the sidecar or marking a
required scenario not-applicable cannot cancel the duty; scenarios missing
a backend or permissions are blocked.

Individual strict-flow checks remain directly runnable via
`scripts/check.py`; legal examples live in `tests/fixtures/`.

Run the installed `.opencode/workflow/scripts/check.py` from the target
project's root; target verification command examples are in
`mvp-delivery/SKILL.md`, step verification in
`construction/references/step-protocol.md`. Verification commands run
through Python `shell=True` in the system shell — `cmd.exe` on Windows,
not OpenCode's PowerShell. Inspect commands before execution and obtain
explicit authorization for destructive, paid, credential/privacy or
external-write risks; the engine is not a sandbox. `verify-step` uses the
caller's cwd and must be run from the project root.

The engine checks structure, bindings, exit/timeout and goal stdout
assertions; test commands must still genuinely check product behavior.
`verify-goal` records a snapshot of the current workspace content and
`finish-goal` recomputes it: changing any non-excluded file after
verification invalidates the result until re-verification, and a
verification command that modifies the workspace itself is judged failed.
The snapshot excludes VCS, `.opencode/**`, workflow artifacts, caches and
generated directories. Hashes cannot stop anyone with write access from
forging artifacts, and prove neither identity, independence nor real
usability. `--selftest` only exercises the engine — it is not proof of
product usability. When reading the source brief the engine already
rejects drafts and unconfirmed sources; the controller must still
explicitly validate the final brief and check its semantics — this is not
merely a prompt-layer constraint.

Stricter confirmation types, frontier uniqueness/openness, user-entry in
any state and BS disposition validation may reject older active/blocked
cards or drafts. Schema 1 and the hash algorithm are unchanged, and
historical cards are never rewritten automatically: fix unfinished
artifacts explicitly before continuing, re-verify definition changes under
the full-invalidation rule, and use CR/new packages for frozen inputs.
Complete cards and frozen history stay immutable — even when they fail new
rules, never fabricate "re-verified under new rules"; later repairs create
a new current card and keep the historical evidence. The workspace
snapshot detects "modified after verification" but proves neither product
semantics nor changes inside snapshot-excluded directories. Tests must
still check every subprocess status, pre-operation input snapshots,
result content and repeated-run stability, and use a few safe fault
injections to prove assertions can fail; an unchanged filename set is
neither proof of no writes nor of correct increments. Audited approval
never replaces the controller's duty to verify the final version, the
original scope, the real entries and install reproducibility.

## Design references

- [GitHub Spec Kit](https://github.com/github/spec-kit): independently
  verifiable MVP stories.
- [OpenSpec](https://github.com/Fission-AI/OpenSpec): progressive rigor
  and incremental specifications.
- [Superpowers](https://github.com/obra/superpowers): continuous execution
  and real subagent isolation; this repository's writing-plans,
  systematic-debugging and brainstorming adapt its methodology (see each
  UPSTREAM.md).
- [Anthropic skills](https://github.com/anthropics/skills): the
  methodology source of webapp-testing (see its UPSTREAM.md).
- [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD): process
  scaled to task size.

## License

MIT.

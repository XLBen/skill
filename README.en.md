# MVP delivery skills

English · [简体中文](README.md)

This OpenCode workflow has a single goal: turn ideas into **really-verified,
running results** — not an agent that asks great questions and leaves a pile
of planning artifacts behind. This README is organized around the suite's
chain of thought: what the agent thinks at each node, how it decides, and
when it stops to ask you.

## The overall chain of thought

```text
idea
 ↓  Can I state it clearly? — no → /grill (interrogate)
 ↓  twelve-dimension coverage closed + user confirmation → docs/brief.md
 ↓  What is the thinnest real slice? How risky? → /plan
 ↓  first slice: assumption list → implement → verify for real
 ↓  compare against the original outcome list: gaps left? — yes → next slice (loop)
 ↓                                                     — no  → acceptance: where is the evidence? → delivery
 ↘  bug → /fix: reproduce → isolate → hypothesize → verify
 ↘  session broke → /resume: delivery-log → goal card → code
```

Every hop's decision basis is persisted in files (brief, goal card, dispatch
record, delivery-log) — never in chat history. The chain unfolds below.

## Step 1: grill — "Can I state it clearly?"

`/grill <idea>` does exactly one thing: interrogate a vague idea into a
requirement brief both sides can repeat back identically.

Its chain of thought:

1. **Draw a decision tree; ask only the frontier.** Questions whose
   prerequisites are already settled; answers unlock later questions — no
   mechanical questionnaire traversal.
2. **Five to ten questions per round, grouped by dimension.** Absorb the
   answers, analyze what they changed, and only then derive the next round;
   never dump every question at once. Every round must be a **real
   interaction**: asked via OpenCode's `question` tool when available, or by
   ending the turn and waiting for the reply — never asked and answered in
   the same turn; only answers the user actually gave enter the brief.
3. **Close against a twelve-dimension coverage table**: user and scenario,
   public interface, environment, representative input, output and
   retrieval, **errors and boundaries**, data and state, authority and
   privacy, non-functional, integrations, success signals, non-goals. Each
   dimension is either covered by an item or explicitly not-applicable;
   termination requires all dimensions closed plus one round with no new
   information. A "you decide" answer is recorded as an owner decision —
   not skipped.
4. **Facts are the agent's job.** Anything answerable from the repository,
   code or primary sources is never asked of the user; external facts
   follow the research skill's grading (official docs/source = grade A;
   community answers are leads only), with citations and freshness.
5. **Three finalization questions**: did the user actually say this, or did
   I fill it in? Is every dimension closed? Did anything get quietly
   narrowed, or an optional wish promoted to required success?
6. When solution shapes materially diverge (2+ architectures,
   build-vs-buy), explore alternatives via brainstorming first — rejected
   alternatives get a one-line rationale too.

Output: a confirmed, frozen `docs/brief.md`. Next: `/plan docs/brief.md`.

## Step 2: plan — "What is the thinnest real slice?"

`/plan`'s chain of thought:

1. **Read the repository before asking.** Code, config, error output and
   primary docs answer most questions.
2. **Pick the thinnest runnable slice**: one concrete input crossing the
   necessary layers to a real output or persistent state; demonstrable
   with one command / browser action / API call; no mock success standing
   in for a declared real boundary.
3. **Grade risk by actual side effects, not keywords**:
   - Normal: reversible in-workspace changes;
   - Guarded: external boundaries, higher rework risk → probes,
     acceptance tests, one independent review;
   - Audited: money, privacy, security, migration, irreversibility →
     contract, PLAN, independent test author, reconcile gate.
4. The first-slice brief is written per **writing-plans** as an executable
   prompt: Context (why), Files (exact paths), Change (implementation
   sketch), **Bounds (boundary conditions: empty input / extreme scale /
   concurrency-idempotency / encoding / mid-failure / cleanup /
   compatibility)**, Verify (command + assertion), Rollback.
5. Interface journeys are designed, never executed, in `/plan`.

## Step 3: build — "Implement one slice, verify one slice for real"

`/build`'s chain of thought:

1. **Verify minimal runtime prerequisites**: working directory, OS/shell,
   runtime, dependency lockfiles, config variable names, services, startup.
   A missing dependency is not behavior-red; mocks cannot stand in.
2. **Assumption list**: before the first slice, surface every reversible
   assumption the agent intends to make for one quick owner pass — not
   item-by-item blocking; the list ships verbatim in the delivery report.
3. Guarded/Audited substantive tasks dispatch worker subagents; Normal may
   stay in-session; dispatch bodies follow the step-brief format above.
4. **Failure thinking**: read the error and fix the root cause first;
   failure signatures (V + command + assertion + stable error summary)
   accumulate across seats/resumes — three same-signature failures with no
   new evidence is a no-progress blocker escalated to the user, and the
   second same-signature failure already demands a genuinely different
   method.
5. **After each slice, look back at the original list**: enumerate the gaps
   still blocking the user's original goal, pick the highest-value or
   riskiest next thin slice, re-grade risk before choosing execution.
   MVP is a delivery order, not a permanent scope cut.
6. **Edge thinking**: every step carries Bounds; the reviewer treats
   "were boundary conditions considered/tested" as its own dimension; an
   untested boundary is a finding, never a silent pass.

## The acceptance chain — "Where is the evidence?"

The self-interrogation at every material handoff (PUA discipline; cards for
Guarded/Audited, direct questions for Normal):

- **Closure**: claimed done? Evidence? Without verification output bound
  to the current version, "complete" cannot enter the report. A written
  command is not an executed command.
- **Fact-driven**: before saying "maybe environment/permissions/network",
  read the error with tools, check the source, run a minimal probe.
  Unverified attribution is blame-shifting.
- **Exhaustive but not blind**: before saying "unsolvable", confirm a
  genuinely different method was tried and the same root cause's sibling
  call sites were checked (iceberg rule); escalating with evidence when
  authorization/tools are genuinely missing is the correct action.
- Self-check the five laziness patterns: brute-force retry, blaming user or
  environment, idle tooling, fake busyness, passive waiting.

UI acceptance routing: web-only journeys → webapp-testing (assertion-first
browser scripts); native apps/OS dialogs → computer-use (per-scenario hard
budget: ≤15 actions, ≤2 observation cycles per action, 10 minutes; an
expectation unobservable after two consecutive attempts is failed and
returned to the repair loop — no spinning in place). A screenshot is not
an acceptance pass.

## The fix chain — four-phase root cause

`/fix <problem>` follows systematic-debugging:

```text
reproduce (minimal reproducing command) → isolate (bisect, read real code and logs)
→ hypothesize (≥2 distinguishable hypotheses; run the falsifying probe before editing)
→ verify (original repro turns green + affected regression + boundary spot checks; regression test freezes the root cause)
```

Forbidden: evidence-free environment blaming, same-signature brute-force
retries, shotgun edits ("change N places and see if it works"). Contract vs
reality conflicts go through CR — never around it.

## The resume chain — no guessing from chat

`/resume` loads in order: `docs/delivery-log.md` → the active goal card →
code. **Completed brief/PLAN/package full text stops being loaded by
default**; expand only via the evidence pointers in the delivery-log when a
specific conclusion needs checking. After OpenCode auto-compaction, the
delivery-log is likewise the primary re-entry point.

## When it stops to ask you

Only these cases:

1. Two mutually exclusive product choices materially change the result and
   neither the repository nor the input can arbitrate;
2. An irreversible or destructive operation is about to run;
3. Credentials, privacy, security boundaries, real money or
   outside-workspace side effects are involved;
4. An Audited gate needs actual owner acceptance;
5. The goal is technically unreachable, every path is a guess, or repeated
   attempts produce no new evidence.

Everything else is decided by the agent — minimally, reversibly, following
existing patterns — recorded in the assumption list and delivery report,
then it continues.

## How context stays small

Each finished goal appends a commit-style entry to `docs/delivery-log.md`
(changes / key decisions / verification summary / evidence pointers /
remaining limits). The files themselves stay — the engine binds hashes by
path (brief freeze, evidence, artifact identity); referenced files are
never deleted; only drafts confirmed unreferenced may move to
`docs/archive/`. What gets compacted is "what enters the session", not the
evidence on disk.

## Command quick reference

| Command | When | Result |
|---|---|---|
| `/grill <idea>` | idea is vague | a confirmed `docs/brief.md` |
| `/plan <goal-or-brief>` | see the path first, no code | lightweight goal card; strict PLAN internally at high risk |
| `/build [goal]` | start delivery | runnable, really-verified, continuously completed results |
| `/fix <problem>` | errors, misbehavior, contract conflicts | root-cause repair + regression verification |
| `/resume` | previous run interrupted | continue from persistent state to the original goal |

Recommended paths: clear → `/build`; plan first → `/plan` → `/build`;
vague → `/grill` → `/plan` → `/build`; bug → `/fix`; interrupted →
`/resume`.

## Internal skills quick reference

| Skill | Role in the chain of thought |
|---|---|
| `mvp-delivery` | master controller: slice loop, risk grading, converging to the original goal |
| `grill` | requirements interrogation: decision tree + twelve-dimension coverage |
| `research` | external fact-finding: source grading, citation, freshness |
| `brainstorming` | solution forks: alternative exploration and convergence |
| `writing-plans` | plans as prompts: six-field step briefs + boundary checklist |
| `systematic-debugging` | four-phase root cause: reproduce/isolate/hypothesize/verify |
| `contract-review` | Audited contract review and PLAN compilation |
| `construction` | Audited PLAN execution and CR recovery |
| `task-worker` | bounded implementation packages (fresh subagent) |
| `test-author` | independent acceptance-test generation and freezing |
| `reviewer` | read-only review; boundary coverage is its own dimension |
| `step-executor` | isolated execution of one strict PLAN step |
| `webapp-testing` | web journeys: assertion-first browser automation |
| `computer-use` | desktop journeys: hard-budgeted GUI operation and verification |
| `product-observer` | whole-product black-box observation: blind discover + goal/history compare, mandatory pre-finish gate |
| `pua` | acceptance interrogation: closure / fact-driven / exhaustive-not-blind |
| `i-have-adhd` | user communication: short view, full facts preserved |
| `security-assurance` | conditional: trust boundaries, auth, privacy, secrets; threat model and control mapping |
| `production-readiness` | conditional: release, progressive rollout, rollback, operations handoff |
| `incident-response` | conditional: active production impact - severity, containment, recovery |
| `outcome-learning` | conditional: user/business hypotheses, baselines, smallest experiment |

The installer additionally deploys six project subagents —
`mvp-researcher`, `mvp-worker`, `mvp-reviewer`, `mvp-test-author`,
`mvp-step-executor`, `mvp-product-observer` — into `.opencode/agents/` with minimal permission
boundaries (reviewer has no write; subagents may not dispatch further);
fresh subagents provide real independent sessions — loading a skill alone
creates no independence.

## Installation

Requires Python 3.10+, from this repository's root:

```powershell
python scripts/install.py "E:/path/to/target-project"
```

The installer copies command wrappers, subagent definitions, the validation
engine and runtime tools (`check.py`, `runtime_trace.py`,
`check_runtime.py`, `workflow_protocol.py`, `worktree_tasks.py`) plus
`stage-routing.json`, records fingerprints in a manifest for doctor drift
detection, and registers this repository's top-level skill directories in
`opencode.json`. OpenCode must be restarted after installing or modifying
skills. Desktop verification is optional: no MCP is auto-installed and no
global permissions change; see
[computer-use/README.md](computer-use/README.md) for wiring.

## Verification

```powershell
python scripts/check.py --selftest
python -B -m unittest discover -s tests -p "test_*.py"
python scripts/check.py hash <file> [<file> ...]   # record digests; never hand-compute
python scripts/check_runtime.py doctor <target-project> [--strict [--strict-freshness]]
python scripts/runtime_trace.py export <target-project> --out trace.json
python .opencode/workflow/scripts/check.py check-current .opencode/mvp/<goal>.md
```

Runtime gate (optional): after writing
`{"schema": "runtime-policy/1", "goals": "all"}` to the target project's
`.opencode/mvp/runtime-policy.json`, `finish-goal` requires a passing
`check.py runtime-gate` first — dispatch claims are verified against
native session evidence (real subsessions, completed skill loads,
parent/child provenance); handwritten/imported traces are rejected. UI
gate: `check.py ui-gate ... --bind` verifies scenario statuses, a real
computer-use/webapp-testing load, native calls and artifact-identity
binding; changed artifacts must re-run and re-bind — `--bind` never
relabels old results onto a new build.

The engine checks structure, bindings, exit/timeout and assertions;
snapshots exclude VCS/`.opencode/**`/caches/generated directories; hashes
detect "modified after verification" — they prove neither semantics nor
safety, and the engine is not a sandbox. Full rules live in each skill's
`SKILL.md` and `references/`.

## Design references

- [GitHub Spec Kit](https://github.com/github/spec-kit): independently
  verifiable MVP stories.
- [OpenSpec](https://github.com/Fission-AI/OpenSpec): progressive rigor.
- [Superpowers](https://github.com/obra/superpowers): continuous
  execution, subagent isolation; methodology source of writing-plans /
  systematic-debugging / brainstorming (see each UPSTREAM.md).
- [Anthropic skills](https://github.com/anthropics/skills): methodology
  source of webapp-testing (see its UPSTREAM.md).
- [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD): process
  scaled to task size.

## License

MIT.

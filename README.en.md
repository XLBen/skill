# MVP delivery skills

English · [简体中文](README.md)

This OpenCode workflow separates design from execution: **grill interrogates the
requirements, plan designs the complete software, build implements and tests one
bounded task at a time**. Every key engineering judgment — architecture,
interfaces, dependency order, acceptance criteria — moves up into plan; build
consumes a bounded task packet and never redesigns the system.

The direct payoff: use a design-strong model for `/plan`, then switch to a
cheaper model (DeepSeek, GLM, ...) for `/build` with fewer guesses, less rework
and less irrelevant context. Structural validation is tooling, not the goal;
the goal is always a really-verified, user-usable result.

## The overall chain of thought

Use `/work <goal>` to orchestrate the needed stages from one command; the
diagram below describes the specialist roles without requiring users to invoke
`/grill` or `/plan` first.

```text
idea
 ↓  Can I state it clearly? — no → /grill (interrogate)
 ↓  twelve-dimension coverage closed + user confirmation → docs/brief.md
 ↓  /plan: synthesize → verify technology → components/interfaces/flows →
 ↓        fully specified tasks → design walkthrough → publish
 ↓  /build: next-step packet → implement → this layer's checks →
 ↓         read actual output → observe feedback
 ↓  component → real boundary → integration milestone (planned dependency order)
 ↓    implementation error → retry   missing environment → blocked
 ↓    falsified design assumption → replan (back to plan)
 ↓  at milestones, compare against the original outcomes — gaps? → next task (loop)
 ↓                                —— no gaps → acceptance: where is the evidence?
 ↓  accepted → whole-product black-box observation before delivery
 ↓            (product-observer; model chosen by /visibility)
 ↓  observation gate: v2 report + native trace — blocking finding → /fix → full re-observation
 ↓                                              — no blocking finding → delivery
 ↘  bug → /fix: reproduce → isolate → hypothesize → verify
 ↘  session broke → /resume: next-step packet → goal card → code
```

Every hop's decision basis is persisted in files (brief, engineering design,
goal card, cycle receipts, delivery-log) — never in chat history.

## Division of labor

| Stage | Answers | Never does |
|---|---|---|
| grill | what, why, what counts as success | does not decide how |
| plan | how the system composes, task order, per-task verification | writes no product code |
| build | implement the current task, observe actual output, classify feedback | never redesigns interfaces/architecture |

## Evidence-backed, conditional plans

New designs use `engineering-plan/3` (goal cards remain schema 3). Complete scope
does not mean freezing unverified implementation details. Critical unmeasured
claims require conditions resolved by actual checks, owner decisions or independent
design review. Dependent tasks stay blocked; bounded probes may establish evidence.

Grill makes interaction costs and the protected intent of prohibitions concrete;
a textual answer is valid but must not be stretched to undisclosed consequences.
Counter-questions trigger an answer-then-reask loop; question-tool choices use
compact labels. New briefs track decision topics and explicit supersession, and
`brief-confirmation` regenerates the itemized current summary whose snapshot
must match finalization. The snapshot does not authenticate who answered.
If native decision attribution is needed, `runtime_trace.py export
--include-conversation-text` is an explicit privacy opt-in, limited to matching
project sessions; keep that trace local and git-ignored. Default traces contain
no conversation body.
Plan must justify evidence scope, probe bootstrap dependencies and fallback
equivalence. Guarded/Audited implementation waits for independent design review.
Challenge walkthroughs look for paused event producers, unknown-result retries,
mixed coordinate frames, weakened acceptance and unsupported reliability budgets.

For mid-build objections, `request-decision` pauses the original attempt and
`resolve-decision` records the actual quoted reply. Continue never fabricates a
test pass; revise returns to planning. Decision versions are retained. References
are locally attributed, not authenticated identities; native provenance still matters.
See [the protocol](mvp-delivery/references/planning-readiness.md) and
[the design walkthrough](writing-plans/references/engineering-challenges.md).
No live model blind evaluation has been run; engine checks are not model-quality evidence.

## Step 1: grill — "Can I state it clearly?"

`/grill <idea>` does exactly one thing: interrogate a vague idea into a
requirement brief both sides can repeat back identically.

1. **Draw a decision tree; ask only the frontier.** Settled prerequisites
   unlock later questions — no mechanical questionnaire traversal.
2. **Usually three to five low-risk questions per round; one material fork at a time.** Absorb the
   answers, analyze what changed, only then derive the next round. Every round
   is a **real interaction**: asked via the `question` tool when available, or
   by ending the turn and waiting; asking and answering in one turn is
   forbidden.
3. **Close the twelve-dimension coverage table**: user & scenario, public
   entry, environment, representative input, output & retrieval, **errors &
   boundaries**, data & state, authority & privacy, non-functional,
   integrations, success signals, non-goals. Every dimension is covered or
   explicitly not-applicable; termination requires all closed plus one round
   with no new information.
4. **Facts are the agent's job.** Anything answerable from the repository,
   code or primary sources is never asked of the user; external facts follow
   the research skill's source grading with citations and freshness.
5. **Three finalization questions**: did the user actually say this, or did I
    fill it in? Is every dimension closed? Was anything quietly narrowed, or an
    optional wish promoted to required?

A counter-question is new information, not an answer to the previous option:
research/answer it, then ask the actual unresolved decision. Keep question-tool
labels short and single-line, put context before choices, and fall back to one
plain-text question if the client renders structured choices poorly.

Output: a confirmed, frozen `docs/brief.md`. Next: `/plan docs/brief.md`.

## Step 2: plan — "How does the whole system compose, and how is every task built?"

`/plan` is the engineering designer, not an interview-notes formatter. Its
deliverable is a standalone engineering design (default `docs/plan.md`, any
project-relative path the user chooses):

1. **Synthesize, don't transcribe.** Rebuild the brief as user workflows:
   precondition → input/action → state change → output retrieval → failure
   recovery. Map every required outcome onto a workflow.
2. **Kill the most expensive unknowns first.** Check primary docs, installed
   APIs and real code: can the library actually perform the target operation;
   what are the permission/platform constraints? Read-only investigation is
   allowed; capabilities that need the real target get an early, budgeted
   verification task with fully specified conditional follow-ups. Never invent
   an API to make the design look complete.
3. **Design the whole system**: component responsibilities and state
   ownership, data models, cross-component contracts (each interface has
   exactly one producer; consumers depend on it), layout, data-flow and
   dependency diagrams. Mutually exclusive product forks go to the user;
   ordinary engineering choices get a decision, a reason and evidence.
4. **Every task reaches construction grade** — not just the first slice. Each
   carries: purpose, dependencies, minimal read files, write scope,
   consumed/produced contracts, ordered implementation actions, key code
   sketches, boundary behavior, layered checks, failure routes (local repair /
   missing environment / evidence that means back-to-design) and rollback.
   Later tasks are never just headings.
5. **Design layered verification**:

   | Layer | When | Proves |
   |---|---|---|
   | component | component ready | component behavior; does not require the full app |
   | boundary | adapter ready, before expanding upward | real contact with target file/device/window/API plus readback |
   | journey | after a stage is wired | a user action through the delivered public entry |
   | final | complete candidate | all promises + independent product observation |

   Negative controls go only where a failure is meaningful; no mandatory
   nonzero-exit script per component.
6. **Publish with automatic bookkeeping**:

   ```powershell
   python .opencode/workflow/scripts/check.py prepare-plan <goal> <design-path>
   python .opencode/workflow/scripts/check.py next-step <goal>
   ```

   `prepare-plan` computes the hash binding, derives UI acceptance obligations
   from browser/desktop journeys, invalidates stale evidence, and generates a
   complete **readable plan** `<design>.readable.md` (per-step headings,
   standalone code blocks, commands, failure handling, diagrams preserved) —
   the user never reads escaped JSON, and nobody maintains two specs.
   `next-step` previews the exact packet build will receive.
7. **Design walkthrough before publishing**: take one normal input and one
   failure input and simulate construction — which files/interfaces/boundaries
   does the input traverse? Could a later task be handed to a session with no
   history? Any disconnected calls, invented APIs, component tests that
   prematurely need the full UI? Passing structural checks ≠ a correct design;
   the walkthrough owns content quality.

Full references: [design template & task fields](writing-plans/references/design-template.md) ·
[worked engineering plan](writing-plans/references/engineering-plan-example.md).

## Step 3: build — "Implement the current task; advance after observing"

`/build` is the bounded executor. The core loop is five commands:

```text
python .opencode/workflow/scripts/check.py next-step   <goal>   # current task packet
python .opencode/workflow/scripts/check.py begin-cycle <goal>   # probe only this step's prerequisites
#   implement this step per implementation/change; shared interfaces stay fixed; no future tasks
python .opencode/workflow/scripts/check.py verify-cycle <goal>  # run this step's checks
#   read the real stdout/stderr/exit codes in `observed` (expand raw receipts when truncated)
python .opencode/workflow/scripts/check.py observe-cycle <goal> --decision <d> --interpretation "<actual vs expected>"
#   next-step again: the tool picks the next dependency-ready task
```

- **The packet**: current step + necessary global invariants + this step's
  consumed/produced contracts + read_files + checks. Future tasks, unrelated
  contracts and full history stay out of context by default.
- **Actual output is captured automatically**: observe-cycle attaches this
  attempt's real receipts; the model writes only the interpretation and the
  decision — never a hand-written "actual" replacing observation.
- **Failure classification** (attribute first, then act):

  | Evidence | Decision |
  |---|---|
  | this step's implementation misses the agreed interface/assertion | `retry`: minimal local repair, new attempt |
  | missing device/driver/service/permission | `blocked`: name the prerequisite; no mock substitution |
  | a design assumption (interface, state model, driver capability) is falsified | `replan`: back to plan with evidence; the old design is locked until revised and republished |

- **Layered execution**: component checks never require the unbuilt full app;
  real-boundary checks precede the integration milestones that depend on them;
  `cycle-gate` verifies all steps and version bindings and is enforced by
  `finish-goal`/`check-current`. Beyond fixed samples, checks need varied
  inputs and state readback — in calibration, a fake that passed the fixed
  positive and negative samples was still rejected by a random-content check.
- **Seats**: Guarded substantive tasks dispatch a worker (one task packet at a
  time, never the whole session history); Normal may stay in-session; Audited
  follows the strict seat table. Independent review happens at integration
  milestones and acceptance points, not per component test.
- **Failure budget**: the second same-signature failure must change method;
  three with no new evidence is a no-progress blocker escalated to the user.
  A new task/session does not reset the count.

Protocol: [task packets and layered feedback](mvp-delivery/references/engineering-delivery.md).
Use a design-strong model for plan, then switch to DeepSeek/GLM for build; the
tooling never invents or auto-switches models for you. **Cost and stability
improvements require evaluation on real model runs and cannot be derived from
engine unit-test counts**. An installed deterministic CLI/file calibration was
previously run, but its test harness/report were removed from the repository at
the user's request. No live DeepSeek/GLM end-to-end evaluation has been run.

## The acceptance chain — "Where is the evidence?"

The self-interrogation at every material handoff (PUA discipline; cards for
Guarded/Audited, direct questions for Normal):

- **Closure**: claimed done? Evidence? Without verification output bound to
  the current version, "complete" cannot enter the report. A written command
  is not an executed command.
- **Fact-driven**: before saying "maybe environment/permissions/network", read
  the error with tools, check the source, run a minimal probe. Unverified
  attribution is blame-shifting.
- **Exhaustive but not blind**: before saying "unsolvable", confirm a genuinely
  different method was tried and the same root cause's sibling call sites were
  checked (iceberg rule).
- Self-check the five laziness patterns: brute-force retry, blaming user or
  environment, idle tooling, fake busyness, passive waiting.

Final reports list separately: unit/mock checks, real boundaries, public-entry
journeys, unverified/blocked items — never a total test count as a usability
claim. UI acceptance routing: web-only journeys → webapp-testing; native
apps/OS dialogs → computer-use (per-scenario hard budget: ≤15 actions, ≤2
observation cycles per action, 10 minutes). A screenshot is not an acceptance
pass.

## The product-observation chain — "Was the whole product actually used?"

Implementation and engine verification only prove "the command runs". Before
delivery, someone must use the complete product the way a first-time user
would. `/build` freezes the candidate and dispatches the independent
`mvp-product-observer` seat, which receives a public brief and the real entry
point — never diffs, tests or implementation notes.

1. **Two phases**: `discover` explores blind; `compare` reconciles against the
   original goal, historical product maps and baselines, hunting for
   capabilities that disappeared, degraded, or only survive in some modes.
2. **Observation model**: chosen with `/visibility [model name]`, default
   `gpt 5.6 luna`; stored in the project's `.opencode/mvp/visibility.json`,
   affecting only this project's observation dispatch — never your main chat
   model. Dispatch uses the plugin tool `visibility_dispatch` (requires an
   OpenCode restart). When the model cannot read images, the gap is recorded,
   never pretended away.
3. **Observe, never repair**: the observer writes no product code, goal or
   gate; two host permission layers enforce it. Normal state writes by a
   stateful product are excluded via `.opencode/mvp/<goal>.runtime-state.json`.
4. **Output and adoption**: the final reply contains exactly one ```json
   fenced block (`product-observation/2`); the controller validates it, binds
   the real session/model/packet hash and writes an immutable `result.json`.
5. **The gate**: `check.py product-audit-gate <goal> --trace <trace>`.
   Unresolved critical/high findings, unexplained capability gaps and missing
   native traces all block `finish-goal`. The independent reviewer judges
   `findings_validity` and `coverage_adequacy` separately.
6. **Repair loop**: blocking findings route to `/fix`; a repaired build is a
   NEW candidate and must re-run the full discover+compare sweep — old
   evidence is invalidated by candidate id, never overwritten.

Real-model calibration results live in
[docs/po-repair/CALIBRATION.md](docs/po-repair/CALIBRATION.md).

## The fix chain — four-phase root cause

`/fix <problem>` follows systematic-debugging:

```text
reproduce (minimal reproducing command) → isolate (bisect, read real code and logs)
→ hypothesize (≥2 distinguishable hypotheses; run the falsifying probe before editing)
→ verify (original repro turns green + affected regression + boundary spot checks)
```

Reproduce through the affected journey; use next-step for the bounded task and
its failure_routes: local implementation errors get local repair (this layer's
checks first, then affected boundary/milestone); a falsified interface or
architecture assumption goes to replan — the executor never patches a wrong
design by guessing. A mock-only regression test cannot close a defect observed
at a real boundary. Forbidden: evidence-free environment blaming,
same-signature brute-force retries, shotgun edits.

## The resume chain — no guessing from chat

`/resume` first runs `check.py next-step <goal>`: it replays cycle history and
returns the current task packet plus the next action
(implement/observe/retry/blocked/replan/final-acceptance) without rereading
all historical plans. With an unobserved attempt, read its receipts before
observing; an interrupted run can only be retried or blocked, never backfilled
as passed. replan goes back to the planner; after revision and prepare-plan,
stale evidence is invalidated — code that already satisfies the new plan is
verified and retained, not rewritten because of a restart or model switch.
When multiple unrelated candidates exist, ask; never guess by mtime.

## When it stops to ask you

1. Two mutually exclusive product choices materially change the result and
   neither the repository nor the input can arbitrate;
2. An irreversible or destructive operation is about to run;
3. Credentials, privacy, security boundaries, real money or
   outside-workspace side effects are involved;
4. An Audited gate needs actual owner acceptance;
5. The goal is technically unreachable, every path is a guess, or repeated
   attempts produce no new evidence.

Everything else is decided by the agent — minimally, reversibly, following
existing patterns — recorded and continued.

## How context stays small

build reads only the current task packet each time; full historical plans,
dispatch archives and findings are never loaded by default. Each finished goal
appends a commit-style entry to `docs/delivery-log.md`. The files themselves
stay — the engine binds hashes by path; what gets compacted is "what enters
the session", not the evidence on disk. After OpenCode auto-compaction, the
delivery-log remains the primary re-entry point.

## Command quick reference

`/work <goal>` is the one-shot entry point. For vague goals it runs `grill` in
autonomous inference mode, labels guesses as assumptions, dynamically selects
matching skills actually available in the current OpenCode session, and plans,
executes, repairs and verifies until completion. It does not create brief/plan
documents just for ceremony; artifacts required by the requested result or a
formal acceptance/recovery gate are still produced. It never fabricates owner
confirmation and asks only for a genuinely blocking product decision,
authorization or external prerequisite. Newly added skills become candidates
automatically once the current OpenCode session has loaded them; no `/work`
allowlist needs maintenance.

| Command | When | Result |
|---|---|---|
| `/work <goal>` | agent should autonomously understand and pursue a goal | dynamically selected skills, planning/execution/verification through evidenced completion or a real blocker |
| `/grill <idea>` | idea is vague | a confirmed `docs/brief.md` |
| `/plan <goal-or-brief>` | see the complete design first, no code | whole-goal engineering design + readable plan + schema-3 goal card; strict compiled PLAN at high risk |
| `/build [goal]` | start delivery | task-packet-driven, observed execution until the original outcomes are verified |
| `/fix <problem>` | errors, misbehavior | root-cause repair + layered reverification |
| `/resume` | previous run interrupted | resume from the next-step packet to the original goal |
| `/visibility [model name]` | choose/view this project's observation model | writes `.opencode/mvp/visibility.json` |

Recommended paths: one-shot → `/work`; owner-confirmed requirements → `/grill` → `/plan` → `/build`; clear → `/plan` →
`/build`; bug → `/fix`; interrupted → `/resume`.

## Internal skills quick reference

| Skill | Role in the chain of thought |
|---|---|
| `work` | autonomous controller: infer unclear goals, discover applicable skills dynamically, execute the loop and verify completion |
| `writing-plans` | engineering designer: synthesize → components/interfaces/flows → fully specified tasks → walkthrough |
| `mvp-delivery` | execution controller: task-packet loop, layered verification, failure routing, convergence to the original goal |
| `grill` | requirements interrogation: decision tree + twelve-dimension coverage |
| `research` | external fact-finding: source grading, citation, freshness |
| `brainstorming` | solution forks: alternative exploration and convergence |
| `systematic-debugging` | four-phase root cause: reproduce/isolate/hypothesize/verify |
| `contract-review` | Audited contract review and PLAN compilation |
| `construction` | Audited PLAN execution and CR recovery |
| `task-worker` | bounded implementation packages (fresh subagent consuming an implementation-packet) |
| `test-author` | independent acceptance-test generation and freezing |
| `reviewer` | read-only review: design-walkthrough acceptance, entry/assertion semantics, boundary coverage |
| `step-executor` | isolated execution of one strict PLAN step |
| `webapp-testing` | web journeys: assertion-first browser automation |
| `computer-use` | desktop journeys: hard-budgeted GUI operation and verification |
| `product-observer` | whole-product black-box observation: discover + compare, mandatory pre-finish gate; its model is chosen by `/visibility` |
| `pua` | acceptance interrogation: closure / fact-driven / exhaustive-not-blind |
| `i-have-adhd` | user communication: short view, full facts preserved |
| `security-assurance` | conditional: trust boundaries, auth, privacy, secrets; threat model and control mapping |
| `production-readiness` | conditional: release, progressive rollout, rollback, operations handoff |
| `incident-response` | conditional: active production impact — severity, containment, recovery |
| `outcome-learning` | conditional: user/business hypotheses, baselines, smallest experiment |

The installer additionally deploys six project subagents — `mvp-researcher`,
`mvp-worker`, `mvp-reviewer`, `mvp-test-author`, `mvp-step-executor`,
`mvp-product-observer` — into `.opencode/agents/` with minimal permission
boundaries (reviewer has no write; subagents may not dispatch further); fresh
subagents provide real independent sessions — loading a skill alone creates no
independence.

## Installation

Requires Python 3.10+, from this repository's root:

```powershell
python scripts/install.py "E:/path/to/target-project"
```

The installer copies command wrappers, subagent definitions, the validation
engine and runtime tools (`check.py`, `engineering_delivery.py`,
`runtime_trace.py`, `workflow_protocol.py`, ...) plus `stage-routing.json`,
records fingerprints in a manifest for doctor drift detection, and registers
this repository's top-level skill directories in `opencode.json`. OpenCode
must be restarted after installing or modifying skills. Desktop verification
is optional: no MCP is auto-installed and no global permissions change; see
[computer-use/README.md](computer-use/README.md).

For `/visibility` dynamic observation-model dispatch, the target `.opencode`
must resolve `@opencode-ai/plugin` (the installer prints a hint when it is
missing — run `npm install` in that directory); the plugin provides
`visibility_dispatch` / `visibility_status` after an OpenCode restart.

## Verification

```powershell
python scripts/check.py --selftest
python -B -m unittest discover -s tests -p "test_*.py"
python .opencode/workflow/scripts/check.py engineering-plan .opencode/mvp/<goal>.md
python .opencode/workflow/scripts/check.py next-step .opencode/mvp/<goal>.md
python .opencode/workflow/scripts/check.py cycle-gate .opencode/mvp/<goal>.md
python scripts/check_runtime.py doctor <target-project> [--strict [--strict-freshness]]
python scripts/runtime_trace.py export <target-project> --out trace.json
python .opencode/workflow/scripts/check.py product-audit-gate .opencode/mvp/<goal>.md --trace trace.json
python .opencode/workflow/scripts/check.py check-current .opencode/mvp/<goal>.md
```

Runtime gate (optional): with `runtime-policy.json` enabled, `finish-goal`
requires a passing `runtime-gate` first — dispatch claims are verified against
native session evidence; handwritten/imported traces are rejected. UI gate:
`ui-gate ... --bind` verifies scenario statuses, real tool loads, native calls
and artifact-identity binding; changed artifacts must re-run and re-bind.
Observation gate: schema-2/3 goals must pass `product-audit-gate` (with a
native trace) before `finish-goal`.

The engine checks structure, bindings, exit/timeout and assertions; hashes
detect "modified after verification" — they prove neither semantics nor
safety, and the engine is not a sandbox. Full rules live in each skill's
`SKILL.md` and `references/`.

## Capability boundaries (stated honestly)

- The engine enforces ordering only **when its commands are used**; it cannot
  stop a model from writing a hundred files outside the plan — reviewer and
  native-trace checks cover that.
- observe-cycle validates fields and result binding, not prose honesty; a
  negative control rules out specific fake successes, not forgery in general.
- Calibration covered a CLI/filesystem boundary; **no desktop game, browser
  or live model has been validated**. Game-UI projects still need a real
  backend (Airtest/computer-use), and backend capability must be probed live.
- Historical schema 1/2 cards stay readable; new projects use
  engineering-plan/3 directly — legacy migration is not the main path.

## Design references

- [GitHub Spec Kit](https://github.com/github/spec-kit): independently
  verifiable MVP stories.
- [OpenSpec](https://github.com/Fission-AI/OpenSpec): progressive rigor.
- [Superpowers](https://github.com/obra/superpowers): continuous execution,
  subagent isolation; methodology source of writing-plans /
  systematic-debugging / brainstorming (see each UPSTREAM.md).
- [Anthropic skills](https://github.com/anthropics/skills): methodology
  source of webapp-testing (see its UPSTREAM.md).
- [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD): process scaled
  to task size.

## License

MIT.

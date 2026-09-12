# GLM-5.3 Runtime Evaluation (current skill suite)

> Status: **NOT RUN**. This directory records a behavior evaluation of the
> *current* top-level skills/agents/engine. It never overwrites or reuses the
> frozen `validation/skill-suite-v0.1/` archive; that archive keeps its own
> historical scope and is not evidence about this version.

## Purpose

Static tests (`tests/`, `scripts/check.py --selftest`) prove structure and
engine behavior. They do not prove that GLM-5.3, executing these skills under
a real OpenCode runtime, produces the unique next action the protocol demands.
This evaluation closes that gap for the current combination.

## Environment fingerprint (fill before running)

| Field | Value |
|---|---|
| Model | `glm-5.3 (zhipuai-coding-plan/glm-5.3)` |
| OpenCode version | `<opencode --version>` |
| Skill suite commit | `<git rev-parse HEAD>` |
| Engine hash | `sha256 of .opencode/workflow/scripts/check.py after install` |
| Target project | `<isolated eval project path>` |
| Subagent capability | `<task tool available? pre-allocated IDs? same-seat continuation?>` |
| Desktop backend | `<Cua Driver present, or explicitly absent>` |

Record the runtime's task-tool ID semantics before scoring scenarios 3 and 8:
whether a session/task ID is available before dispatch, and whether a seat can
be resumed with additional input. The two-step ID bootstrap and
CONTROLLER_ACTION round-trip depend on these facts.

## Scenarios

Each scenario runs in a fresh isolated target project with the suite installed
via `scripts/install.py`. Record dispatch transcripts (or `.dispatch.json`
snapshots) plus the controller's final message. A scenario passes only if the
observed next action is unique and matches the protocol.

| # | Scenario | Must observe | Status |
|---|---|---|---|
| 1 | Normal goal end-to-end | thinnest slice, worker dispatch, real verify-goal evidence, finish-goal, no ceremony artifacts | PASS — runs/2026-09-12-glm53-current/s1-normal-end-to-end.md |
| 2 | Guarded goal, no reviewer seat | capability-unavailable recorded and disclosed; controller check completes finish (Audited would block) | PASS — runs/2026-09-12-glm53-current/s2-guarded-no-reviewer.md |
| 3 | Audited slice | two-step test-author ID bootstrap; package-internal manifest written; STEP_HANDBACK returned before verify-step; controller runs verify-step exactly once per attempt | PASS (dispatch layer; engine verify-step event binding NOT RUN, disclosed) — runs/2026-09-12-glm53-current/s3-audited-slice.md |
| 4 | Three same-signature failures | no fourth ordinary retry after seat change or `/resume`; escalation payload with two costed options | PASS — runs/2026-09-12-glm53-current/s4-circuit-break.md |
| 5 | Reviewer returns `owner`, then interruption | resume executes pending_actions first; done status is not treated as acceptance | PASS — runs/2026-09-12-glm53-current/s5-owner-verdict-resume.md |
| 6 | Defect in a completed package | sibling FIX package created; base package untouched; no same-PLAN CR recovery | PASS — runs/2026-09-12-glm53-current/s6-fix-package.md |
| 7 | New grill after a frozen brief | versioned `docs/brief-vN.md`; old goal source/hash still validates | PASS — runs/2026-09-12-glm53-current/s7-brief-versioning.md |
| 8 | Controller-action round-trip (GUI or engine V) | single controller execution, evidence passed back, seat resumed; no duplicate side effects | PASS (engine-V variant, observed in s3) / NOT RUN (backend absent, GUI) — runs/2026-09-12-glm53-current/s8-controller-action.md |

Scenario 8 with a real desktop backend requires separate explicit
authorization; when the backend is absent, record `NOT RUN (backend absent)`
rather than simulating GUI results.

## Recording

Create `runs/<date>-<slug>/` per scenario containing:

- `environment.md` (fingerprint above);
- `dispatch.json` snapshot and/or dispatch archive copies;
- `transcript.md` (controller-visible messages, reviewer returns);
- `result.md` with PASS/FAIL, the decision point observed, and deviations.

Do not modify frozen historical archives, and do not report a scenario as
passed based on keyword presence in outputs.

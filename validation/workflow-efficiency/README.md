# Workflow Efficiency Baselines

This directory defines how to measure where `/build` wall-clock actually goes.
It exists to answer the question: **within one continuous run, how much time is
engineering, how much is necessary assurance, and how much is orchestration
overhead?**

The metrics produced here are **diagnostic only**. They are never read by
`check.py`, `runtime_trace.py validate`, or any finish gate. A failed metrics
export must never block or alter product delivery.

## Tooling

`scripts/workflow_metrics.py` exports a `workflow-metrics/1` report from the
local OpenCode session store (`~/.local/share/opencode/opencode.db` or
`%LOCALAPPDATA%\opencode\opencode.db`):

```powershell
python .opencode/workflow/scripts/workflow_metrics.py export <target-project> --out docs/metrics/<run>.json
python .opencode/workflow/scripts/workflow_metrics.py compare <baseline>.json <candidate>.json --out docs/metrics/compare.json
```

The report contains:

| Field | Meaning |
|---|---|
| `sessions[]` | Real sessions with parent links, agent, model, created/updated, tokens, cost, `active_seconds`, `span_seconds`, `interrupted` |
| `models{}` | Per-model turns, input/output/reasoning tokens, cache read/write, cost |
| `totals.span_seconds` | First observed activity to last observed activity |
| `totals.active_seconds` | Union of message and tool intervals across all seats (parallel seats never double-count) |
| `totals.idle_seconds` | `span_seconds - active_seconds` when both are known |
| `totals.assistant_turns` | Model turns (the repeated cost unit) |
| `totals.tool_calls` / `task_dispatches` | Tool invocations and child dispatches |
| `tools[]` | Per-session per-tool counts, statuses and durations |
| `duplicate_command_candidates[]` | Exact normalized commands run 2+ times — **suspect-reusable only**; identical commands may legitimately differ in inputs, artifact identity or environment |
| `availability{}` | Which data sources were actually present; absent data is `null`, never zero-filled silently |

## Measurement protocol

1. Use a **fresh target project** installed with the current workflow:
   `python scripts/install.py <target>` and restart OpenCode.
2. Record the model/provider used for the run. Comparing different models or
   different goals invalidates the comparison; `compare` refuses nothing but
   the diff is only meaningful within the same task and model family.
3. Run the case from its case file (see `cases/`) and record wall-clock start
   and end from the session store, not from memory.
4. Export metrics immediately after the run and keep the JSON.
5. Record how much of the span was **waiting on the owner** (credential
   prompts, confirmations, sleep) separately; the tool cannot infer it. Do not
   count owner wait as orchestration overhead.
6. For optimization claims, run the same case before and after the change and
   use `compare`. Report both `active_seconds` and per-model `turns`.

## Case files

- `cases/normal-local-cli.json` — smallest Normal delivery.
- `cases/guarded-boundary.json` — Guarded integration with an external boundary.
- `cases/audited-multistep.json` — Audited multi-step slice with one repair and
  one resume.

Each case file names its goal, setup, expected rigor and the fields to record.

## Reading the numbers

- A high `idle_seconds` with low `active_seconds` means waiting (owner,
  provider queue, or interrupted session), not workflow overhead.
- A high number of `assistant_turns` with few `tool_calls` points at
  orchestration/reasoning overhead, not command execution.
- `duplicate_command_candidates` is a prompt for investigation, never a
  verdict; confirm identical inputs and artifact identity before treating a
  repeat as waste.
- `availability.message_tokens=false` means the store did not expose per-turn
  tokens; do not compare token counts across runs with different availability.

## Baseline status

| Case | Status | Notes |
|---|---|---|
| normal-local-cli | NOT RUN | awaiting a hosted run |
| guarded-boundary | NOT RUN | awaiting a hosted run |
| audited-multistep | NOT RUN | awaiting a hosted run |

# Backend Routing

> When to read: before selecting the execution backend for a
> product-observation phase, and before declaring any backend's capability
> status. A backend is `available` ONLY after its live probe passes on the
> actual host; installation alone proves nothing.

## Backend Order (default selection)

| Surface | Default backend | Alternatives |
|---|---|---|
| Visual surfaces (screenshots) | direct multimodal read: the captured image is handed to the observing model, preferred once the model actually reads it | `Midscene` vision grounding (needs `MIDSCENE_MODEL_*` env + egress) for Canvas / vision-heavy UI |
| Web journeys | `agent-browser` (isolated `--session`, Chrome for Testing) | `playwright-cli` when the appointed observer model is coding-only and cannot read screenshots; installed Playwright assertion scripts |
| Native desktop / OS dialogs | probed desktop backend behind `computer-use` | `UI-TARS` desktop/operator (fallback; needs a vision-language model); Midscene |
| Canvas / vision-heavy UI | Midscene skills (vision grounding) | direct multimodal read; UI-TARS |
| Mobile / native apps | `agent-device` (iOS needs macOS; win32 hosts: Android/ADB + desktop targets only) | — |
| CLI / API / library products | real public entry commands, endpoints, packaged examples | — |
| Audio / video evidence | FFmpeg/ffprobe via `scripts/observation_media.py` (capture/prepare only) | — |

Backend selection and argv construction live in
`scripts/observation_backend.py`: `preflight_skip_plan`, `choose_backend`,
`agent_browser_argv`, `playwright_cli_argv`, `run_step_sequence`.

Do not install overlapping browser frameworks. One execution substrate per
surface; alternatives stay registered, not stacked.

## Preflight Reuse (what may be skipped)

`preflight_skip_plan(preflight, context)` decides per item (`host`, `model`,
`candidate`, `session`) whether a passed preflight lets the controller skip a
repeated probe. A cover only skips when its `status` is exactly `passed` AND
every identity field it records is present and equal in the dispatch context;
a missing preflight, a missing context field, a mismatch, or the word
"controller-verified" alone keeps the probe on (fail closed). `choose_backend`
never invents a backend: an unsupported preference, an unavailable host or a
cover that contradicts the preference returns `backend: null` (no silent
substitution); with no passed host cover the default is `agent-browser`,
marked unverified.

## Batched Short Journeys

An observer dispatch is a short journey batch: several backend steps executed
back to back so the observer spends few model turns, with intermediate
evidence retained even when a later step fails. `run_step_sequence` executes
the batch through an injected runner (`observation_process.run_process`),
stops at the first failure / timeout / exception, and returns the failed step
plus `remaining` — the controller decides the follow-up, never a pre-written
route embedded by the implementer.

## Media: Control Probe First

`capture_chain_verdict` refuses to judge the product unless the control probe
itself passed (`probe_ok`, signal `present`); otherwise the verdict is
`capture-unverified`. A silence claim is only valid from an `audio-track`
record with non-empty `commands`, a named perception model, and a recorded
`capture_chain.verdict == "product-silent"`; transcripts, file existence or
"the video has an audio stream" never prove silence. FFmpeg/ffprobe prepare
and probe evidence; semantic judgement stays with the observing model.

## Live Probes (run before first use, per host)

| Probe | Passes when |
|---|---|
| subagent dispatch | a fresh observer subagent session starts and returns |
| entry operation | the subagent opens/launches the target entry via the backend |
| perception | captured evidence (screenshot/snapshot/output) is actually READ and described by the observing model — writing a file is not perception |
| evidence persistence | traces/screenshots/results land under the round evidence dir and paths return |
| session isolation | observer uses its own session/profile, never the user's browser profile or desktop state |
| sensory channel | for sound/motion/timing: a real capture+read cycle succeeds (e.g. audio actually recorded and audible-checked); video files are NOT assumed to carry audio |

Probe results are recorded in the phase packet generation notes:
`available | unavailable | not-required`, with evidence. `unavailable`
never becomes `not-required`. Static doctor output (installed binaries,
env vars) is reported separately from live probe results.

## Windows Host Notes (this repository's environment)

- `agent-browser record` (repro video) requires ffmpeg on PATH; without it,
  degrade to stepwise screenshots + trace — record the degradation, do not
  fake video evidence.
- Profile file locks: close user Chrome before any `--profile` reuse; the
  observer must use isolated sessions/Chrome for Testing, never the user's
  profile (also the computer-use privacy red line).
- Midscene `computer-automation` works on Windows but requires
  `MIDSCENE_MODEL_API_KEY/NAME/BASE_URL/FAMILY` and network egress to the
  model provider; missing credentials → backend `blocked`, reported.
- `agent-device` iOS/WebDriverAgent paths are macOS-only; on win32 only
  Android/ADB and desktop targets are claimable — never report iOS coverage
  from a Windows host.
- Non-ASCII repository paths: quote every path in commands; `check.py`
  verification commands run through cmd.exe with its quoting rules, not
  PowerShell.

## No-Fabrication Rules

- A backend that cannot actually exercise a surface produces a capability
  gap in the phase result, not an assumed pass.
- Coverage claims cite the backend that produced them.
- Adding tokens/models never substitutes for a channel that was never
  captured (e.g. silent-audio regression with no audio capture).

# Environment Fingerprint

| Field | Value |
|---|---|
| Model | `glm-5.3 (zhipuai-coding-plan/glm-5.3)` |
| OpenCode version | `1.18.25` |
| Skill suite commit | `3106bef8b1f08abd1c4e28b5420d4867c06dcb6f` |
| Engine hash (installed) | `3e080d3ffde1a169e34c7abe86c4bfd94d8a6e3e17e6449951c06a4b9c76847b` |
| Target projects | `validation/glm53-runtime-eval/runs/targets/s1..s7` (gitignored, inside the repo workspace so dispatched subagents operate inside their write boundary — deviation from "external isolated project", disclosed) |
| Subagent capability | task tool available; IDs (`ses_...`) reported only in the completed dispatch result — no pre-allocated IDs; same-seat continuation via `task_id` supported (re-verified empirically in scenario 3) |
| Desktop backend | absent (no desktop MCP configured in this session) |

Dispatch transcripts live in `transcripts.md` per scenario plus the durable
`dispatch.json` / `dispatch-archive/` inside each target.

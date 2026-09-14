# WP1 Findings: capability discovery and invocation, reproduced with native evidence

Date: 2026-09-14. Tool: `scripts/check_runtime.py` (static + host doctor).
Host: opencode 1.18.25, session store `~/.local/share/opencode/opencode.db`
(SQLite; `session.parent_id`, `part.data` for tool calls).

## How to reproduce

```powershell
python scripts/check_runtime.py doctor <target-project> --json report.json
```

`static` computes what the host should discover from real config files
(project walk-up + global + default + external skill locations) and validates
frontmatter. `host` reads the session database and reports only **real**
`skill`/`task` tool parts (`state.status == completed`) plus parent/child
provenance. "Expected-not-evidenced" is a data point, never proof of failure;
the doctor never fabricates success records.

## Finding 1 — dev repo: workflow skills are host-invisible

`E:/MISC/代码项目/skill` has no project `opencode.json` and the global config
has no `skills.paths`, so the 11 workflow skills are not discoverable by any
session opened in this repo. The 5 `mvp-*` agents ARE discoverable via
`.opencode/agents/`. Symptom confirmed live: the current session's skill list
contains only the built-in `customize-opencode` while its task tool lists all
five `mvp-*` subagents. Consequence: in-repo testing cannot exercise the
skill-load chain; validation must happen in an installed target project.

## Finding 2 — installed target project: full chain works, with native proof

`E:/MISC/代码项目/tile` (installed 2026-09-12 by `scripts/install.py`):

- project config registers 11 workflow skills via `skills.paths`
- real completed skill loads recorded in the session database:
  `grill, i-have-adhd, mvp-delivery, pua, reviewer, task-worker`
- 2 task dispatches, both provenance-verified:
  - `ses_f69e3a719ffe3RLmHrQhYr827P` agent `mvp-worker` (parent
    `ses_f6a4ad577ffe2kBBkQ6BeHGLAC`) loaded `task-worker` — completed
  - `ses_f69dc4f2cffep9RTegz4AdGdEB` agent `mvp-reviewer` (same parent)
    loaded `reviewer` then `pua` — completed

So: when installed, official subagents are dispatched and load their role
skills, and the native evidence chain (controller part → child session →
skill parts) is complete in the database. The reported failure mode is not
"host cannot do it" but "nothing checks it per run".

## Finding 3 — the historical PASS that proved nothing

`validation/glm53-runtime-eval/runs/2026-09-12-glm53-current/` reports
`general`/`explore` substitutions for worker/reviewer and still marks s1
PASS. Those sessions do not exist in this machine's database, so the report
cannot be re-verified here. Per protocol it must be treated as
unverifiable-by-us; WP6 reruns the regression with native evidence instead.

## Finding 4 — engine cannot see orchestration evidence (confirmed in code)

`scripts/check.py` `finish_goal()` (check.py:1165-1183) requires only that
every outcome is engine-verified; it never reads dispatch records, reviewer
returns, or skill/task provenance. `subagent_id` fields are validated as
non-empty strings only. Product verification and orchestration verification
are currently disconnected — this is what WP4/WP5 close.

## Doctor bug fixed during WP1

Root-level `SKILL.md` under a `skills.paths` entry (exactly how the installer
registers each skill) was falsely flagged as name-mismatch. Folder name now
resolves to the root's own name when `SKILL.md` sits at the root; verified
against the tile project output.

# OpenCode workflow: strong model plans, weak model builds

English · [简体中文](README.md)

```
/grill   →  docs/brief.md   open questions first (no suggestions), line-by-line playback, then decisions by your criteria
/plan    →  docs/plan.md    architecture, single shared interfaces, one error policy, small task cards (roadmap phases for big projects)
/build   →  card by card    worker subagents write code (optionally in parallel); controller re-verifies, reviews, escalates
/change  →  changes         plans a change like /plan does: append or reopen only the affected tasks
/ship    →  delivery        acceptance, docs, cleanup, delivery notes, merge or PR
```

For an existing project: `/grill <idea>` (change interview, appended to the brief as “变更 N”) → `/change` → `/build`; clear requests can go straight to `/change`.

In existing repositories `codemap` writes a one-page map first; `handoff` passes state to a new session; `retro` reviews a finished build.

Without a command: small changes are done directly, bugs go through `debug`, larger goals plan first and then build (see [AGENTS.md](AGENTS.md)).

## Design

- **The weak model sees one card.** `wf.py task T03` prints the background, conventions, shared interfaces, error policy and the current card — usually under 50 lines.
- **Error handling is defined in one place.** The plan's error policy lists the failures to handle; everything else propagates. The worker has an explicit list of things not to add, and `wf.py diffcheck` lists every try/except, type/None guard and empty fallback for the controller to check against the policy.
- **Tasks are vertical slices.** T01 is an end-to-end skeleton; each task touches at most 4 files and has a verify command that asserts content.
- **The controller does not trust self-reports.** `wf.py done` only accepts a passing `wf.py verify` record.
- **Three review points only**: optional plan review, per-task diff review, and a final review where the reviewer actually runs the acceptance examples.
- **Escalation on failure**: retry with the error → controller diagnoses first → strong `worker-strong` model → back to the plan or the user.
- **Cross-platform**: verify commands starting with `python` run with the current interpreter; lint warns about grep/sed and other commands missing on Windows.
- **Checkers over prompts**: `guardrails` sets up one lint/type-check command (including rules that catch swallowed exceptions) in the plan's `## 检查` section, run on every verify.
- **Contract-first teams**: whenever the design spans several components, the plan defines `## 接口契约` (signature, examples, contract test); T00 by `test-author` builds stubs and failing contract tests; lanes go to `backend-worker` / `frontend-worker` etc. in parallel, and `wf verify` runs the contract tests of each provided interface.
- **Two rules enforced by a plugin**: `.opencode/plugins/wf-guard.js` points every shell command's temp dir at the in-project `.wf/tmp/` (rewriting `/tmp/` paths too), and blocks a 4th retry of a command that failed 3 times in a row with no code change, as well as loops that retry a failed command.
- **Skill profiles**: extras are grouped into profiles (backend, frontend, automation, ai, release) and hidden unless enabled via `python .opencode/skills.py use <profile...>` or `install.py --profile`; workers can only see the `worker` skill.

## Layout

| Path | Contents |
|---|---|
| `grill/` `plan/` `build/` `worker/` `review/` `debug/` | core workflow |
| `change/` `codemap/` `ship/` `handoff/` `guardrails/` `retro/` `testing/` | changes, repo map, delivery, session handoff, checks, retrospective, test techniques |
| `scripts/skills.py` | enables extras by profile via `permission.skill` (installed as `.opencode/skills.py`) |
| `scripts/wf.py` | plan runner: status / next / task / verify / done / diffcheck / lint / regress / reopen / impact / contracts / lanes / wt-add / wt-merge / wt-drop |
| `scripts/vendor.py` | imports optional skills from pinned upstream commits listed in `extras/upstream.json` |
| `scripts/install.py` | installer |
| `models.md` | model roles and known tendencies |
| `extras/` | optional skills from anthropics/skills, vercel-labs/agent-skills, addyosmani/agent-skills and mattpocock/skills (pinned, unmodified), plus local webapp-testing (with agent-browser), computer-use, postgres and frontend-engineering; profiles in `extras/profiles.json` |
| `validation/` | three benchmark tasks, oracles and metrics |

Ideas borrowed from superpowers, mattpocock/skills, ponytail, stop-that-shit, pua, i-have-adhd and others are listed in [CREDITS.md](CREDITS.md).

## Install

Requires Python 3.10+.

```bash
python scripts/install.py /path/to/project
```

Then set `model:` in `.opencode/agents/worker.md` and `reviewer.md` (see [models.md](models.md)) and restart OpenCode.
Skills are referenced by path, so editing them needs no reinstall. Upgrading from v1 removes unmodified files the v1 installer wrote. Use `--no-extras` to skip `extras/`.

## Verify

```bash
python -m unittest discover -s tests -v
python validation/setup.py 01-basic-cli ~/bench/l1
```

Real-world quality is measured by the [validation](validation/README.md) benchmarks; record runs in [validation/RESULTS.md](validation/RESULTS.md).

## License

MIT. Upstream skills under `extras/` keep their own licenses and attribution.

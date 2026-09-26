# MVP delivery skills

English · [简体中文](README.md)

This OpenCode workflow separates **requirements, engineering design, and verified delivery**, while letting users request work or report bugs in ordinary language. The agent selects matching skills actually available in the session; users do not need to name them or invoke a stage command first.

## Entry points

| Entry | Behavior |
|---|---|
| Ordinary goal (no command) | Internal `work` method: infer, plan if needed, implement, and verify. Small clear changes need no formal plan; applicable gates still apply. |
| Defect or failed check (no command) | `systematic-debugging`: reproduce, isolate, test a root-cause hypothesis, repair, and reverify. Managed goals reuse `mvp-delivery` Fix Mode. |
| “Continue” | Recover the uniquely matching durable goal; ask when candidates are ambiguous. |
| `/grill <idea>` | Interactively clarify and confirm a brief; never invent owner answers. |
| `/plan <goal-or-brief>` | Design the whole goal and publish executable tasks without editing product code. |
| `/build [goal]` | Execute an **existing valid plan**; if absent, direct the user to `/plan`. |
| `/resume` | Continue an unfinished goal from durable state. |
| `/visibility [model]` | Select or inspect this project's product-observation model, not the main chat model. |

Explicit stage commands take precedence over the default route. Falsified design assumptions return to planning; implementation errors are repaired within the affected step; missing services or devices are reported as blockers. Completion requires evidence for the original outcomes at real boundaries, not merely structural checks or screenshots. See [mvp-delivery](mvp-delivery/SKILL.md) and the [stage routing authority](mvp-delivery/references/stage-routing.json) for risk, independent seats, UI acceptance, and product-observation gates.

## Install

Requires Python 3.10+. From this repository's root:

```powershell
python scripts/install.py "E:/path/to/target-project"
```

The installer copies five commands, default routing, the workflow engine, and subagent definitions; it registers live skill paths and routing in the target project's `opencode.json`. It preserves an existing `AGENTS.md` and prints manual merge instructions for `opencode.jsonc`. Upgrade old installations with a full install: `--commands-only` does not configure the default route and cannot replace legacy `/work` and `/fix` on its own. **Restart OpenCode** after installing or changing skills.

Dynamic `/visibility` dispatch requires `@opencode-ai/plugin` to resolve from the target project's `.opencode`; the installer prints a hint if missing. Run `npm install` there and restart. The installer does not add a desktop MCP or change global model/permission settings.

## Verify and read further

```powershell
python scripts/check.py --selftest
python scripts/check_runtime.py doctor <target-project> [--strict [--strict-freshness]]
python .opencode/workflow/scripts/check.py next-step .opencode/mvp/<goal>.md
python .opencode/workflow/scripts/check.py check-current .opencode/mvp/<goal>.md
```

Read only the relevant skill: [grill](grill/SKILL.md) · [writing-plans](writing-plans/SKILL.md) · [work](work/SKILL.md) · [mvp-delivery](mvp-delivery/SKILL.md) · [systematic-debugging](systematic-debugging/SKILL.md) · [computer-use](computer-use/SKILL.md) · [webapp-testing](webapp-testing/SKILL.md). `check.py` validates structure and evidence bindings; actual models, devices, and full product journeys still require their own live verification.

## License

MIT.

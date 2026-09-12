# i-have-adhd Upstream and Adaptation

## Source

- Repository: <https://github.com/ayghri/i-have-adhd>
- Skill source: `skills/i-have-adhd/SKILL.md`
- Commit inspected: `6f1f982d0a47c65899af3c5a7450b7098bc65325`
- Author: Ayoub Ghriss (`ayghri`)
- Declared license: MIT

## Kept

- Action-first output.
- Numbered bounded steps.
- Visible state and concrete wins.
- Specific, honest user-facing time estimates.
- Matter-of-fact errors, tangent suppression and no ceremonial preamble/closing.
- A presentation cap of five visible items without dropping required evidence.

## Adapted

- The reader is not assumed to have a diagnosis; this is an output ergonomics layer.
- The skill is internal to this repository's five-command workflow, not an always-on plugin,
  hook or public `/i-have-adhd` command.
- “Lead with the next action” never delegates work the agent is authorized to perform itself.
- Full acceptance facts are placed in `ACCEPTANCE_HANDOFF` for reviewer/PUA; the user receives
  a concise preview or delivery summary.
- Existing owner decisions, engine gates, reviewer independence and PUA evidence rules remain
  authoritative.
- No upstream hooks, commands, telemetry, feedback storage, model calls or automatic updates
  are bundled.

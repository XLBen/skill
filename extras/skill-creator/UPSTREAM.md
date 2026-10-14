# Upstream

- Source: https://github.com/anthropics/skills/tree/33375500bcea98d610eb30ce10ac4e59b89c390d/skills/skill-creator
- Commit: `33375500bcea98d610eb30ce10ac4e59b89c390d`
- `SKILL.md` Git blob: `65b3a402dbd09b8e83f9d637c6b553875189085c`
- The upstream skill tree, including its Apache-2.0 `LICENSE.txt`, supporting scripts, reference files and eval viewer, is copied without editing. `scripts/vendor_upstream_skills.py` verifies each upstream Git blob before adding it.

This is a conditional authoring/evaluation skill, not a gate on ordinary product work. Its `claude -p`, Claude-specific viewer, subagent and packaging examples are upstream instructions, not proof that those capabilities are available in OpenCode. Probe the current host and use only available backends; never report an evaluation as run when it was not. Do not let its suggested commit/push actions override this project's explicit user-authorization rules.

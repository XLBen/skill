# Upstream

- Source: https://github.com/vercel-labs/agent-skills/tree/063bee94c3f4df8453406c830b0a7df0f2860278/skills/react-best-practices
- Commit: `063bee94c3f4df8453406c830b0a7df0f2860278`
- `SKILL.md` Git blob: `237988de4a66dd8a71d30a2c24ebe1a86b58d04e`
- Upstream declares MIT in the skill frontmatter. The original prompt, expanded `AGENTS.md`, and all referenced `rules/` files are copied verbatim. `scripts/vendor_upstream_skills.py` verifies each Git blob before adding it.

Trigger only for React/Next.js work where the relevant component, data-flow or performance rule applies. Read matching rule files as needed, rather than loading all rules for unrelated tasks. Treat optimization suggestions as choices to evaluate against actual behavior and the original goal, not as permission for unrelated refactors.

# Workflow entry for ordinary requests

These rules apply to this repository and, when installed, to projects using this workflow suite. The default routing below applies to the primary controller handling a user's request; delegated subagents follow their assigned role and task instead of starting a new work/fix goal. An explicit `/grill`, `/plan`, `/build`, `/resume`, or `/visibility` command takes precedence. Respect the host's current agent mode, read-only restrictions, permissions, and the user's stated scope.

When the user does **not** name a stage command, decide from the request and current project state:

- A new actionable goal: load the `work` skill and follow its autonomous goal loop. Infer reversible details from evidence, mark assumptions, and continue through suitable planning, execution, and verification without asking the user to invoke another command. Do not require a formal plan for a clear, bounded change; retain any real rigor, recovery, or acceptance gates that apply.
- A defect, failed check, regression, or review finding requiring repair: load `systematic-debugging` and use the existing Fix Mode in `mvp-delivery` when the defect belongs to a managed goal. Reproduce and diagnose before editing, reuse the matching unfinished goal and its evidence, and reverify the affected behavior. A small standalone repair may be handled directly without inventing a plan or goal card.
- A request to continue unfinished work: reconcile the unique durable goal and resume at its pending step using `mvp-delivery` recovery rules. Ask which goal only if the candidates are genuinely ambiguous.
- A question, review, or request explicitly limited to design: answer or perform only the requested scope; do not treat it as authorization to implement.

At each real task or acceptance boundary, choose from the skills **actually available in this OpenCode session**. Load only the original skills whose descriptions and triggers match the work, including domain skills when applicable; re-evaluate on a changed boundary. A skill file merely existing on disk does not mean it was loaded. The user never needs to name a skill. Do not fabricate owner decisions, verification results, or a successful handoff.

Explicit `/build` requires an existing valid plan; if none exists, direct the user to `/plan` rather than silently creating a plan or editing product code. This restriction does not prevent an uncommanded `work` goal from planning internally when the work actually needs it.

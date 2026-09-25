---
description: Clarify a vague idea into a validated requirement brief before review
agent: build
---

Load the `grill` and `i-have-adhd` skills and follow them for this idea:

$ARGUMENTS

Every interview round must be a real interaction: ask through OpenCode's
`question` tool when available, otherwise end the turn with the questions and
wait for the user's reply. Never simulate the questions and the answers in
one turn, and never record decisions or confirmations the user did not
actually give. The final owner confirmation is likewise a real question.

Stop after the brief is final, owner-confirmed, and passes the brief
validator. Before finalizing, apply grill's Final Confirmation Check
(attribution, dimension coverage, honesty of scope); dispatch a fresh reviewer
for Guarded/Audited, or for Normal when the stage routing's risk trigger applies.
Under grill's Brief Versioning, hand off the actual active
version file (`docs/brief.md` or the next-versioned `docs/brief-vN.md`),
never an already-consumed frozen version. The next public command is
`/plan <that path>`.

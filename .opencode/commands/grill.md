---
description: Clarify a vague idea into a validated requirement brief before review
agent: build
---

Load the `grill` and `i-have-adhd` skills and follow them for this idea:

$ARGUMENTS

Stop after the brief is final, owner-confirmed, and passes the brief
validator. Before finalizing, load the `pua` skill and run the `brief-final`
acceptance check against the user confirmation and brief evidence; the
final-brief handoff is a material acceptance handoff (fresh reviewer per the
stage routing). Under grill's Brief Versioning, hand off the actual active
version file (`docs/brief.md` or the next-versioned `docs/brief-vN.md`),
never an already-consumed frozen version. The next public command is
`/plan <that path>`.

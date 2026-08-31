# Requirement And Owner Protocol

> When to read: before the first owner question (intake) and whenever a T
> decision is queued or an authority conflict appears.

## Authority

Use this order: latest explicit owner decision, confirmed project requirement,
confirmed P/T node, then AI consistency inference. AI may identify a conflict
but may not invent budget, preference, legal judgment, or product direction.

Every P sourced from a file records its content hash or revision. Every direct
owner statement references an immutable event ID. A changed source opens T or
CR; it does not silently rewrite P.

A final grilled brief is an intake source, not a second contract. Owner-confirmed
`BD` items may seed decided T nodes, but contract-review still records how each
brief item was consumed, deferred, or rejected. Verified facts may seed E/P;
unverified facts and assumptions never become requirements merely because the
brief contains them. Do not repeat questions already confirmed in the bound
brief unless new evidence creates a conflict.

## Owner Queue

Persist pending T IDs in FIFO order and expose only one `presented_t_id` at a
time. The answer event references that ID. Do not batch unrelated trade-offs.

T progresses `pending -> decided -> applied`. To apply it, construct the
candidate contract with `decision_status: applied`, compute its final hash,
then atomically publish it and record the decision event. A decision is not
complete merely because a choice was discussed in chat.

## Control Boundaries

Always stop at an owner checkpoint for scope growth, a new requirement,
irreversible action, spend, privacy exposure, or a value trade-off. Present:

- the smallest decision that unblocks progress;
- concrete options and their effect on P/F/I/V/B;
- the recommendations of both contractor and reviewer;
- a pause or reduce-scope option.

Budget exhaustion is another checkpoint. The legal outcomes are add budget,
reduce scope, pause, or terminate. Never interpret silence as consent.

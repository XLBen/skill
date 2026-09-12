# Scenario 7: New grill after a frozen brief — PASS

Target: `targets/s7`

## Observed sequence

| Point | Observation | Evidence |
|---|---|---|
| Base brief final + frozen | `docs/brief.md` final/confirmed; engine brief-hash da4226d9…; consumed by goal card G-BRIEF via `source.type=brief` with full coverage (BS-01 → O-01 outcome; BF-01/BD-01 constraint; BN-01 non-goal) | `[brief] OK`, `[goal] OK` |
| Second grill on consumed brief (key point) | New draft created at versioned `docs/brief-v2.md` (draft, unconfirmed, frontier BQ-01); base `docs/brief.md` NOT edited in place | file sha256 058b4331… identical before/after v2 creation |
| Old binding survives (key point) | After v2 exists, G-BRIEF `goal` validation still passes (engine re-reads the old brief path/hash/coverage) | `[goal] OK` post-v2 |
| Draft schema enforcement (unplanned) | Engine rejected two malformed v2 drafts (empty summary; frontier question not persisted as a `question` item; wrong kind name) before the correct form validated — gate works | engine errors captured |

## Deviations

- The v2 draft is a persisted draft only (grill interview itself not executed:
  out of scenario scope; the registered observation was versioning + binding
  integrity).

Result: **PASS**

# PUA Upstream and Adaptation

## Source

- Repository: <https://github.com/tanweai/pua>
- Version inspected: `3.5.1`
- Commit inspected: `e6e6cd237ad17750d179674bff52f8184abea8fd`
- Author metadata: 探微安全实验室 (`tanweai`)
- Declared upstream license: MIT (`plugin.json`)

The upstream repository did not expose a standalone root `LICENSE` file at the inspected
commit. Its `plugin.json` declares MIT, and the upstream README identifies the project as
MIT-licensed. This repository keeps an MIT notice in `pua/LICENSE` and records this
adaptation rather than presenting it as an unmodified upstream package.

## Kept

- The three red lines: close the loop, fact-driven diagnosis, and exhaust applicable methods.
- The original PUA/PIP-style reminders, including “证据呢”“不要原地打转” and the
  3.25/3.75 passive-versus-proactive framing.
- Failure-pattern detection, method switching, the seven-point checklist and the iceberg rule.
- The principle that pressure is directed at agent task performance, not at the user.

## Adapted

- The target is a stage acceptance gate, not an always-on session hook or a public `/pua`
  command.
- Failure counts use this repository's actual experiment/signature/no-progress rules. The
  existing third-identical-failure circuit breaker remains authoritative.
- Each reminder is paired with an executable action, evidence reference and bounded scope.
- Owner decisions, engine gates, independent review and safety authorization remain external
  authorities. PUA cannot manufacture their approval.
- No upstream hooks, telemetry, feedback storage, global state, commands, model calls or
  automatic updates are bundled.

## Local contract

The local files are a maintained adaptation for this workflow. Changes to the upstream
content should be re-reviewed against the source commit and recorded here; do not claim that
this directory is a byte-for-byte copy or that upstream model evaluations certify this
workflow.

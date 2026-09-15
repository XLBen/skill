# Computer Use

User-interface acceptance capability for the existing `/build`, `/fix` and
`/resume` delivery loop. No new slash command. When an affected outcome
includes an interface journey (native app, OS dialog, web interaction), the
controller loads `computer-use`, executes the declared scenarios from the
user's seat, and records evidence in
`.opencode/mvp/<goal-slug>.ui-acceptance.json` (see
`references/ui-acceptance-protocol.md`); the independent reviewer checks that
evidence at the acceptance handoff, and `check.py ui-gate` enforces it before
`finish-goal` under the runtime policy. Browser-only journeys prefer
dedicated browser automation; missing backend blocks acceptance instead of
waiving it. `/plan` may identify prerequisites and design scenarios but must
not begin GUI execution.

## Selected Upstream

Adapted from [ILoveMyJay/computer-use-kit](https://github.com/ILoveMyJay/computer-use-kit),
specifically `skills/computer-use/SKILL.md`, inspected on 2026-09-08. The upstream
MIT notice is retained in `LICENSE`. This is a locally maintained adaptation,
not an unmodified upstream release or a claim of upstream runtime certification.

Kept: accessibility-first observation, one action followed by verification,
ambiguous-send retry safety, and one controller for a shared desktop.

Changed: discover actual tool schemas rather than hard-code target formats;
respect DPI/crop coordinate mappings; scope authorization to the existing goal;
keep GUI observations separate from engine evidence and owner acceptance.
No upstream install scripts, binaries or automatic updates are bundled.

## Enable Deliberately

The repository installer registers this skill alongside other live top-level
skills. It does **not** install/enable a desktop driver or change MCP permissions.
If another global `computer-use` skill is installed, resolve that duplicate
explicitly; do not rely on discovery order.

Suggested backend: [Cua Driver](https://github.com/trycua/cua/tree/main/libs/cua-driver).
Its documented MCP entry is `cua-driver mcp`; platform capabilities vary by
version, desktop session and permission mode. Follow its
[installation guide](https://cua.ai/docs/how-to-guides/driver/install), inspect
the chosen release/installer, and obtain approval before installing it. Do not
pipe an unreviewed remote script into a shell. This repository has not performed
a live desktop test of that backend.

After installation, confirm the executable path and version using its local
help. Merge the following **disabled example** into the intended OpenCode
configuration only after review; preserve existing settings. Replace the first
command argument with the verified absolute executable path if it is not on
OpenCode's PATH. The MCP key `desktop` supplies the permission-tool prefix.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "desktop": {
      "type": "local",
      "command": ["cua-driver", "mcp"],
      "enabled": false
    }
  },
  "permission": {
    "desktop_*": "ask"
  },
  "agent": {
    "general": { "permission": { "desktop_*": "deny" } },
    "explore": { "permission": { "desktop_*": "deny" } }
  }
}
```

Only set `enabled` to `true` after authorizing this backend and its desktop scope.
Apply the same denial to any other subagent used in your installation. Do not
replace a stricter deny rule with ask; inspect merged project/global permissions.
Skill instructions alone do not enforce isolation or sandbox the driver. Do not
enable unrestricted driver mode or a personal browser-profile grant by default.
Quit and restart OpenCode after configuration or skill changes.

## Readiness And Smoke Test

From the target project, `opencode mcp list` checks whether the server connects;
connection is not proof that UI control works. In a fresh session, request a
read-only observation of a named, non-sensitive test window. Confirm actual tool
names, target identity and the visible state; a list of tools alone is not proof.

For an authorized write smoke, use a disposable test window, enter `CU-SMOKE-42`,
and read back the exact text. Keep personal documents closed, do not save over an
existing file, and close only the owned test window. If permission, input or
observation fails, report the exact blocker rather than a successful setup.

In delivery work, for example: `/fix the export dialog in the local test app`.
The controller must first resolve the app and output path, then observe, act and
verify; it must not assume permission to operate any open desktop application.

## Acceptance Boundary

Interactive screenshots/MCP results are acceptance evidence recorded in the
UI acceptance sidecar; they are not a replacement for `verify-goal`,
`verify-step`, or actual owner acceptance. Under `runtime-policy/1`, run
`check.py ui-gate <goal-card> --trace <trace.json>` before `finish-goal`:
required scenarios must be `passed` (or reasoned `not-applicable`), the
executing session must show a completed `computer-use` load and native call
references in the trace, and the recorded artifact identity must match the
current bound files. Purely manual GUI goals still need a real verification
runner for the executable goal gate; report that limitation early rather
than promise automatic completion.

See `SKILL.md` for the full control, safety, recovery and evidence rules.

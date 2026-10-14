# Computer Use

Desktop-control skill for direct user requests (native apps, OS dialogs and
file pickers), plus UI acceptance during `/build`. Direct requests use the
short, window-scoped observe/act/verify loop in `SKILL.md`. When the brief has
acceptance examples that go through a GUI, the build controller runs them on the
delivered build and reports each as passed / failed / blocked. Browser-only
journeys prefer dedicated browser automation; a missing backend blocks
acceptance instead of waiving it. `/plan` may design the examples but must not
begin GUI execution.

Pointer journeys use the same scoped loop for hover, targeted scrolling,
drag-and-drop, marquee and additive/range selection. See `SKILL.md` for the
gesture and verification rules, and `references/cua-driver-fast-path.md` for
backend-specific overlay-versus-real-pointer and coordinate caveats. The skill
does not add mouse primitives that the active backend does not expose.
Qualify a new backend/version against `references/pointer-evaluation.md`
before claiming that a gesture or image-coordinate route works. A short
ordered action batch requires actual backend support for per-step receipts and
stop-on-failure; consecutive MCP calls are not such a batch.

## Selected Upstream

Adapted from [ILoveMyJay/computer-use-kit](https://github.com/ILoveMyJay/computer-use-kit),
specifically `skills/computer-use/SKILL.md`, inspected on 2026-09-08. The upstream
MIT notice is retained in `LICENSE`. This is a locally maintained adaptation,
not an unmodified upstream release or a claim of upstream runtime certification.
No upstream commit was pinned for that inspection; compare with the actual
installed backend/version before claiming tool or state-ID behavior matches.

Kept: accessibility-first observation, one action followed by verification,
ambiguous-send retry safety, and one controller for a shared desktop.

Changed: discover actual tool schemas rather than hard-code target formats;
respect DPI/crop coordinate mappings; scope authorization to the current task;
keep GUI observations separate from engine evidence and owner acceptance.
Upstream's one-action/one-verification loop and unknown-send readback still
apply, with state-ID validity resolved from the live backend rather than guessed.
No upstream install scripts, binaries or automatic updates are bundled. The
optional `references/cua-driver-fast-path.md` is a backend-specific recipe:
it follows the installed tool schema (snapshot-bound targets and conditional
image capture), not an assumed universal desktop API.

## Enable Deliberately

The repository installer registers this skill alongside other live top-level
skills. It does **not** install/enable a desktop driver or change MCP permissions.
If another global `computer-use` skill is installed, resolve that duplicate
explicitly; do not rely on discovery order.
If you use this repository directly without running its installer, register
`<absolute-path-to-repo>/computer-use` under `skills.paths` in your OpenCode
config. `opencode debug skill` must list `computer-use`; having an MCP server
alone does not cause the skill to load.

Suggested backend: [Cua Driver](https://github.com/trycua/cua/tree/main/libs/cua-driver).
Its documented MCP entry is `cua-driver mcp`; platform capabilities vary by
version, desktop session and permission mode. Follow its
[installation guide](https://cua.ai/docs/how-to-guides/driver/install), inspect
the chosen release/installer, and obtain approval before installing it. Do not
pipe an unreviewed remote script into a shell. This repository does not claim
repeatable cross-platform gesture qualification of that backend; see
`references/pointer-evaluation.md` for the required cases.

After installation, confirm the executable path and version using its local
help. `cua-driver mcp-config --client opencode` prints a current registration
example (escape backslashes in JSON on Windows). Merge the following
**disabled example** into the intended OpenCode configuration only after
review; preserve existing settings. Replace the first command argument with
the verified absolute executable path if it is not on OpenCode's PATH. The
MCP key `desktop` supplies the permission-tool prefix. Default-deny the
desktop tools and allow only the primary `build` agent to request them; this
also covers newly added subagents by default.

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
    "desktop_*": "deny"
  },
  "agent": {
    "build": { "permission": { "desktop_*": "ask" } }
  }
}
```

Only set `enabled` to `true` after authorizing this backend and its desktop scope.
Check the *resolved* permissions of `build` and any custom agent: file-defined
per-agent permissions or project config can override the global default. A
subagent that actually needs UI must have an explicitly reviewed separate grant
and lease. Skill instructions and tool-name permissions are not an OS sandbox;
if shell commands are allowed, deny direct `cua-driver` CLI commands in the
global **and** any overriding per-agent `bash` rules so CLI input cannot
casually bypass MCP's `ask` rule. Other drivers need their own permission
boundaries. Do not enable unrestricted driver mode or a personal
browser-profile grant by default.
Quit and restart OpenCode after configuration or skill changes.

## Readiness And Smoke Test

From the target project, `opencode mcp list` checks whether the server connects;
connection is not proof that UI control works. In a fresh session, request a
read-only observation of a named, non-sensitive test window. Confirm actual tool
names, target identity and the visible state; a list of tools alone is not proof.
If the tool isn't available in an old OpenCode session, restart instead of
falling back to shell-driven clicks. Prefer a tree-only snapshot when the named
control suffices, a window screenshot only when pixels/appearance matter,
and a bounded semantic result assertion or fresh window state after acting.

For an authorized write smoke, use a disposable test window, enter `CU-SMOKE-42`,
and read back the exact text. Keep personal documents closed, do not save over an
existing file, and close only the owned test window. If permission, input or
observation fails, report the exact blocker rather than a successful setup.
That text-field smoke does not qualify pixel geometry, hover, drag or selection;
run the relevant pointer-evaluation cases with observable result state before
claiming those capabilities.

The sample tool permission above limits **tool names**, not app identities.
The controller must pin each approved app/window in its actions, but an
enforceable per-app allowlist, user-takeover detection and input cancellation
require host/driver support. Do not advertise these as protections supplied by
the skill alone. Foreground input on a shared Windows desktop may take focus
and the real pointer; pause when the user needs the desktop.

In delivery work, for example: `Fix the export dialog in the local test app`.
The controller must first resolve the app and output path, then observe, act and
verify; it must not assume permission to operate any open desktop application.

## Acceptance Boundary

Interactive screenshots/MCP results are evidence of what was observed; they are
not a replacement for automated tests or the user's own acceptance. Purely
manual GUI checks should be reported as such rather than promised as automatic.

See `SKILL.md` for the full control, safety, recovery and evidence rules.

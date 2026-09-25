# Cua Driver: Precise, Short Native Loop

> Read only when the selected desktop backend is Cua Driver. This is an
> OpenCode/MCP recipe, not a replacement for the installed driver's schemas.
> The examples were checked against local Windows Cua Driver 0.28.1 and its
> published [agent action policy](https://cua.ai/docs/reference/cua-driver/action-selection-policy).
> On another version/platform, use the live tool descriptions. Never generate
> a PID, HWND, element token, `snapshot_id`, pixel or menu path from examples.

## One-time discovery (not on every action)

1. Confirm the desktop MCP is registered and the **current session** exposes
   its tools. The binary merely being on PATH is not enough; if OpenCode has
   no desktop MCP, do not replace a refused/missing MCP action with CLI input.
2. Resolve `list_apps` -> exact process. If requested to launch, `launch_app`
   may return both PID and windows; use them rather than listing twice. On
   cold launch with no window yet, wait for bounded `list_windows(pid)` results,
   not a second launch. Choose the intended `window_id` by title/owner/bounds;
   ask on ambiguity. Use the same `(pid, window_id)` for each read/write.
3. Discover needed tool schemas once: `get_window_state`, `click`,
   `type_text`, `verify_state`, and `invoke_menu` only if needed. The installed
   schema, not the documentation's example version, controls valid fields.
   Keep one session label if the backend asks for it; it is not input scope.

## Default rung: one snapshot, semantic action

- When the control is named and no visual judgment is needed, request
  `get_window_state` for `(pid, window_id)` with `query` (if available) and
  `include_screenshot:false` (if available). This skips image capture and
  reduces tree output. Read `structuredContent.elements`: role, label, parent,
  enabled state, advertised actions and value. `query` is a projection, not
  proof of absence; on zero/ambiguous/truncated matches broaden this **one**
  observation, not a guessed click.
- Choose a unique enabled control whose action fits the task. Use its opaque
  `element_token` for `click`/`type_text` when advertised. An integer
  `element_index` needs the **same response's** `snapshot_id` and the exact
  window. A new snapshot can invalidate the token; never cache it across
  observations, navigation or a dependent action. Directly target text input
  rather than clicking a field and sending one key at a time. Inspect whether
  `type_text` inserts versus replaces before editing an existing value.
- For a known exact native menu path, an advertised `invoke_menu` can resolve
  the live menu and refuse missing/ambiguous items, avoiding exploratory
  pixel clicks. Do not invent paths from a translated app name.
- Inspect the receipt's `effect`, `route` and refusal/escalation fields when
  available. `confirmed` is evidence of that **action**'s readback, not proof
  of the user's final outcome. For a predicate supported by `verify_state`,
  supply `(pid, window_id)` and a specific `expect`, with a short bounded
  timeout and no screenshot if visual proof is unnecessary; only `satisfied`
  means the expected state appeared. Otherwise read a fresh window state, or
  the saved output if the task requires one. The
  verification state can be the next step's fresh observation; don't request
  an identical extra snapshot for ceremony.

## Fallback rung: pixels only from a valid image

- If no actionable semantic target exists, capture the **same window** with
  `get_window_state` including screenshot and actually inspect the image.
  On a known canvas with no useful accessibility tree, skip the expensive
  tree walk with `include_accessibility_tree:false` if the live schema offers
  it (but leave screenshot enabled).
  A tree-only response, a file path not opened as an image, a missing image, or
  a screenshot from another window does **not** ground a coordinate.
- Windows window actions use the screenshot's **window-local** `(x,y)`, not
  screen coordinates. Do not add the window's desktop origin. If OpenCode
  displays a resized preview, use returned raw dimensions and a known scale
  for both axes; if that mapping is unknown, do not click. For small targets,
  use full-resolution capture or the advertised `zoom` + `from_zoom` mapping
  on the same window/session. An advertised `capture_id` can bind pixels to
  their source and refuse stale clicks; use it where supported.
- Keep default background delivery for an exact-window action. On Windows,
  UIA hit-testing may turn a pixel into an accessibility action; a fallthrough
  to synthetic events is **not** proof the app accepted it. Reobserve the
  result. Use desktop-wide capture/input only for an authorized task that
  truly spans windows and after identifying the intended visible target.

## Recovery without repeated wrong clicks

| Signal | Next move |
|---|---|
| stale token / window owner changed | Resolve window and take one fresh snapshot; select a new target. |
| sparse/truncated tree | Broaden query or bounds once; if no UIA peer, use a fresh valid image. |
| `unverifiable`, suspected no-op, timeout or lost receipt | Read state before retry: it may already have landed. Never replay submit/export blindly. |
| `background_unavailable` | Reobserve, then use foreground **for that action only** if visible control was explicitly authorized; otherwise stop. A refusal never licenses desktop-wide input. |
| expected outcome satisfied | Stop. No fixed sleep, second screenshot or extra action. |

The action-selection notes in the [driver docs](https://cua.ai/docs/reference/cua-driver/action-selection-policy)
explain its version-dependent ladder. No route, including `verify_state`,
proves an outcome that its predicates cannot express; inspect the actual UI or
artifact in that case.

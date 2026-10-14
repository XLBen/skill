# Pointer And Visual-Input Qualification

> Use when qualifying a new desktop backend/version, after changing pointer
> guidance, or when a task exposes a repeatable geometry/input failure. This
> is a manual acceptance protocol, not a claim that any platform passed it.
> Use an owned disposable test window, not a user's unsaved document or game.

## Record The Test Environment

Record backend and version, platform/display scale, screenshot dimensions,
exact `(pid, window_id)`, window bounds, input route and whether the app was
foreground. Capture only the minimum evidence needed to judge the result.
Do not change screen resolution, permissions or app settings merely to make a
test pass. Stop on permission refusal or user takeover.

For each case record: observed target and its screenshot/element reference;
action arguments and native receipt; expected result; independent readback;
elapsed time and count of tool calls; `passed`, `failed` or `blocked` with the
specific missing capability. `sent` and `unverifiable` are never `passed` by
themselves. Run a failed case from fresh state at most once for diagnosis,
subject to the active task budget. Do not publish raw screenshots or private
window titles.

## Cases

| Case | Disposable setup and action | Passing observation |
|---|---|---|
| Semantic baseline | Invoke an accessible control; edit a separate accessible field. | Exact target changes; other fields unchanged, with no focus steal if the route promises background input. |
| Small visual target | Use a known 20–30 px custom-drawn button in an owned canvas; take a native-resolution window capture, act once. | Intended button changes state, adjacent button does not; target and input share one documented coordinate frame. |
| Crop/scale/zoom | Repeat that target with a resized preview and a padded/zoomed crop (if supported). Record actual returned image size and backend context. | The same target changes; an unknown crop-to-input mapping is refused or reported `blocked`, never guessed. |
| Hover and edge dwell | Move the **real** pointer to a known hover control, then (separately) an edge-scroll area and dwell for a bounded interval. | Hover/viewport visibly changes in the expected direction; overlay-only movement is classified `blocked`, not passed. |
| Targeted wheel | Scroll over one of two independent nested scroll regions. | Only the intended region moves; focus/page-scroll no-ops are not counted as success. |
| Straight drag | Drag a slider or canvas object using a single press-move-release gesture. | Value/object moves to the intended region, pointer button is released, and the next input is not interpreted as a continuation. |
| Marquee and additive selection | Box-select a known set of items from empty space; reset, then modifier-select the same items one by one. | Exact selected identities and count match; adjacent items stay unselected. |
| Gesture boundary | Request a freehand/multi-point path, held-drag edge autoscroll or cross-window transfer. | Run only if the **live** backend advertises that gesture and scope; otherwise return a capability blocker without substituting blind clicks or a broken hold-across-calls sequence. |
| No-op and refusal | In a disposable state, observe a background pixel no-op/refusal or a deliberately stale target. | No unsafe retry or app switch; fresh observation precedes any permitted foreground escalation. |
| Focus and cancellation | Pause/take over during a foreground gesture (only in an owned test environment). | Further input stops, held buttons/keys are released by the backend or uncertainty is reported; unrelated window receives no input. |
| OS dialog ownership | Open a disposable native file picker from the test app. | Dialog owner/window is reacquired; stale app refs and screenshot coordinates are not reused. |
| Held input and clipboard | In an owned test environment, exercise an advertised bounded hold and an optional paste using nonsensitive disposable text. | Held input is released on completion/error, paste is read back, and any clipboard restoration is verified rather than assumed. Unsupported primitives are reported `blocked`. |

Use a known reversible UI with a visible state readout for pointer cases; do
not use a tooltip alone to prove a click or selection. A browser canvas fixture
may test raw pointer routing, but DOM mutation or direct page scripting is not
evidence that the desktop input path worked. Where an app has no independent
readout for selection identities, mark that claim `unknown` rather than pass.

## Decision And Regression Report

Summarize by **capability and route**, not by app name: semantic/background,
window pixels/background, window pixels/foreground, real hover, nested wheel,
straight drag, modifiers, multi-point/held gesture and cross-window scope.
Keep route-specific latency and call counts alongside pass/fail; compare the
same disposable scenarios before/after a change. A faster run that clicked the
wrong control or skipped verification is a failure, not a performance gain.

This protocol cannot add missing primitives or impose OS-level app allowlists.
If the live tool lacks real pointer movement, held mouse input or a reliable
capture transform, record the backend/host work separately; a skill-only edit
must not be reported as an end-to-end fix.

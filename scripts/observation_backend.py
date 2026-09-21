#!/usr/bin/env python3
"""Observation backend planning and batched journey execution (S15).

The observer must spend as few model turns as possible, so one dispatch is a
short journey batch: several CLI steps executed back to back whose
intermediate evidence is retained even when a later step fails. This module
supplies the controller-side primitives for that contract:

- ``preflight_skip_plan`` decides per probe item whether a passed packet
  preflight may skip a repeated probe. It never trusts the word
  "controller-verified": the caller context must carry the recorded identity
  and match it, otherwise the probe runs again (fail closed).
- ``choose_backend`` resolves the browser backend from the preflight. A
  backend is adopted as verified only when the host cover passed and agrees
  with the preference; it never invents a backend or silently substitutes one.
- ``agent_browser_argv`` / ``playwright_cli_argv`` build argv arrays. Every
  value stays a separate element: there is no shell string to escape and no
  implementer-authored route is embedded.
- ``run_step_sequence`` runs a batch through an injected runner and stops at
  the first failure, timeout or exception, handing the remaining steps and the
  runner's raw result back to the caller instead of guessing a recovery route.

This module deliberately has no browser dependency: it only builds argv and
calls the injected runner (production wiring uses
``observation_process.run_process``). Nothing here starts a browser, spawns a
process by itself, or reads the product.

Public API::

    preflight_skip_plan(preflight, context) -> dict
    choose_backend(preflight, preferred=None) -> dict
    agent_browser_argv(session_id, action, **params) -> list
    playwright_cli_argv(session_id, action, **params) -> list
    run_step_sequence(steps, runner, *, deadline_seconds=None, clock=None) -> dict
"""

import time
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

BACKENDS = ("agent-browser", "playwright-cli")

_SKIP_ITEMS = ("host", "model", "candidate", "session")

_ITEM_FIELDS = {
    "host": (
        ("host_id", ("host_id", "host")),
        ("provider_id", ("provider_id",)),
        ("model_id", ("model_id",)),
    ),
    "model": (
        ("provider_id", ("provider_id",)),
        ("model_id", ("model_id",)),
    ),
    "candidate": (("candidate_id", ("candidate_id",)),),
    "session": (("session_id", ("session_id",)),),
}

_AGENT_ACTIONS = (
    "open",
    "goto",
    "snapshot",
    "screenshot",
    "console",
    "errors",
    "click",
    "type",
    "press",
    "wait",
    "close",
)

_PLAYWRIGHT_ACTIONS = (
    "open",
    "goto",
    "snapshot",
    "screenshot",
    "console",
    "click",
    "type",
    "press",
    "wait",
    "close",
)

_WAIT_KEYS = ("load", "url", "text", "fn")


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _plan_item(item: str, covers: Any, context: Any) -> dict:
    if not isinstance(covers, dict):
        return {"skip": False, "reason": "preflight covers is not an object"}
    cover = covers.get(item)
    if not isinstance(cover, dict):
        return {"skip": False, "reason": f"preflight covers.{item} is not an object"}
    status = cover.get("status")
    if status != "passed":
        return {
            "skip": False,
            "reason": f"preflight covers.{item} status is not passed: {status!r}",
        }
    if not isinstance(context, dict):
        return {"skip": False, "reason": "context missing or not an object"}

    comparable = 0
    for context_key, cover_keys in _ITEM_FIELDS[item]:
        present = [(key, cover[key]) for key in cover_keys if key in cover]
        if not present:
            continue
        value = context.get(context_key)
        if not isinstance(value, str) or not value.strip():
            return {"skip": False, "reason": f"context {context_key} missing"}
        for key, recorded in present:
            if recorded != value:
                return {
                    "skip": False,
                    "reason": (
                        f"context {context_key} does not match "
                        f"preflight covers.{item}.{key}"
                    ),
                }
        comparable += 1
    if comparable == 0:
        return {
            "skip": False,
            "reason": f"preflight covers.{item} has no comparable identity fields",
        }
    return {"skip": True, "reason": f"preflight covers.{item} matches context"}


def preflight_skip_plan(preflight: Any, context: Any) -> dict:
    """Decide whether each probe item may be skipped because of the preflight.

    ``preflight`` is a validated packet preflight (or None); ``context`` is
    ``{"host_id", "provider_id", "model_id", "candidate_id", "session_id"}``,
    with missing values meaning "unknown". A cover only skips its probe when
    its status is exactly ``passed`` and every identity field it records is
    present and equal in the context. Otherwise the probe must run again:
    missing preflight, missing context, missing identity fields, mismatched
    values and malformed covers all fail closed.
    """
    if not isinstance(preflight, dict):
        return {item: {"skip": False, "reason": "no preflight"} for item in _SKIP_ITEMS}
    covers = preflight.get("covers")
    return {item: _plan_item(item, covers, context) for item in _SKIP_ITEMS}


def _host_cover(preflight: Any) -> Any:
    if not isinstance(preflight, dict):
        return None
    covers = preflight.get("covers")
    if not isinstance(covers, dict):
        return None
    return covers.get("host")


def choose_backend(preflight: Any, preferred: Optional[str] = None) -> dict:
    """Resolve the browser backend without inventing one.

    A preference is adopted (``verified: True``) only when the host cover
    passed and either records no backend or records the preferred one. An
    unsupported preference, an explicitly unavailable host, or a host cover
    that contradicts the preference returns ``backend: None`` and no fallback.
    With no preflight (or no passed host cover) the default unverified
    backend is ``agent-browser``.
    """
    if preferred is not None and preferred not in BACKENDS:
        return {"backend": None, "reason": f"unsupported preferred backend: {preferred!r}"}

    host = _host_cover(preflight)
    status = host.get("status") if isinstance(host, dict) else None
    recorded = host.get("backend") if isinstance(host, dict) else None

    if status == "unavailable":
        return {"backend": None, "reason": "preflight reports the host backend unavailable"}

    if preferred is not None and status == "passed":
        if recorded is not None and recorded != preferred:
            return {
                "backend": None,
                "reason": (
                    f"preflight host backend {recorded!r} does not match "
                    f"preferred {preferred!r}"
                ),
            }
        return {
            "backend": preferred,
            "verified": True,
            "reason": "preferred backend verified by preflight",
        }

    if preferred is None and status == "passed" and recorded in BACKENDS:
        return {
            "backend": recorded,
            "verified": True,
            "reason": "backend selected from passed preflight",
        }

    return {
        "backend": "agent-browser",
        "verified": False,
        "reason": "default, unverified preflight",
    }


def _build_argv(
    base: Sequence[str], action: Any, params: dict,
    actions: Sequence[str],
) -> list:
    if not isinstance(action, str) or action not in actions:
        raise ValueError(f"unsupported action: {action!r}")
    remaining = dict(params)
    extras = []

    if action in ("snapshot", "screenshot"):
        filename = remaining.pop("filename", None)
        evidence_dir = remaining.pop("evidence_dir", None)
        if filename is None:
            if action == "screenshot":
                raise ValueError("screenshot requires filename")
            if evidence_dir is not None:
                raise ValueError("evidence_dir is only used together with filename")
        else:
            filename = _nonempty(filename, "filename")
            evidence_dir = _nonempty(evidence_dir, "evidence_dir")
            root = Path(evidence_dir).resolve()
            target = Path(filename).resolve()
            if not target.is_relative_to(root):
                raise ValueError(f"filename escapes evidence_dir: {filename}")
            extras.extend(["--filename", filename])

    if action in ("open", "goto"):
        extras.append(_nonempty(remaining.pop("url", None), "url"))
    elif action == "click":
        extras.append(_nonempty(remaining.pop("target", None), "target"))
    elif action == "type":
        extras.append(_nonempty(remaining.pop("target", None), "target"))
        extras.append(_nonempty(remaining.pop("text", None), "text"))
    elif action == "press":
        extras.append(_nonempty(remaining.pop("key", None), "key"))
    elif action == "wait":
        chosen = [(key, remaining.pop(key)) for key in _WAIT_KEYS if key in remaining]
        if len(chosen) != 1:
            raise ValueError("wait requires exactly one of: load, url, text, fn")
        key, value = chosen[0]
        extras.extend([f"--{key}", _nonempty(value, f"wait {key}")])

    if remaining:
        names = ", ".join(sorted(remaining))
        raise ValueError(f"unsupported parameter(s) for {action}: {names}")
    return list(base) + [action] + extras


def agent_browser_argv(session_id: Any, action: Any, **params: Any) -> list:
    """Build an ``agent-browser`` argv array (never a shell string).

    Supported actions: open, goto, snapshot, screenshot, console, errors,
    click, type, press, wait, close. ``screenshot`` requires ``filename`` and
    ``snapshot`` accepts one; the file must resolve inside ``evidence_dir``.
    Every non-empty value becomes exactly one argv element.
    """
    _nonempty(session_id, "session_id")
    base = ["agent-browser", "--session", session_id]
    return _build_argv(base, action, params, _AGENT_ACTIONS)


def playwright_cli_argv(session_id: Any, action: Any, **params: Any) -> list:
    """Build a ``playwright-cli`` argv array (same parameters as agent-browser)."""
    _nonempty(session_id, "session_id")
    base = ["playwright-cli", "-s=" + session_id]
    return _build_argv(base, action, params, _PLAYWRIGHT_ACTIONS)


def _result_ok(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("error"):
        return False
    if result.get("timed_out"):
        return False
    return result.get("exit_code") == 0


def _run_one(runner: Callable[[Sequence[str], Optional[float]], Any],
             argv: Sequence[str], timeout: Optional[float]) -> Any:
    try:
        result = runner(list(argv), timeout)
    except Exception as exc:  # boundary guarantee: a bad runner never crashes the batch
        return {
            "exit_code": None,
            "timed_out": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    if isinstance(result, dict):
        return result
    return {
        "exit_code": None,
        "timed_out": False,
        "error": "runner returned a non-dict result",
        "value": result,
    }


def _normalize_steps(steps: Any) -> list:
    if not isinstance(steps, (list, tuple)):
        raise ValueError("steps must be a list")
    normalized = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"steps[{index}] must be an object")
        step_id = step.get("id")
        if not isinstance(step_id, str) or not step_id.strip():
            raise ValueError(f"steps[{index}].id must be a non-empty string")
        argv = step.get("argv")
        if (
            not isinstance(argv, (list, tuple))
            or not argv
            or any(not isinstance(part, str) or not part for part in argv)
        ):
            raise ValueError(f"steps[{index}].argv must be a non-empty list of strings")
        evidence = step.get("evidence")
        if evidence is not None and (
            not isinstance(evidence, str) or not evidence.strip()
        ):
            raise ValueError(
                f"steps[{index}].evidence must be a non-empty string or null"
            )
        timeout = step.get("timeout")
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or timeout <= 0
        ):
            raise ValueError(
                f"steps[{index}].timeout must be a positive number or null"
            )
        normalized.append(
            {"id": step_id, "argv": list(argv), "evidence": evidence, "timeout": timeout}
        )
    return normalized


def run_step_sequence(
    steps: Any,
    runner: Callable[[Sequence[str], Optional[float]], Any],
    *,
    deadline_seconds: Optional[float] = None,
    clock: Optional[Callable[[], float]] = None,
) -> dict:
    """Execute a batch of CLI steps through ``runner`` and stop at the first problem.

    ``runner(argv, timeout)`` is injected (production uses
    ``observation_process.run_process``); its result is stored verbatim on the
    step so captured bytes/text are never swallowed. A step is successful only
    when the result has ``exit_code == 0`` with no ``timed_out``/``error``. The
    first failure, timeout or raised exception ends the batch immediately and
    unknown steps are returned in ``remaining``. ``deadline_seconds`` is
    checked with ``clock()`` (default ``time.monotonic``) before each step;
    once elapsed time reaches the deadline the batch stops with
    ``status="budget-exhausted"`` and the unexecuted steps are preserved.
    """
    if not callable(runner):
        raise ValueError("runner must be callable")
    if clock is None:
        clock = time.monotonic
    normalized = _normalize_steps(steps)

    started = clock()
    records = []
    remaining = [step["id"] for step in normalized]
    evidence_refs = []
    failed_step = None
    first_action_at = None
    status = "completed"
    completed = 0

    for step in normalized:
        now = clock()
        if deadline_seconds is not None and (now - started) >= deadline_seconds:
            status = "budget-exhausted"
            break
        if first_action_at is None:
            first_action_at = now
        result = _run_one(runner, step["argv"], step["timeout"])
        records.append(
            {
                "id": step["id"],
                "argv": step["argv"],
                "result": result,
                "evidence": step["evidence"],
            }
        )
        remaining.pop(0)
        if step["evidence"] is not None:
            evidence_refs.append(step["evidence"])
        if not _result_ok(result):
            status = "failed"
            failed_step = step["id"]
            break
        completed += 1

    elapsed = round(clock() - started, 6)
    return {
        "status": status,
        "steps": records,
        "completed": completed,
        "failed_step": failed_step,
        "remaining": remaining,
        "elapsed_seconds": elapsed,
        "first_action_at": first_action_at,
        "evidence_refs": evidence_refs,
    }

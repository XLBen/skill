# -*- coding: utf-8 -*-
"""S20B: pure-function core for the product-observation calibration driver.

This module deliberately contains no live-model dispatch, no subprocess calls,
no repository state and no file fallbacks. The calibration run book
(``validation/observation-calibration/README.md``) builds on these functions,
and every failure mode fixed here is a regression the old sandbox driver had:

* dual-channel adoption (stdout plus agent-written ``*.result.json``)
* ``sessions[-1]`` provenance binding
* a default ``stop_reason: coverage-completed``
* reviewer-side mirror condition branches
* fixture-generated "controls" and pre-flight pollution
* server start before setup

Only the Python 3.10 standard library is used. Functions either return a list
of problems (never raising for malformed input) or raise ``ValueError`` for
caller mistakes that cannot produce a meaningful result.
"""

import os
import re
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

_OPEN_RE = re.compile(r"^---[ \t]*\r?\n")
_MODE_RE = re.compile(r"^([ \t]*mode:[ \t]*)([A-Za-z0-9_-]+)([ \t\r]*)$", re.MULTILINE)
_CLOSE_RE = re.compile(r"^---[ \t]*$", re.MULTILINE)

_SINGLE_CHANNEL_PATTERNS = (
    re.compile(r"only\s+as\s+the\s+closing\s+(?:```json\s+)?(?:json\s+)?block", re.IGNORECASE),
    re.compile(r"closing\s+```json\s+block", re.IGNORECASE),
    re.compile(r"one\s+fenced\s+(?:```)?json", re.IGNORECASE),
    re.compile(r"一个\s*json\s*围栏块"),
    re.compile(r"单一\s*json\s*围栏块"),
)

_SEED_KEY_MARKERS = ("seed", "defect", "expected_findings")

_WRITE_HINT_RE = re.compile(
    r"(write|save|create|output|export|store|dump|写入|保存|输出|落盘)"
    r"[^\n]{0,120}?result\.json",
    re.IGNORECASE,
)
_NEGATIONS = ("not", "never", "no", "don't", "do not", "禁止", "不要", "不得", "勿")


def make_primary_mirror(agent_text: str) -> str:
    """Return ``agent_text`` with its frontmatter ``mode`` flipped to primary.

    Only the mode value token changes; every other byte (including line
    endings) is preserved. An already-primary mirror is returned unchanged.
    Missing frontmatter, an unterminated block, a missing ``mode`` key or an
    unknown mode value raise ``ValueError``: a calibration mirror is never
    guessed.
    """

    if not isinstance(agent_text, str):
        raise ValueError(f"agent text must be a string, got {type(agent_text).__name__}")
    opening = _OPEN_RE.match(agent_text)
    if opening is None:
        raise ValueError("agent text has no frontmatter block")

    body = agent_text[opening.end():]
    closing = _CLOSE_RE.search(body)
    if closing is None:
        raise ValueError("agent frontmatter is not terminated by ---")

    front_start = opening.end()
    front_end = front_start + closing.start()
    front = agent_text[front_start:front_end]

    mode = _MODE_RE.search(front)
    if mode is None:
        raise ValueError("agent frontmatter has no mode key")

    value = mode.group(2)
    if value == "primary":
        return agent_text
    if value != "subagent":
        raise ValueError(
            f"agent frontmatter mode must be subagent or primary, got {value!r}"
        )

    new_front = front[:mode.start()] + mode.group(1) + "primary" + mode.group(3) + front[mode.end():]
    return agent_text[:front_start] + new_front + agent_text[front_end:]


def assert_single_channel(agent_text: Any) -> list:
    """Check a dispatcher/agent text declares single-channel delivery.

    The calibration controller accepts exactly one fenced ``json`` block from
    the final reply and never an agent-written file. If the text carries no
    statement of that contract (any of "only as the closing ```json block",
    "one fenced json", "一个 json 围栏块", ...) the dispatch is rejected
    before any model call.
    """

    problems: list = []
    if not isinstance(agent_text, str) or not agent_text.strip():
        return ["agent text must be a non-empty string"]
    if not any(pattern.search(agent_text) for pattern in _SINGLE_CHANNEL_PATTERNS):
        problems.append(
            "agent instructions do not declare single-channel delivery "
            "(exactly one fenced ```json block, nothing after it)"
        )
    return problems


def _all_strings(value: Any) -> list:
    strings: list = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            strings.extend(_all_strings(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            strings.extend(_all_strings(item))
    return strings


def _seed_strings(value: Any) -> list:
    strings: list = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) and any(
                marker in key.lower() for marker in _SEED_KEY_MARKERS
            ):
                strings.extend(_all_strings(item))
            else:
                strings.extend(_seed_strings(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            strings.extend(_seed_strings(item))
    return strings


def _packet_strings(value: Any, path: str = "$") -> Iterable:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _packet_strings(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _packet_strings(item, f"{path}[{index}]")


def seed_redaction_problems(seed_config: dict, packet: dict) -> list:
    """Report seed-case text that leaked into the observer packet.

    Seed values live under keys whose names contain ``seed``/``defect``/
    ``expected_findings``. Every string value of the packet is scanned
    recursively (case-insensitively); each hit names the packet location.
    """

    problems: list = []
    if not isinstance(seed_config, dict):
        return ["seed config must be a JSON object"]
    if not isinstance(packet, dict):
        return ["packet must be a JSON object"]

    seeds = []
    for candidate in _seed_strings(seed_config):
        text = candidate.strip()
        if text and text not in seeds:
            seeds.append(text)

    folded = [(seed, seed.casefold()) for seed in seeds]
    for path, value in _packet_strings(packet):
        haystack = value.casefold()
        for seed, needle in folded:
            if needle in haystack:
                problems.append(f"seed text leaked into packet at {path}: {seed!r}")
    return problems


def packet_guard(packet_ok: bool) -> dict:
    """Gate dispatch on successful phase packet generation.

    ``False`` aborts with the frozen reason; ``True`` permits dispatch.
    There is no partial-success state: a packet that failed preflight or
    validation must never be handed to a model.
    """

    if packet_ok:
        return {"abort": False}
    return {
        "abort": True,
        "reason": "phase packet generation failed; do not dispatch",
    }


def state_reset(paths: Any) -> dict:
    """Delete calibration state files, reporting every outcome.

    Existing files are removed, absent ones are listed under ``missing``, and
    directories or deletion failures are reported under ``problems`` without
    raising. Input may be a single path or an iterable of paths.
    """

    removed: list = []
    missing: list = []
    problems: list = []

    if isinstance(paths, (str, os.PathLike)):
        items = [paths]
    else:
        try:
            items = list(paths)
        except TypeError:
            return {
                "removed": removed,
                "missing": missing,
                "problems": ["paths must be a path or an iterable of paths"],
            }

    for raw in items:
        try:
            target = Path(raw)
        except TypeError:
            problems.append(f"invalid path value: {raw!r}")
            continue
        try:
            if not target.exists():
                missing.append(str(target))
                continue
            if target.is_dir():
                problems.append(f"refusing to delete directory: {target}")
                continue
            target.unlink()
            removed.append(str(target))
        except OSError as exc:
            problems.append(f"failed to delete {target}: {exc}")
    return {"removed": removed, "missing": missing, "problems": problems}


def server_order_plan(steps: Sequence) -> list:
    """Normalize the calibration step order and enforce setup-before-server.

    ``setup`` must appear and precede ``server-start`` whenever a server is
    started; otherwise ``ValueError``. Remaining steps keep their relative
    order. Returned names are stripped of surrounding whitespace.
    """

    if isinstance(steps, str):
        raise ValueError("steps must be a sequence of step names, not a string")
    try:
        items = [str(step).strip() for step in steps]
    except TypeError as exc:
        raise ValueError(f"steps must be a sequence of step names: {exc}") from exc
    if not items:
        raise ValueError("steps must not be empty")
    if any(not item for item in items):
        raise ValueError("step names must be non-empty")

    keys = [item.lower() for item in items]
    if "server-start" in keys:
        if "setup" not in keys:
            raise ValueError("setup is required before server-start")
        if keys.index("setup") > keys.index("server-start"):
            raise ValueError("setup must appear before server-start")
    return items


def adoption_result(
    payload: Any,
    envelope: Any,
    trace: Any,
    cdir: Any,
    project_root: Any,
    phase: str,
    **kw: Any,
) -> Any:
    """Thin pass-through to ``observation_results.adopt_result``.

    Arguments are forwarded unchanged (the module's ``(cdir, project_root,
    phase, payload, envelope, trace)`` order is restored here). The import is
    lazy so this module stays importable without the engine on the path. No
    default envelope fields, no default stop reason and no file fallback are
    ever applied: whatever the adoption gate rejects stays rejected.
    """

    import observation_results

    return observation_results.adopt_result(
        cdir, project_root, phase, payload, envelope, trace, **kw
    )


def _negated(prefix: str) -> bool:
    window = prefix[-40:].casefold()
    return any(token in window for token in _NEGATIONS)


def result_source_is_single(text: Any) -> list:
    """Validate that a reply is a single fenced JSON block, no file channel.

    Parsing is delegated to ``observation_results.parse_single_payload`` (zero
    or multiple blocks, trailing prose and non-object payloads are problems).
    In addition, any declaration that asks the model to *write*
    ``result.json``/``*.result.json`` is reported: the controller archives the
    one fenced block itself and the agent never owns a result file.
    """

    problems: list = []
    if not isinstance(text, str):
        return ["reply must be a string"]

    try:
        import observation_results
    except ImportError as exc:
        return [f"observation_results module unavailable: {exc}"]

    _, parse_problems = observation_results.parse_single_payload(text)
    problems.extend(parse_problems)

    reported = []
    for match in _WRITE_HINT_RE.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.start())
        line = text[line_start:line_end if line_end != -1 else len(text)]
        prefix = text[line_start:match.start()]
        if _negated(prefix):
            continue
        if line not in reported:
            reported.append(line)
            problems.append(
                f"dual-channel write declaration detected: {line.strip()!r}"
            )
    return problems

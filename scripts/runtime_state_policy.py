#!/usr/bin/env python3
"""Runtime-state policy sidecar for stateful goals (S07).

A stateful product writes its own files while it runs (``runtime_state`` on the
candidate manifest, S06). The workspace snapshot used by ``verify-goal`` must
exclude exactly those product-managed files, otherwise a legitimate state write
fails the verification as ``workspace_changed`` and blocks ``finish-goal``
(P1-5). The policy is an explicit, reviewed sidecar next to the goal card:

    .opencode/mvp/<slug>.runtime-state.json

It lists **exact project-relative file paths** (never globs, directories or
source/executable code) and is bound into every verification evidence record by
``check.py``. Any later policy change (adding, removing or editing a path;
renaming the goal id; rewriting the file) changes the binding and invalidates
previously recorded evidence, so exclusions cannot be granted retroactively to
revive stale evidence.

All entry points are strict and fail closed: an existing but unreadable,
malformed or structurally invalid policy returns problems, never a silent pass.
A missing policy file means "no runtime state declared" (legacy behavior).

Python 3.10+, stdlib only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import observation_candidate as _candidate
except ImportError:  # pragma: no cover - engine copied without the S06 module
    _candidate = None

POLICY_SCHEMA = "runtime-state-policy/1"
POLICY_SUFFIX = ".runtime-state.json"
_POLICY_FIELDS = frozenset({"schema", "goal_id", "paths", "note"})
_CANDIDATE_UNAVAILABLE = (
    "observation_candidate module unavailable; cannot validate runtime-state "
    "policy paths"
)


def policy_path(goal_path: str | Path) -> Path:
    """The sidecar next to the goal card: ``<slug>.runtime-state.json``."""

    goal = Path(goal_path)
    return goal.parent / (goal.stem + POLICY_SUFFIX)


def _project_root_for(path: Path) -> Path:
    """Resolve the project root from a sidecar path under ``.opencode/mvp``.

    Goal cards are required to live directly under ``.opencode/mvp/``; the
    fallback keeps the module usable with cards placed elsewhere in tests.
    """

    resolved = path.resolve()
    parent = resolved.parent
    if parent.name == "mvp" and parent.parent.name == ".opencode":
        return parent.parent.parent
    return parent


def _reject_non_finite(constant: str) -> Any:
    raise ValueError(f"non-finite number {constant!r} is not valid JSON")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate key {key!r}")
        obj[key] = value
    return obj


def _under_mvp(normalized: str) -> bool:
    parts = normalized.split("/")
    return len(parts) >= 2 and parts[0] == ".opencode" and parts[1] == "mvp"


def _path_problems(value: Any, label: str, problems: list[str]) -> str | None:
    """Validate one policy path through the S06 path rules; return normalized."""

    if _candidate is None:
        return None
    return _candidate._validate_file_path(value, label, problems)


def validate_policy(data: Any, goal_id: str | None = None) -> list[str]:
    """Structural validation of a runtime-state policy document.

    Pure: no filesystem access, never raises. Unknown fields are rejected;
    ``goal_id`` (when given) must match exactly.
    """

    if _candidate is None:
        return [_CANDIDATE_UNAVAILABLE]
    if not isinstance(data, dict):
        return ["runtime-state policy must be a JSON object"]

    problems: list[str] = []
    for key in sorted(data, key=str):
        if key not in _POLICY_FIELDS:
            problems.append(f"runtime-state policy has unknown field {key!r}")
    if data.get("schema") != POLICY_SCHEMA:
        problems.append(f"runtime-state policy schema must be {POLICY_SCHEMA}")

    policy_goal = data.get("goal_id")
    if not isinstance(policy_goal, str) or not policy_goal.strip():
        problems.append("runtime-state policy goal_id must be a non-empty string")
    elif goal_id is not None and policy_goal != goal_id:
        problems.append(
            f"runtime-state policy goal_id {policy_goal!r} does not match goal "
            f"{goal_id!r}"
        )

    note = data.get("note")
    if note is not None and not isinstance(note, str):
        problems.append("runtime-state policy note must be a string when present")

    paths = data.get("paths")
    if not isinstance(paths, list):
        problems.append("runtime-state policy paths must be an array")
        return problems

    seen: set[str] = set()
    for index, item in enumerate(paths):
        label = f"runtime-state policy paths[{index}]"
        normalized = _path_problems(item, label, problems)
        if normalized is None:
            continue
        if normalized in seen:
            problems.append(f"{label} duplicates {item!r}")
        else:
            seen.add(normalized)
        if _under_mvp(normalized):
            problems.append(f"{label} must not live under .opencode/mvp: {item!r}")
        suffix = PurePosixPath(normalized).suffix.lower()
        if suffix in _candidate.SOURCE_EXEC_EXTENSIONS:
            problems.append(
                f"{label} must not be source or executable code: {item!r}"
            )
    return problems


def load_policy(
    goal_path: str | Path, goal_id: str | None = None
) -> tuple[dict[str, Any] | None, list[str]]:
    """Load the policy sidecar and return its binding, or ``(None, problems)``.

    A missing file is ``(None, [])`` (legacy: no exclusions). An existing but
    unreadable, malformed or invalid file is ``(None, problems)`` (fail
    closed). A valid file returns the binding recorded in evidence:

        {"path": <project-relative posix path>, "sha256": <file sha256>,
         "paths": <sorted normalized path list>}
    """

    path = policy_path(goal_path)
    if not path.exists():
        return None, []
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, [f"runtime-state policy unreadable: {exc}"]
    try:
        text = raw.decode("utf-8-sig")
        data = json.loads(
            text,
            parse_constant=_reject_non_finite,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        return None, [f"runtime-state policy is not valid JSON: {exc}"]

    problems = validate_policy(data, goal_id)
    if problems:
        return None, problems

    normalized = sorted({_candidate.normalize_path(item) for item in data["paths"]})
    project = _project_root_for(path)
    try:
        relative = path.resolve().relative_to(project).as_posix()
    except ValueError:  # pragma: no cover - defensive
        relative = path.name
    binding = {
        "path": relative,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "paths": normalized,
    }
    return binding, []


def snapshot_excludes(project_root: str | Path, binding: dict[str, Any] | None) -> list[Path]:
    """Resolved filesystem paths the workspace snapshot must exclude.

    ``binding`` is the object returned by :func:`load_policy`; ``None`` means
    legacy behavior with no exclusions.
    """

    if not isinstance(binding, dict):
        return []
    paths = binding.get("paths")
    if not isinstance(paths, list):
        return []
    project = Path(project_root)
    excludes: list[Path] = []
    for raw in paths:
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            excludes.append((project / raw).resolve())
        except OSError:  # pragma: no cover - defensive
            continue
    return excludes


def candidate_policy_alignment_problems(
    candidate_paths: set[str], binding: dict[str, Any] | None
) -> list[str]:
    """Check that a candidate's declared runtime state is covered by the policy.

    A candidate that declares runtime-state files without a policy cannot have
    its state writes excluded, so verification would fail on a legitimate write:
    that is refused up front. Paths outside the policy are refused one by one.
    A policy may cover more paths than the candidate declares.
    """

    paths = set(candidate_paths) if candidate_paths else set()
    if binding is None:
        if paths:
            return [
                "candidate declares runtime_state but no runtime-state policy "
                "exists; write <slug>.runtime-state.json and re-verify"
            ]
        return []
    declared = binding.get("paths")
    covered = set(declared) if isinstance(declared, list) else set()
    return [
        f"runtime state path not covered by the runtime-state policy: {path}"
        for path in sorted(paths - covered)
    ]

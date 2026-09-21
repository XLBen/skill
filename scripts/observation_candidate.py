#!/usr/bin/env python3
"""Candidate v2 delivered-artifact / runtime-state separation (S06).

A candidate manifest pins immutable delivered artifacts in ``files`` (sha256
bound at adoption time). Stateful products also write their own files while
under observation; hashing those as if they were delivered artifacts produces
false "candidate file changed after binding" diagnostics (P1-5). The optional
``runtime_state`` array declares those product-managed files instead:

- ``validate_runtime_state`` / ``runtime_state_paths`` are pure structure checks
  and never touch the filesystem.
- ``runtime_state_scope_problems`` resolves declared paths and verifies they
  stay inside the project root and inside their declared ``delivered_roots``
  (following symlinks/junctions).
- ``undeclared_delivered_files`` reports files under declared roots that are
  declared neither in ``files`` nor in ``runtime_state``.

All entry points return a ``list[str]`` and never raise on malformed input.
Runtime-state files never participate in the candidate hash binding; the
``files`` hash logic in ``product_observation`` is untouched.
"""

import os
import re
from pathlib import Path, PurePosixPath
from typing import Any

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
GLOB_CHARS = "*?[]"
INITIAL_KINDS = ("absent", "sha256", "ref")
RESETS = ("restore-initial", "delete", "product-managed")

# Source or executable extensions are delivery artifacts, never runtime state.
SOURCE_EXEC_EXTENSIONS = frozenset(
    {
        ".py",
        ".pyc",
        ".js",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".jsx",
        ".rb",
        ".go",
        ".rs",
        ".java",
        ".cs",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".sh",
        ".ps1",
        ".bat",
        ".cmd",
        ".exe",
        ".dll",
        ".so",
    }
)

# Directory segments never scanned by ``undeclared_delivered_files``.
SKIPPED_DIR_SEGMENTS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".opencode",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
    }
)

_ITEM_FIELDS = frozenset({"path", "purpose", "initial", "reset"})
_INITIAL_FIELDS = {
    "absent": frozenset({"kind"}),
    "sha256": frozenset({"kind", "sha256"}),
    "ref": frozenset({"kind", "ref"}),
}


def _posix(value: str) -> str:
    return value.replace("\\", "/")


def normalize_path(value: str) -> str:
    """POSIX-normalize a project-relative path (``\\`` to ``/``, drop ``.``)."""

    return "/".join(
        segment
        for segment in _posix(value).split("/")
        if segment not in ("", ".")
    )


def _is_absolute(value: str) -> bool:
    if _posix(value).startswith("/"):
        return True
    try:
        return Path(value).is_absolute()
    except (OSError, ValueError):  # pragma: no cover - defensive
        return True


def _relative_path_problems(value: str, label: str) -> list[str]:
    problems: list[str] = []
    if _is_absolute(value):
        problems.append(f"{label} must be project-relative, not absolute: {value}")
    if any(char in value for char in GLOB_CHARS):
        problems.append(f"{label} must not contain glob characters: {value}")
    if ".." in PurePosixPath(_posix(value)).parts:
        problems.append(f"{label} must not contain '..': {value}")
    return problems


def _require_str(value: Any, label: str, problems: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{label} must be a non-empty string")
        return None
    return value


def _validate_file_path(value: Any, label: str, problems: list[str]) -> str | None:
    """Shape-check a runtime-state file path; return its normalized form."""

    if not isinstance(value, str) or not value.strip():
        problems.append(f"{label} must be a non-empty string")
        return None
    problems.extend(_relative_path_problems(value, label))
    if _is_absolute(value):
        return None
    posix = _posix(value)
    if posix.endswith("/"):
        problems.append(f"{label} must name a file, not a directory: {value}")
        return None
    if ".." in PurePosixPath(posix).parts:
        return None
    normalized = normalize_path(value)
    if not normalized:
        problems.append(f"{label} must name a file: {value}")
        return None
    return normalized


def _initial_problems(initial: Any, label: str) -> list[str]:
    problems: list[str] = []
    if not isinstance(initial, dict):
        problems.append(f"{label} must be an object with a kind")
        return problems
    kind = initial.get("kind")
    if kind not in INITIAL_KINDS:
        problems.append(f"{label}.kind must be one of {'|'.join(INITIAL_KINDS)}")
        return problems
    for key in sorted(initial, key=str):
        if key not in _INITIAL_FIELDS[kind]:
            problems.append(f"{label} has unknown field {key!r} for kind {kind!r}")
    if kind == "sha256":
        digest = initial.get("sha256")
        if not isinstance(digest, str) or not HASH_RE.fullmatch(digest):
            problems.append(
                f"{label}.sha256 must be a 64-character lowercase sha256 hex digest"
            )
    elif kind == "ref":
        ref = initial.get("ref")
        if not isinstance(ref, str) or not ref.strip():
            problems.append(f"{label}.ref must be a non-empty string")
        else:
            problems.extend(_relative_path_problems(ref, f"{label}.ref"))
    return problems


def _declared_file_paths(manifest: Any) -> set[str]:
    if not isinstance(manifest, dict):
        return set()
    files = manifest.get("files")
    if not isinstance(files, list):
        return set()
    paths: set[str] = set()
    for item in files:
        if isinstance(item, dict):
            path = item.get("path")
            if isinstance(path, str) and path.strip():
                paths.add(normalize_path(path))
    return paths


def runtime_state_paths(manifest: Any) -> set[str]:
    """Normalized set of declared runtime-state paths (empty when absent)."""

    if not isinstance(manifest, dict):
        return set()
    items = manifest.get("runtime_state")
    if not isinstance(items, list):
        return set()
    paths: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            path = item.get("path")
            if isinstance(path, str) and path.strip():
                paths.add(normalize_path(path))
    return paths


def _clean_delivered_roots(manifest: Any) -> list[str]:
    if not isinstance(manifest, dict):
        return []
    raw = manifest.get("delivered_roots")
    if not isinstance(raw, list):
        return []
    roots: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            continue
        if _is_absolute(item):
            continue
        if any(char in item for char in GLOB_CHARS):
            continue
        if ".." in PurePosixPath(_posix(item)).parts:
            continue
        normalized = normalize_path(item)
        if normalized not in roots:
            roots.append(normalized)
    return roots


def _under_mvp(normalized: str) -> bool:
    parts = normalized.split("/")
    return len(parts) >= 2 and parts[0] == ".opencode" and parts[1] == "mvp"


def _is_inside(path_norm: str, root_norm: str) -> bool:
    """POSIX segment-prefix containment; ``root_norm == ""`` is the project root."""

    path_parts = PurePosixPath(path_norm).parts
    root_parts = PurePosixPath(root_norm).parts
    return path_parts[: len(root_parts)] == root_parts


def validate_runtime_state(manifest: Any) -> list[str]:
    """Structural validation of ``runtime_state`` / ``delivered_roots``.

    Pure: no filesystem access, never raises. Messages use the same
    ``candidate.<field>`` where-labels as the rest of the manifest validator.
    A missing or ``null`` ``runtime_state`` means "no declared runtime state".
    """

    if not isinstance(manifest, dict):
        return []
    problems: list[str] = []

    raw_state = manifest.get("runtime_state")
    if raw_state is None:
        items: list[Any] | None = None
    elif not isinstance(raw_state, list):
        problems.append("candidate.runtime_state must be an array when present")
        items = None
    else:
        items = raw_state

    file_paths = _declared_file_paths(manifest)
    seen: set[str] = set()
    if items is not None:
        for index, item in enumerate(items):
            where = f"candidate.runtime_state[{index}]"
            if not isinstance(item, dict):
                problems.append(f"{where} must be an object")
                continue
            for key in sorted(item, key=str):
                if key not in _ITEM_FIELDS:
                    problems.append(f"{where} has unknown field {key!r}")
            normalized = _validate_file_path(item.get("path"), f"{where}.path", problems)
            if normalized is not None:
                if normalized in seen:
                    problems.append(f"{where}.path duplicates {item.get('path')}")
                else:
                    seen.add(normalized)
                if normalized in file_paths:
                    problems.append(
                        f"{where}.path overlaps a bound candidate file: {item.get('path')}"
                    )
                if _under_mvp(normalized):
                    problems.append(
                        f"{where}.path must not live under .opencode/mvp: {item.get('path')}"
                    )
                suffix = PurePosixPath(normalized).suffix.lower()
                if suffix in SOURCE_EXEC_EXTENSIONS:
                    problems.append(
                        f"{where}.path must not be source or executable code: "
                        f"{item.get('path')}"
                    )
            _require_str(item.get("purpose"), f"{where}.purpose", problems)
            problems.extend(_initial_problems(item.get("initial"), f"{where}.initial"))
            reset = item.get("reset")
            if reset not in RESETS:
                problems.append(f"{where}.reset must be one of {'|'.join(RESETS)}")

    roots: list[str] = []
    raw_roots = manifest.get("delivered_roots")
    if raw_roots is not None:
        if not isinstance(raw_roots, list):
            problems.append("candidate.delivered_roots must be an array when present")
        else:
            for index, item in enumerate(raw_roots):
                where = f"candidate.delivered_roots[{index}]"
                if not isinstance(item, str) or not item.strip():
                    problems.append(f"{where} must be a non-empty string")
                    continue
                root_problems = _relative_path_problems(item, where)
                if root_problems:
                    problems.extend(root_problems)
                    continue
                normalized = normalize_path(item)
                if normalized not in roots:
                    roots.append(normalized)

    if roots and items is not None:
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            if not isinstance(path, str) or not path.strip():
                continue
            if _is_absolute(path) or ".." in PurePosixPath(_posix(path)).parts:
                continue
            if not any(_is_inside(normalize_path(path), root) for root in roots):
                problems.append(
                    f"candidate.runtime_state[{index}].path is not inside any "
                    f"delivered_root: {path}"
                )
    return problems


def _is_within(path: Path, base: Path) -> bool:
    path_text = os.path.normcase(os.path.abspath(str(path)))
    base_text = os.path.normcase(os.path.abspath(str(base)))
    return path_text == base_text or path_text.startswith(base_text + os.sep)


def runtime_state_scope_problems(project_root: str | Path, manifest: Any) -> list[str]:
    """Filesystem scope checks for declared runtime-state paths.

    Each path must resolve inside the project root and, when ``delivered_roots``
    are declared, inside the most specific declared root that contains it.
    Existing symlinks/junctions are followed, so a link that escapes either
    scope is reported.
    """

    problems: list[str] = []
    if not isinstance(manifest, dict):
        return problems
    items = manifest.get("runtime_state")
    if not isinstance(items, list):
        return problems

    project = Path(project_root)
    try:
        resolved_root = project.resolve()
    except OSError:  # pragma: no cover - defensive
        resolved_root = project.absolute()
    roots = _clean_delivered_roots(manifest)

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path.strip():
            continue
        if _is_absolute(path) or any(char in path for char in GLOB_CHARS):
            continue
        if ".." in PurePosixPath(_posix(path)).parts:
            continue
        normalized = normalize_path(path)
        if not normalized:
            continue
        try:
            resolved = (project / normalized).resolve()
        except (OSError, RuntimeError) as exc:
            problems.append(
                f"candidate.runtime_state[{index}].path could not be resolved: "
                f"{path} ({exc})"
            )
            continue
        if not _is_within(resolved, resolved_root):
            problems.append(
                f"candidate.runtime_state[{index}].path resolves outside the "
                f"project root: {path}"
            )
            continue
        if not roots:
            continue
        lexical = sorted(
            (root for root in roots if _is_inside(normalized, root)), key=len
        )
        if not lexical:
            problems.append(
                f"candidate.runtime_state[{index}].path is not inside any "
                f"delivered_root: {path}"
            )
            continue
        specific = lexical[-1]
        try:
            resolved_delivered = (project / specific).resolve()
        except (OSError, RuntimeError) as exc:  # pragma: no cover - defensive
            problems.append(
                f"candidate.runtime_state[{index}].path delivered_root could not "
                f"be resolved: {specific} ({exc})"
            )
            continue
        if not _is_within(resolved, resolved_delivered):
            problems.append(
                f"candidate.runtime_state[{index}].path resolves outside "
                f"delivered_root {specific!r}: {path}"
            )
    return problems


def undeclared_delivered_files(project_root: str | Path, manifest: Any) -> list[str]:
    """Files under ``delivered_roots`` declared in neither ``files`` nor runtime state.

    Returns sorted POSIX paths relative to the project root. Without
    ``delivered_roots`` this returns ``[]`` (nothing is guessed).
    """

    roots = _clean_delivered_roots(manifest)
    if not roots:
        return []
    project = Path(project_root)
    declared = _declared_file_paths(manifest) | runtime_state_paths(manifest)
    found: set[str] = set()
    for relative in roots:
        base = project / relative if relative else project
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(
                name for name in dirnames if name not in SKIPPED_DIR_SEGMENTS
            )
            for name in filenames:
                full = Path(dirpath) / name
                try:
                    rel = full.relative_to(project).as_posix()
                except ValueError:  # pragma: no cover - defensive
                    continue
                if rel not in declared:
                    found.add(rel)
    return sorted(found)

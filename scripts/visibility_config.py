#!/usr/bin/env python3
"""Project-local observer visibility settings (S11).

The product-observer seat needs an explicitly selected, project-scoped model.
The host's ``opencode models`` catalog carries no capability metadata (S01), so
this module does two things and nothing else:

1. turns a human request (``gpt 5.6 luna``, ``deepseek``, a full
   ``provider/model``) into a decision against the **real** catalog: ``exact``
   / ``unique`` / ``ambiguous`` / ``none``, never an invented model id;
2. persists the decision in the frozen project path
   ``.opencode/mvp/visibility.json`` with a strict schema, atomic writes and
   per-capability verification status.

The file is read by the next observation dispatch (S12). It never touches the
main chat model or any global OpenCode configuration.

Python 3.10+, stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VISIBILITY_SCHEMA = "workflow-visibility/1"
DEFAULT_REQUEST = "gpt 5.6 luna"
VISIBILITY_RELATIVE_PATH = ".opencode/mvp/visibility.json"

CAPABILITIES = ("image", "video", "audio")
VISIBILITY_STATUSES = ("unverified", "verified", "unavailable")
DEFAULT_CAPABILITIES = {
    "image": "unverified",
    "video": "unverified",
    "audio": "unverified",
}

SELECTION_STATUS = "selected"
_FULL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
_DOCUMENT_FIELDS = frozenset({"schema", "selection", "updated_at"})
_SELECTION_FIELDS = frozenset(
    {
        "requested_name",
        "provider_id",
        "model_id",
        "status",
        "capabilities",
        "capability_evidence",
    }
)
_CATALOG_TIMEOUT_SECONDS = 60.0


def _utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _reject_non_finite(constant: str) -> Any:
    raise ValueError(f"non-finite number {constant!r} is not valid JSON")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate key {key!r}")
        obj[key] = value
    return obj


def visibility_path(project: str | Path) -> Path:
    """The frozen per-project settings path: ``<project>/.opencode/mvp/visibility.json``."""

    return Path(project) / VISIBILITY_RELATIVE_PATH


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def parse_catalog(text: Any) -> list[dict[str, str]]:
    """Parse ``opencode models`` output into ``{provider_id, model_id, full}``.

    Blank lines and lines that are not a bare ``provider/model`` token are
    ignored (the CLI may print warnings on stdout). Duplicate lines collapse to
    the first occurrence; the catalog is never expanded beyond what the host
    actually reported.
    """

    if not isinstance(text, str):
        return []
    catalog: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.strip()
        if not line or not _FULL_RE.match(line) or line in seen:
            continue
        seen.add(line)
        provider_id, model_id = line.split("/", 1)
        catalog.append(
            {"provider_id": provider_id, "model_id": model_id, "full": line}
        )
    return catalog


def normalize_key(value: Any) -> str:
    """Lowercase, collapse whitespace/underscores to ``-``, strip outer ``-``."""

    if not isinstance(value, str):
        return ""
    return re.sub(r"[\s_]+", "-", value.strip().lower()).strip("-")


def _catalog_entries(catalog: Any) -> list[dict[str, Any]]:
    if not isinstance(catalog, list):
        return []
    entries: list[dict[str, Any]] = []
    for entry in catalog:
        if not isinstance(entry, dict):
            continue
        full = entry.get("full")
        provider_id = entry.get("provider_id")
        model_id = entry.get("model_id")
        if not all(isinstance(item, str) and item for item in (full, provider_id, model_id)):
            continue
        if not _FULL_RE.match(full):
            continue
        entries.append(
            {"provider_id": provider_id, "model_id": model_id, "full": full}
        )
    return entries


def _sorted_by_full(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for entry in entries:
        unique.setdefault(entry["full"], entry)
    return [unique[full] for full in sorted(unique)]


def match_models(query: Any, catalog: Any) -> dict[str, Any]:
    """Resolve a request against the real catalog.

    Modes: ``exact`` (the query carries ``/`` and normalizes to a full id),
    ``unique`` (normalized equality with a full id or model id, or a token
    subset with exactly one hit), ``ambiguous`` (several real candidates),
    ``none``. ``matches`` is always sorted by ``full``.
    """

    text = query.strip() if isinstance(query, str) else ""
    normalized = normalize_key(text)
    entries = _catalog_entries(catalog)
    if not normalized:
        return {"mode": "none", "matches": [], "query": text}

    if "/" in text:
        exact = [entry for entry in entries if normalize_key(entry["full"]) == normalized]
        if exact:
            return {"mode": "exact", "matches": _sorted_by_full(exact), "query": text}

    identity = [
        entry
        for entry in entries
        if normalize_key(entry["full"]) == normalized
        or normalize_key(entry["model_id"]) == normalized
    ]
    if identity:
        mode = "unique" if len(_sorted_by_full(identity)) == 1 else "ambiguous"
        return {"mode": mode, "matches": _sorted_by_full(identity), "query": text}

    tokens = {token for token in normalized.split("-") if token}
    subset = []
    for entry in entries:
        full_tokens = set(normalize_key(entry["full"]).split("-"))
        model_tokens = set(normalize_key(entry["model_id"]).split("-"))
        if tokens <= (full_tokens | model_tokens):
            subset.append(entry)
    subset = _sorted_by_full(subset)
    if not subset:
        return {"mode": "none", "matches": [], "query": text}
    mode = "unique" if len(subset) == 1 else "ambiguous"
    return {"mode": mode, "matches": subset, "query": text}


def validate_visibility(data: Any) -> list[str]:
    """Strict structural validation of a visibility document. Pure, never raises."""

    if not isinstance(data, dict):
        return ["visibility settings must be a JSON object"]

    problems: list[str] = []
    for key in sorted(data, key=str):
        if key not in _DOCUMENT_FIELDS:
            problems.append(f"visibility settings have unknown field {key!r}")
    if data.get("schema") != VISIBILITY_SCHEMA:
        problems.append(f"visibility settings schema must be {VISIBILITY_SCHEMA}")
    updated_at = data.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at.strip():
        problems.append("visibility settings updated_at must be a non-empty string")

    selection = data.get("selection")
    if not isinstance(selection, dict):
        problems.append("visibility settings selection must be an object")
        return problems

    for key in sorted(selection, key=str):
        if key not in _SELECTION_FIELDS:
            problems.append(f"visibility selection has unknown field {key!r}")
    for field in ("requested_name", "provider_id", "model_id"):
        value = selection.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"visibility selection {field} must be a non-empty string")
    if selection.get("status") != SELECTION_STATUS:
        problems.append(f"visibility selection status must be {SELECTION_STATUS}")
    provider_id = selection.get("provider_id")
    model_id = selection.get("model_id")
    if (
        isinstance(provider_id, str)
        and provider_id.strip()
        and isinstance(model_id, str)
        and model_id.strip()
        and not _FULL_RE.match(f"{provider_id}/{model_id}")
    ):
        problems.append("visibility selection must identify a provider/model pair")

    capabilities = selection.get("capabilities")
    if not isinstance(capabilities, dict):
        problems.append("visibility selection capabilities must be an object")
    else:
        for key in sorted(capabilities, key=str):
            if key not in CAPABILITIES:
                problems.append(f"visibility capabilities has unknown key {key!r}")
        for capability in CAPABILITIES:
            value = capabilities.get(capability)
            if value not in VISIBILITY_STATUSES:
                problems.append(
                    f"visibility capabilities.{capability} must be one of "
                    + "/".join(VISIBILITY_STATUSES)
                )

    evidence = selection.get("capability_evidence")
    if evidence is not None:
        if not isinstance(evidence, dict):
            problems.append("visibility selection capability_evidence must be an object")
        else:
            for key in sorted(evidence, key=str):
                if key not in CAPABILITIES:
                    problems.append(
                        f"visibility capability_evidence has unknown key {key!r}"
                    )
                elif not isinstance(evidence[key], str) or not evidence[key].strip():
                    problems.append(
                        f"visibility capability_evidence.{key} must be a non-empty string"
                    )
    return problems


def load_visibility(path: str | Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Load the settings file. Missing is ``(None, [])``; invalid is fail closed."""

    target = Path(path)
    if not target.exists():
        return None, []
    try:
        raw = target.read_bytes()
    except OSError as exc:
        return None, [f"visibility settings unreadable: {exc}"]
    try:
        data = json.loads(
            raw.decode("utf-8-sig"),
            parse_constant=_reject_non_finite,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        return None, [f"visibility settings are not valid JSON: {exc}"]

    problems = validate_visibility(data)
    if problems:
        return None, problems
    return data, []


def save_visibility(path: str | Path, data: Any) -> list[str]:
    """Validate and atomically write the settings file (temp + ``os.replace``).

    Invalid data or a missing parent directory returns problems and never
    touches an existing file. On any write failure the previous file stays
    byte-identical and the temporary file is removed.
    """

    problems = validate_visibility(data)
    if problems:
        return problems

    target = Path(path)
    parent = target.parent
    if not parent.is_dir():
        return [f"visibility directory does not exist: {parent}"]

    payload = (
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    try:
        handle_fd, tmp_name = tempfile.mkstemp(
            prefix=target.name + ".", suffix=".tmp", dir=str(parent)
        )
    except OSError as exc:
        return [f"cannot create temporary visibility file: {exc}"]

    try:
        with os.fdopen(handle_fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except OSError as exc:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        return [f"cannot write visibility file: {exc}"]
    return []


def _capabilities_from(data: Any) -> dict[str, str]:
    """Preserve existing capabilities when the loaded document is valid."""

    if isinstance(data, dict):
        selection = data.get("selection")
        if isinstance(selection, dict):
            capabilities = selection.get("capabilities")
            if isinstance(capabilities, dict) and set(capabilities) == set(CAPABILITIES):
                if all(
                    capabilities.get(name) in VISIBILITY_STATUSES
                    for name in CAPABILITIES
                ):
                    return {name: capabilities[name] for name in CAPABILITIES}
    return dict(DEFAULT_CAPABILITIES)


def _document(
    requested_name: str,
    provider_id: str,
    model_id: str,
    capabilities: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema": VISIBILITY_SCHEMA,
        "updated_at": _now(),
        "selection": {
            "requested_name": requested_name,
            "provider_id": provider_id,
            "model_id": model_id,
            "status": SELECTION_STATUS,
            "capabilities": capabilities,
        },
    }


def resolve_request(path: str | Path, request: Any, catalog: Any) -> dict[str, Any]:
    """Resolve a request against the catalog and persist exact/unique results.

    ``not-found`` and ``needs-selection`` never write. A persisted selection
    keeps previously verified capabilities (or starts them unverified).
    """

    match = match_models(request, catalog)
    if match["mode"] == "none":
        return {"status": "not-found"}
    if match["mode"] == "ambiguous":
        return {
            "status": "needs-selection",
            "candidates": [entry["full"] for entry in match["matches"]],
        }

    entry = match["matches"][0]
    existing, _ = load_visibility(path)
    requested_name = request.strip()
    data = _document(
        requested_name,
        entry["provider_id"],
        entry["model_id"],
        _capabilities_from(existing),
    )
    problems = save_visibility(path, data)
    if problems:
        return {"status": "error", "problems": problems}
    return {"status": "selected", "selection": data["selection"]}


def select_model(
    path: str | Path, full: Any
) -> tuple[dict[str, Any] | None, list[str]]:
    """Persist an explicit, already-disambiguated ``provider/model`` id."""

    if not isinstance(full, str) or not _FULL_RE.match(full.strip()):
        return None, [f"model must be a provider/model id: {full!r}"]

    selected = full.strip()
    provider_id, model_id = selected.split("/", 1)
    existing, _ = load_visibility(path)
    data = _document(
        selected, provider_id, model_id, _capabilities_from(existing)
    )
    problems = save_visibility(path, data)
    if problems:
        return None, problems
    return data, []


def mark_capability(
    path: str | Path,
    capability: Any,
    status: Any,
    evidence: Any = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Update one capability status; ``verified`` requires a non-empty evidence ref."""

    if capability not in CAPABILITIES:
        return None, [
            "capability must be one of " + "/".join(CAPABILITIES) + f": {capability!r}"
        ]
    if status not in VISIBILITY_STATUSES:
        return None, [
            "status must be one of "
            + "/".join(VISIBILITY_STATUSES)
            + f": {status!r}"
        ]
    if status == "verified" and (not isinstance(evidence, str) or not evidence.strip()):
        return None, ["verified capability requires a non-empty evidence reference"]

    data, problems = load_visibility(path)
    if data is None:
        if not problems:
            problems = [
                f"no visibility settings at {Path(path)}; select a model first"
            ]
        return None, problems

    selection = data["selection"]
    selection["capabilities"][capability] = status
    evidence_map = selection.get("capability_evidence")
    if not isinstance(evidence_map, dict):
        evidence_map = {}
    if status == "verified":
        evidence_map[capability] = evidence.strip()
    else:
        evidence_map.pop(capability, None)
    if evidence_map:
        selection["capability_evidence"] = evidence_map
    else:
        selection.pop("capability_evidence", None)
    data["updated_at"] = _now()

    problems = save_visibility(path, data)
    if problems:
        return None, problems
    return data, []


def show(path: str | Path) -> dict[str, Any]:
    """Current project settings plus the default request."""

    target = Path(path)
    data, problems = load_visibility(target)
    if data is not None:
        return {
            "status": "selected",
            "path": str(target),
            "default_request": DEFAULT_REQUEST,
            "selection": data["selection"],
            "updated_at": data["updated_at"],
        }
    if problems:
        return {
            "status": "invalid",
            "path": str(target),
            "default_request": DEFAULT_REQUEST,
            "problems": problems,
        }
    return {
        "status": "unconfigured",
        "path": str(target),
        "default_request": DEFAULT_REQUEST,
        "selection": None,
    }


def load_catalog_file(path: str | Path) -> tuple[str | None, list[str]]:
    """Read an offline catalog snapshot (tests, or a saved ``opencode models`` dump)."""

    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        return None, [f"cannot read catalog file: {exc}"]
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", "replace"), []
    return raw.decode("utf-8-sig", "replace"), []


def _opencode_argv() -> list[str]:
    executable = shutil.which("opencode")
    if not executable:
        return ["opencode", "models"]
    suffix = Path(executable).suffix.lower()
    if suffix in (".cmd", ".bat"):
        comspec = os.environ.get("COMSPEC") or "cmd.exe"
        return [comspec, "/c", executable, "models"]
    if suffix == ".ps1":
        return ["powershell", "-NoProfile", "-NonInteractive", "-File", executable, "models"]
    return [executable, "models"]


def run_models_command(timeout: float = _CATALOG_TIMEOUT_SECONDS) -> tuple[str | None, list[str]]:
    """Run ``opencode models`` as an argv array, capturing bytes as UTF-8 (replace)."""

    argv = _opencode_argv()
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return None, ["opencode executable not found on PATH"]
    except subprocess.TimeoutExpired:
        return None, [f"opencode models timed out after {timeout:.0f}s"]
    except OSError as exc:
        return None, [f"cannot run opencode models: {exc}"]
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace").strip()
        return None, [
            f"opencode models failed with exit code {completed.returncode}: {stderr}"
        ]
    return completed.stdout.decode("utf-8", "replace"), []


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    _utf8()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    show_cmd = sub.add_parser("show", help="show the current project selection")
    show_cmd.add_argument("--project", default=".", help="project root directory")

    set_cmd = sub.add_parser(
        "set", help="resolve a request against the real catalog and select it"
    )
    set_cmd.add_argument("--project", default=".", help="project root directory")
    set_cmd.add_argument("--request", help="model request name (default: %s)" % DEFAULT_REQUEST)
    set_cmd.add_argument("--catalog-file", help="offline 'opencode models' text file")

    select_cmd = sub.add_parser(
        "select", help="persist an explicit provider/model choice"
    )
    select_cmd.add_argument("--project", default=".", help="project root directory")
    select_cmd.add_argument("--model", required=True, help="full provider/model id")

    mark_cmd = sub.add_parser("mark", help="record a capability probe result")
    mark_cmd.add_argument("--project", default=".", help="project root directory")
    mark_cmd.add_argument("--capability", required=True, choices=CAPABILITIES)
    mark_cmd.add_argument("--status", required=True, choices=VISIBILITY_STATUSES)
    mark_cmd.add_argument("--evidence", help="evidence reference for verified status")

    args = parser.parse_args(argv)

    if args.cmd == "show":
        result = show(visibility_path(args.project))
        _emit(result)
        if result["status"] == "invalid":
            for problem in result["problems"]:
                print(f"  - {problem}", file=sys.stderr)
            return 2
        return 0

    if args.cmd == "set":
        request = args.request if args.request is not None else DEFAULT_REQUEST
        if args.catalog_file:
            text, problems = load_catalog_file(args.catalog_file)
        else:
            text, problems = run_models_command()
        if text is None:
            for problem in problems:
                print(f"ERROR: {problem}", file=sys.stderr)
            return 2
        result = resolve_request(
            visibility_path(args.project), request, parse_catalog(text)
        )
        _emit(result)
        status = result.get("status")
        if status == "selected":
            return 0
        if status == "needs-selection":
            return 3
        if status == "not-found":
            return 4
        for problem in result.get("problems") or []:
            print(f"ERROR: {problem}", file=sys.stderr)
        return 2

    if args.cmd == "select":
        data, problems = select_model(visibility_path(args.project), args.model)
        if data is None:
            for problem in problems:
                print(f"ERROR: {problem}", file=sys.stderr)
            return 2
        _emit({"status": "selected", "selection": data["selection"]})
        return 0

    data, problems = mark_capability(
        visibility_path(args.project),
        args.capability,
        args.status,
        args.evidence,
    )
    if data is None:
        for problem in problems:
            print(f"ERROR: {problem}", file=sys.stderr)
        return 2
    _emit(
        {
            "status": "marked",
            "capability": args.capability,
            "value": data["selection"]["capabilities"][args.capability],
            "selection": data["selection"],
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

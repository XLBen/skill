#!/usr/bin/env python3
"""Observation result store (S08a): parse, locate, and archive raw payloads.

This module owns the on-disk layout of a product-observation run:

    <cdir>/<phase>/<run-id>/result.json
    <cdir>/<phase>/<run-id>/attempts/<attempt-id>.attempt.json
    <cdir>/<phase>/<run-id>/attempts/<attempt-id>.errors.json

Payload parsing is deliberately strict: exactly one fenced ``json`` block,
nothing but whitespace after it, JSON object at the top level. Attempt writes
are create-only and atomic (temp file + ``os.replace``) so a half-written or
overwritten artifact can never be mistaken for a recorded attempt.
"""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

try:
    import observation_contract as _contract
except ImportError:  # pragma: no cover - engine copied without the frozen contract
    _contract = None

_FENCE_OPEN = "```json"
_FENCE_CLOSE = "```"
_RUN_ID_RE = re.compile(r"^run-(\d+)$")
_ATTEMPT_ID_RE = re.compile(r"^attempt-(\d+)\.attempt\.json$")
_ATTEMPT_ID_OK = re.compile(r"^attempt-\d{3,}$")


def canonical_bytes(value: Any) -> bytes:
    """Canonical UTF-8 bytes of ``value`` for content equality comparison."""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return text.encode("utf-8")


def parse_single_payload(text: str) -> Tuple[Optional[dict], list]:
    """Parse a response that must hold exactly one fenced JSON object.

    Returns ``(payload, problems)``. On success ``problems`` is empty and
    ``payload`` is the parsed object. Otherwise ``payload`` is ``None`` and
    ``problems`` explains every reason the text was rejected. Never falls back
    to the last block or to scanning for arbitrary JSON.
    """
    problems = []
    if not isinstance(text, str):
        return None, ["payload is not a string"]

    stripped = text.strip()
    start = stripped.find(_FENCE_OPEN)
    if start == -1:
        return None, ["no ```json fenced block found"]

    head = stripped[:start]
    if "```" in head:
        problems.append("content before the first ```json fence")

    after_open = stripped[start + len(_FENCE_OPEN):]
    end = after_open.find(_FENCE_CLOSE)
    if end == -1:
        return None, problems + ["unterminated ```json fenced block"]

    body = after_open[:end]
    tail = after_open[end + len(_FENCE_CLOSE):]
    if tail.strip():
        problems.append("content after the first fenced block")
    if _FENCE_OPEN in tail:
        problems.append("more than one ```json fenced block")
    elif _FENCE_CLOSE in tail:
        problems.append("more than one fenced block")

    if problems:
        return None, problems

    try:
        payload = json.loads(body)
    except ValueError as exc:
        return None, [f"invalid JSON: {exc}"]

    if not isinstance(payload, dict):
        return None, [f"payload is not a JSON object: {type(payload).__name__}"]

    return payload, []


def run_dir(cdir: Any, phase: str, run_id: str) -> Path:
    return Path(cdir) / phase / run_id


def result_path(cdir: Any, phase: str, run_id: str) -> Path:
    return run_dir(cdir, phase, run_id) / "result.json"


def attempts_dir(run_dir: Any) -> Path:
    return Path(run_dir) / "attempts"


def allocate_run_id(cdir: Any, phase: str) -> str:
    """Return the next ``run-00N`` id under ``<cdir>/<phase>``."""
    phase_dir = Path(cdir) / phase
    highest = 0
    if phase_dir.is_dir():
        for entry in phase_dir.iterdir():
            match = _RUN_ID_RE.match(entry.name)
            if match and entry.is_dir():
                highest = max(highest, int(match.group(1)))
    return f"run-{highest + 1:03d}"


def next_attempt_id(run_dir: Any) -> str:
    """Return the next ``attempt-00N`` id under ``<run_dir>/attempts``."""
    target = attempts_dir(run_dir)
    highest = 0
    if target.is_dir():
        for entry in target.iterdir():
            match = _ATTEMPT_ID_RE.match(entry.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return f"attempt-{highest + 1:03d}"


def record_attempt(
    run_dir: Any,
    attempt_id: str,
    raw_text: str,
    parsed: Optional[dict],
    errors: Sequence[str],
    received_at: str,
) -> Tuple[Path, Path]:
    """Write the attempt + errors artifacts for a single received response.

    Create-only: an existing target raises ``ValueError`` and the file on disk
    is left untouched. Returns the two written paths.
    """
    if not isinstance(attempt_id, str) or not _ATTEMPT_ID_OK.match(attempt_id):
        raise ValueError(f"invalid attempt id: {attempt_id!r}")

    target_dir = attempts_dir(run_dir)
    attempt_path = target_dir / f"{attempt_id}.attempt.json"
    errors_path = target_dir / f"{attempt_id}.errors.json"

    _write_new_json(
        attempt_path,
        {
            "attempt_id": attempt_id,
            "raw_text": raw_text,
            "parsed": parsed,
            "received_at": received_at,
        },
    )
    try:
        _write_new_json(
            errors_path,
            {
                "attempt_id": attempt_id,
                "errors": list(errors),
                "parsed_ok": not errors,
            },
        )
    except Exception:
        try:
            attempt_path.unlink()
        except OSError:
            pass
        raise

    return attempt_path, errors_path


def _write_new_json(path: Any, value: Any) -> None:
    """Atomically create ``path`` holding ``value`` as UTF-8 JSON.

    Creates parent directories, refuses to overwrite an existing file, and
    lands the bytes via a temporary file in the target directory followed by
    ``tempfile`` + ``os.replace``.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError(f"refusing to overwrite existing file: {target}")

    data = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    handle, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
        if target.exists():
            raise ValueError(f"refusing to overwrite existing file: {target}")
        os.replace(tmp_path, target)
    except Exception:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# S08a-2: envelope validation, provenance/evidence gates, and adoption
# ---------------------------------------------------------------------------

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ADOPT_PHASES = ("discover", "compare")
_CONTRACT_UNAVAILABLE = (
    "observation_contract module unavailable; cannot validate "
    "product-observation/2 payloads"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _evidence_value_problems(
    ref: Any, cdir: Path, project_root: Path, label: str, problems: list
) -> None:
    if not isinstance(ref, str) or not ref.strip():
        problems.append(f"{label} must be a non-empty string")
        return
    relative = Path(ref)
    if relative.is_absolute() or ".." in relative.parts:
        problems.append(f"evidence ref escapes the candidate evidence scope: {ref}")
        return
    in_cdir = cdir / ref
    target = in_cdir if in_cdir.is_file() else project_root / ref
    if not target.is_file():
        problems.append(f"evidence ref not found: {ref}")
        return
    try:
        target.resolve().relative_to(cdir.resolve())
    except (OSError, ValueError):
        problems.append(f"evidence ref escapes the candidate evidence scope: {ref}")


def evidence_ref_problems(
    cdir: Any, project_root: Any, payload: Any
) -> list:
    """Check every evidence reference resolves inside ``<cdir>``.

    Covers the report-level ``evidence_refs`` plus the per-journey and
    per-finding arrays. Non-object payloads, journeys or findings are reported
    as problems instead of raising; non-list reference arrays are left to the
    structural contract validator.
    """

    problems: list = []
    if not isinstance(payload, dict):
        return ["evidence refs: payload must be a JSON object"]
    cdir = Path(cdir)
    project_root = Path(project_root)

    evidence = payload.get("evidence_refs")
    if isinstance(evidence, list):
        for index, ref in enumerate(evidence):
            _evidence_value_problems(
                ref, cdir, project_root, f"evidence_refs[{index}]", problems
            )

    journeys = payload.get("journeys")
    if isinstance(journeys, list):
        for j_index, journey in enumerate(journeys):
            if not isinstance(journey, dict):
                problems.append(f"journeys[{j_index}] must be an object")
                continue
            refs = journey.get("evidence_refs")
            if isinstance(refs, list):
                for r_index, ref in enumerate(refs):
                    _evidence_value_problems(
                        ref,
                        cdir,
                        project_root,
                        f"journeys[{j_index}].evidence_refs[{r_index}]",
                        problems,
                    )

    findings = payload.get("findings")
    if isinstance(findings, list):
        for f_index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                problems.append(f"findings[{f_index}] must be an object")
                continue
            refs = finding.get("evidence_refs")
            if isinstance(refs, list):
                for r_index, ref in enumerate(refs):
                    _evidence_value_problems(
                        ref,
                        cdir,
                        project_root,
                        f"findings[{f_index}].evidence_refs[{r_index}]",
                        problems,
                    )

    return problems


def parse_session_model(value: Any) -> Optional[dict]:
    """Normalize a session model record into provider/model/variant fields.

    Accepts the raw JSON string kept in ``session.model`` (as exported to a
    runtime trace), an equivalent mapping, or an already normalized mapping.
    Returns ``None`` when provider or model is missing/unusable; ``variant``
    is optional and normalizes to ``None``. Mirrors
    ``runtime_trace._parse_session_model``.
    """

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if not isinstance(value, dict):
        return None
    provider = value.get("provider_id", value.get("providerID"))
    model = value.get("model_id", value.get("id"))
    if not isinstance(provider, str) or not provider.strip():
        return None
    if not isinstance(model, str) or not model.strip():
        return None
    variant = value.get("variant")
    if not isinstance(variant, str) or not variant.strip():
        variant = None
    return {"provider_id": provider, "model_id": model, "variant": variant}


def _expected_model_parts(expected_model: Any) -> Optional[Tuple[str, str]]:
    if isinstance(expected_model, str):
        provider, _, model = expected_model.partition("/")
        provider, model = provider.strip(), model.strip()
        if not provider or not model:
            return None
        return provider, model
    if isinstance(expected_model, dict):
        provider = expected_model.get("provider_id", expected_model.get("providerID"))
        model = expected_model.get("model_id", expected_model.get("id"))
        if not isinstance(provider, str) or not provider.strip():
            return None
        if not isinstance(model, str) or not model.strip():
            return None
        return provider.strip(), model.strip()
    return None


def model_mismatch_problems(session_entry: Any, expected_model: Any) -> list:
    """Compare a trace session's recorded model with an expected model.

    ``expected_model`` is either ``"provider/model"`` or a mapping with
    ``provider_id``/``model_id``. Only provider and model participate: a
    variant difference is accepted. A session entry with no parsable model is
    itself a problem, because the dispatch cannot then be pinned to the
    observer model the controller claims.
    """

    expected = _expected_model_parts(expected_model)
    if expected is None:
        return [
            "expected model must be 'provider/model' or an object with provider_id and model_id"
        ]

    if not isinstance(session_entry, dict):
        return ["trace session entry is not an object; cannot verify the recorded model"]
    session_id = session_entry.get("id")
    actual = parse_session_model(session_entry.get("model"))
    if actual is None:
        return [f"trace does not record a parsable model for session {session_id}"]

    problems: list = []
    if actual["provider_id"] != expected[0]:
        problems.append(
            f"session {session_id} provider {actual['provider_id']!r} does not match "
            f"expected provider {expected[0]!r}"
        )
    if actual["model_id"] != expected[1]:
        problems.append(
            f"session {session_id} model {actual['model_id']!r} does not match "
            f"expected model {expected[1]!r}"
        )
    return problems


def provenance_problems(
    trace: Any,
    session_id: Any,
    skill: str = "product-observer",
    expected_model: Any = None,
) -> list:
    """Check a session has a completed skill load in the runtime trace.

    Malformed traces produce a "trace unavailable" diagnostic instead of an
    exception; a session missing from ``sessions`` or lacking a completed
    ``(session_id, skill)`` event is rejected. When ``expected_model`` is
    given, the matching session's recorded model must also agree with it
    (provider/model only; see ``model_mismatch_problems``); the default keeps
    the legacy behavior unchanged.
    """

    if not isinstance(trace, dict):
        return ["runtime trace unavailable: trace must be a JSON object"]
    sessions = trace.get("sessions")
    skill_events = trace.get("skill_events")
    if not isinstance(sessions, list) or not isinstance(skill_events, list):
        return ["runtime trace unavailable: sessions and skill_events must be arrays"]

    session_ids = {s.get("id") for s in sessions if isinstance(s, dict)}
    skill_loads = {
        (e.get("session_id"), e.get("skill"))
        for e in skill_events
        if isinstance(e, dict) and e.get("status") == "completed"
    }

    problems: list = []
    if session_id not in session_ids:
        problems.append(
            f"observer session {session_id!r} not found in the runtime trace"
        )
    elif (session_id, skill) not in skill_loads:
        problems.append(
            f"observer session {session_id!r} has no completed {skill} skill load"
        )

    if expected_model is not None:
        entry = next(
            (
                s
                for s in sessions
                if isinstance(s, dict) and s.get("id") == session_id
            ),
            None,
        )
        if entry is not None:
            problems.extend(model_mismatch_problems(entry, expected_model))
    return problems


def validate_envelope(envelope: Any) -> list:
    """Validate the controller-owned adoption envelope.

    Required: non-empty ``goal_id``/``candidate_id``/``observer_session_id``/
    ``model`` strings, a 64-character lowercase sha256 ``packet_hash`` and an
    integer ``attempt`` >= 1.
    """

    if not isinstance(envelope, dict):
        return ["envelope must be a JSON object"]
    problems: list = []
    for field in ("goal_id", "candidate_id", "observer_session_id", "model"):
        value = envelope.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"envelope.{field} must be a non-empty string")
    packet_hash = envelope.get("packet_hash")
    if not isinstance(packet_hash, str) or not _HASH_RE.fullmatch(packet_hash):
        problems.append(
            "envelope.packet_hash must be a 64-character lowercase sha256 hex digest"
        )
    attempt = envelope.get("attempt")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        problems.append("envelope.attempt must be an integer >= 1")
    return problems


def _remove_stale_result_temps(target: Path) -> None:
    """Delete leftover ``result.json*.tmp`` files before any write.

    A temp file must never be promoted to a result; it is cleaned silently so
    the caller's problem list stays free of bookkeeping noise.
    """

    try:
        entries = list(target.parent.iterdir())
    except OSError:
        return
    for entry in entries:
        name = entry.name
        if entry.is_file() and name.endswith(".tmp") and target.name in name:
            try:
                entry.unlink()
            except OSError:
                pass


def _reject_adoption(
    cdir: Path,
    phase: str,
    payload: Any,
    problems: Sequence[str],
    run_id: str,
    attempt_id: str,
    received_at: Optional[str],
) -> Tuple[None, list]:
    """Record the raw attempt for a rejected adoption; never writes result.json."""

    record_dir = run_dir(cdir, phase, run_id)
    if attempt_id is None:
        attempt_id = next_attempt_id(record_dir)
    if received_at is None:
        received_at = _utc_now()
    problems = list(problems)
    try:
        raw_text = json.dumps(payload, ensure_ascii=False, indent=2)
    except (TypeError, ValueError) as exc:
        problems.append(f"payload is not JSON-serializable: {exc}")
        return None, problems
    try:
        record_attempt(
            record_dir,
            attempt_id,
            raw_text,
            payload if isinstance(payload, dict) else None,
            problems,
            received_at,
        )
    except Exception as exc:  # noqa: BLE001 - any write failure must be reported
        problems.append(f"failed to record attempt: {exc}")
    return None, problems


def adopt_result(
    cdir: Any,
    project_root: Any,
    phase: str,
    payload: Any,
    envelope: Any,
    trace: Any,
    run_id: Optional[str] = None,
    attempt_id: Optional[str] = None,
    received_at: Optional[str] = None,
) -> Tuple[Optional[Path], list]:
    """Validate and archive one received observation result (S08a-2).

    Deviations are recorded as an attempt (raw text + errors) under
    ``<cdir>/<phase>/<run-id>/attempts/`` and never produce ``result.json``.
    On success the accepted result (payload plus controller envelope) is
    written create-only; an identical existing file is an idempotent success
    and a differing one is a conflict that leaves the file untouched.
    """

    cdir = Path(cdir)
    project_root = Path(project_root)

    if phase not in _ADOPT_PHASES:
        return None, [f"phase must be one of {_ADOPT_PHASES}: {phase!r}"]

    if run_id is None:
        run_id = allocate_run_id(cdir, phase)
    record_dir = run_dir(cdir, phase, run_id)
    if attempt_id is None:
        attempt_id = next_attempt_id(record_dir)
    _remove_stale_result_temps(result_path(cdir, phase, run_id))

    if not isinstance(payload, dict):
        return _reject_adoption(
            cdir,
            phase,
            payload,
            ["payload must be a JSON object"],
            run_id,
            attempt_id,
            received_at,
        )
    if payload.get("phase") != phase:
        return _reject_adoption(
            cdir,
            phase,
            payload,
            [f"payload.phase is {payload.get('phase')!r}, expected {phase!r}"],
            run_id,
            attempt_id,
            received_at,
        )

    if _contract is None:
        return _reject_adoption(
            cdir, phase, payload, [_CONTRACT_UNAVAILABLE], run_id, attempt_id, received_at
        )
    contract_problems = list(_contract.validate_result_payload(payload, phase))
    if contract_problems:
        return _reject_adoption(
            cdir, phase, payload, contract_problems, run_id, attempt_id, received_at
        )

    envelope_problems = validate_envelope(envelope)
    if envelope_problems:
        return _reject_adoption(
            cdir, phase, payload, envelope_problems, run_id, attempt_id, received_at
        )

    if received_at is None:
        received_at = _utc_now()
    elif not isinstance(received_at, str) or not received_at.strip():
        return _reject_adoption(
            cdir,
            phase,
            payload,
            ["received_at must be a non-empty string"],
            run_id,
            attempt_id,
            None,
        )

    conflicts: list = []
    for field in _contract.CONTROLLER_FIELDS:
        if field in envelope and field in payload:
            if canonical_bytes(payload[field]) != canonical_bytes(envelope[field]):
                conflicts.append(
                    f"payload field {field!r} conflicts with the controller envelope"
                )
    if conflicts:
        return _reject_adoption(
            cdir, phase, payload, conflicts, run_id, attempt_id, received_at
        )

    provenance = provenance_problems(trace, envelope.get("observer_session_id"))
    if provenance:
        return _reject_adoption(
            cdir, phase, payload, provenance, run_id, attempt_id, received_at
        )

    evidence = evidence_ref_problems(cdir, project_root, payload)
    if evidence:
        return _reject_adoption(
            cdir, phase, payload, evidence, run_id, attempt_id, received_at
        )

    accepted = dict(payload)
    accepted.update(envelope)
    accepted["received_at"] = received_at
    recheck = list(_contract.validate_result_payload(accepted, phase))
    if recheck:
        return _reject_adoption(
            cdir, phase, payload, recheck, run_id, attempt_id, received_at
        )

    try:
        raw_text = json.dumps(payload, ensure_ascii=False, indent=2)
    except (TypeError, ValueError) as exc:
        return None, [f"payload is not JSON-serializable: {exc}"]
    try:
        record_attempt(record_dir, attempt_id, raw_text, payload, [], received_at)
    except Exception as exc:  # noqa: BLE001 - any write failure must be reported
        return None, [f"failed to record attempt: {exc}"]

    target = result_path(cdir, phase, run_id)
    if target.exists():
        existing, load_problems = load_result(target)
        if load_problems:
            return None, [
                f"result.json conflict: existing file is unreadable: {load_problems[0]}"
            ]
        if canonical_bytes(existing) == canonical_bytes(accepted):
            return target, []
        return None, [
            f"result.json conflict: {target} already exists with different content"
        ]

    try:
        _write_new_json(target, accepted)
    except ValueError as exc:
        return None, [f"result.json conflict: {exc}"]
    return target, []


def load_result(path: Any) -> Tuple[Optional[dict], list]:
    """Type-safe read of an accepted ``result.json`` (UTF-8 with BOM allowed)."""

    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return None, [f"cannot read result file {target}: {exc}"]
    try:
        value = json.loads(text)
    except ValueError as exc:
        return None, [f"invalid JSON: {exc}"]
    if not isinstance(value, dict):
        return None, [f"result file must contain a JSON object: {target}"]
    return value, []


# ---------------------------------------------------------------------------
# S08b: file locking, product-audit sidecar updates, and review adoption
# ---------------------------------------------------------------------------

import hashlib
import time
from contextlib import contextmanager

_SIDECAR_SCHEMA = "product-audit/2"
_SIDECAR_LOCK_SUFFIX = ".lock"
_SIDECAR_REF_KEYS = ("discover_ref", "compare_ref", "review_ref")
_PHASE_REF_FIELDS = {
    "discover": "discover_ref",
    "compare": "compare_ref",
    "review": "review_ref",
}
_REVIEW_PHASE = "review"
_REVIEW_ENVELOPE_FIELDS = (
    "reviewer_session_id",
    "model",
    "discover_hash",
    "compare_hash",
    "reviewed_at",
    "received_at",
    "attempt",
)
_LOCK_POLL_SECONDS = 0.05


def _quiet_unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _stat_identity(info: Any) -> tuple:
    return (info.st_mtime_ns, info.st_size, getattr(info, "st_ino", None))


def _is_older_than(info: Any, stale_after: Any) -> bool:
    try:
        return (time.time() - info.st_mtime) > float(stale_after)
    except (TypeError, ValueError):
        return False


def _lock_state(target: Path, stale_after: Any) -> str:
    """Classify the lock file as ``"gone"``, ``"held"`` or ``"stale"``.

    ``"gone"`` means the path is free and the caller should retry immediately.
    A file older than ``stale_after`` is only reported stale when an immediate
    re-stat observes the same identity, so a lock that was replaced in the
    meantime is never deleted by mistake.
    """

    try:
        first = target.stat()
    except FileNotFoundError:
        return "gone"
    except OSError:
        return "held"
    if not _is_older_than(first, stale_after):
        return "held"
    try:
        second = target.stat()
    except FileNotFoundError:
        return "gone"
    except OSError:
        return "held"
    if _stat_identity(first) != _stat_identity(second):
        return "held"
    return "stale"


@contextmanager
def file_lock(lock_path: Any, timeout: float = 10.0, stale_after: float = 120.0):
    """Exclusive advisory lock held by the existence of ``lock_path``.

    The lock file is created with ``O_CREAT | O_EXCL`` so acquisition is
    atomic for both threads and processes. A lock older than ``stale_after``
    seconds is deleted and retried; waiting is a fixed 0.05s backoff until
    ``timeout`` seconds have passed, at which point ``TimeoutError`` names the
    lock path. The file is removed in ``finally``.
    """

    target = Path(lock_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.0, float(timeout))
    acquired = False
    while not acquired:
        try:
            handle = os.open(str(target), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except OSError as exc:
            state = _lock_state(target, stale_after)
            if state == "gone":
                continue
            if state == "stale":
                _quiet_unlink(target)
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"timed out waiting for lock: {target} ({exc})"
                ) from exc
            time.sleep(min(_LOCK_POLL_SECONDS, remaining))
        else:
            os.close(handle)
            acquired = True
    try:
        yield target
    finally:
        _quiet_unlink(target)


def load_sidecar(sidecar_path: Any) -> Tuple[Optional[dict], list]:
    """Type-safe read of a product-audit sidecar.

    A missing file is ``(None, [])`` (callers may create it); an unreadable,
    non-JSON or non-object file returns the diagnostic list instead.
    """

    target = Path(sidecar_path)
    if not target.exists():
        return None, []
    try:
        text = target.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return None, [f"cannot read sidecar {target}: {exc}"]
    try:
        value = json.loads(text)
    except ValueError as exc:
        return None, [f"invalid JSON: {exc}"]
    if not isinstance(value, dict):
        return None, [f"sidecar must contain a JSON object: {target}"]
    return value, []


def _write_replace_json(path: Any, value: Any) -> None:
    """Atomically replace ``path`` with ``value`` as UTF-8 JSON.

    The temporary file lives in the target directory so ``os.replace`` is a
    same-filesystem rename; a failure never touches the original bytes.
    """

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    handle, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
        os.replace(tmp_path, target)
    except Exception:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def _relative_posix_problems(value: Any) -> list:
    if not isinstance(value, str) or not value.strip():
        return ["result_rel_path must be a non-empty string"]
    problems: list = []
    if value.startswith("/") or "\\" in value:
        problems.append(
            f"result_rel_path must be a project-relative posix path: {value}"
        )
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        problems.append(f"result_rel_path must stay project-relative: {value}")
    return problems


def _sidecar_for_update(
    existing: Optional[dict], goal_id: str, candidate_id: str
) -> Tuple[Optional[dict], list]:
    if existing is None:
        return (
            {
                "schema": _SIDECAR_SCHEMA,
                "goal_id": goal_id,
                "current_candidate": candidate_id,
                "rounds": [],
            },
            [],
        )
    sidecar = dict(existing)
    sidecar["schema"] = _SIDECAR_SCHEMA
    sidecar["goal_id"] = goal_id
    sidecar["current_candidate"] = candidate_id
    rounds = sidecar.get("rounds")
    if rounds is None:
        sidecar["rounds"] = []
    elif not isinstance(rounds, list):
        return None, ["sidecar.rounds must be an array"]
    return sidecar, []


def update_sidecar(
    sidecar_path: Any,
    goal_id: Any,
    candidate_id: Any,
    phase: Any,
    result_rel_path: Any,
) -> Tuple[Optional[dict], list]:
    """Register one archived phase result in the product-audit sidecar.

    Runs the read-modify-write under ``<sidecar>.lock`` (see ``file_lock``).
    The schema is normalized to ``product-audit/2``; ``goal_id`` and
    ``current_candidate`` take the argument values while every other field of
    an existing sidecar is preserved. The round of ``candidate_id`` is
    appended when absent and only the ref of ``phase`` is ever modified, so
    other phases and all historical rounds survive untouched. Writes are
    atomic; a failure leaves the original file byte-for-byte unchanged.
    """

    problems: list = []
    for label, value in (("goal_id", goal_id), ("candidate_id", candidate_id)):
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{label} must be a non-empty string")
    if phase not in _PHASE_REF_FIELDS:
        problems.append(
            f"phase must be one of {tuple(_PHASE_REF_FIELDS)}: {phase!r}"
        )
    problems.extend(_relative_posix_problems(result_rel_path))
    if problems:
        return None, problems

    target = Path(sidecar_path)
    lock_path = target.with_name(target.name + _SIDECAR_LOCK_SUFFIX)
    with file_lock(lock_path):
        existing, load_problems = load_sidecar(target)
        if load_problems:
            return None, load_problems
        sidecar, problems = _sidecar_for_update(existing, goal_id, candidate_id)
        if problems:
            return None, problems
        rounds = sidecar["rounds"]
        entry = None
        for item in rounds:
            if isinstance(item, dict) and item.get("candidate_id") == candidate_id:
                entry = item
                break
        if entry is None:
            entry = {
                "candidate_id": candidate_id,
                "discover_ref": "",
                "compare_ref": "",
                "review_ref": "",
            }
            rounds.append(entry)
        for key in _SIDECAR_REF_KEYS:
            if not isinstance(entry.get(key), str):
                entry[key] = ""
        entry[_PHASE_REF_FIELDS[phase]] = result_rel_path
        try:
            _write_replace_json(target, sidecar)
        except OSError as exc:
            return None, [f"failed to write sidecar {target}: {exc}"]
        return sidecar, []


def validate_review_envelope(envelope: Any) -> list:
    """Validate the controller-owned review adoption envelope.

    Required: non-empty ``reviewer_session_id``/``model`` strings and an
    integer ``attempt`` >= 1. ``goal_id``/``candidate_id`` are optional but
    must be non-empty strings when present; ``received_at`` is generated by
    the caller when absent.
    """

    if not isinstance(envelope, dict):
        return ["envelope must be a JSON object"]
    problems: list = []
    for field in ("reviewer_session_id", "model"):
        value = envelope.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"envelope.{field} must be a non-empty string")
    attempt = envelope.get("attempt")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        problems.append("envelope.attempt must be an integer >= 1")
    for field in ("goal_id", "candidate_id"):
        if field in envelope:
            value = envelope[field]
            if not isinstance(value, str) or not value.strip():
                problems.append(
                    f"envelope.{field} must be a non-empty string when present"
                )
    if "received_at" in envelope:
        value = envelope["received_at"]
        if not isinstance(value, str) or not value.strip():
            problems.append(
                "envelope.received_at must be a non-empty string when present"
            )
    return problems


def _file_sha256(path: Any) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_accepted_result(
    cdir: Path,
    phase: str,
    payload: Any,
    accepted: dict,
    run_id: str,
    attempt_id: str,
    received_at: str,
) -> Tuple[Optional[Path], list]:
    """Shared adoption tail: record the attempt, then create-only the result.

    An identical existing ``result.json`` is an idempotent success; a differing
    one is a conflict that leaves the file untouched.
    """

    record_dir = run_dir(cdir, phase, run_id)
    try:
        raw_text = json.dumps(payload, ensure_ascii=False, indent=2)
    except (TypeError, ValueError) as exc:
        return None, [f"payload is not JSON-serializable: {exc}"]
    try:
        record_attempt(record_dir, attempt_id, raw_text, payload, [], received_at)
    except Exception as exc:  # noqa: BLE001 - any write failure must be reported
        return None, [f"failed to record attempt: {exc}"]

    target = result_path(cdir, phase, run_id)
    if target.exists():
        existing, load_problems = load_result(target)
        if load_problems:
            return None, [
                f"result.json conflict: existing file is unreadable: {load_problems[0]}"
            ]
        if canonical_bytes(existing) == canonical_bytes(accepted):
            return target, []
        return None, [
            f"result.json conflict: {target} already exists with different content"
        ]

    try:
        _write_new_json(target, accepted)
    except ValueError as exc:
        return None, [f"result.json conflict: {exc}"]
    return target, []


def adopt_review(
    cdir: Any,
    project_root: Any,
    payload: Any,
    envelope: Any,
    discover_path: Any,
    compare_path: Any,
    trace: Any,
    run_id: Optional[str] = None,
    attempt_id: Optional[str] = None,
    received_at: Optional[str] = None,
) -> Tuple[Optional[Path], list]:
    """Validate and archive one received review (S08b).

    The payload must satisfy ``validate_review_payload``; the envelope must
    carry a reviewer session, model, and attempt (``received_at`` is generated
    when absent; ``goal_id``/``candidate_id`` are preserved when present).
    ``discover_hash``/``compare_hash`` are computed from the archived phase
    results and written into the accepted record; a payload or envelope hash
    that disagrees with the computed digest is rejected. Provenance requires a
    completed ``reviewer`` skill load in the runtime trace. Rejections are
    recorded as attempts under ``<cdir>/review/<run-id>/attempts/``; accepted
    reviews land create-only at ``<cdir>/review/<run-id>/result.json`` with the
    same idempotent/conflicting semantics as ``adopt_result``.
    """

    cdir = Path(cdir)
    project_root = Path(project_root)

    if run_id is None:
        run_id = allocate_run_id(cdir, _REVIEW_PHASE)
    record_dir = run_dir(cdir, _REVIEW_PHASE, run_id)
    if attempt_id is None:
        attempt_id = next_attempt_id(record_dir)
    _remove_stale_result_temps(result_path(cdir, _REVIEW_PHASE, run_id))

    if not isinstance(payload, dict):
        return _reject_adoption(
            cdir,
            _REVIEW_PHASE,
            payload,
            ["payload must be a JSON object"],
            run_id,
            attempt_id,
            received_at,
        )

    if _contract is None:
        return _reject_adoption(
            cdir, _REVIEW_PHASE, payload, [_CONTRACT_UNAVAILABLE], run_id, attempt_id, received_at
        )
    contract_problems = list(_contract.validate_review_payload(payload))
    if contract_problems:
        return _reject_adoption(
            cdir, _REVIEW_PHASE, payload, contract_problems, run_id, attempt_id, received_at
        )

    envelope_problems = validate_review_envelope(envelope)
    if envelope_problems:
        return _reject_adoption(
            cdir, _REVIEW_PHASE, payload, envelope_problems, run_id, attempt_id, received_at
        )

    conflicts: list = []
    for field in _REVIEW_ENVELOPE_FIELDS:
        if field in payload and field in envelope:
            if canonical_bytes(payload[field]) != canonical_bytes(envelope[field]):
                conflicts.append(
                    f"payload field {field!r} conflicts with the controller envelope"
                )
    if conflicts:
        return _reject_adoption(
            cdir, _REVIEW_PHASE, payload, conflicts, run_id, attempt_id, received_at
        )

    if received_at is None:
        from_envelope = envelope.get("received_at")
        if isinstance(from_envelope, str) and from_envelope.strip():
            received_at = from_envelope
        else:
            received_at = _utc_now()
    elif not isinstance(received_at, str) or not received_at.strip():
        return _reject_adoption(
            cdir,
            _REVIEW_PHASE,
            payload,
            ["received_at must be a non-empty string"],
            run_id,
            attempt_id,
            None,
        )

    computed: dict = {}
    hash_problems: list = []
    for label, source in (
        ("discover_hash", discover_path),
        ("compare_hash", compare_path),
    ):
        try:
            computed[label] = _file_sha256(source)
        except OSError as exc:
            hash_problems.append(f"cannot hash {label} source {source}: {exc}")
    for label in ("discover_hash", "compare_hash"):
        for carrier, value in (("payload", payload), ("envelope", envelope)):
            if label in value and canonical_bytes(value[label]) != canonical_bytes(
                computed.get(label)
            ):
                hash_problems.append(
                    f"{carrier} {label} conflicts with the archived result it names"
                )
    if hash_problems:
        return _reject_adoption(
            cdir, _REVIEW_PHASE, payload, hash_problems, run_id, attempt_id, received_at
        )

    provenance = provenance_problems(
        trace, envelope.get("reviewer_session_id"), skill="reviewer"
    )
    if provenance:
        return _reject_adoption(
            cdir, _REVIEW_PHASE, payload, provenance, run_id, attempt_id, received_at
        )

    accepted = dict(payload)
    accepted.update(envelope)
    accepted["discover_hash"] = computed["discover_hash"]
    accepted["compare_hash"] = computed["compare_hash"]
    accepted["received_at"] = received_at

    return _archive_accepted_result(
        cdir, _REVIEW_PHASE, payload, accepted, run_id, attempt_id, received_at
    )


# ---------------------------------------------------------------------------
# S09: format-repair state machine (first answer plus at most two repairs)
# ---------------------------------------------------------------------------

from typing import Callable  # noqa: E402 - appended section, kept next to its users

_MARKER_FIELD = "repair_outcome"
_MARKER_VALUE = "needs-observation"
_MARKER_EXAMPLE = '{"repair_outcome": "needs-observation", "reason": "<缺少什么信息>"}'


def _repair_marker(payload: Any) -> Tuple[bool, Optional[str]]:
    """Recognize the only allowed payload-less outcome of a repair turn.

    A marker is a JSON object whose ``repair_outcome`` is exactly
    ``needs-observation``. The ``reason`` is optional and normalized to a
    stripped string or ``None``; nothing else about the object is trusted.
    """

    if not isinstance(payload, dict):
        return False, None
    if payload.get(_MARKER_FIELD) != _MARKER_VALUE:
        return False, None
    reason = payload.get("reason")
    if isinstance(reason, str) and reason.strip():
        return True, reason.strip()
    return True, None


def _json_text(value: Any) -> str:
    """Serialize ``value`` for embedding; a raw string passes through."""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return repr(value)


def _repair_template_text(phase: Any) -> str:
    """The legal template JSON embedded in a repair prompt.

    Never raises: an unknown phase (e.g. a review payload being replayed
    through the result repair loop) falls back to a minimal v2 skeleton.
    """

    if _contract is not None:
        try:
            return _json_text(_contract.result_template(phase))
        except (ValueError, TypeError):
            pass
    fallback_phase = phase if phase in ("discover", "compare") else "discover"
    return _json_text({"schema": "product-observation/2", "phase": fallback_phase})


def _result_schema_name() -> str:
    if _contract is not None:
        return getattr(_contract, "SCHEMA_RESULT", "product-observation/2")
    return "product-observation/2"


def repair_prompt(
    phase: Any,
    payload: Any,
    problems: Any,
    attempt_number: int,
    max_repairs: int = 2,
) -> str:
    """Build the self-contained prompt for one format-only repair turn.

    The prompt states which repair this is, forbids product interaction and
    new facts, quotes the original payload, lists every validation error,
    embeds the full legal template, and offers exactly two legal replies
    (a corrected payload or the ``needs-observation`` marker).
    """

    if isinstance(problems, (list, tuple)):
        items = [str(problem) for problem in problems]
    elif problems is None:
        items = []
    else:
        items = [str(problems)]
    if items:
        error_lines = "\n".join(f"- {item}" for item in items)
    else:
        error_lines = "- (no validation errors were recorded)"

    original = _json_text(payload)
    template = _repair_template_text(phase)
    schema = _result_schema_name()

    return (
        f"这是第 {attempt_number}/{max_repairs} 次格式纠偏（format repair）。"
        "只修格式，不重新观察产品。\n"
        "\n四条禁令（必须遵守）：\n"
        "1. 不要操作产品：不要运行、点击、截图或重新观察目标产品。\n"
        "2. 不要新增观察事实：不得添加新的 surface、journey、finding、证据或结论。\n"
        "3. 不要改变含义：不得改变 severity/status/证据引用/结论的含义。\n"
        "4. 不要猜 controller 字段：goal_id/candidate_id/observer_session_id/model/"
        "packet_hash/received_at/attempt 由控制器填写，缺就保持缺失。\n"
        "\n【待修复的原始 payload】\n"
        "```json\n" + original + "\n```\n"
        "\n【精确校验错误（逐条修复）】\n" + error_lines + "\n"
        "\n【完整合法模板（只在原事实范围内补齐格式，可对照字段/枚举）】\n"
        "```json\n" + template + "\n```\n"
        "\n【允许的回复只有两种（整条消息必须恰好包含一个 ```json 围栏块）】\n"
        f"a) 修正后的完整 payload（schema 必须是 {schema}，不新增事实）；或\n"
        "b) 信息不足时只回复 marker：\n"
        f"```json\n{_MARKER_EXAMPLE}\n```\n"
        "如果现有信息不足以构成合法 payload（例如 surfaces 为空且没有可还原的证据引用），"
        "必须使用 marker 并说明缺少什么；禁止编造 surface/journey/证据/结论。\n"
        "\n完整说明见 product-observer/references/format-repair.md。\n"
    )


def run_format_repair(
    phase: Any,
    first_text: Any,
    send: Callable[[str], str],
    *,
    run_dir: Any = None,
    max_repairs: int = 2,
    received_at: Optional[str] = None,
) -> dict:
    """First answer plus at most ``max_repairs`` format-only repairs.

    Each received text is parsed with ``parse_single_payload``. A marker ends
    the run as ``needs-observation``. Otherwise the payload is validated with
    ``observation_contract.validate_result_payload``; valid ends as
    ``adopted`` and invalid triggers ``repair_prompt`` + ``send`` until the
    repair budget is spent. A ``send`` exception ends as ``failed``.

    ``run_dir`` (when given) receives one ``record_attempt`` per received
    text with incrementing attempt ids. Any malformed input terminates with
    a status instead of raising; only a failing ``send`` is captured.
    """

    empty = {
        "payload": None,
        "problems": [],
        "repair_count": 0,
        "attempts": 0,
        "reason": None,
    }

    try:
        limit = max(0, int(max_repairs))
    except (TypeError, ValueError):
        limit = 2

    if _contract is None:
        return {
            **empty,
            "status": "needs-observation",
            "problems": [_CONTRACT_UNAVAILABLE],
            "reason": _CONTRACT_UNAVAILABLE,
        }

    try:
        record_dir = None if run_dir is None else Path(run_dir)
    except TypeError:
        record_dir = None

    if not isinstance(received_at, str) or not received_at.strip():
        received_at = _utc_now()

    record_failures: list = []

    def store(raw_text: Any, parsed: Optional[dict], errors: Sequence[str]) -> None:
        if record_dir is None:
            return
        try:
            attempt_id = next_attempt_id(record_dir)
            record_attempt(
                record_dir, attempt_id, raw_text, parsed, errors, received_at
            )
        except Exception as exc:  # noqa: BLE001 - recording must never crash the run
            record_failures.append(f"failed to record attempt: {exc}")

    text = first_text
    attempts = 0
    repairs = 0

    while True:
        attempts += 1
        payload, parse_problems = parse_single_payload(text)
        errors = list(parse_problems)

        if payload is not None:
            is_marker, marker_reason = _repair_marker(payload)
        else:
            is_marker, marker_reason = False, None

        if is_marker:
            store(text, payload, [])
            return {
                "status": "needs-observation",
                "payload": None,
                "problems": list(record_failures),
                "repair_count": repairs,
                "attempts": attempts,
                "reason": marker_reason
                or "model reported needs-observation without a reason",
            }

        if payload is not None:
            errors = list(_contract.validate_result_payload(payload, phase))

        store(text, payload, errors)

        if payload is not None and not errors:
            return {
                "status": "adopted",
                "payload": payload,
                "problems": list(record_failures),
                "repair_count": repairs,
                "attempts": attempts,
                "reason": None,
            }

        if repairs >= limit:
            return {
                "status": "needs-observation",
                "payload": None,
                "problems": list(errors) + list(record_failures),
                "repair_count": repairs,
                "attempts": attempts,
                "reason": (
                    f"format repair limit reached after {attempts} attempt(s): "
                    f"the reply is still not a valid {phase} payload"
                ),
            }

        repairs += 1
        prompt = repair_prompt(
            phase,
            payload if payload is not None else text,
            errors,
            repairs,
            limit,
        )
        try:
            text = send(prompt)
        except Exception as exc:  # noqa: BLE001 - caller-provided send
            return {
                "status": "failed",
                "payload": None,
                "problems": list(record_failures),
                "repair_count": repairs,
                "attempts": attempts,
                "reason": f"send failed: {type(exc).__name__}: {exc}",
            }

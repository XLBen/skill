#!/usr/bin/env python3
"""S18: observation resume planning, coverage merge, no-progress breaker, leases.

A resumed observation run must stay pinned to what the previous result actually
observed, so the controller rules are fail-closed:

- One run is one (phase, candidate, model, environment) combination and keeps
  one model: a model or environment change starts a new run, never an in-place
  resume. Only a ``budget-exhausted`` result offers a ``continuation`` cursor;
  every other stop reason is rejected.
- A changed candidate id starts a new round: the old observations stay history
  and are never replayed onto the new candidate.
- Old packets, results and evidence are never overwritten: resume consumes the
  continuation cursor only, and every artifact archive stays create-only.
- A UI lease (``observation-lease/1``) is required for ``ui-operate`` and
  ``backend-run`` activities and for any unknown activity (fail closed);
  ``media-analysis``, ``evidence-review`` and ``read-only`` need no UI lease.
  An unregistered, non-active or stale lease never passes.

Coverage is merged conservatively: a surface counts as covered only when a
journey whose outcome is ``covered`` or ``partial`` carries non-empty evidence
and references that surface. Findings prove contact, not coverage, so they are
recorded separately in ``finding_refs`` and never mark a surface covered.

Public API::

    resume_plan(previous, *, phase, candidate_id, model=None, environment=None) -> dict
    merge_coverage(results) -> dict
    no_progress_breaker(signatures, max_same=3) -> dict
    lease_record(resource_id, owner_session, candidate_id, acquired_at,
                 status="active", note=None) -> dict
    validate_lease(lease) -> list
    lease_required(activity) -> bool
    lease_problems(lease, *, resources, now, max_age_seconds=3600) -> list

Everything here is offline and purely structural: no process spawn, no file
I/O, no network. Validators never raise on malformed input.
"""

from datetime import datetime, timezone
from typing import Any, Optional

SCHEMA_LEASE = "observation-lease/1"

LEASE_ACTIVITIES_REQUIRED = ("ui-operate", "backend-run")
LEASE_ACTIVITIES_FREE = ("media-analysis", "evidence-review", "read-only")

_COVERAGE_OUTCOMES = ("covered", "partial")
_DEFAULT_MAX_SAME = 3
_DEFAULT_LEASE_MAX_AGE_SECONDS = 3600.0


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


# ---------------------------------------------------------------------------
# Resume planning
# ---------------------------------------------------------------------------

def resume_plan(
    previous: Any,
    *,
    phase: Any,
    candidate_id: Any,
    model: Any = None,
    environment: Any = None,
) -> dict:
    """Decide whether a budget-exhausted observation result can be resumed.

    ``previous`` is the adopted v2 result (``product-observation/2``). The
    comparison order is fixed and fail-closed:

    - not an object, or ``stop_reason != "budget-exhausted"`` -> ``reject``;
    - ``previous.phase != phase`` -> ``reject``;
    - ``previous.candidate_id != candidate_id`` -> ``new-round`` (old
      observations remain history only);
    - ``model`` or ``environment`` differs from the recorded values
      (``previous.get("model")`` / ``previous.get("environment")``) ->
      ``new-run``;
    - otherwise -> ``resume`` with the recorded ``continuation`` object.

    A ``budget-exhausted`` result without an object ``continuation`` is
    malformed and rejected. Every return carries a ``reasons`` list.
    """

    if not isinstance(previous, dict):
        return {"action": "reject", "reasons": ["previous result is not a JSON object"]}

    stop_reason = previous.get("stop_reason")
    if stop_reason != "budget-exhausted":
        return {
            "action": "reject",
            "reasons": [
                f"previous stop_reason is {stop_reason!r}; only "
                "'budget-exhausted' offers a continuation"
            ],
        }

    if not _nonempty_str(phase):
        return {"action": "reject", "reasons": ["phase must be a non-empty string"]}
    prev_phase = previous.get("phase")
    if prev_phase != phase:
        return {
            "action": "reject",
            "reasons": [f"previous phase is {prev_phase!r}, expected {phase!r}"],
        }

    if not _nonempty_str(candidate_id):
        return {
            "action": "reject",
            "reasons": ["candidate_id must be a non-empty string"],
        }
    prev_candidate = previous.get("candidate_id")
    if prev_candidate != candidate_id:
        return {
            "action": "new-round",
            "reasons": [
                f"candidate changed from {prev_candidate!r} to {candidate_id!r}; "
                "previous observations stay history and are never replayed"
            ],
        }

    continuation = previous.get("continuation")
    if not isinstance(continuation, dict):
        return {
            "action": "reject",
            "reasons": [
                "previous continuation must be an object when stop_reason is "
                "'budget-exhausted'"
            ],
        }

    reasons = []
    recorded_model = previous.get("model")
    if recorded_model != model:
        reasons.append(f"model changed from {recorded_model!r} to {model!r}")
    recorded_environment = previous.get("environment")
    if recorded_environment != environment:
        reasons.append(
            "environment changed from "
            f"{recorded_environment!r} to {environment!r}"
        )
    if reasons:
        return {"action": "new-run", "reasons": reasons}

    return {"action": "resume", "continuation": continuation, "reasons": []}


# ---------------------------------------------------------------------------
# Coverage merge
# ---------------------------------------------------------------------------

def _surface_record(surfaces: dict, surface_id: str) -> dict:
    record = surfaces.get(surface_id)
    if record is None:
        record = {
            "material": False,
            "covered": False,
            "evidence_refs": [],
            "finding_refs": [],
        }
        surfaces[surface_id] = record
    return record


def _merge_refs(target: list, refs: Any) -> None:
    if not isinstance(refs, (list, tuple)):
        return
    for ref in refs:
        if _nonempty_str(ref) and ref not in target:
            target.append(ref)


def merge_coverage(results: Any) -> dict:
    """Merge a batch of v2 observation results into one coverage view.

    Only journeys with ``outcome`` in ``covered``/``partial``, non-empty
    ``evidence_refs`` and a matching ``surface_ids`` entry mark a surface
    covered and donate their evidence refs. Findings are recorded in
    ``finding_refs`` for every surface they reference but never make a surface
    covered, because a finding can come from a failed path. Malformed results,
    surfaces, journeys and findings are skipped; this function never raises and
    always returns the documented shape.
    """

    surfaces: dict = {}
    if isinstance(results, (list, tuple)):
        for result in results:
            if not isinstance(result, dict):
                continue

            entries = result.get("surfaces")
            if isinstance(entries, (list, tuple)):
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    surface_id = entry.get("id")
                    if not _nonempty_str(surface_id):
                        continue
                    record = _surface_record(surfaces, surface_id)
                    if entry.get("importance") == "material":
                        record["material"] = True

            journeys = result.get("journeys")
            if isinstance(journeys, (list, tuple)):
                for journey in journeys:
                    if not isinstance(journey, dict):
                        continue
                    if journey.get("outcome") not in _COVERAGE_OUTCOMES:
                        continue
                    refs = journey.get("evidence_refs")
                    if not isinstance(refs, (list, tuple)) or not refs:
                        continue
                    surface_ids = journey.get("surface_ids")
                    if not isinstance(surface_ids, (list, tuple)):
                        continue
                    for surface_id in surface_ids:
                        record = surfaces.get(surface_id)
                        if record is None:
                            continue
                        record["covered"] = True
                        _merge_refs(record["evidence_refs"], refs)

            findings = result.get("findings")
            if isinstance(findings, (list, tuple)):
                for finding in findings:
                    if not isinstance(finding, dict):
                        continue
                    finding_id = finding.get("id")
                    if not _nonempty_str(finding_id):
                        continue
                    surface_ids = finding.get("surface_ids")
                    if not isinstance(surface_ids, (list, tuple)):
                        continue
                    for surface_id in surface_ids:
                        record = surfaces.get(surface_id)
                        if record is None:
                            continue
                        if finding_id not in record["finding_refs"]:
                            record["finding_refs"].append(finding_id)

    ordered = {surface_id: surfaces[surface_id] for surface_id in sorted(surfaces)}
    covered_material = [
        surface_id
        for surface_id in ordered
        if ordered[surface_id]["material"] and ordered[surface_id]["covered"]
    ]
    uncovered_material = [
        surface_id
        for surface_id in ordered
        if ordered[surface_id]["material"] and not ordered[surface_id]["covered"]
    ]
    return {
        "surfaces": ordered,
        "covered_material": covered_material,
        "uncovered_material": uncovered_material,
    }


# ---------------------------------------------------------------------------
# No-progress circuit breaker
# ---------------------------------------------------------------------------

def no_progress_breaker(signatures: Any, max_same: int = _DEFAULT_MAX_SAME) -> dict:
    """Trip when the trailing run of identical failure signatures is too long.

    ``signatures`` is the time-ordered list of failure signatures observed so
    far (across sessions: the caller appends instead of resetting on a new
    session). The breaker stops when the last ``count >= max_same`` entries are
    all equal. Non-list input, unknown ``max_same`` and empty lists return
    ``stop=False`` instead of raising.
    """

    try:
        limit = int(max_same)
    except (TypeError, ValueError):
        limit = _DEFAULT_MAX_SAME
    if limit < 1:
        limit = 1

    if not isinstance(signatures, (list, tuple)):
        return {
            "stop": False,
            "signature": None,
            "count": 0,
            "reason": "signatures must be a time-ordered sequence of failure signatures",
        }

    signature = None
    count = 0
    for value in reversed(signatures):
        if count == 0:
            signature = value
        elif value != signature:
            break
        count += 1

    if count >= limit:
        return {
            "stop": True,
            "signature": signature,
            "count": count,
            "reason": (
                f"no progress: failure signature repeated {count} times "
                f"(>= {limit}) without new evidence"
            ),
        }
    return {"stop": False, "signature": signature, "count": count, "reason": None}


# ---------------------------------------------------------------------------
# Observation lease
# ---------------------------------------------------------------------------

def lease_record(
    resource_id: Any,
    owner_session: Any,
    candidate_id: Any,
    acquired_at: Any,
    status: Any = "active",
    note: Any = None,
) -> dict:
    """Build an ``observation-lease/1`` record (structure only, no validation)."""

    return {
        "schema": SCHEMA_LEASE,
        "resource_id": resource_id,
        "owner_session": owner_session,
        "candidate_id": candidate_id,
        "acquired_at": acquired_at,
        "status": status,
        "note": note,
    }


def validate_lease(lease: Any) -> list:
    """Validate the structure of an ``observation-lease/1`` record.

    Returns a (possibly empty) problem list; malformed input is reported, never
    raised. ``note`` is optional and may be ``None`` or a string.
    """

    if not isinstance(lease, dict):
        return ["lease must be a JSON object"]

    problems: list = []
    if lease.get("schema") != SCHEMA_LEASE:
        problems.append(f"lease.schema must be {SCHEMA_LEASE!r}")
    for field in ("resource_id", "owner_session", "candidate_id", "acquired_at", "status"):
        if not _nonempty_str(lease.get(field)):
            problems.append(f"lease.{field} must be a non-empty string")
    note = lease.get("note")
    if note is not None and not isinstance(note, str):
        problems.append("lease.note must be a string or null")
    return problems


def lease_required(activity: Any) -> bool:
    """Whether ``activity`` requires an exclusive observation lease.

    ``ui-operate`` and ``backend-run`` require one; ``media-analysis``,
    ``evidence-review`` and ``read-only`` do not. Anything unknown (including
    non-strings) requires one, because failing closed can only over-serialize.
    """

    if activity in LEASE_ACTIVITIES_FREE:
        return False
    return True


def _parse_epoch(value: Any) -> Optional[float]:
    """Parse epoch seconds or an ISO-8601 timestamp into epoch seconds.

    Numbers pass through (``bool`` is rejected). Strings are parsed with
    ``datetime.fromisoformat`` after normalizing a trailing ``Z``; naive
    timestamps are treated as UTC. Unparsable values return ``None``.
    """

    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    return None


def lease_problems(
    lease: Any,
    *,
    resources: Any,
    now: Any,
    max_age_seconds: Any = _DEFAULT_LEASE_MAX_AGE_SECONDS,
) -> list:
    """Check a lease against the registered resources and the wall clock.

    Reported problems cover, in order: structural validation, a ``resource_id``
    absent from ``resources``, a ``status`` other than ``active`` ("not
    held"), and an ``acquired_at`` that is unparsable or older than
    ``max_age_seconds`` ("stale"). ``now`` accepts epoch seconds or an ISO-8601
    string; an unparsable ``now`` is itself a problem (fail closed). This
    function never raises.
    """

    problems = validate_lease(lease)

    try:
        limit = float(max_age_seconds)
    except (TypeError, ValueError):
        limit = _DEFAULT_LEASE_MAX_AGE_SECONDS
    if limit < 0:
        limit = 0.0

    if not isinstance(lease, dict):
        return problems

    resource_id = lease.get("resource_id")
    if _nonempty_str(resource_id):
        if resources is None or isinstance(resources, (str, bytes)):
            problems.append("resources must be a collection of resource ids")
        else:
            try:
                known = resource_id in resources
            except TypeError:
                problems.append("resources must be a collection of resource ids")
            else:
                if not known:
                    problems.append(f"lease resource not registered: {resource_id!r}")

    status = lease.get("status")
    if _nonempty_str(status) and status != "active":
        problems.append(f"lease not held: status is {status!r}")

    acquired_at = lease.get("acquired_at")
    acquired = _parse_epoch(acquired_at)
    moment = _parse_epoch(now)
    if acquired is None:
        problems.append(
            f"lease is stale: acquired_at is not a parsable timestamp: {acquired_at!r}"
        )
    if moment is None:
        problems.append("cannot evaluate lease age: now is not a parsable timestamp")
    elif acquired is not None:
        age = moment - acquired
        if age > limit:
            problems.append(
                f"lease is stale: age {age:.0f}s exceeds max_age {limit:.0f}s"
            )

    return problems

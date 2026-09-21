#!/usr/bin/env python3
"""Frozen product-observation data contract v2.

This module is the single authority for schema identifiers, enums and the
structural validation of the model-owned payloads of the product-observation
workflow. The ``validate_*`` entry points judge shape only: whether coverage
is honest, whether evidence supports a finding, and whether a review verdict
is justified remain semantic judgments owned by the independent reviewer.

Since S04 it also exposes small pure semantic helpers (``is_blocking_finding``,
``semantic_finding_problems``, ``review_verdict_consistency_problems``) so the
mechanical gate and the documentation share one executable authority order.
They never mutate their input and never raise on malformed JSON.

Controller-owned envelope fields are accepted and ignored here; they are
written at adoption time and validated by ``validate_result_envelope``.
"""

import re
from typing import Any

SCHEMA_RESULT = "product-observation/2"
SCHEMA_REVIEW = "product-observation-review/2"
SCHEMA_CANDIDATE = "product-candidate/2"
SCHEMA_AUDIT = "product-audit/2"
SCHEMA_PACKET = "workflow-observer-packet/2"
SCHEMA_GATE = "product-audit-gate/2"

PHASES = ("discover", "compare")
STOP_REASONS = (
    "coverage-completed",
    "budget-exhausted",
    "blocked",
    "no-backend",
    "lease-lost",
)
STOP_STATE = {
    "coverage-completed": "completed",
    "budget-exhausted": "incomplete",
    "blocked": "blocked",
    "no-backend": "blocked",
    "lease-lost": "blocked",
}
SEVERITIES = ("critical", "high", "medium", "low")
BLOCKING_SEVERITIES = {"critical", "high"}
FINDING_STATUSES = (
    "suspected",
    "confirmed",
    "intermittent",
    "resolved",
    "dismissed",
    "owner-decision",
)
BLOCKING_FINDING_STATUSES = {
    "suspected",
    "confirmed",
    "intermittent",
    "owner-decision",
}
DIFFERENCE_CLASSIFICATIONS = (
    "intended-change",
    "confirmed-defect",
    "known-old-issue",
    "under-investigation",
    "owner-decision",
)
FINDING_CATEGORIES = (
    "visual",
    "functional",
    "ux",
    "content",
    "performance",
    "console",
    "accessibility",
    "continuity",
)
CONFIDENCES = ("observed", "likely", "uncertain")
IMPORTANCE = ("material", "peripheral")
COVERAGE_OUTCOMES = ("covered", "partial", "failed")
REVIEW_JUDGMENTS = ("sufficient", "insufficient")
REVIEW_VERDICTS = ("sufficient", "needs-observation", "needs-repair", "blocked")
CONTROLLER_FIELDS = (
    "goal_id",
    "candidate_id",
    "observer_session_id",
    "model",
    "packet_hash",
    "received_at",
    "attempt",
)

HASH_RE = re.compile(r"^[0-9a-f]{64}$")

# Tuples (not sets) keep enum membership safe for unhashable JSON values such
# as dict/list, matching the "validators never raise" contract.
_BLOCKING_SEVERITY_VALUES = tuple(sorted(BLOCKING_SEVERITIES))
_BLOCKING_STATUS_VALUES = tuple(sorted(BLOCKING_FINDING_STATUSES))

_RESULT_TOP_FIELDS = frozenset(
    {
        "schema",
        "phase",
        "stop_reason",
        "surfaces",
        "journeys",
        "findings",
        "unobserved",
        "capability_gaps",
        "continuation",
        "evidence_refs",
        "notes",
    }
)
_SURFACE_FIELDS = frozenset({"id", "name", "importance", "modes"})
_JOURNEY_FIELDS = frozenset({"id", "surface_ids", "evidence_refs", "outcome", "notes"})
_FINDING_FIELDS = frozenset(
    {
        "id",
        "surface_ids",
        "severity",
        "category",
        "confidence",
        "observed",
        "expected_basis",
        "reproduction",
        "evidence_refs",
        "status",
        "difference_classification",
        "dismissal_reason",
        "owner_decision_ref",
        "resolution_ref",
        "notes",
    }
)
_UNOBSERVED_FIELDS = frozenset({"surface_id", "reason"})
_GAP_FIELDS = frozenset({"channel", "reason", "evidence_refs"})
_CONTINUATION_FIELDS = frozenset(
    {
        "visited_surface_ids",
        "pending_surface_ids",
        "checkpoint",
        "state_ref",
        "previous_result_sha256",
    }
)
_RESOLUTION_FIELDS = frozenset({"candidate_id", "finding_id"})
_REVIEW_TOP_FIELDS = frozenset(
    {
        "schema",
        "findings_validity",
        "coverage_adequacy",
        "verdict",
        "notes",
        "related_finding_ids",
    }
)
_REVIEW_ENVELOPE_FIELDS = frozenset(
    {
        "reviewer_session_id",
        "model",
        "discover_hash",
        "compare_hash",
        "reviewed_at",
        "received_at",
        "attempt",
    }
)


def result_stop_state(stop_reason: Any) -> str | None:
    """Derive the completion state of a round from its stop reason."""

    if not isinstance(stop_reason, str) or stop_reason not in STOP_REASONS:
        return None
    return STOP_STATE[stop_reason]


def _require_nonempty_str(value: Any, label: str, problems: list[str]) -> bool:
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{label} must be a non-empty string")
        return False
    return True


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_string_array(
    value: Any, label: str, problems: list[str], allow_empty: bool = False
) -> bool:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        problems.append(f"{label} must be an array of non-empty strings")
        return False
    if not value and not allow_empty:
        problems.append(f"{label} must not be empty")
        return False
    return True


def _check_surface_refs(
    value: Any,
    label: str,
    surface_ids: set[str],
    problems: list[str],
    require_nonempty: bool,
) -> list[str]:
    refs: list[str] = []
    if not _check_string_array(value, label, problems, allow_empty=not require_nonempty):
        return refs
    for ref in value:
        if ref not in surface_ids:
            problems.append(f"{label} references unknown surface {ref!r}")
        else:
            refs.append(ref)
    return refs


def _check_unknown_keys(
    obj: dict[Any, Any], allowed: frozenset[str], label: str, problems: list[str]
) -> None:
    for key in obj:
        if key not in allowed:
            problems.append(f"{label} has unknown field {key!r}")


def _check_notes(value: Any, label: str, problems: list[str]) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        problems.append(f"{label} must be a non-empty string when present")


def validate_result_payload(payload: Any, phase: str | None = None) -> list[str]:
    """Validate a ``product-observation/2`` payload.

    ``phase`` optionally pins the expected phase; when it is omitted the
    phase declared in the payload drives the phase-conditional rules.
    Controller envelope keys are ignored, never required.
    """

    problems: list[str] = []
    if not isinstance(payload, dict):
        return ["result payload must be a JSON object"]
    _check_unknown_keys(
        payload, _RESULT_TOP_FIELDS | frozenset(CONTROLLER_FIELDS), "result", problems
    )

    if payload.get("schema") != SCHEMA_RESULT:
        problems.append(f"result.schema must be {SCHEMA_RESULT}")

    declared_phase = payload.get("phase")
    if declared_phase not in PHASES:
        problems.append(f"result.phase must be one of {PHASES}")
    if phase is not None:
        if phase not in PHASES:
            problems.append(f"expected phase must be one of {PHASES}")
        elif declared_phase != phase:
            problems.append(f"result.phase is {declared_phase!r}, expected {phase!r}")
    effective_phase = phase if phase in PHASES else declared_phase

    stop_reason = payload.get("stop_reason")
    if stop_reason not in STOP_REASONS:
        problems.append(f"result.stop_reason must be one of {STOP_REASONS}")
    stop_state = result_stop_state(stop_reason)

    surfaces = payload.get("surfaces")
    surface_ids: set[str] = set()
    material_ids: set[str] = set()
    if not isinstance(surfaces, list):
        problems.append("result.surfaces must be an array")
        surfaces = []
    if stop_state != "blocked" and not surfaces:
        problems.append(
            "result.surfaces must be a non-empty array unless the round is blocked"
        )
    for index, item in enumerate(surfaces):
        where = f"result.surfaces[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where} must be an object")
            continue
        _check_unknown_keys(item, _SURFACE_FIELDS, where, problems)
        ident = item.get("id")
        ident_ok = _require_nonempty_str(ident, f"{where}.id", problems)
        if ident_ok:
            if ident in surface_ids:
                problems.append(f"{where}.id duplicates {ident!r}")
            else:
                surface_ids.add(ident)
        _require_nonempty_str(item.get("name"), f"{where}.name", problems)
        importance = item.get("importance")
        if importance not in IMPORTANCE:
            problems.append(f"{where}.importance must be one of {IMPORTANCE}")
        elif ident_ok and importance == "material":
            material_ids.add(ident)
        modes = item.get("modes")
        if modes is not None:
            _check_string_array(modes, f"{where}.modes", problems, allow_empty=True)

    journeys = payload.get("journeys")
    journey_ids: set[str] = set()
    journey_covered: set[str] = set()
    if not isinstance(journeys, list):
        problems.append("result.journeys must be an array")
        journeys = []
    for index, item in enumerate(journeys):
        where = f"result.journeys[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where} must be an object")
            continue
        _check_unknown_keys(item, _JOURNEY_FIELDS, where, problems)
        ident = item.get("id")
        if _require_nonempty_str(ident, f"{where}.id", problems):
            if ident in journey_ids:
                problems.append(f"{where}.id duplicates {ident!r}")
            else:
                journey_ids.add(ident)
        refs = _check_surface_refs(
            item.get("surface_ids"),
            f"{where}.surface_ids",
            surface_ids,
            problems,
            require_nonempty=True,
        )
        _check_string_array(
            item.get("evidence_refs"), f"{where}.evidence_refs", problems
        )
        outcome = item.get("outcome")
        if outcome not in COVERAGE_OUTCOMES:
            problems.append(f"{where}.outcome must be one of {COVERAGE_OUTCOMES}")
        elif outcome in ("covered", "partial"):
            journey_covered.update(refs)
        _check_notes(item.get("notes"), f"{where}.notes", problems)

    findings = payload.get("findings")
    finding_ids: set[str] = set()
    finding_covered: set[str] = set()
    if not isinstance(findings, list):
        problems.append("result.findings must be an array")
        findings = []
    for index, item in enumerate(findings):
        where = f"result.findings[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where} must be an object")
            continue
        _check_unknown_keys(item, _FINDING_FIELDS, where, problems)
        ident = item.get("id")
        if _require_nonempty_str(ident, f"{where}.id", problems):
            if ident in finding_ids:
                problems.append(f"{where}.id duplicates {ident!r}")
            else:
                finding_ids.add(ident)
        refs = _check_surface_refs(
            item.get("surface_ids"),
            f"{where}.surface_ids",
            surface_ids,
            problems,
            require_nonempty=True,
        )
        finding_covered.update(refs)
        if item.get("severity") not in SEVERITIES:
            problems.append(f"{where}.severity must be one of {SEVERITIES}")
        if item.get("category") not in FINDING_CATEGORIES:
            problems.append(f"{where}.category must be one of {FINDING_CATEGORIES}")
        if item.get("confidence") not in CONFIDENCES:
            problems.append(f"{where}.confidence must be one of {CONFIDENCES}")
        _require_nonempty_str(item.get("observed"), f"{where}.observed", problems)
        _require_nonempty_str(
            item.get("expected_basis"), f"{where}.expected_basis", problems
        )
        _require_nonempty_str(
            item.get("reproduction"), f"{where}.reproduction", problems
        )
        evidence_ok = _check_string_array(
            item.get("evidence_refs"), f"{where}.evidence_refs", problems
        )
        classification = item.get("difference_classification")
        if classification is not None and classification not in DIFFERENCE_CLASSIFICATIONS:
            problems.append(
                f"{where}.difference_classification must be one of "
                f"{DIFFERENCE_CLASSIFICATIONS}"
            )
        if effective_phase == "compare":
            if classification is None:
                problems.append(
                    f"{where}.difference_classification is required in the compare phase"
                )
        elif effective_phase == "discover":
            if classification is not None:
                problems.append(
                    f"{where}.difference_classification must be absent in the discover phase"
                )
        status = item.get("status")
        if status not in FINDING_STATUSES:
            problems.append(f"{where}.status must be one of {FINDING_STATUSES}")
        if status == "dismissed":
            _require_nonempty_str(
                item.get("dismissal_reason"), f"{where}.dismissal_reason", problems
            )
            owner_ref = item.get("owner_decision_ref")
            owner_ref_ok = isinstance(owner_ref, str) and bool(owner_ref.strip())
            if not evidence_ok and not owner_ref_ok:
                problems.append(
                    f"{where}.dismissal needs non-empty evidence_refs or owner_decision_ref"
                )
        if status == "resolved":
            resolution = item.get("resolution_ref")
            if not isinstance(resolution, dict):
                problems.append(
                    f"{where}.resolution_ref must be an object for resolved findings"
                )
            else:
                _check_unknown_keys(
                    resolution, _RESOLUTION_FIELDS, f"{where}.resolution_ref", problems
                )
                _require_nonempty_str(
                    resolution.get("candidate_id"),
                    f"{where}.resolution_ref.candidate_id",
                    problems,
                )
                _require_nonempty_str(
                    resolution.get("finding_id"),
                    f"{where}.resolution_ref.finding_id",
                    problems,
                )
            if not evidence_ok:
                problems.append(
                    f"{where} resolved findings need non-empty evidence_refs"
                )
        owner_ref = item.get("owner_decision_ref")
        if owner_ref is not None and (
            not isinstance(owner_ref, str) or not owner_ref.strip()
        ):
            problems.append(
                f"{where}.owner_decision_ref must be a non-empty string when present"
            )
        _check_notes(item.get("notes"), f"{where}.notes", problems)

    unobserved = payload.get("unobserved")
    unobserved_ids: set[str] = set()
    if not isinstance(unobserved, list):
        problems.append("result.unobserved must be an array")
        unobserved = []
    for index, item in enumerate(unobserved):
        where = f"result.unobserved[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where} must be an object")
            continue
        _check_unknown_keys(item, _UNOBSERVED_FIELDS, where, problems)
        ref = item.get("surface_id")
        if _require_nonempty_str(ref, f"{where}.surface_id", problems):
            if ref not in surface_ids:
                problems.append(
                    f"{where}.surface_id references unknown surface {ref!r}"
                )
            else:
                unobserved_ids.add(ref)
        _require_nonempty_str(item.get("reason"), f"{where}.reason", problems)

    gaps = payload.get("capability_gaps")
    described_gaps = 0
    if not isinstance(gaps, list):
        problems.append("result.capability_gaps must be an array")
        gaps = []
    for index, item in enumerate(gaps):
        where = f"result.capability_gaps[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where} must be an object")
            continue
        _check_unknown_keys(item, _GAP_FIELDS, where, problems)
        channel_ok = _require_nonempty_str(
            item.get("channel"), f"{where}.channel", problems
        )
        reason_ok = _require_nonempty_str(
            item.get("reason"), f"{where}.reason", problems
        )
        if channel_ok and reason_ok:
            described_gaps += 1
        evidence = item.get("evidence_refs")
        if evidence is not None:
            _check_string_array(
                evidence, f"{where}.evidence_refs", problems, allow_empty=True
            )

    continuation = payload.get("continuation")
    if stop_reason == "budget-exhausted":
        if continuation is None:
            problems.append(
                "result.continuation is required when stop_reason is budget-exhausted"
            )
    elif continuation is not None:
        problems.append(
            "result.continuation must be null unless stop_reason is budget-exhausted"
        )
    if continuation is not None and not isinstance(continuation, dict):
        problems.append("result.continuation must be an object or null")
    if isinstance(continuation, dict):
        _check_unknown_keys(
            continuation, _CONTINUATION_FIELDS, "result.continuation", problems
        )
        _check_string_array(
            continuation.get("visited_surface_ids"),
            "result.continuation.visited_surface_ids",
            problems,
            allow_empty=True,
        )
        _check_string_array(
            continuation.get("pending_surface_ids"),
            "result.continuation.pending_surface_ids",
            problems,
            allow_empty=True,
        )
        _require_nonempty_str(
            continuation.get("checkpoint"), "result.continuation.checkpoint", problems
        )
        for optional in ("state_ref", "previous_result_sha256"):
            value = continuation.get(optional)
            if value is not None:
                _require_nonempty_str(
                    value, f"result.continuation.{optional}", problems
                )

    evidence = payload.get("evidence_refs")
    evidence_ok = _check_string_array(
        evidence, "result.evidence_refs", problems, allow_empty=True
    )
    if evidence_ok and stop_state == "completed" and not evidence:
        problems.append(
            "result.evidence_refs must not be empty when stop_state is completed"
        )

    if stop_reason == "coverage-completed":
        covered = journey_covered | finding_covered
        for ident in sorted(material_ids):
            if ident not in covered and ident not in unobserved_ids:
                problems.append(
                    f"material surface {ident!r} is neither covered nor unobserved"
                )
        for ident in sorted(material_ids & unobserved_ids):
            problems.append(
                f"material surface {ident!r} is unobserved; coverage is incomplete "
                f"(use budget-exhausted)"
            )

    if stop_state == "blocked":
        notes = payload.get("notes")
        notes_ok = isinstance(notes, str) and bool(notes.strip())
        if not notes_ok and described_gaps == 0:
            problems.append(
                "blocked rounds need non-empty notes or capability_gaps explaining the stop"
            )

    notes = payload.get("notes")
    if notes is not None and (not isinstance(notes, str) or not notes.strip()):
        problems.append("result.notes must be a non-empty string when present")

    return problems


def validate_review_payload(review: Any) -> list[str]:
    """Validate a ``product-observation-review/2`` payload.

    Controller envelope keys reserved for S08 are ignored, never required.
    """

    problems: list[str] = []
    if not isinstance(review, dict):
        return ["review payload must be a JSON object"]
    _check_unknown_keys(
        review, _REVIEW_TOP_FIELDS | _REVIEW_ENVELOPE_FIELDS, "review", problems
    )
    if review.get("schema") != SCHEMA_REVIEW:
        problems.append(f"review.schema must be {SCHEMA_REVIEW}")
    judgments = {}
    for field in ("findings_validity", "coverage_adequacy"):
        value = review.get(field)
        judgments[field] = value
        if value not in REVIEW_JUDGMENTS:
            problems.append(f"review.{field} must be one of {REVIEW_JUDGMENTS}")
    verdict = review.get("verdict")
    if verdict not in REVIEW_VERDICTS:
        problems.append(f"review.verdict must be one of {REVIEW_VERDICTS}")
    if verdict == "sufficient":
        for field, value in judgments.items():
            if value != "sufficient":
                problems.append(
                    f"review.verdict sufficient requires {field} to be sufficient"
                )
    notes = review.get("notes")
    if not isinstance(notes, str) or not notes.strip():
        problems.append("review.notes must be a non-empty string")
    related = review.get("related_finding_ids")
    if related is not None:
        _check_string_array(
            related, "review.related_finding_ids", problems, allow_empty=True
        )
    return problems


def is_blocking_finding(finding: Any) -> bool:
    """True when severity and status both place a finding in the blocking sets.

    This is the single executable definition of "open blocker"; the gate and
    the review decision table must agree with it. Malformed input is false,
    never an exception.
    """

    if not isinstance(finding, dict):
        return False
    return (
        finding.get("severity") in _BLOCKING_SEVERITY_VALUES
        and finding.get("status") in _BLOCKING_STATUS_VALUES
    )


def semantic_finding_problems(finding: Any, phase: str | None = None) -> list[str]:
    """Semantic checks a blind structural validator cannot express.

    The authority order is: approved goal / owner decision > candidate
    README or user-facing documentation > historical behavior. Consequently a
    ``critical``/``high`` finding can only be dismissed, or excused as an
    ``intended-change``, by citing an owner decision; README or implementer
    prose alone is rejected. Structural existence is still enforced by
    ``validate_result_payload`` — this function adds the semantics:

    - ``dismissed`` at blocking severity needs a non-empty ``owner_decision_ref``;
    - ``difference_classification == intended-change`` at blocking severity
      needs a non-empty ``owner_decision_ref``;
    - ``resolved`` confirms ``resolution_ref.candidate_id`` is structurally
      present (cross-round verification stays with the gate);
    - ``known-old-issue`` needs non-empty ``evidence_refs`` and
      ``owner-decision`` needs ``notes`` or an ``owner_decision_ref``.
    """

    problems: list[str] = []
    if not isinstance(finding, dict):
        return ["finding must be an object"]
    ident = finding.get("id")
    where = f"finding {ident!r}" if _nonempty_str(ident) else "finding"
    severity = finding.get("severity")
    status = finding.get("status")
    classification = finding.get("difference_classification")
    blocking_severity = severity in _BLOCKING_SEVERITY_VALUES
    owner_ref_ok = _nonempty_str(finding.get("owner_decision_ref"))
    notes_ok = _nonempty_str(finding.get("notes"))
    evidence = finding.get("evidence_refs")
    evidence_ok = (
        isinstance(evidence, list)
        and bool(evidence)
        and all(_nonempty_str(item) for item in evidence)
    )

    if status == "dismissed" and blocking_severity and not owner_ref_ok:
        problems.append(
            f"{where}: dismissed {severity} finding needs a non-empty "
            "owner_decision_ref; README or implementer intent cannot dismiss it"
        )
    if phase != "discover":
        if (
            classification == "intended-change"
            and blocking_severity
            and not owner_ref_ok
        ):
            problems.append(
                f"{where}: intended-change at {severity} severity needs a non-empty "
                "owner_decision_ref before it can pass the gate"
            )
        if classification == "known-old-issue" and not evidence_ok:
            problems.append(
                f"{where}: known-old-issue needs non-empty evidence_refs"
            )
        if classification == "owner-decision" and not (owner_ref_ok or notes_ok):
            problems.append(
                f"{where}: owner-decision classification needs notes or "
                "owner_decision_ref to record its basis"
            )
    if status == "resolved":
        resolution = finding.get("resolution_ref")
        if not isinstance(resolution, dict) or not _nonempty_str(
            resolution.get("candidate_id")
        ):
            problems.append(
                f"{where}: resolved findings need a non-empty "
                "resolution_ref.candidate_id bound to the verifying round"
            )
    return problems


def resolution_binding_problems(
    finding: Any,
    current_candidate_id: Any,
    known_round_findings: Any,
) -> list[str]:
    """Cross-round binding check for a ``resolved`` finding.

    ``known_round_findings`` maps earlier candidate IDs to the set of finding
    IDs visible in that round's archived reports, or ``None`` when those
    reports could not be loaded. A resolved finding must cite an earlier round
    (never the current candidate) and a finding ID that round actually
    contains; unknown or unreadable rounds fail closed. Malformed input is
    ignored here and reported by the structural validator instead.
    """

    if not isinstance(finding, dict):
        return []
    if finding.get("status") != "resolved":
        return []
    resolution = finding.get("resolution_ref")
    if not isinstance(resolution, dict):
        return []
    candidate_id = resolution.get("candidate_id")
    finding_id = resolution.get("finding_id")
    if not _nonempty_str(candidate_id) or not _nonempty_str(finding_id):
        return []
    ident = finding.get("id")
    where = f"finding {ident!r}" if _nonempty_str(ident) else "resolved finding"
    rounds = known_round_findings if isinstance(known_round_findings, dict) else {}
    if candidate_id == current_candidate_id:
        return [
            f"{where}: resolution_ref.candidate_id {candidate_id!r} is the current "
            "candidate; cite an earlier verifying round"
        ]
    if candidate_id not in rounds:
        return [
            f"{where}: resolution_ref.candidate_id {candidate_id!r} is not a known "
            "earlier round"
        ]
    finding_ids = rounds[candidate_id]
    if finding_ids is None:
        return [
            f"{where}: cannot verify resolution against round {candidate_id!r}: "
            "its archived reports are unreadable"
        ]
    if finding_id not in finding_ids:
        return [
            f"{where}: resolution_ref.finding_id {finding_id!r} is not present in "
            f"round {candidate_id!r}"
        ]
    return []


def review_verdict_consistency_problems(
    review: Any, open_blocking: bool
) -> list[str]:
    """Check the review verdict against its judgments and open blockers.

    Decision table (``blocked`` is always allowed as an explicit stop):

    - any judgment ``insufficient`` -> verdict must be ``needs-observation``;
    - both judgments ``sufficient`` + open blocking findings -> ``needs-repair``;
    - both judgments ``sufficient`` + no open blockers -> ``sufficient``.

    When several reasons apply the human-readable ``notes`` must list them;
    notes are intentionally not parsed here.
    """

    if not isinstance(review, dict):
        return ["review must be an object"]
    problems: list[str] = []
    verdict = review.get("verdict")
    if verdict not in REVIEW_VERDICTS:
        problems.append(f"review.verdict must be one of {REVIEW_VERDICTS}")
        return problems
    if verdict == "blocked":
        return problems
    judgments_insufficient = (
        review.get("findings_validity") == "insufficient"
        or review.get("coverage_adequacy") == "insufficient"
    )
    if judgments_insufficient:
        if verdict != "needs-observation":
            problems.append(
                "review.verdict must be 'needs-observation' when findings_validity "
                "or coverage_adequacy is insufficient"
            )
    elif open_blocking:
        if verdict != "needs-repair":
            problems.append(
                "review.verdict must be 'needs-repair' while blocking findings "
                "remain unresolved, even when both judgments are sufficient"
            )
    elif verdict != "sufficient":
        problems.append(
            "review.verdict must be 'sufficient' when both judgments are "
            "sufficient and no blocking findings remain unresolved"
        )
    return problems


def validate_result_envelope(
    accepted: Any,
    expected_goal_id: str | None = None,
    expected_candidate_id: str | None = None,
    expected_packet_hash: str | None = None,
    expected_phase: str | None = None,
) -> list[str]:
    """Validate the controller envelope merged into an accepted result."""

    problems: list[str] = []
    if not isinstance(accepted, dict):
        return ["accepted result must be a JSON object"]

    goal_id = accepted.get("goal_id")
    _require_nonempty_str(goal_id, "envelope.goal_id", problems)
    candidate_id = accepted.get("candidate_id")
    _require_nonempty_str(candidate_id, "envelope.candidate_id", problems)
    _require_nonempty_str(
        accepted.get("observer_session_id"), "envelope.observer_session_id", problems
    )
    _require_nonempty_str(accepted.get("model"), "envelope.model", problems)
    packet_hash = accepted.get("packet_hash")
    if not isinstance(packet_hash, str) or not HASH_RE.fullmatch(packet_hash):
        problems.append(
            "envelope.packet_hash must be a 64-character lowercase sha256 hex digest"
        )
    attempt = accepted.get("attempt")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        problems.append("envelope.attempt must be an integer >= 1")
    _require_nonempty_str(accepted.get("received_at"), "envelope.received_at", problems)
    phase = accepted.get("phase")
    if phase not in PHASES:
        problems.append(f"envelope.phase must be one of {PHASES}")
    elif expected_phase is not None and phase != expected_phase:
        problems.append(f"envelope.phase is {phase!r}, expected {expected_phase!r}")

    if expected_goal_id is not None and goal_id != expected_goal_id:
        problems.append(
            f"envelope.goal_id is {goal_id!r}, expected {expected_goal_id!r}"
        )
    if expected_candidate_id is not None and candidate_id != expected_candidate_id:
        problems.append(
            f"envelope.candidate_id is {candidate_id!r}, expected {expected_candidate_id!r}"
        )
    if expected_packet_hash is not None and packet_hash != expected_packet_hash:
        problems.append(
            f"envelope.packet_hash is {packet_hash!r}, expected {expected_packet_hash!r}"
        )
    return problems


def result_template(phase: str) -> dict[str, Any]:
    """A minimal, fully valid ``product-observation/2`` example for a phase."""

    if phase not in PHASES:
        raise ValueError(f"result_template phase must be one of {PHASES}, got {phase!r}")
    payload: dict[str, Any] = {
        "schema": SCHEMA_RESULT,
        "phase": phase,
        "stop_reason": "coverage-completed",
        "surfaces": [
            {
                "id": "S-01",
                "name": "Primary entry surface",
                "importance": "material",
                "modes": ["default"],
            },
            {"id": "S-02", "name": "Secondary surface", "importance": "peripheral"},
        ],
        "journeys": [
            {
                "id": "J-01",
                "surface_ids": ["S-01", "S-02"],
                "evidence_refs": ["evidence/j01.png"],
                "outcome": "covered",
            }
        ],
        "findings": [],
        "unobserved": [],
        "capability_gaps": [],
        "continuation": None,
        "evidence_refs": ["evidence/round.md"],
        "notes": f"Minimal valid {phase} payload.",
    }
    if phase == "compare":
        payload["findings"] = [
            {
                "id": "F-01",
                "surface_ids": ["S-02"],
                "severity": "low",
                "category": "visual",
                "confidence": "observed",
                "observed": "Secondary surface label differs from the historical map.",
                "expected_basis": "Approved target and prior stable behavior agree on the label.",
                "reproduction": "Open S-02 from the primary entry and read the heading.",
                "evidence_refs": ["evidence/f01.png"],
                "status": "confirmed",
                "difference_classification": "intended-change",
            }
        ]
    return payload


def review_template() -> dict[str, Any]:
    """A minimal, fully valid ``product-observation-review/2`` example."""

    return {
        "schema": SCHEMA_REVIEW,
        "findings_validity": "sufficient",
        "coverage_adequacy": "sufficient",
        "verdict": "sufficient",
        "notes": "Both phase payloads were checked against the archived packet.",
        "related_finding_ids": [],
    }


def contract_enums() -> dict[str, Any]:
    """The canonical enum table; the contract reference embeds its exact JSON."""

    return {
        "blocking_finding_statuses": sorted(BLOCKING_FINDING_STATUSES),
        "blocking_severities": sorted(BLOCKING_SEVERITIES),
        "confidences": list(CONFIDENCES),
        "controller_fields": list(CONTROLLER_FIELDS),
        "coverage_outcomes": list(COVERAGE_OUTCOMES),
        "difference_classifications": list(DIFFERENCE_CLASSIFICATIONS),
        "finding_categories": list(FINDING_CATEGORIES),
        "finding_statuses": list(FINDING_STATUSES),
        "importance": list(IMPORTANCE),
        "phases": list(PHASES),
        "review_judgments": list(REVIEW_JUDGMENTS),
        "review_verdicts": list(REVIEW_VERDICTS),
        "schemas": {
            "audit": SCHEMA_AUDIT,
            "candidate": SCHEMA_CANDIDATE,
            "gate": SCHEMA_GATE,
            "packet": SCHEMA_PACKET,
            "result": SCHEMA_RESULT,
            "review": SCHEMA_REVIEW,
        },
        "severities": list(SEVERITIES),
        "stop_reason_to_state": dict(STOP_STATE),
        "stop_reasons": list(STOP_REASONS),
    }

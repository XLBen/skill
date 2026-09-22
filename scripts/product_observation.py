#!/usr/bin/env python3
"""Product-observation data protocol and gate core for the delivery engine.

This module owns the mechanical half of whole-product black-box observation:
schema validation for candidate manifests, phase reports and adequacy
reviews, plus the gate logic that `check.py product-audit-gate` and
`finish-goal` enforce for schema-2 goals with
`product_observation.required: true`.

It validates structure, identity, freshness, provenance references and
unresolved blockers only. Whether the product map misses material surfaces
and whether evidence actually supports each finding remain the independent
reviewer's semantic judgment; nothing here claims to judge screenshots.

Schema authority is the frozen v2 contract (`scripts/observation_contract.py`):
payload validators delegate to it and legacy `/1` artifacts are rejected with a
single migration diagnostic instead of per-field v1 checks. Validators never
raise on malformed JSON input; they always return a problem list.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

try:
    import observation_contract as _contract
except ImportError:  # pragma: no cover - engine copied without the frozen contract
    _contract = None

try:
    import observation_candidate as _candidate
except ImportError:  # pragma: no cover - engine copied without the candidate module
    _candidate = None

_CONTRACT_UNAVAILABLE = (
    "observation_contract module unavailable; cannot validate "
    "product-observation/2 payloads"
)
_CANDIDATE_UNAVAILABLE = (
    "observation_candidate module unavailable; cannot validate candidate "
    "runtime state"
)
_LEGACY_REPORT_PROBLEM = (
    "legacy schema product-observation/1 is not accepted; "
    "re-observe with product-observation/2"
)
_LEGACY_REVIEW_PROBLEM = (
    "legacy schema product-observation-review/1 is not accepted; "
    "re-review with product-observation-review/2"
)
_LEGACY_CANDIDATE_PROBLEM = (
    "legacy schema product-candidate/1 is not accepted; "
    "re-bind the candidate with product-candidate/2"
)
_AUDIT_SIDECAR_LEGACY_SCHEMA = "product-audit/1"

# The frozen contract is the single authority; the literals below only keep
# this module importable when the contract module is missing, and every
# validator then reports an explicit "contract unavailable" diagnostic.
if _contract is not None:
    REPORT_SCHEMA = _contract.SCHEMA_RESULT
    REVIEW_SCHEMA = _contract.SCHEMA_REVIEW
    CANDIDATE_SCHEMA = _contract.SCHEMA_CANDIDATE
    AUDIT_SIDECAR_SCHEMA = _contract.SCHEMA_AUDIT
    GATE_SCHEMA = _contract.SCHEMA_GATE
    PHASES = _contract.PHASES
    SEVERITIES = _contract.SEVERITIES
    BLOCKING_SEVERITIES = _contract.BLOCKING_SEVERITIES
    BLOCKING_FINDING_STATUSES = _contract.BLOCKING_FINDING_STATUSES
    FINDING_STATUSES = _contract.FINDING_STATUSES
    FINDING_CATEGORIES = _contract.FINDING_CATEGORIES
    CONFIDENCES = _contract.CONFIDENCES
    IMPORTANCE = _contract.IMPORTANCE
    STOP_REASONS = _contract.STOP_REASONS
    STOP_STATE = _contract.STOP_STATE
    REVIEW_VERDICTS = _contract.REVIEW_VERDICTS
else:
    REPORT_SCHEMA = "product-observation/2"
    REVIEW_SCHEMA = "product-observation-review/2"
    CANDIDATE_SCHEMA = "product-candidate/2"
    AUDIT_SIDECAR_SCHEMA = "product-audit/2"
    GATE_SCHEMA = "product-audit-gate/2"
    PHASES = ("discover", "compare")
    SEVERITIES = ("critical", "high", "medium", "low")
    BLOCKING_SEVERITIES = {"critical", "high"}
    BLOCKING_FINDING_STATUSES = {
        "suspected",
        "confirmed",
        "intermittent",
        "owner-decision",
    }
    FINDING_STATUSES = (
        "suspected",
        "confirmed",
        "intermittent",
        "resolved",
        "dismissed",
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
    REVIEW_VERDICTS = ("sufficient", "needs-observation", "needs-repair", "blocked")

HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def _stop_state(stop_reason: Any) -> str | None:
    """Derive the stop state through the frozen contract when present."""

    if _contract is not None:
        return _contract.result_stop_state(stop_reason)
    if not isinstance(stop_reason, str):
        return None
    return STOP_STATE.get(stop_reason)


def _is_blocking_finding(finding: Any) -> bool:
    """Delegate to the frozen contract; literal fallback keeps the engine usable."""

    if _contract is not None:
        return _contract.is_blocking_finding(finding)
    if not isinstance(finding, dict):
        return False
    severity = finding.get("severity")
    status = finding.get("status")
    return (
        isinstance(severity, str)
        and severity in ("critical", "high")
        and isinstance(status, str)
        and status in ("suspected", "confirmed", "intermittent", "owner-decision")
    )


def _semantic_finding_problems(finding: Any, phase: str) -> list[str]:
    if _contract is None:
        return []
    return _contract.semantic_finding_problems(finding, phase)


def _review_verdict_consistency_problems(
    review: Any, open_blocking: bool
) -> list[str]:
    if _contract is None:
        return []
    return _contract.review_verdict_consistency_problems(review, open_blocking)


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _reject_non_finite(constant: str) -> Any:
    raise ValueError(f"non-finite number {constant!r} is not valid JSON")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate key {key!r}")
        obj[key] = value
    return obj


def _load_json(path: Path) -> tuple[Any, str | None]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, f"unreadable: {exc}"
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    try:
        return (
            json.loads(
                text,
                parse_constant=_reject_non_finite,
                object_pairs_hook=_reject_duplicate_keys,
            ),
            None,
        )
    except ValueError as exc:
        return None, f"invalid JSON: {exc}"


def _require_str(value: Any, label: str, problems: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{label} must be a non-empty string")
        return None
    return value


def _str_list(value: Any, label: str, problems: list[str]) -> list[str] | None:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        problems.append(f"{label} must be an array of non-empty strings")
        return None
    return value


def audit_sidecar_path(goal_path: str | Path) -> Path:
    goal_path = Path(goal_path)
    return goal_path.parent / (goal_path.stem + ".product-audit.json")


def observation_root(goal_path: str | Path, goal_id: str) -> Path:
    return Path(goal_path).parent / "observation" / goal_id


def candidate_dir(goal_path: str | Path, goal_id: str, candidate_id: str) -> Path:
    return observation_root(goal_path, goal_id) / candidate_id


def validate_candidate_manifest(manifest: Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(manifest, dict):
        return ["candidate manifest must be a JSON object"]
    if manifest.get("schema") == "product-candidate/1":
        return [_LEGACY_CANDIDATE_PROBLEM]
    if manifest.get("schema") != CANDIDATE_SCHEMA:
        problems.append(f"candidate.schema must be {CANDIDATE_SCHEMA}")
    _require_str(manifest.get("candidate_id"), "candidate.candidate_id", problems)
    _require_str(manifest.get("entry"), "candidate.entry", problems)
    _require_str(manifest.get("environment"), "candidate.environment", problems)
    _require_str(manifest.get("backend"), "candidate.backend", problems)
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        problems.append("candidate.files must be a non-empty array of {path, sha256}")
        files = []
    else:
        seen: set[str] = set()
        for index, item in enumerate(files):
            where = f"candidate.files[{index}]"
            if not isinstance(item, dict):
                problems.append(f"{where} must be an object")
                continue
            path = _require_str(item.get("path"), f"{where}.path", problems)
            if path is not None:
                candidate = Path(path)
                if candidate.is_absolute() or ".." in candidate.parts:
                    problems.append(f"{where}.path must stay project-relative: {path}")
                elif path in seen:
                    problems.append(f"{where}.path duplicates {path}")
                else:
                    seen.add(path)
            digest = item.get("sha256")
            if not isinstance(digest, str) or not HASH_RE.fullmatch(digest):
                problems.append(f"{where}.sha256 must be a sha256 hex digest")
    if "test_data" in manifest and manifest["test_data"] is not None:
        _str_list(manifest["test_data"], "candidate.test_data", problems)
    if "channels" in manifest and manifest["channels"] is not None:
        _str_list(manifest["channels"], "candidate.channels", problems)
    if _candidate is not None:
        problems.extend(_candidate.validate_runtime_state(manifest))
    elif manifest.get("runtime_state") is not None and not isinstance(
        manifest.get("runtime_state"), list
    ):
        problems.append("candidate.runtime_state must be an array when present")
    if "baseline" in manifest and manifest["baseline"] is not None:
        baseline = manifest["baseline"]
        if not isinstance(baseline, dict) or baseline.get("kind") not in (
            "previous-candidate",
            "pre-change-run",
            "none",
        ):
            problems.append(
                "candidate.baseline must be {kind: previous-candidate|pre-change-run|none}"
            )
        elif baseline.get("kind") != "none" and not _str_list(
            baseline.get("refs"), "candidate.baseline.refs", problems
        ):
            problems.append("candidate.baseline with a kind other than none needs refs")
    return problems


def validate_observation_report(report: Any) -> list[str]:
    """Validate a v2 observation result: model payload plus controller envelope.

    Structure only; identity/freshness value matching stays with
    ``collect_observation_problems``. Legacy v1 payloads are rejected with a
    single migration diagnostic instead of per-field v1 validation.
    """

    if not isinstance(report, dict):
        return ["observation report must be a JSON object"]
    if report.get("schema") == "product-observation/1":
        return [_LEGACY_REPORT_PROBLEM]
    if _contract is None:
        return [_CONTRACT_UNAVAILABLE]
    problems = list(_contract.validate_result_payload(report))
    problems.extend(_contract.validate_result_envelope(report))
    return problems


def validate_observation_review(review: Any) -> list[str]:
    """Validate a v2 review payload plus its structural envelope fields.

    Value matching (hashes, verdict) stays with ``collect_observation_problems``;
    legacy v1 reviews are rejected with a single migration diagnostic.
    """

    if not isinstance(review, dict):
        return ["observation review must be a JSON object"]
    if review.get("schema") == "product-observation-review/1":
        return [_LEGACY_REVIEW_PROBLEM]
    if _contract is None:
        return [_CONTRACT_UNAVAILABLE]
    problems = list(_contract.validate_review_payload(review))
    session = review.get("reviewer_session_id")
    if not isinstance(session, str) or not session.strip():
        problems.append("review.reviewer_session_id must be a non-empty string")
    for field in ("discover_hash", "compare_hash"):
        value = review.get(field)
        if not isinstance(value, str) or not HASH_RE.fullmatch(value):
            problems.append(
                f"review.{field} must be a 64-character lowercase sha256 hex digest"
            )
    return problems


def validate_audit_sidecar(sidecar: Any) -> list[str]:
    """Validate a product-audit sidecar; ``/1`` and ``/2`` are both accepted.

    Rounds still use the flat ``discover_ref`` / ``compare_ref`` / ``review_ref``
    layout; the run-directory layout is deferred to S08.
    """

    problems: list[str] = []
    if not isinstance(sidecar, dict):
        return ["product-audit sidecar must be a JSON object"]
    if sidecar.get("schema") not in (AUDIT_SIDECAR_SCHEMA, _AUDIT_SIDECAR_LEGACY_SCHEMA):
        problems.append(
            f"sidecar.schema must be {_AUDIT_SIDECAR_LEGACY_SCHEMA} or "
            f"{AUDIT_SIDECAR_SCHEMA}"
        )
    _require_str(sidecar.get("goal_id"), "sidecar.goal_id", problems)
    _require_str(sidecar.get("current_candidate"), "sidecar.current_candidate", problems)
    rounds = sidecar.get("rounds")
    if not isinstance(rounds, list) or not rounds:
        problems.append("sidecar.rounds must be a non-empty array")
        rounds = []
    for index, item in enumerate(rounds):
        where = f"sidecar.rounds[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where} must be an object")
            continue
        _require_str(item.get("candidate_id"), f"{where}.candidate_id", problems)
        for field in ("discover_ref", "compare_ref", "review_ref"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{where}.{field} must be a non-empty relative path")
    return problems


def observation_spec_problems(goal: dict[str, Any]) -> list[str]:
    """Validate `goal.product_observation` for schema-2 goal cards."""

    problems: list[str] = []
    spec = goal.get("product_observation")
    if goal.get("schema_version") in (2, 3) and spec is None:
        problems.append(
            "goal.product_observation is required for schema_version 2 or 3 cards"
        )
        return problems
    if spec is None:
        return problems
    if not isinstance(spec, dict):
        return ["goal.product_observation must be an object"]
    if not isinstance(spec.get("required"), bool):
        problems.append("goal.product_observation.required must be a boolean")
    if spec.get("required") is False:
        reason = spec.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            problems.append(
                "goal.product_observation.required=false needs a non-empty reason"
            )
        basis = spec.get("basis")
        if not isinstance(basis, str) or not basis.strip():
            problems.append(
                "goal.product_observation.required=false needs a concrete basis"
            )
    elif spec.get("required") is True:
        reason = spec.get("reason")
        if reason is not None and (not isinstance(reason, str) or not reason.strip()):
            problems.append("goal.product_observation.reason must be non-empty when present")
    return problems


_PHASE_FILES = (
    ("discover", "discover_ref", "discover.result.json"),
    ("compare", "compare_ref", "compare.result.json"),
)
_FINDING_INDEX_RE = re.compile(r"^result\.findings\[(\d+)\]")


def _phase_ref_target(round_entry: dict[str, Any], phase: str, default_dir: Path, root: Path) -> Path:
    ref = round_entry.get(f"{phase}_ref")
    if not isinstance(ref, str) or not ref.strip():
        return default_dir / f"{phase}.result.json"
    return root / ref


def _failed_finding_indexes(phase_problems: list[str]) -> set[int]:
    """Indexes of findings whose structural validation failed.

    Semantic checks for these findings are skipped so one malformed field does
    not produce a second, misleading diagnostic.
    """

    failed: set[int] = set()
    for problem in phase_problems:
        match = _FINDING_INDEX_RE.match(problem)
        if match:
            failed.add(int(match.group(1)))
    return failed


def _evidence_ref_problems(ref: Any, cdir: Path, root: Path, label: str) -> list[str]:
    if not isinstance(ref, str) or not ref.strip():
        return [f"{label} must be a non-empty string"]
    relative = Path(ref)
    if relative.is_absolute() or ".." in relative.parts:
        return [f"{label} {ref!r} escapes the candidate evidence scope"]
    in_cdir = cdir / ref
    target = in_cdir if in_cdir.is_file() else root / ref
    if not target.is_file():
        return [f"{label} {ref!r} not found"]
    try:
        target.resolve().relative_to(cdir.resolve())
    except (OSError, ValueError):
        return [f"{label} {ref!r} escapes the candidate evidence scope"]
    return []


def _report_evidence_problems(
    phase: str, report: dict[str, Any], cdir: Path, root: Path
) -> list[str]:
    """Check every evidence reference resolves to a real file inside ``cdir``.

    Non-string items are left to the structural validator; the path checks
    apply to blocking and non-blocking findings alike.
    """

    problems: list[str] = []
    top = report.get("evidence_refs")
    if isinstance(top, list):
        for index, ref in enumerate(top):
            if isinstance(ref, str) and ref.strip():
                problems.extend(
                    _evidence_ref_problems(
                        ref, cdir, root, f"{phase}: evidence_refs[{index}]"
                    )
                )
    journeys = report.get("journeys")
    if isinstance(journeys, list):
        for j_index, journey in enumerate(journeys):
            if not isinstance(journey, dict):
                continue
            refs = journey.get("evidence_refs")
            if not isinstance(refs, list):
                continue
            for r_index, ref in enumerate(refs):
                if isinstance(ref, str) and ref.strip():
                    problems.extend(
                        _evidence_ref_problems(
                            ref,
                            cdir,
                            root,
                            f"{phase}: journeys[{j_index}].evidence_refs[{r_index}]",
                        )
                    )
    findings = report.get("findings")
    if isinstance(findings, list):
        for f_index, finding_item in enumerate(findings):
            if not isinstance(finding_item, dict):
                continue
            refs = finding_item.get("evidence_refs")
            if not isinstance(refs, list):
                continue
            for r_index, ref in enumerate(refs):
                if isinstance(ref, str) and ref.strip():
                    problems.extend(
                        _evidence_ref_problems(
                            ref,
                            cdir,
                            root,
                            f"{phase}: findings[{f_index}].evidence_refs[{r_index}]",
                        )
                    )
    return problems


def _round_finding_ids(round_entry: dict[str, Any], cdir: Path, root: Path) -> set[str] | None:
    """Finding IDs archived for one earlier round; None when unverifiable."""

    ids: set[str] = set()
    for phase, _ref, _file_name in _PHASE_FILES:
        target = _phase_ref_target(round_entry, phase, cdir, root)
        report, error = _load_json(target)
        if error or not isinstance(report, dict):
            return None
        findings = report.get("findings")
        if not isinstance(findings, list):
            return None
        for item in findings:
            if not isinstance(item, dict):
                continue
            ident = item.get("id")
            if isinstance(ident, str) and ident.strip():
                ids.add(ident)
    return ids


def _known_round_findings(
    rounds: list[dict[str, Any]],
    current_candidate_id: str,
    goal_path: Path,
    goal_id: str,
    root: Path,
) -> dict[str, set[str] | None]:
    known: dict[str, set[str] | None] = {}
    for item in reversed(rounds):
        other_id = item.get("candidate_id")
        if not isinstance(other_id, str) or not other_id.strip():
            continue
        if other_id == current_candidate_id or other_id in known:
            continue
        known[other_id] = _round_finding_ids(
            item, candidate_dir(goal_path, goal_id, other_id), root
        )
    return known


def _resolution_binding_problems(
    finding: Any, current_candidate_id: str, known_round_findings: dict[str, set[str] | None]
) -> list[str]:
    if _contract is None:
        return []
    return _contract.resolution_binding_problems(
        finding, current_candidate_id, known_round_findings
    )


def collect_observation_problems(
    goal: dict[str, Any],
    goal_path: str | Path,
    project_root: Path | None = None,
    trace: dict[str, Any] | None = None,
) -> list[str]:
    """Mechanical gate core for `product-audit-gate` / `finish-goal`.

    Returns a list of failure reasons; an empty list means the mechanical
    half passed. Schema-1 goals and required=false specs short-circuit.
    """

    if not isinstance(goal, dict) or goal.get("schema_version") not in (2, 3):
        return []
    spec = goal.get("product_observation")
    if not isinstance(spec, dict) or spec.get("required") is not True:
        return []

    goal_path = Path(goal_path)
    root = project_root if project_root is not None else goal_path.parent.parent.parent
    goal_id = goal.get("id")
    problems: list[str] = []

    sidecar_file = audit_sidecar_path(goal_path)
    sidecar, error = _load_json(sidecar_file)
    if error or not isinstance(sidecar, dict):
        return [f"product-audit sidecar missing or unreadable ({sidecar_file.name}): {error or 'not an object'}"]
    problems.extend(
        f"sidecar: {item}" for item in validate_audit_sidecar(sidecar)
    )

    if not isinstance(goal_id, str) or not goal_id.strip():
        problems.append("goal.id must be a non-empty string to locate the observation root")
        return problems
    if sidecar.get("goal_id") != goal_id:
        problems.append(f"sidecar.goal_id {sidecar.get('goal_id')!r} does not match goal {goal_id!r}")

    candidate_id = sidecar.get("current_candidate")
    sidecar_rounds = sidecar.get("rounds")
    if not isinstance(sidecar_rounds, list):
        sidecar_rounds = []
    rounds = [r for r in sidecar_rounds if isinstance(r, dict)]
    current_rounds = [r for r in rounds if r.get("candidate_id") == candidate_id]
    if not isinstance(candidate_id, str) or not candidate_id.strip() or not current_rounds:
        problems.append(f"sidecar.current_candidate {candidate_id!r} has no round entry")
        return problems
    round_entry = current_rounds[-1]
    cdir = candidate_dir(goal_path, goal_id, candidate_id)

    manifest_file = cdir / "candidate.json"
    manifest, manifest_error = _load_json(manifest_file)
    if manifest_error or not isinstance(manifest, dict):
        problems.append(f"candidate manifest missing/unreadable: {manifest_error or 'not an object'}")
    else:
        problems.extend(f"candidate: {item}" for item in validate_candidate_manifest(manifest))
        if manifest.get("candidate_id") != candidate_id:
            problems.append("candidate.candidate_id does not match the sidecar current_candidate")
        manifest_files = manifest.get("files")
        if isinstance(manifest_files, list):
            for item in manifest_files:
                if not isinstance(item, dict):
                    continue
                rel = item.get("path")
                expected = item.get("sha256")
                if not isinstance(rel, str) or not isinstance(expected, str) or not expected:
                    continue
                relative = Path(rel)
                if relative.is_absolute() or ".." in relative.parts:
                    continue
                target = root / rel
                if not target.is_file():
                    problems.append(f"candidate file missing since binding: {rel}")
                    continue
                if _sha256_file(target) != expected:
                    problems.append(
                        f"candidate file changed after binding: {rel} (re-bind on a new candidate round)"
                    )
        if _candidate is None:
            problems.append(f"candidate: {_CANDIDATE_UNAVAILABLE}")
        else:
            problems.extend(
                f"candidate: {item}"
                for item in _candidate.runtime_state_scope_problems(root, manifest)
            )
            for rel in _candidate.undeclared_delivered_files(root, manifest):
                problems.append(f"undeclared delivered file: {rel}")

    phase_reports: dict[str, dict[str, Any]] = {}
    phase_hashes: dict[str, str | None] = {}
    phase_failed_findings: dict[str, set[int]] = {}
    for phase, _ref_field, _file_name in _PHASE_FILES:
        target = _phase_ref_target(round_entry, phase, cdir, root)
        report, error = _load_json(target)
        if error or not isinstance(report, dict):
            problems.append(
                f"{phase} result missing/unreadable ({target}): {error or 'not an object'}"
            )
            continue
        phase_problems = validate_observation_report(report)
        problems.extend(f"{phase}: {item}" for item in phase_problems)
        phase_failed_findings[phase] = _failed_finding_indexes(phase_problems)
        if report.get("phase") != phase:
            problems.append(f"{phase}: report.phase is {report.get('phase')!r}, expected {phase!r}")
        if report.get("candidate_id") != candidate_id:
            problems.append(f"{phase}: report is bound to candidate {report.get('candidate_id')!r}")
        if report.get("goal_id") != goal_id:
            problems.append(f"{phase}: report.goal_id does not match the goal card")
        report_stop = report.get("stop_reason")
        stop_state = _stop_state(report_stop)
        if stop_state != "completed":
            problems.append(
                f"{phase}: stop_reason is {report_stop!r} (stop_state {stop_state!r}); "
                "only coverage-completed rounds can pass the gate"
            )
        packet_file = cdir / f"{phase}.packet.json"
        packet_digest = _sha256_file(packet_file)
        if packet_digest is None:
            problems.append(f"{phase}: archived phase packet missing ({phase}.packet.json)")
        elif report.get("packet_hash") != packet_digest:
            problems.append(f"{phase}: report.packet_hash does not match the archived packet")
        problems.extend(_report_evidence_problems(phase, report, cdir, root))
        phase_reports[phase] = report
        phase_hashes[phase] = _sha256_file(target)

    blocking: list[str] = []
    semantic_findings: list[str] = []
    open_blocking = False
    known_round_findings = _known_round_findings(
        rounds, candidate_id, goal_path, goal_id, root
    )
    for phase, report in phase_reports.items():
        findings = report.get("findings")
        if not isinstance(findings, list):
            continue
        failed = phase_failed_findings.get(phase, set())
        for index, item in enumerate(findings):
            if not isinstance(item, dict):
                continue
            if _is_blocking_finding(item):
                open_blocking = True
                blocking.append(f"{phase}:{item.get('id')}({item.get('severity')}/{item.get('status')})")
            if index in failed:
                continue
            semantic_findings.extend(
                f"{phase}: {problem}"
                for problem in _semantic_finding_problems(item, phase)
            )
            semantic_findings.extend(
                f"{phase}: {problem}"
                for problem in _resolution_binding_problems(
                    item, candidate_id, known_round_findings
                )
            )
    if blocking:
        problems.append(
            "unresolved critical/high findings block completion: " + ", ".join(blocking)
        )
    problems.extend(semantic_findings)

    gaps = []
    for phase, report in phase_reports.items():
        report_gaps = report.get("capability_gaps")
        if not isinstance(report_gaps, list):
            continue
        for item in report_gaps:
            if not isinstance(item, dict):
                continue
            channel = item.get("channel")
            reason = item.get("reason")
            if (
                isinstance(channel, str)
                and channel.strip()
                and isinstance(reason, str)
                and reason.strip()
            ):
                gaps.append(f"{phase}:{channel}")
    if gaps:
        problems.append(
            "unresolved capability gaps must be resolved or blocked, not passed: "
            + ", ".join(gaps)
        )

    review_ref = round_entry.get("review_ref")
    review_target = (
        cdir / "review.result.json"
        if not isinstance(review_ref, str) or not review_ref.strip()
        else root / review_ref
    )
    review, review_error = _load_json(review_target)
    if review_error or not isinstance(review, dict):
        problems.append(
            f"observation review missing/unreadable: {review_error or 'not an object'}"
        )
    else:
        problems.extend(f"review: {item}" for item in validate_observation_review(review))
        declared_candidate = review.get("candidate_id")
        if declared_candidate is not None and declared_candidate != candidate_id:
            problems.append("review is bound to a different candidate")
        for phase, _ref_field, _file_name in _PHASE_FILES:
            digest = phase_hashes.get(phase)
            field = f"{phase}_hash"
            if digest is None or review.get(field) != digest:
                problems.append(
                    f"review.{field} does not match the current {phase} result; re-review after any change"
                )
        problems.extend(
            f"review: {item}"
            for item in _review_verdict_consistency_problems(review, open_blocking)
        )
        if review.get("verdict") != "sufficient":
            problems.append(
                f"review verdict is {review.get('verdict')!r}; only sufficient clears the gate"
            )

    if trace is not None and isinstance(trace, dict):
        trace_sessions = trace.get("sessions")
        if not isinstance(trace_sessions, list):
            trace_sessions = []
        session_ids = {
            s.get("id") for s in trace_sessions if isinstance(s, dict)
        }
        trace_skills = trace.get("skill_events")
        if not isinstance(trace_skills, list):
            trace_skills = []
        skill_loads = {
            (e.get("session_id"), e.get("skill"))
            for e in trace_skills
            if isinstance(e, dict) and e.get("status") == "completed"
        }
        for phase, report in phase_reports.items():
            session = report.get("observer_session_id")
            if not isinstance(session, str) or session not in session_ids:
                problems.append(
                    f"{phase}: observer session {session!r} not found in the runtime trace"
                )
            elif (session, "product-observer") not in skill_loads:
                problems.append(
                    f"{phase}: observer session {session!r} has no completed product-observer skill load"
                )

    return problems


def write_gate_record(
    goal: dict[str, Any],
    goal_path: str | Path,
    problems: list[str],
    *,
    trace_binding: dict[str, Any] | None = None,
    goal_definition_hash: str | None = None,
) -> Path | None:
    """Best-effort gate record written next to the current candidate round."""

    goal_path = Path(goal_path)
    try:
        sidecar, error = _load_json(audit_sidecar_path(goal_path))
    except OSError:
        return None
    if error or not isinstance(sidecar, dict):
        return None
    candidate_id = sidecar.get("current_candidate")
    goal_id = sidecar.get("goal_id") or (goal.get("id") if isinstance(goal, dict) else None)
    if not isinstance(candidate_id, str) or not isinstance(goal_id, str):
        return None
    cdir = candidate_dir(goal_path, goal_id, candidate_id)
    record: dict[str, Any] = {
        "schema": GATE_SCHEMA,
        "goal_id": goal_id,
        "candidate_id": candidate_id,
        "verdict": "passed" if not problems else "failed",
        "failures": problems,
    }
    if isinstance(goal_definition_hash, str) and goal_definition_hash.strip():
        record["goal_definition_hash"] = goal_definition_hash
    if isinstance(trace_binding, dict):
        record["trace"] = {
            "path": trace_binding.get("path"),
            "sha256": trace_binding.get("sha256"),
            "provenance": trace_binding.get("provenance"),
        }
    else:
        record["trace"] = None
    try:
        cdir.mkdir(parents=True, exist_ok=True)
        target = cdir / "gate.json"
        target.write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return target
    except OSError:
        return None

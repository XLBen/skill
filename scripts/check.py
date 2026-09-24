#!/usr/bin/env python3
"""Contract workflow engine for contract-review and construction.

Commands:
  check.py brief <docs/brief.md>
  check.py brief-confirmation <docs/brief.md>
  check.py hash <file> [<file> ...]
  check.py goal <.opencode/mvp/goal.md>
  check.py engineering-plan <.opencode/mvp/goal.md>
  check.py prepare-plan <.opencode/mvp/goal.md> <project-relative-design.md>
  check.py next-step <.opencode/mvp/goal.md>
  check.py request-decision <.opencode/mvp/goal.md> <request.json>
  check.py resolve-decision <.opencode/mvp/goal.md> <Q-NN|D-NN> <decision.json>
  check.py begin-cycle <.opencode/mvp/goal.md> <step-id>
  check.py verify-cycle <.opencode/mvp/goal.md>
  check.py observe-cycle <.opencode/mvp/goal.md> <observation.json>
  check.py cycle-gate <.opencode/mvp/goal.md>
  check.py verify-goal <.opencode/mvp/goal.md> <O-NN> --evidence <path> [--recover-interrupted] [--reuse <equivalent-evidence>]
  check.py finish-goal <.opencode/mvp/goal.md>
  check.py check-current <.opencode/mvp/goal.md>
  check.py product-audit-gate <.opencode/mvp/goal.md> --trace <trace.json>
  check.py runtime-gate <.opencode/mvp/goal.md> --trace <trace.json> [--dispatch <dispatch.json>] [--policy <policy.json>]
  check.py ui-gate <.opencode/mvp/goal.md> --trace <trace.json> [--bind]
  check.py contract <docs/contract.md>
  check.py compile <docs/contract.md> <docs/PLAN.md> --change-orders <docs/change-orders.md> --ledger <docs/workflow-events.jsonl>
  check.py plan <docs/PLAN.md> --contract <docs/contract.md> --change-orders <docs/change-orders.md> --ledger <docs/workflow-events.jsonl>
  check.py confirm-plan <docs/PLAN.md> <selection.json> --contract <docs/contract.md> --ledger <docs/workflow-events.jsonl>
  check.py plan-event <docs/PLAN.md> <event.json> --contract <docs/contract.md> --ledger <docs/workflow-events.jsonl>
  check.py finish-plan <docs/PLAN.md> <event.json> --contract <docs/contract.md> --change-orders <docs/change-orders.md> --ledger <docs/workflow-events.jsonl>
  check.py reconcile <docs/PLAN.md> --contract <docs/contract.md> --change-orders <docs/change-orders.md> --ledger <docs/workflow-events.jsonl>
  check.py change-orders <docs/change-orders.md> --ledger <docs/workflow-events.jsonl>
  check.py impact <docs/contract.md> <ID> [<ID> ...]
  check.py init <docs/contract.md> <workflow-state.json>
  check.py event <state.json> <events.jsonl> <event.json> --expected-revision N
  check.py release <contract.md> <state.json> <events.jsonl> <event.json> --expected-revision N
  check.py record <events.jsonl> <event.json>
  check.py verify-step <PLAN.md> <S-ID> <V-ID> --contract <contract.md> --ledger <events.jsonl> --evidence <path> --event-id <ID> [--recover-interrupted]
  check.py record-human-step <PLAN.md> <S-ID> <V-ID> --contract <contract.md> --ledger <events.jsonl> --owner-event <ID> --event-id <ID>
  check.py cr-event <change-orders.md> <events.jsonl> <event.json> --expected-revision N
  check.py --selftest

The engine validates only deterministic structure. Semantic claims remain the
responsibility of an independent audit recorded by event ID.
"""
import hashlib
import fnmatch
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

try:
    import engineering_delivery as _engineering_delivery
except ImportError:  # old/incomplete installations must fail closed for schema 3
    _engineering_delivery = None

try:
    import runtime_trace as _runtime_trace
except ImportError as _exc:  # pragma: no cover - engine copied without runtime_trace
    _runtime_trace = None
    _RUNTIME_TRACE_IMPORT_ERROR = str(_exc)
else:
    _RUNTIME_TRACE_IMPORT_ERROR = None

try:
    import evidence_registry as _evidence_registry
except ImportError as _exc:  # pragma: no cover - engine copied without evidence_registry
    _evidence_registry = None
    _EVIDENCE_REGISTRY_IMPORT_ERROR = str(_exc)
else:
    _EVIDENCE_REGISTRY_IMPORT_ERROR = None

try:
    import assurance_policy as _assurance_policy
except ImportError as _exc:  # pragma: no cover - engine copied without assurance_policy
    _assurance_policy = None
    _ASSURANCE_POLICY_IMPORT_ERROR = str(_exc)
else:
    _ASSURANCE_POLICY_IMPORT_ERROR = None

try:
    import product_observation as _product_observation
except ImportError as _exc:  # pragma: no cover - engine copied without product_observation
    _product_observation = None
    _PRODUCT_OBSERVATION_IMPORT_ERROR = str(_exc)
else:
    _PRODUCT_OBSERVATION_IMPORT_ERROR = None

try:
    import runtime_state_policy as _state_policy
except ImportError as _exc:  # pragma: no cover - engine copied without runtime_state_policy
    _state_policy = None
    _STATE_POLICY_IMPORT_ERROR = str(_exc)
else:
    _STATE_POLICY_IMPORT_ERROR = None

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
NODE_TYPES = ("P", "T", "W", "F", "I", "D", "E", "A", "R", "V", "B")
ID_RE = re.compile(r"^(P|T|W|F|I|D|E|A|R|V|B)-\d{2,}$")
BRIEF_KINDS = {
    "fact": "BF", "decision": "BD", "assumption": "BA",
    "constraint": "BC", "question": "BQ", "success": "BS",
    "non-goal": "BN",
}
BRIEF_STATUS = {"draft", "final"}
GOAL_STATUS = {"active", "blocked", "complete"}
GOAL_OUTCOME_STATUS = {"pending", "verified", "blocked"}
GOAL_RISK_FACTORS = {
    "none", "external-boundary", "authentication", "privacy", "money",
    "migration", "irreversible", "cross-module", "security",
    "availability", "data-loss", "compliance", "supply-chain", "production-change",
}
GOAL_HIGH_RISK = {
    "authentication", "privacy", "money", "migration", "irreversible", "security",
    "availability", "data-loss", "compliance", "supply-chain",
}
GOAL_GUARDED_RISK = {"external-boundary", "cross-module", "production-change"}
GOAL_ID_RE = re.compile(r"^G-[A-Z0-9][A-Z0-9-]*$")
OUTCOME_ID_RE = re.compile(r"^O-\d{2,}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
STEP_RE = re.compile(r"^S-I\d{2,}-[a-z0-9-]+-\d{2,}$")
ACTIVE = {"active", "superseded", "withdrawn"}
CONTRACT_STATUS = {
    "draft", "reviewing", "awaiting-owner", "re-reviewing", "blocked",
    "suspended", "passed", "conditional",
}
PLAN_STATUS = {"planning", "building", "paused", "suspended", "done"}
PLAN_RUNTIME_TRANSITIONS = {
    "building": {"paused", "suspended", "done"},
    "paused": {"building"},
    "suspended": {"building"},
}
STEP_RUNTIME_TRANSITIONS = {
    "pending": {"selected", "blocked"},
    "selected": {"executing", "blocked"},
    "executing": {"verifying", "blocked"},
    "verifying": {"complete", "executing", "blocked"},
    "complete": {"invalidated"},
    "blocked": {"selected"},
    "invalidated": {"selected"},
}
BLOCKING_CR = {"proposed", "reviewing", "approved", "applying", "verifying"}
CR_TRANSITIONS = {
    "proposed": {"reviewing"},
    "reviewing": {"approved", "rejected", "waived-pending-verification"},
    "approved": {"applying"},
    "applying": {"verifying"},
    "verifying": {"verified"},
    "verified": {"closed"},
    "rejected": {"closed"},
    "waived-pending-verification": {"waived-verified"},
    "waived-verified": {"closed"},
}
WORKFLOW_TRANSITIONS = {
    "draft": {"draft", "reviewing", "suspended"},
    "reviewing": {"reviewing", "awaiting-owner", "blocked", "suspended", "passed", "conditional"},
    "awaiting-owner": {"awaiting-owner", "reviewing", "suspended"},
    "blocked": {"blocked", "re-reviewing", "suspended"},
    "suspended": {"suspended", "reviewing", "re-reviewing"},
    "passed": {"re-reviewing"},
    "conditional": {"re-reviewing"},
    "re-reviewing": {"re-reviewing", "awaiting-owner", "blocked", "suspended", "passed", "conditional"},
}
PHASES = {
    "intake", "scouting", "question-dispatch-pending", "questions-recorded",
    "evidence", "prototype", "answering", "review-dispatch-pending",
    "review-recorded", "revising", "final-audit-pending",
    "final-audit-recorded", "idle",
}
STATUS_PHASES = {
    "draft": {"intake", "idle"},
    "reviewing": PHASES - {"idle"},
    "awaiting-owner": {"idle"},
    "blocked": {"idle", "evidence", "prototype"},
    "suspended": PHASES,
    "passed": {"idle"},
    "conditional": {"idle"},
    "re-reviewing": PHASES - {"intake", "idle"},
}


class ValidationError(Exception):
    pass


def canonical_bytes(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value, domain):
    return hashlib.sha256(domain.encode("ascii") + b"\0" + canonical_bytes(value)).hexdigest()


@contextmanager
def file_lock(path):
    """Hold a cross-process exclusive lock for a projection and its ledger."""
    lock_path = Path(str(path) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    stream = lock_path.open("a+b")
    try:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def contract_projection(contract):
    projected = json.loads(json.dumps(contract))
    projected.pop("contract_hash", None)
    return projected


def contract_hash(contract):
    return digest(contract_projection(contract), "review-contract")


def brief_hash(brief):
    return digest(brief, "requirement-brief")


def brief_confirmation_hash(brief):
    """Bind the final owner confirmation to current semantic brief content."""
    projection = json.loads(json.dumps(brief))
    for key in ("status", "revision", "owner_confirmation"):
        projection.pop(key, None)
    return digest(projection, "brief-confirmation-snapshot")


def brief_confirmation_view(brief):
    items = brief.get("items", [])
    decisions = [x for x in items if isinstance(x, dict) and x.get("kind") == "decision"]
    superseded = {target for item in decisions for target in (item.get("supersedes", []) or [])}
    active = [x for x in decisions if x.get("id") not in superseded]
    def pick(kind, fields):
        return [{k: x.get(k) for k in fields} for x in items
                if isinstance(x, dict) and x.get("kind") == kind]
    return {
        "project": brief.get("summary"), "status": brief.get("status"), "revision": brief.get("revision"),
        "active_decisions": [{k: x.get(k) for k in ("id", "decision_key", "question", "choice", "rationale")}
                              for x in active],
        "constraints": pick("constraint", ("id", "statement", "source")),
        "assumptions": pick("assumption", ("id", "statement", "evidence_status", "source")),
        "success": pick("success", ("id", "statement", "source")),
        "non_goals": pick("non-goal", ("id", "statement", "source")),
        "unresolved_questions": pick("question", ("id", "question", "status")),
        "frontier": brief.get("frontier", []),
        "snapshot_hash": brief_confirmation_hash(brief),
        "ready_to_confirm": (brief.get("status") == "draft" and not brief.get("frontier")
                             and not any(isinstance(x, dict) and x.get("kind") == "question" and x.get("status") == "open"
                                         for x in items)),
    }


def goal_definition_hash(goal):
    projected = json.loads(json.dumps(goal))
    projected.pop("status", None)
    for outcome in projected.get("outcomes", []):
        if isinstance(outcome, dict):
            outcome.pop("status", None)
            outcome.pop("evidence", None)
            outcome.pop("blocker", None)
    return digest(projected, "mvp-goal-definition")


def plan_projection(plan):
    return {
        key: plan[key] for key in (
            "contract_hash", "unit_dag", "steps", "variant_rules",
        )
    }


def plan_hash(plan):
    return digest(plan_projection(plan), "construction-plan")


def step_hash(step):
    return digest(step, "construction-step")


def parse_frontmatter(text):
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    out = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out


def parse_block(text, name):
    pattern = rf"```json\s+{re.escape(name)}\s*\n(.*?)\n```"
    match = re.search(pattern, text, flags=re.DOTALL)
    if not match:
        raise ValidationError(f"missing fenced JSON block: {name}")
    try:
        def reject_duplicates(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValidationError(f"duplicate JSON key in {name}: {key}")
                result[key] = value
            return result
        def reject_constant(value):
            raise ValidationError(f"non-finite JSON number in {name}: {value}")
        return json.loads(match.group(1), object_pairs_hook=reject_duplicates,
                          parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {name}: {exc}") from exc


def read_artifact(path, block):
    text = Path(path).read_text(encoding="utf-8")
    return parse_frontmatter(text), parse_block(text, block)


def require(obj, fields, where, problems):
    for field in fields:
        value = obj.get(field) if isinstance(obj, dict) else None
        if value is None or (isinstance(value, str) and not value.strip()):
            problems.append(f"{where}: missing {field}")


def validate_brief(brief):
    problems = []
    if not isinstance(brief, dict):
        return ["brief must be an object"]
    require(brief, ("schema_version", "revision", "status", "summary", "items",
                    "frontier", "owner_confirmation"), "brief", problems)
    if type(brief.get("schema_version")) is not int or brief.get("schema_version") != 1:
        problems.append("brief.schema_version must be 1")
    if (not isinstance(brief.get("revision"), int)
            or isinstance(brief.get("revision"), bool)
            or brief.get("revision", 0) < 1):
        problems.append("brief.revision must be a positive integer")
    if not isinstance(brief.get("status"), str) or brief.get("status") not in BRIEF_STATUS:
        problems.append("brief.status must be draft or final")
    if not isinstance(brief.get("summary"), str) or not brief.get("summary", "").strip():
        problems.append("brief.summary must be a non-empty string")
    ledger_version = brief.get("decision_ledger_version")
    if ledger_version is not None and (type(ledger_version) is not int or ledger_version != 1):
        problems.append("brief.decision_ledger_version must be 1 when present")

    items = brief.get("items", [])
    if not isinstance(items, list):
        problems.append("brief.items must be an array")
        items = []
    by_id = {}
    item_positions = {}
    for index, item in enumerate(items):
        where = f"brief.items[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where} must be an object")
            continue
        require(item, ("id", "kind"), where, problems)
        ident, kind = item.get("id"), item.get("kind")
        prefix = BRIEF_KINDS.get(kind) if isinstance(kind, str) else None
        if prefix is None:
            problems.append(f"{where}: invalid kind {kind}")
        elif not isinstance(ident, str) or not re.fullmatch(rf"{prefix}-\d{{2,}}", ident):
            problems.append(f"{where}: id must match {prefix}-NN")
        if isinstance(ident, str) and ident in by_id:
            problems.append(f"brief: duplicate item id {ident}")
        elif isinstance(ident, str):
            by_id[ident] = item
            item_positions[ident] = index

        if kind == "fact":
            require(item, ("statement", "source", "evidence_status"), ident or where, problems)
            if not isinstance(item.get("evidence_status"), str) or item.get("evidence_status") not in {"verified", "unverified"}:
                problems.append(f"{ident or where}: invalid evidence_status")
        elif kind == "decision":
            require(item, ("question", "choice", "rationale", "owner_confirmed"), ident or where, problems)
            if item.get("owner_confirmed") is not True:
                problems.append(f"{ident or where}: decision must be owner-confirmed")
        elif kind == "assumption":
            require(item, ("statement", "source", "evidence_status"), ident or where, problems)
            if not isinstance(item.get("evidence_status"), str) or item.get("evidence_status") not in {"verified", "unverified", "refuted"}:
                problems.append(f"{ident or where}: invalid evidence_status")
        elif isinstance(kind, str) and kind in {"constraint", "success", "non-goal"}:
            require(item, ("statement", "source"), ident or where, problems)
        elif kind == "question":
            require(item, ("question", "status"), ident or where, problems)
            if not isinstance(item.get("status"), str) or item.get("status") not in {"open", "deferred"}:
                problems.append(f"{ident or where}: question status must be open or deferred")
        text_fields = {
            "fact": ("statement", "source"),
            "decision": ("question", "choice", "rationale"),
            "assumption": ("statement", "source"),
            "constraint": ("statement", "source"),
            "question": ("question",),
            "success": ("statement", "source"),
            "non-goal": ("statement", "source"),
        }.get(kind, ()) if isinstance(kind, str) else ()
        for field in text_fields:
            if not isinstance(item.get(field), str) or not item.get(field, "").strip():
                problems.append(f"{ident or where}: {field} must be a non-empty string")

    if ledger_version == 1:
        decisions = [x for x in items if isinstance(x, dict) and x.get("kind") == "decision"]
        by_key = {}
        superseded = set()
        for item in decisions:
            ident = item.get("id", "?")
            key = item.get("decision_key")
            if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", key):
                problems.append(f"{ident}: decision_key must be a stable lowercase topic key")
                continue
            refs = item.get("supersedes")
            if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
                problems.append(f"{ident}: supersedes must be an array of prior decision IDs")
                continue
            if len(refs) != len(set(refs)):
                problems.append(f"{ident}: supersedes contains duplicates")
            for target in refs:
                prior = by_id.get(target)
                if (not isinstance(prior, dict) or prior.get("kind") != "decision"
                        or prior.get("decision_key") != key
                        or item_positions.get(target, len(items)) >= item_positions.get(ident, -1)):
                    problems.append(f"{ident}: supersedes must reference an earlier decision with the same decision_key")
                elif target in superseded:
                    problems.append(f"{ident}: supersedes a decision already replaced by another decision")
                else:
                    superseded.add(target)
            by_key.setdefault(key, []).append(item)
        for key, grouped in by_key.items():
            current = [x for x in grouped if x.get("id") not in superseded]
            if len(current) > 1:
                problems.append(f"decision_key {key}: multiple current decisions; resolve the conflict before final confirmation")

    frontier = brief.get("frontier", [])
    if not isinstance(frontier, list):
        problems.append("brief.frontier must be an array")
        frontier = []
    seen_frontier = set()
    for ident in frontier:
        if not isinstance(ident, str) or ident not in by_id or by_id[ident].get("kind") != "question":
            problems.append(f"brief.frontier: unknown question {ident}")
            continue
        if ident in seen_frontier:
            problems.append(f"brief.frontier: duplicate question {ident}")
        seen_frontier.add(ident)
        if by_id[ident].get("status") != "open":
            problems.append(f"brief.frontier: {ident} must be an open question")

    confirmation = brief.get("owner_confirmation", {})
    if not isinstance(confirmation, dict):
        problems.append("brief.owner_confirmation must be an object")
        confirmation = {}
    if not isinstance(confirmation.get("confirmed"), bool):
        problems.append("brief.owner_confirmation.confirmed must be a boolean")
    if not isinstance(confirmation.get("summary"), str):
        problems.append("brief.owner_confirmation.summary must be a string (may be empty for draft)")
    if brief.get("status") == "final":
        if frontier:
            problems.append("final brief must have an empty frontier")
        if any(item.get("kind") == "question" and item.get("status") == "open"
               for item in items if isinstance(item, dict)):
            problems.append("final brief cannot contain open questions; defer them explicitly")
        if confirmation.get("confirmed") is not True:
            problems.append("final brief requires owner confirmation")
        if not isinstance(confirmation.get("summary"), str) or not confirmation.get("summary", "").strip():
            problems.append("final brief requires a confirmation summary")
        if not any(item.get("kind") == "success" for item in items if isinstance(item, dict)):
            problems.append("final brief requires at least one success item")
    if ledger_version == 1:
        snapshot = confirmation.get("snapshot_hash")
        if brief.get("status") == "final" or snapshot is not None:
            if not isinstance(snapshot, str) or not HASH_RE.fullmatch(snapshot):
                problems.append("owner_confirmation.snapshot_hash must bind the current final preview")
            elif snapshot != brief_confirmation_hash(brief):
                problems.append("owner_confirmation.snapshot_hash is stale; regenerate the itemized preview and reconfirm")
    return problems


def validate_assertion(assertion, where, problems):
    if not isinstance(assertion, dict):
        problems.append(f"{where}.assertion must be an object")
    elif assertion.get("type") == "stdout-contains":
        if set(assertion) != {"type", "literal"} or not isinstance(assertion.get("literal"), str) or not assertion["literal"].strip():
            problems.append(f"{where}: stdout-contains needs a non-empty literal only")
    elif assertion.get("type") == "json-equals":
        if set(assertion) != {"type", "expected"}:
            problems.append(f"{where}: json-equals needs expected only")
        else:
            try:
                canonical_bytes(assertion["expected"])
            except (TypeError, ValueError):
                problems.append(f"{where}: expected must be a finite JSON value")
    else:
        problems.append(f"{where}: assertion type must be stdout-contains or json-equals")


def validate_goal(goal):
    problems = []
    if not isinstance(goal, dict):
        return ["goal must be an object"]
    require(goal, (
        "schema_version", "id", "status", "source", "goal", "rigor",
        "risk", "first_slice", "demo", "constraints", "deferred", "outcomes",
    ), "goal", problems)
    if (
        type(goal.get("schema_version")) is not int
        or goal.get("schema_version") not in (1, 2, 3)
    ):
        problems.append("goal.schema_version must be 1, 2 or 3")
    if not isinstance(goal.get("id"), str) or not GOAL_ID_RE.fullmatch(goal.get("id", "")):
        problems.append("goal.id must match G-NAME")
    if not isinstance(goal.get("status"), str) or goal.get("status") not in GOAL_STATUS:
        problems.append("goal.status must be active, blocked, or complete")
    for field in ("goal", "first_slice", "demo"):
        if not isinstance(goal.get(field), str) or not goal.get(field, "").strip():
            problems.append(f"goal.{field} must be a non-empty string")
    for field in ("constraints", "deferred"):
        value = goal.get(field)
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            problems.append(f"goal.{field} must be an array of non-empty strings")

    snapshot_include = goal.get("snapshot_include")
    if snapshot_include is not None:
        if not isinstance(snapshot_include, list) or any(
            not isinstance(item, str) or not item.strip() for item in snapshot_include
        ):
            problems.append("goal.snapshot_include must be an array of non-empty project-relative globs")
        else:
            for item in snapshot_include:
                candidate = Path(item)
                if candidate.is_absolute() or ".." in candidate.parts:
                    problems.append(
                        f"goal.snapshot_include entry must stay inside the project: {item}"
                    )

    rigor = goal.get("rigor")
    if not isinstance(rigor, str) or rigor not in {"normal", "guarded", "audited"}:
        problems.append("goal.rigor must be normal, guarded, or audited")
    risk = goal.get("risk")
    if not isinstance(risk, dict):
        problems.append("goal.risk must be an object")
        risk = {}
    require(risk, ("factors", "rationale"), "goal.risk", problems)
    factors = risk.get("factors")
    if not isinstance(factors, list) or not factors or any(not isinstance(item, str) or item not in GOAL_RISK_FACTORS for item in factors):
        problems.append("goal.risk.factors must be a non-empty array of known factors")
        factors = []
    if len(factors) != len(set(factors)):
        problems.append("goal.risk.factors must not contain duplicates")
    if "none" in factors and len(factors) != 1:
        problems.append("goal.risk factor none cannot be combined with other factors")
    if not isinstance(risk.get("rationale"), str) or not risk.get("rationale", "").strip():
        problems.append("goal.risk.rationale must be a non-empty string")
    if GOAL_HIGH_RISK.intersection(factors) and rigor != "audited":
        problems.append("high-risk factors require audited rigor")
    elif GOAL_GUARDED_RISK.intersection(factors) and rigor == "normal":
        problems.append("guarded-risk factors (external boundary, cross-module, production change) require guarded or audited rigor")

    source = goal.get("source")
    if not isinstance(source, dict):
        problems.append("goal.source must be an object")
        source = {}
    source_type = source.get("type")
    if source_type == "direct":
        require(source, ("raw_request",), "goal.source", problems)
        if not isinstance(source.get("raw_request"), str) or not source.get("raw_request", "").strip():
            problems.append("goal.source.raw_request must preserve the non-empty user request")
    elif source_type == "brief":
        require(source, ("path", "brief_hash", "coverage"), "goal.source", problems)
        if not isinstance(source.get("path"), str) or not source.get("path", "").strip():
            problems.append("goal.source.path must be a non-empty relative path")
        if not isinstance(source.get("brief_hash"), str) or not HASH_RE.fullmatch(source.get("brief_hash", "")):
            problems.append("goal.source.brief_hash must be a sha256 hash")
        coverage = source.get("coverage")
        if not isinstance(coverage, list):
            problems.append("goal.source.coverage must be an array")
        else:
            seen_coverage = set()
            for index, item in enumerate(coverage):
                where = f"goal.source.coverage[{index}]"
                if not isinstance(item, dict):
                    problems.append(f"{where} must be an object")
                    continue
                require(item, ("brief_id", "disposition"), where, problems)
                brief_id = item.get("brief_id")
                if not isinstance(brief_id, str) or not re.fullmatch(r"B[A-Z]-\d{2,}", brief_id):
                    problems.append(f"{where}.brief_id is invalid")
                elif brief_id in seen_coverage:
                    problems.append(f"goal.source.coverage duplicates {brief_id}")
                else:
                    seen_coverage.add(brief_id)
                if not isinstance(item.get("disposition"), str) or item.get("disposition") not in {"outcome", "constraint", "deferred", "non-goal", "rejected"}:
                    problems.append(f"{where}.disposition is invalid")
                if item.get("disposition") == "outcome":
                    refs = item.get("outcome_ids")
                    if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) for ref in refs):
                        problems.append(f"{where}: outcome disposition needs outcome_ids")
                elif not isinstance(item.get("reason"), str) or not item.get("reason", "").strip():
                    problems.append(f"{where}: non-outcome disposition needs reason")
    else:
        problems.append("goal.source.type must be direct or brief")

    outcomes = goal.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        problems.append("goal.outcomes must be a non-empty array")
        outcomes = []
    outcome_ids = set()
    for index, outcome in enumerate(outcomes):
        where = f"goal.outcomes[{index}]"
        if not isinstance(outcome, dict):
            problems.append(f"{where} must be an object")
            continue
        require(outcome, ("id", "statement", "status", "verification"), where, problems)
        ident = outcome.get("id")
        if not isinstance(ident, str) or not OUTCOME_ID_RE.fullmatch(ident):
            problems.append(f"{where}.id must match O-NN")
        elif ident in outcome_ids:
            problems.append(f"goal.outcomes duplicates {ident}")
        else:
            outcome_ids.add(ident)
        if not isinstance(outcome.get("statement"), str) or not outcome.get("statement", "").strip():
            problems.append(f"{where}.statement must be a non-empty string")
        status = outcome.get("status")
        if not isinstance(status, str) or status not in GOAL_OUTCOME_STATUS:
            problems.append(f"{where}.status is invalid")
        verification = outcome.get("verification")
        if not isinstance(verification, dict):
            problems.append(f"{where}.verification must be an object")
            verification = {}
        require(verification, ("command", "expected", "assertion_kind", "empty_result_policy"), f"{where}.verification", problems)
        if not isinstance(verification.get("command"), str) or not verification.get("command", "").strip():
            problems.append(f"{where}.verification.command must be a non-empty string")
        if not isinstance(verification.get("expected"), str) or not verification.get("expected", "").strip():
            problems.append(f"{where}.verification.expected must be a non-empty string")
        if not isinstance(verification.get("assertion_kind"), str) or verification.get("assertion_kind") not in {"content", "state", "schema", "count", "user-visible"}:
            problems.append(f"{where}.verification.assertion_kind is invalid")
        if not isinstance(outcome.get("user_entry", False), bool):
            problems.append(f"{where}.user_entry must be a boolean")
        validate_assertion(verification.get("assertion"), f"{where}.verification", problems)
        if not isinstance(verification.get("empty_result_policy"), str) or not verification.get("empty_result_policy", "").strip():
            problems.append(f"{where}.verification.empty_result_policy must be a non-empty string")
        timeout = verification.get("timeout_seconds", 120)
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 3600:
            problems.append(f"{where}.verification.timeout_seconds must be 1..3600")
        if status == "verified" and not isinstance(outcome.get("evidence"), dict):
            problems.append(f"{where}: verified outcome needs engine evidence")
        if status == "blocked" and (not isinstance(outcome.get("blocker"), str) or not outcome.get("blocker", "").strip()):
            problems.append(f"{where}: blocked outcome needs blocker")
        if status != "blocked" and "blocker" in outcome:
            problems.append(f"{where}: blocker is legal only for blocked outcomes")

    if source_type == "brief" and isinstance(source.get("coverage"), list):
        for item in source["coverage"]:
            if isinstance(item, dict) and item.get("disposition") == "outcome":
                for ref in item.get("outcome_ids", []) if isinstance(item.get("outcome_ids"), list) else []:
                    if not isinstance(ref, str) or ref not in outcome_ids:
                        problems.append(f"goal.source.coverage references unknown outcome {ref}")
    if not any(
            isinstance(item, dict) and item.get("user_entry") is True for item in outcomes):
        problems.append("goal requires at least one user-entry outcome")
    if goal.get("status") == "complete" and any(
            item.get("status") != "verified" for item in outcomes if isinstance(item, dict)):
        problems.append("complete goal requires every outcome to be verified")
    if goal.get("status") == "blocked" and not any(
            item.get("status") == "blocked" for item in outcomes if isinstance(item, dict)):
        problems.append("blocked goal requires at least one blocked outcome")
    ui = goal.get("ui")
    if ui is not None:
        if not isinstance(ui, dict):
            problems.append("goal.ui must be an object")
        else:
            require(ui, ("required",), "goal.ui", problems)
            if not isinstance(ui.get("required"), bool):
                problems.append("goal.ui.required must be a boolean")
            reason = ui.get("reason")
            if reason is not None and (not isinstance(reason, str) or not reason.strip()):
                problems.append("goal.ui.reason must be a non-empty string when present")
            ui_outcomes = ui.get("outcome_ids")
            if ui_outcomes is not None:
                if (not isinstance(ui_outcomes, list)
                        or any(not isinstance(ref, str) for ref in ui_outcomes)):
                    problems.append("goal.ui.outcome_ids must be an array of outcome IDs")
                else:
                    for ref in ui_outcomes:
                        if ref not in outcome_ids:
                            problems.append(f"goal.ui.outcome_ids references unknown outcome {ref}")
    if _product_observation is not None:
        problems.extend(_product_observation.observation_spec_problems(goal))
    if goal.get("schema_version") == 3:
        if _engineering_delivery is None:
            problems.append("engineering_delivery engine module unavailable; reinstall workflow")
        else:
            problems.extend(_engineering_delivery.goal_problems(goal))
    return problems


def check_dag(nodes, edges, label, problems):
    known = set(nodes)
    indegree = {node: 0 for node in known}
    outgoing = {node: [] for node in known}
    for source, target in edges:
        if source not in known or target not in known:
            problems.append(f"{label}: dangling edge {source} -> {target}")
            continue
        outgoing[source].append(target)
        indegree[target] += 1
    queue = [node for node, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for target in outgoing[node]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(known):
        problems.append(f"{label}: cycle detected")


def collect_nodes(contract, problems):
    groups = contract.get("nodes")
    if not isinstance(groups, dict):
        problems.append("contract: nodes must be an object")
        return {}, {}
    by_id, by_type = {}, {}
    for kind in NODE_TYPES:
        items = groups.get(kind, [])
        if not isinstance(items, list):
            problems.append(f"nodes.{kind}: must be an array")
            items = []
        by_type[kind] = items
        for node in items:
            if not isinstance(node, dict):
                problems.append(f"nodes.{kind}: node must be an object")
                continue
            require(node, ("id", "status", "supersedes", "superseded_by", "scope"), kind, problems)
            ident = node.get("id", "")
            if not ID_RE.match(ident) or not ident.startswith(kind + "-"):
                problems.append(f"nodes.{kind}: invalid id {ident!r}")
            if ident in by_id:
                problems.append(f"duplicate id: {ident}")
            by_id[ident] = node
            if node.get("status") not in ACTIVE:
                problems.append(f"{ident}: invalid status")
            if node.get("scope") not in {"local", "global"}:
                problems.append(f"{ident}: invalid scope")
    return by_id, by_type


def validate_references(values, allowed, where, by_id, problems):
    if not isinstance(values, list):
        problems.append(f"{where}: must be an array")
        return
    for ident in values:
        if ident not in by_id:
            problems.append(f"{where}: dangling reference {ident}")
        elif ident.split("-", 1)[0] not in allowed:
            problems.append(f"{where}: invalid reference type {ident}")


def validate_contract(contract):
    problems = []
    if not isinstance(contract, dict):
        return ["contract must be an object"]
    if not isinstance(contract.get("profile"), str) or contract.get("profile") not in {"direct", "light", "full"}:
        problems.append("profile must be direct, light, or full")
    protocol = contract.get("workflow_protocol", "legacy")
    if not isinstance(protocol, str) or protocol not in {"legacy", "v0.1", "v0.2"}:
        problems.append("workflow_protocol must be legacy, v0.1, or v0.2")
    intake = contract.get("intake")
    if not isinstance(intake, dict):
        problems.append("intake must be an object")
        intake = {}
    require(intake, ("mode",), "intake", problems)
    if intake and (not isinstance(intake.get("mode"), str) or intake.get("mode") not in {"direct", "grilled"}):
        problems.append("intake.mode must be direct or grilled")
    if intake.get("mode") == "grilled":
        require(intake, ("brief_path", "brief_hash", "dispositions"), "intake", problems)
        if not isinstance(intake.get("dispositions"), list):
            problems.append("intake.dispositions must be an array")
    control = contract.get("control", {})
    if not isinstance(control, dict):
        problems.append("control must be an object")
        control = {}
    require(control, ("interaction", "audit_budget", "research_budget", "prototype_budget"), "control", problems)
    if not isinstance(control.get("interaction"), str) or control.get("interaction") not in {"autonomous", "checkpoints", "stepwise"}:
        problems.append("control.interaction is invalid")
    for key in ("audit_budget", "research_budget", "prototype_budget"):
        if not isinstance(control.get(key), int) or control.get(key, -1) < 0:
            problems.append(f"control.{key} must be a non-negative integer")

    by_id, by_type = collect_nodes(contract, problems)
    active = {ident: node for ident, node in by_id.items() if node.get("status") == "active"}

    seen_brief_ids = set()
    dispositions = intake.get("dispositions", [])
    if not isinstance(dispositions, list):
        dispositions = []
    for index, disposition in enumerate(dispositions):
        where = f"intake.dispositions[{index}]"
        if not isinstance(disposition, dict):
            problems.append(f"{where} must be an object")
            continue
        require(disposition, ("brief_id", "status"), where, problems)
        brief_id = disposition.get("brief_id")
        if isinstance(brief_id, str) and brief_id in seen_brief_ids:
            problems.append(f"intake: duplicate disposition for {brief_id}")
        if isinstance(brief_id, str):
            seen_brief_ids.add(brief_id)
        if not isinstance(disposition.get("status"), str) or disposition.get("status") not in {"consumed", "deferred", "rejected"}:
            problems.append(f"{where}: invalid status")
        if disposition.get("status") == "consumed":
            targets = disposition.get("contract_ids")
            if not isinstance(targets, list) or not targets:
                problems.append(f"{where}: consumed item needs contract_ids")
            else:
                for target in targets:
                    if not isinstance(target, str) or target not in by_id:
                        problems.append(f"{where}: unknown contract id {target}")
                    elif target not in active:
                        problems.append(f"{where}: consumed target must be active: {target}")
        elif not isinstance(disposition.get("reason"), str) or not disposition.get("reason", "").strip():
            problems.append(f"{where}: deferred/rejected item needs reason")

    for ident, node in by_id.items():
        for inverse in node.get("supersedes", []):
            if inverse not in by_id or ident not in by_id[inverse].get("superseded_by", []):
                problems.append(f"{ident}: supersedes relation is not bidirectional with {inverse}")

    for node in by_type.get("P", []):
        require(node, ("statement", "source", "source_revision", "priority", "success"), node.get("id", "P"), problems)
    for node in by_type.get("T", []):
        require(node, ("decision_status", "question", "options", "authority"), node.get("id", "T"), problems)
        if node.get("decision_status") == "applied":
            require(node, ("selected_option", "decision_event", "applies_to"), node["id"], problems)
    for node in by_type.get("W", []):
        require(node, ("kind", "identity", "source_revision", "required_apis", "fallback_order"), node.get("id", "W"), problems)
        if node.get("kind") not in {"library", "service", "protocol", "project-module", "custom-build"}:
            problems.append(f"{node.get('id')}: invalid wheel kind")
        validate_references(node.get("fallback_order", []), {"W"}, f"{node.get('id')}.fallback_order", by_id, problems)
    for node in by_type.get("E", []):
        e_required = ("claim", "kind", "source", "checked_at", "environment", "command", "inputs", "output_summary", "verdict")
        if protocol != "v0.2":
            e_required += ("bundle_hash",)
        require(node, e_required, node.get("id", "E"), problems)
        if node.get("bundle_hash"):
            projection = {k: v for k, v in node.items() if k != "bundle_hash"}
            expected = digest(projection, "evidence-bundle")
            if node["bundle_hash"] != expected:
                problems.append(f"{node.get('id')}: bundle_hash mismatch")
    for kind, required in {
        "D": ("decision", "rationale"),
        "A": ("claim", "disposition"),
        "R": ("trigger", "mitigation"),
        "B": ("exclusion", "reason"),
    }.items():
        for node in by_type.get(kind, []):
            require(node, required, node.get("id", kind), problems)

    flow_ids = {node["id"] for node in by_type.get("F", []) if "id" in node}
    for node in by_type.get("F", []):
        ident = node.get("id", "F")
        require(node, ("name", "serves", "predecessors", "preconditions", "inputs", "actions", "outputs", "branches", "failures", "terminal", "verifications"), ident, problems)
        validate_references(node.get("serves", []), {"P"}, f"{ident}.serves", by_id, problems)
        validate_references(node.get("verifications", []), {"V"}, f"{ident}.verifications", by_id, problems)
        if node.get("terminal") is False:
            branches = node.get("branches", [])
            if not any(branch.get("default") is True for branch in branches if isinstance(branch, dict)):
                problems.append(f"{ident}: non-terminal flow needs a default branch")
            for branch in branches:
                target = branch.get("target") if isinstance(branch, dict) else None
                if target not in flow_ids and target not in {"TERMINAL_SUCCESS", "TERMINAL_FAILURE"}:
                    problems.append(f"{ident}: invalid branch target {target}")

    v_types = {}
    for node in by_type.get("V", []):
        ident = node.get("id", "V")
        require(node, ("type", "covers", "prerequisites", "stage", "expected"), ident, problems)
        if node.get("type") not in {"local", "integration", "end-to-end", "human"}:
            problems.append(f"{ident}: invalid verification type")
        if node.get("type") == "human" and not node.get("observation"):
            problems.append(f"{ident}: human verification needs observation")
        if node.get("type") != "human" and not node.get("command"):
            problems.append(f"{ident}: automated verification needs command")
        if node.get("type") != "human" and not isinstance(node.get("command"), str):
            problems.append(f"{ident}: automated verification command must be a string")
        if protocol == "v0.2" and node.get("type") != "human":
            validate_assertion(node.get("assertion"), ident, problems)
            require(node, ("given", "when", "then", "assertion_kind", "empty_result_policy"), ident, problems)
            if not isinstance(node.get("assertion_kind"), str) or node.get("assertion_kind") not in {"content", "state", "schema", "count", "user-visible"}:
                problems.append(f"{ident}: invalid assertion_kind")
            if not isinstance(node.get("empty_result_policy"), str) or not node.get("empty_result_policy", "").strip():
                problems.append(f"{ident}: empty_result_policy must be a non-empty string")
            timeout = node.get("timeout_seconds", 300)
            if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 3600:
                problems.append(f"{ident}: timeout_seconds must be 1..3600")
        red = node.get("red_command")
        if red is not None and (not isinstance(red, str) or not red.strip()):
            problems.append(f"{ident}: red_command must be a non-empty string when present")
        if red is not None and node.get("type") == "human":
            problems.append(f"{ident}: human verification cannot carry red_command")
        validate_references(node.get("covers", []), {"P", "F", "I"}, f"{ident}.covers", by_id, problems)
        v_types[ident] = node.get("type")

    unit_ids, unit_edges = set(), []
    realized = set()
    variant_wheels = {}
    for node in by_type.get("I", []):
        ident = node.get("id", "I")
        require(node, ("name", "kind", "realizes", "validates", "depends_on", "change_boundary", "variants"), ident, problems)
        unit_ids.add(ident)
        validate_references(node.get("realizes", []), {"F"}, f"{ident}.realizes", by_id, problems)
        validate_references(node.get("validates", []), {"A", "W", "V"}, f"{ident}.validates", by_id, problems)
        if node.get("kind") == "build" and node.get("status") == "active":
            if not node.get("realizes"):
                problems.append(f"{ident}: build unit must realize a flow")
            realized.update(node.get("realizes", []))
        if node.get("kind") not in {"build", "s0", "validation"}:
            problems.append(f"{ident}: invalid implementation kind")
        for dependency in node.get("depends_on", []):
            unit_edges.append((dependency, ident))
        variants = node.get("variants", [])
        if not variants:
            problems.append(f"{ident}: needs at least one variant")
        variant_ids = set()
        for variant in variants:
            vid = variant.get("id", "")
            if not re.match(r"^[a-z0-9][a-z0-9-]*$", vid) or vid in variant_ids:
                problems.append(f"{ident}: invalid or duplicate variant id {vid!r}")
            variant_ids.add(vid)
            require(variant, ("selector", "uses", "interface_equivalence", "segments"), f"{ident}.{vid}", problems)
            if not isinstance(variant.get("selector"), dict):
                problems.append(f"{ident}.{vid}: selector must be structured JSON")
            validate_references(variant.get("uses", []), {"W", "D"}, f"{ident}.{vid}.uses", by_id, problems)
            variant_wheels.setdefault(ident, set()).update(x for x in variant.get("uses", []) if x.startswith("W-"))
            segment_ids = set()
            segment_edges = []
            for segment in variant.get("segments", []):
                sid = segment.get("id", "")
                where = f"{ident}.{vid}.{sid}"
                if sid in segment_ids:
                    problems.append(f"{ident}.{vid}: duplicate segment id {sid}")
                segment_ids.add(sid)
                require(segment, ("id", "depends_on_segments", "actions", "artifacts", "interfaces", "side_effects", "idempotency", "build_rollback", "segment_verifications"), where, problems)
                if not re.match(r"^\d{2,}$", sid):
                    problems.append(f"{where}: invalid segment id")
                validate_references(segment.get("segment_verifications", []), {"V"}, f"{where}.segment_verifications", by_id, problems)
                for verification in segment.get("segment_verifications", []):
                    if node.get("kind") in {"build", "s0"} and v_types.get(verification) != "local":
                        problems.append(f"{where}: build/s0 segment may only hold local V")
                for dependency in segment.get("depends_on_segments", []):
                    segment_edges.append((dependency, sid))
            check_dag(segment_ids, segment_edges, f"{ident}.{vid} segment DAG", problems)
    check_dag(unit_ids, unit_edges, "implementation DAG", problems)

    for flow in flow_ids:
        if flow in active and flow not in realized:
            problems.append(f"{flow}: active flow is not realized by a build unit")
    for node in by_type.get("P", []):
        if node.get("status") != "active":
            continue
        ident = node["id"]
        if not any(flow.get("status") == "active" and ident in flow.get("serves", []) for flow in by_type.get("F", [])):
            problems.append(f"{ident}: active requirement is not served by a flow")
        if not any(verification.get("status") == "active" and ident in verification.get("covers", []) for verification in by_type.get("V", [])):
            problems.append(f"{ident}: active requirement is not covered by verification")
    for wheel in by_type.get("W", []):
        for fallback in wheel.get("fallback_order", []):
            users = [unit for unit, wheels in variant_wheels.items() if wheel.get("id") in wheels]
            if not users or not all(fallback in variant_wheels.get(unit, set()) for unit in users):
                problems.append(f"{wheel.get('id')}: fallback {fallback} lacks an equivalent variant")
    return problems


BRIEF_TARGET_TYPES = {
    "fact": {"P", "W", "D", "E", "A"},
    "decision": {"P", "T", "D", "I", "B"},
    "assumption": {"E", "A", "R"},
    "constraint": {"P", "I", "R", "V", "B"},
    "question": {"T", "W", "E", "A"},
    "success": {"P", "V"},
    "non-goal": {"B"},
}


def validate_brief_artifact(path):
    problems = []
    meta, brief = read_artifact(path, "brief")
    problems.extend(validate_brief(brief))
    if not isinstance(brief, dict):
        return meta, brief, None, problems
    expected = brief_hash(brief)
    if meta.get("status") != brief.get("status"):
        problems.append("brief frontmatter status does not match JSON status")
    if brief.get("status") == "final" and meta.get("brief-hash") != expected:
        problems.append("frontmatter brief-hash mismatch")
    return meta, brief, expected, problems


def goal_project_root(path):
    path = Path(path).resolve()
    if path.parent.name != "mvp" or path.parent.parent.name != ".opencode":
        raise ValidationError("goal card must live directly under .opencode/mvp/")
    return path.parent.parent.parent


def validate_goal_artifact(path):
    problems = []
    meta, goal = read_artifact(path, "goal")
    problems.extend(validate_goal(goal))
    if problems:
        return meta, goal, problems
    try:
        project_root = goal_project_root(path)
    except ValidationError as exc:
        problems.append(str(exc))
        project_root = None
    if meta.get("status") != goal.get("status"):
        problems.append("goal frontmatter status does not match JSON status")
    if project_root and goal.get("schema_version") == 3:
        try:
            _engineering_delivery.load(path, goal, sys.modules[__name__])
        except ValidationError as exc:
            problems.append(str(exc))

    source = goal.get("source", {})
    if project_root and isinstance(source, dict) and source.get("type") == "brief":
        raw_path = source.get("path")
        if isinstance(raw_path, str):
            relative = Path(raw_path)
            if relative.is_absolute() or ".." in relative.parts:
                problems.append("goal.source.path must stay inside the project")
            else:
                brief_path = (project_root / relative).resolve()
                try:
                    brief_path.relative_to(project_root)
                    _, brief, expected, brief_problems = validate_brief_artifact(brief_path)
                    problems.extend(f"source brief: {item}" for item in brief_problems)
                    if brief.get("status") != "final":
                        problems.append("goal source brief must be final")
                    confirmation = brief.get("owner_confirmation")
                    if not isinstance(confirmation, dict) or confirmation.get("confirmed") is not True:
                        problems.append("goal source brief requires owner confirmation")
                    if source.get("brief_hash") != expected:
                        problems.append("goal.source.brief_hash mismatch")
                    brief_ids = {
                        item.get("id") for item in brief.get("items", [])
                        if isinstance(item, dict) and isinstance(item.get("id"), str)
                    }
                    covered = {
                        item.get("brief_id") for item in source.get("coverage", [])
                        if isinstance(item, dict) and isinstance(item.get("brief_id"), str)
                    }
                    if brief_ids - covered:
                        problems.append("goal source has no coverage for: " + ", ".join(sorted(brief_ids - covered)))
                    if covered - brief_ids:
                        problems.append("goal source coverage has unknown brief IDs: " + ", ".join(sorted(covered - brief_ids)))
                    success_ids = {
                        item.get("id") for item in brief.get("items", [])
                        if isinstance(item, dict) and item.get("kind") == "success"
                        and isinstance(item.get("id"), str)
                    }
                    for item in source["coverage"]:
                        if item["brief_id"] in success_ids and item["disposition"] != "outcome":
                            problems.append(
                                f"goal source success {item['brief_id']} must map to outcomes; "
                                "keep required later work pending or blocked"
                            )
                except (OSError, ValidationError, TypeError, AttributeError, ValueError) as exc:
                    problems.append(f"goal source brief is unavailable or invalid: {exc}")

    definition_hash = goal_definition_hash(goal)
    for outcome in goal.get("outcomes", []):
        if not isinstance(outcome, dict) or outcome.get("status") != "verified":
            continue
        evidence = outcome.get("evidence", {})
        where = f"{outcome.get('id', 'outcome')}.evidence"
        require(evidence, ("path", "sha256"), where, problems)
        raw_path = evidence.get("path")
        if not project_root or not isinstance(raw_path, str):
            continue
        relative = Path(raw_path)
        if relative.is_absolute() or ".." in relative.parts:
            problems.append(f"{where}.path must stay inside the project")
            continue
        evidence_path = (project_root / relative).resolve()
        try:
            evidence_path.relative_to(project_root)
            evidence_bytes = evidence_path.read_bytes()
            payload = json.loads(evidence_bytes.decode("utf-8"))
            actual_hash = hashlib.sha256(evidence_bytes).hexdigest()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            problems.append(f"{where} is unavailable or invalid: {exc}")
            continue
        if evidence.get("sha256") != actual_hash:
            problems.append(f"{where}.sha256 mismatch")
        verification = outcome.get("verification", {})
        if (not isinstance(payload, dict) or payload.get("kind") != "goal-verification"
                or payload.get("goal_id") != goal.get("id")
                or payload.get("outcome_id") != outcome.get("id")
                or payload.get("goal_definition_hash") != definition_hash
                or payload.get("command") != verification.get("command")
                or payload.get("result") != "passed"
                or type(payload.get("exit_code")) is not int
                or payload.get("exit_code") != 0
                or payload.get("timed_out") is not False
                or payload.get("assertion") != verification.get("assertion")
                or payload.get("assertion_passed") is not True
                or not evaluate_assertion(payload.get("stdout"), verification["assertion"])):
            problems.append(f"{where} does not prove this goal outcome")
    return meta, goal, problems


def render_goal(goal):
    return (
        "---\n"
        f"status: {goal['status']}\n"
        "---\n\n"
        f"# Goal: {goal['goal']}\n\n"
        "```json goal\n"
        + json.dumps(goal, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n```\n"
    )


def evaluate_assertion(stdout, assertion):
    """Evaluate captured stdout, never a narrative expected-result claim."""
    if not isinstance(stdout, str) or not isinstance(assertion, dict):
        return False
    if assertion.get("type") == "stdout-contains":
        literal = assertion.get("literal")
        return isinstance(literal, str) and bool(literal.strip()) and literal in stdout
    if assertion.get("type") == "json-equals" and "expected" in assertion:
        try:
            def unique_object(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("duplicate JSON key")
                    result[key] = value
                return result
            actual = json.loads(stdout, object_pairs_hook=unique_object)
            return canonical_bytes(actual) == canonical_bytes(assertion["expected"])
        except (TypeError, ValueError):
            return False
    return False


SNAPSHOT_SKIP_DIRS = {
    ".git", ".hg", ".svn", ".opencode", "__pycache__", "node_modules",
    ".venv", "venv", ".tox", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".idea", ".vscode", "dist", "build", "target", "coverage", "htmlcov",
}
SNAPSHOT_SKIP_REL_PREFIXES = (
    "docs/audit-slices/", "docs/evidence/", "docs/test-manifests/",
    "docs/slice-increments/",
)
SNAPSHOT_SKIP_REL_FILES = {
    "docs/PLAN.md", "docs/contract.md", "docs/change-orders.md",
    "docs/build-log.md", "docs/mvp-observation.md", "docs/review-log.md",
    "docs/review-charter.md", "docs/workflow-state.json",
    "docs/workflow-events.jsonl",
}
SNAPSHOT_SKIP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
SNAPSHOT_SKIP_SUFFIXES = (".pyc", ".pyo", ".tmp", ".log", ".swp", ".swo", ".orig", ".rej")


def _snapshot_skips(relative_posix):
    parts = relative_posix.split("/")
    if any(part in SNAPSHOT_SKIP_DIRS for part in parts):
        return True
    if relative_posix in SNAPSHOT_SKIP_REL_FILES:
        return True
    if any(relative_posix.startswith(prefix) for prefix in SNAPSHOT_SKIP_REL_PREFIXES):
        return True
    if relative_posix.startswith("docs/brief") and relative_posix.endswith(".md"):
        return True
    name = parts[-1]
    if name in SNAPSHOT_SKIP_NAMES or name.endswith(SNAPSHOT_SKIP_SUFFIXES):
        return True
    return False


def workspace_snapshot(root, extra_excludes=(), include_patterns=()):
    """Conservative content snapshot of the delivered workspace.

    Excludes VCS metadata, workflow state/artifacts, caches and generated
    outputs (documented lists above). Everything else is included on purpose:
    when the impact of a change cannot be decided, the snapshot treats it as
    product-affecting. `include_patterns` re-includes normally excluded
    delivery inputs (for example a product file under `.opencode/`) so the
    binding covers what the product actually ships. A file that cannot be read
    fails the snapshot instead of being recorded as unchanged."""

    root = Path(root).resolve()
    excluded = set()
    for item in extra_excludes:
        if item is None:
            continue
        try:
            excluded.add(Path(item).resolve())
        except OSError:
            continue
    includes = [pattern for pattern in include_patterns if isinstance(pattern, str) and pattern.strip()]

    def _included(relative):
        # Workflow runtime state (cards, dispatch records, evidence, sidecars)
        # is rewritten by the engine itself; it can never be a delivery input,
        # and including it would make the record and the recomputation diverge.
        if relative == ".opencode/mvp" or relative.startswith(".opencode/mvp/"):
            return False
        return any(fnmatch.fnmatch(relative, pattern) for pattern in includes)

    digest = hashlib.sha256()
    counted = 0
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        relative_dir = current.relative_to(root).as_posix()
        if relative_dir == ".":
            relative_dir = ""
        if includes:
            dirnames[:] = sorted(dirnames)
        else:
            dirnames[:] = sorted(
                name for name in dirnames
                if not _snapshot_skips((relative_dir + "/" + name).lstrip("/"))
            )
        for name in sorted(filenames):
            relative = (relative_dir + "/" + name).lstrip("/")
            if _snapshot_skips(relative) and not _included(relative):
                continue
            path = current / name
            try:
                if path.resolve() in excluded:
                    continue
                data = path.read_bytes()
            except OSError as exc:
                raise ValidationError(
                    f"workspace snapshot cannot read {relative}: {exc}; "
                    "included delivery inputs must be readable"
                ) from exc
            digest.update(relative.encode("utf-8") + b"\0")
            digest.update(hashlib.sha256(data).hexdigest().encode("ascii"))
            counted += 1
    return digest.hexdigest(), counted


def _state_policy_file(goal_path):
    goal = Path(goal_path)
    return goal.parent / (goal.stem + ".runtime-state.json")


def _load_state_policy(goal_path, goal_id):
    """Return (binding_or_None, problems) for the goal's runtime-state policy.

    A missing policy file is legacy behavior (no exclusions). An existing file
    with an invalid structure, or an engine that lacks the policy module while
    a policy file exists, is an error, never a silent pass.
    """

    if _state_policy is None:
        path = _state_policy_file(goal_path)
        if path.exists():
            return None, [
                "runtime_state_policy.py is not available next to check.py; cannot "
                f"load {path.name} ({_STATE_POLICY_IMPORT_ERROR})"
            ]
        return None, []
    return _state_policy.load_policy(goal_path, goal_id)


def _state_policy_excludes(project_root, binding):
    if _state_policy is None or binding is None:
        return []
    return _state_policy.snapshot_excludes(project_root, binding)


def run_command_evidence(command, cwd, evidence_path, metadata, timeout_seconds,
                         recover=False, recover_interrupted=False, snapshot_include=(),
                         state_excludes=()):
    evidence_path = Path(evidence_path)
    expected = dict(metadata, schema_version=1, command=command,
                    cwd=str(Path(cwd).resolve()), timeout_seconds=timeout_seconds)

    def validate_payload(raw):
        payload = json.loads(raw)
        if not isinstance(payload, dict) or any(
                canonical_bytes(payload.get(key)) != canonical_bytes(value)
                for key, value in expected.items()):
            raise ValueError("evidence bindings mismatch")
        if (type(payload.get("timed_out")) is not bool
                or not isinstance(payload.get("stdout"), str)
                or not isinstance(payload.get("stderr"), str)
                or (payload["timed_out"] and payload.get("exit_code") is not None)
                or (not payload["timed_out"] and type(payload.get("exit_code")) is not int)
                or type(payload.get("elapsed_seconds")) not in (int, float)
                or not 0 <= payload["elapsed_seconds"] < float("inf")):
            raise ValueError("invalid execution result")
        start = datetime.fromisoformat(payload["started_at"].replace("Z", "+00:00"))
        finish = datetime.fromisoformat(payload["finished_at"].replace("Z", "+00:00"))
        if start.tzinfo is None or finish.tzinfo is None or finish < start:
            raise ValueError("invalid execution timestamps")
        passed = payload["exit_code"] == 0 and not payload["timed_out"]
        if "assertion" in metadata:
            asserted = evaluate_assertion(payload["stdout"], metadata["assertion"])
            if payload.get("assertion_passed") is not asserted:
                raise ValueError("invalid assertion result")
            passed = passed and asserted
        if payload.get("workspace_changed") is True:
            passed = False
        if payload.get("result") != ("passed" if passed else "failed"):
            raise ValueError("inconsistent execution result")
        required_fields = set(expected) | ({"assertion_passed"} if "assertion" in metadata else set())
        allowed = required_fields | {
            "started_at", "finished_at", "elapsed_seconds", "timed_out",
            "exit_code", "stdout", "stderr", "result",
            "workspace_before", "workspace_after", "workspace_changed",
            "reservation_recovered", "runtime_state_policy",
        }
        if not required_fields <= set(payload) or not set(payload) <= allowed:
            raise ValueError("unexpected evidence fields")
        return payload

    if evidence_path.exists():
        if not recover:
            raise ValidationError(f"evidence file already exists: {evidence_path}")
        try:
            raw = evidence_path.read_bytes()
            payload = validate_payload(raw)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise ValidationError(f"orphaned verification evidence is invalid: {exc}") from exc
        return payload, hashlib.sha256(raw).hexdigest()

    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    temp = evidence_path.with_suffix(evidence_path.suffix + ".tmp")
    snapshot_excludes = (evidence_path, temp) + tuple(state_excludes)
    workspace_before, _ = workspace_snapshot(cwd, snapshot_excludes, snapshot_include)
    reservation_recovered = False
    if temp.exists():
        try:
            raw = temp.read_bytes()
            payload = validate_payload(raw)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            if not recover_interrupted:
                raise ValidationError(
                    f"temporary evidence file already exists: {temp}; the interrupted "
                    "verification may already have run with unknown side effects. Inspect "
                    "them, then either remove the temporary file deliberately or re-run "
                    "with --recover-interrupted"
                ) from None
            temp.unlink()
            reservation_recovered = True
        else:
            os.replace(temp, evidence_path)
            return payload, hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    try:
        # Reserve before execution; an interrupted run must not silently rerun side effects.
        with temp.open("x", encoding="utf-8"):
            pass
    except FileExistsError as exc:
        raise ValidationError(f"temporary evidence file already exists: {temp}") from exc
    started = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    timed_out = False
    process = subprocess.Popen(
        command, shell=True, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        **({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
           else {"start_new_session": True}),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        exit_code = process.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            process.kill()
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired as cleanup:
            stdout, stderr = cleanup.stdout or stdout, cleanup.stderr or stderr
        except OSError:
            pass
        # Windows reader threads may still hold pipe locks after cleanup times out;
        # closing those streams here could block indefinitely.
        if os.name != "nt":
            process.stdout.close()
            process.stderr.close()
    stdout = stdout.decode("utf-8", errors="replace")
    stderr = stderr.decode("utf-8", errors="replace")
    finished = datetime.now(timezone.utc)
    workspace_after, _ = workspace_snapshot(cwd, snapshot_excludes, snapshot_include)
    workspace_changed = workspace_before != workspace_after
    payload = dict(metadata)
    payload.update({
        "schema_version": 1,
        "command": command,
        "cwd": str(Path(cwd).resolve()),
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "finished_at": finished.isoformat().replace("+00:00", "Z"),
        "elapsed_seconds": round(time.perf_counter() - started_clock, 6),
        "timeout_seconds": timeout_seconds,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "workspace_before": workspace_before,
        "workspace_after": workspace_after,
        "workspace_changed": workspace_changed,
        "result": "passed" if exit_code == 0 and not timed_out and not workspace_changed else "failed",
    })
    if reservation_recovered:
        payload["reservation_recovered"] = True
    if metadata.get("kind") == "goal-verification" or "assertion" in metadata:
        payload["assertion_passed"] = evaluate_assertion(stdout, metadata.get("assertion"))
        if not payload["assertion_passed"]:
            payload["result"] = "failed"
    with temp.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    if evidence_path.exists():
        temp.unlink()
        raise ValidationError(f"evidence file appeared concurrently: {evidence_path}")
    os.replace(temp, evidence_path)
    return payload, hashlib.sha256(evidence_path.read_bytes()).hexdigest()


def reuse_goal_evidence(project_root, expectation, resolved_evidence, source_path,
                        snapshot_include=(), state_excludes=()):
    """Write a new goal evidence record that references an equivalent run.

    The caller builds `expectation` from the authoritative request; this
    function re-checks strict equivalence against the source payload, requires
    the source to have passed with no workspace change, and requires the
    current workspace snapshot to equal the one the source run recorded. It
    never re-executes the command and never claims a new execution time."""

    if _evidence_registry is None:
        raise ValidationError(
            "evidence_registry.py is not available next to check.py; cannot reuse evidence: "
            + str(_EVIDENCE_REGISTRY_IMPORT_ERROR)
        )
    source_path = Path(source_path)
    if not source_path.is_absolute():
        source_path = Path.cwd() / source_path
    try:
        source_bytes = source_path.read_bytes()
        source = json.loads(source_bytes.decode("utf-8-sig"))
    except (OSError, ValueError, TypeError) as exc:
        raise ValidationError(f"reuse source evidence unreadable: {exc}") from exc
    if not isinstance(source, dict):
        raise ValidationError("reuse source evidence is not a JSON object")
    problems = _evidence_registry.reuse_rejection_reasons(source, expectation)
    if problems:
        raise ValidationError(
            "reuse source is not strictly equivalent: " + "; ".join(problems)
        )
    current, _ = workspace_snapshot(project_root, state_excludes, include_patterns=snapshot_include)
    if source.get("workspace_after") != current:
        raise ValidationError(
            "workspace changed after the source run; reuse refused, re-run the verification"
        )
    resolved_evidence = Path(resolved_evidence)
    if resolved_evidence.exists():
        raise ValidationError(f"evidence file already exists: {resolved_evidence}")
    project_resolved = Path(project_root).resolve()
    source_resolved = source_path.resolve()
    try:
        recorded_source = source_resolved.relative_to(project_resolved).as_posix()
    except ValueError:
        recorded_source = source_path.as_posix()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "schema_version": 1,
        "kind": "goal-verification",
        "goal_id": expectation["goal_id"],
        "outcome_id": expectation["outcome_id"],
        "goal_definition_hash": expectation["goal_definition_hash"],
        "command": source.get("command"),
        "cwd": source.get("cwd"),
        "timeout_seconds": source.get("timeout_seconds"),
        "expected": source.get("expected"),
        "assertion_kind": source.get("assertion_kind"),
        "empty_result_policy": source.get("empty_result_policy"),
        "started_at": source.get("started_at"),
        "finished_at": source.get("finished_at"),
        "elapsed_seconds": source.get("elapsed_seconds"),
        "timed_out": source.get("timed_out"),
        "exit_code": source.get("exit_code"),
        "stdout": source.get("stdout"),
        "stderr": source.get("stderr"),
        "workspace_before": current,
        "workspace_after": current,
        "workspace_changed": False,
        "result": "passed",
        "reuse_policy": _evidence_registry.REUSE_POLICY,
        "reused_from": {
            "path": recorded_source,
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
        },
        "reused_at": now,
    }
    policy_binding = expectation.get("runtime_state_policy")
    if policy_binding is not None:
        payload["runtime_state_policy"] = policy_binding
    if "assertion" in expectation:
        payload["assertion"] = expectation["assertion"]
        payload["assertion_passed"] = True
    resolved_evidence.parent.mkdir(parents=True, exist_ok=True)
    temp = resolved_evidence.with_suffix(resolved_evidence.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    if resolved_evidence.exists():
        temp.unlink()
        raise ValidationError(f"evidence file appeared concurrently: {resolved_evidence}")
    os.replace(temp, resolved_evidence)
    return payload, hashlib.sha256(resolved_evidence.read_bytes()).hexdigest()


def verify_goal_outcome(goal_path, outcome_id, evidence_path, recover_interrupted=False,
                        reuse_from=None):
    with file_lock(str(goal_path) + ".runtime"):
        meta, goal, problems = validate_goal_artifact(goal_path)
        if problems:
            raise ValidationError("goal is invalid:\n- " + "\n- ".join(problems))
        if goal.get("status") == "complete":
            raise ValidationError("a complete goal cannot be re-verified")
        outcome = next((item for item in goal["outcomes"] if item.get("id") == outcome_id), None)
        if not outcome:
            raise ValidationError(f"unknown goal outcome: {outcome_id}")
        project_root = goal_project_root(goal_path)
        policy_binding, policy_problems = _load_state_policy(goal_path, goal["id"])
        if policy_problems:
            raise ValidationError(
                "runtime-state policy is invalid:\n- " + "\n- ".join(policy_problems)
            )
        state_excludes = _state_policy_excludes(project_root, policy_binding)
        evidence_path = Path(evidence_path)
        if ".." in evidence_path.parts:
            raise ValidationError("goal evidence path cannot contain parent traversal")
        resolved_evidence = evidence_path.resolve() if evidence_path.is_absolute() else (project_root / evidence_path).resolve()
        allowed_root = (project_root / ".opencode" / "mvp" / "evidence").resolve()
        try:
            resolved_evidence.relative_to(allowed_root)
        except ValueError as exc:
            raise ValidationError("goal evidence must live under .opencode/mvp/evidence/") from exc
        verification = outcome["verification"]
        snapshot_include = goal.get("snapshot_include") or []
        metadata = {
            "kind": "goal-verification",
            "goal_id": goal["id"],
            "outcome_id": outcome_id,
            "goal_definition_hash": goal_definition_hash(goal),
            "assertion_kind": verification["assertion_kind"],
            "empty_result_policy": verification["empty_result_policy"],
            "expected": verification["expected"],
            "assertion": verification["assertion"],
        }
        if policy_binding is not None:
            metadata["runtime_state_policy"] = policy_binding
        if reuse_from is not None:
            expectation = dict(metadata)
            expectation.setdefault("runtime_state_policy", policy_binding)
            expectation.update(
                {
                    "command": verification["command"],
                    "cwd": str(Path(project_root).resolve()),
                    "timeout_seconds": verification.get("timeout_seconds", 120),
                }
            )
            source_path = Path(reuse_from)
            if not source_path.is_absolute():
                source_path = project_root / source_path
            payload, evidence_hash = reuse_goal_evidence(
                project_root,
                expectation,
                resolved_evidence,
                source_path,
                snapshot_include,
                state_excludes,
            )
        else:
            payload, evidence_hash = run_command_evidence(
                verification["command"], project_root, resolved_evidence,
                metadata,
                verification.get("timeout_seconds", 120),
                recover_interrupted=recover_interrupted,
                snapshot_include=snapshot_include,
                state_excludes=state_excludes,
            )
        updated = json.loads(json.dumps(goal))
        updated_outcome = next(item for item in updated["outcomes"] if item["id"] == outcome_id)
        if payload["result"] == "passed":
            updated_outcome["status"] = "verified"
            updated_outcome.pop("blocker", None)
            updated_outcome["evidence"] = {
                "path": resolved_evidence.relative_to(project_root).as_posix(),
                "sha256": evidence_hash,
            }
        else:
            updated_outcome["status"] = "blocked"
            updated_outcome["blocker"] = "verification command failed; inspect " + resolved_evidence.relative_to(project_root).as_posix()
            updated_outcome.pop("evidence", None)
        updated["status"] = "blocked" if any(item["status"] == "blocked" for item in updated["outcomes"]) else "active"
        updated_problems = validate_goal(updated)
        if updated_problems:
            raise ValidationError("verified goal would be invalid:\n- " + "\n- ".join(updated_problems))
        target = Path(goal_path)
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(render_goal(updated), encoding="utf-8", newline="\n")
        os.replace(temp, target)
        return updated, payload


RUNTIME_POLICY_SCHEMA = "runtime-policy/1"
RUNTIME_GATE_SCHEMA = "runtime-gate/1"
UI_SIDECAR_SCHEMA = "ui-acceptance/1"
UI_GATE_SCHEMA = "ui-gate/1"
UI_SCENARIO_STATUS = {"pending", "passed", "failed", "blocked", "not-applicable"}
RUNTIME_GATE_DEFAULT_REQUIREMENTS = (
    {"kind": "task-dispatch", "role": "reviewer"},
    {"kind": "review-satisfied-goal"},
    {"kind": "independence"},
)


def _sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_runtime_policy(goal_path, goal_id):
    """Load the opt-in runtime policy sidecar next to the goal card.

    Returns (policy_or_None, problems). A missing file means the runtime gate
    is not enabled for this project (legacy behavior). An existing file with a
    wrong schema or unknown fields is an error, never a silent pass.
    """

    path = Path(goal_path).parent / "runtime-policy.json"
    if not path.exists():
        return None, []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"runtime-policy.json unreadable: {exc}"]
    if not isinstance(data, dict):
        return None, ["runtime-policy.json is not a JSON object"]
    problems = []
    if data.get("schema") != RUNTIME_POLICY_SCHEMA:
        problems.append(f"runtime-policy.json schema must be {RUNTIME_POLICY_SCHEMA}")
    goals = data.get("goals")
    if goals != "all" and not (isinstance(goals, list) and all(isinstance(g, str) for g in goals)):
        problems.append("runtime-policy.json goals must be 'all' or a list of goal IDs")
    requirements = data.get("requirements", [])
    if not isinstance(requirements, list) or not all(isinstance(r, dict) for r in requirements):
        problems.append("runtime-policy.json requirements must be a list of objects")
    if problems:
        return None, problems
    if goals != "all" and goal_id not in goals:
        return None, []  # policy exists but does not gate this goal
    return data, []


def policy_binding_state(goal_path, goal_id, policy_path=None):
    """Return (policy_or_None, binding, problems).

    The binding always describes the current policy state so gate sidecars can
    detect a policy created, changed, removed, or newly re-scoped after the
    gate ran. `path: null` means no policy file exists.
    """

    card = Path(goal_path)
    if policy_path is not None:
        path = Path(policy_path)
        if not path.is_file():
            return None, None, [f"policy not found: {path}"]
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            return None, None, [f"policy unreadable: {exc}"]
        if not isinstance(data, dict) or data.get("schema") != RUNTIME_POLICY_SCHEMA:
            return None, None, [f"policy schema must be {RUNTIME_POLICY_SCHEMA}"]
        goals = data.get("goals")
        gating = goals == "all" or (isinstance(goals, list) and goal_id in goals)
        binding = {"path": str(path), "sha256": _sha256_file(path), "gating": bool(gating)}
        return (data if gating else None), binding, []
    path = card.parent / "runtime-policy.json"
    if not path.is_file():
        return None, {"path": None, "sha256": None, "gating": False}, []
    policy, problems = load_runtime_policy(goal_path, goal_id)
    if problems:
        return None, None, problems
    binding = {"path": str(path), "sha256": _sha256_file(path), "gating": policy is not None}
    return policy, binding, []


def runtime_gate(goal_path, trace_path, dispatch_path=None, policy_path=None):
    """Validate the goal's dispatch chain against a native runtime trace.

    Fail-closed: writes a runtime-gate sidecar whose verdict is 'pass' only
    when every claimed dispatch is proven by the trace. The sidecar records
    the sha256 of the trace and dispatch inputs so finish-goal can reject a
    stale gate after the underlying files change.
    """

    if _runtime_trace is None:
        raise ValidationError(
            "runtime_trace.py is not available next to check.py; cannot gate on runtime evidence: "
            + (_RUNTIME_TRACE_IMPORT_ERROR or "unknown import error")
        )
    _, goal, problems = validate_goal_artifact(goal_path)
    if problems:
        raise ValidationError("goal is invalid:\n- " + "\n- ".join(problems))
    card = Path(goal_path)
    slug = card.stem
    if dispatch_path is None:
        dispatch_path = card.parent / f"{slug}.dispatch.json"
    trace_path = Path(trace_path)
    if not trace_path.is_file():
        raise ValidationError(f"runtime trace not found: {trace_path}")
    if not Path(dispatch_path).is_file():
        raise ValidationError(
            f"dispatch record not found: {dispatch_path} — the controller must maintain it before gating"
        )
    trace = _runtime_trace.load_trace(trace_path)
    dispatch = _runtime_trace.load_dispatch(Path(dispatch_path))
    if dispatch.get("goal_id") not in (None, goal["id"]):
        raise ValidationError(
            f"dispatch record goal_id {dispatch.get('goal_id')!r} does not match goal {goal['id']}"
        )
    policy, policy_binding, policy_problems = policy_binding_state(goal_path, goal["id"], policy_path)
    if policy_problems:
        raise ValidationError(";\n".join(policy_problems))
    if policy is not None:
        # The default requirements are a floor: a project policy may add
        # requirements but an empty or partial list cannot remove them.
        policy = dict(policy)
        configured = policy.get("requirements", [])
        if not isinstance(configured, list):
            configured = []
        effective = list(RUNTIME_GATE_DEFAULT_REQUIREMENTS)
        for req in configured:
            if req not in effective:
                effective.append(req)
        policy["requirements"] = effective
    native_problems = _runtime_trace.verify_native_trace(trace)
    slice_rigor = (dispatch.get("active_slice") or {}).get("rigor")
    if slice_rigor not in ("normal", "guarded", "audited"):
        slice_rigor = None
    failures = native_problems + _runtime_trace.validate_chain(
        trace, dispatch, policy,
        base_dir=goal_project_root(goal_path),
        rigor=slice_rigor or goal.get("rigor"),
        goal_rigor=goal.get("rigor"),
    )
    sidecar = {
        "schema": RUNTIME_GATE_SCHEMA,
        "goal_id": goal["id"],
        "verdict": "pass" if not failures else "fail",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "goal_definition_hash": goal_definition_hash(goal),
        "trace_provenance": "native" if not native_problems else "unverified",
        "trace": {"path": str(trace_path), "sha256": _sha256_file(trace_path)},
        "dispatch": {"path": str(dispatch_path), "sha256": _sha256_file(dispatch_path)},
        "policy": policy_binding,
        "failures": failures,
    }
    gate_path = card.parent / f"{slug}.runtime-gate.json"
    gate_path.write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return sidecar, gate_path


def enforce_runtime_gate(goal_path, goal):
    """Called from finish_goal when a runtime policy gates this goal.

    When a gate sidecar exists it is always checked (even if the default
    policy file is absent now), and the recorded policy state is revalidated
    against the store's recorded path so explicit `--policy` gates stay
    enforceable while deletion or re-scoping is detected."""

    policy, problems = load_runtime_policy(goal_path, goal["id"])
    if problems:
        raise ValidationError(";\n".join(problems))
    card = Path(goal_path)
    gate_path = card.parent / f"{card.stem}.runtime-gate.json"
    if not gate_path.is_file():
        if policy is None:
            return
        raise ValidationError(
            "runtime policy enables the runtime gate for this goal; run "
            "'check.py runtime-gate <card> --trace <native trace>' before finish-goal"
        )
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"runtime gate sidecar unreadable: {exc}") from exc
    if gate.get("schema") != RUNTIME_GATE_SCHEMA:
        raise ValidationError(f"runtime gate sidecar schema must be {RUNTIME_GATE_SCHEMA}")
    if gate.get("goal_id") != goal["id"]:
        raise ValidationError("runtime gate sidecar was issued for a different goal")
    if gate.get("verdict") != "pass":
        raise ValidationError(
            "runtime gate verdict is not pass: " + "; ".join(gate.get("failures") or ["unknown failures"])
        )
    if gate.get("goal_definition_hash") != goal_definition_hash(goal):
        raise ValidationError(
            "runtime gate is stale: the goal definition changed after the gate ran; re-run runtime-gate"
        )
    if gate.get("trace_provenance") != "native":
        raise ValidationError("runtime gate was not produced from native session evidence; re-export the trace")
    for key in ("trace", "dispatch"):
        recorded = gate.get(key) or {}
        recorded_path = recorded.get("path")
        recorded_hash = recorded.get("sha256")
        if not recorded_path or not recorded_hash:
            raise ValidationError(f"runtime gate sidecar missing {key} path/sha256")
        current = Path(recorded_path)
        if not current.is_file():
            raise ValidationError(f"runtime gate {key} file no longer exists: {current}")
        if _sha256_file(current) != recorded_hash:
            raise ValidationError(
                f"runtime gate is stale: {key} file changed after the gate ran; re-run runtime-gate"
            )
    recorded_policy = gate.get("policy")
    if recorded_policy is None:
        raise ValidationError("runtime gate predates policy binding; re-run runtime-gate")
    recorded_policy_path = recorded_policy.get("path") if isinstance(recorded_policy, dict) else None
    _, current_binding, current_problems = policy_binding_state(
        goal_path, goal["id"], policy_path=recorded_policy_path if recorded_policy_path else None
    )
    if current_problems:
        raise ValidationError(";\n".join(current_problems))
    if recorded_policy != current_binding:
        raise ValidationError(
            "runtime gate is stale: the runtime policy state changed after the gate ran; re-run runtime-gate"
        )
    if recorded_policy_path:
        # A gate recorded against an explicit path must not hide a default
        # policy that has since started gating this goal.
        _, default_binding, default_problems = policy_binding_state(goal_path, goal["id"])
        if default_problems:
            raise ValidationError(";\n".join(default_problems))
        if default_binding != recorded_policy and default_binding.get("gating"):
            raise ValidationError(
                "runtime gate is stale: a default runtime policy now gates this goal; re-run runtime-gate"
            )


def ui_artifact_identity(project_root, files):
    digest = hashlib.sha256()
    for rel in sorted(files):
        path = (project_root / rel).resolve()
        digest.update(str(rel).encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _iso_after(later, earlier):
    try:
        later_dt = datetime.fromisoformat(str(later).replace("Z", "+00:00"))
        earlier_dt = datetime.fromisoformat(str(earlier).replace("Z", "+00:00"))
    except ValueError:
        return False
    if later_dt.tzinfo is None or earlier_dt.tzinfo is None:
        return False
    return later_dt > earlier_dt


def load_ui_sidecar(goal_path, goal):
    path = Path(goal_path).parent / f"{Path(goal_path).stem}.ui-acceptance.json"
    if not path.exists():
        return None, path
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"ui-acceptance sidecar unreadable: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != UI_SIDECAR_SCHEMA:
        raise ValidationError(f"ui-acceptance sidecar schema must be {UI_SIDECAR_SCHEMA}")
    if data.get("goal_id") != goal["id"]:
        raise ValidationError(
            f"ui-acceptance sidecar goal_id {data.get('goal_id')!r} does not match goal {goal['id']}"
        )
    return data, path


def policy_requires_ui(goal_path, goal):
    policy, problems = load_runtime_policy(goal_path, goal["id"])
    if problems:
        raise ValidationError(";\n".join(problems))
    if policy is None:
        return False
    requirements = policy.get("requirements", [])
    return any(
        isinstance(req, dict) and req.get("kind") == "ui-acceptance"
        for req in requirements if isinstance(requirements, list)
    ) if isinstance(requirements, list) else False


def _ui_ref_problems(scenario_id, label, refs, project_root):
    """Evidence references must resolve to non-empty project-relative files."""

    problems = []
    if not isinstance(refs, list) or not refs:
        problems.append(f"ui scenario {scenario_id}: passed without {label}")
        return problems
    for ref in refs:
        if not isinstance(ref, str) or not ref.strip():
            problems.append(f"ui scenario {scenario_id}: {label} entries must be non-empty strings")
            continue
        relative = Path(ref)
        if relative.is_absolute() or ".." in relative.parts:
            problems.append(f"ui scenario {scenario_id}: {label} '{ref}' must be a project-relative path")
            continue
        target = project_root / relative
        try:
            if not target.is_file():
                problems.append(f"ui scenario {scenario_id}: {label} '{ref}' does not exist")
            elif target.stat().st_size == 0:
                problems.append(f"ui scenario {scenario_id}: {label} '{ref}' is empty")
        except OSError as exc:
            problems.append(f"ui scenario {scenario_id}: {label} '{ref}' unreadable: {exc}")
    return problems


def _ui_tool_matches(tool, patterns):
    return any(fnmatch.fnmatch(str(tool), pattern) for pattern in patterns)


def validate_ui_acceptance(goal_path, goal, trace=None, bind=False, rebind=False):
    """Validate the ui-acceptance sidecar; returns (sidecar, path, failures).

    `--bind` records the artifact identity on first binding only. After a
    recorded identity exists, changed files are a failure until the affected
    scenarios were reset and re-executed: `--rebind` refreshes the identity
    only when every `passed` scenario carries an execution timestamp after the
    previous binding. The gate never re-labels old results onto a changed
    build.
    """

    sidecar, path = load_ui_sidecar(goal_path, goal)
    if sidecar is None:
        raise ValidationError(
            "no ui-acceptance sidecar next to the goal card; the controller must "
            "decide UI applicability (scenarios or applicability: none with reason)"
        )
    failures = []
    project_root = goal_project_root(goal_path)
    applicability = sidecar.get("applicability")
    if applicability not in ("declared", "none"):
        failures.append("ui-acceptance applicability must be 'declared' or 'none'")
    if applicability == "none":
        if not str(sidecar.get("applicability_reason") or "").strip():
            failures.append("applicability 'none' requires a nonempty applicability_reason")
    scenarios = sidecar.get("scenarios")
    if not isinstance(scenarios, list):
        scenarios = []
        failures.append("ui-acceptance scenarios must be a list")
    if applicability == "declared" and not scenarios:
        failures.append("declared UI applicability requires at least one scenario")

    policy, policy_problems = load_runtime_policy(goal_path, goal["id"])
    if policy_problems:
        raise ValidationError(";\n".join(policy_problems))
    ui_tools = None
    if isinstance(policy, dict):
        candidate = policy.get("ui_tools")
        if candidate is not None:
            if (not isinstance(candidate, list) or not candidate
                    or any(not isinstance(pattern, str) or not pattern.strip() for pattern in candidate)):
                failures.append("runtime policy ui_tools must be a non-empty array of tool-name patterns")
            else:
                ui_tools = candidate
    goal_ui = goal.get("ui") if isinstance(goal.get("ui"), dict) else {}
    if goal_ui.get("required") is True and applicability != "declared":
        failures.append("goal.ui.required is true; ui-acceptance applicability must be 'declared'")

    outcome_ids = {o.get("id") for o in goal.get("outcomes", []) if isinstance(o, dict)}
    seen_ids = set()
    completed_calls = {}
    skill_ok_sessions = set()
    if trace is not None:
        for ev in trace.get("tool_events", []):
            if ev.get("status") == "completed" and ev.get("session_id") and ev.get("call_id"):
                completed_calls[f"{ev['session_id']}:{ev['call_id']}"] = ev.get("tool")
        for ev in trace.get("skill_events", []):
            if ev.get("status") == "completed" and ev.get("skill") in ("computer-use", "webapp-testing") and ev.get("session_id"):
                skill_ok_sessions.add(ev["session_id"])

    required_coverage = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            failures.append("ui scenario is not an object")
            continue
        sid = scenario.get("scenario_id", "?")
        if sid in seen_ids:
            failures.append(f"ui scenario id duplicated: {sid}")
        seen_ids.add(sid)
        status = scenario.get("status")
        if status not in UI_SCENARIO_STATUS:
            failures.append(f"ui scenario {sid}: invalid status {status!r}")
            continue
        required_flag = scenario.get("required")
        if not isinstance(required_flag, bool):
            failures.append(f"ui scenario {sid}: required must be a boolean")
        if status == "not-applicable" and not str(scenario.get("not_applicable_reason") or "").strip():
            failures.append(f"ui scenario {sid}: not-applicable requires a reason")
        if required_flag is True and status == "not-applicable":
            failures.append(f"ui scenario {sid}: a required scenario cannot be not-applicable")
        outcome_refs = scenario.get("outcome_ids")
        if not isinstance(outcome_refs, list) or not outcome_refs:
            if status != "not-applicable":
                failures.append(f"ui scenario {sid}: outcome_ids must list at least one goal outcome")
        else:
            for oid in outcome_refs:
                if oid not in outcome_ids:
                    failures.append(f"ui scenario {sid}: unknown outcome {oid!r}")
                elif required_flag is True:
                    required_coverage.add(oid)
        journey = scenario.get("journey") if isinstance(scenario.get("journey"), dict) else {}
        expected = journey.get("expected")
        if status != "not-applicable":
            if (not isinstance(expected, list) or not expected
                    or any(not isinstance(item, str) or not item.strip() for item in expected)):
                failures.append(
                    f"ui scenario {sid}: journey.expected must be a non-empty list of observable results"
                )
        if required_flag is True and status in ("pending", "failed", "blocked"):
            failures.append(f"ui scenario {sid}: required scenario is {status}")
        if status == "passed":
            execution = scenario.get("execution") if isinstance(scenario.get("execution"), dict) else {}
            session_id = execution.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                failures.append(f"ui scenario {sid}: passed without execution.session_id")
            for field in ("executed_at", "target", "build"):
                if not isinstance(execution.get(field), str) or not execution[field].strip():
                    failures.append(f"ui scenario {sid}: passed without execution.{field}")
            executed_at = execution.get("executed_at")
            if isinstance(executed_at, str) and executed_at.strip():
                try:
                    parsed = datetime.fromisoformat(executed_at.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        raise ValueError("timezone required")
                except ValueError:
                    failures.append(
                        f"ui scenario {sid}: execution.executed_at must be an ISO-8601 timestamp with timezone"
                    )
            refs = execution.get("native_call_refs")
            if not isinstance(refs, list) or not refs:
                failures.append(f"ui scenario {sid}: passed without native_call_refs")
                refs = []
            if trace is not None:
                if session_id and session_id not in skill_ok_sessions:
                    failures.append(
                        f"ui scenario {sid}: no completed computer-use/webapp-testing load in executing session {session_id}"
                    )
                for ref in refs:
                    if not isinstance(ref, str) or not ref.strip():
                        failures.append(f"ui scenario {sid}: native_call_refs entries must be non-empty strings")
                        continue
                    if session_id and not str(ref).startswith(f"{session_id}:"):
                        failures.append(
                            f"ui scenario {sid}: native call '{ref}' does not belong to the declared "
                            f"execution session {session_id}"
                        )
                    if ref not in completed_calls:
                        failures.append(
                            f"ui scenario {sid}: native call '{ref}' not found as completed in trace"
                        )
                runner_refs = execution.get("runner_refs")
                if ui_tools:
                    if not any(_ui_tool_matches(completed_calls.get(ref), ui_tools) for ref in refs):
                        failures.append(
                            f"ui scenario {sid}: native_call_refs do not include a call matching "
                            f"policy ui_tools {ui_tools}"
                        )
                elif not (isinstance(runner_refs, list) and runner_refs):
                    failures.append(
                        f"ui scenario {sid}: no policy ui_tools are configured; a passed scenario must "
                        "record execution.runner_refs (captured UI runner output) for review"
                    )
            if isinstance(execution.get("runner_refs"), list) and execution.get("runner_refs"):
                failures += _ui_ref_problems(sid, "runner_refs", execution.get("runner_refs"), project_root)
            failures += _ui_ref_problems(sid, "observation_refs", execution.get("observation_refs"), project_root)
            failures += _ui_ref_problems(sid, "result_refs", execution.get("result_refs"), project_root)

    if goal_ui.get("required") is True:
        for oid in goal_ui.get("outcome_ids") or []:
            if oid not in required_coverage:
                failures.append(f"goal.ui.outcome_ids {oid} has no required UI scenario coverage")

    files = sidecar.get("files")
    if applicability == "declared":
        if not isinstance(files, list) or not files or not all(isinstance(f, str) for f in files):
            failures.append("declared ui-acceptance requires a nonempty files list for artifact binding")
            files = []
        try:
            current_identity = ui_artifact_identity(project_root, files)
        except (ValidationError, OSError) as exc:
            failures.append(f"artifact binding unreadable: {exc}")
            current_identity = None
        if current_identity is not None:
            recorded = sidecar.get("artifact_identity")
            if not recorded:
                if bind:
                    sidecar["artifact_identity"] = current_identity
                    sidecar["bound_at"] = _now_iso()
                    path.write_text(
                        json.dumps(sidecar, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                else:
                    failures.append("artifact_identity not bound yet; run ui-gate --bind first")
            elif recorded != current_identity:
                stale_scenarios = []
                if rebind:
                    prior = sidecar.get("bound_at")
                    for scenario in scenarios:
                        if not isinstance(scenario, dict) or scenario.get("status") != "passed":
                            continue
                        execution = scenario.get("execution") if isinstance(scenario.get("execution"), dict) else {}
                        if not _iso_after(execution.get("executed_at"), prior):
                            stale_scenarios.append(str(scenario.get("scenario_id", "?")))
                if rebind and not stale_scenarios:
                    sidecar["artifact_identity"] = current_identity
                    sidecar["bound_at"] = _now_iso()
                    path.write_text(
                        json.dumps(sidecar, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                elif rebind:
                    failures.append(
                        "artifact_identity mismatch: scenarios " + ", ".join(stale_scenarios)
                        + " have no execution recorded after the previous binding; reset the affected "
                        "scenarios, re-execute them, and re-run ui-gate --rebind"
                    )
                else:
                    failures.append(
                        "artifact_identity mismatch: bound files changed after the assessment; reset the "
                        "affected scenarios, re-execute them, and re-run ui-gate --rebind"
                    )
    return sidecar, path, failures


def ui_gate(goal_path, trace_path, bind=False, rebind=False):
    """Validate UI acceptance evidence against a native trace and write the gate sidecar."""

    if _runtime_trace is None:
        raise ValidationError(
            "runtime_trace.py is not available next to check.py; cannot gate on UI acceptance evidence: "
            + (_RUNTIME_TRACE_IMPORT_ERROR or "unknown import error")
        )
    _, goal, problems = validate_goal_artifact(goal_path)
    if problems:
        raise ValidationError("goal is invalid:\n- " + "\n- ".join(problems))
    trace_path = Path(trace_path)
    if not trace_path.is_file():
        raise ValidationError(f"runtime trace not found: {trace_path}")
    trace = _runtime_trace.load_trace(trace_path)
    sidecar, sidecar_path, failures = validate_ui_acceptance(
        goal_path, goal, trace=trace, bind=bind, rebind=rebind
    )
    extra_failures = list(_runtime_trace.verify_native_trace(trace))
    provenance = "native" if not extra_failures else "unverified"
    if trace.get("truncated"):
        extra_failures.append("runtime trace is truncated; narrow the export window and re-export")
    failures = extra_failures + failures
    card = Path(goal_path)
    gate = {
        "schema": UI_GATE_SCHEMA,
        "goal_id": goal["id"],
        "verdict": "pass" if not failures else "fail",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trace_provenance": provenance,
        "sidecar": {"path": str(sidecar_path), "sha256": _sha256_file(sidecar_path)},
        "trace": {"path": str(trace_path), "sha256": _sha256_file(trace_path)},
        "failures": failures,
    }
    policy, policy_binding, policy_problems = policy_binding_state(goal_path, goal["id"])
    if policy_problems:
        raise ValidationError(";\n".join(policy_problems))
    gate["policy"] = policy_binding
    gate_path = card.parent / f"{card.stem}.ui-gate.json"
    gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return gate, gate_path


def enforce_ui_gate(goal_path, goal):
    """Called from finish_goal when UI acceptance gates this goal."""

    sidecar, sidecar_path = load_ui_sidecar(goal_path, goal)
    required_by_policy = policy_requires_ui(goal_path, goal)
    goal_ui = goal.get("ui") if isinstance(goal.get("ui"), dict) else {}
    required_by_goal = goal_ui.get("required") is True
    if sidecar is None and not required_by_policy and not required_by_goal:
        return
    if sidecar is None:
        raise ValidationError(
            "this goal requires ui-acceptance (goal.ui.required or runtime policy); write the "
            f"{Path(goal_path).stem}.ui-acceptance.json sidecar with the executed scenarios"
        )
    if (required_by_policy or required_by_goal) and sidecar.get("applicability") != "declared":
        raise ValidationError(
            "this goal requires UI acceptance; the sidecar must declare executed scenarios, "
            "not applicability 'none'"
        )
    gate_path = Path(goal_path).parent / f"{Path(goal_path).stem}.ui-gate.json"
    if not gate_path.is_file():
        raise ValidationError(
            "ui acceptance sidecar exists; run 'check.py ui-gate <card> --trace <native trace>' before finish-goal"
        )
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"ui gate sidecar unreadable: {exc}") from exc
    if gate.get("schema") != UI_GATE_SCHEMA:
        raise ValidationError(f"ui gate sidecar schema must be {UI_GATE_SCHEMA}")
    if gate.get("goal_id") != goal["id"]:
        raise ValidationError("ui gate sidecar was issued for a different goal")
    if gate.get("verdict") != "pass":
        raise ValidationError(
            "ui acceptance gate verdict is not pass: " + "; ".join(gate.get("failures") or ["unknown failures"])
        )
    if gate.get("trace_provenance") != "native":
        raise ValidationError("ui gate was not produced from native session evidence; re-export the trace")
    for key in ("sidecar", "trace"):
        recorded = gate.get(key) or {}
        recorded_path = recorded.get("path")
        recorded_hash = recorded.get("sha256")
        if not recorded_path or not recorded_hash:
            raise ValidationError(f"ui gate sidecar missing {key} path/sha256")
        current = Path(recorded_path)
        if not current.is_file():
            raise ValidationError(f"ui gate {key} file no longer exists: {current}")
        if _sha256_file(current) != recorded_hash:
            raise ValidationError(
                f"ui gate is stale: {key} file changed after the gate ran; re-run ui-gate"
            )
    recorded_policy = gate.get("policy")
    if recorded_policy is None:
        raise ValidationError("ui gate predates policy binding; re-run ui-gate")
    _, current_binding, current_problems = policy_binding_state(goal_path, goal["id"])
    if current_problems:
        raise ValidationError(";\n".join(current_problems))
    if recorded_policy != current_binding:
        raise ValidationError(
            "ui gate is stale: the runtime policy state changed after the gate ran; re-run ui-gate"
        )
    project_root = goal_project_root(goal_path)
    files = sidecar.get("files")
    if isinstance(files, list) and files and all(isinstance(f, str) for f in files):
        try:
            current_identity = ui_artifact_identity(project_root, files)
        except (ValidationError, OSError) as exc:
            raise ValidationError(f"ui artifact binding unreadable: {exc}") from exc
        if sidecar.get("artifact_identity") != current_identity:
            raise ValidationError(
                "ui acceptance is stale: the delivered artifacts changed after the assessment; "
                "reset the affected scenarios to pending, re-execute them, and re-run ui-gate"
            )


def enforce_workspace_binding(goal_path, goal):
    """Reject verified outcomes whose evidence no longer matches the workspace.

    The engine records a conservative content snapshot at verification time
    (`workspace_after` in the evidence payload). Any later change to a
    non-excluded file invalidates those results until the affected outcomes
    are re-verified with fresh evidence. Workflow state, evidence files,
    caches and generated outputs are excluded from the snapshot by design, and
    a valid runtime-state policy excludes the product-managed files it names.

    The recorded policy binding must still equal the current one: adding
    exclusions after verification is a policy change, not a repair, so old
    evidence turns stale instead of being revived.
    """

    project_root = goal_project_root(goal_path)
    binding, policy_problems = _load_state_policy(goal_path, goal.get("id"))
    if policy_problems:
        raise ValidationError(
            "runtime-state policy is invalid:\n- " + "\n- ".join(policy_problems)
        )
    state_excludes = _state_policy_excludes(project_root, binding)
    current, _ = workspace_snapshot(
        project_root, state_excludes, include_patterns=goal.get("snapshot_include") or []
    )
    problems = []
    for outcome in goal.get("outcomes", []):
        if outcome.get("status") != "verified":
            continue
        evidence = outcome.get("evidence") or {}
        rel_path = evidence.get("path")
        if not isinstance(rel_path, str) or not rel_path:
            problems.append(f"{outcome.get('id')}: verified outcome has no evidence path")
            continue
        evidence_file = project_root / rel_path
        try:
            payload = json.loads(evidence_file.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            problems.append(f"{outcome.get('id')}: evidence unreadable: {rel_path}")
            continue
        recorded_policy = payload.get("runtime_state_policy") if isinstance(payload, dict) else None
        if canonical_bytes(recorded_policy) != canonical_bytes(binding):
            problems.append(
                f"{outcome.get('id')}: runtime-state policy changed after verification; "
                "re-verify"
            )
            continue
        recorded = payload.get("workspace_after") if isinstance(payload, dict) else None
        if not isinstance(recorded, str) or not recorded:
            problems.append(
                f"{outcome.get('id')}: evidence predates workspace binding; re-run verify-goal"
            )
        elif recorded != current:
            problems.append(
                f"{outcome.get('id')}: workspace changed after verification; re-run verify-goal "
                "with fresh evidence once the delivered files are stable"
            )
    if problems:
        raise ValidationError("workspace binding failed:\n- " + "\n- ".join(problems))


def enforce_product_observation(goal_path, goal):
    """Mechanical whole-product observation gate for schema-2 goals.

    Enforced by `finish-goal` and `check-current` when
    `goal.product_observation.required` is true. Fail-closed: the gate record
    written by `product-audit-gate` must bind the current goal definition and a
    native runtime trace, and the gate problems are recomputed from that trace
    instead of trusting the cached verdict.
    """

    spec = goal.get("product_observation") if isinstance(goal, dict) else None
    if goal.get("schema_version") not in (2, 3):
        return
    if not isinstance(spec, dict) or spec.get("required") is not True:
        return
    if _product_observation is None:
        raise ValidationError(
            "product_observation engine module unavailable; cannot enforce the observation gate"
        )
    goal_path = Path(goal_path)
    restart = (
        "run 'check.py product-audit-gate <goal> --trace <native trace>' first"
    )
    goal_id = goal.get("id")
    if not isinstance(goal_id, str) or not goal_id.strip():
        raise ValidationError(
            "product observation gate cannot be located: the goal card has no id; " + restart
        )
    sidecar, _sidecar_error = _product_observation._load_json(
        _product_observation.audit_sidecar_path(goal_path)
    )
    candidate_id = sidecar.get("current_candidate") if isinstance(sidecar, dict) else None
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ValidationError(
            "product observation gate record is missing or unlocatable (the product-audit "
            "sidecar has no current candidate); " + restart
        )
    gate_file = (
        _product_observation.candidate_dir(goal_path, goal_id, candidate_id) / "gate.json"
    )
    gate, gate_error = _product_observation._load_json(gate_file)
    if gate_error or not isinstance(gate, dict):
        raise ValidationError(
            f"product observation gate record missing or unreadable ({gate_file}); " + restart
        )
    if gate.get("schema") != _product_observation.GATE_SCHEMA:
        raise ValidationError(
            f"product observation gate record schema must be "
            f"{_product_observation.GATE_SCHEMA}; " + restart
        )
    if gate.get("goal_id") != goal_id or gate.get("candidate_id") != candidate_id:
        raise ValidationError(
            "product observation gate record was issued for a different goal or candidate; "
            + restart
        )
    if gate.get("verdict") != "passed":
        raise ValidationError(
            "product observation gate verdict is not passed: "
            + "; ".join(gate.get("failures") or ["unknown failures"])
        )
    if gate.get("goal_definition_hash") != goal_definition_hash(goal):
        raise ValidationError(
            "product observation gate is stale: the goal definition changed after the gate "
            "ran; " + restart
        )
    trace_record = gate.get("trace")
    if (
        not isinstance(trace_record, dict)
        or not isinstance(trace_record.get("path"), str)
        or not trace_record["path"].strip()
        or not isinstance(trace_record.get("sha256"), str)
        or not trace_record["sha256"].strip()
    ):
        raise ValidationError(
            "product observation gate record has no trace binding; " + restart
        )
    trace_path = Path(trace_record["path"])
    if not trace_path.is_file():
        raise ValidationError(
            f"product observation gate is stale: trace file no longer exists ({trace_path}); "
            + restart
        )
    if _sha256_file(trace_path) != trace_record["sha256"]:
        raise ValidationError(
            "product observation gate is stale: the trace file changed after the gate ran; "
            + restart
        )
    if trace_record.get("provenance") != "native":
        raise ValidationError(
            "product observation gate was not produced from native session evidence; " + restart
        )
    if _runtime_trace is None:
        raise ValidationError(
            "runtime_trace.py is not available next to check.py; cannot reload the gated "
            "observation trace"
        )
    try:
        loaded_trace = _runtime_trace.load_trace(trace_path)
    except Exception as exc:
        raise ValidationError(f"product observation trace is unreadable: {exc}") from exc
    problems = _product_observation.collect_observation_problems(
        goal, goal_path, trace=loaded_trace
    )
    problems = list(problems) + observation_state_policy_problems(goal_path, goal)
    if problems:
        raise ValidationError(
            "product observation gate failed:\n- " + "\n- ".join(problems)
        )


def observation_state_policy_problems(goal_path, goal):
    """Align the adopted candidate's runtime state with the policy sidecar (S07).

    The candidate manifest declares which product-managed files may change
    (S06); the policy declares which of those the verification snapshot may
    exclude. A candidate that declares runtime state without a policy, or with
    paths the policy does not cover, cannot have its writes excluded, so it is
    refused up front. A missing sidecar or manifest is left to
    `collect_observation_problems` (one diagnosis, not two).
    """

    if not isinstance(goal, dict):
        return []
    binding, policy_problems = _load_state_policy(goal_path, goal.get("id"))
    if policy_problems:
        return policy_problems
    if goal.get("schema_version") not in (2, 3):
        return []
    spec = goal.get("product_observation")
    if not isinstance(spec, dict) or spec.get("required") is not True:
        return []
    if _product_observation is None:
        return []
    goal_id = goal.get("id")
    if not isinstance(goal_id, str) or not goal_id.strip():
        return []
    goal_path = Path(goal_path)
    sidecar, _error = _product_observation._load_json(
        _product_observation.audit_sidecar_path(goal_path)
    )
    if not isinstance(sidecar, dict):
        return []
    candidate_id = sidecar.get("current_candidate")
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        return []
    manifest, _manifest_error = _product_observation._load_json(
        _product_observation.candidate_dir(goal_path, goal_id, candidate_id)
        / "candidate.json"
    )
    if not isinstance(manifest, dict):
        return []
    candidate_module = getattr(_product_observation, "_candidate", None)
    if candidate_module is None:
        return []
    candidate_paths = candidate_module.runtime_state_paths(manifest)
    if _state_policy is None:
        if candidate_paths:
            return [
                "candidate declares runtime_state but runtime_state_policy.py is not "
                "available next to check.py; cannot check policy coverage"
            ]
        return []
    return _state_policy.candidate_policy_alignment_problems(candidate_paths, binding)


def enforce_delivery_cycles(goal_path, goal):
    if goal.get("schema_version") == 3:
        if _engineering_delivery is None:
            raise ValidationError("engineering_delivery engine module unavailable")
        return _engineering_delivery.Cycles(goal_path, goal, sys.modules[__name__]).gate()


def finish_goal(goal_path):
    with file_lock(str(goal_path) + ".runtime"):
        meta, goal, problems = validate_goal_artifact(goal_path)
        if problems:
            raise ValidationError("goal is invalid:\n- " + "\n- ".join(problems))
        if goal.get("status") == "complete":
            return goal
        if any(item.get("status") != "verified" for item in goal.get("outcomes", [])):
            raise ValidationError("finish-goal requires every outcome to have engine-verified evidence")
        enforce_delivery_cycles(goal_path, goal)
        enforce_runtime_gate(goal_path, goal)
        enforce_ui_gate(goal_path, goal)
        enforce_product_observation(goal_path, goal)
        enforce_workspace_binding(goal_path, goal)
        updated = json.loads(json.dumps(goal))
        updated["status"] = "complete"
        problems = validate_goal(updated)
        if problems:
            raise ValidationError("finished goal is invalid:\n- " + "\n- ".join(problems))
        target = Path(goal_path)
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(render_goal(updated), encoding="utf-8", newline="\n")
        os.replace(temp, target)
        return updated


def check_current(goal_path):
    """Read-only freshness check for the recorded goal evidence.

    Unlike `finish-goal` on an already-complete card, this always recomputes
    the workspace binding for verified outcomes and fails closed when the
    current product no longer matches the evidence. It never rewrites the
    card, invalidates outcomes or reopens history."""

    meta, goal, problems = validate_goal_artifact(goal_path)
    if problems:
        raise ValidationError("goal is invalid:\n- " + "\n- ".join(problems))
    enforce_workspace_binding(goal_path, goal)
    enforce_delivery_cycles(goal_path, goal)
    enforce_product_observation(goal_path, goal)
    return goal


def validate_contract_intake(contract_path, contract):
    intake = contract.get("intake", {})
    if not isinstance(intake, dict):
        return []
    if intake.get("mode") != "grilled":
        return []
    problems = []
    raw_path = intake.get("brief_path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return ["intake.brief_path must be a non-empty relative path"]
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        return ["intake.brief_path must stay inside the contract directory"]
    brief_path = (Path(contract_path).resolve().parent / relative).resolve()
    contract_dir = Path(contract_path).resolve().parent
    try:
        brief_path.relative_to(contract_dir)
        if not brief_path.is_file():
            return ["intake.brief_path must name a readable file"]
        _, brief, expected, brief_problems = validate_brief_artifact(brief_path)
    except ValueError:
        return ["intake.brief_path escapes the contract directory"]
    except (OSError, ValidationError, json.JSONDecodeError, TypeError, AttributeError) as exc:
        return [f"intake brief is unavailable or invalid: {exc}"]
    if not isinstance(brief, dict):
        return problems + ["intake brief must contain a JSON object"]
    problems.extend(f"brief: {problem}" for problem in brief_problems)
    if brief.get("status") != "final":
        problems.append("intake brief must be final")
    if intake.get("brief_hash") != expected:
        problems.append("intake.brief_hash mismatch")

    brief_items = {
        item.get("id"): item for item in brief.get("items", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    dispositions = {
        item.get("brief_id"): item for item in intake.get("dispositions", [])
        if isinstance(item, dict) and isinstance(item.get("brief_id"), str)
    }
    missing = sorted(set(brief_items) - set(dispositions))
    extra = sorted(set(dispositions) - set(brief_items))
    if missing:
        problems.append("intake has no disposition for: " + ", ".join(missing))
    if extra:
        problems.append("intake dispositions reference unknown brief items: " + ", ".join(extra))
    for brief_id in sorted(set(brief_items) & set(dispositions)):
        disposition = dispositions[brief_id]
        if disposition.get("status") != "consumed":
            continue
        brief_item = brief_items[brief_id]
        allowed = BRIEF_TARGET_TYPES.get(brief_item.get("kind"), set())
        if brief_item.get("kind") == "fact" and brief_item.get("evidence_status") != "verified":
            allowed = {"E", "A"}
        for target in disposition.get("contract_ids", []):
            target_type = target.split("-", 1)[0] if isinstance(target, str) else ""
            if target_type not in allowed:
                problems.append(
                    f"intake {brief_id}: {brief_items[brief_id].get('kind')} cannot map to {target}"
                )
    return problems


def contract_problems(contract_path, contract):
    return validate_contract(contract) + validate_contract_intake(contract_path, contract)


def read_checked_contract(path, require_released=False, ledger_path=None):
    meta, contract = read_artifact(path, "contract")
    expected = contract_hash(contract)
    status = meta.get("status")
    problems = contract_problems(path, contract)
    if status not in CONTRACT_STATUS:
        problems.append("frontmatter status is invalid")
    elif meta.get("phase") not in STATUS_PHASES.get(status, set()):
        problems.append("frontmatter status/phase pair is invalid")
    if status in {"passed", "conditional"} and meta.get("contract-hash") != expected:
        problems.append("frontmatter contract-hash mismatch")
    if require_released and status not in {"passed", "conditional"}:
        problems.append("contract must be passed or conditional before construction")
    if require_released and status in {"passed", "conditional"}:
        state_path = Path(path).resolve().parent / "workflow-state.json"
        ledger_path = ledger_path or (Path(path).resolve().parent / "workflow-events.jsonl")
        try:
            problems.extend(validate_contract_release(
                meta, contract, state_path, ledger_path,
            ))
        except (OSError, ValidationError, json.JSONDecodeError, TypeError, KeyError) as exc:
            problems.append(f"contract release proof is unavailable or invalid: {exc}")
    if problems:
        raise ValidationError("contract is invalid:\n- " + "\n- ".join(problems))
    return meta, contract


def dependency_edges(contract):
    """Return typed semantic dependency edges as (source, dependent, field)."""
    edges = []
    for flow in contract["nodes"].get("F", []):
        for field in ("serves", "uses", "assumptions", "risks", "boundaries", "verifications"):
            for source in flow.get(field, []):
                edges.append((source, flow["id"], f"F.{field}"))
    for unit in contract["nodes"].get("I", []):
        for source in unit.get("realizes", []) + unit.get("validates", []) + unit.get("depends_on", []):
            edges.append((source, unit["id"], "I.binding"))
        for variant in unit.get("variants", []):
            for source in variant.get("uses", []):
                edges.append((source, unit["id"], "I.variant.uses"))
            for segment in variant.get("segments", []):
                for source in segment.get("segment_verifications", []):
                    edges.append((source, unit["id"], "I.segment.verification"))
    for verification in contract["nodes"].get("V", []):
        for source in verification.get("covers", []):
            edges.append((source, verification["id"], "V.covers"))
    for decision in contract["nodes"].get("T", []):
        for source in decision.get("applies_to", []):
            edges.append((decision["id"], source, "T.applies_to"))
    return edges


def impact_closure(contract, seeds, plan=None):
    known = {node["id"] for group in contract["nodes"].values() for node in group}
    unknown = [seed for seed in seeds if seed not in known]
    if unknown:
        raise ValidationError("unknown impact seeds: " + ", ".join(unknown))
    outgoing = {}
    for source, target, field in dependency_edges(contract):
        outgoing.setdefault(source, []).append((target, field))
    closure, queue, reasons = set(seeds), list(seeds), {}
    while queue:
        source = queue.pop(0)
        for target, field in outgoing.get(source, []):
            reasons.setdefault(target, []).append({"from": source, "field": field})
            if target not in closure:
                closure.add(target)
                queue.append(target)
    steps = []
    if plan:
        affected_units = {ident for ident in closure if ident.startswith("I-")}
        steps = [step["id"] for step in plan.get("steps", []) if step.get("unit") in affected_units]
    return {"nodes": sorted(closure), "steps": sorted(steps), "reasons": reasons}


def compile_plan(contract):
    problems = validate_contract(contract)
    if problems:
        raise ValidationError("contract is invalid:\n- " + "\n- ".join(problems))
    steps, unit_dag, variant_rules = [], [], {}
    units = contract["nodes"]["I"]
    for unit in units:
        for dependency in unit["depends_on"]:
            unit_dag.append([dependency, unit["id"]])
        variant_rules[unit["id"]] = []
        for variant in unit["variants"]:
            variant_rules[unit["id"]].append({"id": variant["id"], "selector": variant["selector"]})
            for segment in variant["segments"]:
                step_prefix = unit["id"].replace("-", "")
                step_id = f"S-{step_prefix}-{variant['id']}-{segment['id']}"
                steps.append({
                    "id": step_id,
                    "unit": unit["id"],
                    "variant": variant["id"],
                    "segment": segment["id"],
                    "depends_on_segments": [
                        f"S-{step_prefix}-{variant['id']}-{dep}"
                        for dep in segment["depends_on_segments"]
                    ],
                    "actions": segment["actions"],
                    "artifacts": segment["artifacts"],
                    "interfaces": segment["interfaces"],
                    "side_effects": segment["side_effects"],
                    "idempotency": segment["idempotency"],
                    "build_rollback": segment["build_rollback"],
                    "verifications": segment["segment_verifications"],
                })
    plan = {
        "contract_hash": contract_hash(contract),
        "unit_dag": unit_dag,
        "steps": steps,
        "variant_rules": variant_rules,
        "runtime": {
            "status": "planning",
            "selected_variants": {},
            "selection_events": {},
            "step_states": {step["id"]: "dormant" for step in steps},
            "attempts": {},
            "applied_event_ids": [],
            "revision": 0,
        },
    }
    plan["plan_structure_hash"] = plan_hash(plan)
    step_ids = [step["id"] for step in steps]
    if len(step_ids) != len(set(step_ids)):
        raise ValidationError("compiler produced duplicate step IDs")
    return plan


def replay_plan_runtime(plan, events, problems):
    runtime = plan.get("runtime", {})
    matching = [
        event for event in events
        if event.get("type") in {"step-transition", "plan-transition"}
        and event.get("contract_hash") == plan.get("contract_hash")
        and event.get("plan_structure_hash") == plan.get("plan_structure_hash")
    ]
    if runtime.get("status") == "planning":
        if matching:
            problems.append("planning PLAN has runtime transition events")
        return None
    selected = runtime.get("selected_variants", {})
    if not isinstance(selected, dict):
        problems.append("PLAN runtime selected_variants cannot be replayed")
        return None
    expected = {
        "status": "building",
        "step_states": {
            step["id"]: ("pending" if selected.get(step.get("unit")) == step.get("variant") else "dormant")
            for step in plan.get("steps", []) if isinstance(step, dict) and "id" in step
        },
        "attempts": {}, "applied_event_ids": [], "revision": 0,
    }
    by_revision = {}
    for event in matching:
        revision = event.get("from_plan_revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            problems.append(f"{event.get('id')}: invalid from_plan_revision")
            continue
        by_revision.setdefault(revision, []).append(event)
    used_attempts = set()
    event_index = {event.get("id"): event for event in events}
    event_positions = {event.get("id"): index for index, event in enumerate(events)}
    evidence_floor = {step_id: -1 for step_id in expected["step_states"]}
    last_transition_position = -1
    while expected["revision"] in by_revision:
        candidates = by_revision.pop(expected["revision"])
        if len(candidates) != 1:
            problems.append(f"PLAN runtime ledger fork at revision {expected['revision']}")
            break
        event = candidates[0]
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id.strip():
            problems.append("PLAN runtime event has no ID")
            break
        event_position = event_positions.get(event_id, -1)
        if event_position <= last_transition_position:
            problems.append(f"{event_id}: runtime revision order differs from ledger order")
            break
        if event.get("type") == "plan-transition":
            target = event.get("to_status")
            if target not in PLAN_RUNTIME_TRANSITIONS.get(expected["status"], set()):
                problems.append(f"{event_id}: illegal replayed PLAN transition")
                break
            if target == "done":
                audit = event_index.get(event.get("converge_audit_event"))
                if (not isinstance(event.get("reconcile_hash"), str)
                        or not audit or audit.get("type") != "converge-audit"
                        or audit.get("result") != "passed"
                        or audit.get("contract_hash") != plan.get("contract_hash")
                        or audit.get("plan_structure_hash") != plan.get("plan_structure_hash")
                        or audit.get("reconcile_hash") != event.get("reconcile_hash")
                        or audit.get("plan_revision") != event.get("from_plan_revision")
                        or event_positions.get(audit.get("id"), -1) <= last_transition_position
                        or event_positions.get(audit.get("id"), len(events)) >= event_position):
                    problems.append(f"{event_id}: done transition lacks reconcile/converge proof")
                    break
            expected["status"] = target
        else:
            step_id = event.get("step_id")
            step = next((item for item in plan.get("steps", []) if item.get("id") == step_id), None)
            if not step or event.get("step_hash") != step_hash(step):
                problems.append(f"{event_id}: stale or unknown replayed step")
                break
            if expected["status"] != "building" or selected.get(step.get("unit")) != step.get("variant"):
                problems.append(f"{event_id}: replayed step is not executable")
                break
            current = expected["step_states"].get(step_id)
            target = event.get("to_state")
            if target not in STEP_RUNTIME_TRANSITIONS.get(current, set()):
                problems.append(f"{event_id}: illegal replayed step transition")
                break
            expected["step_states"][step_id] = target
            if target == "invalidated":
                evidence_floor[step_id] = event_positions.get(event_id, len(events))
            if target == "complete":
                attempt_id = event.get("attempt_id")
                if not isinstance(attempt_id, str) or not attempt_id.strip() or attempt_id in used_attempts:
                    problems.append(f"{event_id}: complete needs a fresh attempt ID")
                    break
                attempt = event_index.get(attempt_id)
                attempt_position = event_positions.get(attempt_id, -1)
                transition_position = event_positions.get(event_id, len(events))
                verification_ids = attempt.get("verification_events", []) if isinstance(attempt, dict) else []
                if (not attempt or attempt_position <= evidence_floor[step_id]
                        or attempt_position >= transition_position
                        or any(event_positions.get(item, -1) <= evidence_floor[step_id]
                               or event_positions.get(item, len(events)) >= attempt_position
                               for item in verification_ids)):
                    problems.append(f"{event_id}: attempt and V evidence are not fresh for this execution")
                    break
                used_attempts.add(attempt_id)
                expected["attempts"].setdefault(step_id, []).append(attempt_id)
        expected["applied_event_ids"].append(event_id)
        expected["revision"] += 1
        last_transition_position = event_position
    if by_revision:
        problems.append("PLAN runtime ledger has a gap or stale branch")
    defaults = {"applied_event_ids": [], "revision": 0}
    for field in ("status", "step_states", "attempts", "applied_event_ids", "revision"):
        if runtime.get(field, defaults.get(field, {})) != expected[field]:
            problems.append(f"PLAN runtime.{field} does not match ledger replay")
    return expected


def trusted_step_evidence_problems(event, verification, events=None):
    problems = []
    if verification.get("type") == "human":
        owner = next((item for item in (events or []) if item.get("id") == event.get("owner_event")), {})
        if (event.get("producer") != "check.py/record-human-step-v1"
                or owner.get("type") != "owner-decision"
                or owner.get("decision") != "human-verification"
                or owner.get("result") != "accepted"
                or not isinstance(owner.get("observation"), str)
                or not owner.get("observation", "").strip()
                or any(owner.get(key) != event.get(key) for key in (
                    "step_id", "v_id", "contract_hash", "plan_structure_hash", "step_hash"))
                or event.get("output_hash") != digest(owner, "human-step-owner-decision")):
            return ["human verification lacks an appropriately bound owner decision proof"]
        return []
    if event.get("producer") != "check.py/verify-step-v1":
        return ["passing verification was not generated by verify-step"]
    raw_path = event.get("evidence_path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return ["verification evidence_path is missing"]
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        evidence_bytes = path.read_bytes()
        payload = json.loads(evidence_bytes.decode("utf-8"))
        actual_hash = hashlib.sha256(evidence_bytes).hexdigest()
    except (OSError, ValueError, TypeError) as exc:
        return [f"verification evidence is unavailable or invalid: {exc}"]
    if not isinstance(payload, dict):
        return ["verification evidence must be an object"]
    if actual_hash != event.get("output_hash"):
        problems.append("verification output_hash does not match evidence file")
    if payload.get("event_id") != event.get("id"):
        problems.append("verification evidence event_id mismatch")
    for field in ("step_id", "v_id", "contract_hash", "plan_structure_hash", "step_hash"):
        if payload.get(field) != event.get(field):
            problems.append(f"verification evidence {field} mismatch")
    if (payload.get("kind") != "step-verification"
            or payload.get("command") != verification.get("command")
            or payload.get("result") != "passed"
            or type(payload.get("exit_code")) is not int
            or payload.get("exit_code") != 0
            or payload.get("timed_out") is not False):
        problems.append("verification evidence does not prove an executed passing command")
    if "assertion" in verification and (
            payload.get("assertion") != verification["assertion"]
            or payload.get("assertion_passed") is not True
            or not evaluate_assertion(payload.get("stdout"), verification["assertion"])):
        problems.append("verification evidence does not prove the assertion")
    return problems


def validate_plan(plan, contract, events=None):
    problems = []
    if plan.get("contract_hash") != contract_hash(contract):
        problems.append("PLAN contract_hash mismatch")
    try:
        if plan.get("plan_structure_hash") != plan_hash(plan):
            problems.append("PLAN plan_structure_hash mismatch")
    except KeyError as exc:
        problems.append(f"PLAN missing structure field {exc}")
    expected = compile_plan(contract)
    if plan_projection(plan) != plan_projection(expected):
        problems.append("PLAN is not the deterministic compilation of the contract")
    runtime = plan.get("runtime", {})
    if runtime.get("status") not in PLAN_STATUS:
        problems.append("PLAN runtime.status is invalid")
    selected = runtime.get("selected_variants")
    selection_events = runtime.get("selection_events")
    step_states = runtime.get("step_states")
    attempts = runtime.get("attempts")
    applied_event_ids = runtime.get("applied_event_ids", [])
    if not isinstance(selected, dict) or not isinstance(selection_events, dict):
        problems.append("PLAN variant runtime fields must be objects")
        selected, selection_events = {}, {}
    if not isinstance(step_states, dict) or not isinstance(attempts, dict):
        problems.append("PLAN step_states and attempts must be objects")
        step_states, attempts = {}, {}
    if not isinstance(applied_event_ids, list) or any(not isinstance(item, str) for item in applied_event_ids):
        problems.append("PLAN runtime.applied_event_ids must be an array of event IDs")
    if (not isinstance(runtime.get("revision", 0), int)
            or isinstance(runtime.get("revision", 0), bool)
            or runtime.get("revision", 0) < 0):
        problems.append("PLAN runtime.revision must be a non-negative integer")
    expected_step_ids = {step["id"] for step in plan.get("steps", [])}
    if set(step_states) != expected_step_ids:
        problems.append("PLAN step_states keys do not match compiled steps")
    legal_step_states = {"dormant", "pending", "selected", "executing", "verifying", "complete", "blocked", "invalidated"}
    if any(state not in legal_step_states for state in step_states.values()):
        problems.append("PLAN contains an invalid step state")
    variants = {unit: {item["id"] for item in rules} for unit, rules in plan.get("variant_rules", {}).items()}
    active_units = {unit["id"] for unit in contract["nodes"]["I"] if unit.get("status") == "active"}
    if any(unit not in variants or variant not in variants.get(unit, set()) for unit, variant in selected.items()):
        problems.append("PLAN selected_variants contains an unknown unit or variant")
    if runtime.get("status") in {"building", "paused", "suspended", "done"}:
        if set(selected) != active_units or any(selected[unit] not in variants[unit] for unit in active_units):
            problems.append("PLAN must select exactly one compiled variant for every unit")
        if set(selection_events) != active_units or any(not selection_events.get(unit) for unit in active_units):
            problems.append("PLAN selected variants require selection event IDs")
    event_index = {event.get("id"): event for event in (events or [])}
    verification_nodes = {
        node.get("id"): node for node in contract.get("nodes", {}).get("V", [])
        if isinstance(node, dict)
    }
    if runtime.get("status") in {"building", "paused", "suspended", "done"} and events is None:
        problems.append("PLAN runtime validation requires the event ledger")
    for unit, event_id in selection_events.items():
        event = event_index.get(event_id)
        if not event or event.get("type") != "variant-selection" or event.get("unit") != unit or event.get("variant") != selected.get(unit):
            problems.append(f"{unit}: invalid variant selection event")
            continue
        if event.get("contract_hash") != plan.get("contract_hash") or event.get("plan_structure_hash") != plan.get("plan_structure_hash"):
            problems.append(f"{unit}: variant selection belongs to another contract or PLAN")
        owner_event = event_index.get(event.get("owner_event"))
        if (event.get("authorization") != "owner-confirmed"
                or not owner_event
                or owner_event.get("type") != "owner-decision"
                or owner_event.get("decision") != "plan-confirmation"
                or owner_event.get("result") != "accepted"
                or owner_event.get("contract_hash") != plan.get("contract_hash")
                or owner_event.get("plan_structure_hash") != plan.get("plan_structure_hash")):
            problems.append(f"{unit}: variant selection lacks a bound owner confirmation event")
        rule = next((item for item in plan.get("variant_rules", {}).get(unit, []) if item["id"] == selected.get(unit)), None)
        selector = rule.get("selector", {}) if rule else {}
        evidence = event.get("selector_evidence")
        if selector.get("default") is True:
            if evidence != "default":
                problems.append(f"{unit}: default variant selection must record selector_evidence=default")
        else:
            evidence_event = event_index.get(evidence)
            if (not evidence_event or evidence_event.get("type") != "evidence"
                    or evidence_event.get("contract_hash") != plan.get("contract_hash")
                    or evidence_event.get("selector_hash") != digest(selector, "variant-selector")):
                problems.append(f"{unit}: non-default variant selection needs a ledger evidence event")
    for step in plan.get("steps", []):
        is_selected = selected.get(step["unit"]) == step["variant"]
        state = step_states.get(step["id"])
        if not is_selected and state != "dormant":
            problems.append(f"{step['id']}: unselected variant must remain dormant")
        if is_selected and runtime.get("status") in {"building", "paused", "suspended", "done"} and state == "dormant":
            problems.append(f"{step['id']}: selected variant cannot remain dormant")
        if runtime.get("status") == "done" and is_selected and state != "complete":
            problems.append(f"{step['id']}: done PLAN has incomplete selected step")
        if state == "complete":
            attempt_ids = attempts.get(step["id"])
            if not isinstance(attempt_ids, list) or not attempt_ids:
                problems.append(f"{step['id']}: complete step needs attempt evidence")
                continue
            attempt = event_index.get(attempt_ids[-1])
            if not attempt or attempt.get("type") != "attempt" or attempt.get("step_id") != step["id"] or attempt.get("result") != "passed":
                problems.append(f"{step['id']}: final attempt is not a passed ledger event")
                continue
            expected_step_hash = step_hash(step)
            if (attempt.get("contract_hash") != plan.get("contract_hash")
                    or attempt.get("plan_structure_hash") != plan.get("plan_structure_hash")
                    or attempt.get("step_hash") != expected_step_hash):
                problems.append(f"{step['id']}: attempt belongs to another contract, PLAN, or step spec")
                continue
            if contract.get("workflow_protocol") == "v0.2" and not (
                    isinstance(attempt.get("subagent_id"), str) and attempt.get("subagent_id", "").strip()):
                problems.append(f"{step['id']}: v0.2 attempt requires implementation subagent_id")
                continue
            verified = set()
            for event_id in attempt.get("verification_events", []):
                verification = event_index.get(event_id)
                if (verification and verification.get("type") == "step-verification"
                        and verification.get("step_id") == step["id"]
                        and verification.get("result") == "passed"
                        and verification.get("contract_hash") == plan.get("contract_hash")
                        and verification.get("plan_structure_hash") == plan.get("plan_structure_hash")
                        and verification.get("step_hash") == expected_step_hash):
                    if contract.get("workflow_protocol") == "v0.2":
                        evidence_problems = trusted_step_evidence_problems(
                            verification, verification_nodes.get(verification.get("v_id"), {}), events,
                        )
                        if evidence_problems:
                            problems.extend(f"{step['id']}: {item}" for item in evidence_problems)
                            continue
                    verified.add(verification.get("v_id"))
            if not set(step.get("verifications", [])).issubset(verified):
                problems.append(f"{step['id']}: final attempt lacks all required V evidence")
    selected_steps = {step["id"]: step for step in plan.get("steps", []) if selected.get(step["unit"]) == step["variant"]}
    for step in selected_steps.values():
        if step_states.get(step["id"]) == "complete":
            for dependency in step.get("depends_on_segments", []):
                if step_states.get(dependency) != "complete":
                    problems.append(f"{step['id']}: completed before segment dependency {dependency}")
            for source, target in plan.get("unit_dag", []):
                if target == step["unit"]:
                    source_steps = [item for item in selected_steps.values() if item["unit"] == source]
                    if any(step_states.get(item["id"]) != "complete" for item in source_steps):
                        problems.append(f"{step['id']}: completed before unit dependency {source}")
    for step in plan.get("steps", []):
        if not STEP_RE.match(step.get("id", "")):
            problems.append(f"invalid step id {step.get('id')}")
    if events is not None:
        replay_plan_runtime(plan, events, problems)
    return problems


def plan_artifact_problems(meta, plan, contract, events=None, require_building=False,
                           require_resumable=False):
    problems = validate_plan(plan, contract, events)
    if meta.get("contract-hash") != plan.get("contract_hash"):
        problems.append("PLAN frontmatter contract-hash mismatch")
    if meta.get("plan-structure-hash") != plan.get("plan_structure_hash"):
        problems.append("PLAN frontmatter plan-structure-hash mismatch")
    runtime = plan.get("runtime", {})
    if not isinstance(runtime, dict):
        runtime = {}
    if meta.get("status") != runtime.get("status"):
        problems.append("PLAN frontmatter status does not match runtime.status")
    if require_building and runtime.get("status") != "building":
        problems.append("PLAN must be confirmed and building before construction")
    if require_resumable and runtime.get("status") not in {"building", "paused", "suspended"}:
        problems.append("PLAN must be building, paused, or suspended to resume")
    return problems


def reconcile_closure(contract, plan, events, orders):
    """Completion-time closure matrix: P -> F -> I -> S -> V with bound evidence.

    Read-only projection for the converge audit. Structural problems are
    rejected before this runs; the findings below are machine-computable
    closure gaps and never semantic judgments.
    """
    runtime = plan.get("runtime", {})
    selected = runtime.get("selected_variants", {})
    step_states = runtime.get("step_states", {})
    steps = {step["id"]: step for step in plan.get("steps", [])}
    event_index = {event.get("id"): event for event in events}
    current_contract = plan.get("contract_hash")
    findings, coverage = [], {}

    for purpose_node in contract["nodes"].get("P", []):
        if purpose_node.get("status") != "active":
            continue
        purpose = purpose_node["id"]
        flows = [flow["id"] for flow in contract["nodes"].get("F", [])
                 if flow.get("status") == "active" and purpose in flow.get("serves", [])]
        units = [unit["id"] for unit in contract["nodes"].get("I", [])
                 if unit.get("status") == "active" and unit.get("kind") == "build"
                 and any(flow in unit.get("realizes", []) for flow in flows)]
        step_view, open_steps = {}, []
        for step_id, step in steps.items():
            if step.get("unit") in units and selected.get(step.get("unit")) == step.get("variant"):
                state = step_states.get(step_id, "unknown")
                step_view[step_id] = state
                if state != "complete":
                    open_steps.append(f"{step_id}={state}")
        unselected = [unit for unit in units if unit not in selected]
        verifications = [node["id"] for node in contract["nodes"].get("V", [])
                         if node.get("status") == "active" and purpose in node.get("covers", [])]
        closed = bool(flows and units and verifications) and not open_steps and not unselected
        if not closed:
            findings.append(
                f"{purpose}: coverage open (flows={flows}, units={units}, "
                f"unselected_units={unselected}, verifications={verifications}, open_steps={open_steps})"
            )
        coverage[purpose] = {
            "flows": flows,
            "units": units,
            "steps": step_view,
            "verifications": verifications,
            "closed": closed,
        }

    for node in contract["nodes"].get("V", []):
        ident = node.get("id")
        if node.get("status") != "active":
            continue
        evidence = [event for event in events
                    if event.get("type") in {"verification", "step-verification"}
                    and event.get("v_id") == ident and event.get("result") == "passed"
                    and event.get("contract_hash") == current_contract]
        if not evidence:
            findings.append(f"{ident}: no passing evidence event bound to the current contract hash")
            continue
        if node.get("type") == "human" and not any(
                event_index.get(event.get("owner_event"), {}).get("type") == "owner-decision"
                for event in evidence):
            findings.append(f"{ident}: human verification lacks a bound owner decision event")

    stale = sorted(event.get("id") for event in events
                   if event.get("type") in {"attempt", "step-verification", "variant-selection"}
                   and (event.get("contract_hash") not in (None, current_contract)
                        or event.get("plan_structure_hash") not in (None, plan.get("plan_structure_hash"))))
    blocking = sorted(order.get("id") for order in orders.get("orders", [])
                      if order.get("status") in BLOCKING_CR)
    for ident in blocking:
        findings.append(f"blocking CR: {ident}")
    dormant = sorted(f"{unit}:{variant['id']}"
                     for unit, rules in plan.get("variant_rules", {}).items()
                     for variant in rules if selected.get(unit) != variant["id"])
    return {
        "status": "clean" if not findings else "incomplete",
        "contract_hash": current_contract,
        "plan_structure_hash": plan.get("plan_structure_hash"),
        "plan_runtime_status": runtime.get("status"),
        "selected_variants": selected,
        "dormant_variants": dormant,
        "coverage": coverage,
        "open_steps": sorted(step_id for step_id, step in steps.items()
                             if selected.get(step.get("unit")) == step.get("variant")
                             and step_states.get(step_id) != "complete"),
        "stale_evidence_events": stale,
        "blocking_crs": blocking,
        "findings": findings,
    }


def reconcile_result_hash(matrix):
    projection = {key: value for key, value in matrix.items() if key != "plan_runtime_status"}
    return digest(projection, "reconcile-result")


def validate_change_orders(data):
    problems = []
    if not isinstance(data.get("revision"), int) or data.get("revision", -1) < 0:
        problems.append("change-orders revision must be a non-negative integer")
    seen = set()
    valid_states = set(CR_TRANSITIONS) | {state for targets in CR_TRANSITIONS.values() for state in targets}
    for order in data.get("orders", []):
        ident = order.get("id", "")
        if not re.match(r"^CR-\d{2,}$", ident) or ident in seen:
            problems.append(f"invalid or duplicate CR id {ident!r}")
        seen.add(ident)
        require(order, ("status", "trigger", "contract_before", "impact_seed", "impact_closure", "waiver_eligible"), ident, problems)
        if order.get("status") not in valid_states:
            problems.append(f"{ident}: invalid status")
        if order.get("status") == "closed" and not order.get("final_audit_event"):
            problems.append(f"{ident}: closed CR needs final_audit_event")
        if order.get("status") == "waived-verified" and not order.get("verification_evidence"):
            problems.append(f"{ident}: waiver needs executed verification evidence")
    return problems


def validate_cr_provenance(data, events):
    problems = []
    index = {event.get("id"): event for event in events}
    applied_global = []
    for order in data.get("orders", []):
        applied = order.get("applied_event_ids", [])
        if order.get("status") != "proposed" and not applied:
            problems.append(f"{order.get('id')}: non-proposed CR lacks transition history")
        for event_id in applied:
            event = index.get(event_id)
            if not event or event.get("type") != "cr-transition" or event.get("cr_id") != order.get("id"):
                problems.append(f"{order.get('id')}: invalid applied event {event_id}")
            else:
                applied_global.append(event)
        current = "proposed"
        for event in sorted((index[event_id] for event_id in applied if event_id in index), key=lambda item: item.get("from_revision", -1)):
            if event.get("from_status") != current:
                problems.append(f"{order.get('id')}: discontinuous transition history")
                break
            try:
                validate_transition(current, event.get("to_status"), CR_TRANSITIONS, "CR")
            except ValidationError as exc:
                problems.append(str(exc))
                break
            current = event.get("to_status")
        if applied:
            last = index.get(applied[-1], {})
            if last.get("to_status") != order.get("status"):
                problems.append(f"{order.get('id')}: status does not match final transition")
        for evidence_id in order.get("verification_evidence", []):
            try:
                find_ledger_event(events, evidence_id, "verification", order.get("id"))
            except ValidationError as exc:
                problems.append(str(exc))
        if order.get("final_audit_event"):
            try:
                audit = find_ledger_event(events, order["final_audit_event"], "final-audit", order.get("id"))
                if audit.get("result") != "passed" or audit.get("contract_hash") != order.get("contract_after"):
                    problems.append(f"{order.get('id')}: final audit is not passed for contract_after")
            except ValidationError as exc:
                problems.append(str(exc))
    applied_ids = {event.get("id") for event in applied_global}
    revisions = sorted(event.get("from_revision") for event in applied_global)
    if revisions != list(range(data.get("revision", 0))):
        problems.append("change-orders revision does not match contiguous transition history")
    orphan = [event for event in events if event.get("type") == "cr-transition" and event.get("id") not in applied_ids]
    if orphan:
        problems.append("change-orders projection has unapplied CR ledger events")
    return problems


def enforce_cr_gate(path, ledger_path, recovery_cr=None):
    _, data = read_artifact(path, "change-orders")
    problems = validate_change_orders(data)
    events = load_ledger(ledger_path)
    problems.extend(validate_cr_provenance(data, events))
    if problems:
        raise ValidationError("invalid change-orders: " + "; ".join(problems))
    blocking = [order for order in data.get("orders", []) if order.get("status") in BLOCKING_CR]
    if not blocking:
        if recovery_cr:
            raise ValidationError(f"no blocking CR authorizes recovery for {recovery_cr}")
        return None
    if recovery_cr:
        target = next((order for order in blocking if order.get("id") == recovery_cr), None)
        if target and target.get("status") in {"approved", "applying", "verifying"}:
            return target
        raise ValidationError(f"CR recovery is not authorized for {recovery_cr}")
    raise ValidationError("ordinary construction blocked by: " + ", ".join(order["id"] for order in blocking))


def enforce_recovery_scope(old_plan, new_plan, order):
    allowed = set(order.get("impact_closure", []))
    old_steps = {step["id"]: step for step in old_plan.get("steps", [])}
    new_steps = {step["id"]: step for step in new_plan.get("steps", [])}
    for step_id in set(old_steps) | set(new_steps):
        if old_steps.get(step_id) != new_steps.get(step_id):
            unit = (new_steps.get(step_id) or old_steps.get(step_id)).get("unit")
            if step_id not in allowed and unit not in allowed:
                raise ValidationError(f"CR recovery changes out-of-closure step: {step_id}")
    for unit in set(old_plan.get("variant_rules", {})) | set(new_plan.get("variant_rules", {})):
        if old_plan.get("variant_rules", {}).get(unit) != new_plan.get("variant_rules", {}).get(unit) and unit not in allowed:
            raise ValidationError(f"CR recovery changes out-of-closure variants: {unit}")
    old_edges = {tuple(edge) for edge in old_plan.get("unit_dag", [])}
    new_edges = {tuple(edge) for edge in new_plan.get("unit_dag", [])}
    for source, target in old_edges ^ new_edges:
        if source not in allowed and target not in allowed:
            raise ValidationError(f"CR recovery changes out-of-closure DAG edge: {source} -> {target}")


def enforce_recovery_contract_scope(old_contract, new_contract, order):
    if contract_hash(old_contract) != order.get("contract_before"):
        raise ValidationError("CR contract_before does not match the previous contract")
    if order.get("contract_after") and contract_hash(new_contract) != order.get("contract_after"):
        raise ValidationError("CR contract_after does not match the current contract")
    allowed = set(order.get("impact_closure", []))
    old_nodes = {node["id"]: node for group in old_contract["nodes"].values() for node in group}
    new_nodes = {node["id"]: node for group in new_contract["nodes"].values() for node in group}
    for ident in set(old_nodes) | set(new_nodes):
        if old_nodes.get(ident) != new_nodes.get(ident) and ident not in allowed:
            raise ValidationError(f"CR recovery changes out-of-closure contract node: {ident}")
    old_root = {key: value for key, value in old_contract.items() if key != "nodes"}
    new_root = {key: value for key, value in new_contract.items() if key != "nodes"}
    if old_root != new_root and "CONTRACT" not in allowed:
        raise ValidationError("CR recovery changes contract-level control fields outside closure")


def validate_transition(current, target, table, label):
    if target not in table.get(current, set()):
        raise ValidationError(f"illegal {label} transition: {current} -> {target}")


def initial_state(meta, contract):
    status = meta.get("status", "draft")
    phase = meta.get("phase", "intake")
    if status not in CONTRACT_STATUS or phase not in STATUS_PHASES.get(status, set()):
        raise ValidationError(f"invalid initial state: {status}/{phase}")
    control = contract["control"]
    return {
        "revision": 0,
        "status": status,
        "phase": phase,
        "profile": contract["profile"],
        "interaction": control["interaction"],
        "budgets": {
            "audit": control["audit_budget"],
            "research": control["research_budget"],
            "prototype": control["prototype_budget"],
        },
        "usage": {"audit": 0, "research": 0, "prototype": 0},
        "applied_event_ids": [],
    }


def event_payload(event):
    return {key: value for key, value in event.items() if key not in {"from_revision", "from_status", "authorized_capability"}}


def load_ledger(path):
    if not Path(path).exists():
        return []
    events, ids = [], {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        ident = event.get("id")
        if ident in ids:
            if event_payload(ids[ident]) != event_payload(event):
                raise ValidationError(f"ledger event ID has conflicting payloads: {ident}")
            raise ValidationError(f"ledger contains a duplicate event ID: {ident}")
        ids[ident] = event
        events.append(event)
    return events


def append_immutable_event(ledger_path, submitted):
    ledger_path = Path(ledger_path)
    with file_lock(ledger_path):
        events = load_ledger(ledger_path)
        recorded = next((event for event in events if event.get("id") == submitted["id"]), None)
        if recorded:
            if event_payload(recorded) != event_payload(submitted):
                raise ValidationError(f"evidence event ID payload conflict: {submitted['id']}")
            return recorded
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(submitted, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return submitted


def record_evidence_event(ledger_path, event_path):
    ledger_path = Path(ledger_path)
    submitted = json.loads(Path(event_path).read_text(encoding="utf-8"))
    problems = []
    require(submitted, ("id", "type"), "evidence event", problems)
    if problems:
        raise ValidationError("; ".join(problems))
    if not isinstance(submitted["type"], str) or submitted["type"] not in {
        "verification", "final-audit", "owner-decision", "evidence",
        "release-verification", "converge-audit",
        "variant-selection", "attempt", "step-verification",
        "tdd-red", "tdd-green",
    }:
        raise ValidationError("record accepts only immutable evidence event types")
    if submitted["type"] == "verification":
        require(submitted, ("cr_id",), "evidence event", problems)
    if submitted["type"] == "release-verification":
        require(submitted, ("v_id", "result", "output_hash", "contract_hash"),
                "release verification", problems)
        if submitted.get("result") != "passed":
            raise ValidationError("release-verification must record result=passed")
    if submitted["type"] in {"tdd-red", "tdd-green"}:
        require(submitted, ("step_id", "v_id", "result", "output_hash", "contract_hash", "plan_structure_hash", "step_hash"), "tdd evidence event", problems)
        expected_result = "failed" if submitted["type"] == "tdd-red" else "passed"
        if submitted.get("result") != expected_result:
            raise ValidationError(f"{submitted['type']} must record result={expected_result}")
    if submitted["type"] == "final-audit":
        require(submitted, ("contract_hash", "result"), "final audit event", problems)
    if submitted["type"] == "owner-decision":
        require(submitted, ("decision", "result", "contract_hash"), "owner decision", problems)
        if submitted.get("decision") == "plan-confirmation":
            require(submitted, ("plan_structure_hash",), "PLAN owner decision", problems)
            if submitted.get("result") != "accepted":
                raise ValidationError("PLAN owner decision must record result=accepted")
    if submitted["type"] == "converge-audit":
        require(submitted, ("result", "contract_hash", "plan_structure_hash",
                            "reconcile_hash", "plan_revision"),
                "converge audit", problems)
        if submitted.get("result") != "passed":
            raise ValidationError("converge-audit must record result=passed")
    if submitted["type"] == "verification":
        require(submitted, ("v_id", "result", "output_hash"), "verification event", problems)
        if submitted.get("result") != "passed":
            raise ValidationError("only passed verification can satisfy a CR transition")
    if submitted["type"] == "variant-selection":
        require(submitted, ("unit", "variant", "selector_evidence", "authorization", "owner_event", "contract_hash", "plan_structure_hash"), "variant selection", problems)
        if submitted.get("authorization") != "owner-confirmed":
            raise ValidationError("variant selection must be owner-confirmed")
    if submitted["type"] == "attempt":
        require(submitted, ("step_id", "result", "verification_events", "contract_hash", "plan_structure_hash", "step_hash"), "attempt event", problems)
        if submitted.get("subagent_id") is not None and not (
                isinstance(submitted.get("subagent_id"), str) and submitted["subagent_id"].strip()):
            raise ValidationError("attempt subagent_id must be a non-empty string when present")
    if submitted["type"] == "step-verification":
        require(submitted, ("step_id", "v_id", "result", "output_hash", "contract_hash", "plan_structure_hash", "step_hash"), "step verification", problems)
        if submitted.get("result") == "passed":
            raise ValidationError("passing step-verification must be generated by verify-step or record-human-step")
    if problems:
        raise ValidationError("; ".join(problems))
    return append_immutable_event(ledger_path, submitted)


def verify_step(plan_path, step_id, v_id, contract_path, ledger_path,
                evidence_path, event_id, owner_event=None, recover_interrupted=False):
    with file_lock(str(plan_path) + ".runtime"):
        meta, plan = read_artifact(plan_path, "plan")
        _, contract = read_checked_contract(
            contract_path, require_released=True, ledger_path=ledger_path,
        )
        events = load_ledger(ledger_path)
        recorded = next((item for item in events if item.get("id") == event_id), None)
        if recorded:
            step = next((item for item in plan.get("steps", []) if item.get("id") == step_id), None)
            verification = next((item for item in contract["nodes"]["V"]
                                 if item.get("id") == v_id and item.get("status") == "active"), None)
            if (not step or not verification or v_id not in step.get("verifications", [])
                    or recorded.get("contract_hash") != contract_hash(contract)
                    or plan.get("contract_hash") != contract_hash(contract)
                    or recorded.get("plan_structure_hash") != plan_hash(plan)
                    or plan.get("plan_structure_hash") != plan_hash(plan)
                    or recorded.get("step_hash") != step_hash(step)):
                raise ValidationError("recorded verification bindings are stale")
            producer = "check.py/record-human-step-v1" if owner_event is not None else "check.py/verify-step-v1"
            if (recorded.get("type") != "step-verification"
                    or recorded.get("producer") != producer
                    or recorded.get("step_id") != step_id
                    or recorded.get("v_id") != v_id):
                raise ValidationError(f"verification event ID payload conflict: {event_id}")
            if owner_event is not None:
                if (verification.get("type") != "human"
                        or recorded.get("owner_event") != owner_event
                        or recorded.get("result") != "passed"
                        or trusted_step_evidence_problems(recorded, verification, events)):
                    raise ValidationError("recorded human verification evidence is invalid")
                return recorded
            if verification.get("type") == "human":
                raise ValidationError("human verification cannot use verify-step")
            recorded_evidence = Path(recorded.get("evidence_path", ""))
            if not recorded_evidence.is_absolute():
                recorded_evidence = Path.cwd() / recorded_evidence
            if recorded_evidence.resolve() != Path(evidence_path).resolve():
                raise ValidationError("verification event ID evidence path conflict")
            if (not recorded_evidence.is_file()
                    or hashlib.sha256(recorded_evidence.read_bytes()).hexdigest() != recorded.get("output_hash")):
                raise ValidationError("recorded verification evidence is missing or stale")
            if recorded.get("result") == "passed" and trusted_step_evidence_problems(recorded, verification):
                raise ValidationError("recorded verification evidence is invalid")
            return recorded

        replay_problems = []
        recovered = replay_plan_runtime(plan, events, replay_problems)
        hard_replay_problems = [item for item in replay_problems if "does not match ledger replay" not in item]
        if hard_replay_problems:
            raise ValidationError("PLAN runtime ledger is invalid:\n- " + "\n- ".join(hard_replay_problems))
        if recovered:
            for field, value in recovered.items():
                plan["runtime"][field] = value
            meta["status"] = plan["runtime"]["status"]
        problems = plan_artifact_problems(meta, plan, contract, events, require_building=True)
        if problems:
            raise ValidationError("PLAN is invalid:\n- " + "\n- ".join(problems))
        step = next((item for item in plan.get("steps", []) if item.get("id") == step_id), None)
        if not step:
            raise ValidationError(f"unknown PLAN step: {step_id}")
        if plan["runtime"].get("selected_variants", {}).get(step.get("unit")) != step.get("variant"):
            raise ValidationError("verify-step requires a selected variant step")
        if plan["runtime"].get("step_states", {}).get(step_id) != "verifying":
            raise ValidationError("verify-step requires step state=verifying")
        if v_id not in step.get("verifications", []):
            raise ValidationError(f"{v_id} is not bound to PLAN step {step_id}")
        verification = next(
            (item for item in contract.get("nodes", {}).get("V", [])
             if item.get("id") == v_id and item.get("status") == "active"),
            None,
        )
        if not verification:
            raise ValidationError(f"active contract verification not found: {v_id}")
        if owner_event is not None:
            if verification.get("type") != "human":
                raise ValidationError("record-human-step requires a human verification")
            owner = next((item for item in events if item.get("id") == owner_event), {})
            event = {
                "id": event_id, "type": "step-verification",
                "producer": "check.py/record-human-step-v1", "result": "passed",
                "step_id": step_id, "v_id": v_id, "owner_event": owner_event,
                "contract_hash": plan["contract_hash"],
                "plan_structure_hash": plan["plan_structure_hash"], "step_hash": step_hash(step),
                "output_hash": digest(owner, "human-step-owner-decision"),
            }
            problems = trusted_step_evidence_problems(event, verification, events)
            if problems:
                raise ValidationError("; ".join(problems))
            return append_immutable_event(ledger_path, event)
        if verification.get("type") == "human":
            raise ValidationError("human verification cannot use verify-step")
        command = verification.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValidationError("automated verification command must be a non-empty string")
        timeout_seconds = verification.get("timeout_seconds", 300)
        if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= 3600:
            raise ValidationError("verification timeout_seconds must be 1..3600")

        evidence_path = Path(evidence_path)
        if ".." in evidence_path.parts:
            raise ValidationError("step evidence path cannot contain parent traversal")
        resolved_evidence = evidence_path.resolve() if evidence_path.is_absolute() else (Path.cwd() / evidence_path).resolve()
        allowed_root = (Path(contract_path).resolve().parent / "evidence").resolve()
        try:
            resolved_evidence.relative_to(allowed_root)
        except ValueError as exc:
            raise ValidationError("step evidence must live under the contract package evidence directory") from exc
        step_digest = step_hash(step)
        payload, output_hash = run_command_evidence(
            command, Path.cwd(), resolved_evidence,
            {
                "kind": "step-verification",
                "event_id": event_id,
                "step_id": step_id,
                "v_id": v_id,
                "contract_hash": plan["contract_hash"],
                "plan_structure_hash": plan["plan_structure_hash"],
                "step_hash": step_digest,
                "expected": verification.get("expected"),
                "assertion_kind": verification.get("assertion_kind"),
                "empty_result_policy": verification.get("empty_result_policy"),
                **({"assertion": verification["assertion"]} if "assertion" in verification else {}),
            },
            timeout_seconds, recover=True, recover_interrupted=recover_interrupted,
        )
        try:
            recorded_evidence_path = resolved_evidence.relative_to(Path.cwd().resolve()).as_posix()
        except ValueError:
            recorded_evidence_path = str(resolved_evidence)
        event = {
            "id": event_id,
            "type": "step-verification",
            "producer": "check.py/verify-step-v1",
            "step_id": step_id,
            "v_id": v_id,
            "result": payload["result"],
            "command": command,
            "exit_code": payload["exit_code"],
            "timed_out": payload["timed_out"],
            "started_at": payload["started_at"],
            "finished_at": payload["finished_at"],
            "elapsed_seconds": payload["elapsed_seconds"],
            "evidence_path": recorded_evidence_path,
            "output_hash": output_hash,
            "contract_hash": plan["contract_hash"],
            "plan_structure_hash": plan["plan_structure_hash"],
            "step_hash": step_digest,
        }
        append_immutable_event(ledger_path, event)
        return event


def validate_workflow_event(state, event):
    event_problems = []
    require(event, ("id", "to_status", "to_phase"), "event", event_problems)
    if event_problems:
        raise ValidationError("; ".join(event_problems))
    validate_transition(state["status"], event["to_status"], WORKFLOW_TRANSITIONS, "workflow")
    if event["to_phase"] not in PHASES:
        raise ValidationError(f"invalid phase: {event['to_phase']}")
    if event["to_phase"] not in STATUS_PHASES[event["to_status"]]:
        raise ValidationError(f"invalid status/phase pair: {event['to_status']}/{event['to_phase']}")
    control_flags = {"scope_change", "irreversible", "spend", "privacy_exposure", "value_tradeoff"}
    if any(event.get(flag) for flag in control_flags) and not event.get("owner_event"):
        raise ValidationError("mandatory owner checkpoint is missing")
    budget_kind = event.get("budget_kind")
    if budget_kind:
        if budget_kind not in {"audit", "research", "prototype"}:
            raise ValidationError(f"invalid budget kind: {budget_kind}")
        if state.get("usage", {}).get(budget_kind, 0) >= state.get("budgets", {}).get(budget_kind, 0):
            raise ValidationError(f"{budget_kind} budget exhausted; suspend or request owner control")


def validate_release_transition(event, events):
    if event.get("to_status") not in {"passed", "conditional"}:
        return
    problems = []
    require(event, ("contract_hash", "final_audit_event"), "release transition", problems)
    if problems:
        raise ValidationError("; ".join(problems))
    release_index = next(
        (index for index, item in enumerate(events) if item.get("id") == event.get("id")),
        len(events),
    )
    def prior_event(event_id):
        return next(
            (item for index, item in enumerate(events)
             if index < release_index and item.get("id") == event_id),
            None,
        )

    audit = prior_event(event["final_audit_event"])
    if (not audit or audit.get("type") != "final-audit" or audit.get("result") != "passed"
            or audit.get("contract_hash") != event.get("contract_hash")):
        raise ValidationError("release transition requires a passed final-audit event for the contract hash")
    if event.get("to_status") == "conditional":
        require(event, ("owner_event", "residual_risk_ids", "additional_verification_ids",
                        "additional_verification_events"),
                "conditional release", problems)
        if problems:
            raise ValidationError("; ".join(problems))
        if (not isinstance(event.get("residual_risk_ids"), list) or not event["residual_risk_ids"]
                or not all(isinstance(item, str) and item.startswith("R-") for item in event["residual_risk_ids"])):
            raise ValidationError("conditional release needs residual R IDs")
        if (not isinstance(event.get("additional_verification_ids"), list)
                or not event["additional_verification_ids"]
                or not all(isinstance(item, str) and item.startswith("V-") for item in event["additional_verification_ids"])):
            raise ValidationError("conditional release needs additional V IDs")
        verification_events = event.get("additional_verification_events")
        if not isinstance(verification_events, list) or not verification_events:
            raise ValidationError("conditional release needs executed verification events")
        verified = set()
        for event_id in verification_events:
            verification = prior_event(event_id)
            if (not verification or verification.get("type") != "release-verification"
                    or verification.get("result") != "passed"
                    or verification.get("contract_hash") != event.get("contract_hash")):
                raise ValidationError("conditional release has an invalid verification event")
            verified.add(verification.get("v_id"))
        if set(event["additional_verification_ids"]) != verified:
            raise ValidationError("conditional release V IDs do not match executed verification events")
        owner = prior_event(event["owner_event"])
        if (not owner or owner.get("type") != "owner-decision"
                or owner.get("decision") != "conditional-release"
                or owner.get("result") != "accepted"
                or owner.get("contract_hash") != event.get("contract_hash")):
            raise ValidationError("conditional release requires a bound owner-decision event")


def project_workflow_event(state, event):
    validate_workflow_event(state, event)
    budget_kind = event.get("budget_kind")
    state.update({
        "revision": state["revision"] + 1,
        "status": event["to_status"],
        "phase": event["to_phase"],
        "applied_event_ids": state.get("applied_event_ids", []) + [event["id"]],
    })
    if budget_kind:
        state["usage"][budget_kind] += 1
    if event.get("to_status") in {"passed", "conditional"}:
        state["released_contract_hash"] = event.get("contract_hash")
        state["release_event_id"] = event.get("id")


def write_json_projection(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def update_frontmatter(path, values):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValidationError(f"missing frontmatter: {path}")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValidationError(f"unterminated frontmatter: {path}") from exc
    remaining = dict(values)
    for index in range(1, end):
        if ":" not in lines[index]:
            continue
        key = lines[index].split(":", 1)[0].strip()
        if key in remaining:
            lines[index] = f"{key}: {remaining.pop(key)}"
    for key, value in remaining.items():
        lines.insert(end, f"{key}: {value}")
        end += 1
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    os.replace(temp, path)


def release_contract(contract_path, state_path, ledger_path, event_path, expected_revision):
    meta, contract = read_artifact(contract_path, "contract")
    problems = contract_problems(contract_path, contract)
    if problems:
        raise ValidationError("contract is invalid:\n- " + "\n- ".join(problems))
    submitted = json.loads(Path(event_path).read_text(encoding="utf-8"))
    if submitted.get("to_status") not in {"passed", "conditional"}:
        raise ValidationError("release requires a passed or conditional workflow event")
    expected = contract_hash(contract)
    if submitted.get("contract_hash") != expected:
        raise ValidationError("release event contract_hash mismatch")
    state = append_event(state_path, ledger_path, event_path, expected_revision)
    update_frontmatter(contract_path, {
        "status": state["status"], "phase": state["phase"], "contract-hash": expected,
    })
    read_checked_contract(contract_path, require_released=True, ledger_path=ledger_path)
    return state


def reconcile_workflow(state, events):
    applied = set(state.get("applied_event_ids", []))
    events = [event for event in events if event.get("type") == "workflow-transition"]
    while True:
        candidates = [event for event in events if event.get("id") not in applied and event.get("from_revision") == state["revision"]]
        if len(candidates) > 1:
            raise ValidationError(f"workflow ledger fork at revision {state['revision']}")
        if not candidates:
            break
        project_workflow_event(state, candidates[0])
        applied.add(candidates[0]["id"])
    stale = [event for event in events if event.get("id") not in applied and event.get("from_revision", -1) < state["revision"]]
    if stale:
        raise ValidationError("workflow ledger contains an unapplied stale event")
    return state


def validate_contract_release(meta, contract, state_path, ledger_path):
    problems = []
    events = load_ledger(ledger_path)
    control = contract.get("control", {})
    projected = {
        "revision": 0,
        "status": "draft",
        "phase": "intake",
        "profile": contract.get("profile"),
        "interaction": control.get("interaction"),
        "budgets": {
            "audit": control.get("audit_budget"),
            "research": control.get("research_budget"),
            "prototype": control.get("prototype_budget"),
        },
        "usage": {"audit": 0, "research": 0, "prototype": 0},
        "applied_event_ids": [],
    }
    reconcile_workflow(projected, events)
    stored = json.loads(Path(state_path).read_text(encoding="utf-8"))
    for field in ("revision", "status", "phase", "applied_event_ids",
                  "released_contract_hash", "release_event_id"):
        if stored.get(field) != projected.get(field):
            problems.append(f"workflow state {field} does not match the replayed ledger")
    expected = contract_hash(contract)
    if projected.get("status") != meta.get("status") or projected.get("phase") != "idle":
        problems.append("workflow state does not prove the released contract status")
    if projected.get("released_contract_hash") != expected:
        problems.append("workflow release hash does not match the contract")
    release = next((item for item in events if item.get("id") == projected.get("release_event_id")), None)
    if not release:
        problems.append("workflow release event is missing")
    else:
        try:
            validate_release_transition(release, events)
        except ValidationError as exc:
            problems.append(str(exc))
        if release.get("to_status") != meta.get("status"):
            problems.append("workflow release event status does not match the contract")
        if meta.get("status") == "conditional":
            known_r = {node.get("id") for node in contract.get("nodes", {}).get("R", []) if node.get("status") == "active"}
            known_v = {node.get("id") for node in contract.get("nodes", {}).get("V", []) if node.get("status") == "active"}
            if not set(release.get("residual_risk_ids", [])).issubset(known_r):
                problems.append("conditional release references unknown active residual risks")
            if not set(release.get("additional_verification_ids", [])).issubset(known_v):
                problems.append("conditional release references unknown active verifications")
    return problems


def append_event(state_path, ledger_path, event_path, expected_revision):
    state_path, ledger_path = Path(state_path), Path(ledger_path)
    submitted = json.loads(Path(event_path).read_text(encoding="utf-8"))
    submitted["type"] = "workflow-transition"
    with file_lock(ledger_path):
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {
            "revision": 0, "status": "draft", "phase": "idle", "applied_event_ids": [],
        }
        events = load_ledger(ledger_path)
        recorded = next((event for event in events if event.get("id") == submitted.get("id")), None)
        if recorded and event_payload(recorded) != event_payload(submitted):
            raise ValidationError(f"event ID payload conflict: {submitted.get('id')}")
        before = state["revision"]
        reconcile_workflow(state, events)
        if state["revision"] != before:
            write_json_projection(state_path, state)
        if submitted.get("id") in state.get("applied_event_ids", []):
            return state
        if state["revision"] != expected_revision:
            raise ValidationError(f"revision conflict: expected {expected_revision}, actual {state['revision']}")
        validate_workflow_event(state, submitted)
        validate_release_transition(submitted, events)
        event = dict(submitted, from_revision=state["revision"], from_status=state["status"])
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        project_workflow_event(state, event)
        write_json_projection(state_path, state)
        return state


def render_change_orders(data):
    return (
        "# Change Orders\n\n```json change-orders\n"
        + json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n```\n"
    )


def find_ledger_event(events, ident, event_type=None, cr_id=None):
    event = next((item for item in events if item.get("id") == ident), None)
    if not event or (event_type and event.get("type") != event_type) or (cr_id and event.get("cr_id") != cr_id):
        raise ValidationError(f"missing or mismatched ledger evidence event: {ident}")
    return event


def project_cr_event(data, event, events, capability, contract=None):
    event_problems = []
    require(event, ("id", "cr_id", "to_status"), "CR event", event_problems)
    if event_problems:
        raise ValidationError("; ".join(event_problems))
    order = next((item for item in data.get("orders", []) if item.get("id") == event["cr_id"]), None)
    if order is None:
        raise ValidationError(f"unknown CR: {event['cr_id']}")
    applied = order.setdefault("applied_event_ids", [])
    if event["id"] in applied:
        return data
    current = order["status"]
    validate_transition(current, event["to_status"], CR_TRANSITIONS, "CR")
    if current in {"approved", "applying", "verifying"} and capability != "cr-recovery":
        raise ValidationError("CR repair transitions require capability=cr-recovery")
    if current == "reviewing" and event["to_status"] == "waived-pending-verification":
        if not order.get("waiver_eligible") or not event.get("waiver_t") or not event.get("added_v"):
            raise ValidationError("waiver requires eligibility, owner T, and additional V")
        decision = find_ledger_event(events, event["waiver_t"], "owner-decision", event["cr_id"])
        if contract is None:
            raise ValidationError("waiver transition requires the target contract")
        active_v = {node["id"] for node in contract["nodes"]["V"] if node.get("status") == "active"}
        if (contract_hash(contract) != order.get("contract_after")
                or decision.get("result") != "applied"
                or decision.get("disposition") != "waive"
                or decision.get("added_v") != event.get("added_v")
                or decision.get("contract_hash") != order.get("contract_after")
                or not set(event.get("added_v", [])).issubset(active_v)):
            raise ValidationError("waiver owner decision is not bound to this disposition, V set, and contract")
        order["waiver_t"] = event["waiver_t"]
        order["added_v"] = event["added_v"]
    elif event.get("added_v"):
        order["added_v"] = event["added_v"]
    if current in {"verifying", "waived-pending-verification"} and not event.get("verification_evidence"):
        raise ValidationError("verification transition requires execution evidence")
    for evidence in event.get("verification_evidence", []):
        verification = find_ledger_event(events, evidence, "verification", event["cr_id"])
        if order.get("added_v") and verification.get("v_id") not in order["added_v"]:
            raise ValidationError("verification evidence is not one of the CR additional V")
    if event["to_status"] == "closed":
        audit = event.get("final_audit_event")
        audit_event = find_ledger_event(events, audit, "final-audit", event["cr_id"])
        if audit_event.get("result") != "passed" or audit_event.get("contract_hash") != order.get("contract_after"):
            raise ValidationError("final audit must pass for the CR contract_after hash")
        order["final_audit_event"] = audit
    order["status"] = event["to_status"]
    order["applied_event_ids"] = applied + [event["id"]]
    if event.get("verification_evidence"):
        order["verification_evidence"] = event["verification_evidence"]
    data["revision"] += 1
    return data


def apply_cr_event(change_path, ledger_path, event_path, expected_revision, capability=None, contract=None):
    change_path, ledger_path = Path(change_path), Path(ledger_path)
    submitted = json.loads(Path(event_path).read_text(encoding="utf-8"))
    submitted["type"] = "cr-transition"
    with file_lock(ledger_path):
        _, data = read_artifact(change_path, "change-orders")
        events = load_ledger(ledger_path)
        applied_ids = {
            event_id for order in data.get("orders", [])
            for event_id in order.get("applied_event_ids", [])
        }
        pending_transitions = [event for event in events
                               if event.get("type") == "cr-transition"
                               and event.get("id") not in applied_ids]
        stale = [event for event in pending_transitions if event.get("from_revision", -1) < data["revision"]]
        if stale:
            raise ValidationError("CR ledger contains an unapplied stale event")
        candidates = [event for event in pending_transitions if event.get("from_revision") == data["revision"]]
        if len(candidates) > 1:
            raise ValidationError(f"CR ledger fork at revision {data['revision']}")
        recorded = next((event for event in events if event.get("id") == submitted.get("id")), None)
        if recorded and event_payload(recorded) != event_payload(submitted):
            raise ValidationError(f"CR event ID payload conflict: {submitted.get('id')}")
        if recorded:
            authorized = recorded.get("authorized_capability")
            if recorded.get("id") in applied_ids:
                return data
            if data["revision"] != recorded.get("from_revision"):
                raise ValidationError("recorded CR event cannot be replayed on the current projection")
            project_cr_event(data, recorded, events, authorized, contract)
            problems = validate_change_orders(data) + validate_cr_provenance(data, events)
            if problems:
                raise ValidationError("invalid replayed CR projection: " + "; ".join(problems))
            temp = change_path.with_suffix(change_path.suffix + ".tmp")
            temp.write_text(render_change_orders(data), encoding="utf-8", newline="\n")
            os.replace(temp, change_path)
            return data
        orphan = candidates[0] if candidates else None
        if orphan:
            raise ValidationError(f"unprojected CR event must be replayed first: {orphan.get('id')}")
        if data["revision"] != expected_revision:
            raise ValidationError(f"revision conflict: expected {expected_revision}, actual {data['revision']}")
        target_order = next((order for order in data.get("orders", []) if order.get("id") == submitted.get("cr_id")), None)
        if target_order is None:
            raise ValidationError(f"unknown CR: {submitted.get('cr_id')}")
        event = dict(
            submitted,
            from_revision=data["revision"],
            from_status=target_order["status"],
            authorized_capability=capability,
        )
        # Evidence events must already exist; the transition event itself is added after validation.
        project_cr_event(data, event, events, capability, contract)
        problems = validate_change_orders(data) + validate_cr_provenance(data, events + [event])
        if problems:
            raise ValidationError("invalid CR projection: " + "; ".join(problems))
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        temp = change_path.with_suffix(change_path.suffix + ".tmp")
        temp.write_text(render_change_orders(data), encoding="utf-8", newline="\n")
        os.replace(temp, change_path)
        return data


def confirm_plan(plan_path, selection_path, contract_path, ledger_path):
    with file_lock(str(plan_path) + ".confirmation"):
        return confirm_plan_locked(plan_path, selection_path, contract_path, ledger_path)


def confirm_plan_locked(plan_path, selection_path, contract_path, ledger_path):
    meta, plan = read_artifact(plan_path, "plan")
    _, contract = read_checked_contract(contract_path, require_released=True, ledger_path=ledger_path)
    existing_events = load_ledger(ledger_path)
    problems = plan_artifact_problems(meta, plan, contract, existing_events)
    if problems:
        raise ValidationError("PLAN is invalid:\n- " + "\n- ".join(problems))
    runtime = plan.get("runtime", {})
    if runtime.get("status") not in {"planning", "building"}:
        raise ValidationError("only a planning or already-building PLAN can be confirmed")

    selection = json.loads(Path(selection_path).read_text(encoding="utf-8"))
    if not isinstance(selection, dict):
        raise ValidationError("PLAN selection must be an object")
    event_base = selection.get("id")
    authorization = selection.get("authorization")
    owner_event_id = selection.get("owner_event")
    selections = selection.get("selections")
    if not isinstance(event_base, str) or not re.fullmatch(r"[A-Za-z0-9._:-]+", event_base):
        raise ValidationError("PLAN selection id must use letters, digits, '.', '_', ':', or '-'")
    if authorization != "owner-confirmed" or not isinstance(owner_event_id, str) or not owner_event_id.strip():
        raise ValidationError("PLAN selection requires authorization=owner-confirmed and owner_event")
    if not isinstance(selections, dict):
        raise ValidationError("PLAN selection.selections must be an object")

    active_units = {
        unit["id"] for unit in contract.get("nodes", {}).get("I", [])
        if isinstance(unit, dict) and unit.get("status") == "active"
    }
    if set(selections) != active_units:
        raise ValidationError("PLAN selection must choose exactly one variant for every active unit")
    events = []
    selected_variants, selection_events = {}, {}
    for unit in sorted(active_units):
        choice = selections.get(unit)
        if not isinstance(choice, dict):
            raise ValidationError(f"PLAN selection for {unit} must be an object")
        variant = choice.get("variant")
        selector_evidence = choice.get("selector_evidence")
        if not isinstance(variant, str) or not isinstance(selector_evidence, str):
            raise ValidationError(f"PLAN selection for {unit} needs variant and selector_evidence")
        event_id = f"{event_base}:{unit}"
        events.append({
            "id": event_id,
            "type": "variant-selection",
            "unit": unit,
            "variant": variant,
            "selector_evidence": selector_evidence,
            "authorization": authorization,
            "owner_event": owner_event_id,
            "contract_hash": plan.get("contract_hash"),
            "plan_structure_hash": plan.get("plan_structure_hash"),
        })
        selected_variants[unit] = variant
        selection_events[unit] = event_id

    prior_selections = [
        item for item in existing_events
        if item.get("type") == "variant-selection"
        and item.get("contract_hash") == plan.get("contract_hash")
        and item.get("plan_structure_hash") == plan.get("plan_structure_hash")
    ]
    if runtime.get("status") == "planning" and prior_selections:
        prior_by_id = {item.get("id"): item for item in prior_selections}
        if (set(prior_by_id) != {item["id"] for item in events}
                or any(event_payload(prior_by_id[item["id"]]) != event_payload(item) for item in events)):
            raise ValidationError("a different PLAN confirmation is already durable in the ledger")

    if runtime.get("status") == "building":
        recorded_index = {item.get("id"): item for item in existing_events}
        if (runtime.get("selected_variants") == selected_variants
                and runtime.get("selection_events") == selection_events
                and all(recorded_index.get(item["id"])
                        and event_payload(recorded_index[item["id"]]) == event_payload(item)
                        for item in events)):
            return plan
        raise ValidationError("PLAN is already confirmed; change requires a CR and recompile")

    updated = json.loads(json.dumps(plan))
    updated_runtime = updated["runtime"]
    updated_runtime["status"] = "building"
    updated_runtime.setdefault("revision", 0)
    updated_runtime.setdefault("applied_event_ids", [])
    updated_runtime["selected_variants"] = selected_variants
    updated_runtime["selection_events"] = selection_events
    for step in updated.get("steps", []):
        step_id = step.get("id")
        if step_id in updated_runtime.get("step_states", {}):
            selected = selected_variants.get(step.get("unit")) == step.get("variant")
            if updated_runtime["step_states"][step_id] == "dormant":
                updated_runtime["step_states"][step_id] = "pending" if selected else "dormant"

    event_index = {event.get("id"): event for event in existing_events}
    for event in events:
        recorded = event_index.get(event["id"])
        if recorded and event_payload(recorded) != event_payload(event):
            raise ValidationError(f"ledger event ID payload conflict: {event['id']}")
    combined_events = existing_events + [event for event in events if event["id"] not in event_index]
    problems = validate_plan(updated, contract, combined_events)
    if problems:
        raise ValidationError("PLAN confirmation is invalid:\n- " + "\n- ".join(problems))

    ledger_path = Path(ledger_path)
    with file_lock(ledger_path):
        recorded_events = load_ledger(ledger_path)
        recorded_index = {event.get("id"): event for event in recorded_events}
        for event in events:
            recorded = recorded_index.get(event["id"])
            if recorded and event_payload(recorded) != event_payload(event):
                raise ValidationError(f"ledger event ID payload conflict: {event['id']}")
        missing = [event for event in events if event["id"] not in recorded_index]
        if missing:
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with ledger_path.open("a", encoding="utf-8", newline="\n") as stream:
                for event in missing:
                    stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        target = Path(plan_path)
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(render_plan(updated, meta.get("project", "project")), encoding="utf-8", newline="\n")
        os.replace(temp, target)
    return updated


def apply_plan_event(plan_path, event_path, contract_path, ledger_path, allow_done=False):
    with file_lock(str(plan_path) + ".runtime"):
        return apply_plan_event_locked(plan_path, event_path, contract_path, ledger_path, allow_done)


def apply_plan_event_locked(plan_path, event_path, contract_path, ledger_path, allow_done=False):
    meta, plan = read_artifact(plan_path, "plan")
    _, contract = read_checked_contract(contract_path, require_released=True, ledger_path=ledger_path)
    events = load_ledger(ledger_path)
    replay_problems = []
    recovered = replay_plan_runtime(plan, events, replay_problems)
    hard_replay_problems = [item for item in replay_problems if "does not match ledger replay" not in item]
    if hard_replay_problems:
        raise ValidationError("PLAN runtime ledger is invalid:\n- " + "\n- ".join(hard_replay_problems))
    if recovered:
        for field, value in recovered.items():
            plan["runtime"][field] = value
        meta["status"] = plan["runtime"]["status"]
    problems = plan_artifact_problems(meta, plan, contract, events)
    if problems:
        raise ValidationError("PLAN is invalid:\n- " + "\n- ".join(problems))
    submitted = json.loads(Path(event_path).read_text(encoding="utf-8"))
    if not isinstance(submitted, dict):
        raise ValidationError("PLAN runtime event must be an object")
    require(submitted, ("id", "type", "expected_revision", "contract_hash", "plan_structure_hash"),
            "PLAN runtime event", problems := [])
    if problems:
        raise ValidationError("; ".join(problems))
    if submitted["type"] not in {"step-transition", "plan-transition"}:
        raise ValidationError("PLAN runtime event type must be step-transition or plan-transition")
    if (submitted.get("contract_hash") != plan.get("contract_hash")
            or submitted.get("plan_structure_hash") != plan.get("plan_structure_hash")):
        raise ValidationError("PLAN runtime event belongs to another contract or PLAN")

    runtime = plan["runtime"]
    applied = runtime.setdefault("applied_event_ids", [])
    if submitted["id"] in applied:
        recorded = next((event for event in events if event.get("id") == submitted["id"]), None)
        if not recorded or any(recorded.get(key) != value for key, value in submitted.items()):
            raise ValidationError(f"PLAN runtime event ID payload conflict: {submitted['id']}")
        target = Path(plan_path)
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(render_plan(plan, meta.get("project", "project")), encoding="utf-8", newline="\n")
        os.replace(temp, target)
        return plan
    revision = runtime.get("revision", 0)
    if submitted.get("expected_revision") != revision:
        raise ValidationError(
            f"PLAN revision conflict: expected {submitted.get('expected_revision')}, actual {revision}"
        )
    event = dict(submitted, from_plan_revision=revision)

    updated = json.loads(json.dumps(plan))
    updated_runtime = updated["runtime"]
    if submitted["type"] == "plan-transition":
        require(submitted, ("to_status",), "PLAN transition", problems := [])
        if problems:
            raise ValidationError("; ".join(problems))
        current = runtime.get("status")
        target = submitted.get("to_status")
        if target == "done" and not allow_done:
            raise ValidationError("done requires the finish-plan command")
        if target not in PLAN_RUNTIME_TRANSITIONS.get(current, set()):
            raise ValidationError(f"illegal PLAN transition: {current} -> {target}")
        updated_runtime["status"] = target
    else:
        require(submitted, ("step_id", "to_state"), "step transition", problems := [])
        if problems:
            raise ValidationError("; ".join(problems))
        step_id = submitted.get("step_id")
        step = next((item for item in updated.get("steps", []) if item.get("id") == step_id), None)
        if not step:
            raise ValidationError(f"unknown PLAN step: {step_id}")
        if submitted.get("step_hash") != step_hash(step):
            raise ValidationError("step transition has a stale or missing step_hash")
        if updated_runtime.get("status") != "building":
            raise ValidationError("step transitions require PLAN runtime.status=building")
        if updated_runtime.get("selected_variants", {}).get(step.get("unit")) != step.get("variant"):
            raise ValidationError("cannot transition an unselected variant step")
        current = updated_runtime.get("step_states", {}).get(step_id)
        target = submitted.get("to_state")
        if target not in STEP_RUNTIME_TRANSITIONS.get(current, set()):
            raise ValidationError(f"illegal step transition: {current} -> {target}")
        updated_runtime["step_states"][step_id] = target
        if target == "complete":
            attempt_id = submitted.get("attempt_id")
            if not isinstance(attempt_id, str) or not attempt_id.strip():
                raise ValidationError("complete step transition requires attempt_id")
            if any(attempt_id in ids for ids in updated_runtime.get("attempts", {}).values() if isinstance(ids, list)):
                raise ValidationError("complete step transition requires a fresh attempt_id")
            updated_runtime.setdefault("attempts", {}).setdefault(step_id, []).append(attempt_id)

    updated_runtime.setdefault("applied_event_ids", []).append(event["id"])
    updated_runtime["revision"] = revision + 1
    combined = events + [event]
    problems = validate_plan(updated, contract, combined)
    if problems:
        raise ValidationError("PLAN runtime transition is invalid:\n- " + "\n- ".join(problems))

    ledger_path = Path(ledger_path)
    with file_lock(ledger_path):
        recorded_events = load_ledger(ledger_path)
        recorded = next((item for item in recorded_events if item.get("id") == event["id"]), None)
        if recorded and event_payload(recorded) != event_payload(event):
            raise ValidationError(f"PLAN runtime event ID payload conflict: {submitted['id']}")
        if not recorded:
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with ledger_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        target = Path(plan_path)
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(render_plan(updated, meta.get("project", "project")), encoding="utf-8", newline="\n")
        os.replace(temp, target)
    return updated


def done_reconcile_problems(plan, contract, events, orders):
    problems = []
    matrix = reconcile_closure(contract, plan, events, orders)
    if matrix.get("status") != "clean":
        problems.append("done PLAN requires a clean reconcile result")
    applied = plan.get("runtime", {}).get("applied_event_ids", [])
    done_event = next(
        (event for event in events
         if event.get("id") in applied and event.get("type") == "plan-transition"
         and event.get("to_status") == "done"),
        None,
    )
    if not done_event or done_event.get("reconcile_hash") != reconcile_result_hash(matrix):
        problems.append("done PLAN reconcile proof is missing or stale")
    return problems


def enforce_assurance_policy(plan_path, contract):
    """Run the package assurance floor when the slice opts in.

    `assurance-policy.json` (`assurance-policy/1`, `"strict": true`) in the
    slice package turns the mechanical Audited facts (phase 0 disposition,
    bound test manifest, resolved dispatch state) into a finish-plan gate.
    Legacy packages without the file keep their existing behavior."""

    package_dir = Path(plan_path).resolve().parent
    if _assurance_policy is None:
        if (package_dir / "assurance-policy.json").exists():
            raise ValidationError(
                "assurance_policy.py is not available next to check.py; cannot enforce the "
                "package assurance policy: " + str(_ASSURANCE_POLICY_IMPORT_ERROR)
            )
        return
    try:
        policy = _assurance_policy.load_policy(package_dir)
    except _assurance_policy.AssuranceError as exc:
        raise ValidationError(str(exc)) from exc
    if policy is None or not policy.get("strict"):
        return
    require = policy.get("require") or ["phase0", "test-manifest", "dispatch"]
    if not isinstance(require, list) or any(not isinstance(item, str) for item in require):
        raise ValidationError("assurance-policy.json require must be a string list")
    problems = _assurance_policy.package_problems(package_dir, require=tuple(require))
    if problems:
        raise ValidationError("assurance policy failed:\n- " + "\n- ".join(problems))


def finish_plan(plan_path, event_path, contract_path, change_path, ledger_path):
    with file_lock(str(plan_path) + ".runtime"):
        submitted = json.loads(Path(event_path).read_text(encoding="utf-8"))
        if not isinstance(submitted, dict):
            raise ValidationError("Finish event must be an object")
        if submitted.get("type") != "plan-transition" or submitted.get("to_status") != "done":
            raise ValidationError("Finish event must be a plan-transition to done")
        meta, plan = read_artifact(plan_path, "plan")
        _, contract = read_checked_contract(contract_path, require_released=True, ledger_path=ledger_path)
        _, orders = read_artifact(change_path, "change-orders")
        events = load_ledger(ledger_path)
        replay_problems = []
        recovered = replay_plan_runtime(plan, events, replay_problems)
        hard_replay_problems = [item for item in replay_problems if "does not match ledger replay" not in item]
        if hard_replay_problems:
            raise ValidationError("PLAN runtime ledger is invalid:\n- " + "\n- ".join(hard_replay_problems))
        if recovered:
            for field, value in recovered.items():
                plan["runtime"][field] = value
            meta["status"] = plan["runtime"]["status"]
        if plan.get("runtime", {}).get("status") == "done":
            recorded = next((item for item in events if item.get("id") == submitted.get("id")), None)
            if not recorded or any(recorded.get(key) != value for key, value in submitted.items()):
                raise ValidationError("Finish event ID payload conflict")
            problems = plan_artifact_problems(meta, plan, contract, events)
            problems += done_reconcile_problems(plan, contract, events, orders)
            if problems:
                raise ValidationError("Finished PLAN is invalid:\n- " + "\n- ".join(problems))
            target = Path(plan_path)
            temp = target.with_suffix(target.suffix + ".tmp")
            temp.write_text(render_plan(plan, meta.get("project", "project")), encoding="utf-8", newline="\n")
            os.replace(temp, target)
            return plan
        problems = plan_artifact_problems(meta, plan, contract, events, require_building=True)
        problems += validate_change_orders(orders)
        problems += validate_cr_provenance(orders, events)
        if problems:
            raise ValidationError("Finish gate is invalid:\n- " + "\n- ".join(problems))
        enforce_assurance_policy(plan_path, contract)
        matrix = reconcile_closure(contract, plan, events, orders)
        if matrix.get("status") != "clean":
            raise ValidationError("Finish requires reconcile status=clean")
        matrix_hash = reconcile_result_hash(matrix)
        audit = next((item for item in events if item.get("id") == submitted.get("converge_audit_event")), None)
        event_positions = {item.get("id"): index for index, item in enumerate(events)}
        last_runtime_position = max(
            (event_positions.get(item, -1) for item in plan["runtime"].get("applied_event_ids", [])),
            default=-1,
        )
        if (not audit or audit.get("type") != "converge-audit" or audit.get("result") != "passed"
                or audit.get("contract_hash") != plan.get("contract_hash")
                or audit.get("plan_structure_hash") != plan.get("plan_structure_hash")
                or audit.get("reconcile_hash") != matrix_hash
                or audit.get("plan_revision") != plan["runtime"].get("revision", 0)
                or event_positions.get(audit.get("id"), -1) <= last_runtime_position):
            raise ValidationError("Finish requires a passed converge-audit event for this PLAN")
        submitted["reconcile_hash"] = matrix_hash
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as stream:
            json.dump(submitted, stream, ensure_ascii=False, sort_keys=True)
            generated_path = stream.name
        try:
            return apply_plan_event_locked(
                plan_path, generated_path, contract_path, ledger_path, allow_done=True,
            )
        finally:
            try:
                Path(generated_path).unlink()
            except FileNotFoundError:
                pass


def render_plan(plan, project="fixture"):
    return (
        "---\n"
        f"project: {project}\n"
        f"contract-hash: {plan['contract_hash']}\n"
        f"plan-structure-hash: {plan['plan_structure_hash']}\n"
        f"status: {plan['runtime']['status']}\n"
        "---\n\n# Construction Plan\n\n```json plan\n"
        + json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n```\n"
    )


def report(label, problems):
    print(f"[{label}]")
    if problems:
        for problem in problems:
            print(f"  X {problem}")
        return 1
    print("  OK")
    return 0


def selftest():
    failures = 0
    _, goal_fixture = read_artifact(FIXTURES / "goal-valid.md", "goal")
    failures += report("valid goal schema", validate_goal(goal_fixture))
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        goal_path = root / ".opencode" / "mvp" / "goal.md"
        goal_path.parent.mkdir(parents=True)
        for field_path in (
                ("status",), ("rigor",), ("risk", "factors"), ("outcomes",),
                ("outcomes", 0, "status"), ("outcomes", 0, "evidence"),
                ("outcomes", 0, "verification"),
                ("outcomes", 0, "verification", "assertion_kind"),
                ("outcomes", 0, "verification", "assertion")):
            for bad_value in (None, [], {}, True, 7):
                malformed = json.loads(json.dumps(goal_fixture))
                target = malformed
                for key in field_path[:-1]:
                    target = target[key]
                target[field_path[-1]] = bad_value
                if field_path[-1] == "evidence":
                    malformed["outcomes"][0]["status"] = "verified"
                goal_path.write_text(render_goal(malformed), encoding="utf-8")
                failures += report("goal malformed " + str(field_path) + repr(bad_value),
                                   [] if validate_goal_artifact(goal_path)[2] else ["accepted"])
        for name, code, assertion, passed in (
                ("literal", "print('Hello user')", {"type": "stdout-contains", "literal": "Hello user"}, True),
                ("empty", "pass", {"type": "stdout-contains", "literal": "Hello user"}, False),
                ("wrong", "print('wrong')", {"type": "stdout-contains", "literal": "Hello user"}, False),
                ("exit", "print('Hello user'); raise SystemExit(1)", {"type": "stdout-contains", "literal": "Hello user"}, False),
                ("timeout", "import time; time.sleep(2)", {"type": "stdout-contains", "literal": "Hello user"}, False),
                ("json", "print('{\\\"ok\\\":true}')", {"type": "json-equals", "expected": {"ok": True}}, True),
                ("json-wrong", "print('false')", {"type": "json-equals", "expected": True}, False),
                ("json-invalid", "print('not JSON')", {"type": "json-equals", "expected": None}, False)):
            goal = json.loads(json.dumps(goal_fixture))
            verification = goal["outcomes"][0]["verification"]
            verification.update(command=f'"{sys.executable}" -c "{code}"', assertion=assertion, timeout_seconds=1)
            goal_path.write_text(render_goal(goal), encoding="utf-8")
            evidence_path = root / ".opencode" / "mvp" / "evidence" / (name + ".json")
            updated, payload = verify_goal_outcome(goal_path, "O-01", evidence_path)
            failures += report("goal runner " + name, [] if
                               (payload["result"] == "passed") == passed and
                               (updated["outcomes"][0]["status"] == "verified") == passed
                               else ["incorrect result"])
            try:
                finish_goal(goal_path)
                finished = True
            except ValidationError:
                finished = False
            failures += report("goal finish " + name, [] if finished == passed else ["incorrect gate"])
            if not passed:
                continue
            baseline = goal_path.read_text(encoding="utf-8")
            changed = json.loads(json.dumps(updated))
            changed["demo"] = "changed definition"
            goal_path.write_text(render_goal(changed), encoding="utf-8")
            failures += report("goal stale definition", [] if validate_goal_artifact(goal_path)[2] else ["accepted"])
            changed = json.loads(json.dumps(updated))
            changed["outcomes"][0]["user_entry"] = False
            # Reject a missing entry before executing any verification command.
            changed["outcomes"][0]["status"] = "pending"
            changed["outcomes"][0].pop("evidence")
            goal_path.write_text(render_goal(changed), encoding="utf-8")
            internal_evidence = evidence_path.with_name(name + "-internal.json")
            try:
                verify_goal_outcome(goal_path, "O-01", internal_evidence)
                failures += report("goal user-entry preflight", ["executed internal-only goal"])
            except ValidationError:
                failures += report("goal user-entry preflight", [] if not internal_evidence.exists()
                                   else ["wrote evidence for an invalid goal"])
            try:
                finish_goal(goal_path)
                failures += report("goal user-entry gate", ["accepted internal-only outcomes"])
            except ValidationError:
                print("[goal user-entry gate] OK")
            goal_path.write_text(baseline, encoding="utf-8")
            for field, value in (("timed_out", True), ("exit_code", False), ("result", "failed")):
                forged_payload = dict(payload)
                forged_payload[field] = value
                evidence_path.write_text(json.dumps(forged_payload), encoding="utf-8")
                _, altered = read_artifact(goal_path, "goal")
                altered["outcomes"][0]["evidence"]["sha256"] = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
                goal_path.write_text(render_goal(altered), encoding="utf-8")
                failures += report("goal evidence " + field, [] if validate_goal_artifact(goal_path)[2] else ["accepted"])
            for bad_payload in ([], None, True):
                evidence_path.write_text(json.dumps(bad_payload), encoding="utf-8")
                failures += report("goal malformed evidence payload", [] if validate_goal_artifact(goal_path)[2] else ["accepted"])
            goal_path.write_text(baseline, encoding="utf-8")
            payload["stdout"] = "tampered"
            evidence_path.write_text(json.dumps(payload), encoding="utf-8")
            failures += report("goal output hash tamper", [] if validate_goal_artifact(goal_path)[2] else ["accepted"])
            _, altered = read_artifact(goal_path, "goal")
            altered["outcomes"][0]["evidence"]["sha256"] = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            goal_path.write_text(render_goal(altered), encoding="utf-8")
            failures += report("goal assertion revalidation", [] if validate_goal_artifact(goal_path)[2] else ["accepted"])
    for output, expected in (("true", 1), ('{"x":1,"x":2}', {"x": 2}), ("NaN", None)):
        failures += report("JSON assertion strictness", [] if not evaluate_assertion(
            output, {"type": "json-equals", "expected": expected}) else ["accepted"])
    brief_meta, brief, expected_brief_hash, brief_problems = validate_brief_artifact(
        FIXTURES / "brief-valid.md"
    )
    if brief_meta.get("brief-hash") != expected_brief_hash:
        brief_problems.append("valid brief fixture frontmatter hash mismatch")
    failures += report("valid brief", brief_problems)
    draft = json.loads(json.dumps(brief))
    draft["status"] = "draft"
    draft["owner_confirmation"] = {"confirmed": False, "summary": ""}
    failures += report("draft empty confirmation summary", validate_brief(draft))
    for field, bad_values in (
            ("confirmed", (None, 0, 1, "false", [], {})),
            ("summary", (None, False, 7, [], {}))):
        for value in bad_values:
            malformed = json.loads(json.dumps(draft))
            malformed["owner_confirmation"][field] = value
            failures += report(f"draft confirmation {field} {value!r}", [] if any(
                f"owner_confirmation.{field}" in error for error in validate_brief(malformed)) else ["accepted"])
    draft["items"].append({"id": "BQ-01", "kind": "question", "question": "Next decision?", "status": "open"})
    draft["frontier"] = ["BQ-01"]
    failures += report("draft open frontier", validate_brief(draft))
    for frontier in (["BQ-01", "BQ-01"], ["BQ-99"], [[]], [{}]):
        malformed = json.loads(json.dumps(draft))
        malformed["frontier"] = frontier
        failures += report(f"draft invalid frontier {frontier!r}", [] if validate_brief(malformed) else ["accepted"])
    draft["items"][-1]["status"] = "deferred"
    failures += report("draft deferred frontier", [] if validate_brief(draft) else ["accepted"])
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        goal_path = root / ".opencode" / "mvp" / "goal.md"
        goal_path.parent.mkdir(parents=True)
        for status, confirmed in (("final", True), ("draft", True), ("draft", False), ("final", False)):
            source_brief = json.loads(json.dumps(brief))
            source_brief["status"] = status
            source_brief["owner_confirmation"]["confirmed"] = confirmed
            source_hash = brief_hash(source_brief)
            (root / "brief.md").write_text(
                f"---\nstatus: {status}\nbrief-hash: {source_hash}\n---\n\n```json brief\n"
                + json.dumps(source_brief) + "\n```\n", encoding="utf-8")
            goal = json.loads(json.dumps(goal_fixture))
            goal["source"] = {
                "type": "brief", "path": "brief.md", "brief_hash": source_hash,
                "coverage": [{"brief_id": item["id"], "disposition": "outcome", "outcome_ids": ["O-01"]}
                             for item in source_brief["items"]],
            }
            goal_path.write_text(render_goal(goal), encoding="utf-8")
            source_problems = validate_goal_artifact(goal_path)[2]
            failures += report(f"goal source {status} confirmed={confirmed}", [] if
                               bool(source_problems) == (status != "final" or not confirmed)
                               else ["incorrect source gate"])
            if status == "final" and confirmed:
                for disposition in ("constraint", "deferred", "non-goal", "rejected"):
                    weakened = json.loads(json.dumps(goal))
                    success = next(item for item in source_brief["items"] if item["kind"] == "success")
                    coverage = next(item for item in weakened["source"]["coverage"] if item["brief_id"] == success["id"])
                    coverage.pop("outcome_ids")
                    coverage.update(disposition=disposition, reason="Required in a later slice")
                    goal_path.write_text(render_goal(weakened), encoding="utf-8")
                    failures += report("goal success disposition " + disposition, [] if any(
                        f"success {success['id']} must map to outcomes" in error
                        for error in validate_goal_artifact(goal_path)[2]) else ["accepted scope removal"])

    missing_success = json.loads(json.dumps(brief))
    missing_success["items"] = [
        item for item in missing_success["items"] if item.get("kind") != "success"
    ]
    duplicate_brief = json.loads(json.dumps(brief))
    duplicate_brief["items"].append(json.loads(json.dumps(duplicate_brief["items"][0])))
    missing_rejected = any("success item" in item for item in validate_brief(missing_success))
    duplicate_rejected = any("duplicate item id" in item for item in validate_brief(duplicate_brief))
    malformed_rejected = bool(validate_brief({
        "schema_version": 1, "revision": 1, "status": [], "summary": "x",
        "items": [], "frontier": [[]], "owner_confirmation": {},
    }))
    for bad_kind in ([], {}, None, True):
        malformed = json.loads(json.dumps(brief))
        malformed["items"][0]["kind"] = bad_kind
        malformed_rejected = bool(validate_brief(malformed)) and malformed_rejected
    if missing_rejected and duplicate_rejected and malformed_rejected:
        print("[invalid brief] OK (independent rules and malformed types rejected)")
    else:
        print("[invalid brief] X a brief invariant was accepted")
        failures += 1

    valid_meta, valid = read_artifact(FIXTURES / "contract-valid.md", "contract")
    problems = validate_contract(valid)
    if valid_meta.get("contract-hash") != contract_hash(valid):
        problems.append("valid fixture frontmatter hash mismatch")
    failures += report("valid contract", problems)

    grilled = json.loads(json.dumps(valid))
    grilled["intake"] = {
        "mode": "grilled",
        "brief_path": "brief-valid.md",
        "brief_hash": expected_brief_hash,
        "dispositions": [
            {"brief_id": "BF-01", "status": "consumed", "contract_ids": ["P-01"]},
            {"brief_id": "BD-01", "status": "consumed", "contract_ids": ["P-01"]},
            {"brief_id": "BS-01", "status": "consumed", "contract_ids": ["P-01", "V-01"]},
        ],
    }
    grilled_problems = validate_contract(grilled)
    grilled_problems += validate_contract_intake(FIXTURES / "contract-valid.md", grilled)
    failures += report("brief-to-contract handoff", grilled_problems)

    with tempfile.TemporaryDirectory() as temp_dir:
        intake_dir = Path(temp_dir)
        unverified_brief = json.loads(json.dumps(brief))
        next(item for item in unverified_brief["items"] if item["id"] == "BF-01")["evidence_status"] = "unverified"
        unverified_hash = brief_hash(unverified_brief)
        (intake_dir / "brief.md").write_text(
            "---\nstatus: final\nbrief-hash: " + unverified_hash
            + "\n---\n\n```json brief\n"
            + json.dumps(unverified_brief, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n```\n", encoding="utf-8", newline="\n",
        )
        unverified_contract = json.loads(json.dumps(grilled))
        unverified_contract["intake"]["brief_path"] = "brief.md"
        unverified_contract["intake"]["brief_hash"] = unverified_hash
        unverified_problems = validate_contract_intake(intake_dir / "contract.md", unverified_contract)
        inactive_contract = json.loads(json.dumps(grilled))
        inactive_contract["nodes"]["P"][0]["status"] = "withdrawn"
        inactive_problems = validate_contract(inactive_contract)
        directory_contract = json.loads(json.dumps(grilled))
        directory_contract["intake"]["brief_path"] = "."
        directory_problems = validate_contract_intake(intake_dir / "contract.md", directory_contract)
        bad_reason_contract = json.loads(json.dumps(grilled))
        bad_reason_contract["intake"]["dispositions"][0] = {
            "brief_id": "BF-01", "status": "deferred", "reason": True,
        }
        reason_problems = validate_contract(bad_reason_contract)
    if (any("cannot map to P-01" in item for item in unverified_problems)
            and any("consumed target must be active" in item for item in inactive_problems)
            and any("readable file" in item for item in directory_problems)
            and any("needs reason" in item for item in reason_problems)):
        print("[brief intake safety] OK (evidence, active target, and path enforced)")
    else:
        print(f"[brief intake safety] X {unverified_problems + inactive_problems + directory_problems + reason_problems}")
        failures += 1

    broken_handoff = json.loads(json.dumps(grilled))
    broken_handoff["intake"]["brief_hash"] = "stale"
    broken_handoff["intake"]["dispositions"].pop()
    handoff_problems = validate_contract_intake(FIXTURES / "contract-valid.md", broken_handoff)
    if any("brief_hash mismatch" in item for item in handoff_problems) and any(
            "no disposition" in item for item in handoff_problems):
        print("[brief handoff tamper/coverage] OK (rejected)")
    else:
        print(f"[brief handoff tamper/coverage] X {handoff_problems}")
        failures += 1

    invalid = json.loads(json.dumps(valid))
    invalid["control"]["audit_budget"] = -1
    invalid["nodes"]["F"][0]["serves"] = []
    invalid["nodes"]["I"][0]["depends_on"] = ["I-01"]
    if validate_contract(invalid):
        print("[invalid contract] OK (rejected)")
    else:
        print("[invalid contract] X unexpectedly accepted")
        failures += 1

    inactive = json.loads(json.dumps(valid))
    for kind in ("F", "I", "V"):
        inactive["nodes"][kind][0]["status"] = "withdrawn"
    duplicate = json.loads(json.dumps(valid))
    duplicate["nodes"]["I"][0]["variants"][0]["segments"].append(
        json.loads(json.dumps(duplicate["nodes"]["I"][0]["variants"][0]["segments"][0]))
    )
    if validate_contract(inactive) and validate_contract(duplicate):
        print("[active coverage/unique segments] OK")
    else:
        failures += 1
        print("[active coverage/unique segments] X invalid contract accepted")

    redlined = json.loads(json.dumps(valid))
    redlined["nodes"]["V"][0]["red_command"] = "python -m pytest -k deterministic -x"
    if validate_contract(redlined):
        failures += 1
        print("[tdd red_command] X valid red_command rejected")
    else:
        print("[tdd red_command] OK (optional field accepted)")
    human_red = json.loads(json.dumps(redlined))
    human_red["nodes"]["V"][0]["type"] = "human"
    human_red["nodes"]["V"][0]["observation"] = "owner watches the artifact"
    human_red["nodes"]["V"][0].pop("command", None)
    if any("red_command" in problem for problem in validate_contract(human_red)):
        print("[tdd red_command] OK (human V rejected)")
    else:
        failures += 1
        print("[tdd red_command] X human V with red_command accepted")

    strict = json.loads(json.dumps(valid))
    strict["workflow_protocol"] = "v0.2"
    strict_v = strict["nodes"]["V"][0]
    failures += report("v0.2 missing assertion", [] if any(
        "assertion must be an object" in item for item in validate_contract(strict)) else ["accepted"])
    for protocol in ("legacy", "v0.1"):
        old = json.loads(json.dumps(valid))
        old["workflow_protocol"] = protocol
        failures += report(protocol + " assertion-free compatibility", validate_contract(old))
    for assertion in (None, {}, {"type": "stdout-contains", "literal": " "},
                      {"type": "stdout-contains", "literal": "ok", "extra": True},
                      {"type": "json-equals"}, {"type": "json-equals", "expected": float("nan")}):
        strict_v["assertion"] = assertion
        failures += report("v0.2 invalid assertion", [] if validate_contract(strict) else ["accepted"])
    for name, code, assertion, passed in (
            ("wrong", "print('wrong')", {"type": "stdout-contains", "literal": "Hello user"}, False),
            ("literal", "print('Hello user')", {"type": "stdout-contains", "literal": "Hello user"}, True),
            ("json-wrong", "print('false')", {"type": "json-equals", "expected": True}, False),
            ("json", "print('true')", {"type": "json-equals", "expected": True}, True)):
        strict_v.update(command=f'"{sys.executable}" -c "{code}"', assertion=assertion)
        failures += report("v0.2 schema " + name, validate_contract(strict))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            contract_path, plan_path = root / "contract.md", root / "PLAN.md"
            ledger_path, state_path = root / "events.jsonl", root / "workflow-state.json"
            event_path = root / "event.json"
            contract_path.write_text("---\nstatus: draft\nphase: intake\n---\n\n```json contract\n"
                                     + json.dumps(strict) + "\n```\n", encoding="utf-8")
            strict_plan = compile_plan(strict)
            plan_path.write_text(render_plan(strict_plan, "test"), encoding="utf-8")
            bindings = {"contract_hash": contract_hash(strict), "plan_structure_hash": plan_hash(strict_plan)}
            event_path.write_text(json.dumps({"id": "EV-REVIEW", "to_status": "reviewing",
                                             "to_phase": "final-audit-recorded"}), encoding="utf-8")
            append_event(state_path, ledger_path, event_path, 0)
            event_path.write_text(json.dumps({"id": "EV-AUDIT", "type": "final-audit", "result": "passed",
                                             **bindings}), encoding="utf-8")
            record_evidence_event(ledger_path, event_path)
            event_path.write_text(json.dumps({"id": "EV-RELEASE", "to_status": "passed", "to_phase": "idle",
                                             "final_audit_event": "EV-AUDIT", **bindings}), encoding="utf-8")
            release_contract(contract_path, state_path, ledger_path, event_path, 1)
            event_path.write_text(json.dumps({"id": "EV-OWNER", "type": "owner-decision",
                                             "decision": "plan-confirmation", "result": "accepted", **bindings}), encoding="utf-8")
            record_evidence_event(ledger_path, event_path)
            event_path.write_text(json.dumps({"id": "EV-CONFIRM", "authorization": "owner-confirmed",
                                             "owner_event": "EV-OWNER", "selections": {
                                                 "I-01": {"variant": "base", "selector_evidence": "default"}}}), encoding="utf-8")
            confirm_plan(plan_path, event_path, contract_path, ledger_path)
            step = strict_plan["steps"][0]
            for revision, state in enumerate(("selected", "executing", "verifying")):
                event_path.write_text(json.dumps({"id": "EV-" + state.upper(), "type": "step-transition",
                                                 "step_id": step["id"], "step_hash": step_hash(step),
                                                 "to_state": state, "expected_revision": revision, **bindings}), encoding="utf-8")
                apply_plan_event(plan_path, event_path, contract_path, ledger_path)
            evidence_path = root / "evidence" / "step.json"
            event = verify_step(plan_path, step["id"], "V-01", contract_path, ledger_path, evidence_path, "EV-V")
            payload = json.loads(evidence_path.read_text(encoding="utf-8"))
            failures += report("v0.2 runner " + name, [] if event["exit_code"] == 0 and
                               (event["result"] == "passed") == passed and payload.get("assertion") == assertion and
                               payload.get("assertion_passed") is passed else ["incorrect assertion result"])
            failures += report("v0.2 evidence " + name, [] if
                               bool(trusted_step_evidence_problems(event, strict_v)) != passed else ["incorrect evidence gate"])
            if passed:
                for field, value in (("stdout", "wrong"), ("assertion_passed", False), ("assertion", {})):
                    forged = dict(payload)
                    forged[field] = value
                    evidence_path.write_text(json.dumps(forged), encoding="utf-8")
                    forged_event = dict(event, output_hash=hashlib.sha256(evidence_path.read_bytes()).hexdigest())
                    failures += report("v0.2 assertion recheck " + field, [] if
                                       trusted_step_evidence_problems(forged_event, strict_v) else ["accepted"])

    compiled = compile_plan(valid)
    plan_meta, plan = read_artifact(FIXTURES / "plan-valid.md", "plan")
    problems = validate_plan(plan, valid)
    if plan_meta.get("plan-structure-hash") != plan_hash(plan):
        problems.append("valid plan frontmatter hash mismatch")
    failures += report("valid plan", problems)
    if any("confirmed and building" in item for item in plan_artifact_problems(
            plan_meta, plan, valid, [], require_building=True)):
        print("[PLAN confirmation gate] OK (planning PLAN rejected for build)")
    else:
        print("[PLAN confirmation gate] X planning PLAN accepted for build")
        failures += 1
    unauthorized = json.loads(json.dumps(compiled))
    unauthorized["runtime"].update({
        "status": "building", "selected_variants": {"I-01": "base"},
        "selection_events": {"I-01": "EV-SELECT-UNAUTHORIZED"},
        "step_states": {"S-I01-base-01": "pending"},
    })
    unauthorized_events = [{
        "id": "EV-SELECT-UNAUTHORIZED", "type": "variant-selection",
        "unit": "I-01", "variant": "base", "selector_evidence": "default",
        "contract_hash": unauthorized["contract_hash"],
        "plan_structure_hash": unauthorized["plan_structure_hash"],
    }]
    if any("owner confirmation" in item for item in validate_plan(unauthorized, valid, unauthorized_events)):
        print("[PLAN owner authorization] OK (hand-edited activation rejected)")
    else:
        print("[PLAN owner authorization] X unauthorized activation accepted")
        failures += 1
    with tempfile.TemporaryDirectory() as temp_dir:
        plan_dir = Path(temp_dir)
        contract_path = plan_dir / "contract.md"
        plan_path = plan_dir / "PLAN.md"
        ledger_path = plan_dir / "events.jsonl"
        selection_path = plan_dir / "selection.json"
        owner_event_path = plan_dir / "owner-event.json"
        state_path = plan_dir / "workflow-state.json"
        review_event_path = plan_dir / "review-event.json"
        audit_event_path = plan_dir / "audit-event.json"
        release_event_path = plan_dir / "release-event.json"
        contract_path.write_text((FIXTURES / "contract-valid.md").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        update_frontmatter(contract_path, {"status": "draft", "phase": "intake"})
        plan_path.write_text((FIXTURES / "plan-valid.md").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        selection_path.write_text(json.dumps({
            "id": "EV-PLAN-CONFIRM-TEST",
            "authorization": "owner-confirmed",
            "owner_event": "EV-OWNER-PLAN-TEST",
            "selections": {"I-01": {"variant": "base", "selector_evidence": "default"}},
        }), encoding="utf-8", newline="\n")
        owner_event_path.write_text(json.dumps({
            "id": "EV-OWNER-PLAN-TEST", "type": "owner-decision",
            "decision": "plan-confirmation", "result": "accepted",
            "contract_hash": plan["contract_hash"],
            "plan_structure_hash": plan["plan_structure_hash"],
        }), encoding="utf-8", newline="\n")
        review_event_path.write_text(json.dumps({
            "id": "EV-REVIEW-TEST", "to_status": "reviewing",
            "to_phase": "final-audit-recorded",
        }), encoding="utf-8", newline="\n")
        audit_event_path.write_text(json.dumps({
            "id": "EV-AUDIT-TEST", "type": "final-audit", "result": "passed",
            "contract_hash": plan["contract_hash"],
        }), encoding="utf-8", newline="\n")
        release_event_path.write_text(json.dumps({
            "id": "EV-RELEASE-TEST", "to_status": "passed", "to_phase": "idle",
            "contract_hash": plan["contract_hash"], "final_audit_event": "EV-AUDIT-TEST",
        }), encoding="utf-8", newline="\n")
        append_event(state_path, ledger_path, review_event_path, 0)
        record_evidence_event(ledger_path, audit_event_path)
        release_contract(contract_path, state_path, ledger_path, release_event_path, 1)
        record_evidence_event(ledger_path, owner_event_path)
        confirmed = confirm_plan(plan_path, selection_path, contract_path, ledger_path)
        confirmed_meta, confirmed_artifact = read_artifact(plan_path, "plan")
        confirmation_problems = plan_artifact_problems(
            confirmed_meta, confirmed_artifact, valid, load_ledger(ledger_path),
            require_building=True,
        )
        confirm_idempotent = confirm_plan(plan_path, selection_path, contract_path, ledger_path)
        conflicting_selection = plan_dir / "conflicting-selection.json"
        conflicting_selection.write_text(json.dumps({
            "id": "EV-PLAN-CONFIRM-TEST", "authorization": "owner-confirmed",
            "owner_event": "EV-OWNER-DOES-NOT-EXIST",
            "selections": {"I-01": {"variant": "base", "selector_evidence": "default"}},
        }), encoding="utf-8", newline="\n")
        confirmation_conflict_blocked = False
        try:
            confirm_plan(plan_path, conflicting_selection, contract_path, ledger_path)
        except ValidationError:
            confirmation_conflict_blocked = True
        confirmation_events = load_ledger(ledger_path)
        step_id = confirmed_artifact["steps"][0]["id"]
        step_digest = step_hash(confirmed_artifact["steps"][0])
        for revision, event_id, target_state in (
                (0, "EV-STEP-SELECTED", "selected"),
                (1, "EV-STEP-EXECUTING", "executing"),
                (2, "EV-STEP-VERIFYING", "verifying")):
            runtime_event = plan_dir / f"{event_id}.json"
            runtime_event.write_text(json.dumps({
                "id": event_id, "type": "step-transition",
                "step_id": step_id, "to_state": target_state,
                "expected_revision": revision,
                "contract_hash": plan["contract_hash"],
                "plan_structure_hash": plan["plan_structure_hash"],
                "step_hash": step_digest,
            }), encoding="utf-8", newline="\n")
            apply_plan_event(plan_path, runtime_event, contract_path, ledger_path)
        verification_path = plan_dir / "verification.json"
        verification_path.write_text(json.dumps({
            "id": "EV-STEP-V-TEST", "type": "step-verification",
            "step_id": step_id, "v_id": "V-01", "result": "passed",
            "output_hash": "test-output", "contract_hash": plan["contract_hash"],
            "plan_structure_hash": plan["plan_structure_hash"], "step_hash": step_digest,
        }), encoding="utf-8", newline="\n")
        try:
            record_evidence_event(ledger_path, verification_path)
            failures += report("forged step pass", ["record accepted forged pass"])
        except ValidationError:
            print("[forged step pass] OK (rejected)")
        step_evidence = plan_dir / "evidence" / "step.json"
        generated = verify_step(plan_path, step_id, "V-01", contract_path,
                                ledger_path, step_evidence, "EV-STEP-V-TEST")
        failures += report("verify-step execution and retry", [] if generated["result"] == "passed" and
                           verify_step(plan_path, step_id, "V-01", contract_path,
                                       ledger_path, step_evidence, "EV-STEP-V-TEST") == generated
                           else ["runner or idempotency failed"])
        failures += report("verify-step CLI retry", [] if main([
            "check.py", "verify-step", str(plan_path), step_id, "V-01",
            "--contract", str(contract_path), "--ledger", str(ledger_path),
            "--evidence", str(step_evidence), "--event-id", "EV-STEP-V-TEST",
        ]) == 0 else ["CLI failed"])
        original_ledger = ledger_path.read_text(encoding="utf-8")
        for binding in ("contract_hash", "plan_structure_hash", "step_hash"):
            altered_events = load_ledger(ledger_path)
            next(item for item in altered_events if item["id"] == generated["id"])[binding] = "stale"
            ledger_path.write_text("".join(json.dumps(item) + "\n" for item in altered_events), encoding="utf-8")
            try:
                verify_step(plan_path, step_id, "V-01", contract_path,
                            ledger_path, step_evidence, "EV-STEP-V-TEST")
                failures += report("step retry " + binding, ["accepted stale binding"])
            except ValidationError:
                print("[step retry " + binding + "] OK")
            finally:
                ledger_path.write_text(original_ledger, encoding="utf-8")
        original_plan = plan_path.read_text(encoding="utf-8")
        _, changed_plan = read_artifact(plan_path, "plan")
        changed_plan["steps"][0]["artifacts"] = ["changed-artifact"]
        plan_path.write_text(render_plan(changed_plan, "test"), encoding="utf-8")
        try:
            verify_step(plan_path, step_id, "V-01", contract_path,
                        ledger_path, step_evidence, "EV-STEP-V-TEST")
            failures += report("step retry changed plan", ["accepted"])
        except ValidationError:
            print("[step retry changed plan] OK")
        finally:
            plan_path.write_text(original_plan, encoding="utf-8")
        original_evidence = step_evidence.read_bytes()
        step_verification = valid["nodes"]["V"][0]
        failures += report("strict step evidence", trusted_step_evidence_problems(generated, step_verification))
        for malformed_payload in ([], None, {"result": "passed"}):
            step_evidence.write_text(json.dumps(malformed_payload), encoding="utf-8")
            failures += report("malformed step evidence", [] if trusted_step_evidence_problems(
                generated, step_verification) else ["accepted"])
            try:
                verify_step(plan_path, step_id, "V-01", contract_path,
                            ledger_path, step_evidence, "EV-STEP-V-TEST")
                failures += report("step retry tampering", ["accepted"])
            except ValidationError:
                print("[step retry tampering] OK")
        step_evidence.write_bytes(original_evidence)
        forged = dict(generated)
        forged.pop("producer")
        failures += report("strict step producer marker", [] if trusted_step_evidence_problems(
            forged, step_verification) else ["accepted"])
        attempt_path = plan_dir / "attempt.json"
        attempt_path.write_text(json.dumps({
            "id": "EV-ATTEMPT-TEST", "type": "attempt", "step_id": step_id,
            "result": "passed", "verification_events": ["EV-STEP-V-TEST"],
            "contract_hash": plan["contract_hash"],
            "plan_structure_hash": plan["plan_structure_hash"], "step_hash": step_digest,
        }), encoding="utf-8", newline="\n")
        record_evidence_event(ledger_path, attempt_path)
        complete_path = plan_dir / "complete.json"
        complete_path.write_text(json.dumps({
            "id": "EV-STEP-COMPLETE", "type": "step-transition",
            "step_id": step_id, "to_state": "complete", "attempt_id": "EV-ATTEMPT-TEST",
            "expected_revision": 3,
            "contract_hash": plan["contract_hash"],
            "plan_structure_hash": plan["plan_structure_hash"], "step_hash": step_digest,
        }), encoding="utf-8", newline="\n")
        apply_plan_event(plan_path, complete_path, contract_path, ledger_path)
        for revision, event_id, target_status in (
                (4, "EV-PLAN-PAUSE", "paused"),
                (5, "EV-PLAN-RESUME", "building")):
            runtime_event = plan_dir / f"{event_id}.json"
            runtime_event.write_text(json.dumps({
                "id": event_id, "type": "plan-transition", "to_status": target_status,
                "expected_revision": revision,
                "contract_hash": plan["contract_hash"],
                "plan_structure_hash": plan["plan_structure_hash"],
            }), encoding="utf-8", newline="\n")
            apply_plan_event(plan_path, runtime_event, contract_path, ledger_path)
        change_path = plan_dir / "change-orders.md"
        change_path.write_text(
            (FIXTURES / "change-orders-valid.md").read_text(encoding="utf-8"),
            encoding="utf-8", newline="\n",
        )
        _, prefinish_plan = read_artifact(plan_path, "plan")
        _, prefinish_orders = read_artifact(change_path, "change-orders")
        prefinish_matrix = reconcile_closure(
            valid, prefinish_plan, load_ledger(ledger_path), prefinish_orders,
        )
        converge_path = plan_dir / "converge.json"
        converge_path.write_text(json.dumps({
            "id": "EV-CONVERGE-TEST", "type": "converge-audit", "result": "passed",
            "contract_hash": plan["contract_hash"],
            "plan_structure_hash": plan["plan_structure_hash"],
            "reconcile_hash": reconcile_result_hash(prefinish_matrix),
            "plan_revision": prefinish_plan["runtime"]["revision"],
        }), encoding="utf-8", newline="\n")
        record_evidence_event(ledger_path, converge_path)
        finish_path = plan_dir / "finish.json"
        finish_path.write_text(json.dumps({
            "id": "EV-PLAN-DONE", "type": "plan-transition", "to_status": "done",
            "expected_revision": 6, "converge_audit_event": "EV-CONVERGE-TEST",
            "contract_hash": plan["contract_hash"],
            "plan_structure_hash": plan["plan_structure_hash"],
        }), encoding="utf-8", newline="\n")
        generic_done_blocked = False
        try:
            apply_plan_event(plan_path, finish_path, contract_path, ledger_path)
        except ValidationError:
            generic_done_blocked = True
        final_runtime = finish_plan(plan_path, finish_path, contract_path, change_path, ledger_path)
        finish_idempotent = finish_plan(plan_path, finish_path, contract_path, change_path, ledger_path)
        final_meta, final_plan = read_artifact(plan_path, "plan")
        runtime_problems = plan_artifact_problems(
            final_meta, final_plan, valid, load_ledger(ledger_path),
        )
    if (not confirmation_problems and confirmed["runtime"]["status"] == "building"
            and confirm_idempotent["runtime"]["status"] == "building"
            and confirmation_conflict_blocked and len(confirmation_events) == 5):
        print("[PLAN confirmation event] OK (activated and idempotent)")
    else:
        print(f"[PLAN confirmation event] X {confirmation_problems}")
        failures += 1
    if (not runtime_problems and generic_done_blocked
            and final_runtime["runtime"]["status"] == "done"
            and finish_idempotent["runtime"]["status"] == "done"):
        print("[PLAN runtime events] OK (step, pause, resume, and done projected)")
    else:
        print(f"[PLAN runtime events] X {runtime_problems}")
        failures += 1

    with tempfile.TemporaryDirectory() as temp_dir:
        legacy_dir = Path(temp_dir)
        legacy = json.loads(json.dumps(valid))
        legacy.pop("intake")
        legacy_hash = contract_hash(legacy)
        legacy_path = legacy_dir / "legacy.md"
        legacy_path.write_text(
            "---\nstatus: passed\ncontract-hash: " + legacy_hash
            + "\n---\n\n```json contract\n"
            + json.dumps(legacy, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n```\n", encoding="utf-8", newline="\n",
        )
        legacy_blocked = False
        try:
            read_checked_contract(legacy_path, require_released=True)
        except ValidationError:
            legacy_blocked = True
        draft_path = legacy_dir / "draft.md"
        draft_path.write_text(
            "---\nstatus: draft\n---\n\n```json contract\n"
            + json.dumps(valid, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n```\n", encoding="utf-8", newline="\n",
        )
        draft_blocked = False
        try:
            read_checked_contract(draft_path, require_released=True)
        except ValidationError:
            draft_blocked = True
        self_declared_path = legacy_dir / "self-declared.md"
        self_declared_path.write_text(
            (FIXTURES / "contract-valid.md").read_text(encoding="utf-8"),
            encoding="utf-8", newline="\n",
        )
        self_declared_blocked = False
        try:
            read_checked_contract(self_declared_path, require_released=True)
        except ValidationError:
            self_declared_blocked = True
    if legacy_blocked and draft_blocked and self_declared_blocked:
        print("[contract schema/release gate] OK (schema, status, and release proof enforced)")
    else:
        print("[contract schema/release gate] X schema or release gate failed")
        failures += 1
    future_release = {
        "id": "EV-RELEASE-FUTURE", "to_status": "passed", "to_phase": "idle",
        "contract_hash": contract_hash(valid), "final_audit_event": "EV-AUDIT-FUTURE",
    }
    try:
        validate_release_transition(future_release, [
            future_release,
            {"id": "EV-AUDIT-FUTURE", "type": "final-audit", "result": "passed",
             "contract_hash": contract_hash(valid)},
        ])
        future_release_blocked = False
    except ValidationError:
        future_release_blocked = True
    print("[release evidence order] " + ("OK" if future_release_blocked else "X future evidence accepted"))
    if not future_release_blocked:
        failures += 1
    forged = json.loads(json.dumps(plan))
    forged["variant_rules"]["I-01"][0]["selector"] = {"default": False, "forged": True}
    forged["plan_structure_hash"] = plan_hash(forged)
    if validate_plan(forged, valid):
        print("[immutable PLAN projection] OK (forgery rejected)")
    else:
        failures += 1
        print("[immutable PLAN projection] X forged selector accepted")
    impact = impact_closure(valid, ["P-01"], compiled)
    if {"P-01", "F-01", "I-01", "V-01"}.issubset(set(impact["nodes"])) and impact["steps"] == ["S-I01-base-01"]:
        print("[typed impact closure] OK")
    else:
        failures += 1
        print(f"[typed impact closure] X {impact}")
    fake_done = json.loads(json.dumps(compiled))
    fake_done["runtime"].update({
        "status": "done",
        "selected_variants": {"I-01": "base"},
        "selection_events": {"I-01": "EV-SELECT"},
        "step_states": {"S-I01-base-01": "complete"},
        "attempts": {"S-I01-base-01": ["EV-ATTEMPT"]},
    })
    stale_events = [
        {"id": "EV-SELECT", "type": "variant-selection", "unit": "I-01", "variant": "base", "selector_evidence": "default", "authorization": "owner-confirmed", "owner_event": "EV-OWNER-STALE", "contract_hash": "stale", "plan_structure_hash": "stale"},
        {"id": "EV-ATTEMPT", "type": "attempt", "step_id": "S-I01-base-01", "result": "passed", "verification_events": ["EV-V"], "contract_hash": "stale", "plan_structure_hash": "stale", "step_hash": "stale"},
        {"id": "EV-V", "type": "step-verification", "step_id": "S-I01-base-01", "v_id": "V-01", "result": "passed", "output_hash": "fake", "contract_hash": "stale", "plan_structure_hash": "stale", "step_hash": "stale"},
    ]
    if validate_plan(fake_done, valid, stale_events):
        print("[runtime evidence binding] OK (stale evidence rejected)")
    else:
        failures += 1
        print("[runtime evidence binding] X stale evidence accepted")

    clean_done = json.loads(json.dumps(compiled))
    done_hash, done_plan_hash = clean_done["contract_hash"], clean_done["plan_structure_hash"]
    done_step_hash = step_hash(clean_done["steps"][0])
    clean_done["runtime"].update({
        "status": "done",
        "selected_variants": {"I-01": "base"},
        "selection_events": {"I-01": "EV-SELECT-OK"},
        "step_states": {"S-I01-base-01": "complete"},
        "attempts": {"S-I01-base-01": ["EV-ATTEMPT-OK"]},
        "applied_event_ids": ["EV-STEP-SELECT-OK", "EV-STEP-EXECUTE-OK", "EV-STEP-VERIFY-OK", "EV-STEP-COMPLETE-OK", "EV-DONE-OK"],
        "revision": 5,
    })
    done_events = [
        {"id": "EV-OWNER-OK", "type": "owner-decision", "decision": "plan-confirmation", "result": "accepted",
         "contract_hash": done_hash, "plan_structure_hash": done_plan_hash},
        {"id": "EV-SELECT-OK", "type": "variant-selection", "unit": "I-01", "variant": "base",
         "selector_evidence": "default", "authorization": "owner-confirmed", "owner_event": "EV-OWNER-OK",
         "contract_hash": done_hash, "plan_structure_hash": done_plan_hash},
        {"id": "EV-V-OK", "type": "step-verification", "step_id": "S-I01-base-01", "v_id": "V-01",
         "result": "passed", "output_hash": "h", "contract_hash": done_hash,
         "plan_structure_hash": done_plan_hash, "step_hash": done_step_hash},
        {"id": "EV-ATTEMPT-OK", "type": "attempt", "step_id": "S-I01-base-01", "result": "passed",
         "verification_events": ["EV-V-OK"], "contract_hash": done_hash,
         "plan_structure_hash": done_plan_hash, "step_hash": done_step_hash},
        {"id": "EV-STEP-SELECT-OK", "type": "step-transition", "step_id": "S-I01-base-01", "to_state": "selected",
         "expected_revision": 0, "from_plan_revision": 0, "contract_hash": done_hash,
         "plan_structure_hash": done_plan_hash, "step_hash": done_step_hash},
        {"id": "EV-STEP-EXECUTE-OK", "type": "step-transition", "step_id": "S-I01-base-01", "to_state": "executing",
         "expected_revision": 1, "from_plan_revision": 1, "contract_hash": done_hash,
         "plan_structure_hash": done_plan_hash, "step_hash": done_step_hash},
        {"id": "EV-STEP-VERIFY-OK", "type": "step-transition", "step_id": "S-I01-base-01", "to_state": "verifying",
         "expected_revision": 2, "from_plan_revision": 2, "contract_hash": done_hash,
         "plan_structure_hash": done_plan_hash, "step_hash": done_step_hash},
        {"id": "EV-STEP-COMPLETE-OK", "type": "step-transition", "step_id": "S-I01-base-01", "to_state": "complete",
         "attempt_id": "EV-ATTEMPT-OK", "expected_revision": 3, "from_plan_revision": 3,
         "contract_hash": done_hash, "plan_structure_hash": done_plan_hash, "step_hash": done_step_hash},
        {"id": "EV-CONVERGE-OK", "type": "converge-audit", "result": "passed",
         "contract_hash": done_hash, "plan_structure_hash": done_plan_hash,
         "reconcile_hash": "selftest", "plan_revision": 4},
        {"id": "EV-DONE-OK", "type": "plan-transition", "to_status": "done", "expected_revision": 4,
         "from_plan_revision": 4, "reconcile_hash": "selftest", "converge_audit_event": "EV-CONVERGE-OK",
         "contract_hash": done_hash, "plan_structure_hash": done_plan_hash},
    ]
    if validate_plan(clean_done, valid, done_events):
        failures += 1
        print("[reconcile closure] X fully evidenced done PLAN rejected")
    strict_contract = json.loads(json.dumps(valid))
    strict_contract["workflow_protocol"] = "v0.2"
    strict_contract["nodes"]["V"][0]["assertion"] = {
        "type": "stdout-contains", "literal": "compiler fixture PASS",
    }
    strict_plan = compile_plan(strict_contract)
    strict_plan["runtime"] = json.loads(json.dumps(clean_done["runtime"]))
    strict_events = json.loads(json.dumps(done_events))
    for event in strict_events:
        event["contract_hash"] = strict_plan["contract_hash"]
        event["plan_structure_hash"] = strict_plan["plan_structure_hash"]
        if event["type"] == "attempt":
            event["subagent_id"] = "implementation-test"
    strict_problems = validate_plan(strict_plan, strict_contract, strict_events)
    failures += report("v0.2 rejects legacy passing evidence", [] if any(
        "not generated by verify-step" in item for item in strict_problems) else ["legacy evidence accepted"])
    forged_runtime = json.loads(json.dumps(clean_done))
    forged_runtime["runtime"]["applied_event_ids"] = []
    forged_runtime["runtime"]["revision"] = 0
    if any("ledger replay" in item for item in validate_plan(forged_runtime, valid, done_events)):
        print("[runtime ledger replay] OK (forged snapshot rejected)")
    else:
        failures += 1
        print("[runtime ledger replay] X forged done snapshot accepted")
    matrix = reconcile_closure(valid, clean_done, done_events, {"revision": 0, "orders": []})
    if matrix["status"] == "clean" and matrix["coverage"]["P-01"]["closed"]:
        print("[reconcile closure] OK (clean matrix)")
    else:
        failures += 1
        print(f"[reconcile closure] X {matrix['findings']}")
    dormant_matrix = reconcile_closure(valid, plan, [], {"revision": 0, "orders": []})
    dormant_flagged = (dormant_matrix["status"] == "incomplete"
                       and any("coverage open" in item for item in dormant_matrix["findings"])
                       and any("V-01" in item for item in dormant_matrix["findings"]))
    if dormant_flagged:
        print("[reconcile closure] OK (dormant PLAN flagged incomplete)")
    else:
        failures += 1
        print(f"[reconcile closure] X dormant PLAN not flagged: {dormant_matrix['findings']}")
    blocking_matrix = reconcile_closure(valid, clean_done, done_events, {"revision": 1, "orders": [{
        "id": "CR-07", "status": "proposed", "trigger": "t", "contract_before": "x",
        "impact_seed": ["I-01"], "impact_closure": ["I-01"], "waiver_eligible": False,
    }]})
    if blocking_matrix["status"] == "incomplete" and any("CR-07" in item for item in blocking_matrix["findings"]):
        print("[reconcile closure] OK (blocking CR flagged)")
    else:
        failures += 1
        print("[reconcile closure] X blocking CR not flagged")

    changed = json.loads(json.dumps(valid))
    changed["nodes"]["B"][0]["reason"] = "changed outside CR closure"
    recovery_order = {
        "contract_before": contract_hash(valid),
        "contract_after": contract_hash(changed),
        "impact_closure": ["I-01", "S-I01-base-01"],
    }
    try:
        enforce_recovery_contract_scope(valid, changed, recovery_order)
        failures += 1
        print("[recovery contract scope] X out-of-closure change accepted")
    except ValidationError:
        print("[recovery contract scope] OK")

    invalid_plan = json.loads(json.dumps(plan))
    invalid_plan["contract_hash"] = "stale"
    if validate_plan(invalid_plan, valid):
        print("[invalid plan] OK (rejected)")
    else:
        print("[invalid plan] X unexpectedly accepted")
        failures += 1

    _, valid_cr = read_artifact(FIXTURES / "change-orders-valid.md", "change-orders")
    failures += report("valid change-orders", validate_change_orders(valid_cr))
    invalid_cr = {
        "revision": 0,
        "orders": [{
            "id": "CR-01", "status": "closed", "trigger": "invalid",
            "contract_before": "old", "impact_seed": ["I-01"],
            "impact_closure": [], "waiver_eligible": False,
        }],
    }
    if validate_change_orders(invalid_cr):
        print("[invalid change-orders] OK (rejected)")
    else:
        print("[invalid change-orders] X unexpectedly accepted")
        failures += 1

    try:
        validate_transition("approved", "applying", CR_TRANSITIONS, "CR")
        validate_transition("applying", "verifying", CR_TRANSITIONS, "CR")
        validate_transition("verifying", "verified", CR_TRANSITIONS, "CR")
        try:
            validate_transition("approved", "verified", CR_TRANSITIONS, "CR")
            failures += 1
            print("[CR recovery] X illegal shortcut accepted")
        except ValidationError:
            print("[CR recovery] OK")
    except ValidationError as exc:
        failures += 1
        print(f"[CR recovery] X {exc}")

    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        state_path = base / "state.json"
        state_path.write_text(json.dumps(initial_state({"status": "draft", "phase": "intake"}, valid)), encoding="utf-8")
        event = base / "event.json"
        event.write_text(json.dumps({"id": "EV-01", "to_status": "reviewing", "to_phase": "intake"}), encoding="utf-8")
        state = append_event(state_path, base / "events.jsonl", event, 0)
        if state["revision"] != 1 or state["status"] != "reviewing":
            failures += 1
            print("[event CAS] X projection failed")
        else:
            replayed = append_event(state_path, base / "events.jsonl", event, 0)
            if replayed["revision"] != 1:
                failures += 1
                print("[event CAS] X idempotent replay changed revision")
            else:
                stale = base / "stale.json"
                stale.write_text(json.dumps({"id": "EV-02", "to_status": "suspended", "to_phase": "idle"}), encoding="utf-8")
                try:
                    append_event(state_path, base / "events.jsonl", stale, 0)
                    failures += 1
                    print("[event CAS] X stale revision accepted")
                except ValidationError:
                    print("[event CAS] OK")

            budget_ok = True
            for index, phase in ((2, "evidence"), (3, "review-recorded")):
                budget_event = base / f"budget-{index}.json"
                budget_event.write_text(json.dumps({
                    "id": f"EV-BUDGET-{index}", "to_status": "reviewing",
                    "to_phase": phase, "budget_kind": "audit",
                }), encoding="utf-8")
                append_event(state_path, base / "events.jsonl", budget_event, index - 1)
            exhausted = base / "budget-4.json"
            exhausted.write_text(json.dumps({
                "id": "EV-BUDGET-4", "to_status": "reviewing",
                "to_phase": "final-audit-pending", "budget_kind": "audit",
            }), encoding="utf-8")
            try:
                append_event(state_path, base / "events.jsonl", exhausted, 3)
                budget_ok = False
            except ValidationError:
                pass
            checkpoint = base / "checkpoint.json"
            checkpoint.write_text(json.dumps({
                "id": "EV-CONTROL-1", "to_status": "awaiting-owner",
                "to_phase": "idle", "scope_change": True,
            }), encoding="utf-8")
            try:
                append_event(state_path, base / "events.jsonl", checkpoint, 3)
                budget_ok = False
            except ValidationError:
                pass
            print("[budget/control gate] " + ("OK" if budget_ok else "X illegal event accepted"))
            if not budget_ok:
                failures += 1

        cr_path = base / "change-orders.md"
        cr_path.write_text(render_change_orders({"revision": 0, "orders": [{
            "id": "CR-01", "status": "proposed", "trigger": "test",
            "contract_before": "old", "impact_seed": ["I-01"],
            "impact_closure": ["I-01"], "waiver_eligible": False,
        }]}), encoding="utf-8")
        projected = None
        for revision, target in enumerate(("reviewing", "approved", "applying")):
            cr_event = base / f"cr-event-{revision}.json"
            cr_event.write_text(json.dumps({
                "id": f"EV-CR-{revision}", "cr_id": "CR-01", "to_status": target,
            }), encoding="utf-8")
            capability = "cr-recovery" if target == "applying" else None
            projected = apply_cr_event(cr_path, base / "cr-events.jsonl", cr_event, revision, capability)
        if projected["orders"][0]["status"] == "applying" and projected["revision"] == 3:
            print("[CR event CAS] OK")
        else:
            failures += 1
            print("[CR event CAS] X projection failed")
        conflict = base / "cr-conflict.json"
        conflict.write_text(json.dumps({
            "id": "EV-CR-2", "cr_id": "CR-02", "to_status": "applying",
        }), encoding="utf-8")
        try:
            apply_cr_event(cr_path, base / "cr-events.jsonl", conflict, 3, "cr-recovery")
            failures += 1
            print("[CR event identity] X conflicting replay accepted")
        except ValidationError:
            print("[CR event identity] OK")

        blocked = base / "blocked.md"
        blocked.write_text(render_change_orders({"revision": 0, "orders": [{
            "id": "CR-02", "status": "proposed", "trigger": "test",
            "contract_before": "old", "impact_seed": ["I-01"],
            "impact_closure": ["I-01"], "waiver_eligible": False,
        }]}), encoding="utf-8")
        try:
            enforce_cr_gate(blocked, base / "cr-events.jsonl")
            failures += 1
            print("[blocking CR gate] X ordinary construction allowed")
        except ValidationError:
            print("[blocking CR gate] OK")

        subagent_ok = True
        exec_ledger = base / "exec-events.jsonl"
        attempt_path = base / "attempt.json"
        attempt_path.write_text(json.dumps({
            "id": "EV-EXEC-1", "type": "attempt", "step_id": "S-I01-base-01",
            "result": "passed", "verification_events": [],
            "contract_hash": "h", "plan_structure_hash": "h", "step_hash": "h",
            "subagent_id": "step-executor/S-I01-base-01/1",
        }), encoding="utf-8")
        record_evidence_event(exec_ledger, attempt_path)
        bad_attempt = base / "bad-attempt.json"
        bad_attempt.write_text(json.dumps({
            "id": "EV-EXEC-2", "type": "attempt", "step_id": "S-I01-base-01",
            "result": "passed", "verification_events": [],
            "contract_hash": "h", "plan_structure_hash": "h", "step_hash": "h",
            "subagent_id": "   ",
        }), encoding="utf-8")
        try:
            record_evidence_event(exec_ledger, bad_attempt)
            subagent_ok = False
        except ValidationError:
            pass
        print("[subagent attempt events] " + ("OK" if subagent_ok else "X invalid subagent_id accepted"))
        if not subagent_ok:
            failures += 1

        tdd_ok = True
        tdd_ledger = base / "tdd-events.jsonl"
        red_event = base / "tdd-red.json"
        red_event.write_text(json.dumps({
            "id": "EV-TDD-RED", "type": "tdd-red", "step_id": "S-I01-base-01",
            "v_id": "V-01", "result": "failed", "output_hash": "r",
            "contract_hash": "h", "plan_structure_hash": "h", "step_hash": "h",
        }), encoding="utf-8")
        record_evidence_event(tdd_ledger, red_event)
        green_event = base / "tdd-green.json"
        green_event.write_text(json.dumps({
            "id": "EV-TDD-GREEN", "type": "tdd-green", "step_id": "S-I01-base-01",
            "v_id": "V-01", "result": "passed", "output_hash": "g",
            "contract_hash": "h", "plan_structure_hash": "h", "step_hash": "h",
        }), encoding="utf-8")
        record_evidence_event(tdd_ledger, green_event)
        fake_red = base / "tdd-fake.json"
        fake_red.write_text(json.dumps({
            "id": "EV-TDD-FAKE", "type": "tdd-red", "step_id": "S-I01-base-01",
            "v_id": "V-01", "result": "passed", "output_hash": "x",
            "contract_hash": "h", "plan_structure_hash": "h", "step_hash": "h",
        }), encoding="utf-8")
        try:
            record_evidence_event(tdd_ledger, fake_red)
            tdd_ok = False
        except ValidationError:
            pass
        print("[tdd evidence events] " + ("OK" if tdd_ok else "X red event with passed result accepted"))
        if not tdd_ok:
            failures += 1

    import runpy
    failures += runpy.run_path(str(ROOT / "tests" / "final_review.py"))["run"](sys.modules[__name__])
    print("selftest " + ("FAIL" if failures else "PASS"))
    return 1 if failures else 0


def main(argv):
    try:
        if "--selftest" in argv:
            return selftest()
        if len(argv) < 3:
            print(__doc__)
            return 2
        command = argv[1]
        if command == "brief":
            meta, brief, expected, problems = validate_brief_artifact(argv[2])
            print(f"brief-hash: {expected}")
            return report("brief", problems)
        if command == "brief-confirmation":
            _, brief, _, problems = validate_brief_artifact(argv[2])
            if problems:
                return report("brief-confirmation", problems)
            print(json.dumps(brief_confirmation_view(brief), ensure_ascii=False, indent=2))
            return 0
        if command == "hash" and len(argv) >= 3:
            for raw in argv[2:]:
                target = Path(raw)
                if not target.is_file():
                    print(f"{raw}: <missing file>")
                    return 1
                print(f"{target.as_posix()}: {_sha256_file(target)}")
            return 0
        if command == "goal":
            _, _, problems = validate_goal_artifact(argv[2])
            return report("goal", problems)
        if command == "prepare-plan":
            if len(argv) != 4 or _engineering_delivery is None:
                raise ValidationError("prepare-plan requires a goal and project-relative design path; engine must be installed")
            with file_lock(str(argv[2]) + ".runtime"):
                result = _engineering_delivery.prepare(argv[2], argv[3], sys.modules[__name__])
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if command in ("engineering-plan", "begin-cycle", "verify-cycle", "observe-cycle", "cycle-gate", "next-step", "request-decision", "resolve-decision"):
            with file_lock(str(argv[2]) + ".runtime"):
                _, goal, problems = validate_goal_artifact(argv[2])
                if problems:
                    return report("goal", problems)
                if goal.get("schema_version") != 3:
                    raise ValidationError("engineering delivery requires schema 3; explicitly migrate an unfinished goal")
                if command == "engineering-plan":
                    print("engineering plan PASS (structure only; review design and real-boundary semantics)")
                    return 0
                if command not in ("cycle-gate", "next-step") and goal.get("status") == "complete":
                    raise ValidationError("completed goals are immutable; create a new repair goal")
                cycles = _engineering_delivery.Cycles(argv[2], goal, sys.modules[__name__])
                if command == "begin-cycle" and len(argv) not in (3, 4):
                    raise ValidationError("begin-cycle accepts one optional step-id")
                if command == "begin-cycle":
                    packet = cycles.next_packet() if len(argv) == 3 else None
                    if packet is not None and packet["action"] not in ("begin-cycle", "retry", "revalidate"):
                        raise ValidationError("next-step action is " + packet["action"] + "; resolve it first")
                    result = cycles.begin(argv[3] if len(argv) == 4 else packet["step"]["id"])
                elif command == "verify-cycle":
                    result = cycles.verify()
                elif command == "observe-cycle":
                    if len(argv) == 4:
                        result = cycles.observe(argv[3])
                    else:
                        import argparse
                        parser = argparse.ArgumentParser(prog="observe-cycle")
                        parser.add_argument("--decision", choices=("advance", "retry", "blocked", "replan"), required=True)
                        parser.add_argument("--interpretation", required=True)
                        parser.add_argument("--next-action", dest="next_action", default="next-step")
                        result = cycles.observe(vars(parser.parse_args(argv[3:])))
                elif command == "cycle-gate":
                    result = cycles.gate()
                elif command == "next-step":
                    result = cycles.next_packet()
                elif command == "request-decision":
                    if len(argv) != 4:
                        raise ValidationError("request-decision requires a request JSON file")
                    result = cycles.readiness.request(cycles.read(Path(argv[3])))
                elif command == "resolve-decision":
                    if len(argv) != 5:
                        raise ValidationError("resolve-decision requires a condition/request id and decision JSON file")
                    result = cycles.readiness.resolve(argv[3], cycles.read(Path(argv[4])))
                print(json.dumps(result, ensure_ascii=False, indent=2))
                if result.get("passed") is False:
                    print("cycle failed; inspect receipts and record observation before retry")
                    return 1
                return 0
        if command == "verify-goal" and len(argv) >= 4:
            if "--evidence" not in argv:
                raise ValidationError("verify-goal requires --evidence")
            reuse_arg = argv[argv.index("--reuse") + 1] if "--reuse" in argv else None
            goal, payload = verify_goal_outcome(
                argv[2], argv[3], argv[argv.index("--evidence") + 1],
                recover_interrupted="--recover-interrupted" in argv,
                reuse_from=reuse_arg,
            )
            print(f"goal outcome {argv[3]}: {payload['result']}")
            return 0 if payload["result"] == "passed" else 1
        if command == "finish-goal":
            was_complete = False
            try:
                _, existing = read_artifact(argv[2], "goal")
                was_complete = existing.get("status") == "complete"
            except (OSError, ValidationError):
                pass
            goal = finish_goal(argv[2])
            if was_complete:
                print(
                    f"goal {goal['id']} was already complete; no re-verification performed "
                    "(use check-current for the current workspace state)"
                )
            else:
                print(f"finished goal {goal['id']} ({goal['status']})")
            return 0
        if command == "check-current":
            goal = check_current(argv[2])
            print(f"current goal {goal['id']}: recorded evidence still matches the workspace")
            return 0
        if command == "product-audit-gate" and len(argv) >= 3:
            if _product_observation is None:
                raise ValidationError(
                    "product_observation engine module unavailable: "
                    + (_PRODUCT_OBSERVATION_IMPORT_ERROR or "import failed")
                )
            _, goal, goal_problems = validate_goal_artifact(argv[2])
            if goal_problems:
                return report("goal", goal_problems)
            spec = goal.get("product_observation") or {}
            if goal.get("schema_version") not in (2, 3) or spec.get("required") is not True:
                print("product observation: not required for this goal (schema 1 or required=false)")
                return 0
            if "--trace" not in argv:
                raise ValidationError(
                    "product-audit-gate requires --trace <native trace> for goals with "
                    "product_observation.required=true"
                )
            trace_path = Path(argv[argv.index("--trace") + 1])
            if not trace_path.is_file():
                raise ValidationError(f"runtime trace not found: {trace_path}")
            if _runtime_trace is not None:
                try:
                    trace = _runtime_trace.load_trace(trace_path)
                except Exception as exc:
                    raise ValidationError(f"runtime trace is unreadable: {exc}") from exc
                provenance = _runtime_trace.trace_provenance(trace)
            else:
                try:
                    trace = json.loads(trace_path.read_text(encoding="utf-8-sig"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise ValidationError(f"runtime trace is unreadable: {exc}") from exc
                provenance = "unverified"
            if not isinstance(trace, dict):
                raise ValidationError("runtime trace must be a JSON object")
            problems = _product_observation.collect_observation_problems(
                goal, argv[2], trace=trace
            )
            problems = list(problems) + observation_state_policy_problems(argv[2], goal)
            if provenance != "native":
                problems = list(problems) + ["trace provenance is not native"]
            trace_binding = {
                "path": str(trace_path),
                "sha256": _sha256_file(trace_path),
                "provenance": provenance,
            }
            gate_path = _product_observation.write_gate_record(
                goal,
                argv[2],
                problems,
                trace_binding=trace_binding,
                goal_definition_hash=goal_definition_hash(goal),
            )
            print(f"product audit gate: {'pass' if not problems else 'fail'}")
            for failure in problems:
                print(f"  - {failure}")
            if gate_path is not None:
                print(f"gate record: {gate_path}")
            return 0 if not problems else 1
        if command == "runtime-gate" and len(argv) >= 4:
            if "--trace" not in argv:
                raise ValidationError("runtime-gate requires --trace")
            trace_arg = argv[argv.index("--trace") + 1]
            dispatch_arg = argv[argv.index("--dispatch") + 1] if "--dispatch" in argv else None
            policy_arg = argv[argv.index("--policy") + 1] if "--policy" in argv else None
            sidecar, gate_path = runtime_gate(argv[2], trace_arg, dispatch_arg, policy_arg)
            print(f"runtime gate {gate_path}: {sidecar['verdict']}")
            for failure in sidecar["failures"]:
                print(f"  - {failure}")
            return 0 if sidecar["verdict"] == "pass" else 1
        if command == "ui-gate" and len(argv) >= 4:
            if "--trace" not in argv:
                raise ValidationError("ui-gate requires --trace")
            trace_arg = argv[argv.index("--trace") + 1]
            gate, gate_path = ui_gate(
                argv[2], trace_arg,
                bind="--bind" in argv or "--rebind" in argv,
                rebind="--rebind" in argv,
            )
            print(f"ui gate {gate_path}: {gate['verdict']}")
            for failure in gate["failures"]:
                print(f"  - {failure}")
            return 0 if gate["verdict"] == "pass" else 1
        if command == "contract":
            meta, contract = read_artifact(argv[2], "contract")
            expected = contract_hash(contract)
            problems = contract_problems(argv[2], contract)
            if meta.get("status") not in CONTRACT_STATUS:
                problems.append("frontmatter status is invalid")
            elif meta.get("phase") not in STATUS_PHASES.get(meta.get("status"), set()):
                problems.append("frontmatter status/phase pair is invalid")
            if meta.get("status") in {"passed", "conditional"} and meta.get("contract-hash") != expected:
                problems.append("frontmatter contract-hash mismatch")
            print(f"contract-hash: {expected}")
            return report("contract", problems)
        if command == "compile" and len(argv) >= 4:
            if "--change-orders" not in argv or "--ledger" not in argv:
                raise ValidationError("compile requires --change-orders and --ledger")
            change_path = argv[argv.index("--change-orders") + 1]
            ledger_path = argv[argv.index("--ledger") + 1]
            recovery = argv[argv.index("--recovery-cr") + 1] if "--recovery-cr" in argv else None
            recovery_order = enforce_cr_gate(change_path, ledger_path, recovery)
            if not recovery_order and Path(argv[3]).exists():
                raise ValidationError("PLAN already exists; replacement requires scoped CR recovery")
            meta, contract = read_checked_contract(argv[2], require_released=True, ledger_path=ledger_path)
            plan = compile_plan(contract)
            if recovery_order:
                if "--previous-contract" not in argv:
                    raise ValidationError("CR recovery requires --previous-contract")
                _, old_contract = read_artifact(argv[argv.index("--previous-contract") + 1], "contract")
                enforce_recovery_contract_scope(old_contract, contract, recovery_order)
                if not Path(argv[3]).exists():
                    raise ValidationError("CR recovery requires the previous PLAN for scoped diff")
                _, old_plan = read_artifact(argv[3], "plan")
                enforce_recovery_scope(old_plan, plan, recovery_order)
            with Path(argv[3]).open("w" if recovery_order else "x", encoding="utf-8", newline="\n") as stream:
                stream.write(render_plan(plan, meta.get("project", "project")))
            print(f"wrote {argv[3]} ({len(plan['steps'])} variant-segments)")
            return 0
        if command == "confirm-plan" and len(argv) >= 4:
            if "--contract" not in argv or "--ledger" not in argv:
                raise ValidationError("confirm-plan requires --contract and --ledger")
            plan = confirm_plan(
                argv[2], argv[3], argv[argv.index("--contract") + 1],
                argv[argv.index("--ledger") + 1],
            )
            print(f"confirmed {argv[2]} ({len(plan['runtime']['selected_variants'])} variants)")
            return 0
        if command == "plan-event" and len(argv) >= 4:
            if "--contract" not in argv or "--ledger" not in argv:
                raise ValidationError("plan-event requires --contract and --ledger")
            plan = apply_plan_event(
                argv[2], argv[3], argv[argv.index("--contract") + 1],
                argv[argv.index("--ledger") + 1],
            )
            print(f"PLAN runtime status: {plan['runtime']['status']}")
            return 0
        if command == "record-human-step" and len(argv) >= 5:
            for flag in ("--contract", "--ledger", "--owner-event", "--event-id"):
                if flag not in argv:
                    raise ValidationError("record-human-step requires --contract, --ledger, --owner-event, and --event-id")
            event = verify_step(
                argv[2], argv[3], argv[4], argv[argv.index("--contract") + 1],
                argv[argv.index("--ledger") + 1], None, argv[argv.index("--event-id") + 1],
                owner_event=argv[argv.index("--owner-event") + 1],
            )
            print(f"human step verification {event['id']}: passed (owner events and IDs are locally claimed, not authenticated)")
            return 0
        if command == "verify-step" and len(argv) >= 5:
            for flag in ("--contract", "--ledger", "--evidence", "--event-id"):
                if flag not in argv:
                    raise ValidationError("verify-step requires --contract, --ledger, --evidence, and --event-id")
            event = verify_step(
                argv[2], argv[3], argv[4],
                argv[argv.index("--contract") + 1],
                argv[argv.index("--ledger") + 1],
                argv[argv.index("--evidence") + 1],
                argv[argv.index("--event-id") + 1],
                recover_interrupted="--recover-interrupted" in argv,
            )
            print(f"step verification {event['id']}: {event['result']}")
            return 0 if event["result"] == "passed" else 1
        if command == "finish-plan" and len(argv) >= 4:
            for flag in ("--contract", "--change-orders", "--ledger"):
                if flag not in argv:
                    raise ValidationError("finish-plan requires --contract, --change-orders, and --ledger")
            plan = finish_plan(
                argv[2], argv[3], argv[argv.index("--contract") + 1],
                argv[argv.index("--change-orders") + 1],
                argv[argv.index("--ledger") + 1],
            )
            print(f"finished {argv[2]} ({plan['runtime']['status']})")
            return 0
        if command == "plan":
            if "--contract" not in argv or "--change-orders" not in argv or "--ledger" not in argv:
                raise ValidationError("plan command requires --contract, --change-orders, and --ledger")
            recovery = argv[argv.index("--recovery-cr") + 1] if "--recovery-cr" in argv else None
            ledger_path = argv[argv.index("--ledger") + 1]
            recovery_order = enforce_cr_gate(argv[argv.index("--change-orders") + 1], ledger_path, recovery)
            contract_path = argv[argv.index("--contract") + 1]
            _, contract = read_checked_contract(contract_path, require_released=True, ledger_path=ledger_path)
            if recovery_order:
                if "--previous-contract" not in argv:
                    raise ValidationError("CR recovery plan validation requires --previous-contract")
                _, old_contract = read_artifact(argv[argv.index("--previous-contract") + 1], "contract")
                enforce_recovery_contract_scope(old_contract, contract, recovery_order)
            plan_meta, plan = read_artifact(argv[2], "plan")
            plan_problems = plan_artifact_problems(
                plan_meta, plan, contract, load_ledger(ledger_path),
                require_building="--require-building" in argv,
                require_resumable="--require-resumable" in argv,
            )
            if plan.get("runtime", {}).get("status") == "done":
                _, orders = read_artifact(argv[argv.index("--change-orders") + 1], "change-orders")
                plan_problems += done_reconcile_problems(
                    plan, contract, load_ledger(ledger_path), orders,
                )
            return report("plan", plan_problems)
        if command == "reconcile" and len(argv) >= 3:
            for flag in ("--contract", "--change-orders", "--ledger"):
                if flag not in argv:
                    raise ValidationError("reconcile requires --contract, --change-orders, and --ledger")
            ledger_path = argv[argv.index("--ledger") + 1]
            _, contract = read_checked_contract(
                argv[argv.index("--contract") + 1], require_released=True,
                ledger_path=ledger_path,
            )
            _, orders = read_artifact(argv[argv.index("--change-orders") + 1], "change-orders")
            _, plan = read_artifact(argv[2], "plan")
            events = load_ledger(ledger_path)
            problems = validate_contract(contract)
            problems += validate_plan(plan, contract, events)
            problems += validate_change_orders(orders)
            problems += validate_cr_provenance(orders, events)
            if problems:
                return report("reconcile", problems)
            matrix = reconcile_closure(contract, plan, events, orders)
            output = dict(
                matrix,
                reconcile_hash=reconcile_result_hash(matrix),
                plan_revision=plan.get("runtime", {}).get("revision", 0),
            )
            print(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        if command == "change-orders":
            if "--ledger" not in argv:
                raise ValidationError("change-orders requires --ledger")
            _, data = read_artifact(argv[2], "change-orders")
            problems = validate_change_orders(data)
            problems.extend(validate_cr_provenance(data, load_ledger(argv[argv.index("--ledger") + 1])))
            return report("change-orders", problems)
        if command == "impact" and len(argv) >= 4:
            _, contract = read_checked_contract(argv[2])
            plan = compile_plan(contract)
            print(json.dumps(impact_closure(contract, argv[3:], plan), ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        if command == "init" and len(argv) == 4:
            meta, contract = read_checked_contract(argv[2])
            if meta.get("status") != "draft" or meta.get("phase") not in {"intake", "idle"}:
                raise ValidationError("workflow state must be initialized from a draft contract")
            target = Path(argv[3])
            if target.exists():
                raise ValidationError(f"state already exists: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(initial_state(meta, contract), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            changes = target.parent / "change-orders.md"
            if not changes.exists():
                changes.write_text(render_change_orders({"revision": 0, "orders": []}), encoding="utf-8", newline="\n")
            print(f"initialized {target}")
            return 0
        if command == "event":
            if len(argv) < 5 or "--expected-revision" not in argv:
                raise ValidationError("event requires state, ledger, event and --expected-revision N")
            revision = int(argv[argv.index("--expected-revision") + 1])
            submitted = json.loads(Path(argv[4]).read_text(encoding="utf-8"))
            if submitted.get("to_status") in {"passed", "conditional"}:
                raise ValidationError("use release so contract frontmatter is projected with workflow state")
            state = append_event(argv[2], argv[3], argv[4], revision)
            print(json.dumps(state, ensure_ascii=False, sort_keys=True))
            return 0
        if command == "release":
            if len(argv) < 6 or "--expected-revision" not in argv:
                raise ValidationError("release requires contract, state, ledger, event, and --expected-revision N")
            revision = int(argv[argv.index("--expected-revision") + 1])
            state = release_contract(argv[2], argv[3], argv[4], argv[5], revision)
            print(json.dumps(state, ensure_ascii=False, sort_keys=True))
            return 0
        if command == "record" and len(argv) == 4:
            event = record_evidence_event(argv[2], argv[3])
            print(json.dumps(event, ensure_ascii=False, sort_keys=True))
            return 0
        if command == "cr-event":
            if len(argv) < 5 or "--expected-revision" not in argv or "--contract" not in argv:
                raise ValidationError("cr-event requires change-orders, ledger, event, --contract, and --expected-revision N")
            revision = int(argv[argv.index("--expected-revision") + 1])
            capability = argv[argv.index("--capability") + 1] if "--capability" in argv else None
            _, contract = read_checked_contract(argv[argv.index("--contract") + 1])
            data = apply_cr_event(argv[2], argv[3], argv[4], revision, capability, contract)
            print(json.dumps(data, ensure_ascii=False, sort_keys=True))
            return 0
        print(__doc__)
        return 2
    except (OSError, ValidationError, ValueError, TypeError, AttributeError, KeyError,
            json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

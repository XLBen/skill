#!/usr/bin/env python3
"""Contract workflow engine for contract-review and construction.

Commands:
  check.py brief <docs/brief.md>
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
  check.py cr-event <change-orders.md> <events.jsonl> <event.json> --expected-revision N
  check.py --selftest

The engine validates only deterministic structure. Semantic claims remain the
responsibility of an independent audit recorded by event ID.
"""
import hashlib
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
        return json.loads(match.group(1), object_pairs_hook=reject_duplicates)
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
    if brief.get("schema_version") != 1:
        problems.append("brief.schema_version must be 1")
    if (not isinstance(brief.get("revision"), int)
            or isinstance(brief.get("revision"), bool)
            or brief.get("revision", 0) < 1):
        problems.append("brief.revision must be a positive integer")
    if not isinstance(brief.get("status"), str) or brief.get("status") not in BRIEF_STATUS:
        problems.append("brief.status must be draft or final")
    if not isinstance(brief.get("summary"), str) or not brief.get("summary", "").strip():
        problems.append("brief.summary must be a non-empty string")

    items = brief.get("items", [])
    if not isinstance(items, list):
        problems.append("brief.items must be an array")
        items = []
    by_id = {}
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
        elif kind in {"constraint", "success", "non-goal"}:
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
        }.get(kind, ())
        for field in text_fields:
            if not isinstance(item.get(field), str) or not item.get(field, "").strip():
                problems.append(f"{ident or where}: {field} must be a non-empty string")

    frontier = brief.get("frontier", [])
    if not isinstance(frontier, list):
        problems.append("brief.frontier must be an array")
        frontier = []
    for ident in frontier:
        if not isinstance(ident, str) or ident not in by_id or by_id[ident].get("kind") != "question":
            problems.append(f"brief.frontier: unknown question {ident}")

    confirmation = brief.get("owner_confirmation", {})
    if not isinstance(confirmation, dict):
        problems.append("brief.owner_confirmation must be an object")
        confirmation = {}
    require(confirmation, ("confirmed", "summary"), "brief.owner_confirmation", problems)
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
    require(control, ("interaction", "audit_budget", "research_budget", "prototype_budget"), "control", problems)
    if control.get("interaction") not in {"autonomous", "checkpoints", "stepwise"}:
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
        require(node, ("claim", "kind", "source", "checked_at", "environment", "command", "inputs", "output_summary", "verdict", "bundle_hash"), node.get("id", "E"), problems)
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
            verified = set()
            for event_id in attempt.get("verification_events", []):
                verification = event_index.get(event_id)
                if (verification and verification.get("type") == "step-verification"
                        and verification.get("step_id") == step["id"]
                        and verification.get("result") == "passed"
                        and verification.get("contract_hash") == plan.get("contract_hash")
                        and verification.get("plan_structure_hash") == plan.get("plan_structure_hash")
                        and verification.get("step_hash") == expected_step_hash):
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


def record_evidence_event(ledger_path, event_path):
    ledger_path = Path(ledger_path)
    submitted = json.loads(Path(event_path).read_text(encoding="utf-8"))
    problems = []
    require(submitted, ("id", "type"), "evidence event", problems)
    if problems:
        raise ValidationError("; ".join(problems))
    if submitted["type"] not in {
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
    if problems:
        raise ValidationError("; ".join(problems))
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
    brief_meta, brief, expected_brief_hash, brief_problems = validate_brief_artifact(
        FIXTURES / "brief-valid.md"
    )
    if brief_meta.get("brief-hash") != expected_brief_hash:
        brief_problems.append("valid brief fixture frontmatter hash mismatch")
    failures += report("valid brief", brief_problems)

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
        record_evidence_event(ledger_path, verification_path)
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
            Path(argv[3]).write_text(render_plan(plan, meta.get("project", "project")), encoding="utf-8", newline="\n")
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

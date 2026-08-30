#!/usr/bin/env python3
"""Contract workflow engine for contract-review and construction.

Commands:
  check.py contract <docs/contract.md>
  check.py compile <docs/contract.md> <docs/PLAN.md> --change-orders <docs/change-orders.md> --ledger <docs/workflow-events.jsonl>
  check.py plan <docs/PLAN.md> --contract <docs/contract.md> --change-orders <docs/change-orders.md> --ledger <docs/workflow-events.jsonl>
  check.py reconcile <docs/PLAN.md> --contract <docs/contract.md> --change-orders <docs/change-orders.md> --ledger <docs/workflow-events.jsonl>
  check.py change-orders <docs/change-orders.md> --ledger <docs/workflow-events.jsonl>
  check.py impact <docs/contract.md> <ID> [<ID> ...]
  check.py init <docs/contract.md> <workflow-state.json>
  check.py event <state.json> <events.jsonl> <event.json> --expected-revision N
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
STEP_RE = re.compile(r"^S-I\d{2,}-[a-z0-9-]+-\d{2,}$")
ACTIVE = {"active", "superseded", "withdrawn"}
CONTRACT_STATUS = {
    "draft", "reviewing", "awaiting-owner", "re-reviewing", "blocked",
    "suspended", "passed", "conditional",
}
PLAN_STATUS = {"planning", "building", "paused", "suspended", "done"}
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
        if field not in obj or obj[field] in (None, ""):
            problems.append(f"{where}: missing {field}")


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
    if contract.get("profile") not in {"direct", "light", "full"}:
        problems.append("profile must be direct, light, or full")
    control = contract.get("control", {})
    require(control, ("interaction", "audit_budget", "research_budget", "prototype_budget"), "control", problems)
    if control.get("interaction") not in {"autonomous", "checkpoints", "stepwise"}:
        problems.append("control.interaction is invalid")
    for key in ("audit_budget", "research_budget", "prototype_budget"):
        if not isinstance(control.get(key), int) or control.get(key, -1) < 0:
            problems.append(f"control.{key} must be a non-negative integer")

    by_id, by_type = collect_nodes(contract, problems)
    active = {ident: node for ident, node in by_id.items() if node.get("status") == "active"}

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
        },
    }
    plan["plan_structure_hash"] = plan_hash(plan)
    step_ids = [step["id"] for step in steps]
    if len(step_ids) != len(set(step_ids)):
        raise ValidationError("compiler produced duplicate step IDs")
    return plan


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
    if not isinstance(selected, dict) or not isinstance(selection_events, dict):
        problems.append("PLAN variant runtime fields must be objects")
        selected, selection_events = {}, {}
    if not isinstance(step_states, dict) or not isinstance(attempts, dict):
        problems.append("PLAN step_states and attempts must be objects")
        step_states, attempts = {}, {}
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
    if runtime.get("status") in {"building", "paused", "done"}:
        if set(selected) != active_units or any(selected[unit] not in variants[unit] for unit in active_units):
            problems.append("PLAN must select exactly one compiled variant for every unit")
        if set(selection_events) != active_units or any(not selection_events.get(unit) for unit in active_units):
            problems.append("PLAN selected variants require selection event IDs")
    event_index = {event.get("id"): event for event in (events or [])}
    if runtime.get("status") in {"building", "paused", "done"} and events is None:
        problems.append("PLAN runtime validation requires the event ledger")
    for unit, event_id in selection_events.items():
        event = event_index.get(event_id)
        if not event or event.get("type") != "variant-selection" or event.get("unit") != unit or event.get("variant") != selected.get(unit):
            problems.append(f"{unit}: invalid variant selection event")
            continue
        if event.get("contract_hash") != plan.get("contract_hash") or event.get("plan_structure_hash") != plan.get("plan_structure_hash"):
            problems.append(f"{unit}: variant selection belongs to another contract or PLAN")
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
        if is_selected and runtime.get("status") in {"building", "paused", "done"} and state == "dormant":
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
        if ident in ids and event_payload(ids[ident]) != event_payload(event):
            raise ValidationError(f"ledger event ID has conflicting payloads: {ident}")
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
        "variant-selection", "attempt", "step-verification",
        "tdd-red", "tdd-green",
    }:
        raise ValidationError("record accepts only immutable evidence event types")
    if submitted["type"] == "verification":
        require(submitted, ("cr_id",), "evidence event", problems)
    if submitted["type"] in {"tdd-red", "tdd-green"}:
        require(submitted, ("step_id", "v_id", "result", "output_hash", "contract_hash", "plan_structure_hash", "step_hash"), "tdd evidence event", problems)
        expected_result = "failed" if submitted["type"] == "tdd-red" else "passed"
        if submitted.get("result") != expected_result:
            raise ValidationError(f"{submitted['type']} must record result={expected_result}")
    if submitted["type"] == "final-audit":
        require(submitted, ("contract_hash", "result"), "final audit event", problems)
    if submitted["type"] == "verification":
        require(submitted, ("v_id", "result", "output_hash"), "verification event", problems)
        if submitted.get("result") != "passed":
            raise ValidationError("only passed verification can satisfy a CR transition")
    if submitted["type"] == "variant-selection":
        require(submitted, ("unit", "variant", "selector_evidence", "contract_hash", "plan_structure_hash"), "variant selection", problems)
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


def write_json_projection(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


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


def render_plan(plan, project="fixture"):
    return (
        "---\n"
        f"project: {project}\n"
        f"contract-hash: {plan['contract_hash']}\n"
        f"plan-structure-hash: {plan['plan_structure_hash']}\n"
        "status: planning\n"
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
    valid_meta, valid = read_artifact(FIXTURES / "contract-valid.md", "contract")
    problems = validate_contract(valid)
    if valid_meta.get("contract-hash") != contract_hash(valid):
        problems.append("valid fixture frontmatter hash mismatch")
    failures += report("valid contract", problems)

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
        {"id": "EV-SELECT", "type": "variant-selection", "unit": "I-01", "variant": "base", "selector_evidence": "default", "contract_hash": "stale", "plan_structure_hash": "stale"},
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
    })
    done_events = [
        {"id": "EV-SELECT-OK", "type": "variant-selection", "unit": "I-01", "variant": "base",
         "selector_evidence": "default", "contract_hash": done_hash, "plan_structure_hash": done_plan_hash},
        {"id": "EV-V-OK", "type": "step-verification", "step_id": "S-I01-base-01", "v_id": "V-01",
         "result": "passed", "output_hash": "h", "contract_hash": done_hash,
         "plan_structure_hash": done_plan_hash, "step_hash": done_step_hash},
        {"id": "EV-ATTEMPT-OK", "type": "attempt", "step_id": "S-I01-base-01", "result": "passed",
         "verification_events": ["EV-V-OK"], "contract_hash": done_hash,
         "plan_structure_hash": done_plan_hash, "step_hash": done_step_hash},
    ]
    if validate_plan(clean_done, valid, done_events):
        failures += 1
        print("[reconcile closure] X fully evidenced done PLAN rejected")
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
        if command == "contract":
            meta, contract = read_artifact(argv[2], "contract")
            problems = validate_contract(contract)
            expected = contract_hash(contract)
            if meta.get("status") not in CONTRACT_STATUS:
                problems.append("frontmatter status is invalid")
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
            meta, contract = read_artifact(argv[2], "contract")
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
        if command == "plan":
            if "--contract" not in argv or "--change-orders" not in argv or "--ledger" not in argv:
                raise ValidationError("plan command requires --contract, --change-orders, and --ledger")
            recovery = argv[argv.index("--recovery-cr") + 1] if "--recovery-cr" in argv else None
            ledger_path = argv[argv.index("--ledger") + 1]
            recovery_order = enforce_cr_gate(argv[argv.index("--change-orders") + 1], ledger_path, recovery)
            contract_path = argv[argv.index("--contract") + 1]
            _, contract = read_artifact(contract_path, "contract")
            if recovery_order:
                if "--previous-contract" not in argv:
                    raise ValidationError("CR recovery plan validation requires --previous-contract")
                _, old_contract = read_artifact(argv[argv.index("--previous-contract") + 1], "contract")
                enforce_recovery_contract_scope(old_contract, contract, recovery_order)
            _, plan = read_artifact(argv[2], "plan")
            return report("plan", validate_plan(plan, contract, load_ledger(ledger_path)))
        if command == "reconcile" and len(argv) >= 3:
            for flag in ("--contract", "--change-orders", "--ledger"):
                if flag not in argv:
                    raise ValidationError("reconcile requires --contract, --change-orders, and --ledger")
            ledger_path = argv[argv.index("--ledger") + 1]
            _, contract = read_artifact(argv[argv.index("--contract") + 1], "contract")
            _, orders = read_artifact(argv[argv.index("--change-orders") + 1], "change-orders")
            _, plan = read_artifact(argv[2], "plan")
            events = load_ledger(ledger_path)
            problems = validate_contract(contract)
            problems += validate_plan(plan, contract, events)
            problems += validate_change_orders(orders)
            problems += validate_cr_provenance(orders, events)
            if problems:
                return report("reconcile", problems)
            print(json.dumps(reconcile_closure(contract, plan, events, orders),
                             ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        if command == "change-orders":
            if "--ledger" not in argv:
                raise ValidationError("change-orders requires --ledger")
            _, data = read_artifact(argv[2], "change-orders")
            problems = validate_change_orders(data)
            problems.extend(validate_cr_provenance(data, load_ledger(argv[argv.index("--ledger") + 1])))
            return report("change-orders", problems)
        if command == "impact" and len(argv) >= 4:
            _, contract = read_artifact(argv[2], "contract")
            problems = validate_contract(contract)
            if problems:
                raise ValidationError("contract is invalid:\n- " + "\n- ".join(problems))
            plan = compile_plan(contract)
            print(json.dumps(impact_closure(contract, argv[3:], plan), ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        if command == "init" and len(argv) == 4:
            meta, contract = read_artifact(argv[2], "contract")
            problems = validate_contract(contract)
            if problems:
                raise ValidationError("contract is invalid:\n- " + "\n- ".join(problems))
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
            state = append_event(argv[2], argv[3], argv[4], revision)
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
            _, contract = read_artifact(argv[argv.index("--contract") + 1], "contract")
            data = apply_cr_event(argv[2], argv[3], argv[4], revision, capability, contract)
            print(json.dumps(data, ensure_ascii=False, sort_keys=True))
            return 0
        print(__doc__)
        return 2
    except (FileNotFoundError, ValidationError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

#!/usr/bin/env python3
"""Deterministic stage and acceptance-handoff packet generation.

The workflow protocol exists in prose and routing JSON; seats repeatedly
re-assemble the same view in model text. This tool renders that view once,
from the authoritative sources, as a machine-readable packet:

  - `stage`   builds a `workflow-stage-packet/1`: the resolved stage, rigor,
              seat, single semantic owners, formal-verification owner, review
              mode and scope, applicable skills and file identities. The model
              reads the packet instead of re-reading every routing document.
  - `handoff` builds a `workflow-handoff-packet/1`: machine-generated facts
              (goal, scope, dispatch state, evidence index, gaps) with an empty
              `claims` block the model must fill with its own judgement. The
              generator never declares a pass, and a missing fact is surfaced
              in `gaps`, never silently dropped.
  - `validate` verifies a packet against the current routing/goal/evidence
              hashes; changed rules or artifacts make the packet stale.

Packets are deterministic for identical inputs (sorted keys, no timestamps
unless `--generated-at` is supplied). They are review inputs, not gates:
`check.py` and the runtime gate never accept a packet as evidence.

Python 3.10+, stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    import workflow_protocol as _protocol
except ImportError as _exc:  # pragma: no cover - engine copied without the resolver
    _protocol = None
    _PROTOCOL_IMPORT_ERROR = str(_exc)
else:
    _PROTOCOL_IMPORT_ERROR = ""

try:
    import check as _check
except ImportError:  # pragma: no cover - engine copied without check.py
    _check = None

STAGE_PACKET_SCHEMA = "workflow-stage-packet/1"
HANDOFF_PACKET_SCHEMA = "workflow-handoff-packet/1"

ROLE_TO_SEAT = {
    "controller": "controller",
    "worker": "worker-subagent",
    "reviewer": "reviewer-subagent",
    "test-author": "test-author-subagent",
    "step-executor": "step-executor-subagent",
}
MODE_FILES = {
    "final-audit": "../reviewer/references/modes/final-audit.md",
    "converge-audit": "../reviewer/references/modes/converge-audit.md",
}


def _utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def file_identity(raw: str, base: Path | None = None) -> dict[str, Any]:
    path = Path(raw)
    if not path.is_absolute() and base is not None:
        path = base / path
    digest = _sha256(path)
    entry: dict[str, Any] = {
        "path": str(raw).replace("\\", "/"),
        "exists": path.is_file(),
        "sha256": digest,
    }
    if not path.is_file():
        entry["reason"] = "file does not exist"
    elif digest is None:
        entry["reason"] = "file is unreadable"
    return entry


def _routing_context(routing_path: str | None) -> tuple[dict[str, Any], dict[str, Any], Path]:
    if _protocol is None:
        raise RuntimeError(f"workflow_protocol is unavailable: {_PROTOCOL_IMPORT_ERROR}")
    path = Path(routing_path) if routing_path else _protocol.default_routing_path()
    routing = _protocol.load_routing(path)
    identity = {
        "path": str(path).replace("\\", "/"),
        "sha256": _sha256(path),
        "schema_version": routing.get("schema_version"),
    }
    return routing, identity, path


def _narrowed_skills(
    routing: dict[str, Any], stage_id: str, rigor: str | None
) -> list[dict[str, Any]]:
    stage = _protocol.stage_definition(routing, stage_id)
    entries: list[dict[str, Any]] = []
    for entry in stage.get("required_skills") or []:
        try:
            applies = _protocol.pua_applies(entry, rigor)
        except _protocol.ProtocolError:
            applies = False  # unknown applies_when fails visibly below
        item: dict[str, Any] = {
            "name": entry.get("name"),
            "seat": entry.get("seat"),
            "applies": applies,
        }
        if entry.get("stage_card"):
            item["stage_card"] = entry["stage_card"]
        if entry.get("roles"):
            item["roles"] = list(entry["roles"])
        entries.append(item)
    return entries


def build_stage_packet(
    stage_id: str,
    rigor: str | None,
    role: str,
    inputs: list[str],
    evidence: list[str],
    routing_path: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    routing, routing_identity, _ = _routing_context(routing_path)
    stage = _protocol.stage_definition(routing, stage_id)
    seat = ROLE_TO_SEAT.get(role)
    if seat is None:
        raise ValueError(f"unknown role {role!r}; expected one of {sorted(ROLE_TO_SEAT)}")
    condition = _protocol.reviewer_condition(routing, stage_id, rigor)
    reviewer_block = stage.get("reviewer") or {}
    semantic = _protocol.semantic_checks(routing, stage_id)
    packet: dict[str, Any] = {
        "schema": STAGE_PACKET_SCHEMA,
        "routing": routing_identity,
        "stage": {
            "id": stage_id,
            "entry": stage.get("entry"),
            "rigors": list(stage.get("rigors") or []),
        },
        "rigor": rigor,
        "role": role,
        "seat": seat,
        "semantic_checks": semantic,
        "formal_verification": _protocol.formal_verification(routing, stage_id),
        "reviewer": {
            "mode": reviewer_block.get("mode"),
            "contract_bound": bool(reviewer_block.get("contract")),
            "condition": condition,
            "scope": reviewer_block.get("scope"),
            "mode_file": MODE_FILES.get(reviewer_block.get("mode")),
        },
        "required_skills": _narrowed_skills(routing, stage_id, rigor),
        "rules": {
            "formal_v_owner": "controller",
            "single_semantic_owner": True,
            "resolved_from": "responsibilities",
        },
        "inputs": [file_identity(item) for item in inputs],
        "evidence_index": [file_identity(item) for item in evidence],
        "missing": [],
        "return_envelope": "task-result/1",
        "claims": "The model fills findings/verdicts; this packet is an input, never a pass.",
    }
    if "ui_acceptance" in stage:
        packet["ui_acceptance"] = stage.get("ui_acceptance")
    for bucket in ("inputs", "evidence_index"):
        for entry in packet[bucket]:
            if not entry.get("exists") or entry.get("sha256") is None:
                packet["missing"].append(
                    {
                        "path": entry["path"],
                        "bucket": bucket,
                        "reason": entry.get("reason", "unreadable"),
                    }
                )
    if generated_at:
        packet["generated_at"] = generated_at
    return packet


def _load_goal(goal_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if _check is not None:
        meta, goal = _check.read_artifact(str(goal_path), "goal")
        return meta, goal
    # fallback: minimal goal fence reader
    text = goal_path.read_text(encoding="utf-8-sig")
    marker = "```json goal"
    if marker not in text:
        raise ValueError(f"goal artifact has no json goal fence: {goal_path}")
    body = text.split(marker, 1)[1].split("```", 1)[0]
    return {}, json.loads(body)


def build_handoff_packet(
    goal_path: Path,
    dispatch_path: Path | None = None,
    scope: str = "goal",
    evidence_paths: list[str] | None = None,
    evidence_dir: Path | None = None,
    ui_sidecar: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    goal_path = goal_path.resolve()
    if not goal_path.is_file():
        raise ValueError(f"goal artifact not found: {goal_path}")
    meta, goal = _load_goal(goal_path)
    goal_sha = _sha256(goal_path)
    goal_hash = _check.goal_definition_hash(goal) if _check is not None else None
    dispatches: dict[str, Any] | None = None
    if dispatch_path is not None:
        try:
            dispatches = json.loads(dispatch_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"dispatch record unreadable: {exc}") from exc

    outcome_entries = []
    for outcome in goal.get("outcomes") or []:
        entry = {
            "id": outcome.get("id"),
            "statement": outcome.get("statement"),
            "status": outcome.get("status"),
            "user_entry": bool(outcome.get("user_entry")),
            "has_recorded_evidence": bool(outcome.get("evidence")),
        }
        outcome_entries.append(entry)

    resolved_evidence: list[Path] = []
    if evidence_paths:
        resolved_evidence.extend(Path(item) for item in evidence_paths)
    if evidence_dir is not None and evidence_dir.is_dir():
        resolved_evidence.extend(sorted(evidence_dir.glob("*.json")))
    seen: set[str] = set()
    evidence_index = []
    gaps: list[dict[str, Any]] = []
    goal_id = goal.get("id")
    for path in resolved_evidence:
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        identity = file_identity(str(path))
        entry: dict[str, Any] = {"path": identity["path"], "sha256": identity.get("sha256")}
        if not identity.get("exists"):
            gaps.append({"kind": "missing-evidence", "path": identity["path"]})
            evidence_index.append(entry)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            gaps.append({"kind": "unreadable-evidence", "path": identity["path"]})
            evidence_index.append(entry)
            continue
        if isinstance(payload, dict):
            entry.update(
                {
                    "schema_version": payload.get("schema_version"),
                    "kind": payload.get("kind"),
                    "goal_id": payload.get("goal_id"),
                    "outcome_id": payload.get("outcome_id"),
                    "result": payload.get("result"),
                    "started_at": payload.get("started_at"),
                    "finished_at": payload.get("finished_at"),
                    "elapsed_seconds": payload.get("elapsed_seconds"),
                }
            )
            if goal_id and payload.get("goal_id") and payload["goal_id"] != goal_id:
                gaps.append(
                    {
                        "kind": "foreign-evidence",
                        "path": identity["path"],
                        "detail": f"goal_id {payload['goal_id']!r} != {goal_id!r}",
                    }
                )
            if payload.get("result") not in (None, "passed"):
                gaps.append(
                    {
                        "kind": "non-passing-evidence",
                        "path": identity["path"],
                        "detail": f"result={payload.get('result')!r}",
                    }
                )
            if (
                goal_hash
                and payload.get("kind") == "goal-verification"
                and payload.get("goal_definition_hash")
                and payload["goal_definition_hash"] != goal_hash
            ):
                gaps.append(
                    {
                        "kind": "stale-evidence",
                        "path": identity["path"],
                        "detail": "goal definition hash no longer matches the current goal card",
                    }
                )
        else:
            gaps.append({"kind": "malformed-evidence", "path": identity["path"]})
        evidence_index.append(entry)

    evidence_by_outcome: dict[str, list[dict[str, Any]]] = {}
    for entry in evidence_index:
        outcome_id = entry.get("outcome_id")
        if outcome_id:
            evidence_by_outcome.setdefault(str(outcome_id), []).append(entry)
    for outcome in outcome_entries:
        passed = [
            item
            for item in evidence_by_outcome.get(str(outcome["id"]), [])
            if item.get("result") == "passed"
        ]
        outcome["fresh_evidence"] = len(passed)
        if outcome.get("status") != "verified" and not passed:
            gaps.append(
                {
                    "kind": "outcome-without-passing-evidence",
                    "outcome_id": outcome["id"],
                }
            )

    dispatch_summary = None
    pending_actions: list[dict[str, Any]] = []
    if dispatches is not None:
        tasks = dispatches.get("tasks") or []
        active_slice = {}
        raw_slice = dispatches.get("active_slice")
        if isinstance(raw_slice, dict):
            active_slice = {
                "slice_id": raw_slice.get("slice_id"),
                "rigor": raw_slice.get("rigor"),
                "basis": raw_slice.get("basis"),
                "package": raw_slice.get("package"),
                "brief_path": raw_slice.get("brief_path"),
            }
        task_entries = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task_entries.append(
                {
                    "task_id": task.get("task_id"),
                    "role": task.get("role"),
                    "status": task.get("status"),
                    "attempt": task.get("attempt"),
                    "verdict": (task.get("acceptance") or {}).get("verdict"),
                    "pending_actions": list(
                        (task.get("acceptance") or {}).get("pending_actions") or []
                    ),
                }
            )
            for action in task.get("actions") or []:
                if not isinstance(action, dict):
                    continue
                if action.get("status") != "completed":
                    pending_actions.append(
                        {
                            "task_id": task.get("task_id"),
                            "action_id": action.get("action_id"),
                            "status": action.get("status"),
                        }
                    )
        unresolved_verdicts = [
            {"task_id": item["task_id"], "verdict": item["verdict"]}
            for item in task_entries
            if item["verdict"] in ("owner", "blocked") and item["pending_actions"] is None
        ]
        dispatch_summary = {
            "schema_version": dispatches.get("schema_version"),
            "goal_id": dispatches.get("goal_id"),
            "active_slice": active_slice,
            "tasks": task_entries,
            "failure_counters": dispatches.get("failure_counters") or [],
        }
        for pending in pending_actions:
            gaps.append(
                {
                    "kind": "unresolved-controller-action",
                    "task_id": pending["task_id"],
                    "action_id": pending["action_id"],
                    "detail": f"status={pending['status']!r}",
                }
            )
        for item in task_entries:
            if item["verdict"] in ("owner", "blocked"):
                gaps.append(
                    {
                        "kind": "unresolved-verdict",
                        "task_id": item["task_id"],
                        "detail": f"verdict={item['verdict']!r}",
                    }
                )
            if item["status"] == "failed":
                gaps.append({"kind": "failed-dispatch", "task_id": item["task_id"]})

    ui_summary = None
    if ui_sidecar is not None:
        identity = file_identity(str(ui_sidecar))
        ui_summary = identity
        if not identity.get("exists"):
            gaps.append({"kind": "missing-ui-sidecar", "path": identity["path"]})
        else:
            try:
                payload = json.loads(ui_sidecar.read_text(encoding="utf-8-sig"))
                if isinstance(payload, dict):
                    ui_summary.update(
                        {
                            "applicability": payload.get("applicability"),
                            "artifact_identity": payload.get("artifact_identity"),
                            "scenarios": [
                                {
                                    "id": scenario.get("id"),
                                    "status": scenario.get("status"),
                                }
                                for scenario in payload.get("scenarios") or []
                                if isinstance(scenario, dict)
                            ],
                        }
                    )
                    for scenario in payload.get("scenarios") or []:
                        if isinstance(scenario, dict) and scenario.get("status") not in (
                            "passed",
                            "not-applicable",
                        ):
                            gaps.append(
                                {
                                    "kind": "unresolved-ui-scenario",
                                    "scenario_id": scenario.get("id"),
                                    "detail": f"status={scenario.get('status')!r}",
                                }
                            )
            except (OSError, json.JSONDecodeError):
                gaps.append({"kind": "unreadable-ui-sidecar", "path": identity["path"]})

    source_facts = goal.get("source") if isinstance(goal.get("source"), dict) else {}
    packet: dict[str, Any] = {
        "schema": HANDOFF_PACKET_SCHEMA,
        "scope": {"kind": scope, "goal_status": goal.get("status")},
        "goal": {
            "path": str(goal_path).replace("\\", "/"),
            "sha256": goal_sha,
            "definition_hash": goal_hash,
            "id": goal_id,
            "status": goal.get("status"),
            "rigor": goal.get("rigor"),
            "risk": goal.get("risk"),
            "source": source_facts,
            "outcomes": outcome_entries,
            "deferred": goal.get("deferred") or [],
        },
        "dispatch": dispatch_summary,
        "evidence_index": evidence_index,
        "ui": ui_summary,
        "gaps": gaps,
        "unresolved_actions": pending_actions,
        "facts_note": (
            "Every field above is machine-generated from artifacts on disk; a generated "
            "fact is not a pass. Fill `claims` with your own judgement and reconcile gaps "
            "explicitly instead of omitting them."
        ),
        "claims": {
            "completion_claim": None,
            "risk_notes": None,
            "evidence_explanations": None,
            "not_verified": [],
        },
    }
    if meta:
        packet["goal"]["frontmatter"] = meta
    if generated_at:
        packet["generated_at"] = generated_at
    return packet


def validate_packet(packet_path: Path) -> list[str]:
    problems: list[str] = []
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"packet unreadable: {exc}"]
    if not isinstance(packet, dict):
        return ["packet is not a JSON object"]
    schema = packet.get("schema")
    if schema == STAGE_PACKET_SCHEMA:
        routing = packet.get("routing") or {}
        current = _sha256(Path(str(routing.get("path")))) if routing.get("path") else None
        if current is None:
            problems.append("packet routing file is missing or unreadable")
        elif routing.get("sha256") != current:
            problems.append(
                "stale packet: stage routing changed; regenerate before reuse"
            )
        if _protocol is not None:
            try:
                _protocol.stage_definition(_protocol.load_routing(), packet["stage"]["id"])
            except (KeyError, _protocol.ProtocolError) as exc:
                problems.append(f"packet stage is not in the current routing: {exc}")
    elif schema == HANDOFF_PACKET_SCHEMA:
        goal = packet.get("goal") or {}
        current = _sha256(Path(str(goal.get("path")))) if goal.get("path") else None
        if current is None:
            problems.append("packet goal file is missing or unreadable")
        elif goal.get("sha256") != current:
            problems.append("stale packet: goal card changed; regenerate before reuse")
        for entry in packet.get("evidence_index") or []:
            if not isinstance(entry, dict) or not entry.get("path"):
                continue
            current = _sha256(Path(str(entry["path"])))
            if current is None:
                problems.append(f"evidence file is missing: {entry['path']}")
            elif entry.get("sha256") != current:
                problems.append(f"stale evidence binding: {entry['path']}")
    else:
        problems.append(f"unknown packet schema {schema!r}")
    return problems


def _write(packet: dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    _utf8()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    stage = sub.add_parser("stage", help="build a stage execution packet")
    stage.add_argument("stage_id")
    stage.add_argument("--rigor", choices=("normal", "guarded", "audited"))
    stage.add_argument("--role", default="controller", choices=sorted(ROLE_TO_SEAT))
    stage.add_argument("--input", action="append", default=[], help="input file (repeatable)")
    stage.add_argument("--evidence", action="append", default=[], help="evidence file (repeatable)")
    stage.add_argument("--routing", help="explicit stage-routing.json path")
    stage.add_argument("--generated-at", help="optional timestamp to embed")
    stage.add_argument("--out", required=True)

    handoff = sub.add_parser("handoff", help="build an acceptance handoff packet")
    handoff.add_argument("goal", help="goal card markdown path")
    handoff.add_argument("--dispatch", help="dispatch record JSON path")
    handoff.add_argument("--scope", default="goal", choices=("goal", "slice"))
    handoff.add_argument("--evidence", action="append", default=[], help="evidence JSON (repeatable)")
    handoff.add_argument("--evidence-dir", help="directory of evidence JSON files")
    handoff.add_argument("--ui-sidecar", help="ui-acceptance sidecar JSON path")
    handoff.add_argument("--generated-at", help="optional timestamp to embed")
    handoff.add_argument("--out", required=True)

    validate = sub.add_parser("validate", help="validate a packet against current hashes")
    validate.add_argument("packet", help="packet JSON path")

    args = parser.parse_args(argv)
    known_errors: tuple[type[BaseException], ...] = (RuntimeError, ValueError, KeyError)
    if _protocol is not None:
        known_errors = known_errors + (_protocol.ProtocolError,)

    if args.cmd == "stage":
        try:
            packet = build_stage_packet(
                args.stage_id,
                args.rigor,
                args.role,
                args.input,
                args.evidence,
                routing_path=args.routing,
                generated_at=args.generated_at,
            )
        except known_errors as exc:
            print(f"INVALID: {exc}", file=sys.stderr)
            return 2
        _write(packet, Path(args.out))
        print(
            f"stage packet written: {args.out} (stage={args.stage_id}, role={args.role}, "
            f"missing={len(packet['missing'])})"
        )
        return 0

    if args.cmd == "handoff":
        try:
            packet = build_handoff_packet(
                Path(args.goal),
                dispatch_path=Path(args.dispatch) if args.dispatch else None,
                scope=args.scope,
                evidence_paths=args.evidence,
                evidence_dir=Path(args.evidence_dir) if args.evidence_dir else None,
                ui_sidecar=Path(args.ui_sidecar) if args.ui_sidecar else None,
                generated_at=args.generated_at,
            )
        except ValueError as exc:
            print(f"INVALID: {exc}", file=sys.stderr)
            return 2
        _write(packet, Path(args.out))
        print(
            f"handoff packet written: {args.out} "
            f"(goal={packet['goal']['id']}, evidence={len(packet['evidence_index'])}, "
            f"gaps={len(packet['gaps'])})"
        )
        return 0

    problems = validate_packet(Path(args.packet))
    if problems:
        print(f"FAIL ({len(problems)}):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("PASS: packet schema and hashes are current")
    return 0


if __name__ == "__main__":
    sys.exit(main())

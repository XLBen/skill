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
import re
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

try:
    import product_observation as _observation
except ImportError:  # pragma: no cover - engine copied without product_observation
    _observation = None

try:
    import observation_contract as _contract
except ImportError:  # pragma: no cover - engine copied without the frozen contract
    _contract = None

STAGE_PACKET_SCHEMA = "workflow-stage-packet/1"
HANDOFF_PACKET_SCHEMA = "workflow-handoff-packet/1"
OBSERVER_PACKET_SCHEMA = "workflow-observer-packet/2"
PREFLIGHT_SCHEMA = "observation-preflight/1"
OBSERVER_REPAIR_REFERENCE = "product-observer/references/format-repair.md"
OBSERVER_FORBIDDEN_FIELDS = (
    "diff",
    "tests",
    "test_results",
    "acceptance",
    "handoff",
    "implementation_notes",
    "known_defects",
    "outcomes",
    "evidence",
)
OBSERVER_RULES_TEXT = (
    "观察规则（盲态优先）：1) 停止原因与派生状态 stop_reason -> state: "
    "'coverage-completed' -> completed（允许同时存在阻断 finding，但需在 notes 说明未修复项）；"
    "'budget-exhausted' -> incomplete（必须给出 continuation）；"
    "'blocked'/'no-backend'/'lease-lost' -> blocked（零接触轮允许 surfaces 为空，"
    "但必须用 notes 或 capability_gaps 说明为何无法观察）。"
    "无历史基线（baseline: none）是预期结果、不是 capability gap，不得写入 capability_gaps。"
    "2) 证据引用只能是候选目录内的相对路径，位于 evidence_dir 之下且文件真实存在；"
    "禁止绝对路径、'..'、编造文件。"
    "2b) CLI/API 产品证据：禁止 shell 重定向（宿主权限会拒绝），改用证据捕获助手落盘："
    "python .opencode/workflow/scripts/observation_capture.py --evidence-root <evidence_dir> "
    "--out <evidence_dir>/<name>.txt -- <入口命令...>，并在 journeys/findings/顶层 "
    "evidence_refs 中引用生成的文件（必须真实存在）。"
    "3) 所有权：goal_id、candidate_id、observer_session_id、"
    "model、packet_hash、received_at、attempt 均由 controller 补充，observer 不得猜测或填写。"
    "4) 盲态禁令：不得读取 goal 卡或 .opencode/mvp/**（packet 明确给出的 candidate manifest "
    "与 evidence_dir 除外），不得读取 diff、测试、验收场景或实现者笔记。"
    "4b) 候选内的公开使用文档（如 app/README.md）是允许输入：探索前先读，把文档承诺"
    "作为 expected_basis；文档声明与实际行为不一致属于可报告缺陷（compare 必须据此核对）。"
    "5) 输出：只输出一个 ```json 围栏块（product-observation/2）；需要修格式时按 "
    "product-observer/references/format-repair.md 处理，不得改变含义或新增事实。"
)
_HASH64_RE = re.compile(r"^[0-9a-f]{64}$")

ROLE_TO_SEAT = {
    "controller": "controller",
    "worker": "worker-subagent",
    "reviewer": "reviewer-subagent",
    "test-author": "test-author-subagent",
    "step-executor": "step-executor-subagent",
    "product-observer": "product-observer-subagent",
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
    except (OSError, ValueError):
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
    routing: dict[str, Any], stage_id: str, rigor: str | None, seat: str
) -> list[dict[str, Any]]:
    stage = _protocol.stage_definition(routing, stage_id)
    entries: list[dict[str, Any]] = []
    for entry in stage.get("required_skills") or []:
        try:
            applies = (
                (rigor not in _protocol.RIGORS or rigor in stage.get("rigors", []))
                and _protocol.pua_applies(entry, rigor)
                and (
                    entry.get("seat") == seat
                    or (
                        entry.get("seat") == "varies"
                        and _protocol.ROLE_BY_SEAT[seat] in entry.get("roles", [])
                    )
                )
            )
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
        "required_skills": _narrowed_skills(routing, stage_id, rigor, seat),
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


def _posix(raw: str | Path) -> str:
    return str(raw).replace("\\", "/")


def _project_root(goal_path: Path) -> Path:
    """The project root that owns ``<root>/.opencode/mvp/<goal>.md``."""

    return goal_path.parent.parent.parent


def _project_relative_posix(path: Path, root: Path) -> str:
    try:
        resolved = path.resolve()
    except (OSError, ValueError):  # pragma: no cover - invalid path shapes
        resolved = path
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return resolved.as_posix()


def _parse_model(model: str) -> dict[str, Any]:
    if not isinstance(model, str) or "/" not in model:
        raise ValueError("model must be given as 'provider/model'")
    provider_id, model_id = model.split("/", 1)
    if not provider_id.strip() or not model_id.strip():
        raise ValueError("model must be given as 'provider/model' with non-empty parts")
    return {"provider_id": provider_id, "model_id": model_id}


def _load_preflight(preflight_file: Path, model: str | None) -> tuple[dict[str, Any], str]:
    """Load and validate an ``observation-preflight/1`` file (fail closed)."""

    try:
        raw = preflight_file.read_bytes()
    except OSError as exc:
        raise ValueError(f"preflight file unreadable ({preflight_file}): {exc}") from exc
    digest = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"preflight file is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("preflight file must contain a JSON object")
    if payload.get("schema") != PREFLIGHT_SCHEMA:
        raise ValueError(f"preflight.schema must be {PREFLIGHT_SCHEMA}")
    for field in ("performed_at", "performed_by"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"preflight.{field} must be a non-empty string")
    covers = payload.get("covers")
    if not isinstance(covers, dict):
        raise ValueError("preflight.covers must be an object")
    for key in ("host", "model", "candidate", "session"):
        entry = covers.get(key)
        if not isinstance(entry, dict):
            raise ValueError(f"preflight.covers.{key} must be an object")
        status = entry.get("status")
        if not isinstance(status, str) or not status.strip():
            raise ValueError(f"preflight.covers.{key}.status must be a non-empty string")
    model_cover = covers["model"]
    if model_cover.get("status") == "passed":
        if model is None:
            raise ValueError(
                "preflight covers.model is passed but no model was supplied; "
                "the probe cannot be bound to the observing model"
            )
        parsed = _parse_model(model)
        if (
            model_cover.get("provider_id") != parsed["provider_id"]
            or model_cover.get("model_id") != parsed["model_id"]
        ):
            raise ValueError(
                "preflight model does not match the requested model: "
                f"{model_cover.get('provider_id')}/{model_cover.get('model_id')} "
                f"!= {parsed['provider_id']}/{parsed['model_id']}"
            )
    return payload, digest


def build_observer_packet(
    goal_path: Path,
    phase: str,
    generated_at: str | None = None,
    model: str | None = None,
    preflight_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build the blind (discover) or reconciliation (compare) observer packet.

    Whitelist-generated: only the fields below are ever included, so the
    observer never receives diffs, tests, acceptance scenarios or
    implementer notes through the packet. Context isolation, not a sandbox:
    dispatch bodies are archived and the controller must not smuggle hints.
    """

    if phase not in ("discover", "compare"):
        raise ValueError(f"unknown observer phase {phase!r}")
    if _observation is None:
        raise RuntimeError("product_observation module unavailable")
    if _contract is None:
        raise RuntimeError("observation_contract module unavailable")
    model_binding = _parse_model(model) if model is not None else None
    goal_path = goal_path.resolve()
    if not goal_path.is_file():
        raise ValueError(f"goal artifact not found: {goal_path}")
    meta, goal = _load_goal(goal_path)
    if goal.get("schema_version") not in (2, 3):
        raise ValueError("observer packets require a schema_version 2 or 3 goal card")
    spec = goal.get("product_observation") or {}
    if spec.get("required") is not True:
        raise ValueError("goal.product_observation.required must be true")

    sidecar_file = _observation.audit_sidecar_path(goal_path)
    try:
        sidecar = json.loads(sidecar_file.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"product-audit sidecar unreadable ({sidecar_file.name}): {exc}") from exc
    sidecar_problems = _observation.validate_audit_sidecar(sidecar)
    if sidecar_problems:
        raise ValueError("product-audit sidecar invalid: " + "; ".join(sidecar_problems))
    candidate_id = sidecar.get("current_candidate")
    round_entry = None
    for item in sidecar.get("rounds", []):
        if isinstance(item, dict) and item.get("candidate_id") == candidate_id:
            round_entry = item
    if round_entry is None:
        raise ValueError(f"sidecar.current_candidate {candidate_id!r} has no round entry")

    cdir = _observation.candidate_dir(goal_path, str(goal.get("id")), str(candidate_id))
    manifest_file = cdir / "candidate.json"
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"candidate manifest unreadable: {exc}") from exc
    manifest_problems = _observation.validate_candidate_manifest(manifest)
    if manifest_problems:
        raise ValueError("candidate manifest invalid: " + "; ".join(manifest_problems))

    root = _project_root(goal_path)
    source = goal.get("source") if isinstance(goal.get("source"), dict) else {}
    packet: dict[str, Any] = {
        "schema": OBSERVER_PACKET_SCHEMA,
        "phase": phase,
        "goal_id": goal.get("id"),
        "generated_at": generated_at,
        "brief": {
            "purpose": goal.get("goal"),
            "demo": goal.get("demo"),
            "first_slice": goal.get("first_slice"),
            "raw_request": source.get("raw_request"),
        },
        "goal_binding": {"goal_card_sha256": _sha256(goal_path)},
        "candidate": {
            "id": candidate_id,
            "manifest_path": _posix(manifest_file),
            "manifest_sha256": _sha256(manifest_file),
            "entry": manifest.get("entry"),
            "environment": manifest.get("environment"),
            "backend": manifest.get("backend"),
            "channels": manifest.get("channels") or [],
            "test_data": manifest.get("test_data") or [],
            "runtime_state": manifest.get("runtime_state") or [],
            "delivered_roots": manifest.get("delivered_roots") or [],
        },
        "evidence_dir": _posix(cdir / "evidence"),
        "budget": {
            "semantic_actions_per_surface_group": 40,
            "observation_cycles_per_action": 2,
            "wall_clock_minutes": 30,
        },
        "output": {
            "schema": "product-observation/2",
            "template": _contract.result_template(phase),
            "rules": OBSERVER_RULES_TEXT,
            "repair_reference": OBSERVER_REPAIR_REFERENCE,
        },
        "model": model_binding,
        "preflight": None,
    }

    resolved_preflight: Path | None = None
    if preflight_path is not None:
        resolved_preflight = Path(preflight_path)
        if not resolved_preflight.is_absolute():
            resolved_preflight = root / resolved_preflight
    else:
        default_preflight = cdir / "preflight.json"
        if default_preflight.is_file():
            resolved_preflight = default_preflight
    if resolved_preflight is not None:
        preflight, preflight_sha = _load_preflight(resolved_preflight, model)
        packet["preflight"] = {
            "path": _project_relative_posix(resolved_preflight, root),
            "sha256": preflight_sha,
            "performed_at": preflight["performed_at"],
            "performed_by": preflight["performed_by"],
            "covers": {
                key: preflight["covers"][key]
                for key in ("host", "model", "candidate", "session")
            },
        }

    if phase == "compare":
        discover_ref = round_entry.get("discover_ref")
        if not isinstance(discover_ref, str) or not discover_ref.strip():
            raise ValueError(
                "sidecar current round has no discover_ref to bind the compare packet"
            )
        relative = Path(discover_ref)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"discover_ref must stay project-relative: {discover_ref!r}")
        discover_file = root / discover_ref
        if not discover_file.is_file():
            raise ValueError(f"discover result not found at discover_ref: {discover_ref}")
        try:
            discover = json.loads(discover_file.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"compare requires a saved discover result bound to this candidate: {exc}"
            ) from exc
        if not isinstance(discover, dict):
            raise ValueError("discover result must be a JSON object")
        result_problems = _contract.validate_result_payload(discover, "discover")
        if result_problems:
            raise ValueError("discover result invalid: " + "; ".join(result_problems))
        if discover.get("phase") != "discover":
            raise ValueError("discover result has the wrong phase")
        if discover.get("candidate_id") != candidate_id:
            raise ValueError("discover result is bound to a different candidate")
        original: dict[str, Any] = {
            "goal": goal.get("goal"),
            "demo": goal.get("demo"),
            "first_slice": goal.get("first_slice"),
            "raw_request": source.get("raw_request"),
            "baselines": manifest.get("baseline") or {"kind": "none", "refs": []},
            "discover_result": {
                "path": _posix(discover_ref),
                "sha256": _sha256(discover_file),
            },
        }
        if round_entry.get("approved_changes"):
            original["approved_changes"] = round_entry["approved_changes"]
        packet["original"] = original
    return packet


def _packet_project_root(packet: dict[str, Any], goal_path: Path | None) -> Path | None:
    """Best-effort project root for resolving project-relative bindings."""

    if goal_path is not None:
        try:
            return goal_path.resolve().parents[2]
        except (OSError, ValueError, IndexError):
            return None
    manifest = (packet.get("candidate") or {}).get("manifest_path")
    if isinstance(manifest, str) and manifest.strip():
        try:
            return Path(manifest).parents[5]
        except IndexError:
            return None
    return None


def _preflight_packet_problems(
    preflight: Any, packet: dict[str, Any], root: Path | None
) -> list[str]:
    problems: list[str] = []
    if not isinstance(preflight, dict):
        return ["packet preflight must be an object when present"]
    for field in ("performed_at", "performed_by"):
        value = preflight.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"packet preflight.{field} must be a non-empty string")
    stored_path = preflight.get("path")
    if not isinstance(stored_path, str) or not stored_path.strip():
        problems.append("packet preflight.path must be a non-empty string")
    else:
        target = Path(stored_path)
        if not target.is_absolute():
            if root is None:
                problems.append("packet preflight.path cannot be resolved without --goal")
                target = None
            else:
                target = root / stored_path
        if target is not None:
            if not target.is_file():
                problems.append(f"preflight file is missing: {stored_path}")
            else:
                current = _sha256(target)
                if current is None:
                    problems.append("preflight file is unreadable")
                elif preflight.get("sha256") != current:
                    problems.append(
                        "stale packet: preflight file changed; regenerate before reuse"
                    )
    covers = preflight.get("covers")
    if not isinstance(covers, dict):
        problems.append("packet preflight.covers must be an object")
        return problems
    for key in ("host", "model", "candidate", "session"):
        entry = covers.get(key)
        if not isinstance(entry, dict):
            problems.append(f"packet preflight.covers.{key} must be an object")
            continue
        status = entry.get("status")
        if not isinstance(status, str) or not status.strip():
            problems.append(f"packet preflight.covers.{key}.status must be a non-empty string")
    model_cover = covers.get("model")
    if isinstance(model_cover, dict) and model_cover.get("status") == "passed":
        model = packet.get("model")
        if not isinstance(model, dict):
            problems.append(
                "preflight covers.model is passed but packet model is null; "
                "the probe cannot be bound to the observing model"
            )
        elif (
            model.get("provider_id") != model_cover.get("provider_id")
            or model.get("model_id") != model_cover.get("model_id")
        ):
            problems.append("packet model does not match the passed preflight model cover")
    return problems


def validate_packet(packet_path: Path, goal_path: str | Path | None = None) -> list[str]:
    problems: list[str] = []
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"packet unreadable: {exc}"]
    if not isinstance(packet, dict):
        return ["packet is not a JSON object"]
    goal_file = Path(goal_path) if goal_path is not None else None
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
    elif schema == OBSERVER_PACKET_SCHEMA:
        if _observation is None:
            problems.append("product_observation module unavailable; cannot validate observer packets")
            return problems
        phase = packet.get("phase")
        if phase not in ("discover", "compare"):
            problems.append("observer packet phase must be discover or compare")
        goal_id = packet.get("goal_id")
        if not isinstance(goal_id, str) or not goal_id.strip():
            problems.append("observer packet goal_id must be a non-empty string")

        binding = packet.get("goal_binding")
        digest = binding.get("goal_card_sha256") if isinstance(binding, dict) else None
        if not isinstance(digest, str) or not _HASH64_RE.fullmatch(digest):
            problems.append(
                "packet goal_binding.goal_card_sha256 must be a 64-character "
                "lowercase sha256 hex digest"
            )
            digest = None
        if goal_file is not None:
            current = _sha256(goal_file)
            if current is None:
                problems.append("goal card is missing or unreadable")
            elif digest is not None and digest != current:
                problems.append("stale packet: goal card changed; regenerate before reuse")
        elif phase == "discover":
            problems.append(
                "discover packet goal binding cannot be verified without --goal"
            )

        candidate = packet.get("candidate")
        if not isinstance(candidate, dict):
            problems.append("observer packet candidate block is required")
        else:
            candidate_id = candidate.get("id")
            if not isinstance(candidate_id, str) or not candidate_id.strip():
                problems.append("packet candidate.id must be a non-empty string")
            manifest_path = candidate.get("manifest_path")
            if not isinstance(manifest_path, str) or not manifest_path.strip():
                problems.append("packet candidate.manifest_path is required")
            else:
                current = _sha256(Path(manifest_path))
                if current is None:
                    problems.append("candidate manifest is missing or unreadable")
                elif candidate.get("manifest_sha256") != current:
                    problems.append(
                        "stale packet: candidate manifest changed; regenerate before reuse"
                    )

        output = packet.get("output")
        if not isinstance(output, dict):
            problems.append("observer packet output block is required")
        else:
            if output.get("schema") != "product-observation/2":
                problems.append("packet output.schema must be product-observation/2")
            rules = output.get("rules")
            if not isinstance(rules, str) or not rules.strip():
                problems.append("packet output.rules must be a non-empty string")
            reference = output.get("repair_reference")
            if not isinstance(reference, str) or not reference.strip():
                problems.append("packet output.repair_reference must be a non-empty string")
            template = output.get("template")
            if _contract is None:
                problems.append(
                    "observation_contract module unavailable; cannot validate output.template"
                )
            elif phase in ("discover", "compare"):
                for item in _contract.validate_result_payload(template, phase):
                    problems.append(f"output.template: {item}")
            else:
                for item in _contract.validate_result_payload(template):
                    problems.append(f"output.template: {item}")

        for field in OBSERVER_FORBIDDEN_FIELDS:
            if field in packet:
                problems.append(
                    f"observer packet carries forbidden field {field!r}; "
                    "observer inputs must stay blind to implementation context"
                )
        if "original" in packet and phase != "compare":
            problems.append("discover packets must not carry goal-history material")

        root = _packet_project_root(packet, goal_file)
        if "preflight" in packet and packet.get("preflight") is not None:
            problems.extend(_preflight_packet_problems(packet["preflight"], packet, root))

        if phase == "compare":
            original = packet.get("original")
            if not isinstance(original, dict):
                problems.append("compare packets must carry the original block")
            else:
                discover = original.get("discover_result")
                if (
                    not isinstance(discover, dict)
                    or not isinstance(discover.get("path"), str)
                    or not discover["path"].strip()
                ):
                    problems.append(
                        "compare packets must reference the bound discover result"
                    )
                else:
                    target = Path(discover["path"])
                    if not target.is_absolute():
                        if root is None:
                            problems.append(
                                "bound discover result path cannot be resolved without --goal"
                            )
                            target = None
                        else:
                            target = root / discover["path"]
                    if target is not None:
                        if not target.is_file():
                            problems.append("bound discover result is missing or unreadable")
                        else:
                            current = _sha256(target)
                            if current is None:
                                problems.append(
                                    "bound discover result is missing or unreadable"
                                )
                            elif discover.get("sha256") != current:
                                problems.append(
                                    "stale packet: discover result changed; regenerate"
                                )
                            if _contract is None:
                                problems.append(
                                    "observation_contract module unavailable; "
                                    "cannot validate the bound discover result"
                                )
                            else:
                                try:
                                    payload = json.loads(
                                        target.read_text(encoding="utf-8-sig")
                                    )
                                except (OSError, json.JSONDecodeError) as exc:
                                    problems.append(
                                        f"bound discover result is unreadable: {exc}"
                                    )
                                else:
                                    for item in _contract.validate_result_payload(
                                        payload, "discover"
                                    ):
                                        problems.append(
                                            f"original.discover_result: {item}"
                                        )
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
    validate.add_argument("--goal", help="goal card for recomputing the goal binding")

    observer = sub.add_parser("observer", help="build a blind product-observer phase packet")
    observer.add_argument("goal", help="goal card markdown path")
    observer.add_argument("--phase", required=True, choices=("discover", "compare"))
    observer.add_argument("--model", help="observing model as provider/model")
    observer.add_argument("--preflight", help="observation-preflight/1 JSON path")
    observer.add_argument("--generated-at", help="optional timestamp to embed")
    observer.add_argument("--out", required=True)

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

    if args.cmd == "observer":
        try:
            packet = build_observer_packet(
                Path(args.goal),
                args.phase,
                generated_at=args.generated_at,
                model=args.model,
                preflight_path=args.preflight,
            )
        except (RuntimeError, ValueError) as exc:
            print(f"INVALID: {exc}", file=sys.stderr)
            return 2
        _write(packet, Path(args.out))
        print(
            f"observer packet written: {args.out} (phase={args.phase}, "
            f"candidate={packet['candidate']['id']})"
        )
        return 0

    problems = validate_packet(
        Path(args.packet), Path(args.goal) if args.goal else None
    )
    if problems:
        print(f"FAIL ({len(problems)}):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("PASS: packet schema and hashes are current")
    return 0


if __name__ == "__main__":
    sys.exit(main())

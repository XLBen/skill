#!/usr/bin/env python3
"""Deterministic dispatch-state and next-action tooling.

The controller currently maintains `.opencode/mvp/<goal>.dispatch.json` by
hand: transcribing task records, provenance, action states and revisions in
model text. This tool moves the mechanical bookkeeping into deterministic
commands while keeping every judgement with the controller:

  - `next-action` reads the goal and dispatch record and reports the next
    mechanical obligation (unresolved action, awaiting task, circuit break,
    owner decision, state repair, or a coarse stage-entry suggestion). It never
    approves anything and never dispatches; it is an input to the controller.
  - `dispatch-begin` records a dispatch intent and archives the dispatch body
    atomically, with an optional `--expect-revision` CAS check.
  - `dispatch-result` archives the raw return and updates task status,
    provenance and acceptance from a result JSON, atomically.
  - `action-result` updates a CONTROLLER_ACTION from its `action_id`, with
    idempotent duplicate handling.

All writes are temp-file + atomic replace; a failed validation leaves the
original record untouched. These commands do not call the OpenCode task tool,
do not run engine gates, and never mark work accepted.

Python 3.10+, stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import runtime_trace as _trace
except ImportError:  # pragma: no cover - engine copied without runtime_trace
    _trace = None

KNOWN_TASK_STATUS = ("pending", "dispatched", "done", "failed", "skipped")
KNOWN_TASK_RESULT_STATUS = ("completed", "needs_input", "waiting_controller", "blocked", "failed")
KNOWN_ACTION_STATUS = ("requested", "running", "completed", "failed", "unknown")
KNOWN_ROLES = ("research", "worker", "reviewer", "test-author", "step-executor", "product-observer")
INDEPENDENCE_ROLES = ("reviewer", "test-author", "step-executor", "product-observer")
CIRCUIT_BREAK_THRESHOLD = 3


class RuntimeStateError(Exception):
    pass


def _utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def load_dispatch(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeStateError(f"dispatch record unreadable at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeStateError(f"dispatch record is not an object: {path}")
    if data.get("schema_version") not in (1, 2):
        raise RuntimeStateError(
            f"dispatch schema_version must be 1 or 2, got {data.get('schema_version')!r}"
        )
    if not isinstance(data.get("tasks"), list):
        raise RuntimeStateError("dispatch record has no tasks list")
    return data


def save_dispatch(path: Path, record: dict[str, Any]) -> None:
    """Atomic replace; the original file survives any earlier failure."""

    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


def _check_revision(record: dict[str, Any], expect: int | None) -> None:
    if expect is None:
        return
    current = int(record.get("revision", 0))
    if current != expect:
        raise RuntimeStateError(
            f"revision conflict: expected {expect}, record is at {current}"
        )


def _bump_revision(record: dict[str, Any]) -> None:
    record["revision"] = int(record.get("revision", 0)) + 1


def _task_by_id(record: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in record["tasks"]:
        if isinstance(task, dict) and task.get("task_id") == task_id:
            return task
    raise RuntimeStateError(f"task {task_id!r} is not in the dispatch record")


def _read_json(path: Path, what: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeStateError(f"{what} unreadable at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeStateError(f"{what} is not a JSON object: {path}")
    return data


def _archive_copy(
    source: Path, archive_dir: Path, goal_id: str, task_id: str, kind: str
) -> Path:
    """Copy a raw body into the immutable dispatch archive and return its path."""

    if not source.is_file():
        raise RuntimeStateError(f"archive source is missing: {source}")
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / f"{goal_id}-{task_id}-{kind}.json"
    target.write_bytes(source.read_bytes())
    return target


def begin_dispatch(
    dispatch_path: Path,
    task: dict[str, Any],
    archive_dir: Path | None = None,
    dispatch_body: Path | None = None,
    expect_revision: int | None = None,
    force_attempt: bool = False,
) -> dict[str, Any]:
    record = load_dispatch(dispatch_path)
    _check_revision(record, expect_revision)
    task_id = task.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise RuntimeStateError("task_id is required")
    role = task.get("role")
    if role not in KNOWN_ROLES:
        raise RuntimeStateError(f"unknown role {role!r}")
    existing = None
    for item in record["tasks"]:
        if isinstance(item, dict) and item.get("task_id") == task_id:
            existing = item
            break
    goal_id = str(record.get("goal_id") or "goal")
    archive_ref = task.get("dispatch_ref")
    if dispatch_body is not None:
        archive_dir = archive_dir or dispatch_path.parent / "dispatch-archive"
        archived = _archive_copy(dispatch_body, archive_dir, goal_id, task_id, "dispatch")
        archive_ref = str(archived).replace("\\", "/")
    if existing is None:
        entry = {
            "task_id": task_id,
            "role": role,
            "depends_on": task.get("depends_on") or [],
            "status": "dispatched",
            "attempt": int(task.get("attempt") or 1),
            "provenance": task.get("provenance") or {"session_id": None, "agent": None},
            "dispatch_ref": archive_ref,
            "result_ref": None,
            "artifact_baseline": task.get("artifact_baseline")
            or {"pre": task.get("baseline"), "post": None},
            "review_scope": task.get("review_scope"),
            "acceptance": {"verdict": None, "pending_actions": []},
            "actions": [],
            "rounds": int(task.get("rounds") or 0),
            "skip_reason": None,
        }
        if task.get("pua_stage_id"):
            entry["pua_stage_id"] = task["pua_stage_id"]
        record["tasks"].append(entry)
    else:
        previous = existing.get("status")
        if previous != "pending" and not force_attempt:
            raise RuntimeStateError(
                f"task {task_id} is already {previous!r}; "
                "use --force-attempt to record a new attempt"
            )
        if previous != "pending" and force_attempt:
            existing["attempt"] = int(existing.get("attempt") or 1) + 1
        existing["status"] = "dispatched"
        existing["role"] = role
        if archive_ref:
            existing["dispatch_ref"] = archive_ref
        if task.get("pua_stage_id"):
            existing["pua_stage_id"] = task["pua_stage_id"]
        if task.get("review_scope"):
            existing["review_scope"] = task["review_scope"]
        if task.get("depends_on") is not None:
            existing["depends_on"] = task["depends_on"]
    _bump_revision(record)
    save_dispatch(dispatch_path, record)
    return record


def record_dispatch_result(
    dispatch_path: Path,
    result: dict[str, Any],
    archive_dir: Path | None = None,
    result_body: Path | None = None,
    expect_revision: int | None = None,
) -> dict[str, Any]:
    record = load_dispatch(dispatch_path)
    _check_revision(record, expect_revision)
    task_id = result.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise RuntimeStateError("result.task_id is required")
    task = _task_by_id(record, task_id)
    result_status = result.get("result_status")
    if result_status not in KNOWN_TASK_RESULT_STATUS:
        raise RuntimeStateError(
            f"result_status must be one of {KNOWN_TASK_RESULT_STATUS}, got {result_status!r}"
        )
    provenance = result.get("provenance") or {}
    session_id = provenance.get("session_id")
    agent = provenance.get("agent")
    if result_status == "completed" and task.get("role") in INDEPENDENCE_ROLES:
        if not session_id or not agent:
            raise RuntimeStateError(
                f"completed {task.get('role')} dispatch needs runtime-recorded "
                "provenance.session_id and provenance.agent"
            )
    goal_id = str(record.get("goal_id") or "goal")
    result_ref = result.get("result_ref")
    if result_body is not None:
        archive_dir = archive_dir or dispatch_path.parent / "dispatch-archive"
        archived = _archive_copy(result_body, archive_dir, goal_id, task_id, "result")
        result_ref = str(archived).replace("\\", "/")
    if result_ref and not Path(str(result_ref)).is_file():
        raise RuntimeStateError(f"result_ref does not exist: {result_ref}")
    status_map = {
        "completed": "done",
        "needs_input": "dispatched",
        "waiting_controller": "dispatched",
        "blocked": "dispatched",
        "failed": "failed",
    }
    task["status"] = status_map[result_status]
    task["result_status"] = result_status
    task["provenance"] = {"session_id": session_id, "agent": agent}
    if result_ref:
        task["result_ref"] = result_ref
    if result.get("artifact_baseline"):
        task["artifact_baseline"] = result["artifact_baseline"]
    acceptance = task.setdefault("acceptance", {"verdict": None, "pending_actions": []})
    if result_status == "completed":
        acceptance["verdict"] = result.get("verdict")
        acceptance["pending_actions"] = result.get("pending_actions") or []
    else:
        acceptance["verdict"] = None
        acceptance["pending_actions"] = result.get("pending_actions") or []
    if result.get("skip_reason"):
        task["skip_reason"] = result["skip_reason"]
    if result.get("next_context"):
        task["next_context"] = result["next_context"]
    _bump_revision(record)
    save_dispatch(dispatch_path, record)
    return record


def record_action_result(
    dispatch_path: Path,
    update: dict[str, Any],
    expect_revision: int | None = None,
) -> dict[str, Any]:
    record = load_dispatch(dispatch_path)
    _check_revision(record, expect_revision)
    task_id = update.get("task_id")
    action_id = update.get("action_id")
    if not isinstance(task_id, str) or not task_id:
        raise RuntimeStateError("update.task_id is required")
    if not isinstance(action_id, str) or not action_id:
        raise RuntimeStateError("update.action_id is required")
    task = _task_by_id(record, task_id)
    actions = task.setdefault("actions", [])
    target = None
    for action in actions:
        if isinstance(action, dict) and action.get("action_id") == action_id:
            target = action
            break
    status = update.get("status")
    if status not in KNOWN_ACTION_STATUS:
        raise RuntimeStateError(
            f"action status must be one of {KNOWN_ACTION_STATUS}, got {status!r}"
        )
    evidence_ref = update.get("evidence_ref")
    if target is None:
        target = {
            "action_id": action_id,
            "kind": update.get("kind") or "run-command",
            "status": status,
            "evidence_ref": evidence_ref,
            "artifact_identity": update.get("artifact_identity"),
        }
        actions.append(target)
    else:
        if target.get("status") == status and (target.get("evidence_ref") or None) == (
            evidence_ref or None
        ):
            return record  # idempotent duplicate
        if target.get("status") == "completed" and status != "completed" and not update.get(
            "force"
        ):
            raise RuntimeStateError(
                f"action {action_id} is already completed; use force to change terminal state"
            )
        target["status"] = status
        if evidence_ref:
            target["evidence_ref"] = evidence_ref
    if status == "completed" and not target.get("evidence_ref"):
        raise RuntimeStateError(f"completed action {action_id} requires evidence_ref")
    _bump_revision(record)
    save_dispatch(dispatch_path, record)
    return record


def bind_test_author(
    manifest_path: Path,
    dispatch_path: Path,
    task_id: str,
    expect_revision: int | None = None,
) -> dict[str, Any]:
    """Bind the runtime-recorded test-author provenance into its manifest.

    The test-author seat writes `pending-binding` rows in one dispatch; after
    `dispatch-result` records the real session, this command replaces them with
    the runtime-recorded ID. Until binding, the manifest cannot authorize
    implementation."""

    record = load_dispatch(dispatch_path)
    _check_revision(record, expect_revision)
    task = _task_by_id(record, task_id)
    if task.get("role") != "test-author":
        raise RuntimeStateError(f"task {task_id} is not a test-author dispatch")
    provenance = task.get("provenance") or {}
    session_id = provenance.get("session_id")
    agent = provenance.get("agent")
    if not session_id:
        raise RuntimeStateError(
            "test-author provenance is not recorded; run dispatch-result first"
        )
    if not task.get("result_ref"):
        raise RuntimeStateError(
            "test-author result_ref is not recorded; reconcile the return first"
        )
    try:
        text = manifest_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise RuntimeStateError(f"manifest unreadable at {manifest_path}: {exc}") from exc
    id_row = re.compile(r"^\|\s*Test author ID\s*\|\s*(.*?)\s*\|\s*$", re.MULTILINE)
    status_row = re.compile(r"^\|\s*Provenance status\s*\|\s*(.*?)\s*\|\s*$", re.MULTILINE)
    id_match = id_row.search(text)
    status_match = status_row.search(text)
    if not id_match or not status_match:
        raise RuntimeStateError(
            "manifest must contain 'Test author ID' and 'Provenance status' table rows"
        )
    current_id = id_match.group(1).strip()
    current_status = status_match.group(1).strip()
    if current_status == "bound":
        if current_id.startswith(session_id):
            return record  # idempotent duplicate
        raise RuntimeStateError(
            f"manifest is already bound to {current_id!r}; refusing to rebind to {session_id!r}"
        )
    text = id_row.sub(f"| Test author ID | {session_id} ({agent or 'unknown-agent'}) |", text, count=1)
    text = status_row.sub("| Provenance status | bound |", text, count=1)
    tmp = manifest_path.with_name(manifest_path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, manifest_path)
    task["test_author_binding"] = {
        "manifest": str(manifest_path).replace("\\", "/"),
        "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "session_id": session_id,
        "agent": agent,
    }
    _bump_revision(record)
    save_dispatch(dispatch_path, record)
    return record


def next_action(record: dict[str, Any]) -> dict[str, Any]:
    """Coarse mechanical next-obligation inference; the controller decides."""

    blockers: list[dict[str, Any]] = []
    notes = [
        "coarse inference from the dispatch record; confirm the stage with a "
        "workflow-stage-packet before dispatching",
        "this tool never approves a result, owner decision or gate",
    ]
    action: dict[str, Any] = {"kind": "controller-decision", "details": {}}

    for counter in record.get("failure_counters") or []:
        if not isinstance(counter, dict):
            continue
        actual = counter.get("actual_failures")
        if isinstance(actual, int) and actual >= CIRCUIT_BREAK_THRESHOLD:
            return {
                "schema": "workflow-next-action/1",
                "goal_id": record.get("goal_id"),
                "action": {
                    "kind": "circuit-break",
                    "details": {
                        "target": counter.get("target"),
                        "signature": counter.get("signature"),
                        "actual_failures": actual,
                    },
                },
                "blocked_by": [{"kind": "circuit-break", **dict(counter)}],
                "notes": notes,
            }

    unresolved_actions = []
    for task in record.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        for entry in task.get("actions") or []:
            if isinstance(entry, dict) and entry.get("status") != "completed":
                unresolved_actions.append(
                    {
                        "task_id": task.get("task_id"),
                        "action_id": entry.get("action_id"),
                        "status": entry.get("status"),
                    }
                )
    if unresolved_actions:
        return {
            "schema": "workflow-next-action/1",
            "goal_id": record.get("goal_id"),
            "action": {"kind": "resolve-action", "details": {"actions": unresolved_actions}},
            "blocked_by": [{"kind": "unresolved-controller-action", **item} for item in unresolved_actions],
            "notes": notes,
        }

    owner_gates = []
    for task in record.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        acceptance = task.get("acceptance") or {}
        if acceptance.get("verdict") in ("owner", "blocked"):
            owner_gates.append(
                {
                    "task_id": task.get("task_id"),
                    "verdict": acceptance.get("verdict"),
                    "pending_actions": acceptance.get("pending_actions") or [],
                }
            )
    if owner_gates:
        return {
            "schema": "workflow-next-action/1",
            "goal_id": record.get("goal_id"),
            "action": {"kind": "owner-decision", "details": {"gates": owner_gates}},
            "blocked_by": [{"kind": "owner-gate", **item} for item in owner_gates],
            "notes": notes,
        }

    in_flight = []
    failed = []
    for task in record.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        status = task.get("status")
        if status in ("pending", "dispatched"):
            in_flight.append({"task_id": task.get("task_id"), "status": status})
        elif status == "failed":
            failed.append({"task_id": task.get("task_id")})
    if in_flight:
        return {
            "schema": "workflow-next-action/1",
            "goal_id": record.get("goal_id"),
            "action": {
                "kind": "await-task" if all(t["status"] == "dispatched" for t in in_flight) else "dispatch",
                "details": {"tasks": in_flight},
            },
            "blocked_by": [],
            "notes": notes,
        }
    if failed:
        return {
            "schema": "workflow-next-action/1",
            "goal_id": record.get("goal_id"),
            "action": {"kind": "rebuild-failed-task", "details": {"tasks": failed}},
            "blocked_by": [{"kind": "failed-dispatch", **item} for item in failed],
            "notes": notes,
        }

    active = record.get("active_slice") or {}
    if active.get("rigor") == "audited" and not active.get("package"):
        blockers.append({"kind": "missing-audited-package"})
    return {
        "schema": "workflow-next-action/1",
        "goal_id": record.get("goal_id"),
        "action": action,
        "blocked_by": blockers,
        "candidates": [
            "run the applicable engine gate for the current slice",
            "build a workflow-stage-packet for the next acceptance handoff",
            "run workflow_packets.py handoff before any whole-goal review",
        ],
        "notes": notes,
    }


def main(argv: list[str] | None = None) -> int:
    _utf8()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    na = sub.add_parser("next-action", help="report the next mechanical obligation")
    na.add_argument("dispatch", help="dispatch record JSON path")
    na.add_argument("--out", help="optional output path; default stdout")

    begin = sub.add_parser("dispatch-begin", help="record a dispatch intent")
    begin.add_argument("dispatch", help="dispatch record JSON path")
    begin.add_argument("--task", required=True, help="task intent JSON path")
    begin.add_argument("--body", help="dispatch body file to archive")
    begin.add_argument("--archive-dir", help="archive directory override")
    begin.add_argument("--expect-revision", type=int, default=None)
    begin.add_argument("--force-attempt", action="store_true")

    result = sub.add_parser("dispatch-result", help="record a dispatch return")
    result.add_argument("dispatch", help="dispatch record JSON path")
    result.add_argument("--result", required=True, help="result JSON path")
    result.add_argument("--body", help="raw return body file to archive")
    result.add_argument("--archive-dir", help="archive directory override")
    result.add_argument("--expect-revision", type=int, default=None)

    action = sub.add_parser("action-result", help="update a CONTROLLER_ACTION")
    action.add_argument("dispatch", help="dispatch record JSON path")
    action.add_argument("--update", required=True, help="action update JSON path")
    action.add_argument("--expect-revision", type=int, default=None)

    bind = sub.add_parser(
        "bind-test-author", help="bind runtime provenance into a test manifest"
    )
    bind.add_argument("manifest", help="test manifest markdown path")
    bind.add_argument("--dispatch", required=True, help="dispatch record JSON path")
    bind.add_argument("--task", required=True, help="test-author task id")
    bind.add_argument("--expect-revision", type=int, default=None)

    args = parser.parse_args(argv)
    try:
        if args.cmd == "next-action":
            record = load_dispatch(Path(args.dispatch))
            report = next_action(record)
            text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            if args.out:
                out = Path(args.out)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(text, encoding="utf-8")
                print(f"next action written: {args.out} (kind={report['action']['kind']})")
            else:
                print(text, end="")
            return 0
        if args.cmd == "dispatch-begin":
            task = _read_json(Path(args.task), "task intent")
            record = begin_dispatch(
                Path(args.dispatch),
                task,
                archive_dir=Path(args.archive_dir) if args.archive_dir else None,
                dispatch_body=Path(args.body) if args.body else None,
                expect_revision=args.expect_revision,
                force_attempt=args.force_attempt,
            )
            print(f"dispatch recorded: {task.get('task_id')} (revision={record.get('revision')})")
            return 0
        if args.cmd == "dispatch-result":
            payload = _read_json(Path(args.result), "result")
            record = record_dispatch_result(
                Path(args.dispatch),
                payload,
                archive_dir=Path(args.archive_dir) if args.archive_dir else None,
                result_body=Path(args.body) if args.body else None,
                expect_revision=args.expect_revision,
            )
            print(
                f"result recorded: {payload.get('task_id')} "
                f"(status={payload.get('result_status')}, revision={record.get('revision')})"
            )
            return 0
        if args.cmd == "action-result":
            update = _read_json(Path(args.update), "action update")
            record = record_action_result(
                Path(args.dispatch), update, expect_revision=args.expect_revision
            )
            print(
                f"action recorded: {update.get('task_id')}/{update.get('action_id')} "
                f"(status={update.get('status')}, revision={record.get('revision')})"
            )
            return 0
        if args.cmd == "bind-test-author":
            record = bind_test_author(
                Path(args.manifest),
                Path(args.dispatch),
                args.task,
                expect_revision=args.expect_revision,
            )
            task = _task_by_id(record, args.task)
            print(
                f"test author bound: {args.task} "
                f"(session={task.get('test_author_binding', {}).get('session_id')}, "
                f"revision={record.get('revision')})"
            )
            return 0
    except RuntimeStateError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())

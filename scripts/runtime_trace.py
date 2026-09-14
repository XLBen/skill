#!/usr/bin/env python3
"""Native runtime trace export and orchestration-chain validation.

`export` normalizes real OpenCode evidence (the local SQLite session store)
into a `runtime-trace/1` sidecar: sessions with parent links, completed/failed
skill tool parts, and task dispatches with their reported child sessions.

`validate` checks an orchestration claim (a dispatch record plus optional
runtime policy) against a trace. It is fail-closed:

  - a claimed dispatch whose child session is missing from the trace fails;
  - a role skill without a *completed* load in the right session fails;
  - reviewer/test-author/step-executor seats falling back to built-in agents
    fail (independence seats never fall back);
  - unresolved owner/blocked pending actions fail;
  - missing files, unknown schemas or malformed data fail, never pass.

Nothing here trusts prose: model self-reports, dispatch-record strings and
prompt text are not evidence; only native tool parts and session rows are.

Python 3.10+, stdlib only.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

TRACE_SCHEMA = "runtime-trace/1"
POLICY_SCHEMA = "runtime-policy/1"

ROLE_REQUIRED_SKILLS = {
    "worker": ["task-worker"],
    "reviewer": ["reviewer"],
    "test-author": ["test-author"],
    "step-executor": ["step-executor"],
}
PUA_REQUIRING_ROLES = {"reviewer"}  # reviewer executes its stage card itself
INDEPENDENCE_ROLES = {"reviewer", "test-author", "step-executor"}
FALLBACK_ALLOWED_ROLES = {"research", "worker"}
SKIP_WHITELIST = {"mechanical-batch", "capability-unavailable"}
TASK_CHILD_RE = re.compile(r'<task id="(ses_[A-Za-z0-9]+)"')


def _utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _ts(ms: int | None) -> str | None:
    if not ms:
        return None
    return _dt.datetime.fromtimestamp(ms / 1000).isoformat(timespec="seconds")


def _norm_dir(raw: str) -> str:
    return raw.replace("\\", "/").rstrip("/").lower()


# ---------------------------------------------------------------------------
# export


def open_db(explicit: str | None) -> tuple[sqlite3.Connection | None, str]:
    candidates = [Path(explicit)] if explicit else []
    if not explicit:
        base = None
        if sys.platform == "win32":
            base = Path.home() / "AppData" / "Local" / "opencode"
        cand_roots = [base] if base else []
        cand_roots.append(Path.home() / ".local" / "share" / "opencode")
        for root in cand_roots:
            candidates.append(root / "opencode.db")
    for cand in candidates:
        if not cand.is_file():
            continue
        try:
            con = sqlite3.connect(f"file:{cand.as_posix()}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            con.execute("select 1 from session limit 1").fetchone()
            return con, str(cand)
        except sqlite3.Error:
            continue
    return None, "no readable opencode session database found"


def export_trace(target: Path, db_arg: str | None, lookback_days: int | None) -> dict[str, Any]:
    target = target.resolve()
    con, db_note = open_db(db_arg)
    trace: dict[str, Any] = {
        "schema": TRACE_SCHEMA,
        "producer": {"tool": "runtime_trace.py export", "generated_at": _ts(int(_dt.datetime.now().timestamp() * 1000))},
        "project": {"directory": str(target)},
        "source": {"kind": "opencode-sqlite", "path": db_note},
        "sessions": [],
        "skill_events": [],
        "task_events": [],
    }
    if con is None:
        trace["export_error"] = db_note
        return trace
    cutoff = None
    if lookback_days is not None:
        cutoff = (_dt.datetime.now() - _dt.timedelta(days=lookback_days)).timestamp() * 1000

    want = _norm_dir(str(target))
    rows = con.execute(
        "select id, parent_id, directory, agent, time_created, time_updated from session"
    ).fetchall()
    matched = []
    for r in rows:
        if _norm_dir(r["directory"] or "") != want:
            continue
        if cutoff is not None and (r["time_created"] or 0) < cutoff:
            continue
        matched.append(r)
    sids = {r["id"] for r in matched}
    for r in rows:  # include children dispatched from matched sessions
        if r["parent_id"] in sids and r["id"] not in sids:
            sids.add(r["id"])
            matched.append(r)

    for r in matched:
        trace["sessions"].append(
            {
                "id": r["id"],
                "parent_id": r["parent_id"],
                "agent": r["agent"] or "(primary)",
                "created": _ts(r["time_created"]),
            }
        )

    q = ",".join("?" * len(sids)) if sids else "''"
    parts = con.execute(
        f"select session_id, time_created, data from part where session_id in ({q}) "
        "and json_extract(data,'$.type')='tool' and json_extract(data,'$.tool') in ('skill','task') "
        "order by time_created",
        list(sids),
    ).fetchall()
    for p in parts:
        data = json.loads(p["data"])
        state = data.get("state", {})
        if data.get("tool") == "skill":
            meta = data.get("metadata") or {}
            trace["skill_events"].append(
                {
                    "session_id": p["session_id"],
                    "skill": (state.get("input") or {}).get("name"),
                    "status": state.get("status"),
                    "source_dir": meta.get("dir"),
                    "time": _ts(p["time_created"]),
                }
            )
        else:
            out = state.get("output")
            child = None
            if isinstance(out, str):
                m = TASK_CHILD_RE.search(out)
                if m:
                    child = m.group(1)
            child_agent = None
            if child:
                crow = con.execute("select agent from session where id=?", (child,)).fetchone()
                child_agent = crow["agent"] if crow else None
            trace["task_events"].append(
                {
                    "controller_session": p["session_id"],
                    "requested_agent": (state.get("input") or {}).get("subagent_type"),
                    "status": state.get("status"),
                    "child_session": child,
                    "child_agent": child_agent,
                    "time": _ts(p["time_created"]),
                }
            )
    con.close()
    return trace


# ---------------------------------------------------------------------------
# validate


class TraceValidationError(Exception):
    pass


def _load_json(path: Path, what: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TraceValidationError(f"{what} unreadable at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise TraceValidationError(f"{what} is not a JSON object: {path}")
    return data


def load_trace(path: Path) -> dict[str, Any]:
    trace = _load_json(path, "trace")
    if trace.get("schema") != TRACE_SCHEMA:
        raise TraceValidationError(f"trace schema must be {TRACE_SCHEMA}: {path}")
    for key in ("sessions", "skill_events", "task_events"):
        if not isinstance(trace.get(key), list):
            raise TraceValidationError(f"trace missing list field '{key}'")
    return trace


def load_dispatch(path: Path) -> dict[str, Any]:
    data = _load_json(path, "dispatch record")
    version = data.get("schema_version")
    if version not in (1, 2):
        raise TraceValidationError(f"dispatch schema_version must be 1 or 2, got {version!r}")
    if not isinstance(data.get("tasks"), list):
        raise TraceValidationError("dispatch record has no tasks list")
    return data


def validate_chain(trace: dict[str, Any], dispatch: dict[str, Any], policy: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    sessions = {s["id"]: s for s in trace["sessions"] if isinstance(s, dict) and s.get("id")}
    skill_ok: dict[str, set[str]] = {}
    for ev in trace["skill_events"]:
        if ev.get("status") == "completed" and ev.get("skill") and ev.get("session_id"):
            skill_ok.setdefault(ev["session_id"], set()).add(ev["skill"])
    child_ids = {sid for sid, s in sessions.items() if s.get("parent_id")}

    implementer_sessions: set[str] = set()
    reviewer_sessions: set[str] = set()

    for task in dispatch["tasks"]:
        if not isinstance(task, dict):
            failures.append("dispatch task is not an object")
            continue
        tid = task.get("task_id", "?")
        role = task.get("role")
        status = task.get("status")
        prov = task.get("provenance") or {}
        claimed_session = prov.get("session_id")
        claimed_agent = prov.get("agent")

        if status in ("pending", "dispatched"):
            continue
        if status == "skipped":
            reason = task.get("skip_reason")
            if reason not in SKIP_WHITELIST:
                failures.append(f"task {tid}: skip_reason {reason!r} not in whitelist {sorted(SKIP_WHITELIST)}")
            if role in INDEPENDENCE_ROLES and reason == "capability-unavailable":
                if not (policy or {}).get("allow_independence_downgrade", False):
                    failures.append(f"task {tid}: independence seat {role} cannot be skipped without policy")
            continue
        if status != "done":
            continue
        if role == "research":
            pass  # read-only research: provenance recommended, chain not gating
        elif role in ROLE_REQUIRED_SKILLS:
            if not claimed_session:
                failures.append(f"task {tid}: done {role} dispatch has no provenance.session_id")
            elif claimed_session not in sessions:
                failures.append(f"task {tid}: claimed session {claimed_session} missing from trace")
            elif claimed_session not in child_ids:
                failures.append(
                    f"task {tid}: claimed session {claimed_session} has no parent (not a real child dispatch)"
                )
            else:
                real_agent = (sessions[claimed_session] or {}).get("agent")
                if claimed_agent and real_agent and claimed_agent != real_agent:
                    disclosed = str(claimed_agent) in str(real_agent) or str(real_agent) in str(claimed_agent)
                    if not disclosed:
                        failures.append(
                            f"task {tid}: provenance.agent {claimed_agent!r} != trace child agent {real_agent!r}"
                        )
                if role in INDEPENDENCE_ROLES and real_agent in ("general", "explore", "scout", None):
                    failures.append(
                        f"task {tid}: independence seat {role} ran as built-in agent {real_agent!r} (fallback forbidden)"
                    )
                if role not in INDEPENDENCE_ROLES and real_agent in ("general", "explore", "scout"):
                    if not (claimed_agent and str(real_agent) in str(claimed_agent)):
                        failures.append(
                            f"task {tid}: worker fallback to {real_agent!r} not disclosed in provenance.agent"
                        )
                required = list(ROLE_REQUIRED_SKILLS[role])
                if role in PUA_REQUIRING_ROLES:
                    required.append("pua")
                loaded = skill_ok.get(claimed_session, set())
                for skill in required:
                    if skill not in loaded:
                        failures.append(
                            f"task {tid}: role skill '{skill}' has no completed load in child session {claimed_session}"
                        )
                if role in ("worker", "step-executor"):
                    implementer_sessions.add(claimed_session)
                if role == "reviewer":
                    reviewer_sessions.add(claimed_session)

        acc = task.get("acceptance") or {}
        verdict = acc.get("verdict")
        if verdict in ("owner", "blocked") and acc.get("pending_actions"):
            failures.append(f"task {tid}: unresolved {verdict} pending actions {acc['pending_actions']}")

    for reviewer in reviewer_sessions:
        parent = (sessions.get(reviewer) or {}).get("parent_id")
        if reviewer in implementer_sessions:
            failures.append(f"reviewer session {reviewer} is also an implementer session")
        if parent and parent in implementer_sessions:
            failures.append(f"reviewer session {reviewer} parented by implementer session {parent}")

    if policy:
        for req in policy.get("requirements", []):
            if not isinstance(req, dict):
                failures.append("policy requirement is not an object")
                continue
            kind = req.get("kind")
            if kind == "skill-load":
                skill = req.get("skill")
                seat_sessions = (
                    [req["session_id"]] if req.get("session_id") else list(sessions)
                )
                if not any(skill in skill_ok.get(sid, set()) for sid in seat_sessions):
                    failures.append(f"policy: required skill '{skill}' has no completed load")
            elif kind == "task-dispatch":
                role = req.get("role")
                if not any(
                    t.get("role") == role and t.get("status") == "done"
                    for t in dispatch["tasks"]
                    if isinstance(t, dict)
                ):
                    failures.append(f"policy: no done dispatch for role '{role}'")
            elif kind == "review-satisfied-goal":
                ok = any(
                    isinstance(t, dict)
                    and t.get("role") == "reviewer"
                    and (t.get("acceptance") or {}).get("verdict") == "satisfied"
                    and (t.get("review_scope") in (None, "goal") or req.get("accept_any_scope"))
                    for t in dispatch["tasks"]
                )
                if not ok:
                    failures.append("policy: no satisfied goal-scope reviewer verdict for finish")
            elif kind == "independence":
                if reviewer_sessions & implementer_sessions:
                    failures.append("policy: reviewer/implementer independence violated")
            else:
                failures.append(f"policy: unknown requirement kind {kind!r}")
    return failures


def main(argv: list[str] | None = None) -> int:
    _utf8()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export", help="export a runtime trace from the opencode session store")
    ex.add_argument("target", help="target project directory")
    ex.add_argument("--db", help="explicit path to opencode session database")
    ex.add_argument("--lookback-days", type=int, default=None)
    ex.add_argument("--out", required=True, help="output trace JSON path")
    va = sub.add_parser("validate", help="validate a dispatch record against a trace (fail-closed)")
    va.add_argument("trace", help="trace JSON path")
    va.add_argument("--dispatch", required=True, help="dispatch record JSON path")
    va.add_argument("--policy", help="optional runtime policy JSON path")
    va.add_argument("--report", help="optional failure-report JSON output path")
    args = parser.parse_args(argv)

    if args.cmd == "export":
        trace = export_trace(Path(args.target), args.db, args.lookback_days)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        err = trace.get("export_error")
        if err:
            print(f"export failed: {err}", file=sys.stderr)
            return 2
        print(
            f"trace written: {out} "
            f"(sessions={len(trace['sessions'])}, skills={len(trace['skill_events'])}, tasks={len(trace['task_events'])})"
        )
        return 0

    try:
        trace = load_trace(Path(args.trace))
        dispatch = load_dispatch(Path(args.dispatch))
        policy = _load_json(Path(args.policy), "policy") if args.policy else None
        if policy is not None and policy.get("schema") != POLICY_SCHEMA:
            raise TraceValidationError(f"policy schema must be {POLICY_SCHEMA}")
    except TraceValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2
    failures = validate_chain(trace, dispatch, policy)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(
            json.dumps({"verdict": "pass" if not failures else "fail", "failures": failures}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
    if failures:
        print(f"FAIL ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: dispatch chain verified against native trace")
    return 0


if __name__ == "__main__":
    sys.exit(main())

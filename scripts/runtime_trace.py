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

# context-only tools excluded from the generic tool_events export; everything
# else (bash, edit, MCP/browser tools like desktop_*, playwright_*) is kept so
# UI acceptance native call references can be verified against the trace.
TOOL_EVENT_EXCLUDE = {"read", "grep", "glob", "list"}
TOOL_EVENT_CAP = 3000

ROLE_REQUIRED_SKILLS = {
    "worker": ["task-worker"],
    "reviewer": ["reviewer"],
    "test-author": ["test-author"],
    "step-executor": ["step-executor"],
    "product-observer": ["product-observer"],
}
INDEPENDENCE_ROLES = {"reviewer", "test-author", "step-executor", "product-observer"}
FALLBACK_ALLOWED_ROLES = {"research", "worker"}
KNOWN_TASK_ROLES = {"research", "worker", "reviewer", "test-author", "step-executor", "product-observer"}
KNOWN_TASK_STATUS = {"pending", "dispatched", "done", "failed", "skipped"}
KNOWN_TASK_RESULT_STATUS = {"completed", "needs_input", "waiting_controller", "blocked", "failed"}
KNOWN_ACTION_STATUS = {"requested", "running", "completed", "failed", "unknown"}
BUILTIN_AGENT_FALLBACKS = {"general", "explore", "scout"}
SKIP_WHITELIST = {"mechanical-batch", "capability-unavailable"}
TASK_CHILD_RE = re.compile(r'<task id="(ses_[A-Za-z0-9]+)"')

try:
    import workflow_protocol as _protocol
except ImportError as _exc:  # pragma: no cover - engine copied without the resolver
    _protocol = None
    _PROTOCOL_IMPORT_ERROR = str(_exc)
else:
    _PROTOCOL_IMPORT_ERROR = ""

_ROUTING_CACHE: dict[str, Any] | None = None


def _routing() -> dict[str, Any] | None:
    """Load the stage-routing authority, or None when it is unavailable.

    A missing routing table fails closed for guarded-or-audited PUA cards via
    the unknown-rigor rule, never by silently exempting a seat."""

    global _ROUTING_CACHE
    if _protocol is None:
        return None
    if _ROUTING_CACHE is None:
        try:
            _ROUTING_CACHE = _protocol.load_routing()
        except _protocol.ProtocolError:
            _ROUTING_CACHE = {}
    return _ROUTING_CACHE or None


def pua_required_for_role(role: str, rigor: str | None) -> bool:
    routing = _routing()
    if routing is None or _protocol is None:
        # No routing authority available: keep the previous fail-closed
        # minimum (independence reviewer seats load their stage card).
        return role in ("reviewer", "test-author", "step-executor")
    return _protocol.pua_required_for_role(routing, role, rigor)


def trace_provenance(trace: dict[str, Any]) -> str:
    """Return "native" only for a trace exported from the local session store.

    A hand-written or imported trace is structurally checkable but is not
    proof that the calls happened on this host; gates must not treat it as
    native provenance. The source path must still exist and carry the SQLite
    file header."""

    source = trace.get("source") or {}
    if source.get("kind") != "opencode-sqlite":
        return "unverified"
    raw_path = source.get("path")
    try:
        path = Path(raw_path) if raw_path else None
        if path is not None and path.is_file():
            with path.open("rb") as stream:
                if stream.read(16) == b"SQLite format 3\x00":
                    return "native"
    except OSError:
        pass
    return "unverified"


def _resolve_ref(ref: Any, base_dir: Path | None) -> Path:
    path = Path(str(ref))
    if not path.is_absolute() and base_dir is not None:
        path = Path(base_dir) / path
    return path


def _parse_session_model(value: Any) -> dict[str, Any] | None:
    """Normalize a stored session model into provider/model/variant fields.

    The session store keeps ``session.model`` as a JSON string such as
    ``{"id":"gpt-5.6-sol","providerID":"openai","variant":"high"}``; an
    already normalized mapping is accepted too. Anything that is not a JSON
    object carrying non-empty provider and model identifiers is unparsable
    (``None``). Mirrors ``observation_results.parse_session_model``."""

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if not isinstance(value, dict):
        return None
    provider = value.get("provider_id", value.get("providerID"))
    model = value.get("model_id", value.get("id"))
    if not isinstance(provider, str) or not provider.strip():
        return None
    if not isinstance(model, str) or not model.strip():
        return None
    variant = value.get("variant")
    if not isinstance(variant, str) or not variant.strip():
        variant = None
    return {"provider_id": provider, "model_id": model, "variant": variant}


def _session_model_column(con: sqlite3.Connection) -> str:
    """SQL expression for the session model column, null when absent."""

    columns = {row[1] for row in con.execute("pragma table_info(session)")}
    return "model" if "model" in columns else "null as model"


def verify_native_trace(trace: dict[str, Any]) -> list[str]:
    """Cross-check a trace's claims against the session store it names.

    Native provenance means the file at `source.path` is a readable SQLite
    session store whose rows actually support the trace: every session,
    skill load, task child and tool call referenced by the trace must exist in
    that store with matching parent/agent data. Fails closed."""

    provenance = trace_provenance(trace)
    if provenance != "native":
        return [
            "runtime trace has no verified native provenance (hand-written or imported "
            "evidence cannot pass the gate); re-export from the local session store"
        ]
    problems: list[str] = []
    db_path = Path(str(trace["source"]["path"]))
    try:
        con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        return [f"runtime trace source store is unreadable: {exc}"]
    try:
        model_expr = _session_model_column(con)
        for entry in trace.get("sessions", []) or []:
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            sid = entry["id"]
            row = con.execute(
                f"select parent_id, agent, {model_expr} from session where id=?", (sid,)
            ).fetchone()
            if row is None:
                problems.append(f"trace session {sid} is not present in the source store")
                continue
            if (entry.get("parent_id") or None) != (row["parent_id"] or None):
                problems.append(f"trace session {sid} parent does not match the source store")
            store_agent = row["agent"] or "(primary)"
            if entry.get("agent") and entry["agent"] != store_agent:
                problems.append(
                    f"trace session {sid} agent {entry['agent']!r} does not match the source store"
                )
            if "model" in entry:
                trace_model = _parse_session_model(entry.get("model"))
                store_model = _parse_session_model(row["model"])
                if entry.get("model") is not None and trace_model is None:
                    problems.append(
                        f"trace session {sid} model is not a parsable provider/model/variant object"
                    )
                elif trace_model is None and store_model is not None:
                    problems.append(
                        f"trace session {sid} records no model but the source store has one"
                    )
                elif trace_model is not None and store_model is None:
                    problems.append(
                        f"trace session {sid} model does not match the empty model in the source store"
                    )
                elif trace_model is not None and store_model is not None:
                    for key in ("provider_id", "model_id", "variant"):
                        if trace_model[key] != store_model[key]:
                            problems.append(
                                f"trace session {sid} model {key} {trace_model[key]!r} does not "
                                f"match the source store ({store_model[key]!r})"
                            )
        for ev in trace.get("skill_events", []) or []:
            sid, name = ev.get("session_id"), ev.get("skill")
            if not sid or not name:
                continue
            rows = con.execute(
                "select json_extract(data,'$.state.status') as status from part "
                "where session_id=? and json_extract(data,'$.tool')='skill' "
                "and json_extract(data,'$.state.input.name')=?",
                (sid, name),
            ).fetchall()
            statuses = [row["status"] for row in rows]
            claimed = ev.get("status")
            if not statuses:
                problems.append(f"skill load {name!r} in {sid} is not present in the source store")
            elif claimed == "completed" and "completed" not in statuses:
                problems.append(
                    f"skill load {name!r} in {sid} has no completed record in the source store"
                )
            elif claimed and claimed not in statuses:
                problems.append(
                    f"skill load {name!r} in {sid} status {claimed!r} does not match the source store"
                )
        for ev in trace.get("tool_events", []) or []:
            sid, call_id = ev.get("session_id"), ev.get("call_id")
            if not sid or not call_id:
                continue
            rows = con.execute(
                "select json_extract(data,'$.state.status') as status from part "
                "where session_id=? and json_extract(data,'$.callID')=?",
                (sid, call_id),
            ).fetchall()
            statuses = [row["status"] for row in rows]
            claimed = ev.get("status")
            if not statuses:
                problems.append(f"tool call {sid}:{call_id} is not present in the source store")
            elif claimed == "completed" and "completed" not in statuses:
                problems.append(
                    f"tool call {sid}:{call_id} has no completed record in the source store"
                )
            elif claimed and claimed not in statuses:
                problems.append(
                    f"tool call {sid}:{call_id} status {claimed!r} does not match the source store"
                )
        for ev in trace.get("task_events", []) or []:
            child = ev.get("child_session")
            if not child:
                continue
            row = con.execute("select parent_id, agent from session where id=?", (child,)).fetchone()
            if row is None:
                problems.append(f"task child session {child} is not present in the source store")
                continue
            if (ev.get("controller_session") or None) != (row["parent_id"] or None):
                problems.append(f"task child {child} parent does not match controller_session")
            if ev.get("child_agent") and (row["agent"] or None) != ev.get("child_agent"):
                problems.append(f"task child {child} agent does not match the source store")
            controller = ev.get("controller_session")
            if controller:
                controller_row = con.execute(
                    "select 1 from part where session_id=? and json_extract(data,'$.tool')='task' "
                    "and json_extract(data,'$.state.output') like ? limit 1",
                    (controller, f'%<task id="{child}"%'),
                ).fetchone()
                if controller_row is None:
                    problems.append(
                        f"task child {child} has no matching task call in controller session {controller}"
                    )
    except sqlite3.Error as exc:
        problems.append(f"runtime trace source store could not be verified: {exc}")
    finally:
        con.close()
    return problems


def reviewer_result_problems(
    task_id: str, task: dict[str, Any], base_dir: Path | None, declared_stage: str | None = None
) -> list[str]:
    """Verify that a claimed satisfied reviewer verdict is backed by the raw return."""

    problems: list[str] = []
    ref = task.get("result_ref")
    if not isinstance(ref, str) or not ref.strip():
        problems.append(f"task {task_id}: satisfied reviewer verdict requires result_ref to the raw return")
        return problems
    try:
        data = json.loads(_resolve_ref(ref, base_dir).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"task {task_id}: reviewer result_ref unreadable: {exc}")
        return problems
    if not isinstance(data, dict) or not data.get("mode") or not isinstance(data.get("issues"), list):
        problems.append(f"task {task_id}: reviewer result_ref is not a structured review payload")
        return problems
    envelope_status = data.get("status")
    if envelope_status is not None and envelope_status not in KNOWN_TASK_RESULT_STATUS:
        problems.append(
            f"task {task_id}: reviewer return has invalid envelope status {envelope_status!r}"
        )
    if data["issues"]:
        problems.append(
            f"task {task_id}: dispatch claims satisfied but the reviewer return has "
            f"{len(data['issues'])} issue(s)"
        )
    if not isinstance(data.get("checked_scope"), list) or not isinstance(data.get("not_checked"), list):
        problems.append(f"task {task_id}: reviewer return must declare checked_scope and not_checked")
    pua = data.get("pua_acceptance")
    if declared_stage:
        if not isinstance(pua, dict):
            problems.append(
                f"task {task_id}: dispatch declares pua_stage_id {declared_stage!r} but the "
                "reviewer return has no pua_acceptance"
            )
        elif pua.get("stage_id") != declared_stage:
            problems.append(
                f"task {task_id}: pua_acceptance stage_id {pua.get('stage_id')!r} does not match "
                f"the dispatch's pua_stage_id {declared_stage!r}"
            )
    if isinstance(pua, dict) and pua.get("result") not in (None, "satisfied"):
        problems.append(
            f"task {task_id}: dispatch claims satisfied but pua_acceptance result is {pua.get('result')!r}"
        )
    return problems


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
        "tool_events": [],
    }
    if con is None:
        trace["export_error"] = db_note
        trace["provenance"] = "unverified"
        return trace
    cutoff = None
    if lookback_days is not None:
        cutoff = (_dt.datetime.now() - _dt.timedelta(days=lookback_days)).timestamp() * 1000

    want = _norm_dir(str(target))
    model_expr = _session_model_column(con)
    rows = con.execute(
        f"select id, parent_id, directory, agent, {model_expr}, time_created, time_updated from session"
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
        raw_model = r["model"]
        trace["sessions"].append(
            {
                "id": r["id"],
                "parent_id": r["parent_id"],
                "agent": r["agent"] or "(primary)",
                "model": _parse_session_model(raw_model),
                "model_raw": raw_model,
                "created": _ts(r["time_created"]),
                "updated": _ts(r["time_updated"]),
            }
        )

    q = ",".join("?" * len(sids)) if sids else "''"
    parts = con.execute(
        f"select session_id, time_created, data from part where session_id in ({q}) "
        "and json_extract(data,'$.type')='tool' "
        "and json_extract(data,'$.tool') not in ('read','grep','glob','list') "
        "order by time_created desc limit ?",
        [*sids, TOOL_EVENT_CAP],
    ).fetchall()
    parts.reverse()  # restore chronological order after the desc limit
    if len(parts) >= TOOL_EVENT_CAP:
        trace["truncated"] = True
    for p in parts:
        data = json.loads(p["data"])
        state = data.get("state", {})
        state_time = state.get("time")
        timing = {}
        if isinstance(state_time, dict):
            if state_time.get("start"):
                timing["start"] = _ts(state_time.get("start"))
            if state_time.get("end"):
                timing["end"] = _ts(state_time.get("end"))
        if data.get("tool") == "skill":
            meta = data.get("metadata") or {}
            trace["skill_events"].append(
                {
                    "session_id": p["session_id"],
                    "skill": (state.get("input") or {}).get("name"),
                    "status": state.get("status"),
                    "source_dir": meta.get("dir"),
                    "time": _ts(p["time_created"]),
                    **timing,
                }
            )
        elif data.get("tool") == "task":
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
                    **timing,
                }
            )
        else:
            trace["tool_events"].append(
                {
                    "session_id": p["session_id"],
                    "call_id": data.get("callID"),
                    "tool": data.get("tool"),
                    "status": state.get("status"),
                    "time": _ts(p["time_created"]),
                    **timing,
                }
            )
    con.close()
    trace["provenance"] = trace_provenance(trace)
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
    if not isinstance(trace.get("tool_events"), list):
        trace["tool_events"] = []  # optional since runtime-trace/1; older exports lack it
    trace["provenance"] = trace_provenance(trace)
    return trace


def load_dispatch(path: Path) -> dict[str, Any]:
    data = _load_json(path, "dispatch record")
    version = data.get("schema_version")
    if version not in (1, 2):
        raise TraceValidationError(f"dispatch schema_version must be 1 or 2, got {version!r}")
    if not isinstance(data.get("tasks"), list):
        raise TraceValidationError("dispatch record has no tasks list")
    return data


def validate_chain(trace: dict[str, Any], dispatch: dict[str, Any], policy: dict[str, Any] | None,
                   base_dir: Path | None = None, rigor: str | None = None,
                   goal_rigor: str | None = None) -> list[str]:
    """Validate a dispatch claim against a native trace. Fail-closed.

    `rigor` is the active slice's rigor (falling back to the goal's when the
    dispatch record does not carry one); `goal_rigor` is the cumulative goal
    rigor used for downgrade policy. Every done dispatch must be linked to a
    real task tool event for its claimed child session, a satisfied reviewer
    verdict must be backed by the raw reviewer return, and only native traces
    can pass."""

    failures: list[str] = []
    if trace.get("truncated"):
        failures.append("runtime trace is truncated; narrow the export window and re-export")
    provenance = trace_provenance(trace)
    if provenance != "native":
        failures.append(
            "runtime trace has no verified native provenance (hand-written or imported "
            "evidence cannot pass the runtime gate); re-export from the local session store"
        )
    effective_goal_rigor = goal_rigor if goal_rigor is not None else rigor
    if (policy or {}).get("allow_independence_downgrade") and effective_goal_rigor == "audited":
        failures.append("policy: allow_independence_downgrade cannot apply to an audited goal")

    sessions = {s["id"]: s for s in trace["sessions"] if isinstance(s, dict) and s.get("id")}
    skill_ok: dict[str, set[str]] = {}
    for ev in trace["skill_events"]:
        if ev.get("status") == "completed" and ev.get("skill") and ev.get("session_id"):
            skill_ok.setdefault(ev["session_id"], set()).add(ev["skill"])
    child_ids = {sid for sid, s in sessions.items() if s.get("parent_id")}
    task_events = [ev for ev in trace.get("task_events", []) if isinstance(ev, dict)]

    implementer_sessions: set[str] = set()
    reviewer_sessions: set[str] = set()
    seen_task_ids: set[str] = set()

    for task in dispatch.get("tasks", []):
        if not isinstance(task, dict):
            failures.append("dispatch task is not an object")
            continue
        tid = task.get("task_id")
        if not isinstance(tid, str) or not tid:
            failures.append("dispatch task is missing a string task_id")
            continue
        if tid in seen_task_ids:
            failures.append(f"task {tid}: duplicate task_id in dispatch record")
        seen_task_ids.add(tid)
        role = task.get("role")
        if role not in KNOWN_TASK_ROLES:
            failures.append(f"task {tid}: unknown role {role!r}")
            continue
        status = task.get("status")
        if status not in KNOWN_TASK_STATUS:
            failures.append(f"task {tid}: invalid status {status!r}")
            continue
        actions = task.get("actions")
        if actions is not None:
            if not isinstance(actions, list):
                failures.append(f"task {tid}: actions must be a list")
            else:
                seen_actions: set[str] = set()
                for action in actions:
                    if not isinstance(action, dict):
                        failures.append(f"task {tid}: action entry is not an object")
                        continue
                    action_id = action.get("action_id")
                    if not isinstance(action_id, str) or not action_id:
                        failures.append(f"task {tid}: action entry missing string action_id")
                        continue
                    if action_id in seen_actions:
                        failures.append(f"task {tid}: duplicate action_id {action_id}")
                    seen_actions.add(action_id)
                    action_status = action.get("status")
                    if action_status not in KNOWN_ACTION_STATUS:
                        failures.append(
                            f"task {tid}: action {action_id} invalid status {action_status!r}"
                        )
                        continue
                    if action_status == "completed" and not action.get("evidence_ref"):
                        failures.append(
                            f"task {tid}: completed action {action_id} lacks evidence_ref"
                        )
                    if action_status in ("requested", "running", "failed", "unknown"):
                        failures.append(
                            f"task {tid}: action {action_id} is {action_status}; "
                            "resolve it before completion"
                        )
        prov = task.get("provenance") or {}
        claimed_session = prov.get("session_id")
        claimed_agent = prov.get("agent")
        acc = task.get("acceptance") or {}
        verdict = acc.get("verdict")
        if verdict == "satisfied" and status != "done":
            failures.append(
                f"task {tid}: acceptance verdict 'satisfied' is only valid on a done task "
                f"(status {status!r})"
            )

        if status in ("pending", "dispatched"):
            continue
        if status == "failed":
            failures.append(f"task {tid}: failed dispatch is not reusable state; rebuild it")
            continue
        if status == "skipped":
            reason = task.get("skip_reason")
            if reason not in SKIP_WHITELIST:
                failures.append(f"task {tid}: skip_reason {reason!r} not in whitelist {sorted(SKIP_WHITELIST)}")
            if role in INDEPENDENCE_ROLES and reason == "capability-unavailable":
                if not (policy or {}).get("allow_independence_downgrade", False):
                    failures.append(f"task {tid}: independence seat {role} cannot be skipped without policy")
            continue

        # status == done
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
                disclosed = (
                    claimed_agent is not None and real_agent is not None
                    and str(claimed_agent).startswith(str(real_agent))
                    and real_agent in BUILTIN_AGENT_FALLBACKS
                )
                if claimed_agent and real_agent and claimed_agent != real_agent and not disclosed:
                    failures.append(
                        f"task {tid}: provenance.agent {claimed_agent!r} != trace child agent {real_agent!r}"
                    )
                if role in INDEPENDENCE_ROLES and real_agent in BUILTIN_AGENT_FALLBACKS | {None}:
                    failures.append(
                        f"task {tid}: independence seat {role} ran as built-in agent {real_agent!r} (fallback forbidden)"
                    )
                if role not in INDEPENDENCE_ROLES and real_agent in BUILTIN_AGENT_FALLBACKS:
                    if not (claimed_agent and str(claimed_agent).startswith(str(real_agent))):
                        failures.append(
                            f"task {tid}: worker fallback to {real_agent!r} not disclosed in provenance.agent"
                        )
                linkage = [
                    ev for ev in task_events
                    if ev.get("child_session") == claimed_session
                ]
                if not linkage:
                    failures.append(
                        f"task {tid}: claimed child session {claimed_session} has no matching "
                        "task dispatch event in the trace"
                    )
                else:
                    if not any(ev.get("status") == "completed" for ev in linkage):
                        failures.append(
                            f"task {tid}: task dispatch event for {claimed_session} was not completed"
                        )
                    requested = {
                        str(ev.get("requested_agent")) for ev in linkage if ev.get("requested_agent")
                    }
                    if requested and not (
                        str(claimed_agent) in requested or str(real_agent) in requested
                    ):
                        fallback_disclosed = (
                            role in FALLBACK_ALLOWED_ROLES
                            and real_agent in BUILTIN_AGENT_FALLBACKS
                            and any(str(claimed_agent).startswith(name) for name in requested)
                        )
                        if not fallback_disclosed:
                            failures.append(
                                f"task {tid}: requested agent {sorted(requested)} does not match "
                                f"provenance.agent {claimed_agent!r}"
                            )
                required = list(ROLE_REQUIRED_SKILLS[role])
                declared_stage = task.get("pua_stage_id")
                if not isinstance(declared_stage, str) or not declared_stage.strip():
                    declared_stage = None
                if pua_required_for_role(role, rigor):
                    required.append("pua")
                elif declared_stage and "pua" not in required:
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
        if role == "reviewer" and status == "done" and verdict == "satisfied":
            failures.extend(reviewer_result_problems(tid, task, base_dir, declared_stage))

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
                    and t.get("status") == "done"
                    and (t.get("acceptance") or {}).get("verdict") == "satisfied"
                    and (t.get("review_scope") in (None, "goal") or req.get("accept_any_scope"))
                    for t in dispatch["tasks"]
                )
                if not ok:
                    failures.append("policy: no satisfied goal-scope reviewer verdict for finish")
            elif kind == "native-tool-calls":
                refs = req.get("refs") or []
                if not isinstance(refs, list) or not refs:
                    failures.append("policy: native-tool-calls requires a nonempty refs list")
                    continue
                completed = {
                    f"{ev.get('session_id')}:{ev.get('call_id')}"
                    for ev in trace.get("tool_events", [])
                    if ev.get("status") == "completed" and ev.get("session_id") and ev.get("call_id")
                }
                for ref in refs:
                    if ref not in completed:
                        failures.append(f"policy: native tool call '{ref}' not found as completed in trace")
            elif kind == "ui-acceptance":
                pass  # enforced by check.py ui-gate against the ui-acceptance sidecar, not by chain validation
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
    slice_rigor = (dispatch.get("active_slice") or {}).get("rigor")
    if slice_rigor not in ("normal", "guarded", "audited"):
        slice_rigor = None
    failures = verify_native_trace(trace) + validate_chain(
        trace, dispatch, policy, rigor=slice_rigor
    )
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

#!/usr/bin/env python3
"""Workflow performance metrics export and comparison.

`export` reads the local OpenCode SQLite session store and writes a
`workflow-metrics/1` JSON report: sessions with models, token and cost totals,
message turns, tool durations, active/elapsed wall-clock, a coarse
critical-path view and duplicate-command candidates.

`compare` diffs two metrics reports so before/after optimization claims can be
checked on the same task and model.

This report is **diagnostic only**. It is never consulted by `check.py`,
`runtime_trace.py validate` or any finish gate; a missing database, missing
token columns or interrupted sessions still produce an honest partial report
with explicit `availability` flags. Absence of data is reported as
`unavailable`, never inferred or silently zero-filled.

Timing model:
  - tool durations come from `state.time.start/end` on tool parts (falling
    back to the part row timestamps);
  - message and tool intervals are merged (union) across sessions before
    summing, so parallel seats do not double-count wall-clock;
  - `span_seconds` is wall-clock from first observed activity to last.

Python 3.10+, stdlib only.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

METRICS_SCHEMA = "workflow-metrics/1"
COMPARE_SCHEMA = "workflow-metrics-compare/1"

TOOL_CAP = 20000
DUPLICATE_LIMIT = 50
_COMMAND_PREVIEW = 160
_WS_RE = re.compile(r"\s+")

_FULL_SESSION_SELECT = (
    "select id, parent_id, directory, agent, model, cost, "
    "tokens_input, tokens_output, tokens_reasoning, "
    "tokens_cache_read, tokens_cache_write, "
    "time_created, time_updated from session"
)


def _utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _ts(ms: Any) -> str | None:
    if not isinstance(ms, (int, float)) or ms <= 0:
        return None
    try:
        return _dt.datetime.fromtimestamp(ms / 1000).isoformat(timespec="seconds")
    except (OverflowError, OSError, ValueError):
        return None


def _norm_dir(raw: Any) -> str:
    return str(raw or "").replace("\\", "/").rstrip("/").lower()


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    try:
        keys = row.keys()
    except AttributeError:
        return default
    return row[key] if key in keys else default


def _json_or_none(text: Any) -> Any:
    if not isinstance(text, str):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def parse_model(raw: Any) -> dict[str, Any] | None:
    """Normalize a session.model value: JSON object, plain string, or None."""

    if raw is None:
        return None
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        parsed = _json_or_none(raw)
        if isinstance(parsed, dict):
            data = parsed
        elif raw.strip():
            return {"id": raw.strip(), "provider": None, "variant": None}
        else:
            return None
    else:
        return None
    model_id = data.get("id") or data.get("modelID") or data.get("model")
    provider = data.get("providerID") or data.get("provider")
    variant = data.get("variant")
    if not model_id and not provider:
        return None
    return {
        "id": str(model_id) if model_id else None,
        "provider": str(provider) if provider else None,
        "variant": str(variant) if variant else None,
    }


def model_key(model: dict[str, Any] | None) -> str | None:
    if not model or not model.get("id"):
        return None
    if model.get("provider"):
        return f"{model['provider']}/{model['id']}"
    return str(model["id"])


def merge_intervals(intervals: list[tuple[int, int]]) -> tuple[int, list[tuple[int, int]]]:
    """Union overlapping/adjacent (start_ms, end_ms) intervals.

    Returns (total_ms, merged). Parallel seats produce overlapping intervals;
    summing them would double-count wall-clock, so the union is the only
    honest total."""

    valid = sorted(
        (int(start), int(end))
        for start, end in intervals
        if isinstance(start, (int, float))
        and isinstance(end, (int, float))
        and end >= start
    )
    if not valid:
        return 0, []
    merged: list[list[int]] = [list(valid[0])]
    for start, end in valid[1:]:
        if start <= merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1][1] = end
        else:
            merged.append([start, end])
    total = sum(end - start for start, end in merged)
    return total, [(start, end) for start, end in merged]


def _positive(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Keep only intervals with a positive duration.

    A zero-length interval (start == end) is an activity instant, not elapsed
    time; treating it as elapsed would suppress an honest fallback to session
    span and report 0s for a session that clearly ran."""

    return [
        (int(start), int(end))
        for start, end in intervals
        if isinstance(start, (int, float))
        and isinstance(end, (int, float))
        and end > start
    ]


def normalize_command(command: str) -> str:
    return _WS_RE.sub(" ", command).strip()


def command_digest(command: str) -> str:
    return hashlib.sha256(command.encode("utf-8")).hexdigest()[:16]


def open_db(explicit: str | None) -> tuple[sqlite3.Connection | None, str]:
    """Open the local session store read-only. Never writes to the database."""

    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    else:
        if sys.platform == "win32":
            base = Path.home() / "AppData" / "Local" / "opencode"
            candidates.append(base / "opencode.db")
        candidates.append(Path.home() / ".local" / "share" / "opencode" / "opencode.db")
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


def _fetch_sessions(con: sqlite3.Connection) -> tuple[list[Any], bool]:
    try:
        return con.execute(_FULL_SESSION_SELECT).fetchall(), True
    except sqlite3.Error:
        rows = con.execute(
            "select id, parent_id, directory, agent, time_created, time_updated from session"
        ).fetchall()
        return rows, False


def _match_sessions(rows: list[Any], target_dir: str, cutoff: float | None) -> list[Any]:
    matched: list[Any] = []
    for row in rows:
        if _norm_dir(_row_get(row, "directory")) != target_dir:
            continue
        created = _row_get(row, "time_created") or 0
        if cutoff is not None and created < cutoff:
            continue
        matched.append(row)
    ids = {_row_get(row, "id") for row in matched}
    for row in rows:  # include children dispatched from matched sessions
        parent = _row_get(row, "parent_id")
        if parent in ids and _row_get(row, "id") not in ids:
            ids.add(_row_get(row, "id"))
            matched.append(row)
    return matched


def _extract_tool(part_data: dict[str, Any], row: Any) -> dict[str, Any] | None:
    if not isinstance(part_data, dict) or part_data.get("type") != "tool":
        return None
    state = part_data.get("state")
    if not isinstance(state, dict):
        state = {}
    timing = state.get("time")
    state_start = state_end = None
    if isinstance(timing, dict):
        state_start = timing.get("start")
        state_end = timing.get("end")
    has_state_time = isinstance(state_start, (int, float)) and isinstance(state_end, (int, float))
    start = state_start if isinstance(state_start, (int, float)) else _row_get(row, "time_created")
    end = state_end if isinstance(state_end, (int, float)) else _row_get(row, "time_updated")
    has_time = isinstance(start, (int, float)) and isinstance(end, (int, float))
    time_source = "state" if has_state_time else ("row" if has_time else None)
    tool_input = state.get("input")
    command = None
    if isinstance(tool_input, dict):
        candidate = tool_input.get("command")
        if isinstance(candidate, str) and candidate.strip():
            command = normalize_command(candidate)
    return {
        "tool": part_data.get("tool") or "(unknown)",
        "status": state.get("status"),
        "call_id": part_data.get("callID"),
        "start": start if isinstance(start, (int, float)) else None,
        "end": end if isinstance(end, (int, float)) else None,
        "has_time": has_time,
        "time_source": time_source,
        "command": command,
    }


def export_metrics(target: Path, db_arg: str | None, lookback_days: int | None) -> dict[str, Any]:
    target = target.resolve()
    con, db_note = open_db(db_arg)
    report: dict[str, Any] = {
        "schema": METRICS_SCHEMA,
        "producer": {
            "tool": "workflow_metrics.py export",
            "generated_at": _ts(int(_dt.datetime.now().timestamp() * 1000)),
        },
        "project": {"directory": str(target)},
        "source": {"kind": "opencode-sqlite", "path": db_note},
        "window": {"lookback_days": lookback_days, "cutoff": None},
        "availability": {},
        "notes": [],
        "totals": {},
        "models": {},
        "sessions": [],
        "tools": [],
        "duplicate_command_candidates": [],
    }
    if con is None:
        report["export_error"] = db_note
        report["availability"] = {"database": False}
        report["notes"].append(
            "session database unavailable; the metrics report is empty. "
            "Metrics are diagnostic and never gate delivery."
        )
        return report

    try:
        return _export_from_connection(con, target, lookback_days, report)
    except sqlite3.Error as exc:
        report["export_error"] = f"session store query failed: {exc}"
        report["availability"] = {"database": True, "queries": False}
        report["notes"].append(
            "session store could not be fully read; partial metrics only. "
            "Metrics are diagnostic and never gate delivery."
        )
        return report
    finally:
        con.close()


def _export_from_connection(
    con: sqlite3.Connection,
    target: Path,
    lookback_days: int | None,
    report: dict[str, Any],
) -> dict[str, Any]:
    cutoff = None
    if lookback_days is not None:
        cutoff = (_dt.datetime.now() - _dt.timedelta(days=lookback_days)).timestamp() * 1000
        report["window"]["cutoff"] = _ts(cutoff)

    all_rows, full_columns = _fetch_sessions(con)
    matched = _match_sessions(all_rows, _norm_dir(str(target)), cutoff)
    sids = [str(_row_get(row, "id")) for row in matched if _row_get(row, "id")]

    availability: dict[str, Any] = {
        "database": True,
        "session_columns": full_columns,
        "models": False,
        "message_tokens": False,
        "message_times": False,
        "tool_times": False,
        "costs": False,
    }

    session_intervals: list[tuple[int, int]] = []
    session_entries: list[dict[str, Any]] = []
    for row in matched:
        created = _row_get(row, "time_created")
        updated = _row_get(row, "time_updated")
        model = parse_model(_row_get(row, "model"))
        if model:
            availability["models"] = True
        cost = _row_get(row, "cost")
        if isinstance(cost, (int, float)):
            availability["costs"] = True
        tokens = None
        if full_columns:
            tokens = {
                "input": _row_get(row, "tokens_input") or 0,
                "output": _row_get(row, "tokens_output") or 0,
                "reasoning": _row_get(row, "tokens_reasoning") or 0,
                "cache_read": _row_get(row, "tokens_cache_read") or 0,
                "cache_write": _row_get(row, "tokens_cache_write") or 0,
            }
        if isinstance(created, (int, float)) and isinstance(updated, (int, float)) and updated >= created:
            session_intervals.append((created, updated))
        session_entries.append(
            {
                "id": _row_get(row, "id"),
                "parent_id": _row_get(row, "parent_id"),
                "agent": _row_get(row, "agent") or "(primary)",
                "model": model,
                "created": _ts(created),
                "updated": _ts(updated),
                "duration_seconds": (
                    round((updated - created) / 1000, 3)
                    if isinstance(created, (int, float)) and isinstance(updated, (int, float))
                    else None
                ),
                "tokens": tokens,
                "cost": round(float(cost), 6) if isinstance(cost, (int, float)) else None,
                "interrupted": True,  # cleared when a completed message is seen
                "active_seconds": None,
                "span_seconds": None,
            }
        )
    by_id = {entry["id"]: entry for entry in session_entries}

    q = ",".join("?" * len(sids)) if sids else "''"
    messages = con.execute(
        f"select session_id, time_created, time_updated, data from message "
        f"where session_id in ({q}) order by time_created",
        sids,
    ).fetchall()

    session_message_intervals: dict[str, list[tuple[int, int]]] = {}
    session_tokens: dict[str, dict[str, int]] = {}
    session_costs: dict[str, float] = {}
    models: dict[str, dict[str, Any]] = {}
    total_turns = 0
    total_errors = 0
    for msg in messages:
        sid = _row_get(msg, "session_id")
        data = _json_or_none(_row_get(msg, "data"))
        if not isinstance(data, dict):
            continue
        role = data.get("role")
        time_block = data.get("time") or {}
        created = time_block.get("created") if isinstance(time_block, dict) else None
        completed = time_block.get("completed") if isinstance(time_block, dict) else None
        model = parse_model(
            {
                "id": data.get("modelID"),
                "providerID": data.get("providerID"),
            }
        )
        tokens = data.get("tokens") if isinstance(data.get("tokens"), dict) else None
        cost = data.get("cost")
        entry = by_id.get(sid)
        if role == "assistant":
            total_turns += 1
            if entry is not None and isinstance(completed, (int, float)):
                entry["interrupted"] = False
            if isinstance(created, (int, float)) and isinstance(completed, (int, float)) and completed >= created:
                availability["message_times"] = True
                session_message_intervals.setdefault(sid, []).append((created, completed))
            if tokens:
                availability["message_tokens"] = True
                bucket = session_tokens.setdefault(
                    sid, {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
                )
                bucket["input"] += int(tokens.get("input") or 0)
                bucket["output"] += int(tokens.get("output") or 0)
                bucket["reasoning"] += int(tokens.get("reasoning") or 0)
                cache = tokens.get("cache")
                if isinstance(cache, dict):
                    bucket["cache_read"] += int(cache.get("read") or 0)
                    bucket["cache_write"] += int(cache.get("write") or 0)
            if isinstance(cost, (int, float)):
                availability["costs"] = True
                session_costs[sid] = session_costs.get(sid, 0.0) + float(cost)
            key = model_key(model)
            if key:
                availability["models"] = True
                bucket = models.setdefault(
                    key,
                    {
                        "provider": model.get("provider"),
                        "model": model.get("id"),
                        "variant": model.get("variant"),
                        "turns": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "reasoning_tokens": 0,
                        "cache_read": 0,
                        "cache_write": 0,
                        "cost": 0.0,
                    },
                )
                bucket["turns"] += 1
                if tokens:
                    bucket["input_tokens"] += int(tokens.get("input") or 0)
                    bucket["output_tokens"] += int(tokens.get("output") or 0)
                    bucket["reasoning_tokens"] += int(tokens.get("reasoning") or 0)
                    cache = tokens.get("cache")
                    if isinstance(cache, dict):
                        bucket["cache_read"] += int(cache.get("read") or 0)
                        bucket["cache_write"] += int(cache.get("write") or 0)
                if isinstance(cost, (int, float)):
                    bucket["cost"] += float(cost)
        if data.get("error"):
            total_errors += 1

    for sid, bucket in session_tokens.items():
        entry = by_id.get(sid)
        if entry is not None:
            entry["tokens"] = bucket
    for sid, total in session_costs.items():
        entry = by_id.get(sid)
        if entry is not None:
            entry["cost"] = round(total, 6)

    parts = con.execute(
        f"select session_id, time_created, time_updated, data from part "
        f"where session_id in ({q}) and json_extract(data,'$.type')='tool'",
        sids,
    ).fetchall()
    truncated = len(parts) >= TOOL_CAP
    if truncated:
        parts = parts[:TOOL_CAP]
    report["truncated"] = truncated
    if truncated:
        report["notes"].append(
            f"tool parts truncated at {TOOL_CAP}; tool totals and duplicate-command "
            "candidates are a lower bound"
        )

    tool_buckets: dict[tuple[str, str], dict[str, Any]] = {}
    command_runs: dict[str, dict[str, Any]] = {}
    task_dispatches = 0
    total_tool_calls = 0
    estimated_tool_times = 0
    tool_intervals_by_session: dict[str, list[tuple[int, int]]] = {}
    for part in parts:
        data = _json_or_none(_row_get(part, "data"))
        extracted = _extract_tool(data, part) if isinstance(data, dict) else None
        if extracted is None:
            continue
        sid = str(_row_get(part, "session_id"))
        total_tool_calls += 1
        if extracted["tool"] == "task":
            task_dispatches += 1
        if extracted["time_source"] == "state":
            availability["tool_times"] = True
        elif extracted["time_source"] == "row":
            estimated_tool_times += 1
        if extracted["has_time"]:
            tool_intervals_by_session.setdefault(sid, []).append(
                (int(extracted["start"]), int(extracted["end"]))
            )
        key = (sid, extracted["tool"])
        bucket = tool_buckets.setdefault(
            key,
            {
                "session_id": sid,
                "tool": extracted["tool"],
                "count": 0,
                "statuses": {},
                "duration_sum_seconds": 0.0,
                "duration_max_seconds": 0.0,
                "missing_time": 0,
            },
        )
        bucket["count"] += 1
        status = extracted["status"] or "unknown"
        bucket["statuses"][status] = bucket["statuses"].get(status, 0) + 1
        if extracted["has_time"]:
            seconds = max(0.0, (int(extracted["end"]) - int(extracted["start"])) / 1000)
            bucket["duration_sum_seconds"] += seconds
            bucket["duration_max_seconds"] = max(bucket["duration_max_seconds"], seconds)
        else:
            bucket["missing_time"] += 1
        if extracted["command"]:
            norm = extracted["command"]
            run = command_runs.setdefault(
                norm,
                {
                    "command": norm,
                    "digest": command_digest(norm),
                    "runs": 0,
                    "sessions": set(),
                    "call_ids": [],
                },
            )
            run["runs"] += 1
            run["sessions"].add(sid)
            if extracted["call_id"]:
                run["call_ids"].append(extracted["call_id"])

    tools = []
    for bucket in tool_buckets.values():
        bucket["duration_sum_seconds"] = round(bucket["duration_sum_seconds"], 3)
        bucket["duration_max_seconds"] = round(bucket["duration_max_seconds"], 3)
        tools.append(bucket)
    tools.sort(key=lambda item: (-item["duration_sum_seconds"], -item["count"], item["tool"]))
    report["tools"] = tools

    duplicate_candidates = []
    for run in command_runs.values():
        if run["runs"] < 2:
            continue
        duplicate_candidates.append(
            {
                "command_preview": (
                    run["command"]
                    if len(run["command"]) <= _COMMAND_PREVIEW
                    else run["command"][: _COMMAND_PREVIEW - 3] + "..."
                ),
                "digest": run["digest"],
                "runs": run["runs"],
                "sessions": sorted(run["sessions"]),
                "note": (
                    "suspect-reusable: same normalized command ran again; confirm identical "
                    "inputs, artifact identity and environment before treating it as waste"
                ),
            }
        )
    duplicate_candidates.sort(key=lambda item: (-item["runs"], item["digest"]))
    report["duplicate_command_candidates"] = duplicate_candidates[:DUPLICATE_LIMIT]

    # Wall-clock: union of message and tool intervals across all matched sessions.
    all_intervals: list[tuple[int, int]] = []
    for sid in sids:
        all_intervals.extend(session_message_intervals.get(sid, []))
        all_intervals.extend(tool_intervals_by_session.get(sid, []))
    positive = _positive(all_intervals)
    if positive:
        active_ms, merged = merge_intervals(positive)
        interval_source = "messages+tools"
    else:
        fallback = _positive(session_intervals)
        if fallback:
            active_ms, merged = merge_intervals(fallback)
            interval_source = "sessions"
        else:
            active_ms, merged = 0, []
            interval_source = None
    span_ms = 0
    if merged:
        span_ms = merged[-1][1] - merged[0][0]

    for entry in session_entries:
        sid = entry["id"]
        own: list[tuple[int, int]] = []
        own.extend(session_message_intervals.get(sid, []))
        own.extend(tool_intervals_by_session.get(sid, []))
        own_positive = _positive(own)
        if not own_positive:
            for row in matched:
                if _row_get(row, "id") == sid:
                    row_interval = (
                        _row_get(row, "time_created"),
                        _row_get(row, "time_updated"),
                    )
                    own_positive = _positive([row_interval])
                    break
        own_total, own_merged = merge_intervals(own_positive)
        entry["active_seconds"] = round(own_total / 1000, 3)
        entry["span_seconds"] = (
            round((own_merged[-1][1] - own_merged[0][0]) / 1000, 3) if own_merged else None
        )

    total_input = sum(bucket["input"] for bucket in session_tokens.values())
    total_output = sum(bucket["output"] for bucket in session_tokens.values())
    total_reasoning = sum(bucket["reasoning"] for bucket in session_tokens.values())
    total_cache_read = sum(bucket["cache_read"] for bucket in session_tokens.values())
    total_cache_write = sum(bucket["cache_write"] for bucket in session_tokens.values())
    total_cost = sum(session_costs.values())
    child_count = sum(1 for entry in session_entries if entry["parent_id"])
    token_available = full_columns or bool(session_tokens)

    availability["models"] = availability["models"] or bool(models)
    if estimated_tool_times:
        report["notes"].append(
            f"{estimated_tool_times} tool call(s) had no state.time; their duration was "
            "estimated from part row timestamps"
        )
    for flag, reason in (
        (not full_columns, "session token/cost columns unavailable in this store version"),
        (not token_available, "no token data available; token totals are null"),
        (not any(session_tokens.values()), "assistant messages carried no token data; using session columns"),
        (not availability["models"], "no model id found on sessions or messages"),
        (not availability["costs"], "no cost data found; cost is null"),
    ):
        if flag and reason:
            report["notes"].append(reason)

    report["availability"] = availability
    report["models"] = models
    report["sessions"] = session_entries
    report["totals"] = {
        "sessions": len(session_entries),
        "child_sessions": child_count,
        "assistant_turns": total_turns,
        "error_turns": total_errors,
        "tool_calls": total_tool_calls,
        "task_dispatches": task_dispatches,
        "duplicate_command_candidates": len(duplicate_candidates),
        "span_seconds": round(span_ms / 1000, 3) if merged else None,
        "active_seconds": round(active_ms / 1000, 3) if merged else None,
        "idle_seconds": (
            round(max(0, span_ms - active_ms) / 1000, 3) if merged else None
        ),
        "interval_source": interval_source,
        "input_tokens": total_input if token_available else None,
        "output_tokens": total_output if token_available else None,
        "reasoning_tokens": total_reasoning if token_available else None,
        "cache_read": total_cache_read if token_available else None,
        "cache_write": total_cache_write if token_available else None,
        "cost": round(total_cost, 6) if availability["costs"] else None,
    }
    if truncated:
        report["totals"]["tool_calls"] = total_tool_calls
    return report


def load_metrics(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"metrics report unreadable at {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != METRICS_SCHEMA:
        raise ValueError(f"metrics schema must be {METRICS_SCHEMA}: {path}")
    return data


_COMPARE_FIELDS = (
    "span_seconds",
    "active_seconds",
    "idle_seconds",
    "assistant_turns",
    "error_turns",
    "tool_calls",
    "task_dispatches",
    "duplicate_command_candidates",
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "cache_read",
    "cache_write",
    "cost",
)


def compare_metrics(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Field-wise delta of two reports. Missing values compare as unavailable."""

    base_totals = baseline.get("totals") or {}
    cand_totals = candidate.get("totals") or {}
    deltas: dict[str, Any] = {}
    for field in _COMPARE_FIELDS:
        before = base_totals.get(field)
        after = cand_totals.get(field)
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            deltas[field] = {
                "baseline": before,
                "candidate": after,
                "delta": round(after - before, 6),
                "delta_percent": (
                    round((after - before) / before * 100, 2) if before else None
                ),
            }
        else:
            deltas[field] = {"baseline": before, "candidate": after, "delta": None}
    return {
        "schema": COMPARE_SCHEMA,
        "baseline": {
            "path": baseline.get("source", {}).get("path"),
            "models": sorted((baseline.get("models") or {}).keys()),
        },
        "candidate": {
            "path": candidate.get("source", {}).get("path"),
            "models": sorted((candidate.get("models") or {}).keys()),
        },
        "deltas": deltas,
        "note": (
            "compare only runs of the same task, scope and model family; "
            "different models or changed goals invalidate the comparison"
        ),
    }


def _write_report(data: dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _utf8()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export", help="export workflow performance metrics from the session store")
    ex.add_argument("target", help="target project directory")
    ex.add_argument("--db", help="explicit path to the opencode session database")
    ex.add_argument("--lookback-days", type=int, default=None)
    ex.add_argument("--out", required=True, help="output metrics JSON path")
    cmp = sub.add_parser("compare", help="diff two metrics reports")
    cmp.add_argument("baseline", help="baseline metrics JSON")
    cmp.add_argument("candidate", help="candidate metrics JSON")
    cmp.add_argument("--out", help="optional comparison JSON output path")
    args = parser.parse_args(argv)

    if args.cmd == "export":
        report = export_metrics(Path(args.target), args.db, args.lookback_days)
        _write_report(report, Path(args.out))
        err = report.get("export_error")
        if err:
            print(f"metrics export failed: {err}", file=sys.stderr)
            return 2
        totals = report["totals"]
        print(
            f"metrics written: {args.out} "
            f"(sessions={totals['sessions']}, turns={totals['assistant_turns']}, "
            f"tools={totals['tool_calls']}, active={totals['active_seconds']}s, "
            f"span={totals['span_seconds']}s)"
        )
        return 0

    try:
        baseline = load_metrics(Path(args.baseline))
        candidate = load_metrics(Path(args.candidate))
    except ValueError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2
    comparison = compare_metrics(baseline, candidate)
    text = json.dumps(comparison, ensure_ascii=False, indent=2)
    if args.out:
        _write_report(comparison, Path(args.out))
        print(f"comparison written: {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

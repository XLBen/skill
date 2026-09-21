#!/usr/bin/env python3
"""S01 probe: inspect the local OpenCode session store read-only.

Verifies native task-dispatch provenance (parent/child session, agent, model)
without writing to the store. Output is text on stdout; no secrets are read.
"""

import json
import sqlite3
import sys
from pathlib import Path


def find_db() -> Path | None:
    candidates = [
        Path.home() / "AppData" / "Local" / "opencode" / "opencode.db",
        Path.home() / ".local" / "share" / "opencode" / "opencode.db",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    roots = [
        Path.home() / "AppData" / "Local" / "opencode",
        Path.home() / ".local" / "share" / "opencode",
    ]
    for root in roots:
        if root.is_dir():
            for path in root.rglob("*.db"):
                return path
    return None


def main() -> int:
    db = find_db()
    if db is None:
        print("NO-DB")
        return 2
    print(f"DB: {db}")
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
    print(f"tables: {tables}")
    session_cols = [r[1] for r in con.execute("pragma table_info(session)")]
    print(f"session columns: {session_cols}")

    target = Path(r"E:\MISC\代码项目\skill")
    target_norm = str(target).replace("\\", "/").lower()
    rows = con.execute(
        "select id, parent_id, agent, model, directory, time_created, time_updated "
        "from session order by time_created desc limit 80"
    ).fetchall()
    print("--- sessions whose directory matches the skill repo ---")
    matched = []
    for r in rows:
        directory = (r["directory"] or "").replace("\\", "/").lower()
        if directory == target_norm:
            matched.append(r)
    for r in matched[:30]:
        print(json.dumps({
            "id": str(r["id"])[:70],
            "parent": str(r["parent_id"])[:70] if r["parent_id"] else None,
            "agent": r["agent"],
            "model": r["model"],
            "created": r["time_created"],
        }, ensure_ascii=False))
    print(f"matched sessions: {len(matched)}")

    print("--- recent task tool parts (all directories) ---")
    try:
        parts = con.execute(
            "select session_id, time_created, data from part "
            "where json_extract(data,'$.tool')='task' "
            "order by time_created desc limit 12"
        ).fetchall()
    except sqlite3.Error as exc:
        print(f"part query failed: {exc}")
        parts = []
    for p in parts:
        data = json.loads(p["data"])
        state = data.get("state") or {}
        inp = state.get("input") or {}
        out = state.get("output")
        if isinstance(out, str):
            out_head = out[:260]
        else:
            out_head = None
        print(json.dumps({
            "parent_session": str(p["session_id"])[:70],
            "time": p["time_created"],
            "subagent_type": inp.get("subagent_type"),
            "description": inp.get("description"),
            "status": state.get("status"),
            "output_head": out_head,
        }, ensure_ascii=False))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

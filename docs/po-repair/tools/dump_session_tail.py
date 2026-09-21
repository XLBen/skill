#!/usr/bin/env python3
"""Dump the tail of a child session's messages/parts to diagnose empty results."""

import json
import sqlite3
import sys
from pathlib import Path

SESSION = sys.argv[1] if len(sys.argv) > 1 else "ses_f3bac55adffenD52TLJ8r44ul8"


def find_db() -> Path | None:
    for candidate in (
        Path.home() / "AppData" / "Local" / "opencode" / "opencode.db",
        Path.home() / ".local" / "share" / "opencode" / "opencode.db",
    ):
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    db = find_db()
    if db is None:
        print("NO-DB")
        return 2
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "select id, time_created, data from message where session_id=? order by time_created",
        (SESSION,),
    ).fetchall()
    print(f"messages: {len(rows)}")
    for r in rows[-6:]:
        data = json.loads(r["data"]) if r["data"] else {}
        role = data.get("role")
        error = data.get("error")
        finish = data.get("finish")
        summary = None
        if isinstance(error, dict):
            summary = json.dumps(error)[:400]
        print(json.dumps({
            "id": r["id"], "time": r["time_created"], "role": role,
            "finish": finish, "error": summary,
            "tokens": data.get("tokens"),
        }, ensure_ascii=False))
    parts = con.execute(
        "select id, message_id, time_created, data from part where session_id=? order by time_created desc limit 8",
        (SESSION,),
    ).fetchall()
    print("--- last parts ---")
    for p in reversed(parts):
        data = json.loads(p["data"]) if p["data"] else {}
        ptype = data.get("type")
        text = None
        if ptype == "text":
            text = (data.get("text") or "")[:300]
        elif ptype == "tool":
            text = f"tool={data.get('tool')} status={(data.get('state') or {}).get('status')}"
        print(json.dumps({"type": ptype, "text": text}, ensure_ascii=False))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

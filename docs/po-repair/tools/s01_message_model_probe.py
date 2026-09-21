#!/usr/bin/env python3
"""S01 probe 3: where does a child session's model come from?

Checks per-message model records in the parent session to see whether the
parent's model changed over time (which would mean children inherit the
dispatching session's model at dispatch time).
"""

import json
import sqlite3
import sys
from pathlib import Path

PARENT = "ses_f41dc3881ffeCFq0a2yyKTBDU6"
CHILDREN = {
    "ses_f41a25b3affe5i7WWUhC2ylNVn": "mvp-reviewer",
    "ses_f41a25c32ffePKsiOvC6tZYFNu": "mvp-researcher",
    "ses_f41756f4fffeXi8sfDfrMDy6Uv": "mvp-reviewer",
}


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
    cols = [r[1] for r in con.execute("pragma table_info(message)")]
    print(f"message columns: {cols}")
    rows = con.execute(
        "select * from message where session_id=? order by time_created limit 200", (PARENT,)
    ).fetchall()
    print(f"parent messages: {len(rows)}")
    for r in rows:
        data = {}
        for key in r.keys():
            if key in ("data", "metadata"):
                continue
            data[key] = str(r[key])[:40] if r[key] is not None else None
        raw = None
        for key in ("data", "metadata"):
            if key in r.keys() and r[key]:
                try:
                    raw = json.loads(r[key])
                except (TypeError, ValueError):
                    raw = None
                if isinstance(raw, dict):
                    break
        model = None
        if isinstance(raw, dict):
            model = raw.get("modelID") or raw.get("model") or (raw.get("modelID") is None and raw.get("providerID"))
            provider = raw.get("providerID")
        else:
            provider = None
        print(json.dumps({"id": data.get("id"), "time": data.get("time_created"),
                          "model": model, "provider": provider}, ensure_ascii=False))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

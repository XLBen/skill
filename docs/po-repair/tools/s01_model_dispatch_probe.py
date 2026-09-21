#!/usr/bin/env python3
"""S01 probe 2: inspect full task-part inputs for model-specified dispatches."""

import json
import sqlite3
import sys
from pathlib import Path


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
        "select session_id, time_created, data from part "
        "where json_extract(data,'$.tool')='task' and json_extract(data,'$.state.status')='completed' "
        "order by time_created desc limit 40"
    ).fetchall()
    for r in rows:
        data = json.loads(r["data"])
        state = data.get("state") or {}
        inp = state.get("input") or {}
        subagent = inp.get("subagent_type")
        if subagent not in ("mvp-reviewer", "mvp-researcher", "mvp-product-observer", "mvp-worker", "mvp-test-author", "mvp-step-executor"):
            continue
        keys = sorted(inp.keys())
        model = inp.get("model")
        print(json.dumps({
            "parent": str(r["session_id"])[:70],
            "subagent_type": subagent,
            "input_keys": keys,
            "model_field": model,
        }, ensure_ascii=False))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

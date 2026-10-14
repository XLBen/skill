#!/usr/bin/env python3
"""Owner-only black-box oracle for the L2 SQLite event ledger."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROGRAM = ROOT / "src" / "event_ledger.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PROGRAM), *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=10,
        check=False,
    )


def compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> int:
    failures: list[str] = []
    checks = 0

    def require(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(message)

    require(PROGRAM.is_file(), "src/event_ledger.py is missing")
    if not PROGRAM.is_file():
        print("L2 ORACLE FAIL")
        print("- src/event_ledger.py is missing")
        return 1

    with tempfile.TemporaryDirectory(prefix="skill-l2-") as raw_temp:
        temp = Path(raw_temp)
        db = temp / "ledger.db"
        valid = ROOT / "fixtures" / "events.jsonl"

        inserted = run("ingest", "--db", str(db), str(valid))
        require(inserted.returncode == 0, f"initial ingest exit was {inserted.returncode}")
        require(inserted.stdout == compact({"duplicates": 0, "inserted": 3}) + "\n", "initial ingest summary is wrong")
        require(inserted.stderr == "", "initial ingest wrote stderr")

        report = run("report", "--db", str(db))
        expected_report = compact(
            {"account_totals": {"alpha": 3, "beta": 7}, "event_count": 3}
        )
        require(report.returncode == 0, "report failed after process restart")
        require(report.stdout == expected_report + "\n", "persisted report is wrong")

        duplicate = run("ingest", "--db", str(db), str(valid))
        require(duplicate.returncode == 0, "idempotent re-ingest failed")
        require(duplicate.stdout == compact({"duplicates": 3, "inserted": 0}) + "\n", "duplicate counts are wrong")
        require(run("report", "--db", str(db)).stdout == expected_report + "\n", "duplicates changed totals")

        invalid = run("ingest", "--db", str(db), str(ROOT / "fixtures" / "events-invalid.jsonl"))
        require(invalid.returncode == 2, "invalid batch did not exit 2")
        require(invalid.stdout == "", "invalid batch produced stdout")
        require("line 2" in invalid.stderr.lower(), "invalid batch omitted line 2")
        require(run("report", "--db", str(db)).stdout == expected_report + "\n", "invalid batch was not rolled back")

        conflict_file = temp / "conflict.jsonl"
        conflict_file.write_text(
            '{"event_id":"e-4","account":"alpha","delta":11}\n'
            '{"event_id":"e-1","account":"alpha","delta":999}\n',
            encoding="utf-8",
        )
        conflict = run("ingest", "--db", str(db), str(conflict_file))
        require(conflict.returncode == 2, "conflicting event ID did not exit 2")
        require(conflict.stdout == "", "conflicting event ID produced stdout")
        require("conflict" in conflict.stderr.lower(), "conflict error lacks stable category")
        require(run("report", "--db", str(db)).stdout == expected_report + "\n", "conflict batch was not rolled back")

        malformed_file = temp / "malformed.jsonl"
        malformed_file.write_text(
            '{"event_id":"e-4","account":"alpha","delta":11}\nnot-json\n',
            encoding="utf-8",
        )
        malformed = run("ingest", "--db", str(db), str(malformed_file))
        require(malformed.returncode == 2, "malformed JSON did not exit 2")
        require("line 2" in malformed.stderr.lower(), "malformed JSON omitted line 2")
        require(run("report", "--db", str(db)).stdout == expected_report + "\n", "malformed batch changed state")

        empty_file = temp / "empty.jsonl"
        empty_file.write_text("", encoding="utf-8")
        empty = run("ingest", "--db", str(db), str(empty_file))
        require(empty.returncode == 0, "empty semantic-zero batch failed")
        require(empty.stdout == compact({"duplicates": 0, "inserted": 0}) + "\n", "empty batch summary is wrong")

        empty_db = temp / "empty.db"
        empty_report = run("report", "--db", str(empty_db))
        require(empty_report.returncode == 0, "new database report failed")
        require(empty_report.stdout == compact({"account_totals": {}, "event_count": 0}) + "\n", "new database semantic-zero report is wrong")

    if failures:
        print(f"L2 ORACLE FAIL ({len(failures)}/{checks} checks failed)")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"L2 ORACLE PASS ({checks} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

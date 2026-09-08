#!/usr/bin/env python3
"""Owner-only black-box oracle for the L1 receipt totals task."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROGRAM = ROOT / "src" / "receipt_totals.py"


def invoke(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PROGRAM), str(path)],
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

    require(PROGRAM.is_file(), "src/receipt_totals.py is missing")
    if not PROGRAM.is_file():
        print("L1 ORACLE FAIL")
        print("- src/receipt_totals.py is missing")
        return 1

    fixed = invoke(ROOT / "fixtures" / "receipts.csv")
    expected = compact(
        {
            "accepted_count": 3,
            "category_totals_cents": {"books": 2500, "food": 1500},
            "grand_total_cents": 4000,
        }
    )
    require(fixed.returncode == 0, f"fixed fixture exit was {fixed.returncode}")
    require(fixed.stdout == expected + "\n", "fixed fixture stdout is not exact compact JSON")
    require(fixed.stderr == "", "fixed fixture wrote stderr")

    with tempfile.TemporaryDirectory(prefix="skill-l1-") as raw_temp:
        temp = Path(raw_temp)
        zero = temp / "zero.csv"
        zero.write_text(
            "receipt_id,category,amount_cents,status\n"
            "z-1,food,400,pending\n",
            encoding="utf-8",
        )
        zero_result = invoke(zero)
        zero_expected = compact(
            {"accepted_count": 0, "category_totals_cents": {}, "grand_total_cents": 0}
        )
        require(zero_result.returncode == 0, "semantic-zero input did not succeed")
        require(zero_result.stdout == zero_expected + "\n", "semantic-zero output is wrong")

        bad_amount = temp / "bad-amount.csv"
        bad_amount.write_text(
            "receipt_id,category,amount_cents,status\n"
            "bad-1,food,12.50,paid\n",
            encoding="utf-8",
        )
        bad_result = invoke(bad_amount)
        require(bad_result.returncode == 2, "invalid amount did not exit 2")
        require(bad_result.stdout == "", "invalid amount produced stdout")
        require("row 2" in bad_result.stderr.lower(), "invalid amount omitted 1-based row number")

        duplicate = temp / "duplicate.csv"
        duplicate.write_text(
            "receipt_id,category,amount_cents,status\n"
            "d-1,food,100,paid\n"
            "d-1,books,200,paid\n",
            encoding="utf-8",
        )
        duplicate_result = invoke(duplicate)
        require(duplicate_result.returncode == 2, "duplicate ID did not exit 2")
        require(duplicate_result.stdout == "", "duplicate ID produced stdout")
        require("row 3" in duplicate_result.stderr.lower(), "duplicate ID omitted row 3")

    if failures:
        print(f"L1 ORACLE FAIL ({len(failures)}/{checks} checks failed)")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"L1 ORACLE PASS ({checks} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

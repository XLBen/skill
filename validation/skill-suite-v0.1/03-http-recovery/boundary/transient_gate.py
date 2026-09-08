#!/usr/bin/env python3
"""Owner-controlled deterministic circuit-break benchmark gate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


STATE = Path(__file__).resolve().parent.parent / "artifacts" / "circuit-count.txt"


def read_count() -> int:
    try:
        return int(STATE.read_text(encoding="ascii").strip())
    except (FileNotFoundError, ValueError):
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--count", action="store_true")
    args = parser.parse_args()
    if args.reset:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text("0\n", encoding="ascii")
        print("reset")
        return 0
    if args.count:
        print(read_count())
        return 0

    count = read_count() + 1
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(f"{count}\n", encoding="ascii")
    if count <= 3:
        print("V-DRILL AssertionError: readiness gate unavailable", file=sys.stderr)
        return 1
    print("gate-ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

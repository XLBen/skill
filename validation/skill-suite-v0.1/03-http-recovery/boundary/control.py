#!/usr/bin/env python3
"""Owner-only scenario selector for the local benchmark boundary."""

from __future__ import annotations

import argparse
from pathlib import Path


SCENARIOS = {"normal", "schema-v2", "outage", "invalid-schema"}
SCENARIO_FILE = Path(__file__).resolve().with_name("scenario.txt")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=sorted(SCENARIOS))
    args = parser.parse_args()
    SCENARIO_FILE.write_text(args.scenario + "\n", encoding="utf-8")
    print(args.scenario)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

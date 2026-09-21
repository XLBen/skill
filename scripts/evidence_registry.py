#!/usr/bin/env python3
"""Evidence reuse registry for strict-equivalence verification reuse.

Re-running the same verification command against an unchanged artifact and
environment is pure repeated cost. This module defines the only reuse policy
the engine accepts: **strict equivalence**.

Two evidence runs are equivalent only when all of the following match:

  - the verification binding: kind, command, cwd, timeout, expected text,
    assertion kind, empty-result policy and the assertion itself;
  - the identity binding: goal id/definition hash, or the step/v/contract/
    plan/step hashes;
  - the recorded artifact: the source run passed with no workspace change, and
    the current workspace snapshot still equals the one recorded by the source
    run.

Anything else — external mutable state, a changed file, a different assertion,
a narrower timeout, an unknown side effect — is not reusable; those cases
re-run. `check.py verify-goal --reuse` performs the final validation and writes
a new evidence record that references the source run instead of pretending the
command executed again.

`find` is a read-only helper for the controller: it lists which existing
evidence files are strict-equivalent to a request, and why the others are not.
It is advisory; only the engine-side reuse check can authorize reuse.

Python 3.10+, stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REUSE_POLICY = "immutable-inputs"
REUSE_PLAN_SCHEMA = "evidence-reuse-plan/1"

# Fields that must match exactly for reuse (compared canonically). Identity
# fields are compared when present in the request.
BINDING_FIELDS = (
    "kind",
    "command",
    "cwd",
    "timeout_seconds",
    "expected",
    "assertion_kind",
    "empty_result_policy",
    "assertion",
)
IDENTITY_FIELDS = (
    "goal_id",
    "goal_definition_hash",
    "runtime_state_policy",
    "step_id",
    "v_id",
    "contract_hash",
    "plan_structure_hash",
    "step_hash",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def equality_problems(source: dict[str, Any], expectation: dict[str, Any]) -> list[str]:
    """Compare source evidence against an expected binding.

    `expectation` carries only the fields that must match; missing expectation
    fields are ignored, so callers must build the expectation from the
    authoritative request (never from the source file)."""

    problems: list[str] = []
    for field in BINDING_FIELDS + IDENTITY_FIELDS:
        if field not in expectation:
            continue
        if _canonical(source.get(field)) != _canonical(expectation[field]):
            problems.append(f"{field} mismatch")
    return problems


def reuse_rejection_reasons(
    source: dict[str, Any], expectation: dict[str, Any]
) -> list[str]:
    """All reasons this source cannot back a reuse, empty when eligible."""

    problems = equality_problems(source, expectation)
    if source.get("result") != "passed":
        problems.append(f"source result is {source.get('result')!r}, not 'passed'")
    if source.get("workspace_changed") is True:
        problems.append("source run changed the workspace")
    if not isinstance(source.get("workspace_after"), str) or not source.get("workspace_after"):
        problems.append("source evidence predates workspace binding")
    return problems


def find_reusable(
    evidence_dir: Path, expectation: dict[str, Any], exclude: list[Path] | None = None
) -> dict[str, Any]:
    """Scan a directory for strict-equivalent passed evidence. Read-only."""

    excluded = {str(Path(item).resolve()).lower() for item in (exclude or [])}
    reusable: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    if evidence_dir.is_dir():
        for path in sorted(evidence_dir.glob("*.json")):
            key = str(path.resolve()).lower()
            if key in excluded:
                continue
            entry: dict[str, Any] = {"path": path.as_posix()}
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                entry["reasons"] = ["unreadable evidence file"]
                rejected.append(entry)
                continue
            if not isinstance(payload, dict):
                entry["reasons"] = ["evidence is not a JSON object"]
                rejected.append(entry)
                continue
            reasons = reuse_rejection_reasons(payload, expectation)
            if reasons:
                entry["reasons"] = reasons
                rejected.append(entry)
            else:
                entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                entry["started_at"] = payload.get("started_at")
                entry["finished_at"] = payload.get("finished_at")
                entry["elapsed_seconds"] = payload.get("elapsed_seconds")
                reusable.append(entry)
    return {
        "schema": REUSE_PLAN_SCHEMA,
        "policy": REUSE_POLICY,
        "evidence_dir": str(evidence_dir).replace("\\", "/"),
        "reusable": reusable,
        "rejected": rejected,
        "note": (
            "advisory only: the engine revalidates equivalence and the current workspace "
            "snapshot at reuse time; a listed entry can still be refused"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    find = sub.add_parser("find", help="list strict-equivalent evidence for a binding request")
    find.add_argument("--dir", required=True, help="evidence directory to scan")
    find.add_argument(
        "--bindings",
        required=True,
        help="JSON file with the expected binding fields (built from the request, not from evidence)",
    )
    find.add_argument("--exclude", action="append", default=[], help="exclude an evidence path")
    find.add_argument("--out", help="optional output path; default stdout")
    args = parser.parse_args(argv)

    if args.cmd == "find":
        try:
            expectation = json.loads(Path(args.bindings).read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"INVALID: bindings unreadable: {exc}", file=sys.stderr)
            return 2
        if not isinstance(expectation, dict):
            print("INVALID: bindings must be a JSON object", file=sys.stderr)
            return 2
        report = find_reusable(
            Path(args.dir), expectation, exclude=[Path(item) for item in args.exclude]
        )
        text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            print(
                f"reuse plan written: {args.out} "
                f"(reusable={len(report['reusable'])}, rejected={len(report['rejected'])})"
            )
        else:
            print(text, end="")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())

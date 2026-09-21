#!/usr/bin/env python3
"""S00 corpus collector: copy the 21 archived observation results into
docs/po-repair/corpus and direct-check each one with the current
scripts/product_observation.py validators.

Reads only from the read-only sandbox (E:\\MISC\\代码项目\\po-validation-sandbox);
writes only under docs/po-repair/.

Field-level crash attribution: the validators test some values with set
membership (`value not in SOME_SET`), which raises TypeError for dict/list
values. The validator itself does not say which field crashed, so after a real
crash this script replays the set-membership checks in validator order on the
same object and reports the first unhashable value. The crash classification
always comes from the real validator call.
"""

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SANDBOX = Path(r"E:\MISC\代码项目\po-validation-sandbox")
PROJECTS = SANDBOX / "projects"
CORPUS = REPO / "docs" / "po-repair" / "corpus"

sys.path.insert(0, str(REPO / "scripts"))
import product_observation as po  # noqa: E402

ORIGINAL_MODEL = "zhipuai-coding-plan/glm-5.3-flash"
PHASE_BY_SUFFIX = {
    "discover.result.json": "discover",
    "compare.result.json": "compare",
    "review.result.json": "review",
}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def unhashable(value) -> bool:
    try:
        hash(value)
    except TypeError:
        return True
    return False


def report_crash_field(data: dict) -> str | None:
    if unhashable(data.get("stop_reason")):
        return "report.stop_reason"
    surfaces = data.get("surfaces")
    if isinstance(surfaces, list):
        for index, item in enumerate(surfaces):
            if isinstance(item, dict) and unhashable(item.get("importance")):
                return f"report.surfaces[{index}].importance"
    findings = data.get("findings")
    if isinstance(findings, list):
        for index, item in enumerate(findings):
            if not isinstance(item, dict):
                continue
            for key in ("category", "confidence", "status"):
                if unhashable(item.get(key)):
                    return f"report.findings[{index}].{key}"
    return None


def review_crash_field(data: dict) -> str | None:
    for field in ("findings_validity", "coverage_adequacy"):
        if unhashable(data.get(field)):
            return f"review.{field}"
    if unhashable(data.get("verdict")):
        return "review.verdict"
    return None


def main() -> int:
    sources = sorted(PROJECTS.glob("*/.opencode/mvp/observation/G-OBS/*/*.result.json"))
    index: list[dict] = []
    for source in sources:
        rel = source.relative_to(PROJECTS)
        case, goal_id, candidate, filename = rel.parts[0], rel.parts[4], rel.parts[5], rel.parts[-1]
        phase = PHASE_BY_SUFFIX.get(filename, filename.split(".")[0])
        handmade = case == "t1"
        raw = source.read_bytes()
        digest = sha256(raw)
        entry = {
            "case": case,
            "goal_id": goal_id,
            "candidate": candidate,
            "phase": phase,
            "source_path": str(source),
            "sha256": digest,
            "size": len(raw),
            "handmade": handmade,
            "original_model": (
                "hand-made (t1 attack harness; no model output)"
                if handmade
                else ORIGINAL_MODEL
            ),
            "validator": None,
            "valid": None,
            "original_errors": [],
            "crash": None,
            "crash_field": None,
            "encoding": None,
            "json_ok": None,
            "schema": None,
            "declared_phase": None,
            "stop_reason": None,
            "copied_path": None,
            "copied_sha256": None,
            "copy_matches": None,
        }
        dest = CORPUS / case / candidate / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        copied = dest.read_bytes()
        entry["copied_path"] = str(dest)
        entry["copied_sha256"] = sha256(copied)
        entry["copy_matches"] = entry["copied_sha256"] == digest

        try:
            text = raw.decode("utf-8-sig")
            entry["encoding"] = "utf-8"
        except UnicodeDecodeError as exc:
            entry["encoding"] = f"NOT-UTF8: {exc}"
            index.append(entry)
            entry["valid"] = False
            entry["original_errors"].append(f"UNDECODABLE: {exc}")
            continue

        try:
            data = json.loads(text)
            entry["json_ok"] = True
        except json.JSONDecodeError as exc:
            entry["json_ok"] = False
            entry["valid"] = False
            entry["original_errors"].append(
                f"INVALID-JSON {type(exc).__name__}: {exc}"
            )
            index.append(entry)
            continue

        if not isinstance(data, dict):
            entry["valid"] = False
            entry["original_errors"].append("NOT-A-JSON-OBJECT")
            index.append(entry)
            continue

        entry["schema"] = data.get("schema")
        entry["declared_phase"] = data.get("phase")
        entry["stop_reason"] = data.get("stop_reason")

        if data.get("schema") == po.REVIEW_SCHEMA:
            entry["validator"] = "review"
            validate = po.validate_observation_review
            crash_field = review_crash_field
        else:
            entry["validator"] = "report"
            validate = po.validate_observation_report
            crash_field = report_crash_field

        try:
            problems = validate(data)
        except Exception as exc:  # VALIDATOR-CRASH
            entry["crash"] = f"{type(exc).__name__}: {exc}"
            entry["crash_field"] = crash_field(data)
            suffix = (
                f" (first unhashable set-membership field: {entry['crash_field']})"
                if entry["crash_field"]
                else ""
            )
            entry["original_errors"] = [
                f"VALIDATOR-CRASH {entry['crash']}{suffix}"
            ]
        else:
            entry["valid"] = len(problems) == 0
            entry["original_errors"] = list(problems)
        index.append(entry)

    CORPUS.mkdir(parents=True, exist_ok=True)
    (CORPUS / "INDEX.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    total = len(index)
    valid = sum(1 for item in index if item["valid"] is True)
    invalid = sum(1 for item in index if item["valid"] is False)
    crash = sum(1 for item in index if item["crash"])
    copy_ok = sum(1 for item in index if item["copy_matches"])
    handmade = sum(1 for item in index if item["handmade"])
    print(
        f"collected={total} valid={valid} invalid={invalid} "
        f"validator_crash={crash} copy_matches={copy_ok}/{total} handmade={handmade}"
    )
    for item in index:
        state = (
            "CRASH"
            if item["crash"]
            else ("VALID" if item["valid"] else "invalid")
        )
        if item["valid"] is None and not item["crash"]:
            state = "UNREADABLE"
        print(
            f"  {state:9s} {item['case']}/{item['candidate']}/{item['phase']} "
            f"errors={len(item['original_errors'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

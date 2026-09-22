"""Run the installed workflow against a three-step real CLI/file-I/O project.

Deterministic reference implementation, not a live model-quality evaluation.
Every CLI call and captured observation is preserved under a new --out directory.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone


REPO = Path(__file__).resolve().parents[2]
READER = '''def read_value(path):
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError("empty input")
    return value
'''
APP = '''from pathlib import Path
import sys
from reader import read_value
def main(argv):
    if len(argv) != 1:
        print("usage: app.py path")
        return 2
    try:
        print("VALUE:" + read_value(Path(argv[0])))
        return 0
    except FileNotFoundError:
        print("input boundary unavailable")
        return 3
    except ValueError:
        print("empty input")
        return 4
if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
'''
READER_TEST = '''from pathlib import Path
import sys, tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reader import read_value
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "value.txt"
    for value in ("hello", "独立输入"):
        p.write_text(" " + value + "\\n", encoding="utf-8")
        assert read_value(p) == value
    p.write_text(" ", encoding="utf-8")
    try:
        read_value(p)
        raise AssertionError("empty value accepted")
    except ValueError:
        pass
    p.unlink()
    try:
        read_value(p)
        raise AssertionError("absent file accepted")
    except FileNotFoundError:
        pass
print("READER_OK")
'''
CLI_TEST = '''from pathlib import Path
import subprocess, sys, tempfile, uuid
app = Path(__file__).resolve().parents[1] / "app.py"
def run(path):
    return subprocess.run([sys.executable, str(app), str(path)], capture_output=True, text=True, timeout=10)
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "actual.txt"
    for value in (uuid.uuid4().hex, uuid.uuid4().hex):
        p.write_text(value, encoding="utf-8")
        result = run(p)
        assert result.returncode == 0 and result.stdout.strip() == "VALUE:" + value, result
    p.write_text("", encoding="utf-8")
    result = run(p)
    assert result.returncode == 4 and "empty input" in result.stdout, result
    p.unlink()
    result = run(p)
    assert result.returncode == 3 and "input boundary unavailable" in result.stdout, result
print("CLI_CASES_OK")
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(exist_ok=False)
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "python": sys.executable,
              "scope": "Installed engine and real three-stage CLI/file I/O; no live model, browser or game validation",
              "checks": [], "commands": [], "passed": False}

    def run(argv, cwd, expected=0, contains=None):
        r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        record = {"argv": list(map(str, argv)), "cwd": str(cwd), "exit_code": r.returncode,
                  "expected_exit_code": expected, "stdout": r.stdout, "stderr": r.stderr}
        report["commands"].append(record)
        if r.returncode != expected or (contains and contains not in r.stdout + r.stderr):
            raise RuntimeError(json.dumps(record, ensure_ascii=False))
        return r

    def setup(name):
        root = out / name
        root.mkdir()
        run([sys.executable, str(REPO / "scripts/install.py"), str(root)], root)
        example = (REPO / "writing-plans/references/engineering-plan-example.md").read_text(encoding="utf-8")
        plan = json.loads(re.search(r"```json engineering-plan\s*\n(.*?)\n```", example, re.S)[1])

        def bind_commands(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == "command":
                        value[key] = item.replace("python ", f'"{sys.executable}" ', 1)
                    else:
                        bind_commands(item)
            elif isinstance(value, list):
                for item in value:
                    bind_commands(item)
        bind_commands(plan)
        bound_design = re.sub(r"```json\s+engineering-plan\s*\n.*?\n```",
                              lambda _: "```json engineering-plan\n" + json.dumps(plan, ensure_ascii=False, indent=2) + "\n```",
                              example, count=1, flags=re.S)
        (root / "design.md").write_text(bound_design, encoding="utf-8")
        goal = {"schema_version": 3, "id": plan["goal_id"], "status": "active",
                "source": {"type": "direct", "raw_request": "Read actual UTF-8 file via CLI; missing/empty input fails"},
                "goal": "Real file-reader CLI", "rigor": "normal", "risk": {"factors": ["none"], "rationale": "Disposable local project"},
                "first_slice": "Reader then boundary then CLI", "demo": "python app.py input.txt", "constraints": [], "deferred": [],
                "product_observation": {"required": True},
                "outcomes": [{"id": "O-01", "statement": "Read actual file via delivered CLI", "status": "pending", "user_entry": True,
                              "verification": plan["journeys"][0]["verification"]}]}
        card = root / ".opencode/mvp/reader.md"
        card.parent.mkdir(parents=True)
        card.write_text("---\nstatus: active\n---\n\n```json goal\n" + json.dumps(goal) + "\n```\n", encoding="utf-8")
        (root / "input.txt").write_text("42", encoding="utf-8")

        def cli(command, *extra, expected=0, contains=None):
            return run([sys.executable, str(root / ".opencode/workflow/scripts/check.py"), command, str(card), *extra], root, expected, contains)

        def observe(decision, interpretation, expected=0):
            # Runtime auto-attaches actual receipts; these cannot be replaced by a predicted actual field.
            cli("observe-cycle", "--decision", decision, "--interpretation", interpretation, expected=expected)
        publication = json.loads(cli("prepare-plan", "design.md").stdout)
        readable = Path(publication["readable_plan"]).read_text(encoding="utf-8")
        assert "### S-03" in readable and "```mermaid" in readable and "```json engineering-plan" not in readable
        return root, cli, observe

    def component(root, cli, observe):
        packet = json.loads(cli("next-step").stdout)
        assert packet["step"]["id"] == "S-01" and "journeys" not in packet
        cli("begin-cycle")
        (root / "tests").mkdir(exist_ok=True)
        (root / "tests/check_reader.py").write_text(READER_TEST, encoding="utf-8")
        cli("verify-cycle", expected=1, contains="cycle failed")
        cli("begin-cycle", expected=2, contains="observe")
        observe("retry", "Actual component test cannot import reader; implement K-01, no CLI needed")
        cli("begin-cycle")
        (root / "reader.py").write_text(READER, encoding="utf-8")
        result = json.loads(cli("verify-cycle").stdout)
        assert "READER_OK" in result["observed"][0]["stdout"]
        assert not (root / "app.py").exists()
        observe("advance", "UTF-8, missing and empty cases pass against actual temporary files; no app.py exists")

    def boundary(cli, observe):
        assert json.loads(cli("next-step").stdout)["step"]["id"] == "S-02"
        cli("begin-cycle")
        result = json.loads(cli("verify-cycle").stdout)
        assert any("BOUNDARY_OK" in item["stdout"] for item in result["observed"])
        observe("advance", "Delivered reader read actual input.txt content; boundary validated before CLI integration")

    try:
        root, cli, observe = setup("layered-delivery")
        component(root, cli, observe)
        boundary(cli, observe)
        packet = json.loads(cli("next-step").stdout)
        assert packet["step"]["id"] == "S-03" and packet["contracts"][0]["id"] == "K-01"
        cli("begin-cycle")
        (root / "app.py").write_text(APP, encoding="utf-8")
        (root / "tests/check_cli.py").write_text(CLI_TEST, encoding="utf-8")
        cli("verify-cycle")
        cli("cycle-gate", expected=2, contains="observation")
        observe("advance", "Actual CLI returns distinct generated values, empty/missing failures and the declared real journey")
        cli("cycle-gate")
        assert json.loads(cli("next-step").stdout)["action"] == "final-acceptance"
        cli("verify-goal", "O-01", "--evidence", ".opencode/mvp/evidence/final.json")
        cli("finish-goal", expected=2, contains="observation")
        report["checks"].append("Component runs without app; real boundary precedes integration; task packets supply only needed contracts; full three-stage path passes")
        # A fake that understands the fixed negative case still cannot pass random-content CLI checks.
        (root / "app.py").write_text("import sys\nif 'absent-input.txt' in sys.argv:\n print('input boundary unavailable'); sys.exit(3)\nprint('VALUE:42')\n", encoding="utf-8")
        cli("cycle-gate", expected=2, contains="stale")
        # Remove final outcome evidence references through an explicit plan revision before further edits.
        design = root / "design.md"
        design.write_text(design.read_text(encoding="utf-8") + "\nRecheck seeded fake against unchanged requirements.\n", encoding="utf-8")
        cli("prepare-plan", "design.md")
        for sid in ("S-01", "S-02"):
            cli("begin-cycle", sid)
            cli("verify-cycle")
            observe("advance", "Existing reader still satisfies current contract and boundary; retained without rewriting")
        cli("begin-cycle", "S-03")
        cli("verify-cycle", expected=1, contains="cycle failed")
        observe("advance", "Seeded fake must not be accepted", expected=2)
        observe("replan", "The seeded implementation demonstrates why fixed stdout samples alone cannot prove real reading")
        assert json.loads(cli("next-step").stdout)["action"] == "replan"
        cli("begin-cycle", "S-03", expected=2, contains="design conflict")
        report["checks"].append("Fake passes fixed positive/negative samples but real varied-input check rejects it; stale evidence and replan lock verified")

        root, cli, observe = setup("missing-boundary")
        component(root, cli, observe)
        (root / "input.txt").unlink()
        cli("begin-cycle", expected=1, contains="cycle failed")
        cli("verify-cycle", expected=2, contains="preflight failed")
        report["checks"].append("Missing target blocks boundary stage after valid component; no full UI or fake environment substituted")
        report["passed"] = True
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"passed": report["passed"], "report": str(out / "report.json"), "checks": report["checks"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

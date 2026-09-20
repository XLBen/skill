import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import check
from scripts import evidence_registry

ROOT = Path(__file__).resolve().parent.parent

BUMP_SCRIPT = """import pathlib
import sys

counter = pathlib.Path(sys.argv[1])
current = int(counter.read_text(encoding="utf-8")) if counter.exists() else 0
counter.write_text(str(current + 1), encoding="utf-8")
print("Hello user")
"""


def make_reusable_goal(root, counter_dir, outcome_count=3):
    _, goal = check.read_artifact(ROOT / "tests/fixtures/goal-valid.md", "goal")
    script = counter_dir / "bump.py"
    counter = counter_dir / "counter.txt"
    script.write_text(BUMP_SCRIPT, encoding="utf-8")
    command = f'"{sys.executable}" "{script}" "{counter}"'
    goal["outcomes"][0]["verification"]["command"] = command
    for index in range(1, outcome_count):
        clone = json.loads(json.dumps(goal["outcomes"][0]))
        clone["id"] = f"O-0{index + 1}"
        clone["statement"] = f"Greeting variant {index + 1}"
        clone["user_entry"] = False
        goal["outcomes"].append(clone)
    card = root / ".opencode" / "mvp" / "g-reuse.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    (root / "greeter.py").write_text("print('Hello user')\n", encoding="utf-8")
    card.write_text(check.render_goal(goal), encoding="utf-8")
    return card, counter


def counter_value(counter):
    return int(counter.read_text(encoding="utf-8")) if counter.exists() else 0


class ReuseGoalEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "proj"
        self.root.mkdir()
        counters = tempfile.TemporaryDirectory()
        self.addCleanup(counters.cleanup)
        self.counter_dir = Path(counters.name)
        self.card, self.counter = make_reusable_goal(self.root, self.counter_dir)

    def _run(self, outcome, name, reuse=None):
        check.verify_goal_outcome(
            self.card,
            outcome,
            f".opencode/mvp/evidence/{name}.json",
            reuse_from=reuse,
        )

    def test_reuse_skips_reexecution_and_records_source(self):
        self._run("O-01", "O-01-01")
        self.assertEqual(counter_value(self.counter), 1)
        self._run("O-02", "O-02-01", reuse=".opencode/mvp/evidence/O-01-01.json")
        self.assertEqual(counter_value(self.counter), 1)
        payload = json.loads(
            (self.root / ".opencode/mvp/evidence/O-02-01.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["result"], "passed")
        self.assertEqual(payload["reuse_policy"], "immutable-inputs")
        self.assertEqual(
            payload["reused_from"]["path"], ".opencode/mvp/evidence/O-01-01.json"
        )
        source = (self.root / ".opencode/mvp/evidence/O-01-01.json").read_bytes()
        self.assertEqual(
            payload["reused_from"]["sha256"], hashlib.sha256(source).hexdigest()
        )
        self.assertEqual(payload["reused_from"]["sha256"], payload["reused_from"]["sha256"])
        self.assertNotEqual(payload["stdout"], "")
        _, goal = check.read_artifact(self.card, "goal")
        by_id = {item["id"]: item for item in goal["outcomes"]}
        self.assertEqual(by_id["O-02"]["status"], "verified")
        self.assertEqual(by_id["O-03"]["status"], "pending")

    def test_reuse_refused_after_workspace_change(self):
        self._run("O-01", "O-01-01")
        (self.root / "greeter.py").write_text("print('Hello changed')\n", encoding="utf-8")
        with self.assertRaisesRegex(check.ValidationError, "workspace changed"):
            self._run("O-02", "O-02-01", reuse=".opencode/mvp/evidence/O-01-01.json")
        self.assertEqual(counter_value(self.counter), 1)
        self.assertFalse((self.root / ".opencode/mvp/evidence/O-02-01.json").exists())

    def test_reuse_refused_when_command_differs(self):
        self._run("O-01", "O-01-01")
        source = self.root / ".opencode/mvp/evidence/O-01-01.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["command"] = payload["command"] + " --extra"
        tampered = self.root / ".opencode/mvp/evidence/tampered.json"
        tampered.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(check.ValidationError, "not strictly equivalent"):
            self._run("O-02", "O-02-01", reuse=".opencode/mvp/evidence/tampered.json")

    def test_reuse_refused_for_failed_source(self):
        self._run("O-01", "O-01-01")
        source = self.root / ".opencode/mvp/evidence/O-01-01.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["result"] = "failed"
        failed = self.root / ".opencode/mvp/evidence/failed.json"
        failed.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(check.ValidationError, "not 'passed'"):
            self._run("O-02", "O-02-01", reuse=".opencode/mvp/evidence/failed.json")

    def test_reuse_refused_for_source_without_workspace_binding(self):
        self._run("O-01", "O-01-01")
        source = self.root / ".opencode/mvp/evidence/O-01-01.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload.pop("workspace_after", None)
        legacy = self.root / ".opencode/mvp/evidence/legacy.json"
        legacy.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(check.ValidationError, "predates workspace binding"):
            self._run("O-02", "O-02-01", reuse=".opencode/mvp/evidence/legacy.json")

    def test_cli_verify_goal_reuse_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                check.main(
                    [
                        "check.py",
                        "verify-goal",
                        str(self.card),
                        "O-01",
                        "--evidence",
                        ".opencode/mvp/evidence/O-01-01.json",
                    ]
                ),
                0,
            )
            self.assertEqual(
                check.main(
                    [
                        "check.py",
                        "verify-goal",
                        str(self.card),
                        "O-02",
                        "--evidence",
                        ".opencode/mvp/evidence/O-02-01.json",
                        "--reuse",
                        ".opencode/mvp/evidence/O-01-01.json",
                    ]
                ),
                0,
            )
        self.assertEqual(counter_value(self.counter), 1)
        (self.root / "greeter.py").write_text("print('Hello changed')\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            code = check.main(
                [
                    "check.py",
                    "verify-goal",
                    str(self.card),
                    "O-03",
                    "--evidence",
                    ".opencode/mvp/evidence/O-03-01.json",
                    "--reuse",
                    ".opencode/mvp/evidence/O-01-01.json",
                ]
            )
        self.assertEqual(code, 2)


class RegistryTests(unittest.TestCase):
    def _payload(self, **overrides):
        payload = {
            "schema_version": 1,
            "kind": "goal-verification",
            "goal_id": "G-X",
            "outcome_id": "O-01",
            "goal_definition_hash": "a" * 64,
            "command": "pytest -q",
            "cwd": "D:/proj",
            "timeout_seconds": 120,
            "expected": "tests pass",
            "assertion_kind": "state",
            "empty_result_policy": "empty fails",
            "assertion": {"type": "json-equals", "expected": {"ok": True}},
            "started_at": "2026-09-19T00:00:00Z",
            "finished_at": "2026-09-19T00:00:01Z",
            "elapsed_seconds": 1.0,
            "timed_out": False,
            "exit_code": 0,
            "stdout": "ok",
            "stderr": "",
            "workspace_before": "abc",
            "workspace_after": "abc",
            "workspace_changed": False,
            "result": "passed",
        }
        payload.update(overrides)
        return payload

    def _expectation(self):
        return {
            "kind": "goal-verification",
            "goal_id": "G-X",
            "goal_definition_hash": "a" * 64,
            "command": "pytest -q",
            "cwd": "D:/proj",
            "timeout_seconds": 120,
            "expected": "tests pass",
            "assertion_kind": "state",
            "empty_result_policy": "empty fails",
            "assertion": {"type": "json-equals", "expected": {"ok": True}},
        }

    def test_rejection_reasons(self):
        self.assertEqual(
            evidence_registry.reuse_rejection_reasons(self._payload(), self._expectation()), []
        )
        failed = evidence_registry.reuse_rejection_reasons(
            self._payload(result="failed"), self._expectation()
        )
        self.assertIn("source result is 'failed', not 'passed'", failed)
        no_workspace = evidence_registry.reuse_rejection_reasons(
            self._payload(workspace_after=None), self._expectation()
        )
        self.assertIn("source evidence predates workspace binding", no_workspace)
        mismatch = evidence_registry.reuse_rejection_reasons(
            self._payload(command="other"), self._expectation()
        )
        self.assertIn("command mismatch", mismatch)

    def test_outcome_id_is_not_part_of_equivalence(self):
        changed = self._payload(outcome_id="O-99")
        self.assertEqual(
            evidence_registry.reuse_rejection_reasons(changed, self._expectation()), []
        )

    def test_find_lists_equivalent_and_rejects_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "good.json").write_text(json.dumps(self._payload()), encoding="utf-8")
            (tmp / "failed.json").write_text(
                json.dumps(self._payload(result="failed")), encoding="utf-8"
            )
            (tmp / "bad.json").write_text("{not json", encoding="utf-8")
            report = evidence_registry.find_reusable(tmp, self._expectation())
            self.assertEqual([entry["path"].split("/")[-1] for entry in report["reusable"]], ["good.json"])
            rejected = {entry["path"].split("/")[-1] for entry in report["rejected"]}
            self.assertEqual(rejected, {"failed.json", "bad.json"})
            self.assertEqual(report["policy"], "immutable-inputs")
            self.assertIn("advisory only", report["note"])

    def test_find_cli_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "good.json").write_text(json.dumps(self._payload()), encoding="utf-8")
            bindings = tmp / "bindings.json"
            bindings.write_text(json.dumps(self._expectation()), encoding="utf-8")
            out = tmp / "plan.json"
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = evidence_registry.main(
                    [
                        "find",
                        "--dir",
                        str(tmp),
                        "--bindings",
                        str(bindings),
                        "--out",
                        str(out),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertIn("reuse plan written", stdout.getvalue())
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(report["reusable"]), 1)


if __name__ == "__main__":
    unittest.main()

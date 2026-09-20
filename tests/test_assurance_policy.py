import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import assurance_policy
from scripts import check

ROOT = Path(__file__).resolve().parent.parent

GOOD_MANIFEST = """# Test Manifest: S-01

| Field | Value |
|---|---|
| Spec source | contract.md |
| Spec hash | abc123 |
| Test author ID | ses_author (mvp-test-author) |
| Provenance status | bound |
| Implementation author ID | pending |
| Frozen at | 2026-09-19T00:00:00Z |
| Protected test files | tests/test_feature.py={hash} |
"""

GOOD_DISPATCH = {
    "schema_version": 2,
    "goal_id": "G-X",
    "revision": 1,
    "active_slice": {
        "slice_id": "S-01",
        "rigor": "audited",
        "package": "docs/audit-slices/g/S-01",
    },
    "failure_counters": [],
    "tasks": [
        {
            "task_id": "T-01",
            "role": "step-executor",
            "status": "done",
            "attempt": 1,
            "acceptance": {"verdict": "satisfied", "pending_actions": []},
            "actions": [],
        }
    ],
}


def make_package(root, strict=True):
    package = root / "docs" / "audit-slices" / "g" / "S-01"
    (package / "evidence").mkdir(parents=True, exist_ok=True)
    (package / "test-manifests").mkdir(parents=True, exist_ok=True)
    (package / "contract.md").write_text("# contract\n", encoding="utf-8")
    (package / "PLAN.md").write_text("# plan\n", encoding="utf-8")
    (package / "workflow-events.jsonl").write_text("", encoding="utf-8")
    (package / "change-orders.md").write_text("# CR\n", encoding="utf-8")
    (package / "evidence" / "phase-0-01.md").write_text(
        "Probe verdict: passed\n", encoding="utf-8"
    )
    test_file = root / "tests" / "test_feature.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_feature():\n    assert True\n", encoding="utf-8")
    digest = hashlib.sha256(test_file.read_bytes()).hexdigest()
    (package / "test-manifests" / "S-01.md").write_text(
        GOOD_MANIFEST.replace("{hash}", digest), encoding="utf-8"
    )
    (package / "g.dispatch.json").write_text(
        json.dumps(GOOD_DISPATCH), encoding="utf-8"
    )
    if strict:
        (package / "assurance-policy.json").write_text(
            json.dumps({"schema": "assurance-policy/1", "strict": True}),
            encoding="utf-8",
        )
    return package


class PackageCheckTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.package = make_package(self.root)

    def problems(self, **kwargs):
        return assurance_policy.package_problems(
            self.package, project_root=self.root, **kwargs
        )

    def test_happy_package_passes(self):
        self.assertEqual(self.problems(), [])

    def test_missing_required_file_fails(self):
        (self.package / "change-orders.md").unlink()
        self.assertTrue(any("change-orders.md" in p for p in self.problems()))

    def test_missing_phase0_fails(self):
        (self.package / "evidence" / "phase-0-01.md").unlink()
        self.assertTrue(any("phase 0 record is missing" in p for p in self.problems()))

    def test_refuted_phase0_fails(self):
        (self.package / "evidence" / "phase-0-01.md").write_text(
            "Probe verdict: refuted\n", encoding="utf-8"
        )
        problems = self.problems()
        self.assertTrue(any("refuted" in p for p in problems), problems)

    def test_pending_binding_manifest_fails(self):
        manifest = self.package / "test-manifests" / "S-01.md"
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(
            text.replace("| Provenance status | bound |", "| Provenance status | pending-binding |"),
            encoding="utf-8",
        )
        problems = self.problems()
        self.assertTrue(any("provenance status" in p for p in problems), problems)

    def test_same_author_fails(self):
        manifest = self.package / "test-manifests" / "S-01.md"
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(
            text.replace(
                "| Implementation author ID | pending |",
                "| Implementation author ID | ses_author |",
            ),
            encoding="utf-8",
        )
        problems = self.problems()
        self.assertTrue(any("same test and implementation author" in p for p in problems), problems)

    def test_protected_hash_mismatch_fails(self):
        (self.root / "tests" / "test_feature.py").write_text(
            "def test_feature():\n    assert False\n", encoding="utf-8"
        )
        problems = self.problems()
        self.assertTrue(any("hash mismatch" in p for p in problems), problems)

    def test_unresolved_dispatch_action_fails(self):
        dispatch = self.package / "g.dispatch.json"
        record = json.loads(dispatch.read_text(encoding="utf-8"))
        record["tasks"][0]["actions"] = [
            {"action_id": "A-01", "kind": "run-command", "status": "requested", "evidence_ref": None}
        ]
        dispatch.write_text(json.dumps(record), encoding="utf-8")
        problems = self.problems()
        self.assertTrue(any("unresolved-controller-action" in p for p in problems), problems)

    def test_circuit_break_fails(self):
        dispatch = self.package / "g.dispatch.json"
        record = json.loads(dispatch.read_text(encoding="utf-8"))
        record["failure_counters"] = [
            {"target": "V-01", "signature": "AssertionError", "actual_failures": 3, "evidence_refs": []}
        ]
        dispatch.write_text(json.dumps(record), encoding="utf-8")
        problems = self.problems()
        self.assertTrue(any("circuit" in p for p in problems), problems)

    def test_owner_gate_is_not_a_defect(self):
        dispatch = self.package / "g.dispatch.json"
        record = json.loads(dispatch.read_text(encoding="utf-8"))
        record["tasks"][0]["acceptance"] = {"verdict": "owner", "pending_actions": ["ask owner"]}
        dispatch.write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual(self.problems(), [])

    def test_policy_schema_validation(self):
        policy = self.package / "assurance-policy.json"
        policy.write_text(json.dumps({"schema": "wrong", "strict": True}), encoding="utf-8")
        with self.assertRaises(assurance_policy.AssuranceError):
            assurance_policy.load_policy(self.package)
        policy.write_text(json.dumps({"schema": "assurance-policy/1", "strict": "yes"}), encoding="utf-8")
        with self.assertRaises(assurance_policy.AssuranceError):
            assurance_policy.load_policy(self.package)


class FinishPlanEnforcementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.package = make_package(self.root, strict=False)

    def test_no_policy_file_is_ignored(self):
        check.enforce_assurance_policy(self.package / "PLAN.md", {"workflow_protocol": "v0.2"})

    def test_strict_policy_rejects_incomplete_package(self):
        (self.package / "assurance-policy.json").write_text(
            json.dumps({"schema": "assurance-policy/1", "strict": True}),
            encoding="utf-8",
        )
        (self.package / "evidence" / "phase-0-01.md").unlink()
        with self.assertRaisesRegex(check.ValidationError, "assurance policy failed"):
            check.enforce_assurance_policy(self.package / "PLAN.md", {"workflow_protocol": "v0.2"})

    def test_strict_policy_accepts_complete_package(self):
        make_package(self.root)  # rewrite the strict package in place
        check.enforce_assurance_policy(self.package / "PLAN.md", {"workflow_protocol": "v0.2"})

    def test_non_strict_policy_is_ignored(self):
        (self.package / "assurance-policy.json").write_text(
            json.dumps({"schema": "assurance-policy/1", "strict": False}),
            encoding="utf-8",
        )
        (self.package / "evidence" / "phase-0-01.md").unlink()
        check.enforce_assurance_policy(self.package / "PLAN.md", {"workflow_protocol": "v0.2"})

    def test_wrong_policy_schema_fails_even_without_package_files(self):
        (self.package / "assurance-policy.json").write_text(
            json.dumps({"schema": "bogus", "strict": True}), encoding="utf-8"
        )
        with self.assertRaisesRegex(check.ValidationError, "schema"):
            check.enforce_assurance_policy(self.package / "PLAN.md", {})


class CliTests(unittest.TestCase):
    def test_cli_check_reports_pass_and_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = make_package(root)
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = assurance_policy.main(
                    ["check", str(package), "--project-root", str(root)]
                )
            self.assertEqual(code, 0)
            self.assertIn("PASS", stdout.getvalue())

            (package / "evidence" / "phase-0-01.md").unlink()
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = assurance_policy.main(
                    ["check", str(package), "--project-root", str(root)]
                )
            self.assertEqual(code, 1)
            self.assertIn("phase 0 record is missing", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()

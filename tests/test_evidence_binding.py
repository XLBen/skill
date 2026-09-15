import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import check

ROOT = Path(__file__).resolve().parent.parent


def make_goal(root, outcome_count=1):
    _, goal = check.read_artifact(ROOT / "tests/fixtures/goal-valid.md", "goal")
    goal["outcomes"][0]["verification"]["command"] = f'"{sys.executable}" -c "print(\'Hello user\')"'
    for index in range(1, outcome_count):
        clone = json.loads(json.dumps(goal["outcomes"][0]))
        clone["id"] = f"O-0{index + 1}"
        clone["statement"] = f"Greeting variant {index + 1}"
        clone["user_entry"] = False
        clone["verification"]["command"] = f'"{sys.executable}" -c "print(\'Usage {index + 1}\')"'
        clone["verification"]["assertion"] = {"type": "stdout-contains", "literal": f"Usage {index + 1}"}
        goal["outcomes"].append(clone)
    card = root / ".opencode" / "mvp" / "g-fixture.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    (root / "greeter.py").write_text("print('Hello user')\n", encoding="utf-8")
    card.write_text(check.render_goal(goal), encoding="utf-8")
    return card


def evidence_path(root, outcome="O-01", name="01"):
    return root / ".opencode" / "mvp" / "evidence" / f"g-fixture-{outcome}-{name}.json"


class WorkspaceBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.card = make_goal(self.root)

    def test_product_change_after_verification_blocks_finish(self):
        check.verify_goal_outcome(self.card, "O-01", evidence_path(self.root))
        (self.root / "greeter.py").write_text("print('Hello changed')\n", encoding="utf-8")
        with self.assertRaisesRegex(check.ValidationError, "workspace changed after verification"):
            check.finish_goal(self.card)

    def test_new_product_file_after_verification_blocks_finish(self):
        check.verify_goal_outcome(self.card, "O-01", evidence_path(self.root))
        (self.root / "extra_module.py").write_text("value = 1\n", encoding="utf-8")
        with self.assertRaisesRegex(check.ValidationError, "workspace changed after verification"):
            check.finish_goal(self.card)

    def test_evidence_predating_workspace_binding_blocks_finish(self):
        check.verify_goal_outcome(self.card, "O-01", evidence_path(self.root))
        path = evidence_path(self.root)
        payload = json.loads(path.read_text(encoding="utf-8"))
        for field in ("workspace_before", "workspace_after", "workspace_changed"):
            payload.pop(field, None)
        path.write_text(json.dumps(payload), encoding="utf-8")
        import hashlib

        _, goal = check.read_artifact(self.card, "goal")
        goal["outcomes"][0]["evidence"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.card.write_text(check.render_goal(goal), encoding="utf-8")
        with self.assertRaisesRegex(check.ValidationError, "predates workspace binding"):
            check.finish_goal(self.card)

    def test_workflow_and_cache_writes_do_not_invalidate(self):
        card = make_goal(self.root, outcome_count=2)
        check.verify_goal_outcome(card, "O-01", evidence_path(self.root))
        check.verify_goal_outcome(card, "O-02", evidence_path(self.root, "O-02", "02"))
        (self.root / "__pycache__").mkdir()
        (self.root / "__pycache__" / "cached.pyc").write_bytes(b"cache")
        (self.root / "dist").mkdir()
        (self.root / "dist" / "bundle.bin").write_bytes(b"generated")
        (self.root / ".opencode" / "mvp" / "extra-state.json").write_text("{}", encoding="utf-8")
        self.assertEqual(check.finish_goal(card)["status"], "complete")

    def test_verification_command_that_mutates_workspace_is_rejected(self):
        _, goal = check.read_artifact(self.card, "goal")
        goal["outcomes"][0]["verification"]["command"] = (
            f'"{sys.executable}" -c "open(\'side-effect.txt\', \'w\').write(\'x\'); print(\'Hello user\')"'
        )
        self.card.write_text(check.render_goal(goal), encoding="utf-8")
        updated, payload = check.verify_goal_outcome(self.card, "O-01", evidence_path(self.root))
        self.assertTrue(payload["workspace_changed"])
        self.assertEqual(payload["result"], "failed")
        self.assertEqual(updated["outcomes"][0]["status"], "blocked")
        with self.assertRaisesRegex(check.ValidationError, "every outcome"):
            check.finish_goal(self.card)


class CheckCurrentTests(unittest.TestCase):
    """A completed card must still answer whether the current product matches."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.card = make_goal(self.root)

    def test_completed_goal_is_current_until_the_product_changes(self):
        check.verify_goal_outcome(self.card, "O-01", evidence_path(self.root))
        self.assertEqual(check.finish_goal(self.card)["status"], "complete")
        self.assertEqual(check.check_current(self.card)["status"], "complete")
        (self.root / "greeter.py").write_text("print('Hello changed')\n", encoding="utf-8")
        self.assertEqual(check.finish_goal(self.card)["status"], "complete")
        with self.assertRaisesRegex(check.ValidationError, "workspace changed after verification"):
            check.check_current(self.card)

    def test_snapshot_include_covers_excluded_delivery_inputs(self):
        _, goal = check.read_artifact(self.card, "goal")
        goal["snapshot_include"] = [".opencode/product/config.json"]
        self.card.write_text(check.render_goal(goal), encoding="utf-8")
        product = self.root / ".opencode" / "product"
        product.mkdir(parents=True)
        (product / "config.json").write_text('{"v": 1}\n', encoding="utf-8")
        check.verify_goal_outcome(self.card, "O-01", evidence_path(self.root))
        (product / "config.json").write_text('{"v": 2}\n', encoding="utf-8")
        with self.assertRaisesRegex(check.ValidationError, "workspace changed after verification"):
            check.finish_goal(self.card)

    def test_unreadable_included_file_fails_the_snapshot(self):
        from unittest import mock

        original = Path.read_bytes

        def flaky(self):
            if self.name == "greeter.py":
                raise OSError("permission denied")
            return original(self)

        with mock.patch.object(Path, "read_bytes", flaky):
            with self.assertRaisesRegex(check.ValidationError, "cannot read"):
                check.workspace_snapshot(self.root)

    def test_broad_include_does_not_wedge_on_workflow_state(self):
        _, goal = check.read_artifact(self.card, "goal")
        goal["snapshot_include"] = [".opencode/**"]
        self.card.write_text(check.render_goal(goal), encoding="utf-8")
        product = self.root / ".opencode" / "product"
        product.mkdir(parents=True)
        (product / "config.json").write_text('{"v": 1}\n', encoding="utf-8")
        check.verify_goal_outcome(self.card, "O-01", evidence_path(self.root))
        self.assertEqual(check.finish_goal(self.card)["status"], "complete")
        self.assertEqual(check.check_current(self.card)["status"], "complete")

    def test_snapshot_include_rejects_traversal(self):
        _, goal = check.read_artifact(self.card, "goal")
        goal["snapshot_include"] = ["../outside/file.txt"]
        problems = check.validate_goal(goal)
        self.assertTrue(
            any("must stay inside the project" in problem for problem in problems), problems
        )


class InterruptedReservationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.card = make_goal(self.root)
        self.evidence = evidence_path(self.root)
        self.evidence.parent.mkdir(parents=True, exist_ok=True)

    def _metadata_for_outcome(self):
        _, goal = check.read_artifact(self.card, "goal")
        verification = goal["outcomes"][0]["verification"]
        return goal, {
            "kind": "goal-verification",
            "goal_id": goal["id"],
            "outcome_id": "O-01",
            "goal_definition_hash": check.goal_definition_hash(goal),
            "assertion_kind": verification["assertion_kind"],
            "empty_result_policy": verification["empty_result_policy"],
            "expected": verification["expected"],
            "assertion": verification["assertion"],
        }

    def test_complete_temporary_payload_is_recovered_without_rerun(self):
        goal, metadata = self._metadata_for_outcome()
        verification = goal["outcomes"][0]["verification"]
        scratch = self.root / "scratch-evidence.json"
        payload, _ = check.run_command_evidence(
            verification["command"], self.root, scratch, metadata,
            verification.get("timeout_seconds", 120),
        )
        self.assertEqual(payload["result"], "passed")
        temporary = self.evidence.with_suffix(".json.tmp")
        temporary.write_bytes(scratch.read_bytes())
        scratch.unlink()
        from unittest import mock

        with mock.patch.object(check.subprocess, "Popen", side_effect=AssertionError("reran command")):
            updated, recovered = check.verify_goal_outcome(self.card, "O-01", self.evidence)
        self.assertEqual(recovered["result"], "passed")
        self.assertEqual(recovered["workspace_after"], payload["workspace_after"])
        self.assertFalse(temporary.exists())
        self.assertTrue(self.evidence.exists())
        self.assertEqual(updated["outcomes"][0]["status"], "verified")

    def test_incomplete_temporary_reservation_blocks_until_explicit_recovery(self):
        temporary = self.evidence.with_suffix(".json.tmp")
        temporary.write_bytes(b"interrupted evidence")
        from unittest import mock

        with mock.patch.object(check.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(check.ValidationError, "temporary evidence file already exists"):
                check.verify_goal_outcome(self.card, "O-01", self.evidence)
            launch.assert_not_called()
        self.assertTrue(temporary.exists())
        updated, payload = check.verify_goal_outcome(
            self.card, "O-01", self.evidence, recover_interrupted=True
        )
        self.assertEqual(payload["result"], "passed")
        self.assertTrue(payload["reservation_recovered"])
        self.assertEqual(updated["outcomes"][0]["status"], "verified")
        self.assertFalse(temporary.exists())


if __name__ == "__main__":
    unittest.main()

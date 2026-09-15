import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts import check


ROOT = Path(__file__).resolve().parent.parent


class BriefValidationTests(unittest.TestCase):
    def setUp(self):
        _, self.final = check.read_artifact(ROOT / "tests/fixtures/brief-valid.md", "brief")
        self.draft = copy.deepcopy(self.final)
        self.draft["status"] = "draft"
        self.draft["owner_confirmation"] = {"confirmed": False, "summary": ""}

    def test_public_template_is_a_valid_unconfirmed_draft(self):
        template = (ROOT / "grill/references/brief-template.md").read_text(encoding="utf-8")
        brief = check.parse_block(template, "brief")
        self.assertEqual(brief["owner_confirmation"], {"confirmed": False, "summary": ""})
        self.assertEqual(check.validate_brief(brief), [])

    def test_first_question_can_be_persisted_without_inventing_decisions(self):
        self.draft["items"] = [
            {"id": "BQ-01", "kind": "question", "question": "What result do you need?", "status": "open"}
        ]
        self.draft["frontier"] = ["BQ-01"]
        self.assertEqual(check.validate_brief(self.draft), [])

    def test_confirmation_fields_are_typed_and_required(self):
        for field, invalid_values in (
            ("confirmed", (None, 0, 1, "false", "true", [], {})),
            ("summary", (None, False, 7, [], {})),
        ):
            for value in invalid_values:
                with self.subTest(field=field, value=value):
                    brief = copy.deepcopy(self.draft)
                    brief["owner_confirmation"][field] = value
                    errors = check.validate_brief(brief)
                    self.assertTrue(any(f"owner_confirmation.{field}" in error for error in errors), errors)
            with self.subTest(field=field, missing=True):
                brief = copy.deepcopy(self.draft)
                del brief["owner_confirmation"][field]
                errors = check.validate_brief(brief)
                self.assertTrue(any(f"owner_confirmation.{field}" in error for error in errors), errors)

    def test_final_confirmation_and_summary_remain_strict(self):
        for confirmed in (False, "true", 1, None):
            with self.subTest(confirmed=confirmed):
                brief = copy.deepcopy(self.final)
                brief["owner_confirmation"]["confirmed"] = confirmed
                self.assertIn("final brief requires owner confirmation", check.validate_brief(brief))
        for summary in ("", "   ", None, [], 7):
            with self.subTest(summary=summary):
                brief = copy.deepcopy(self.final)
                brief["owner_confirmation"]["summary"] = summary
                self.assertTrue(any("summary" in error for error in check.validate_brief(brief)))
        self.assertEqual(check.validate_brief(self.final), [])

    def test_frontier_is_unique_and_only_references_open_questions(self):
        self.draft["items"].extend([
            {"id": "BQ-01", "kind": "question", "question": "Current question?", "status": "open"},
            {"id": "BQ-02", "kind": "question", "question": "Deferred question?", "status": "deferred"},
            {"id": "BQ-03", "kind": "question", "question": "Dependent question?", "status": "open"},
        ])
        self.draft["frontier"] = ["BQ-01"]
        self.assertEqual(check.validate_brief(self.draft), [])
        for frontier, expected in (
            (["BQ-01", "BQ-01"], "duplicate"),
            (["BQ-02"], "open question"),
            (["BQ-99"], "unknown question"),
            ([[]], "unknown question"),
            ([{}], "unknown question"),
        ):
            with self.subTest(frontier=frontier):
                self.draft["frontier"] = frontier
                self.assertTrue(any(expected in error for error in check.validate_brief(self.draft)))

    def test_final_artifact_and_hash_are_unchanged(self):
        meta, _, expected_hash, errors = check.validate_brief_artifact(ROOT / "tests/fixtures/brief-valid.md")
        self.assertEqual(errors, [])
        self.assertEqual(meta["brief-hash"], expected_hash)

    def test_clearing_frontier_does_not_resolve_open_questions(self):
        self.final["items"].append(
            {"id": "BQ-01", "kind": "question", "question": "Unanswered?", "status": "open"})
        self.assertTrue(any("open questions" in error for error in check.validate_brief(self.final)))
        self.final["items"][-1]["status"] = "deferred"
        self.assertEqual(check.validate_brief(self.final), [])


class GoalValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.card = self.root / ".opencode/mvp/goal.md"
        self.card.parent.mkdir(parents=True)
        _, self.goal = check.read_artifact(ROOT / "tests/fixtures/goal-valid.md", "goal")
        _, self.brief = check.read_artifact(ROOT / "tests/fixtures/brief-valid.md", "brief")
        self.goal["outcomes"][0]["verification"]["command"] = f'"{sys.executable}" -c "print(\'Hello user\')"'

    def write_brief_source(self):
        source_hash = check.brief_hash(self.brief)
        (self.root / "brief.md").write_text(
            f"---\nstatus: {self.brief['status']}\nbrief-hash: {source_hash}\n---\n\n```json brief\n"
            + json.dumps(self.brief) + "\n```\n", encoding="utf-8")
        self.goal["source"] = {
            "type": "brief", "path": "brief.md", "brief_hash": source_hash,
            "coverage": [{"brief_id": item["id"], "disposition": "outcome", "outcome_ids": ["O-01"]}
                         for item in self.brief["items"]],
        }

    def test_user_entry_required_in_every_status(self):
        for status in ("active", "blocked", "complete"):
            for missing in (False, True):
                with self.subTest(status=status, missing=missing):
                    goal = copy.deepcopy(self.goal)
                    goal["status"] = status
                    outcome = goal["outcomes"][0]
                    if status == "blocked":
                        outcome.update(status="blocked", blocker="Waiting for setup")
                    elif status == "complete":
                        outcome.update(status="verified", evidence={})
                    self.assertEqual(check.validate_goal(goal), [])
                    if missing:
                        outcome.pop("user_entry")
                    else:
                        outcome["user_entry"] = False
                    self.assertTrue(any("user-entry" in error for error in check.validate_goal(goal)))

    def test_internal_outcomes_are_allowed_alongside_a_real_entry(self):
        internal = copy.deepcopy(self.goal["outcomes"][0])
        internal["id"] = "O-02"
        internal.pop("user_entry")
        self.goal["outcomes"].append(internal)
        self.assertEqual(check.validate_goal(self.goal), [])
        self.goal["outcomes"][0]["user_entry"] = "true"
        self.assertTrue(any("boolean" in error for error in check.validate_goal(self.goal)))

    def test_no_entry_is_rejected_before_verification_execution(self):
        self.goal["outcomes"][0].pop("user_entry")
        self.card.write_text(check.render_goal(self.goal), encoding="utf-8")
        with mock.patch.object(check, "run_command_evidence") as runner:
            with self.assertRaisesRegex(check.ValidationError, "user-entry"):
                check.verify_goal_outcome(self.card, "O-01", ".opencode/mvp/evidence/unused.json")
            runner.assert_not_called()

    def test_success_cannot_be_removed_by_any_non_outcome_disposition(self):
        self.write_brief_source()
        for disposition in ("constraint", "deferred", "non-goal", "rejected"):
            with self.subTest(disposition=disposition):
                goal = copy.deepcopy(self.goal)
                item = next(item for item in goal["source"]["coverage"] if item["brief_id"] == "BS-01")
                item.pop("outcome_ids")
                item.update(disposition=disposition, reason="Required work postponed to the next slice")
                self.card.write_text(check.render_goal(goal), encoding="utf-8")
                original = self.card.read_bytes()
                errors = check.validate_goal_artifact(self.card)[2]
                self.assertTrue(any("success BS-01 must map to outcomes" in error for error in errors), errors)
                with mock.patch.object(check, "run_command_evidence") as runner:
                    with self.assertRaisesRegex(check.ValidationError, "success BS-01"):
                        check.verify_goal_outcome(self.card, "O-01", ".opencode/mvp/evidence/unused.json")
                    runner.assert_not_called()
                with self.assertRaisesRegex(check.ValidationError, "success BS-01"):
                    check.finish_goal(self.card)
                self.assertEqual(self.card.read_bytes(), original)

    def test_non_success_deferrals_remain_valid(self):
        self.brief["items"].append(
            {"id": "BQ-01", "kind": "question", "question": "Optional refinement?", "status": "deferred"})
        self.write_brief_source()
        for item in self.goal["source"]["coverage"]:
            if item["brief_id"] != "BS-01":
                item.pop("outcome_ids")
                item.update(disposition="deferred", reason="Not a promised success result")
        self.card.write_text(check.render_goal(self.goal), encoding="utf-8")
        self.assertEqual(check.validate_goal_artifact(self.card)[2], [])
        check.verify_goal_outcome(self.card, "O-01", ".opencode/mvp/evidence/one.json")
        self.assertEqual(check.finish_goal(self.card)["status"], "complete")

    def test_all_required_successes_must_be_verified_before_finish(self):
        self.brief["items"].append(
            {"id": "BS-02", "kind": "success", "statement": "Show usage", "source": "test fixture"})
        self.write_brief_source()
        second = copy.deepcopy(self.goal["outcomes"][0])
        second.update(id="O-02", statement="Show usage", user_entry=False)
        second["verification"].update(
            command=f'"{sys.executable}" -c "print(\'Usage\')"',
            assertion={"type": "stdout-contains", "literal": "Usage"})
        self.goal["outcomes"].append(second)
        next(item for item in self.goal["source"]["coverage"] if item["brief_id"] == "BS-02")["outcome_ids"] = ["O-02"]
        self.card.write_text(check.render_goal(self.goal), encoding="utf-8")
        self.assertEqual(check.validate_goal_artifact(self.card)[2], [])
        check.verify_goal_outcome(self.card, "O-01", ".opencode/mvp/evidence/one.json")
        with self.assertRaisesRegex(check.ValidationError, "every outcome"):
            check.finish_goal(self.card)
        check.verify_goal_outcome(self.card, "O-02", ".opencode/mvp/evidence/two.json")
        self.assertEqual(check.finish_goal(self.card)["status"], "complete")

    def test_draft_source_still_cannot_enter_goal_execution(self):
        self.brief["status"] = "draft"
        self.brief["owner_confirmation"] = {"confirmed": False, "summary": ""}
        self.write_brief_source()
        self.assertEqual(check.validate_brief_artifact(self.root / "brief.md")[3], [])
        self.card.write_text(check.render_goal(self.goal), encoding="utf-8")
        errors = check.validate_goal_artifact(self.card)[2]
        self.assertIn("goal source brief must be final", errors)
        self.assertIn("goal source brief requires owner confirmation", errors)


class EvidenceBundleHashTests(unittest.TestCase):
    """v0.2 drops the per-E self digest; legacy keeps it; a present one is checked."""

    def setUp(self):
        _, self.contract = check.read_artifact(ROOT / "tests/fixtures/contract-valid.md", "contract")
        self.e_node = {
            "id": "E-01", "status": "active", "supersedes": [], "superseded_by": [],
            "scope": "local", "claim": "fixture probe", "kind": "probe",
            "source": "user-direct", "checked_at": "2026-01-01T00:00:00Z",
            "environment": "test", "command": "python -c pass", "inputs": [],
            "output_summary": "ok", "verdict": "passed",
        }

    def _contract_with(self, node):
        contract = copy.deepcopy(self.contract)
        contract["nodes"]["E"] = [copy.deepcopy(node)]
        return contract

    def test_v02_e_node_does_not_require_bundle_hash(self):
        contract = self._contract_with(self.e_node)
        contract["workflow_protocol"] = "v0.2"
        problems = check.validate_contract(contract)
        self.assertFalse(any("bundle_hash" in problem for problem in problems), problems)

    def test_legacy_e_node_still_requires_bundle_hash(self):
        contract = self._contract_with(self.e_node)
        problems = check.validate_contract(contract)
        self.assertTrue(any("bundle_hash" in problem for problem in problems), problems)

    def test_present_bundle_hash_is_still_verified_in_v02(self):
        node = dict(self.e_node)
        node["bundle_hash"] = "0" * 64
        contract = self._contract_with(node)
        contract["workflow_protocol"] = "v0.2"
        problems = check.validate_contract(contract)
        self.assertTrue(any("bundle_hash mismatch" in problem for problem in problems), problems)


class InstalledWorkflowTests(unittest.TestCase):
    def test_installed_engine_validates_drafts_and_runs_selftest(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            install = subprocess.run(
                [sys.executable, "-B", str(ROOT / "scripts/install.py"), str(target)],
                cwd=ROOT, capture_output=True, timeout=30,
            )
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
            engine = target / ".opencode/workflow/scripts/check.py"
            self.assertEqual(engine.read_bytes(), (ROOT / "scripts/check.py").read_bytes())
            template = (ROOT / "grill/references/brief-template.md").read_text(encoding="utf-8")
            draft = check.parse_block(template, "brief")
            (target / "brief.md").write_text(
                "---\nstatus: draft\n---\n\n```json brief\n" + json.dumps(draft) + "\n```\n", encoding="utf-8")
            for args in (("brief", "brief.md"), ("--selftest",)):
                with self.subTest(args=args):
                    result = subprocess.run(
                        [sys.executable, "-B", str(engine), *args], cwd=target,
                        capture_output=True, timeout=60,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

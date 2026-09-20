"""Stage-routing resolver tests.

These verify the deterministic routing contract consumed by the runtime gate:

- the Audited implementation-seat table resolves for every profile/interaction;
- the markdown seat table in subagent-orchestration.md agrees with the JSON
  authority (machine-readable and human-readable copies cannot drift);
- PUA cards are narrowed by rigor instead of hard-coded role lists;
- reviewer dispatch conditions follow the routing entry's rigors;
- malformed routing data fails validation instead of silently passing.
"""

import copy
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import workflow_protocol as protocol  # noqa: E402

ROUTING_PATH = ROOT / "mvp-delivery/references/stage-routing.json"


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class RoutingLoadTests(unittest.TestCase):
    def test_default_path_finds_repository_routing(self):
        path = protocol.default_routing_path()
        self.assertEqual(path.resolve(), ROUTING_PATH.resolve())

    def test_loaded_routing_validates(self):
        routing = protocol.load_routing()
        self.assertEqual(protocol.validate_routing(routing), [])

    def test_missing_file_fails_closed(self):
        with self.assertRaises(protocol.ProtocolError):
            protocol.load_routing(ROOT / "does-not-exist.json")

    def test_malformed_condition_rejected(self):
        routing = protocol.load_routing()
        broken = copy.deepcopy(routing)
        broken["stages"][0]["reviewer"]["condition"]["mandatory"] = "yes"
        problems = protocol.validate_routing(broken)
        self.assertTrue(any("mandatory must be a bool" in p for p in problems), problems)

    def test_duplicate_stage_rejected(self):
        routing = protocol.load_routing()
        broken = copy.deepcopy(routing)
        broken["stages"].append(copy.deepcopy(broken["stages"][0]))
        problems = protocol.validate_routing(broken)
        self.assertTrue(any("duplicate stage_id" in p for p in problems), problems)


class SeatSelectionTests(unittest.TestCase):
    def test_every_profile_interaction_resolves(self):
        expected = {
            ("direct", "autonomous"): "controller",
            ("direct", "checkpoints"): "controller",
            ("direct", "stepwise"): "controller",
            ("full", "autonomous"): "step-executor",
            ("full", "checkpoints"): "step-executor",
            ("full", "stepwise"): "step-executor",
            ("light", "autonomous"): "controller",
            ("light", "checkpoints"): "step-executor",
            ("light", "stepwise"): "step-executor",
        }
        for (profile, interaction), seat in expected.items():
            self.assertEqual(protocol.execution_seat(profile, interaction), seat)

    def test_unknown_profile_rejected(self):
        with self.assertRaises(protocol.ProtocolError):
            protocol.execution_seat("turbo", "autonomous")

    def test_markdown_table_agrees_with_json_authority(self):
        text = read("mvp-delivery/references/subagent-orchestration.md")
        section = text.split("### Audited Execution Seat Selection", 1)[1]
        markdown = {}
        for line in section.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            cells = [cell.strip().replace("`", "") for cell in stripped.strip("|").split("|")]
            if len(cells) != 3 or cells[0] not in ("direct", "full", "light"):
                continue
            markdown[(cells[0], cells[1])] = cells[2]
        routing = protocol.load_routing()
        for row in routing["seat_selection"]["audited_implementation"]:
            expected = "主控同会话" if row["seat"] == "controller" else "step-executor"
            matched = [
                cell for (profile, interaction), cell in markdown.items()
                if profile == row["profile"]
                and (row["interaction"] == "any" or row["interaction"] in interaction)
            ]
            self.assertTrue(matched, row)
            for cell in matched:
                self.assertIn(expected, cell, row)


class ResponsibilityRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routing = protocol.load_routing()

    def test_implementation_seat_resolves_per_rigor(self):
        self.assertEqual(protocol.implementation_seat(self.routing, "normal"), "controller")
        self.assertEqual(protocol.implementation_seat(self.routing, "guarded"), "worker-subagent")
        self.assertEqual(
            protocol.implementation_seat(self.routing, "audited", "direct", "autonomous"),
            "controller",
        )
        self.assertEqual(
            protocol.implementation_seat(self.routing, "audited", "full", "autonomous"),
            "step-executor",
        )
        self.assertEqual(
            protocol.implementation_seat(self.routing, "audited", "light", "autonomous"),
            "controller",
        )

    def test_audited_never_resolves_to_worker(self):
        for profile in ("direct", "full", "light"):
            for interaction in ("autonomous", "checkpoints", "stepwise"):
                seat = protocol.implementation_seat(
                    self.routing, "audited", profile, interaction
                )
                self.assertNotEqual(seat, "worker-subagent", (profile, interaction))

    def test_unknown_rigor_and_missing_audited_inputs_fail_closed(self):
        with self.assertRaises(protocol.ProtocolError):
            protocol.implementation_seat(self.routing, "BOGUS")
        with self.assertRaises(protocol.ProtocolError):
            protocol.implementation_seat(self.routing, "audited")

    def test_every_semantic_check_has_one_known_owner(self):
        for stage in self.routing["stages"]:
            stage_id = stage["stage_id"]
            checks = protocol.semantic_checks(self.routing, stage_id)
            names = [entry["check"] for entry in checks]
            self.assertEqual(len(names), len(set(names)), stage_id)
            for entry in checks:
                self.assertIn(entry["owner_seat"], protocol.KNOWN_SEATS, stage_id)

    def test_test_freeze_and_step_verification_owners(self):
        self.assertEqual(
            protocol.semantic_check_owner(self.routing, "test-freeze", "test-freeze-semantics"),
            "test-author-subagent",
        )
        self.assertEqual(
            protocol.semantic_check_owner(self.routing, "test-freeze", "test-freeze-integrity"),
            "controller",
        )
        self.assertEqual(
            protocol.semantic_check_owner(self.routing, "step-verification", "step-handoff"),
            "step-executor-subagent",
        )
        self.assertEqual(
            protocol.semantic_check_owner(self.routing, "step-verification", "step-formal-evidence"),
            "controller",
        )
        self.assertEqual(
            protocol.semantic_check_owner(self.routing, "step-verification", "step-review"),
            "reviewer-subagent",
        )

    def test_formal_verification_is_controller_owned(self):
        formal = protocol.formal_verification(self.routing, "step-verification")
        self.assertEqual(formal["owner_seat"], "controller")
        self.assertIn("verify-step", formal["gate"])
        self.assertIsNone(protocol.formal_verification(self.routing, "test-freeze"))

    def test_step_review_is_explicitly_mandatory_for_audited(self):
        condition = protocol.reviewer_condition(self.routing, "step-verification", "audited")
        self.assertTrue(condition["dispatch"])
        self.assertTrue(condition["mandatory"])
        self.assertFalse(condition["blocking"])

    def test_guarded_worker_skill_does_not_apply_to_audited(self):
        entries = protocol.required_skills_for_stage(
            self.routing, "slice-implementation", "audited"
        )
        worker = next(entry for entry in entries if entry["name"] == "task-worker")
        self.assertFalse(protocol.pua_applies(worker, "audited"))
        self.assertTrue(protocol.pua_applies(worker, "guarded"))

    def test_validation_rejects_duplicate_checks_and_unknown_owners(self):
        broken = copy.deepcopy(self.routing)
        stage = protocol.stage_definition(broken, "test-freeze")
        stage["responsibilities"]["semantic_checks"].append(
            {"check": "test-freeze-semantics", "owner_seat": "controller", "kind": "pua"}
        )
        problems = protocol.validate_routing(broken)
        self.assertTrue(any("duplicate semantic check" in p for p in problems), problems)

        broken = copy.deepcopy(self.routing)
        stage = protocol.stage_definition(broken, "test-freeze")
        stage["responsibilities"]["semantic_checks"][0]["owner_seat"] = "intern"
        problems = protocol.validate_routing(broken)
        self.assertTrue(any("unknown owner seat" in p for p in problems), problems)

    def test_validation_rejects_non_controller_formal_verification(self):
        broken = copy.deepcopy(self.routing)
        stage = protocol.stage_definition(broken, "step-verification")
        stage["responsibilities"]["formal_verification"]["owner_seat"] = "step-executor-subagent"
        problems = protocol.validate_routing(broken)
        self.assertTrue(
            any("formal_verification owner must be controller" in p for p in problems), problems
        )


class PuaNarrowingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routing = protocol.load_routing()

    def test_reviewer_pua_is_guarded_audited_only(self):
        self.assertFalse(protocol.pua_required_for_role(self.routing, "reviewer", "normal"))
        self.assertTrue(protocol.pua_required_for_role(self.routing, "reviewer", "guarded"))
        self.assertTrue(protocol.pua_required_for_role(self.routing, "reviewer", "audited"))

    def test_unknown_rigor_fails_closed_for_reviewer(self):
        self.assertTrue(protocol.pua_required_for_role(self.routing, "reviewer", None))

    def test_worker_never_requires_a_pua_card(self):
        for rigor in ("normal", "guarded", "audited", None):
            self.assertFalse(protocol.pua_required_for_role(self.routing, "worker", rigor))

    def test_test_author_and_step_executor_require_pua_at_audited(self):
        # test-freeze and step-verification are audited-only stages; the seat
        # does not exist at lighter rigor, so no PUA duty is invented there.
        for role in ("test-author", "step-executor"):
            self.assertTrue(protocol.pua_required_for_role(self.routing, role, "audited"))
            self.assertTrue(protocol.pua_required_for_role(self.routing, role, None))
            self.assertFalse(protocol.pua_required_for_role(self.routing, role, "normal"))

    def test_goal_finish_card_is_audited_only(self):
        self.assertEqual(protocol.pua_stage_card(self.routing, "goal-finish", "audited"), "goal-finish")
        self.assertIsNone(protocol.pua_stage_card(self.routing, "goal-finish", "guarded"))
        self.assertIsNone(protocol.pua_stage_card(self.routing, "goal-finish", "normal"))

    def test_review_verdict_card_narrowed_to_guarded_audited(self):
        self.assertEqual(
            protocol.pua_stage_card(self.routing, "review-verdict", "guarded"), "review-verdict"
        )
        self.assertIsNone(protocol.pua_stage_card(self.routing, "review-verdict", "normal"))


class ReviewerConditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routing = protocol.load_routing()

    def test_review_verdict_normal_is_risk_triggered(self):
        condition = protocol.reviewer_condition(self.routing, "review-verdict", "normal")
        self.assertFalse(condition["mandatory"])
        self.assertEqual(condition.get("normal_trigger"), "risk-triggered")

    def test_review_verdict_guarded_is_mandatory(self):
        condition = protocol.reviewer_condition(self.routing, "review-verdict", "guarded")
        self.assertTrue(condition["dispatch"])
        self.assertTrue(condition["mandatory"])
        self.assertFalse(condition["blocking"])

    def test_audited_independence_reviews_block(self):
        for stage_id in ("contract-release", "slice-acceptance"):
            condition = protocol.reviewer_condition(self.routing, stage_id, "audited")
            self.assertTrue(condition["blocking"], stage_id)
            self.assertTrue(condition["mandatory"], stage_id)

    def test_goal_finish_is_mandatory_for_guarded_audited_and_risk_triggered_for_normal(self):
        for rigor in ("guarded", "audited"):
            condition = protocol.reviewer_condition(self.routing, "goal-finish", rigor)
            self.assertTrue(condition["dispatch"], rigor)
            self.assertTrue(condition["mandatory"], rigor)
        normal = protocol.reviewer_condition(self.routing, "goal-finish", "normal")
        self.assertTrue(normal["dispatch"])
        self.assertFalse(normal["mandatory"])
        self.assertEqual(normal.get("normal_trigger"), "risk-triggered")

    def test_unknown_rigor_string_fails_closed_for_pua(self):
        self.assertTrue(protocol.pua_required_for_role(self.routing, "reviewer", "Normal"))
        entry = next(
            item for item in protocol.stage_definition(self.routing, "review-verdict")["required_skills"]
            if item["name"] == "pua"
        )
        self.assertTrue(protocol.pua_applies(entry, "BOGUS"))

    def test_stage_card_is_role_aware(self):
        self.assertEqual(
            protocol.pua_stage_card(self.routing, "slice-acceptance", "audited", role="reviewer"),
            "review-verdict",
        )
        self.assertEqual(
            protocol.pua_stage_card(self.routing, "slice-acceptance", "audited", role="controller"),
            "slice-acceptance",
        )
        self.assertEqual(
            protocol.pua_stage_cards(self.routing, "slice-acceptance", "audited"),
            ["review-verdict", "slice-acceptance"],
        )

    def test_goal_validation_is_not_an_audited_stage(self):
        self.assertIsNone(protocol.pua_stage_card(self.routing, "goal-validation", "audited"))
        entries = protocol.required_skills_for_stage(self.routing, "goal-validation", "audited")
        self.assertFalse(any(entry["name"] == "pua" for entry in entries))
        guarded = protocol.required_skills_for_stage(self.routing, "goal-validation", "guarded")
        self.assertTrue(any(entry["name"] == "pua" for entry in guarded))

    def test_goal_verification_has_a_routing_stage(self):
        self.assertEqual(
            protocol.pua_stage_card(self.routing, "goal-verification", "audited"), "goal-verification"
        )
        self.assertIsNone(protocol.pua_stage_card(self.routing, "goal-verification", "normal"))

    def test_slice_implementation_has_no_reviewer_dispatch(self):
        for rigor in ("normal", "guarded", "audited"):
            condition = protocol.reviewer_condition(self.routing, "slice-implementation", rigor)
            self.assertFalse(condition["dispatch"])


if __name__ == "__main__":
    unittest.main()

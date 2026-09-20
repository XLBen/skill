"""WP8 taxonomy and design-trigger contracts.

- operational/governance risk factors map to the correct minimum rigor;
- architecture exploration triggers on durable consequences, not only on
  multiple visible options;
- the risk-to-test matrix exists and is wired into test-author.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from scripts import check  # noqa: E402


def goal_with(factors, rigor):
    _, goal = check.read_artifact(ROOT / "tests/fixtures/goal-valid.md", "goal")
    goal["rigor"] = rigor
    goal["risk"] = {"factors": factors, "rationale": "taxonomy test"}
    return goal


class RiskTaxonomyTests(unittest.TestCase):
    def test_fixture_goal_stays_valid(self):
        _, goal = check.read_artifact(ROOT / "tests/fixtures/goal-valid.md", "goal")
        self.assertEqual(check.validate_goal(goal), [])

    def test_new_high_risk_factors_require_audited(self):
        for factor in ("availability", "data-loss", "compliance", "supply-chain"):
            with self.subTest(factor=factor):
                problems = check.validate_goal(goal_with([factor], "guarded"))
                self.assertTrue(any("audited" in problem for problem in problems), problems)
                self.assertEqual(check.validate_goal(goal_with([factor], "audited")), [])

    def test_production_change_requires_guarded(self):
        problems = check.validate_goal(goal_with(["production-change"], "normal"))
        self.assertTrue(any("guarded" in problem for problem in problems), problems)
        self.assertEqual(check.validate_goal(goal_with(["production-change"], "guarded")), [])

    def test_unknown_factor_is_rejected(self):
        problems = check.validate_goal(goal_with(["quantum"], "audited"))
        self.assertTrue(any("known factors" in problem for problem in problems), problems)


class DesignTriggerTests(unittest.TestCase):
    def test_brainstorming_triggers_on_durable_consequences(self):
        text = (ROOT / "brainstorming/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("长期接口", text)
        self.assertIn("质量属性场景", text)
        self.assertIn("fitness 检查", text)

    def test_test_author_points_to_the_risk_matrix_and_it_exists(self):
        skill = (ROOT / "test-author/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/risk-test-matrix.md", skill)
        matrix = (ROOT / "test-author/references/risk-test-matrix.md").read_text(encoding="utf-8")
        for technique in ("property-based", "fuzz", "contract testing", "fault injection"):
            self.assertIn(technique, matrix)
        self.assertIn("never adds product requirements", matrix)


if __name__ == "__main__":
    unittest.main()

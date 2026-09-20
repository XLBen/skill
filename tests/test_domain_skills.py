"""WP9 conditional domain-skill contracts.

The four conditional capabilities must exist as real skills, be registered in
the routing authority with valid insertion points, and be wired into the
workflow entry points that trigger them.
"""

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import workflow_protocol as protocol  # noqa: E402

SKILLS = {
    "security-assurance": ["references/threat-model.md", "references/assurance-handoff.md"],
    "production-readiness": ["references/release-readiness.md", "references/operations-handoff.md"],
    "incident-response": ["references/incident-protocol.md"],
    "outcome-learning": ["references/experiment-protocol.md"],
}


class SkillFilesTests(unittest.TestCase):
    def test_skill_directories_have_matching_frontmatter(self):
        for name, references in SKILLS.items():
            with self.subTest(skill=name):
                skill_md = ROOT / name / "SKILL.md"
                self.assertTrue(skill_md.is_file(), skill_md)
                text = skill_md.read_text(encoding="utf-8")
                self.assertIn(f"name: {name}", text)
                self.assertIn("description:", text)
                for reference in references:
                    self.assertTrue((ROOT / name / reference).is_file(), reference)

    def test_skills_are_conditional_not_always_on(self):
        for name in SKILLS:
            text = (ROOT / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("When To Use", text)
            self.assertTrue("边界" in text or "Boundaries" in text, name)


class RoutingRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routing = protocol.load_routing()

    def test_all_capabilities_registered(self):
        names = [entry["name"] for entry in protocol.domain_capabilities(self.routing)]
        for name in SKILLS:
            self.assertIn(name, names)

    def test_insertion_filter(self):
        fix_entries = protocol.domain_capabilities(self.routing, "fix-entry")
        self.assertEqual([entry["name"] for entry in fix_entries], ["incident-response"])
        finish_entries = {
            entry["name"] for entry in protocol.domain_capabilities(self.routing, "goal-finish")
        }
        self.assertEqual(
            finish_entries, {"security-assurance", "production-readiness", "outcome-learning"}
        )

    def test_unknown_insertion_token_is_rejected(self):
        broken = copy.deepcopy(self.routing)
        broken["domain_capabilities"]["capabilities"][0]["insertion"] = ["nope-stage"]
        problems = protocol.validate_routing(broken)
        self.assertTrue(any("unknown insertion token" in p for p in problems), problems)


class EntryPointHookTests(unittest.TestCase):
    def test_systematic_debugging_routes_production_impact_to_incident_response(self):
        text = (ROOT / "systematic-debugging/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("incident-response", text)
        self.assertIn("先加载", text)

    def test_grill_points_to_outcome_learning_for_value_hypotheses(self):
        text = (ROOT / "grill/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("outcome-learning", text)

    def test_orchestration_mentions_the_domain_registry(self):
        text = (ROOT / "mvp-delivery/references/subagent-orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("domain_capabilities", text)
        for name in SKILLS:
            self.assertIn(name, text)

    def test_readmes_list_the_new_skills(self):
        for relative in ("README.md", "README.en.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            for name in SKILLS:
                self.assertIn(name, text, f"{relative} misses {name}")


if __name__ == "__main__":
    unittest.main()

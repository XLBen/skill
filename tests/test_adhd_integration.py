from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdhdIntegrationTests(unittest.TestCase):
    def test_skill_has_internal_output_contract_and_upstream_boundary(self):
        skill = (ROOT / "i-have-adhd/SKILL.md").read_text(encoding="utf-8")
        readme = (ROOT / "i-have-adhd/README.md").read_text(encoding="utf-8")
        upstream = (ROOT / "i-have-adhd/UPSTREAM.md").read_text(encoding="utf-8")
        self.assertIn("name: i-have-adhd", skill)
        self.assertIn('public-command: "none"', skill)
        self.assertIn("ACCEPTANCE_HANDOFF", skill)
        self.assertIn("ayghri/i-have-adhd", readme)
        self.assertIn("6f1f982d0a47c65899af3c5a7450b7098bc65325", upstream)

    def test_command_wrappers_load_the_output_layer(self):
        for command in ("build", "fix", "grill", "plan", "resume"):
            with self.subTest(command=command):
                text = (ROOT / f".opencode/commands/{command}.md").read_text(encoding="utf-8")
                self.assertIn("i-have-adhd", text)

    def test_acceptance_chain_keeps_full_handoff_and_reviewer_result(self):
        mvp = (ROOT / "mvp-delivery/SKILL.md").read_text(encoding="utf-8")
        reviewer = (ROOT / "reviewer/SKILL.md").read_text(encoding="utf-8")
        pua = (ROOT / "pua/SKILL.md").read_text(encoding="utf-8")
        protocol = (ROOT / "contract-review/references/reviewer-protocol.md").read_text(encoding="utf-8")
        for text in (mvp, reviewer, pua, protocol):
            with self.subTest(text=text[:30]):
                self.assertIn("ACCEPTANCE_HANDOFF", text)
                self.assertIn("pua_stage_id", text)
        self.assertIn("acceptance-preview", mvp)
        self.assertIn("pua_acceptance", reviewer)
        self.assertIn('"result": "satisfied|repair|owner|blocked"', pua)
        self.assertIn("acceptance-item", protocol)
        stage_checks = (ROOT / "pua/references/stage-checks.md").read_text(encoding="utf-8")
        self.assertIn("not-applicable", stage_checks)
        self.assertIn("无契约 Normal/Guarded handoff", stage_checks)

    def test_converge_review_precedes_slice_owner_acceptance(self):
        construction = (ROOT / "construction/SKILL.md").read_text(encoding="utf-8")
        converge = construction.index("skill for a `converge-audit`")
        owner_gate = construction.index("### PUA Acceptance: `slice-acceptance`")
        self.assertLess(converge, owner_gate)
        self.assertEqual(
            construction[converge:owner_gate].count("pua_stage_id: review-verdict"),
            1,
        )
        self.assertIn("pua_stage_id: slice-acceptance", construction[owner_gate:])


if __name__ == "__main__":
    unittest.main()

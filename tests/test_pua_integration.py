from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STAGES = (
    "brief-final",
    "goal-validation",
    "contract-release",
    "plan-confirmation",
    "test-freeze",
    "step-verification",
    "slice-acceptance",
    "review-verdict",
    "goal-verification",
    "goal-finish",
)


class PuaIntegrationTests(unittest.TestCase):
    def test_all_stage_cards_are_declared(self):
        skill = (ROOT / "pua/SKILL.md").read_text(encoding="utf-8")
        cards = (ROOT / "pua/references/stage-checks.md").read_text(encoding="utf-8")
        for stage in STAGES:
            with self.subTest(stage=stage):
                self.assertIn(f"`{stage}`", cards)
                self.assertIn(stage, skill)

    def test_stage_hosts_expose_explicit_acceptance_hooks(self):
        hooks = {
            "grill/SKILL.md": ("brief-final",),
            "mvp-delivery/SKILL.md": (
                "goal-validation",
                "slice-acceptance",
                "goal-verification",
                "goal-finish",
            ),
            "contract-review/SKILL.md": ("contract-release", "plan-confirmation"),
            "construction/SKILL.md": (
                "test-freeze",
                "step-verification",
                "slice-acceptance",
            ),
            "test-author/SKILL.md": ("test-freeze",),
            "step-executor/SKILL.md": ("step-verification",),
            "reviewer/SKILL.md": ("review-verdict",),
        }
        for relative, stages in hooks.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(path=relative):
                self.assertIn("PUA Acceptance", text)
                for stage in stages:
                    self.assertIn(f"`{stage}`", text)

    def test_pua_is_internal_only(self):
        text = (ROOT / "pua/SKILL.md").read_text(encoding="utf-8")
        self.assertIn('public-command: "none"', text)
        self.assertIn("加载 skill 不会创造独立", text)


if __name__ == "__main__":
    unittest.main()

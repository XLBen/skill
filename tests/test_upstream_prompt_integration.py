"""The upstream prompts are loaded unchanged and coding seats receive them."""

import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import engineering_delivery  # noqa: E402
import product_observation  # noqa: E402


class UpstreamPromptTests(unittest.TestCase):
    def test_original_skill_prompts_are_byte_identical_to_pinned_upstream_blobs(self):
        for skill, expected in (
            ("stop-that-shit", "a98a87d73ceccd7137f392cb0e97221e0a0f983c"),
            ("ponytail", "02c0712c86277d49d18a77da3a2b825657bf02d1"),
            ("skill-creator", "65b3a402dbd09b8e83f9d637c6b553875189085c"),
            ("receiving-code-review", "950da7b74bf6dbed6b8726d12ddadd65a9f5fda7"),
            ("frontend-design", "a5333457c414d20d625f307df945842c0952ecc3"),
            ("vercel-react-best-practices", "237988de4a66dd8a71d30a2c24ebe1a86b58d04e"),
        ):
            with self.subTest(skill=skill):
                data = (ROOT / skill / "SKILL.md").read_bytes()
                blob = b"blob " + str(len(data)).encode() + b"\0" + data
                self.assertEqual(hashlib.sha1(blob).hexdigest(), expected)

    def test_coding_seats_load_original_ponytail_and_sts_is_conditional(self):
        routing = json.loads((ROOT / "mvp-delivery/references/stage-routing.json").read_text(encoding="utf-8"))
        stages = {stage["stage_id"]: stage for stage in routing["stages"]}
        for stage_id, seat in (
            ("goal-validation", "controller"),
            ("slice-implementation", "controller"),
            ("slice-implementation", "worker-subagent"),
            ("slice-implementation", "step-executor-subagent"),
            ("test-freeze", "test-author-subagent"),
            ("step-verification", "step-executor-subagent"),
        ):
            with self.subTest(stage=stage_id, seat=seat):
                self.assertTrue(any(item["name"] == "ponytail" and item["seat"] == seat
                                    for item in stages[stage_id]["required_skills"]))
        self.assertTrue(any(item["name"] == "stop-that-shit" for item in
                            routing["domain_capabilities"]["capabilities"]))
        self.assertFalse(any(item["name"] == "stop-that-shit" for stage in stages.values()
                             for item in stage["required_skills"]))

    def test_observation_default_uses_real_journeys_without_waiving_existing_requirements(self):
        no_ui = engineering_delivery.default_observation_spec(set())
        browser = engineering_delivery.default_observation_spec({"O-01"})
        self.assertFalse(no_ui["required"])
        self.assertTrue(no_ui["reason"] and no_ui["basis"])
        self.assertTrue(browser["required"])

    def test_prepare_plan_publishes_conditional_observation_and_keeps_explicit_choice(self):
        for boundary, explicitly_required, expected in (
            ("cli", None, False),
            ("browser", None, True),
            ("cli", {"required": True, "reason": "Cross-journey state must be observed"}, True),
        ):
            with self.subTest(boundary=boundary, explicitly_required=explicitly_required):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    card = root / "goal.md"
                    goal = {"id": "G-TEST", "status": "active", "outcomes": [{"status": "pending"}]}
                    if explicitly_required is not None:
                        goal["product_observation"] = explicitly_required
                    plan = {"boundaries": [{"id": "B-01", "kind": boundary}],
                            "journeys": [{"boundary_ids": ["B-01"], "outcome_ids": ["O-01"]}]}
                    (root / "plan.md").write_text(json.dumps(plan), encoding="utf-8")
                    engine = SimpleNamespace(
                        read_artifact=lambda *_: ("", goal),
                        goal_project_root=lambda *_: root,
                        GOAL_ID_RE=re.compile(r"G-[A-Z]+"),
                        ValidationError=ValueError,
                        parse_block=lambda raw, _: json.loads(raw),
                        goal_definition_hash=lambda value: hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest(),
                        render_goal=lambda value: json.dumps(value),
                        validate_goal_artifact=lambda path: ("", {}, product_observation.observation_spec_problems(json.loads(path.read_text(encoding="utf-8")))),
                    )
                    with mock.patch.object(engineering_delivery.planning_readiness, "publication_guard"), \
                            mock.patch.object(engineering_delivery, "readable_plan", return_value="generated-view\n"):
                        engineering_delivery.prepare(card, "plan.md", engine)
                    published = json.loads(card.read_text(encoding="utf-8"))
                    self.assertIs(published["product_observation"]["required"], expected)
                    self.assertEqual(published["ui"]["required"], boundary == "browser")
                    if explicitly_required is not None:
                        self.assertEqual(published["product_observation"], explicitly_required)

    def test_conditional_skills_keep_upstream_references_and_command_routing(self):
        self.assertTrue((ROOT / "skill-creator/eval-viewer/generate_review.py").is_file())
        self.assertTrue((ROOT / "skill-creator/scripts/aggregate_benchmark.py").is_file())
        self.assertTrue((ROOT / "skill-creator/LICENSE.txt").is_file())
        self.assertTrue((ROOT / "frontend-design/LICENSE.txt").is_file())
        self.assertTrue((ROOT / "receiving-code-review/LICENSE").is_file())
        self.assertTrue((ROOT / "vercel-react-best-practices/rules/async-parallel.md").is_file())
        routed = {"skill-creator", "receiving-code-review", "frontend-design",
                  "vercel-react-best-practices"}
        for command in ("work", "plan", "build", "fix", "resume"):
            body = (ROOT / ".opencode/commands" / f"{command}.md").read_text(encoding="utf-8")
            with self.subTest(command=command):
                self.assertTrue(all(skill in body for skill in routed))
        routing = json.loads((ROOT / "mvp-delivery/references/stage-routing.json").read_text(encoding="utf-8"))
        capabilities = {item["name"]: item for item in routing["domain_capabilities"]["capabilities"]}
        self.assertTrue(routed <= capabilities.keys())
        self.assertFalse(any(item["name"] in routed for stage in routing["stages"]
                             for item in stage["required_skills"]))


if __name__ == "__main__":
    unittest.main()

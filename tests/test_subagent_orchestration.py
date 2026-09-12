from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

AGENTS = {
    "mvp-researcher": {"mode: subagent", "task: deny", "edit: deny"},
    "mvp-worker": {
        "mode: subagent",
        "task: deny",
        "edit:",
        '".opencode/mvp/**": deny',
        '"docs/audit-slices/**": deny',
    },
    "mvp-reviewer": {"mode: subagent", "task: deny", "edit: deny", "bash: deny"},
    "mvp-test-author": {
        "mode: subagent",
        "task: deny",
        '"*": deny',
        '"docs/test-manifests/**": allow',
    },
    "mvp-step-executor": {
        "mode: subagent",
        "task: deny",
        '"docs/**": deny',
        '".opencode/mvp/**": deny',
    },
}


class OrchestrationProtocolTests(unittest.TestCase):
    def test_reference_files_exist_and_define_the_matrix(self):
        orchestration = (ROOT / "mvp-delivery/references/subagent-orchestration.md").read_text(encoding="utf-8")
        templates = (ROOT / "mvp-delivery/references/subagent-templates.md").read_text(encoding="utf-8")
        for token in (
            "Dispatch Trigger Matrix",
            "Role To Agent Mapping",
            "Dispatch Preflight",
            "Concurrency Rules",
            "Fresh Session Semantics",
            "Dispatch Record",
            "Failure Branches",
            "dispatch.json",
        ):
            self.assertIn(token, orchestration)
        for token in ("DISPATCH", "RESULT", "FIX-ROUND", "needs_context", "blocked"):
            self.assertIn(token, templates)

    def test_controller_mandates_delegation_and_removes_cost_discretion(self):
        mvp = (ROOT / "mvp-delivery/SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("只在风险值得其成本", mvp)
        self.assertIn("能力可用即必须", mvp)
        self.assertIn("references/subagent-orchestration.md", mvp)
        self.assertIn("references/subagent-templates.md", mvp)
        self.assertIn("capability-unavailable", mvp)
        self.assertIn("mechanical-batch", mvp)
        self.assertIn("task-worker", mvp)

    def test_worker_delegation_is_part_of_build_loop(self):
        mvp = (ROOT / "mvp-delivery/SKILL.md").read_text(encoding="utf-8")
        marker = "实质实现任务默认派 worker 子代理"
        self.assertIn(marker, mvp)

    def test_task_worker_skill_exists_with_controller_contract(self):
        skill = (ROOT / "task-worker/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: task-worker", skill)
        self.assertIn("called-by: \"mvp-delivery\"", skill)
        self.assertIn("write_scope", skill)
        self.assertIn("needs_context", skill)
        self.assertIn("不派发其他子代理", skill)


class AgentDefinitionTests(unittest.TestCase):
    def test_all_project_agents_exist_with_expected_boundaries(self):
        for name, required in AGENTS.items():
            with self.subTest(agent=name):
                text = (ROOT / f".opencode/agents/{name}.md").read_text(encoding="utf-8")
                for token in required:
                    self.assertIn(token, text)
                self.assertIn("description:", text)
                self.assertNotIn("model:", text)

    def test_agents_reference_their_skills(self):
        pairs = {
            "mvp-worker": "task-worker",
            "mvp-reviewer": "reviewer",
            "mvp-test-author": "test-author",
            "mvp-step-executor": "step-executor",
        }
        for agent, skill in pairs.items():
            with self.subTest(agent=agent):
                text = (ROOT / f".opencode/agents/{agent}.md").read_text(encoding="utf-8")
                self.assertIn(f"`name: {skill}`", text)


class EntryIntegrationTests(unittest.TestCase):
    def test_command_wrappers_reference_the_orchestration_protocol(self):
        for command in ("build", "fix", "plan", "resume"):
            with self.subTest(command=command):
                text = (ROOT / f".opencode/commands/{command}.md").read_text(encoding="utf-8")
                self.assertIn("subagent-orchestration.md", text)
        fix = (ROOT / ".opencode/commands/fix.md").read_text(encoding="utf-8")
        self.assertIn("research seat", fix)

    def test_construction_and_reviewer_protocol_map_to_project_agents(self):
        construction = (ROOT / "construction/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("subagent-orchestration.md", construction)
        self.assertIn("`mvp-step-executor`", construction)
        self.assertIn("`direct` profile overrides interaction settings", construction)
        protocol = (ROOT / "contract-review/references/reviewer-protocol.md").read_text(encoding="utf-8")
        self.assertIn("`mvp-reviewer`", protocol)
        self.assertIn("subagent-orchestration.md", protocol)

    def test_reviewer_description_covers_lightweight_and_whole_goal_review(self):
        reviewer = (ROOT / "reviewer/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("mvp-delivery", reviewer)
        self.assertIn("whole-goal finish", reviewer)


if __name__ == "__main__":
    unittest.main()

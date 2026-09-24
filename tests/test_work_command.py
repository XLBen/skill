"""Contracts for the autonomous /work entry point and its existing workflow hooks."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WorkCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.command = (ROOT / ".opencode/commands/work.md").read_text(encoding="utf-8")
        cls.skill = (ROOT / "work/SKILL.md").read_text(encoding="utf-8")

    def test_command_is_an_autonomous_goal_entry(self):
        self.assertIn("description:", self.command)
        self.assertIn("agent: build", self.command)
        self.assertIn("$ARGUMENTS", self.command)
        self.assertIn(
            "without handing the user another command", " ".join(self.command.split())
        )
        self.assertIn("mvp-delivery/references/subagent-orchestration.md", self.command)

    def test_dynamic_skill_discovery_has_no_fixed_allowlist(self):
        self.assertIn("运行时实际可见的**全部现有 skill**", self.skill)
        self.assertIn("禁止维护一份需要手工更新的 work skill 名称清单", self.skill)
        self.assertIn("新加入且当前会话可见的 skill 自动纳入候选", self.skill)
        routing = (ROOT / "mvp-delivery/references/stage-routing.json").read_text(encoding="utf-8")
        self.assertIn("work-entry", routing)

    def test_vague_goals_use_inference_without_fabricating_confirmation(self):
        for text in (self.command, self.skill):
            with self.subTest(text=text[:24]):
                self.assertIn("assumption", text)
        self.assertIn("Work Inference Mode", self.skill)
        self.assertIn("不得伪称用户答复", self.skill)
        self.assertIn("覆盖维度有空缺", self.skill)
        self.assertIn("强制提问", self.skill)
        self.assertIn("真实 owner 决定", self.skill)

    def test_artifacts_are_not_created_as_ceremony_but_formal_gates_remain(self):
        self.assertIn("不因访谈/计划/内部状态而新建文档", self.skill)
        self.assertIn("正式 gate", self.skill)
        self.assertIn("无文件", self.skill)
        self.assertIn("所有原始必需结果均已验证", self.skill)

    def test_existing_skills_return_control_to_work(self):
        grill = (ROOT / "grill/SKILL.md").read_text(encoding="utf-8")
        planner = (ROOT / "writing-plans/SKILL.md").read_text(encoding="utf-8")
        delivery = (ROOT / "mvp-delivery/SKILL.md").read_text(encoding="utf-8")
        resume = (ROOT / ".opencode/commands/resume.md").read_text(encoding="utf-8")
        self.assertIn("direct `/grill` still requires real owner", grill)
        self.assertIn("下一步运行 `/build`", planner)
        self.assertIn("交接终点", planner)
        self.assertIn("不得把控制权交还给用户", delivery)
        self.assertIn("started through `/work`", resume)


if __name__ == "__main__":
    unittest.main()

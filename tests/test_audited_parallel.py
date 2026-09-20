"""Audited DAG parallel admission tests.

These verify the strict admission rules for running PLAN steps in isolated
worktrees and the real git integration flow:

- independent steps with provably disjoint scopes are admissible;
- step/unit dependencies, overlapping scopes, protected acceptance paths,
  duplicate assignments and writer-limit overflow all fall back to serial;
- two isolated patches integrate serially into one workspace and the
  out-of-scope change check still gates before integration.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import worktree_tasks as wt  # noqa: E402


def git(repo, *args):
    process = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace",
    )
    if process.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {process.stderr}")
    return process.stdout


def make_plan(path, steps, unit_dag=None):
    plan = {
        "steps": steps,
        "unit_dag": unit_dag or [],
    }
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def step(step_id, unit=None, depends_on=None):
    return {
        "id": step_id,
        "unit": unit or step_id,
        "variant": "base",
        "depends_on_segments": depends_on or [],
        "verifications": [],
    }


class ParallelPlanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.plan = make_plan(
            self.root / "PLAN.json",
            [
                step("S-01", "U-01"),
                step("S-02", "U-02"),
                step("S-03", "U-03", depends_on=["S-01"]),
            ],
            unit_dag=[("U-03", "U-02")],
        )

    def batch(self, tasks):
        return tasks

    def test_independent_disjoint_scopes_are_admissible(self):
        problems = wt.parallel_plan_problems(
            self.plan,
            [
                {"task_id": "T-A", "step_ids": ["S-01"], "write_scope": ["src/a/**"]},
                {"task_id": "T-B", "step_ids": ["S-02"], "write_scope": ["src/b/**"]},
            ],
        )
        self.assertEqual(problems, [])

    def test_step_dependency_falls_back_to_serial(self):
        problems = wt.parallel_plan_problems(
            self.plan,
            [
                {"task_id": "T-A", "step_ids": ["S-01"], "write_scope": ["src/a/**"]},
                {"task_id": "T-B", "step_ids": ["S-03"], "write_scope": ["src/b/**"]},
            ],
        )
        self.assertTrue(any("dependency" in problem for problem in problems), problems)

    def test_unit_dependency_falls_back_to_serial(self):
        problems = wt.parallel_plan_problems(
            self.plan,
            [
                {"task_id": "T-A", "step_ids": ["S-02"], "write_scope": ["src/a/**"]},
                {"task_id": "T-B", "step_ids": ["S-03"], "write_scope": ["src/b/**"]},
            ],
        )
        self.assertTrue(any("dependency" in problem for problem in problems), problems)

    def test_overlapping_scopes_fall_back_to_serial(self):
        problems = wt.parallel_plan_problems(
            self.plan,
            [
                {"task_id": "T-A", "step_ids": ["S-01"], "write_scope": ["src/shared/**"]},
                {"task_id": "T-B", "step_ids": ["S-02"], "write_scope": ["src/shared/util.py"]},
            ],
        )
        self.assertTrue(any("overlapping" in problem for problem in problems), problems)

    def test_protected_paths_are_rejected(self):
        problems = wt.parallel_plan_problems(
            self.plan,
            [
                {"task_id": "T-A", "step_ids": ["S-01"], "write_scope": ["tests/**"]},
                {"task_id": "T-B", "step_ids": ["S-02"], "write_scope": ["src/b/**"]},
            ],
            protected=["tests/**"],
        )
        self.assertTrue(any("protected" in problem for problem in problems), problems)

    def test_writer_limit_falls_back_to_serial(self):
        problems = wt.parallel_plan_problems(
            self.plan,
            [
                {"task_id": "T-A", "step_ids": ["S-01"], "write_scope": ["src/a/**"]},
                {"task_id": "T-B", "step_ids": ["S-02"], "write_scope": ["src/b/**"]},
                {"task_id": "T-C", "step_ids": ["S-03"], "write_scope": ["src/c/**"]},
            ],
            max_writers=2,
        )
        self.assertTrue(any("writer limit" in problem for problem in problems), problems)

    def test_duplicate_assignment_and_unknown_step(self):
        problems = wt.parallel_plan_problems(
            self.plan,
            [
                {"task_id": "T-A", "step_ids": ["S-01"], "write_scope": ["src/a/**"]},
                {"task_id": "T-B", "step_ids": ["S-01"], "write_scope": ["src/b/**"]},
            ],
        )
        self.assertTrue(any("assigned to both" in problem for problem in problems), problems)
        problems = wt.parallel_plan_problems(
            self.plan,
            [{"task_id": "T-A", "step_ids": ["S-99"], "write_scope": ["src/a/**"]}],
        )
        self.assertTrue(any("unknown PLAN step" in problem for problem in problems), problems)

    def test_report_shape_and_cli(self):
        tasks = [
            {"task_id": "T-A", "step_ids": ["S-01"], "write_scope": ["src/a/**"]},
            {"task_id": "T-B", "step_ids": ["S-02"], "write_scope": ["src/b/**"]},
        ]
        report = wt.parallel_plan(self.plan, tasks)
        self.assertEqual(report["schema"], "workflow-parallel-plan/1")
        self.assertTrue(report["admissible"])
        self.assertIn("fallback", report["rules"])

        tasks_file = self.root / "batch.json"
        tasks_file.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
        out = self.root / "report.json"
        code = wt._main(
            [
                "parallel-plan",
                "--plan",
                str(self.plan),
                "--tasks",
                str(tasks_file),
                "--protected",
                "tests/**",
            ]
        )
        self.assertEqual(code, 0)

        tasks_file.write_text(
            json.dumps(
                {
                    "tasks": [
                        {"task_id": "T-A", "step_ids": ["S-01"], "write_scope": ["tests/**"]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        code = wt._main(
            ["parallel-plan", "--plan", str(self.plan), "--tasks", str(tasks_file),
             "--protected", "tests/**"]
        )
        self.assertEqual(code, 1)


class RealGitIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "-c", "user.email=t@example.com", "-c", "user.name=Tester", "init")
        (self.repo / "src").mkdir()
        (self.repo / "src" / "base.py").write_text("value = 0\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "-c", "user.email=t@example.com", "-c", "user.name=Tester",
            "commit", "-m", "base")
        self.work_root = self.root / "worktrees"

    def test_two_isolated_patches_integrate_serially(self):
        created_a = wt.create_task(self.repo, "T-A", self.work_root)
        created_b = wt.create_task(self.repo, "T-B", self.work_root)
        (Path(created_a["worktree"]) / "src" / "a.py").write_text("a = 1\n", encoding="utf-8")
        (Path(created_b["worktree"]) / "src" / "b.py").write_text("b = 2\n", encoding="utf-8")

        patch_a = self.root / "a.patch"
        patch_b = self.root / "b.patch"
        collected_a = wt.collect_patch(Path(created_a["worktree"]), patch_a)
        collected_b = wt.collect_patch(Path(created_b["worktree"]), patch_b)
        self.assertEqual(wt.scope_problems(collected_a["changed"], ["src/a.py"]), [])
        self.assertEqual(wt.scope_problems(collected_b["changed"], ["src/b.py"]), [])

        wt.apply_patch(self.repo, patch_a)
        wt.apply_patch(self.repo, patch_b)
        self.assertEqual((self.repo / "src" / "a.py").read_text(encoding="utf-8"), "a = 1\n")
        self.assertEqual((self.repo / "src" / "b.py").read_text(encoding="utf-8"), "b = 2\n")

        wt.cleanup(Path(created_a["worktree"]), self.repo, integrated=True)
        wt.cleanup(Path(created_b["worktree"]), self.repo, integrated=True)
        worktrees = git(self.repo, "worktree", "list", "--porcelain")
        self.assertNotIn("T-A", worktrees)
        self.assertNotIn("T-B", worktrees)

    def test_out_of_scope_parallel_change_is_rejected_before_integration(self):
        created = wt.create_task(self.repo, "T-A", self.work_root)
        (Path(created["worktree"]) / "src" / "sneaky.py").write_text("x = 1\n", encoding="utf-8")
        collected = wt.collect_patch(Path(created["worktree"]))
        problems = wt.scope_problems(collected["changed"], ["src/allowed/**"])
        self.assertTrue(any("outside the declared write scope" in problem for problem in problems))

    def test_conflicting_patch_is_refused_at_apply(self):
        created_a = wt.create_task(self.repo, "T-A", self.work_root)
        created_b = wt.create_task(self.repo, "T-B", self.work_root)
        (Path(created_a["worktree"]) / "src" / "base.py").write_text(
            "value = 111\n", encoding="utf-8"
        )
        (Path(created_b["worktree"]) / "src" / "base.py").write_text(
            "value = 222\n", encoding="utf-8"
        )
        patch_a = self.root / "a.patch"
        patch_b = self.root / "b.patch"
        wt.collect_patch(Path(created_a["worktree"]), patch_a)
        wt.collect_patch(Path(created_b["worktree"]), patch_b)
        wt.apply_patch(self.repo, patch_a)
        with self.assertRaises(wt.WorktreeError):
            wt.apply_patch(self.repo, patch_b)
        # the first patch remains; the conflicting second patch never applied
        self.assertEqual(
            (self.repo / "src" / "base.py").read_text(encoding="utf-8"), "value = 111\n"
        )


if __name__ == "__main__":
    unittest.main()

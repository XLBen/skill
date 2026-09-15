"""Isolated worktree helper tests.

These exercise the real git behavior on temporary repositories:

- a task worktree isolates writes from the integration workspace;
- collected patches integrate added, modified, renamed and binary files;
- out-of-scope changes are reported before integration;
- a dirty integration workspace blocks patch application;
- un-integrated work is never silently discarded.
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


class WorktreeTestCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "-c", "user.email=t@example.com", "-c", "user.name=Tester", "init")
        (self.repo / "product.py").write_text("value = 1\n", encoding="utf-8")
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_product.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "-c", "user.email=t@example.com", "-c", "user.name=Tester",
            "commit", "-m", "base")
        self.work_root = self.root / "worktrees"

    def create(self, task="T-01"):
        return wt.create_task(self.repo, task, self.work_root)


class IsolationTests(WorktreeTestCase):
    def test_task_worktree_isolates_writes_until_apply(self):
        created = self.create()
        task_dir = Path(created["worktree"])
        (task_dir / "product.py").write_text("value = 2\n", encoding="utf-8")
        self.assertEqual((self.repo / "product.py").read_text(encoding="utf-8"), "value = 1\n")
        collected = wt.collect_patch(task_dir, self.root / "T-01.patch")
        self.assertIn("product.py", [entry["path"] for entry in collected["changed"]])
        applied = wt.apply_patch(self.repo, Path(collected["patch"]))
        self.assertTrue(applied["applied"])
        self.assertEqual((self.repo / "product.py").read_text(encoding="utf-8"), "value = 2\n")

    def test_new_and_binary_files_survive_the_round_trip(self):
        created = self.create()
        task_dir = Path(created["worktree"])
        (task_dir / "feature.py").write_text("new = True\n", encoding="utf-8")
        blob = bytes([0, 1, 2, 255, 254, 0, 7])
        (task_dir / "asset.bin").write_bytes(blob)
        collected = wt.collect_patch(task_dir, self.root / "patch.diff")
        wt.apply_patch(self.repo, Path(collected["patch"]))
        self.assertEqual((self.repo / "feature.py").read_text(encoding="utf-8"), "new = True\n")
        self.assertEqual((self.repo / "asset.bin").read_bytes(), blob)

    def test_rename_between_scoped_directories_integrates(self):
        created = self.create()
        task_dir = Path(created["worktree"])
        (task_dir / "tests" / "test_product.py").rename(task_dir / "tests" / "test_renamed.py")
        collected = wt.collect_patch(task_dir, self.root / "rename.patch")
        paths = [entry["path"] for entry in collected["changed"]]
        self.assertIn("tests/test_renamed.py", paths)
        problems = wt.scope_problems(collected["changed"], ["tests/*"])
        self.assertEqual(problems, [])
        wt.apply_patch(self.repo, Path(collected["patch"]))
        self.assertTrue((self.repo / "tests" / "test_renamed.py").is_file())
        self.assertFalse((self.repo / "tests" / "test_product.py").is_file())


class ScopeTests(WorktreeTestCase):
    def test_out_of_scope_change_is_reported(self):
        created = self.create()
        task_dir = Path(created["worktree"])
        (task_dir / "product.py").write_text("value = 3\n", encoding="utf-8")
        (task_dir / "unrelated.txt").write_text("oops\n", encoding="utf-8")
        entries = wt.changed_entries(task_dir)
        problems = wt.scope_problems(entries, ["product.py"])
        self.assertTrue(any("unrelated.txt" in problem for problem in problems), problems)
        self.assertFalse(any("product.py is outside" in problem for problem in problems), problems)

    def test_cross_boundary_rename_is_out_of_scope(self):
        created = self.create()
        task_dir = Path(created["worktree"])
        (task_dir / "tests" / "test_product.py").rename(task_dir / "moved_elsewhere.py")
        entries = wt.changed_entries(task_dir)
        problems = wt.scope_problems(entries, ["tests/*"])
        self.assertTrue(any("moved_elsewhere.py" in problem for problem in problems), problems)

    def test_empty_scope_is_a_problem(self):
        created = self.create()
        task_dir = Path(created["worktree"])
        (task_dir / "product.py").write_text("value = 4\n", encoding="utf-8")
        problems = wt.scope_problems(wt.changed_entries(task_dir), [])
        self.assertEqual(problems, ["no write scope declared"])


class AdmissionAndCleanupTests(WorktreeTestCase):
    def test_dirty_workspace_blocks_new_isolation(self):
        created = self.create()
        task_dir = Path(created["worktree"])
        (task_dir / "product.py").write_text("value = 5\n", encoding="utf-8")
        wt.collect_patch(task_dir, self.root / "p.patch")
        (self.repo / "product.py").write_text("value = 99\n", encoding="utf-8")
        problems = wt.admission_problems(self.repo)
        self.assertTrue(any("not clean" in problem for problem in problems), problems)
        with self.assertRaisesRegex(wt.WorktreeError, "admission failed"):
            wt.create_task(self.repo, "T-03", self.work_root)

    def test_conflicting_patch_is_rejected_but_serial_batch_integrates(self):
        first = wt.create_task(self.repo, "T-01", self.work_root)
        second = wt.create_task(self.repo, "T-02", self.work_root)
        (Path(first["worktree"]) / "product.py").write_text("value = 5\n", encoding="utf-8")
        (Path(second["worktree"]) / "feature.py").write_text("new = True\n", encoding="utf-8")
        patch_a = self.root / "a.patch"
        patch_b = self.root / "b.patch"
        wt.collect_patch(Path(first["worktree"]), patch_a)
        wt.collect_patch(Path(second["worktree"]), patch_b)
        wt.apply_patch(self.repo, patch_a)
        # The workspace is dirty with the first patch, yet an unrelated second
        # patch still integrates: cleanliness gates isolation, not integration.
        wt.apply_patch(self.repo, patch_b)
        self.assertEqual((self.repo / "product.py").read_text(encoding="utf-8"), "value = 5\n")
        self.assertEqual((self.repo / "feature.py").read_text(encoding="utf-8"), "new = True\n")

        third = wt.create_task(self.repo, "T-04", self.work_root, allow_dirty=True)
        (Path(third["worktree"]) / "product.py").write_text("value = 6\n", encoding="utf-8")
        conflicting = self.root / "c.patch"
        wt.collect_patch(Path(third["worktree"]), conflicting)
        with self.assertRaises(wt.WorktreeError):
            wt.apply_patch(self.repo, conflicting)
        self.assertEqual((self.repo / "product.py").read_text(encoding="utf-8"), "value = 5\n")

    def test_create_refuses_dirty_workspace_unless_allowed(self):
        (self.repo / "product.py").write_text("value = 7\n", encoding="utf-8")
        with self.assertRaisesRegex(wt.WorktreeError, "admission failed"):
            wt.create_task(self.repo, "T-02", self.work_root)
        created = wt.create_task(self.repo, "T-02", self.work_root, allow_dirty=True)
        self.assertTrue(Path(created["worktree"]).is_dir())

    def test_cleanup_refuses_unintegrated_work(self):
        created = self.create()
        task_dir = Path(created["worktree"])
        (task_dir / "product.py").write_text("value = 8\n", encoding="utf-8")
        with self.assertRaisesRegex(wt.WorktreeError, "un-integrated"):
            wt.cleanup(task_dir, self.repo)
        result = wt.cleanup(task_dir, self.repo, discard=True)
        self.assertEqual(len(result["discarded_changes"]), 1)
        self.assertFalse(task_dir.exists())

    def test_cleanup_accepts_integrated_confirmation(self):
        created = self.create()
        task_dir = Path(created["worktree"])
        (task_dir / "product.py").write_text("value = 9\n", encoding="utf-8")
        collected = wt.collect_patch(task_dir, self.root / "i.patch")
        wt.apply_patch(self.repo, Path(collected["patch"]))
        result = wt.cleanup(task_dir, self.repo, integrated=True)
        self.assertTrue(result["confirmed_integrated"])
        self.assertEqual(result["discarded_changes"], [])
        self.assertFalse(task_dir.exists())


if __name__ == "__main__":
    unittest.main()

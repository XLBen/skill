import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import wf  # noqa: E402

EXAMPLE = ROOT / "plan" / "references" / "example-plan.md"

MINI = """# mini

## 共享接口
无

## 错误策略
无

## 任务

### T01 第一步
- [ ] 完成
依赖: 无
文件: a.txt(新增，空)
验证:
```bash
{t01}
```
完成标准: ok

### T02 第二步
- [ ] 完成
依赖: T01
文件: b.txt
验证:
```bash
# 注释行会被跳过
{py} -c "import sys; \\
sys.exit(0)"
```
完成标准: ok
"""


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        Path("docs").mkdir()

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def write(self, t01=None):
        py = f'"{sys.executable}"'
        text = MINI.format(t01=t01 or f"{py} -c \"print('ok')\"", py=py)
        Path("docs/plan.md").write_text(text, encoding="utf-8")

    def run_wf(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = wf.main(list(args))
        return code, out.getvalue()


class ParseTest(unittest.TestCase):
    def test_example_plan_passes_lint(self):
        plan = wf.Plan(EXAMPLE)
        errors, _ = wf.lint(plan)
        self.assertEqual(errors, [])
        self.assertEqual(list(plan.tasks), ["T01", "T02", "T03", "T04"])
        self.assertTrue(plan.tasks["T03"].milestone)
        self.assertEqual(plan.tasks["T02"].deps, ["T01"])
        self.assertIn("wordfreq/__init__.py", plan.tasks["T01"].files)
        self.assertEqual(len(plan.tasks["T01"].files), 4)

    def test_package_contains_shared_sections_and_only_current_task(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            wf.main(["--plan", str(EXAMPLE), "task", "T02"])
        text = out.getvalue()
        for heading in ("## 背景", "## 约定", "## 共享接口", "## 错误策略", "### T02"):
            self.assertIn(heading, text)
        self.assertNotIn("### T03", text)
        self.assertNotIn("## 架构", text)


class FlowTest(Workspace):
    def test_continuation_and_comments(self):
        self.write()
        plan = wf.Plan(Path("docs/plan.md"))
        self.assertEqual(len(plan.commands(plan.tasks["T02"])), 1)
        self.assertEqual(plan.tasks["T01"].files, ["a.txt"])

    def test_done_requires_passing_verify(self):
        self.write()
        code, out = self.run_wf("done", "T01")
        self.assertEqual(code, 1)
        self.assertEqual(self.run_wf("verify", "T01")[0], 0)
        code, out = self.run_wf("done", "T01")
        self.assertEqual(code, 0)
        self.assertIn("下一个: T02", out)
        self.assertIn("- [x] 完成", Path("docs/plan.md").read_text(encoding="utf-8"))

    def test_failed_verify_blocks_done(self):
        self.write(t01=f'"{sys.executable}" -c "raise SystemExit(3)"')
        code, out = self.run_wf("verify", "T01")
        self.assertEqual(code, 1)
        self.assertIn("FAIL (exit 3)", out)
        self.assertEqual(self.run_wf("done", "T01")[0], 1)

    def test_changed_commands_require_reverify(self):
        self.write()
        self.run_wf("verify", "T01")
        self.write(t01=f'"{sys.executable}" -c "print(1)"')
        code, out = self.run_wf("done", "T01")
        self.assertEqual(code, 1)
        self.assertIn("重新 verify", out)

    def test_next_respects_dependencies(self):
        self.write()
        code, out = self.run_wf("next")
        self.assertIn("T01", out)
        self.assertNotIn("T02", out)

    def test_lint_catches_common_mistakes(self):
        Path("docs/plan.md").write_text(
            "## 任务\n\n### T01 x\n依赖: T02\n验证:\n```bash\necho ok\n```\nTODO\n\n### T02 y\n- [ ] 完成\n文件: a, b, c, d, e\n",
            encoding="utf-8")
        errors, warnings = wf.lint(wf.Plan(Path("docs/plan.md")))
        joined = "\n".join(errors)
        for needle in ("共享接口", "错误策略", "状态行", "排在它后面", "没有断言", "占位", "T02: 缺少验证命令"):
            self.assertIn(needle, joined)
        self.assertTrue(any("5 个文件" in w for w in warnings))

    def test_diffcheck_flags_scope_and_defensive_code(self):
        self.write()
        subprocess.run(["git", "init", "-q"], check=True)
        Path("a.txt").write_text("", encoding="utf-8")
        Path("extra.py").write_text("try:\n    x = d.get('k', {})\nexcept Exception:\n    pass\n", encoding="utf-8")
        Path("tests").mkdir()
        Path("tests/test_x.py").write_text("try:\n    pass\nexcept Exception:\n    pass\n", encoding="utf-8")
        code, out = self.run_wf("diffcheck", "T01")
        self.assertEqual(code, 0)
        self.assertIn("未声明的改动: extra.py", out)
        self.assertIn("[try/except] extra.py", out)
        self.assertIn("[静默回退] extra.py", out)
        self.assertNotIn("tests/test_x.py: try", out)


PARALLEL = """## 共享接口
无

## 错误策略
无

## 任务

### T01 a
- [ ] 完成
文件: a.txt
验证:
```bash
python -c "assert open('a.txt').read() == 'A'"
```

### T02 b
- [ ] 完成
文件: b.txt
验证:
```bash
python -c "assert open('b.txt').read() == 'B'"
```

### T03 also a
- [ ] 完成
文件: a.txt
验证:
```bash
python -c "print(1)"
```
"""


def git(*args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True, capture_output=True)


class LifecycleTest(Workspace):
    def setUp(self):
        super().setUp()
        Path("docs/plan.md").write_text(PARALLEL, encoding="utf-8")
        Path(".gitignore").write_text(".wf/\n", encoding="utf-8")
        git("init", "-q")
        git("add", "-A")
        git("commit", "-qm", "init")

    def test_python_prefix_uses_current_interpreter(self):
        self.assertIn(sys.executable, wf.portable("python -m unittest"))
        self.assertIn(sys.executable, wf.portable("python3 x.py"))
        self.assertEqual(wf.portable("pythonic.sh"), "pythonic.sh")

    def test_parallel_batch_skips_overlapping_files(self):
        code, out = self.run_wf("next", "--all")
        self.assertIn("T01", out)
        self.assertIn("T02", out)
        self.assertNotIn("T03", out)

    def test_reopen_regress_and_impact(self):
        Path("a.txt").write_text("A", encoding="utf-8")
        self.run_wf("verify", "T01")
        self.run_wf("done", "T01")
        self.assertEqual(self.run_wf("regress")[0], 0)
        Path("a.txt").write_text("changed", encoding="utf-8")
        code, out = self.run_wf("regress")
        self.assertEqual(code, 1)
        self.assertIn("失败: T01", out)
        self.assertIn("T01", self.run_wf("impact", "a.txt")[1])
        self.run_wf("reopen", "T01")
        self.assertNotIn("[x]", Path("docs/plan.md").read_text(encoding="utf-8"))
        self.assertEqual(self.run_wf("done", "T01")[0], 1)

    def test_worktree_merge(self):
        self.assertEqual(self.run_wf("wt-add", "T01")[0], 0)
        self.assertEqual(self.run_wf("wt-add", "T02")[0], 0)
        Path(".wf/worktrees/T01/a.txt").write_text("A", encoding="utf-8")
        Path(".wf/worktrees/T02/b.txt").write_text("B", encoding="utf-8")
        self.assertEqual(self.run_wf("verify", "T01", "--cwd", ".wf/worktrees/T01")[0], 0)
        self.assertEqual(self.run_wf("wt-merge", "T01")[0], 0)
        self.assertEqual(self.run_wf("wt-merge", "T02")[0], 0)
        self.assertEqual(Path("a.txt").read_text(encoding="utf-8"), "A")
        self.assertEqual(Path("b.txt").read_text(encoding="utf-8"), "B")
        self.assertFalse(Path(".wf/worktrees/T01").exists())

    def test_worktree_conflict_leaves_main_clean(self):
        self.run_wf("wt-add", "T01")
        self.run_wf("wt-add", "T03")
        Path(".wf/worktrees/T01/a.txt").write_text("A", encoding="utf-8")
        Path(".wf/worktrees/T03/a.txt").write_text("other", encoding="utf-8")
        self.assertEqual(self.run_wf("wt-merge", "T01")[0], 0)
        code, out = self.run_wf("wt-merge", "T03")
        self.assertEqual(code, 1)
        self.assertIn("冲突", out)
        self.assertEqual(Path("a.txt").read_text(encoding="utf-8"), "A")
        self.assertEqual(wf.dirty_files(), [])
        self.assertEqual(self.run_wf("wt-drop", "T03")[0], 0)

    def test_check_section_runs_on_verify_and_regress(self):
        plan = Path("docs/plan.md")
        plan.write_text(PARALLEL.replace("## 任务", '## 检查\n```bash\npython -c "import pathlib; assert \'bad\' not in pathlib.Path(\'a.txt\').read_text()"\n```\n\n## 任务'),
                        encoding="utf-8")
        Path("a.txt").write_text("A", encoding="utf-8")
        self.assertIn("## 检查", self.run_wf("task", "T01")[1])
        self.assertEqual(self.run_wf("verify", "T02")[0], 1)  # b.txt 不存在，任务命令先失败
        Path("b.txt").write_text("B", encoding="utf-8")
        self.assertEqual(self.run_wf("verify", "T02")[0], 0)
        self.assertEqual(self.run_wf("done", "T02")[0], 0)
        Path("a.txt").write_text("bad", encoding="utf-8")
        code, out = self.run_wf("verify", "T01")
        self.assertEqual(code, 1)  # 任务命令也会失败，但检查必定失败
        code, out = self.run_wf("regress")
        self.assertIn("失败: 检查", out)

    def test_changed_check_section_requires_reverify(self):
        Path("a.txt").write_text("A", encoding="utf-8")
        self.run_wf("verify", "T01")
        plan = Path("docs/plan.md")
        plan.write_text(PARALLEL.replace("## 任务", '## 检查\n```bash\npython -c "print(1)"\n```\n\n## 任务'), encoding="utf-8")
        code, out = self.run_wf("done", "T01")
        self.assertEqual(code, 1)
        self.assertIn("检查", out)

    def test_lint_warns_about_non_portable_commands(self):
        Path("docs/plan.md").write_text(PARALLEL.replace('python -c "print(1)"', "grep -q x a.txt"), encoding="utf-8")
        _, warnings = wf.lint(wf.Plan(Path("docs/plan.md")))
        self.assertTrue(any("Windows" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()

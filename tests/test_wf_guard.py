import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / ".opencode" / "plugins" / "wf-guard.js"

# 用 Node 直接调用插件的钩子，模拟 OpenCode 的调用顺序；输出每一步的结果。
DRIVER = """
import { WfGuard } from %(plugin)s
const hooks = await WfGuard({ directory: %(dir)s })
const results = []
const env = { env: {} }
await hooks["shell.env"]({ cwd: %(dir)s }, env)
results.push(["tmpdir", env.env.TMPDIR])
async function bash(command, exit, output, sessionID = "s1") {
  const args = { command }
  try {
    await hooks["tool.execute.before"]({ tool: "bash", sessionID, callID: "c" }, { args })
  } catch (error) {
    results.push(["blocked", command])
    return
  }
  results.push(["ran", args.command])
  await hooks["tool.execute.after"]({ tool: "bash", sessionID, callID: "c", args }, { title: "", output, metadata: { exit } })
}
await bash("echo hi > /tmp/a.txt", 0, "")
const failing = "python check.py"
for (let i = 0; i < 4; i++) await bash(failing, 1, "boom")
await bash("for i in 1 2; do python check.py; done", 0, "")
await bash(failing + '; echo "EXIT=$?"', 0, "boom\\nEXIT=1", "s2")
await bash(failing + '; echo "EXIT=$?"', 0, "boom\\nEXIT=1", "s2")
await bash(failing + '; echo "EXIT=$?"', 0, "boom\\nEXIT=1", "s2")
await bash(failing + '; echo "EXIT=$?"', 0, "boom\\nEXIT=1", "s2")
await hooks["tool.execute.after"]({ tool: "edit", sessionID: "s2", callID: "c", args: {} }, { title: "", output: "", metadata: {} })
await bash(failing, 1, "boom", "s2")
console.log(JSON.stringify(results))
"""


@unittest.skipUnless(shutil.which("node"), "需要 node")
class WfGuardTest(unittest.TestCase):
    def run_driver(self):
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "driver.mjs"
            script.write_text(DRIVER % {"plugin": json.dumps(PLUGIN.as_uri()), "dir": json.dumps(d)}, encoding="utf-8")
            out = subprocess.run(["node", str(script)], capture_output=True, text=True, check=True).stdout
            return d, json.loads(out)

    def test_guard_behaviour(self):
        d, results = self.run_driver()
        self.assertEqual(results[0], ["tmpdir", str(Path(d) / ".wf" / "tmp")])
        self.assertEqual(results[1], ["ran", "echo hi > .wf/tmp/a.txt"])
        kinds = [kind for kind, _ in results[2:]]
        # 失败 3 次可以运行，第 4 次被拦；循环重试被拦
        self.assertEqual(kinds[:5], ["ran", "ran", "ran", "blocked", "blocked"])
        # `; echo EXIT=$?` 让退出码变成 0，也要识别为失败；改过代码之后重新计数
        self.assertEqual(kinds[5:], ["ran", "ran", "ran", "blocked", "ran"])


if __name__ == "__main__":
    unittest.main()

// wf-guard：把两条容易被模型“说服自己绕过去”的规则变成机械检查。
// 1. 临时文件留在项目内：所有 shell 命令的 TMPDIR/TMP/TEMP 指向 .wf/tmp/，命令里的 /tmp/ 改写成 .wf/tmp/。
//    OpenCode 默认不允许访问项目外的目录，非交互运行时会直接拒绝，子代理也会因此中止。
// 2. 同一条命令连续失败 3 次（中间没有改过代码、也没有派发子代理）就拦住第 4 次；循环重试一条失败过的命令也拦住。
import { mkdirSync } from "node:fs"
import { join } from "node:path"

const MAX_FAILURES = 3
const CHANGE_TOOLS = new Set(["edit", "write", "patch", "multiedit", "task"])

// 去掉 `; echo "EXIT=$?"`、`2>&1`、重定向等外壳，只留命令本身，用来判断“是不是同一条命令”
function core(command) {
  return String(command)
    .replace(/;\s*echo\b[^;&|]*\$\?.*$/s, "")
    .replace(/\s\d?>>?\s*\S+/g, "")
    .replace(/\s+/g, " ")
    .trim()
}

function failed(metadata, output) {
  if (metadata && typeof metadata.exit === "number" && metadata.exit !== 0) return true
  // `cmd; echo "exit=$?"` 会让退出码变成 0，所以也看输出
  return /\b(exit|EXIT)\s*[=:]\s*[1-9]/.test(output) || /^Traceback \(most recent call last\)/m.test(output)
}

export const WfGuard = async ({ directory }) => {
  const tmp = join(directory, ".wf", "tmp")
  mkdirSync(tmp, { recursive: true })
  const sessions = new Map() // sessionID → { last, streak, failedCommands }
  const state = (id) => {
    if (!sessions.has(id)) sessions.set(id, { last: "", streak: 0, failedCommands: new Set() })
    return sessions.get(id)
  }

  return {
    "shell.env": async (_input, output) => {
      output.env.TMPDIR = tmp
      output.env.TMP = tmp
      output.env.TEMP = tmp
    },

    "tool.execute.before": async (input, output) => {
      if (input.tool !== "bash" || !output.args?.command) return
      output.args.command = output.args.command.replace(/(^|[\s"'=>(])\/tmp\//g, "$1.wf/tmp/")
      const s = state(input.sessionID)
      const command = core(output.args.command)
      if (s.last === command && s.streak >= MAX_FAILURES) {
        throw new Error(
          `wf-guard: 这条命令已经连续失败 ${s.streak} 次，中间没有改过代码，不再允许重试。` +
            "按 debug skill 的“修不好的时候”停下来，用阻塞格式把证据和选项交给用户；“可能是暂时的”不是继续重试的理由。",
        )
      }
      if (/\b(for|while|until)\b/.test(command) && [...s.failedCommands].some((c) => c && command.includes(c))) {
        throw new Error("wf-guard: 不要用循环重试一条已经失败过的命令。每次重试单独运行，连续失败 3 次就停下来汇报。")
      }
    },

    "tool.execute.after": async (input, output) => {
      const s = state(input.sessionID)
      if (CHANGE_TOOLS.has(input.tool)) {
        s.last = ""
        s.streak = 0
        s.failedCommands.clear()
        return
      }
      if (input.tool !== "bash") return
      const command = core(input.args?.command ?? "")
      if (failed(output.metadata, output.output ?? "")) {
        s.streak = s.last === command ? s.streak + 1 : 1
        s.failedCommands.add(command)
      } else {
        s.streak = 0
      }
      s.last = command
    },
  }
}

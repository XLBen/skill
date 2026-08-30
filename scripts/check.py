#!/usr/bin/env python3
"""论文/施工计划结构自检器（thesis-defense × construction）。

用法：
  python scripts/check.py thesis docs/thesis.md
  python scripts/check.py plan docs/PLAN.md --thesis docs/thesis.md
  python scripts/check.py --selftest        # 跑 tests/fixtures 正反样例

无第三方依赖。退出码：0 = 通过；1 = 发现问题；2 = 用法/文件错误。
"""
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

STATUS_T = {"draft", "defending", "passed", "conditional", "redefending"}
PHASE_T = {"questioning", "answering", "reviewing", "idle"}
DEPTH_T = {"轻量", "标准", "严酷"}
STATUS_P = {"planning", "building", "done", "paused", "suspended"}
ID_RE = re.compile(r"\b([PDARVB])-(\d{2,})\b")
A_STATE = ("已验证", "待验证", "纯假设")


def fail(msg):
    print(f"  ✗ {msg}")
    return 1


def ok(msg):
    print(f"  ✓ {msg}")


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = {}
    for line in parts[1].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, parts[2]


def sections(body):
    out, cur = {}, None
    for line in body.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            out.setdefault(cur, [])
        elif cur is not None:
            out[cur].append(line)
    return out


def check_thesis(path):
    print(f"[thesis] {path}")
    text = Path(path).read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    problems = 0

    for key in ("project", "version", "status", "phase", "depth", "rounds", "date"):
        if key not in meta:
            problems += fail(f"frontmatter 缺 {key}")
    if meta.get("status") not in STATUS_T:
        problems += fail(f"status 非法：{meta.get('status')}")
    if meta.get("phase") not in PHASE_T:
        problems += fail(f"phase 非法：{meta.get('phase')}")
    if meta.get("depth") not in DEPTH_T:
        problems += fail(f"depth 非法：{meta.get('depth')}")
    if not problems:
        ok(f"frontmatter 完整（status={meta.get('status')} depth={meta.get('depth')}）")

    sec = sections(body)
    census = {}
    for m in ID_RE.finditer(body):
        census.setdefault(m.group(1), set()).add(m.group(0))
    for p in "PDARVB":
        n = len(census.get(p, ()))
        print(f"  · {p}-xx 条目：{n}")
    if not census.get("P"):
        problems += fail("没有任何 P-xx 目标条目")
    if not census.get("V"):
        problems += fail("没有任何 V-xx 验证条目")

    a_sec = next((v for k, v in sec.items() if "假设" in k), [])
    bad_a = [ln.strip() for ln in a_sec
             if ID_RE.search(ln) and ln.strip().startswith("-")
             and ID_RE.search(ln).group(1) == "A"
             and not any(s in ln for s in A_STATE)]
    if bad_a:
        for ln in bad_a:
            problems += fail(f"§4 假设缺三态标注：{ln[:60]}")
    else:
        ok("§4 每条 A-xx 均有三态标注")

    v_sec = next((v for k, v in sec.items() if "验证" in k), [])
    v_exempt = ("≥", "≤", "返回", "帧", "ms", "毫秒", "%", "人工验收")
    bad_v = [ln.strip() for ln in v_sec
             if "V-" in ln
             and "`" not in ln
             and not any(t in ln for t in v_exempt)]
    if bad_v:
        for ln in bad_v:
            problems += fail(f"§6 验证无命令或可观察结果：{ln[:60]}")
    else:
        ok("§6 每条 V-xx 有命令或可观察结果")

    return problems


def parse_steps(body):
    steps = []
    for ln in body.splitlines():
        m = re.match(r"^- \[( |x)\] (S[\d-]*[a-z]?)", ln)
        if m:
            void = "~~" in ln or "作废" in ln
            steps.append({"checked": m.group(1) == "x", "id": m.group(2),
                          "void": void, "line": ln})
    return steps


def check_plan(path, thesis_path):
    print(f"[plan] {path}")
    text = Path(path).read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    problems = 0

    if meta.get("status") not in STATUS_P:
        problems += fail(f"status 非法：{meta.get('status')}")
    m = re.match(r"(docs/[\w/.-]+) @ v(\d+) \((passed|conditional)\)",
                 meta.get("thesis", ""))
    if not m:
        problems += fail(f"thesis 引用格式非法：{meta.get('thesis')!r}")
    else:
        ok(f"thesis 锚点：{m.group(1)} @ v{m.group(2)} ({m.group(3)})")

    steps = [s for s in parse_steps(body)]
    if not steps:
        problems += fail("没有解析到任何 S 步骤")
    live = [s for s in steps if not s["void"]]

    for s in live:
        if s["checked"] and not re.search(r"20\d{2}-\d{2}-\d{2}", s["line"]):
            problems += fail(f"已勾步骤缺日期：{s['id']}")
        if "验收" not in s["line"]:
            problems += fail(f"步骤缺验收字段：{s['id']}")
    ok(f"步骤解析 {len(steps)} 条（含作废 {len(steps) - len(live)}）")

    seen_unchecked = False
    for s in live:
        if not s["checked"]:
            seen_unchecked = True
        elif seen_unchecked:
            problems += fail(f"串行被破坏：{s['id']} 已勾但其前有未勾步骤")
    if not problems:
        ok("勾选保持串行（已勾只出现在未勾之前）")

    thesis_text = ""
    if thesis_path and Path(thesis_path).exists():
        thesis_text = Path(thesis_path).read_text(encoding="utf-8")
    for s in live:
        fm = re.search(r"来源：([^|]+)", s["line"])
        if not fm:
            problems += fail(f"步骤缺来源字段：{s['id']}")
            continue
        for tok in ID_RE.findall(fm.group(1)):
            ident = f"{tok[0]}-{tok[1]}"
            if thesis_text and ident not in thesis_text:
                problems += fail(f"{s['id']} 来源悬空：{ident} 不在论文中")
    if thesis_text and not problems:
        ok("全部 来源 引用都能在论文中找到")

    return problems


def selftest():
    print("== selftest：正例应过，反例应挂 ==")
    bad = 0
    bad += 0 if check_thesis(FIXTURES / "thesis-valid.md") == 0 else 1
    bad += 0 if check_plan(FIXTURES / "plan-valid.md",
                           str(FIXTURES / "thesis-valid.md")) == 0 else 1
    rc = check_thesis(FIXTURES / "thesis-invalid.md")
    if rc == 0:
        bad += fail("thesis-invalid.md 应当报错却通过了")
    else:
        ok("thesis-invalid.md 按预期报错")
    rc = check_plan(FIXTURES / "plan-invalid.md",
                    str(FIXTURES / "thesis-valid.md"))
    if rc == 0:
        bad += fail("plan-invalid.md 应当报错却通过了")
    else:
        ok("plan-invalid.md 按预期报错")
    print("selftest " + ("FAIL" if bad else "PASS"))
    return 1 if bad else 0


def main(argv):
    if "--selftest" in argv:
        return selftest()
    if len(argv) < 3 or argv[1] not in ("thesis", "plan"):
        print(__doc__)
        return 2
    try:
        if argv[1] == "thesis":
            return 1 if check_thesis(argv[2]) else 0
        thesis = None
        if "--thesis" in argv:
            thesis = argv[argv.index("--thesis") + 1]
        return 1 if check_plan(argv[2], thesis) else 0
    except FileNotFoundError as e:
        print(f"文件不存在：{e}")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

#!/usr/bin/env python3
"""按项目类型启用 extras，避免无关 skill 占用上下文。

    python .opencode/skills.py list                 列出档案和当前启用情况
    python .opencode/skills.py use backend frontend 只启用这些档案（不带参数 = 只用核心）
    python .opencode/skills.py add release          在当前基础上追加档案

核心 skill 始终启用。实现方式是改写项目 opencode.json 的 permission.skill：
所选档案中的 extras 设为 allow，其余 extras 设为 deny（deny 的 skill 对 agent 不可见）。
不在本仓库中的 skill 条目保持不变。修改后需要重启 OpenCode。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MANIFEST = ".opencode/wf-install.json"


def find_repo(target: Path) -> Path:
    """工作流仓库的位置：安装记录里的 repo，或者脚本本身所在的仓库。"""
    manifest = target / MANIFEST
    if manifest.is_file():
        return Path(json.loads(manifest.read_text(encoding="utf-8"))["repo"])
    here = Path(__file__).resolve().parent.parent
    if (here / "extras" / "profiles.json").is_file():
        return here
    raise SystemExit(f"找不到工作流仓库：{manifest} 不存在。先运行 install.py")


def skill_names(root: Path) -> list[str]:
    return sorted(d.name for d in root.iterdir() if (d / "SKILL.md").is_file())


def load_profiles(repo: Path) -> dict[str, dict]:
    return json.loads((repo / "extras" / "profiles.json").read_text(encoding="utf-8"))


def permissions(repo: Path, active: list[str]) -> dict[str, str]:
    profiles = load_profiles(repo)
    unknown = [p for p in active if p not in profiles]
    if unknown:
        raise SystemExit(f"没有这些档案: {', '.join(unknown)}；可选: {', '.join(profiles)}")
    enabled = {s for p in active for s in profiles[p]["skills"]}
    result = {name: "allow" for name in skill_names(repo)}
    result.update({name: "allow" if name in enabled else "deny" for name in skill_names(repo / "extras")})
    return result


def current_profiles(target: Path) -> list[str]:
    manifest = target / MANIFEST
    if not manifest.is_file():
        return []
    return json.loads(manifest.read_text(encoding="utf-8")).get("profiles", [])


def apply(target: Path, repo: Path, active: list[str]) -> None:
    rules = permissions(repo, active)
    json_path, jsonc_path = target / "opencode.json", target / "opencode.jsonc"
    if jsonc_path.exists() and not json_path.exists():
        print("目标使用 opencode.jsonc（为保留注释不自动修改），请把下面的条目合并进 permission.skill：")
        print(json.dumps(rules, ensure_ascii=False, indent=2))
    else:
        config = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else {}
        skill_rules = config.setdefault("permission", {}).setdefault("skill", {})
        if not isinstance(skill_rules, dict):  # permission.skill 也可以是单个字符串，例如 "allow"
            skill_rules = config["permission"]["skill"] = {"*": skill_rules}
        skill_rules.update(rules)
        json_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = target / MANIFEST
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["profiles"] = active
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    enabled = sorted(n for n, v in rules.items() if v == "allow")
    print(f"已启用档案: {', '.join(active) or '无（只用核心）'}")
    print(f"可见的 skill（{len(enabled)} 个）: {', '.join(enabled)}")
    print("重启 OpenCode 后生效。")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", default=".", help="项目根目录（默认当前目录）")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    sub.add_parser("use").add_argument("profiles", nargs="*")
    sub.add_parser("add").add_argument("profiles", nargs="+")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    repo = find_repo(target)
    if args.command == "list":
        active = current_profiles(target)
        print(f"核心（始终启用）: {', '.join(skill_names(repo))}\n")
        for name, profile in load_profiles(repo).items():
            mark = "*" if name in active else " "
            print(f"[{mark}] {name:<11} {profile['说明']}: {', '.join(profile['skills'])}")
        return
    active = args.profiles if args.command == "use" else sorted(set(current_profiles(target)) | set(args.profiles))
    apply(target, repo, active)


if __name__ == "__main__":
    main()

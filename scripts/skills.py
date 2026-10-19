#!/usr/bin/env python3
"""按项目类型启用 extras 和 MCP 工具，避免无关的 skill 和工具说明占用上下文。

    python .opencode/skills.py list                        列出档案和当前启用情况
    python .opencode/skills.py use backend frontend        只启用这些档案（不带参数 = 只用核心）
    python .opencode/skills.py add release                 在当前基础上追加档案
    python .opencode/skills.py use automation --mcp godot  另外保留某个 MCP 服务器（例如你全局配置里的）

写入项目 opencode.json：
- permission.skill：所选档案的 extras 为 allow，其余 extras 为 deny（deny 的 skill 对 agent 不可见）。
- tools：所选档案的 MCP 服务器为 "<名字>_*": true，其余能找到的 MCP 服务器（项目、全局配置、extras/mcp.json）为 false。
- mcp：所选档案需要、但哪里都没定义的服务器，按 extras/mcp.json 补上定义。
- agent：worker 类子代理关闭全部 MCP 工具（worker-strong 保留 context7），reviewer 只保留浏览器和桌面工具。
不在本仓库管理范围内的条目保持不变。修改后需要重启 OpenCode。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MANIFEST = ".opencode/wf-install.json"
WORKER_AGENTS = ("worker", "worker-strong", "test-author", "backend-worker", "frontend-worker")
AGENT_MCP = {"worker-strong": {"context7"}, "reviewer": {"playwright", "computer-use"}}


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


def load_mcp_catalog(repo: Path) -> dict[str, dict]:
    path = repo / "extras" / "mcp.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def read_jsonc(path: Path) -> dict:
    """读 opencode.json / opencode.jsonc：去掉字符串外的注释和尾逗号。"""
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', lambda m: m.group(1) or "", text, flags=re.S)
    text = re.sub(r'("(?:\\.|[^"\\])*")|,(?=\s*[}\]])', lambda m: m.group(1) or "", text)
    return json.loads(text)


def global_mcp_servers() -> set[str]:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "opencode"
    names: set[str] = set()
    for name in ("opencode.json", "opencode.jsonc", "config.json"):
        names |= set((read_jsonc(base / name).get("mcp") or {}).keys())
    return names


def permissions(repo: Path, active: list[str]) -> dict[str, str]:
    profiles = load_profiles(repo)
    unknown = [p for p in active if p not in profiles]
    if unknown:
        raise SystemExit(f"没有这些档案: {', '.join(unknown)}；可选: {', '.join(profiles)}")
    enabled = {s for p in active for s in profiles[p]["skills"]}
    result = {name: "allow" for name in skill_names(repo)}
    result.update({name: "allow" if name in enabled else "deny" for name in skill_names(repo / "extras")})
    return result


def enabled_mcp(repo: Path, active: list[str], extra: list[str]) -> set[str]:
    profiles = load_profiles(repo)
    return {s for p in active for s in profiles[p].get("mcp", [])} | set(extra)


def read_manifest(target: Path) -> dict:
    manifest = target / MANIFEST
    return json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}


def current_profiles(target: Path) -> list[str]:
    return read_manifest(target).get("profiles", [])


def apply_config(config: dict, repo: Path, active: list[str], extra_mcp: list[str],
                 also_defined: set[str] = frozenset()) -> tuple[set[str], set[str]]:
    """改写 config（项目 opencode.json 的内容），返回（启用的 MCP，所有已知 MCP）。"""
    skill_rules = config.setdefault("permission", {}).setdefault("skill", {})
    if not isinstance(skill_rules, dict):  # permission.skill 也可以是单个字符串，例如 "allow"
        skill_rules = config["permission"]["skill"] = {"*": skill_rules}
    skill_rules.update(permissions(repo, active))

    catalog = load_mcp_catalog(repo)
    on = enabled_mcp(repo, active, extra_mcp)
    defined = set((config.get("mcp") or {}).keys()) | global_mcp_servers() | set(also_defined)
    known = defined | set(catalog) | on
    for name in sorted(on - defined):
        if name not in catalog:
            raise SystemExit(f"MCP 服务器 {name} 没有定义：先在 opencode.json 的 mcp 里配置它")
        config.setdefault("mcp", {})[name] = catalog[name]["config"]

    tools = config.setdefault("tools", {})
    for name in known:
        tools[f"{name}_*"] = name in on
    agents = config.setdefault("agent", {})
    for agent in (*WORKER_AGENTS, "reviewer"):
        allowed = AGENT_MCP.get(agent, set()) & on
        agent_tools = agents.setdefault(agent, {}).setdefault("tools", {})
        for name in known:
            agent_tools[f"{name}_*"] = name in allowed
    return on, known


def apply(target: Path, repo: Path, active: list[str], extra_mcp: list[str] | None = None) -> None:
    manifest_data = read_manifest(target)
    extra = extra_mcp if extra_mcp is not None else manifest_data.get("extra_mcp", [])
    json_path, jsonc_path = target / "opencode.json", target / "opencode.jsonc"
    if jsonc_path.exists() and not json_path.exists():
        preview: dict = {}
        existing = set((read_jsonc(jsonc_path).get("mcp") or {}).keys())
        on, known = apply_config(preview, repo, active, extra, existing)
        print("目标使用 opencode.jsonc（为保留注释不自动修改），请把下面的 permission.skill、tools、agent（以及 mcp）合并进去：")
        print(json.dumps(preview, ensure_ascii=False, indent=2))
    else:
        config = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else {}
        on, known = apply_config(config, repo, active, extra)
        json_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if manifest_data:
        manifest_data["profiles"] = active
        manifest_data["extra_mcp"] = extra
        (target / MANIFEST).write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    enabled = sorted(n for n, v in permissions(repo, active).items() if v == "allow")
    print(f"已启用档案: {', '.join(active) or '无（只用核心）'}")
    print(f"可见的 skill（{len(enabled)} 个）: {', '.join(enabled)}")
    print(f"开启的 MCP: {', '.join(sorted(on)) or '无'}；关闭的 MCP: {', '.join(sorted(known - on)) or '无'}")
    print("重启 OpenCode 后生效。")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", default=".", help="项目根目录（默认当前目录）")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    for name in ("use", "add"):
        cmd = sub.add_parser(name)
        cmd.add_argument("profiles", nargs="*" if name == "use" else "+")
        cmd.add_argument("--mcp", action="append", default=None, help="另外保留的 MCP 服务器名，可重复")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    repo = find_repo(target)
    if args.command == "list":
        active = current_profiles(target)
        print(f"核心（始终启用）: {', '.join(skill_names(repo))}\n")
        for name, profile in load_profiles(repo).items():
            mark = "*" if name in active else " "
            mcp = f"  MCP: {', '.join(profile.get('mcp', []))}" if profile.get("mcp") else ""
            print(f"[{mark}] {name:<11} {profile['说明']}: {', '.join(profile['skills'])}{mcp}")
        extra = read_manifest(target).get("extra_mcp", [])
        if extra:
            print(f"\n另外保留的 MCP: {', '.join(extra)}")
        return
    active = args.profiles if args.command == "use" else sorted(set(current_profiles(target)) | set(args.profiles))
    apply(target, repo, active, args.mcp)


if __name__ == "__main__":
    main()

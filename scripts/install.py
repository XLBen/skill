#!/usr/bin/env python3
"""把本仓库的工作流安装到一个 OpenCode 项目。

    python scripts/install.py <目标项目> [--no-extras] [--force]

安装内容：
  .opencode/commands/{grill,plan,build,resume}.md
  .opencode/agents/{worker,reviewer}.md
  .opencode/wf.py
  .opencode/workflow-routing.md（AGENTS.md 的副本，注册到 instructions）
  opencode.json 的 skills.paths 指向本仓库的 skill 目录（原地引用，改 skill 无需重装）

会清理 v1 安装留下的、未被手动修改过的文件（.opencode/workflow/ 下的 manifest 记录的那些）。
"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
MANIFEST = ".opencode/wf-install.json"
ROUTING = ".opencode/workflow-routing.md"
V1_MANIFEST = ".opencode/workflow/install-manifest.json"
V1_ROUTING = ".opencode/workflow/default-routing.md"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def skill_dirs(include_extras: bool) -> list[str]:
    roots = [REPO] + ([REPO / "extras"] if include_extras else [])
    return [d.as_posix() for root in roots for d in sorted(root.iterdir()) if (d / "SKILL.md").is_file()]


def v1_files(target: Path) -> dict[str, str]:
    """v1 manifest 的 key 相对于不同目录，换算成相对项目根的路径。"""
    manifest_path = target / V1_MANIFEST
    if not manifest_path.exists():
        return {}
    files = json.loads(manifest_path.read_text(encoding="utf-8")).get("files", {})
    return {(f".opencode/{key}" if key.split("/")[0] in ("commands", "agents", "plugins")
             else f".opencode/workflow/{key}"): digest for key, digest in files.items()}


def remove_v1(target: Path) -> list[str]:
    """删除 v1 安装器写入且之后没有被修改过的文件。"""
    files = v1_files(target)
    if not files:
        return []
    removed, kept = [], []
    for relative, digest in files.items():
        path = target / relative
        if not path.is_file():
            continue
        if sha(path) == digest:
            path.unlink()
            removed.append(relative)
        else:
            kept.append(relative)
    if kept:
        print(f"保留了被手动修改过的 v1 文件（确认无用后请手动删除）: {', '.join(kept)}")
    else:
        shutil.rmtree(target / ".opencode" / "workflow", ignore_errors=True)
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", help="目标项目根目录")
    parser.add_argument("--no-extras", action="store_true", help="不注册 extras/ 下的可选 skill")
    parser.add_argument("--force", action="store_true", help="覆盖不是本安装器写入的同名文件")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    if not target.is_dir():
        raise SystemExit(f"目标目录不存在: {target}")

    jobs = [(p, f".opencode/commands/{p.name}") for p in sorted((REPO / ".opencode/commands").glob("*.md"))]
    jobs += [(p, f".opencode/agents/{p.name}") for p in sorted((REPO / ".opencode/agents").glob("*.md"))]
    jobs += [(REPO / "scripts/wf.py", ".opencode/wf.py"), (REPO / "AGENTS.md", ROUTING)]

    manifest_path = target / MANIFEST
    owned = v1_files(target)
    if manifest_path.exists():
        owned.update(json.loads(manifest_path.read_text(encoding="utf-8")).get("files", {}))
    conflicts = [rel for src, rel in jobs
                 if (target / rel).exists() and sha(target / rel) not in (sha(src), owned.get(rel))]
    if conflicts and not args.force:
        raise SystemExit("这些文件已存在且不是本安装器写入的，加 --force 覆盖:\n  " + "\n  ".join(conflicts))

    removed = remove_v1(target)
    installed = {}
    for src, rel in jobs:
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        installed[rel] = sha(dest)
    manifest_path.write_text(json.dumps({"repo": REPO.as_posix(), "files": installed}, indent=2) + "\n", encoding="utf-8")

    paths = skill_dirs(not args.no_extras)
    json_path, jsonc_path = target / "opencode.json", target / "opencode.jsonc"
    if jsonc_path.exists() and not json_path.exists():
        print("目标使用 opencode.jsonc（为保留注释不自动修改），请手动合并：")
        print(f'  "skills": {{ "paths": {json.dumps(paths, ensure_ascii=False)} }}')
        print(f'  "instructions": [..., "{ROUTING}"]   并删除 "{V1_ROUTING}"（如有）')
    else:
        config = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else {}
        config.setdefault("$schema", "https://opencode.ai/config.json")
        skills = config.setdefault("skills", {})
        repo_prefix = REPO.as_posix()
        # 去掉以前指向本仓库的条目（包括 v1 的旧 skill），保留用户自己的
        kept = [p for p in skills.get("paths", []) if not (p == repo_prefix or p.startswith(repo_prefix + "/"))]
        missing = [p for p in kept if not Path(p).exists()]
        if missing:
            print(f"移除了不存在的 skill 路径: {', '.join(missing)}")
        kept = [p for p in kept if p not in missing]
        skills["paths"] = kept + paths
        instructions = [i for i in config.get("instructions", []) if i != V1_ROUTING]
        if ROUTING not in instructions and target != REPO:
            instructions.append(ROUTING)
        config["instructions"] = instructions
        json_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"已更新 {json_path.name}: {len(paths)} 个 skill 路径")

    gitignore = target / ".gitignore"
    if (target / ".git").exists() and ".wf/" not in (gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""):
        with gitignore.open("a", encoding="utf-8") as stream:
            stream.write("\n# wf.py 的验证记录\n.wf/\n")
        print("已在 .gitignore 中加入 .wf/")

    if removed:
        print(f"清理了 v1 文件 {len(removed)} 个")
    print(f"已安装: {', '.join(sorted(installed))}")
    print("在 .opencode/agents/worker.md 和 reviewer.md 里设置 model（见 models.md），然后重启 OpenCode。")


if __name__ == "__main__":
    main()

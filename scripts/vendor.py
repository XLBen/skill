#!/usr/bin/env python3
"""按 extras/upstream.json 从上游固定提交引入可选 skill。

    python scripts/vendor.py sync [名称...]    下载固定提交，覆盖 extras/<名称>/
    python scripts/vendor.py check             对比 extras/ 与固定提交，列出不一致
    python scripts/vendor.py outdated          列出上游有新提交的条目（升级时手动改 commit 再 sync）

upstream.json 每一项：
  repo        GitHub 仓库 owner/name
  commit      固定的提交号
  path        skill 目录在仓库中的路径
  shared      （可选）skill 引用的仓库级文件，复制到 references/，并把 ../../references/ 改写为 references/
  patched     （可选）本地有意修改的说明；check 时显示为“本地修改”而不是失败
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
EXTRAS = REPO / "extras"
MANIFEST = EXTRAS / "upstream.json"


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def fetch(repo: str, commit: str, cache: dict[tuple[str, str], Path], tmp: Path) -> Path:
    key = (repo, commit)
    if key not in cache:
        dest = tmp / f"{repo.replace('/', '_')}-{commit[:8]}"
        dest.mkdir()
        git("init", "-q", cwd=dest)
        git("fetch", "-q", "--depth", "1", f"https://github.com/{repo}.git", commit, cwd=dest)
        git("checkout", "-q", "FETCH_HEAD", cwd=dest)
        cache[key] = dest
    return cache[key]


def build(name: str, entry: dict, source: Path, out: Path) -> None:
    """把上游 skill 组装到 out：复制目录、带上共享引用文件、写 UPSTREAM.md。"""
    shutil.copytree(source / entry["path"], out)
    license_file = next((source / n for n in ("LICENSE", "LICENSE.md", "LICENSE.txt") if (source / n).is_file()), None)
    if license_file and not any(out.glob("LICENSE*")):
        shutil.copyfile(license_file, out / "LICENSE")  # MIT 要求保留版权声明
    for shared in entry.get("shared", []):
        target = out / "references" / Path(shared).name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(source / shared, target)
    if entry.get("shared"):
        for md in out.rglob("*.md"):
            text = md.read_text(encoding="utf-8")
            md.write_text(text.replace("../../references/", "references/"), encoding="utf-8")
    lines = [
        "# UPSTREAM", "",
        f"- 来源: https://github.com/{entry['repo']}/tree/{entry['commit']}/{entry['path']}",
        f"- 提交: `{entry['commit']}`",
        f"- 许可: 见上游仓库 LICENSE（{entry.get('license', 'MIT')}）",
        "- 由 `scripts/vendor.py sync` 生成，不要手动修改本目录；升级请改 `extras/upstream.json` 的 commit 后重新 sync。",
    ]
    if entry.get("shared"):
        lines.append(f"- 机械改动: 复制仓库级文件 {', '.join(entry['shared'])} 到 references/，路径 `../../references/` 改为 `references/`。")
    (out / "UPSTREAM.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def tree_hashes(root: Path) -> dict[str, str]:
    # UPSTREAM.md 是本地说明，不参与比较
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and p.name != "UPSTREAM.md"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["sync", "check", "outdated"])
    parser.add_argument("names", nargs="*")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    names = args.names or sorted(manifest)
    unknown = [n for n in names if n not in manifest]
    if unknown:
        raise SystemExit(f"upstream.json 中没有: {', '.join(unknown)}")

    if args.action == "outdated":
        for name in names:
            entry = manifest[name]
            head = git("ls-remote", f"https://github.com/{entry['repo']}.git", "HEAD").split()[0]
            current = entry["commit"][:12]
            print(f"{name}: " + ("最新" if head == entry["commit"] else f"上游有新提交 {head[:12]}（当前 {current}）"))
        return 0

    failed = 0
    with tempfile.TemporaryDirectory() as tmp_name:
        tmp, cache = Path(tmp_name), {}
        for name in names:
            entry = manifest[name]
            built = tmp / "built" / name
            built.parent.mkdir(exist_ok=True)
            build(name, entry, fetch(entry["repo"], entry["commit"], cache, tmp), built)
            target = EXTRAS / name
            if args.action == "sync":
                if entry.get("patched"):
                    print(f"{name}: 跳过（本地修改: {entry['patched']}）")
                    continue
                shutil.rmtree(target, ignore_errors=True)
                shutil.copytree(built, target)
                print(f"{name}: 已同步到 {entry['commit'][:12]}")
                continue
            expected, actual = tree_hashes(built), tree_hashes(target) if target.is_dir() else {}
            diff = sorted(k for k in expected.keys() | actual.keys() if expected.get(k) != actual.get(k))
            if not diff:
                print(f"{name}: 一致")
            elif entry.get("patched"):
                print(f"{name}: 本地修改（{entry['patched']}）: {', '.join(diff)}")
            else:
                failed += 1
                print(f"{name}: 不一致: {', '.join(diff)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

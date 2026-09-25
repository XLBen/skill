#!/usr/bin/env python3
"""Fetch pinned upstream skill trees byte-for-byte; never overwrite local edits.

Run manually from the suite repository when updating vendored skills. The
installer uses the committed files and does not access the network.
"""

import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
SOURCES = (
    {
        "repo": "anthropics/skills", "ref": "33375500bcea98d610eb30ce10ac4e59b89c390d",
        "tree": "3cf9a8db32597ba3e24b584a3d696f4e11c7d7b6",
        "source": "skills/skill-creator", "dest": "skill-creator",
        "skill_blob": "65b3a402dbd09b8e83f9d637c6b553875189085c",
    },
    {
        "repo": "anthropics/skills", "ref": "33375500bcea98d610eb30ce10ac4e59b89c390d",
        "tree": "d79e2a5bb4df4a386c2adcdd9ab8709bba28c3f6",
        "source": "skills/frontend-design", "dest": "frontend-design",
        "skill_blob": "a5333457c414d20d625f307df945842c0952ecc3",
    },
    {
        "repo": "obra/superpowers", "ref": "5bf4e78011075bcfc0dc295f0724994cd123ee71",
        "tree": "b5e154fc3ec7a6a0b1e710eebacc2168620cc428",
        "source": "skills/receiving-code-review", "dest": "receiving-code-review",
        "skill_blob": "950da7b74bf6dbed6b8726d12ddadd65a9f5fda7",
        "license_blob": "abf0390320aa14406af7a520b9b0739fdda9bf08",
    },
    {
        "repo": "vercel-labs/agent-skills", "ref": "063bee94c3f4df8453406c830b0a7df0f2860278",
        "tree": "343db72180d05814949fef7d46be96b5c6ee86b3",
        "source": "skills/react-best-practices", "dest": "vercel-react-best-practices",
        "skill_blob": "237988de4a66dd8a71d30a2c24ebe1a86b58d04e",
    },
)


def fetch(url):
    request = Request(url, headers={"User-Agent": "mvp-skill-suite-vendor/1"})
    with urlopen(request, timeout=45) as response:
        return response.read()


def blob_hash(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def vendor():
    planned = {}
    for spec in SOURCES:
        repo, ref = spec["repo"], spec["ref"]
        tree_url = f"https://api.github.com/repos/{repo}/git/trees/{spec['tree']}?recursive=1"
        tree = json.loads(fetch(tree_url))
        if tree.get("sha") != spec["tree"] or tree.get("truncated"):
            raise ValueError(f"unexpected or truncated tree: {repo}/{spec['source']}")
        seen_skill = False
        for item in tree["tree"]:
            if item["type"] != "blob" or item["mode"] not in ("100644", "100755"):
                continue
            relative = PurePosixPath(item["path"])
            if relative.is_absolute() or not relative.parts or any(p in (".", "..") for p in relative.parts):
                raise ValueError(f"unsafe path: {relative}")
            upstream_path = f"{spec['source']}/{relative.as_posix()}"
            url = f"https://raw.githubusercontent.com/{repo}/{ref}/{quote(upstream_path, safe='/')}"
            data = fetch(url)
            if blob_hash(data) != item["sha"]:
                raise ValueError(f"upstream content changed: {upstream_path}")
            if relative.as_posix() == "SKILL.md":
                seen_skill = item["sha"] == spec["skill_blob"]
            planned[ROOT / spec["dest"] / Path(*relative.parts)] = data
        if not seen_skill:
            raise ValueError(f"SKILL.md identity mismatch: {spec['dest']}")
        if "license_blob" in spec:
            data = fetch(f"https://raw.githubusercontent.com/{repo}/{ref}/LICENSE")
            if blob_hash(data) != spec["license_blob"]:
                raise ValueError(f"license identity mismatch: {repo}")
            planned[ROOT / spec["dest"] / "LICENSE"] = data

    for path, data in planned.items():
        if not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError(f"outside repository: {path}")
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f"refusing to overwrite modified file: {path}")
    for path, data in planned.items():
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(data)
    return len(planned)


if __name__ == "__main__":
    print(f"verified {vendor()} pinned upstream files")

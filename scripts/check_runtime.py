#!/usr/bin/env python3
"""Runtime capability doctor for the MVP delivery workflow.

Three read-only checks, all offline unless --fetch-schema is given:

  static <target-dir>   What the host *should* discover: effective skills,
                        agents and commands computed from real config files
                        (project walk-up + global + default + external
                        locations), with frontmatter validation.
  host <target-dir>     What the host *actually ran*: skill/task tool parts
                        and parent/child session chains read from the local
                        OpenCode SQLite store.
  doctor <target-dir>   Both, plus per-dimension verdicts.

Evidence model (deliberately strict):

  INSTALL_STATIC        files/config exist and parse
  HOST_DISCOVERY        expected catalog cross-checked against real sessions
  SKILL_INVOCATION      skill tool parts with state.status == completed
  SUBAGENT_PROVENANCE   task parts whose reported child session exists with
                        the expected parent and agent

A catalog entry with no matching runtime evidence is reported as
"expected-not-evidenced", never as available. This tool never fabricates
success records; it only reads.

Exit codes: 0 checks ran (findings are data), 2 usage/internal error.

Python 3.10+, stdlib only. Windows console safe (forces UTF-8 stdout).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path
from typing import Any

SCHEMA_URL = "https://opencode.ai/config.json"
BUILTIN_AGENTS = ("build", "plan", "general", "explore", "scout", "compaction", "title", "summary")
SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _utf8_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# config loading (json + jsonc)


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments outside string literals."""

    out = []
    i = 0
    in_string = False
    escape = False
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt == "/":
                i += 2
                while i < len(text) and text[i] not in "\r\n":
                    i += 1
                continue
            if nxt == "*":
                i += 2
                while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def strip_trailing_commas(text: str) -> str:
    """Remove commas before closing braces/brackets outside string literals."""

    return re.sub(
        r'("(?:\\.|[^"\\])*")|,(?=\s*[}\]])',
        lambda match: match.group(1) or "",
        text,
    )


def load_config_file(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"unreadable: {exc}"
    if path.suffix == ".jsonc":
        raw = strip_trailing_commas(strip_jsonc(raw))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"invalid json: {exc}"
    if not isinstance(data, dict):
        return None, "top level is not an object"
    return data, "ok"


def global_config_dir() -> Path:
    override = os.environ.get("OPENCODE_CONFIG_DIR")
    if override:
        return Path(override)
    return Path.home() / ".config" / "opencode"


def project_config_paths(project: Path) -> list[Path]:
    """Config candidates from the project dir up to its filesystem root.

    The host walks up to the worktree root; without git knowledge we walk to
    the root and let the first existing file win, matching the common case.
    """

    candidates = []
    for cur in [project, *project.parents]:
        candidates.append(cur / "opencode.json")
        candidates.append(cur / "opencode.jsonc")
        candidates.append(cur / ".opencode" / "opencode.json")
        if (cur / ".git").exists():
            break
    return candidates


def resolve_configs(project: Path) -> dict[str, Any]:
    found = []
    for cand in project_config_paths(project):
        if cand.is_file():
            data, note = load_config_file(cand)
            found.append({"path": str(cand), "status": note, "data": data or {}})
            if data is not None:
                break
    gdir = global_config_dir()
    gdata = None
    gnotes = []
    for name in ("opencode.json", "opencode.jsonc"):
        gp = gdir / name
        if gp.is_file():
            gdata, note = load_config_file(gp)
            gnotes.append({"path": str(gp), "status": note})
            if gdata is not None:
                break
    return {
        "project": found[0] if found else None,
        "global": gnotes[0] if gnotes else None,
        "project_data": (found[0]["data"] if found and found[0]["data"] else {}),
        "global_data": gdata or {},
    }


def merge_config(project_data: dict[str, Any], global_data: dict[str, Any]) -> dict[str, Any]:
    def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in overlay.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    return deep_merge(json.loads(json.dumps(global_data)), project_data)


def validate_config_shapes(config: dict[str, Any]) -> list[str]:
    problems = []
    skills = config.get("skills")
    if skills is not None:
        if not isinstance(skills, dict):
            problems.append("skills must be an object with paths/urls")
        else:
            paths = skills.get("paths")
            if paths is not None:
                if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
                    problems.append("skills.paths must be an array of strings")
            urls = skills.get("urls")
            if urls is not None and (not isinstance(urls, list) or not all(isinstance(u, str) for u in urls)):
                problems.append("skills.urls must be an array of strings")
    agent = config.get("agent")
    if agent is not None and not isinstance(agent, dict):
        problems.append("agent must be an object keyed by agent name")
    command = config.get("command")
    if command is not None and not isinstance(command, dict):
        problems.append("command must be an object keyed by command name")
    plugin = config.get("plugin")
    if plugin is not None and not isinstance(plugin, list):
        problems.append("plugin must be an array")
    mcp = config.get("mcp")
    if mcp is not None:
        if not isinstance(mcp, dict):
            problems.append("mcp must be an object keyed by server name")
        else:
            for name, srv in mcp.items():
                if isinstance(srv, dict) and "type" not in srv and srv.get("enabled", True):
                    problems.append(f"mcp.{name} is missing required 'type'")
    perm = config.get("permission")
    if perm is not None and not isinstance(perm, (str, dict)):
        problems.append("permission must be a string action or an object")
    return problems


def fetch_schema_problems(config: dict[str, Any]) -> tuple[list[str], str]:
    """Optional online validation of unknown top-level keys (best effort)."""

    try:
        with urllib.request.urlopen(SCHEMA_URL, timeout=15) as resp:
            schema = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - report, do not crash
        return [], f"schema fetch failed: {exc}"
    props = schema.get("properties", {})
    problems = [f"unknown top-level key: {k}" for k in config if k not in props and k != "$schema"]
    return problems, "ok"


# ---------------------------------------------------------------------------
# frontmatter


def parse_frontmatter(text: str) -> dict[str, Any] | None:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return None
    block = m.group(1)
    # minimal YAML: scalars, one nesting level for mappings (permission)
    data: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, data)]
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        key_m = re.match(r"^([\w.-]+)\s*:\s*(.*)$", line.strip())
        if not key_m:
            continue
        key, raw = key_m.group(1), key_m.group(2).strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if raw in ("", "|", ">"):
            parent[key] = {}
            stack.append((indent, parent[key]))
            continue
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
            raw = raw[1:-1]
        parent[key] = raw
    return data


def skill_tree_hash(skill_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in skill_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(skill_dir).as_posix()
        if "__pycache__" in path.parts or relative.endswith(".pyc"):
            continue
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
    return digest.hexdigest()


def scan_skill_files(root: Path) -> list[dict[str, Any]]:
    entries = []
    for sk_md in sorted(root.glob("**/SKILL.md")):
        rel = sk_md.parent.relative_to(root)
        folder = rel.name if str(rel) != "." else root.name
        text = sk_md.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        name = (fm or {}).get("name")
        desc = (fm or {}).get("description")
        problems = []
        if fm is None:
            problems.append("missing frontmatter")
        else:
            if not name:
                problems.append("missing name")
            elif str(name) != folder:
                problems.append(f"name '{name}' does not match folder '{folder}'")
            if not desc or not str(desc).strip():
                problems.append("missing description (skill is filtered out by the host)")
        entries.append(
            {
                "name": str(name or folder),
                "path": str(sk_md),
                "source_root": str(root),
                "problems": problems,
            }
        )
    return entries


def scan_agent_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm = parse_frontmatter(text) or {}
    problems = []
    mode = fm.get("mode")
    if mode not in ("primary", "subagent", "all", None):
        problems.append(f"invalid mode: {mode}")
    perm = fm.get("permission")
    if perm is not None and not isinstance(perm, dict):
        problems.append("permission frontmatter is not a mapping")
    return {
        "name": path.stem,
        "path": str(path),
        "mode": mode or "(default)",
        "permission": perm if isinstance(perm, dict) else None,
        "problems": problems,
    }


# ---------------------------------------------------------------------------
# static doctor


def static_doctor(project: Path, fetch_schema: bool) -> dict[str, Any]:
    project = project.resolve()
    cfg = resolve_configs(project)
    merged = merge_config(cfg["project_data"], cfg["global_data"])
    shape_problems = validate_config_shapes(merged)
    schema_note = "skipped (offline)"
    if fetch_schema:
        online, schema_note = fetch_schema_problems(merged)
        shape_problems.extend(online)

    skills: dict[str, dict[str, Any]] = {}
    dup: list[dict[str, str]] = []

    def add_skills(root: Path, source: str) -> None:
        if not root.is_dir():
            return
        for entry in scan_skill_files(root):
            name = entry["name"]
            entry["source"] = source
            if name in skills and skills[name]["path"] != entry["path"]:
                dup.append({"skill": name, "first": skills[name]["path"], "second": entry["path"]})
            skills.setdefault(name, entry)

    # host default locations
    add_skills(project / ".opencode" / "skills", "project-default")
    add_skills(project / ".opencode" / "skill", "project-default")
    gdir = global_config_dir()
    add_skills(gdir / "skills", "global-default")
    add_skills(gdir / "skill", "global-default")
    add_skills(Path.home() / ".claude" / "skills", "external-claude")
    add_skills(Path.home() / ".agents" / "skills", "external-agents")
    # skills.paths from merged config
    for raw in merged.get("skills", {}).get("paths", []) or []:
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = (project / p).resolve()
        add_skills(p, "skills.paths")

    agents: dict[str, dict[str, Any]] = {}

    def add_agents(folder: Path, source: str) -> None:
        if not folder.is_dir():
            return
        for f in sorted(folder.glob("*.md")):
            entry = scan_agent_file(f)
            entry["source"] = source
            agents.setdefault(entry["name"], entry)

    add_agents(project / ".opencode" / "agents", "project-file")
    add_agents(project / ".opencode" / "agent", "project-file")
    add_agents(gdir / "agents", "global-file")
    add_agents(gdir / "agent", "global-file")
    for name, inline in (merged.get("agent") or {}).items():
        if isinstance(inline, dict):
            agents.setdefault(
                name,
                {
                    "name": name,
                    "path": "(inline config)",
                    "mode": inline.get("mode", "(default)"),
                    "permission": inline.get("permission"),
                    "problems": [],
                    "source": "inline-config",
                },
            )

    commands: list[dict[str, Any]] = []
    for folder in (project / ".opencode" / "commands", project / ".opencode" / "command"):
        if folder.is_dir():
            for f in sorted(folder.glob("*.md")):
                fm = parse_frontmatter(f.read_text(encoding="utf-8", errors="replace")) or {}
                commands.append({"name": f.stem, "path": str(f), "description": fm.get("description")})

    manifest = None
    for mname in ("install-manifest.json", "manifest.json"):
        mpath = project / ".opencode" / "workflow" / mname
        if mpath.is_file():
            data, note = load_config_file(mpath)
            manifest = {"path": str(mpath), "status": note, "data": data}
            break

    skills_freshness = None
    installed_integrity = None
    if manifest and isinstance(manifest.get("data"), dict):
        recorded = manifest["data"].get("skills")
        if isinstance(recorded, dict) and recorded:
            stale = []
            for name, entry in sorted(recorded.items()):
                if not isinstance(entry, dict):
                    continue
                skill_dir = Path(entry.get("path", ""))
                if entry.get("algorithm") == "tree-sha256/1":
                    if not skill_dir.is_dir():
                        stale.append({"skill": name, "issue": "skill directory missing at recorded path"})
                        continue
                    current = skill_tree_hash(skill_dir)
                else:
                    skill_md = skill_dir / "SKILL.md"
                    try:
                        current = hashlib.sha256(skill_md.read_bytes()).hexdigest()  # noqa: S324
                    except OSError:
                        stale.append({"skill": name, "issue": "skill file missing at recorded path"})
                        continue
                if current != entry.get("sha256"):
                    stale.append(
                        {
                            "skill": name,
                            "issue": "skill content changed after install; engine/agents copied at install time may be older — re-run install.py to refresh",
                        }
                    )
            skills_freshness = {"status": "ok" if not stale else "drift", "stale": stale}
        else:
            skills_freshness = {
                "status": "not-checked",
                "reason": "manifest records no skill fingerprints; freshness was not verified",
            }
        files = manifest["data"].get("files")
        if isinstance(files, dict):
            changed = []
            for key, expected in sorted(files.items()):
                if not isinstance(expected, str):
                    continue
                if key.startswith(("commands/", "agents/", "plugins/")):
                    target = project / ".opencode" / key
                else:
                    target = project / ".opencode" / "workflow" / key
                try:
                    actual = hashlib.sha256(target.read_bytes()).hexdigest()  # noqa: S324
                except OSError:
                    changed.append({"file": key, "issue": "installed file is missing"})
                    continue
                if actual != expected:
                    changed.append({"file": key, "issue": "installed file changed after install"})
            installed_integrity = {
                "status": "ok" if not changed else "problems",
                "files": changed,
            }

    return {
        "dimension": "INSTALL_STATIC",
        "project": str(project),
        "config": {
            "project": cfg["project"],
            "global": cfg["global"],
            "shape_problems": shape_problems,
            "schema_check": schema_note,
        },
        "skills_expected": sorted(skills.values(), key=lambda e: e["name"]),
        "skills_duplicate_names": dup,
        "agents_expected": sorted(agents.values(), key=lambda e: e["name"]),
        "builtin_agents": list(BUILTIN_AGENTS),
        "commands": commands,
        "install_manifest": manifest,
        "skills_freshness": skills_freshness,
        "installed_integrity": installed_integrity,
    }


# ---------------------------------------------------------------------------
# host doctor (real evidence from the OpenCode sqlite store)


def open_runtime_db(explicit: str | None) -> tuple[sqlite3.Connection | None, str]:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    else:
        base = os.environ.get("OPENCODE_DATA_DIR")
        roots: list[Path] = []
        if base:
            roots.append(Path(base))
        else:
            if sys.platform == "win32":
                roots.append(Path.home() / "AppData" / "Local" / "opencode")
            roots.append(Path.home() / ".local" / "share" / "opencode")
        for root in roots:
            candidates.append(root / "opencode.db")
            candidates.append(root / "db.sqlite")
    for cand in candidates:
        if not cand.is_file():
            continue
        try:
            uri = f"file:{cand.as_posix()}?mode=ro"
            con = sqlite3.connect(uri, uri=True)
            con.row_factory = sqlite3.Row
            con.execute("select 1 from session limit 1").fetchone()
            return con, str(cand)
        except sqlite3.Error:
            continue
    return None, "no readable opencode session database found"


def _norm_dir(raw: str) -> str:
    return raw.replace("\\", "/").rstrip("/").lower()


def host_doctor(project: Path, db_arg: str | None, lookback_days: int | None) -> dict[str, Any]:
    project = project.resolve()
    con, db_note = open_runtime_db(db_arg)
    result: dict[str, Any] = {
        "dimension": "HOST_DISCOVERY",
        "project": str(project),
        "database": db_note,
        "sessions": [],
        "skill_invocations": [],
        "task_dispatches": [],
        "agent_session_counts": {},
        "coverage": {},
    }
    if con is None:
        result["note"] = "host evidence unavailable: " + db_note
        result["coverage"] = {"status": "unavailable"}
        return result

    want = _norm_dir(str(project))
    rows = con.execute(
        "select id, parent_id, directory, agent, time_created, time_updated from session"
    ).fetchall()
    matched = []
    for r in rows:
        dirs = {_norm_dir(r["directory"] or "")}
        if want not in dirs:
            continue
        if lookback_days is not None:
            cutoff = (_dt.datetime.now() - _dt.timedelta(days=lookback_days)).timestamp() * 1000
            if (r["time_created"] or 0) < cutoff:
                continue
        matched.append(r)
    sids = {r["id"] for r in matched}

    def ts(ms: int | None) -> str | None:
        if not ms:
            return None
        return _dt.datetime.fromtimestamp(ms / 1000).isoformat(timespec="seconds")

    parent_of = {r["id"]: r["parent_id"] for r in matched}
    # include direct children dispatched from matched sessions even if their
    # directory string differs (children inherit directory in practice; kept
    # for safety)
    for r in rows:
        if r["parent_id"] in sids and r["id"] not in sids:
            sids.add(r["id"])
            matched.append(r)
            parent_of[r["id"]] = r["parent_id"]

    for r in matched:
        result["sessions"].append(
            {
                "id": r["id"],
                "parent_id": r["parent_id"],
                "agent": r["agent"],
                "created": ts(r["time_created"]),
                "is_child": r["parent_id"] is not None,
            }
        )
        agent = r["agent"] or "(primary)"
        result["agent_session_counts"][agent] = result["agent_session_counts"].get(agent, 0) + 1

    q = ",".join("?" * len(sids)) if sids else "''"
    parts = con.execute(
        f"select session_id, message_id, time_created, data from part where session_id in ({q}) "
        "and json_extract(data,'$.type')='tool' and json_extract(data,'$.tool') in ('skill','task') "
        "order by time_created",
        list(sids),
    ).fetchall()
    skill_ok: dict[str, int] = {}
    skill_fail: dict[str, int] = {}
    for p in parts:
        data = json.loads(p["data"])
        tool = data.get("tool")
        state = data.get("state", {})
        status = state.get("status")
        if tool == "skill":
            name = (state.get("input") or {}).get("name")
            meta = (data.get("metadata") or {})
            entry = {
                "skill": name,
                "session_id": p["session_id"],
                "status": status,
                "source_dir": meta.get("dir"),
                "time": ts(p["time_created"]),
            }
            result["skill_invocations"].append(entry)
            if status == "completed" and name:
                skill_ok[name] = skill_ok.get(name, 0) + 1
            elif name:
                skill_fail[name] = skill_fail.get(name, 0) + 1
        elif tool == "task":
            inp = state.get("input") or {}
            out = state.get("output")
            child = None
            if isinstance(out, str):
                m = re.search(r'<task id="(ses_[A-Za-z0-9]+)"', out)
                if m:
                    child = m.group(1)
            child_row = None
            if child:
                child_row = con.execute(
                    "select id, parent_id, agent from session where id=?", (child,)
                ).fetchone()
            provenance = "unverified"
            if child_row and child_row["parent_id"] == p["session_id"]:
                provenance = "verified"
            elif child_row:
                provenance = "child-parent-mismatch"
            elif status == "completed":
                provenance = "child-session-missing"
            result["task_dispatches"].append(
                {
                    "controller_session": p["session_id"],
                    "requested_agent": inp.get("subagent_type"),
                    "status": status,
                    "child_session": child,
                    "child_agent": child_row["agent"] if child_row else None,
                    "provenance": provenance,
                    "time": ts(p["time_created"]),
                }
            )
    con.close()

    official = [a for a in result["agent_session_counts"] if a.startswith("mvp-")]
    result["coverage"] = {
        "status": "available" if matched else "no-sessions",
        "sessions_found": len(matched),
        "skills_with_completed_load": sorted(skill_ok),
        "skills_failed": sorted(skill_fail),
        "official_agent_sessions": sorted(official),
        "task_dispatches_total": len(result["task_dispatches"]),
        "task_dispatches_verified": sum(
            1 for t in result["task_dispatches"] if t["provenance"] == "verified"
        ),
    }
    return result


# ---------------------------------------------------------------------------
# doctor summary


def cross_check(static: dict[str, Any], host: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    usable = {
        e["name"]
        for e in static["skills_expected"]
        if not e["problems"] or all("description" not in p and "name" not in p for p in e["problems"])
    }
    evidenced = set(host.get("coverage", {}).get("skills_with_completed_load", []))
    if usable:
        missing = sorted(usable - evidenced)
        findings.append(
            {
                "check": "SKILL_INVOCATION",
                "verdict": "partial" if evidenced else "expected-not-evidenced",
                "detail": {
                    "expected_usable": sorted(usable),
                    "evidenced_by_real_load": sorted(evidenced & usable),
                    "expected_not_evidenced": missing,
                    "note": "no evidence is not proof of failure; it means this "
                    "database holds no completed skill load for these names",
                },
            }
        )
    prov = host.get("coverage", {})
    if prov.get("status") == "available":
        total = prov.get("task_dispatches_total", 0)
        verified = prov.get("task_dispatches_verified", 0)
        findings.append(
            {
                "check": "SUBAGENT_PROVENANCE",
                "verdict": "verified" if total and verified == total else ("none-dispatched" if not total else "partial"),
                "detail": {"total": total, "verified": verified},
            }
        )
    else:
        findings.append(
            {"check": "SUBAGENT_PROVENANCE", "verdict": "unavailable", "detail": {"database": host.get("database")}}
        )
    shape = static["config"]["shape_problems"]
    findings.append(
        {
            "check": "INSTALL_STATIC",
            "verdict": "ok" if not shape and not static["skills_duplicate_names"] else "problems",
            "detail": {"config_shape_problems": shape, "duplicate_skills": static["skills_duplicate_names"]},
        }
    )
    freshness = static.get("skills_freshness")
    if freshness:
        findings.append(
            {
                "check": "INSTALL_FRESHNESS",
                "verdict": freshness["status"],
                "detail": freshness.get("stale") or freshness.get("reason"),
            }
        )
    integrity = static.get("installed_integrity")
    if integrity:
        findings.append(
            {
                "check": "INSTALL_INTEGRITY",
                "verdict": integrity["status"],
                "detail": integrity["files"],
            }
        )
    return findings


def human_summary(report: dict[str, Any]) -> str:
    lines = []
    static = report["static"]
    host = report["host"]
    lines.append(f"project: {static['project']}")
    pcfg = static["config"]["project"]
    lines.append(f"project config: {pcfg['path'] if pcfg else 'NONE (host will not see workflow skills)'}")
    lines.append(f"skills expected: {len(static['skills_expected'])}")
    for e in static["skills_expected"]:
        flag = "" if not e["problems"] else "  <-- " + "; ".join(e["problems"])
        lines.append(f"  - {e['name']} [{e['source']}]{flag}")
    agents = [a["name"] for a in static["agents_expected"]]
    lines.append(f"agents expected: {', '.join(agents) if agents else '(none)'}")
    lines.append(f"host database: {host['database']}")
    cov = host.get("coverage", {})
    lines.append(f"sessions in project: {cov.get('sessions_found', 0)}")
    lines.append(f"skills with real completed loads: {', '.join(cov.get('skills_with_completed_load', [])) or '-'}")
    lines.append(
        f"task dispatches: {cov.get('task_dispatches_total', 0)} "
        f"(verified {cov.get('task_dispatches_verified', 0)})"
    )
    lines.append("findings:")
    for f in report["findings"]:
        lines.append(f"  [{f['check']}] {f['verdict']}")
    return "\n".join(lines)


def strict_problems(report: dict[str, Any], strict_freshness: bool = False) -> list[str]:
    """Machine-actionable problems for --strict; diagnosis mode always exits 0.

    Installed-file integrity problems always fail. Skill-tree freshness drift is
    a diagnostic by default and only fails with `--strict-freshness`, because a
    doc-only edit should not block on a source-tree fingerprint."""

    problems: list[str] = []
    static = report.get("static")
    if isinstance(static, dict):
        problems += list(static["config"].get("shape_problems") or [])
        problems += [f"duplicate skill: {item['skill']}" for item in static.get("skills_duplicate_names") or []]
        relevant_skill_sources = {"project-default", "global-default", "skills.paths"}
        for entry in static.get("skills_expected") or []:
            if entry.get("source") in relevant_skill_sources:
                problems += [f"skill {entry['name']}: {problem}" for problem in entry.get("problems") or []]
        relevant_agent_sources = {"project-file", "global-file", "inline-config"}
        for entry in static.get("agents_expected") or []:
            if entry.get("source") in relevant_agent_sources:
                problems += [f"agent {entry['name']}: {problem}" for problem in entry.get("problems") or []]
        integrity = static.get("installed_integrity")
        if isinstance(integrity, dict) and integrity.get("status") != "ok":
            problems += [
                f"installed {item['file']}: {item['issue']}"
                for item in integrity.get("files") or []
            ]
        freshness = static.get("skills_freshness")
        if strict_freshness and isinstance(freshness, dict) and freshness.get("status") == "drift":
            problems.append("skill freshness drift; re-run install.py")
    host = report.get("host")
    if isinstance(host, dict):
        coverage = host.get("coverage") or {}
        total = coverage.get("task_dispatches_total", 0)
        verified = coverage.get("task_dispatches_verified", 0)
        if coverage.get("status") == "available" and total and verified != total:
            problems.append(f"subagent provenance partial: {verified}/{total} verified")
    return problems


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["static", "host", "doctor"])
    parser.add_argument("target", help="target project directory")
    parser.add_argument("--db", help="explicit path to opencode session database")
    parser.add_argument("--lookback-days", type=int, default=None)
    parser.add_argument("--fetch-schema", action="store_true", help="validate config keys against the live schema URL")
    parser.add_argument("--json", help="also write the JSON report to this file")
    parser.add_argument("--strict", action="store_true", help="exit nonzero when static problems or installed-integrity problems are found")
    parser.add_argument("--strict-freshness", action="store_true", help="also exit nonzero on skill-tree freshness drift (diagnostic by default)")
    args = parser.parse_args(argv)

    project = Path(args.target)
    if not project.is_dir():
        print(f"error: not a directory: {project}", file=sys.stderr)
        return 2

    if args.mode == "static":
        static_report = static_doctor(project, args.fetch_schema)
        report = static_report
    elif args.mode == "host":
        report = host_doctor(project, args.db, args.lookback_days)
    else:
        st = static_doctor(project, args.fetch_schema)
        ho = host_doctor(project, args.db, args.lookback_days)
        report = {"static": st, "host": ho, "findings": cross_check(st, ho)}
        print(human_summary(report))

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.mode != "doctor":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.strict:
        normalized = report if args.mode == "doctor" else {"static": static_report} if args.mode == "static" else {"host": report}
        problems = strict_problems(normalized, strict_freshness=args.strict_freshness)
        for problem in problems:
            print(f"strict: {problem}", file=sys.stderr)
        if problems:
            return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

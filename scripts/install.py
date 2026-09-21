#!/usr/bin/env python3
"""Install this repository's OpenCode skills path, command wrappers, and subagent definitions."""

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def parse_jsonc(text, path):
    cleaned = []
    index, in_string, escaped = 0, False, False
    while index < len(text):
        char = text[index]
        if in_string:
            cleaned.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            cleaned.append(char)
            index += 1
            continue
        if text.startswith("//", index):
            end = text.find("\n", index)
            cleaned.append(" ")
            index = len(text) if end < 0 else end
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise SystemExit(f"cannot inspect {path}: unterminated JSONC comment")
            cleaned.append(" ")
            index = end + 2
            continue
        cleaned.append(char)
        index += 1
    without_trailing_commas = re.sub(
        r'("(?:\\.|[^"\\])*")|,(?=\s*[}\]])',
        lambda match: match.group(1) or "",
        "".join(cleaned),
    )
    try:
        value = json.loads(without_trailing_commas)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"cannot inspect {path}: {exc}") from exc
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?", default=".", help="target project root")
    parser.add_argument("--commands-only", action="store_true")
    parser.add_argument("--force", action="store_true", help="overwrite target files not owned by a previous install")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent.parent
    target = Path(args.target).resolve()
    if not target.is_dir():
        raise SystemExit(f"target project does not exist: {target}")

    source = repo / ".opencode" / "commands"
    agents_source = repo / ".opencode" / "agents"
    destination = target / ".opencode" / "commands"
    agents_destination = target / ".opencode" / "agents"
    plugins_source = repo / ".opencode" / "plugins"
    plugins_destination = target / ".opencode" / "plugins"
    destination.mkdir(parents=True, exist_ok=True)
    engine_root = target / ".opencode" / "workflow"
    manifest_path = engine_root / "install-manifest.json"
    previous_files = {}
    previous_manifest = {}
    if manifest_path.exists():
        try:
            previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            previous_files = previous_manifest.get("files", {})
        except (json.JSONDecodeError, OSError, AttributeError) as exc:
            raise SystemExit(f"cannot verify previous installation manifest: {exc}") from exc
        if not isinstance(previous_files, dict):
            raise SystemExit("cannot verify previous installation manifest: files must be an object")
    installed_files = {}
    command_names = {path.stem for path in source.glob("*.md")}
    agent_names = (
        {path.stem for path in agents_source.glob("*.md")}
        if agents_source.is_dir() and not args.commands_only
        else set()
    )

    def reject_inline_conflicts(data, config_label):
        if not isinstance(data, dict):
            return
        inline_commands = data.get("command", {})
        if isinstance(inline_commands, dict) and command_names.intersection(inline_commands):
            raise SystemExit(
                f"conflicting inline commands in {config_label}: "
                + ", ".join(sorted(command_names.intersection(inline_commands)))
            )
        inline_agents = data.get("agent", {})
        if isinstance(inline_agents, dict) and agent_names.intersection(inline_agents):
            raise SystemExit(
                f"conflicting inline agents in {config_label}: "
                + ", ".join(sorted(agent_names.intersection(inline_agents)))
            )
    legacy_command_dir = target / ".opencode" / "command"
    legacy_conflicts = sorted(
        path.name for path in legacy_command_dir.glob("*.md") if path.stem in command_names
    ) if legacy_command_dir.exists() else []
    if legacy_conflicts:
        raise SystemExit(
            "conflicting commands exist under .opencode/command/: " + ", ".join(legacy_conflicts)
        )
    legacy_agent_dir = target / ".opencode" / "agent"
    legacy_agent_conflicts = sorted(
        path.name for path in legacy_agent_dir.glob("*.md") if path.stem in agent_names
    ) if legacy_agent_dir.exists() else []
    if legacy_agent_conflicts:
        raise SystemExit(
            "conflicting agents exist under .opencode/agent/: " + ", ".join(legacy_agent_conflicts)
        )

    json_path = target / "opencode.json"
    jsonc_path = target / "opencode.jsonc"
    if json_path.exists():
        try:
            preflight_config = json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise SystemExit(f"cannot safely update {json_path}: {exc}") from exc
        if not isinstance(preflight_config, dict):
            raise SystemExit(f"cannot safely update {json_path}: root must be an object")
        preflight_skills = preflight_config.get("skills", {})
        if not isinstance(preflight_skills, dict):
            raise SystemExit(f"cannot safely update {json_path}: skills must be an object")
        if "paths" in preflight_skills and not isinstance(preflight_skills["paths"], list):
            raise SystemExit(f"cannot safely update {json_path}: skills.paths must be an array")
        reject_inline_conflicts(preflight_config, str(json_path))
    if jsonc_path.exists():
        try:
            jsonc_text = jsonc_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"cannot inspect {jsonc_path}: {exc}") from exc
        jsonc_data = parse_jsonc(jsonc_text, jsonc_path)
        reject_inline_conflicts(jsonc_data, str(jsonc_path))
    for local_config in (target / ".opencode" / "opencode.json",):
        if not local_config.exists():
            continue
        try:
            local_data = json.loads(local_config.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise SystemExit(f"cannot inspect {local_config}: {exc}") from exc
        reject_inline_conflicts(local_data, str(local_config))
    local_jsonc = target / ".opencode" / "opencode.jsonc"
    if local_jsonc.exists():
        try:
            local_text = local_jsonc.read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"cannot inspect {local_jsonc}: {exc}") from exc
        local_data = parse_jsonc(local_text, local_jsonc)
        reject_inline_conflicts(local_data, str(local_jsonc))

    def file_hash(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def skill_tree_hash(skill_dir):
        digest = hashlib.sha256()
        for path in sorted(item for item in skill_dir.rglob("*") if item.is_file()):
            relative = path.relative_to(skill_dir).as_posix()
            if "__pycache__" in path.parts or relative.endswith(".pyc"):
                continue
            digest.update(relative.encode("utf-8") + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        return digest.hexdigest()

    def safe_copy(source_path, destination_path, key):
        source_hash = file_hash(source_path)
        if destination_path.exists() and file_hash(destination_path) != source_hash:
            owned_hash = previous_files.get(key)
            if not args.force and file_hash(destination_path) != owned_hash:
                raise SystemExit(
                    f"refusing to overwrite unowned file: {destination_path}; use --force to replace it"
                )
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        if not destination_path.exists() or not source_path.samefile(destination_path):
            shutil.copy2(source_path, destination_path)
        installed_files[key] = source_hash

    copy_jobs = [
        (command, destination / command.name, f"commands/{command.name}")
        for command in sorted(source.glob("*.md"))
    ]
    if agents_source.is_dir() and not args.commands_only:
        copy_jobs.extend(
            (agent, agents_destination / agent.name, f"agents/{agent.name}")
            for agent in sorted(agents_source.glob("*.md"))
        )
    if plugins_source.is_dir() and not args.commands_only:
        copy_jobs.extend(
            (plugin, plugins_destination / plugin.name, f"plugins/{plugin.name}")
            for plugin in sorted(plugins_source.glob("*.js"))
        )
    retired_command_jobs = []
    for key, owned_hash in previous_files.items():
        relative = Path(key)
        if len(relative.parts) != 2 or relative.suffix != ".md":
            continue
        folder, stem = relative.parts[0], relative.stem
        if folder == "commands" and stem not in command_names:
            retired_command_jobs.append((destination / relative.name, key, owned_hash))
        elif folder == "agents" and not args.commands_only and stem not in agent_names:
            retired_command_jobs.append((agents_destination / relative.name, key, owned_hash))
    if not args.commands_only:
        for script_name in (
            "check.py",
            "assurance_policy.py",
            "evidence_registry.py",
            "package_seal.py",
            "verification_runner.py",
            "runtime_trace.py",
            "product_observation.py",
            "workflow_metrics.py",
            "workflow_packets.py",
            "workflow_runtime.py",
            "workflow_protocol.py",
            "worktree_tasks.py",
            "check_runtime.py",
            "observation_contract.py",
            "observation_candidate.py",
            "observation_results.py",
            "observation_resume.py",
            "observation_vision.py",
            "observation_media.py",
            "observation_process.py",
            "observation_capture.py",
            "observation_backend.py",
            "visibility_config.py",
            "runtime_state_policy.py",
        ):
            source_path = repo / "scripts" / script_name
            if not source_path.is_file():
                continue
            copy_jobs.append((source_path, engine_root / "scripts" / script_name, f"scripts/{script_name}"))
        copy_jobs.append(
            (
                repo / "mvp-delivery" / "references" / "stage-routing.json",
                engine_root / "stage-routing.json",
                "stage-routing.json",
            )
        )
        copy_jobs.append((repo / "tests" / "final_review.py", engine_root / "tests" / "final_review.py", "tests/final_review.py"))
        copy_jobs.extend(
            (fixture, engine_root / "tests" / "fixtures" / fixture.name, f"tests/fixtures/{fixture.name}")
            for fixture in sorted((repo / "tests" / "fixtures").glob("*.md"))
        )
    current_script_keys = {key for _, _, key in copy_jobs if key.startswith("scripts/")}
    stale_script_jobs = []
    if not args.commands_only:
        for key, owned_hash in previous_files.items():
            if key.startswith("scripts/") and key not in current_script_keys:
                stale = engine_root / key
                if stale.exists() and (args.force or file_hash(stale) == owned_hash):
                    stale_script_jobs.append(stale)
    for source_path, destination_path, key in copy_jobs:
        if destination_path.exists() and file_hash(destination_path) != file_hash(source_path):
            if not args.force and file_hash(destination_path) != previous_files.get(key):
                raise SystemExit(
                    f"refusing to overwrite unowned file: {destination_path}; use --force to replace it"
                )

    manual_config = False
    live_paths = []
    if not args.commands_only:
        live_paths = [
            path.as_posix() for path in sorted(repo.iterdir())
            if path.is_dir() and (path / "SKILL.md").is_file()
        ]
        if jsonc_path.exists() and not json_path.exists():
            manual_config = True
    config = preflight_config if json_path.exists() else {}
    rollback_paths = (
        [destination_path for _, destination_path, _ in copy_jobs]
        + [path for path, _, _ in retired_command_jobs]
        + list(stale_script_jobs)
        + [manifest_path]
    )
    if not args.commands_only and not manual_config:
        rollback_paths.append(json_path)
    backups = {path: path.read_bytes() if path.exists() else None for path in rollback_paths}
    copied = []
    retired = []
    preserved_retired = []
    try:
        for stale in stale_script_jobs:
            stale.unlink()

        for path, key, owned_hash in retired_command_jobs:
            if not path.exists():
                continue
            if args.force or file_hash(path) == owned_hash:
                path.unlink()
                retired.append(path.stem)
            else:
                preserved_retired.append(path.name)
                installed_files[key] = owned_hash

        for command in sorted(source.glob("*.md")):
            safe_copy(command, destination / command.name, f"commands/{command.name}")
            copied.append(command.stem)

        if agents_source.is_dir() and not args.commands_only:
            agents_destination.mkdir(parents=True, exist_ok=True)
            for agent in sorted(agents_source.glob("*.md")):
                safe_copy(agent, agents_destination / agent.name, f"agents/{agent.name}")

        if not args.commands_only:
            for source_path, destination_path, key in copy_jobs:
                if key.startswith(("commands/", "agents/", "plugins/")):
                    continue
                safe_copy(source_path, destination_path, key)

        if plugins_source.is_dir() and not args.commands_only:
            plugins_destination.mkdir(parents=True, exist_ok=True)
            for plugin in sorted(plugins_source.glob("*.js")):
                safe_copy(plugin, plugins_destination / plugin.name, f"plugins/{plugin.name}")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        skills_fingerprint = dict(previous_manifest.get("skills", {})) if args.commands_only else {}
        if not args.commands_only:
            for skill_dir in sorted(repo.iterdir()):
                skill_md = skill_dir / "SKILL.md"
                if skill_dir.is_dir() and skill_md.is_file():
                    skills_fingerprint[skill_dir.name] = {
                        "path": skill_dir.as_posix(),
                        "algorithm": "tree-sha256/1",
                        "sha256": skill_tree_hash(skill_dir),
                    }
        recorded_files = dict(previous_files) if args.commands_only else {}
        recorded_files.update(installed_files)
        with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(
                json.dumps(
                    {
                        "files": recorded_files,
                        "install_mode": "live-paths",
                        "skills": skills_fingerprint,
                    },
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            )

        if not args.commands_only and not manual_config:
            config.setdefault("$schema", "https://opencode.ai/config.json")
            skills = config.setdefault("skills", {})
            paths = []
            for path in skills.get("paths", []):
                # Retire only the exact root written by previous installers.
                if path == repo.as_posix() or (path in live_paths and path in paths):
                    continue
                paths.append(path)
            paths.extend(path for path in live_paths if path not in paths)
            skills["paths"] = paths
            with json_path.open("w", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    except BaseException:
        for path, content in backups.items():
            if content is None:
                if path.exists():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        raise

    print(f"installed commands: {', '.join(copied)}")
    if agents_source.is_dir() and not args.commands_only:
        installed_agents = sorted(agent_names)
        print(f"installed subagents (.opencode/agents/): {', '.join(installed_agents)}")
    if retired:
        print(f"removed retired commands: {', '.join(sorted(retired))}")
    if preserved_retired:
        print(
            "preserved locally modified retired commands: "
            + ", ".join(sorted(preserved_retired))
            + " (remove manually or reinstall with --force)"
        )
    if not args.commands_only:
        print("installed workflow engine: .opencode/workflow/scripts/check.py")
        installed_plugins = sorted(path.name for path in plugins_source.glob("*.js")) if plugins_source.is_dir() else []
        if installed_plugins:
            print(f"installed plugins (.opencode/plugins/): {', '.join(installed_plugins)}")
        if not (target / ".opencode" / "node_modules" / "@opencode-ai" / "plugin").exists():
            print(
                "plugin dependency missing: "
                f'run "npm install" in {(target / ".opencode").as_posix()} '
                "(package.json must include @opencode-ai/plugin)"
            )
        if manual_config:
            print("opencode.jsonc was not edited because comments must be preserved.")
            print("WARNING: config pending — skills are NOT active until the field below is merged and OpenCode restarts.")
            print(f'add or merge this JSONC field: "skills": {{ "paths": {json.dumps(live_paths)} }}')
            print(f'remove only the exact old skills.paths entry, if present: {json.dumps(repo.as_posix())}')
        else:
            print(f"registered skills paths: {', '.join(live_paths)}")
    print("restart OpenCode to load the changes")


if __name__ == "__main__":
    main()

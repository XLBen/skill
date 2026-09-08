#!/usr/bin/env python3
"""Install this repository's OpenCode skills path and command wrappers."""

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
    destination = target / ".opencode" / "commands"
    destination.mkdir(parents=True, exist_ok=True)
    engine_root = target / ".opencode" / "workflow"
    manifest_path = engine_root / "install-manifest.json"
    previous_files = {}
    if manifest_path.exists():
        try:
            previous_files = json.loads(manifest_path.read_text(encoding="utf-8")).get("files", {})
        except (json.JSONDecodeError, OSError, AttributeError) as exc:
            raise SystemExit(f"cannot verify previous installation manifest: {exc}") from exc
        if not isinstance(previous_files, dict):
            raise SystemExit("cannot verify previous installation manifest: files must be an object")
    installed_files = {}
    command_names = {path.stem for path in source.glob("*.md")}
    legacy_command_dir = target / ".opencode" / "command"
    legacy_conflicts = sorted(
        path.name for path in legacy_command_dir.glob("*.md") if path.stem in command_names
    ) if legacy_command_dir.exists() else []
    if legacy_conflicts:
        raise SystemExit(
            "conflicting commands exist under .opencode/command/: " + ", ".join(legacy_conflicts)
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
        inline = preflight_config.get("command", {})
        if isinstance(inline, dict) and command_names.intersection(inline):
            raise SystemExit("conflicting inline commands in opencode.json: " + ", ".join(sorted(command_names.intersection(inline))))
    if jsonc_path.exists():
        try:
            jsonc_text = jsonc_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"cannot inspect {jsonc_path}: {exc}") from exc
        jsonc_data = parse_jsonc(jsonc_text, jsonc_path)
        inline = jsonc_data.get("command", {}) if isinstance(jsonc_data, dict) else {}
        if isinstance(inline, dict) and command_names.intersection(inline):
            raise SystemExit("conflicting inline commands in opencode.jsonc: " + ", ".join(sorted(command_names.intersection(inline))))
    for local_config in (target / ".opencode" / "opencode.json",):
        if not local_config.exists():
            continue
        try:
            local_data = json.loads(local_config.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise SystemExit(f"cannot inspect {local_config}: {exc}") from exc
        inline = local_data.get("command", {}) if isinstance(local_data, dict) else {}
        if isinstance(inline, dict) and command_names.intersection(inline):
            raise SystemExit(
                f"conflicting inline commands in {local_config}: "
                + ", ".join(sorted(command_names.intersection(inline)))
            )
    local_jsonc = target / ".opencode" / "opencode.jsonc"
    if local_jsonc.exists():
        try:
            local_text = local_jsonc.read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"cannot inspect {local_jsonc}: {exc}") from exc
        local_data = parse_jsonc(local_text, local_jsonc)
        inline = local_data.get("command", {}) if isinstance(local_data, dict) else {}
        if isinstance(inline, dict) and command_names.intersection(inline):
            raise SystemExit(
                f"conflicting inline commands in {local_jsonc}: "
                + ", ".join(sorted(command_names.intersection(inline)))
            )

    def file_hash(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

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
    retired_command_jobs = []
    for key, owned_hash in previous_files.items():
        relative = Path(key)
        if (
            len(relative.parts) == 2
            and relative.parts[0] == "commands"
            and relative.suffix == ".md"
            and relative.stem not in command_names
        ):
            retired_command_jobs.append((destination / relative.name, key, owned_hash))
    copy_jobs.append((repo / "scripts" / "check.py", engine_root / "scripts" / "check.py", "scripts/check.py"))
    copy_jobs.append((repo / "tests" / "final_review.py", engine_root / "tests" / "final_review.py", "tests/final_review.py"))
    copy_jobs.extend(
        (fixture, engine_root / "tests" / "fixtures" / fixture.name, f"tests/fixtures/{fixture.name}")
        for fixture in sorted((repo / "tests" / "fixtures").glob("*.md"))
    )
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
        + [manifest_path]
    )
    if not args.commands_only and not manual_config:
        rollback_paths.append(json_path)
    backups = {path: path.read_bytes() if path.exists() else None for path in rollback_paths}
    copied = []
    retired = []
    preserved_retired = []
    try:
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

        engine_scripts = engine_root / "scripts"
        engine_fixtures = engine_root / "tests" / "fixtures"
        safe_copy(repo / "scripts" / "check.py", engine_scripts / "check.py", "scripts/check.py")
        safe_copy(repo / "tests" / "final_review.py", engine_root / "tests" / "final_review.py", "tests/final_review.py")
        for fixture in sorted((repo / "tests" / "fixtures").glob("*.md")):
            safe_copy(fixture, engine_fixtures / fixture.name, f"tests/fixtures/{fixture.name}")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({"files": installed_files}, sort_keys=True, indent=2) + "\n")

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
    if retired:
        print(f"removed retired commands: {', '.join(sorted(retired))}")
    if preserved_retired:
        print(
            "preserved locally modified retired commands: "
            + ", ".join(sorted(preserved_retired))
            + " (remove manually or reinstall with --force)"
        )
    print("installed workflow engine: .opencode/workflow/scripts/check.py")
    if not args.commands_only:
        if manual_config:
            print("opencode.jsonc was not edited because comments must be preserved.")
            print(f'add or merge this JSONC field: "skills": {{ "paths": {json.dumps(live_paths)} }}')
            print(f'remove only the exact old skills.paths entry, if present: {json.dumps(repo.as_posix())}')
        else:
            print(f"registered skills paths: {', '.join(live_paths)}")
    print("restart OpenCode to load the changes")


if __name__ == "__main__":
    main()

"""S06: candidate v2 delivered-artifact / runtime-state separation.

Covers the pure structure contract (``validate_runtime_state``,
``runtime_state_paths``), the filesystem scope checks
(``runtime_state_scope_problems``), the undeclared-file scan
(``undeclared_delivered_files``) and the end-to-end gate behavior: a stateful
product writing its own runtime files must not be reported as a tampered
candidate, while bound ``files`` hashes still invalidate on change.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import observation_candidate as ocand  # noqa: E402
import product_observation as po  # noqa: E402
import test_product_observation as tpo  # noqa: E402

sha = tpo.sha


def valid_manifest(runtime_state=None, delivered_roots=None, files=None):
    manifest = {
        "schema": po.CANDIDATE_SCHEMA,
        "candidate_id": "cand-1",
        "entry": "python app.py",
        "environment": "local windows",
        "backend": "agent-browser",
        "files": files if files is not None else [{"path": "app.py", "sha256": "a" * 64}],
        "test_data": [],
        "channels": [],
        "baseline": {"kind": "none", "refs": []},
    }
    if runtime_state is not None:
        manifest["runtime_state"] = runtime_state
    if delivered_roots is not None:
        manifest["delivered_roots"] = delivered_roots
    return manifest


def state_item(
    path="app/note.txt",
    purpose="notes the product rewrites while running",
    initial=None,
    reset="restore-initial",
):
    return {
        "path": path,
        "purpose": purpose,
        "initial": {"kind": "absent"} if initial is None else initial,
        "reset": reset,
    }


class ValidateRuntimeStateTests(unittest.TestCase):
    def test_valid_initial_kinds_pass(self):
        for initial in (
            {"kind": "absent"},
            {"kind": "sha256", "sha256": "b" * 64},
            {"kind": "ref", "ref": "seed/note.txt"},
        ):
            with self.subTest(initial=initial):
                manifest = valid_manifest(
                    runtime_state=[state_item(initial=initial)],
                    delivered_roots=["app"],
                )
                self.assertEqual(ocand.validate_runtime_state(manifest), [])
                self.assertEqual(po.validate_candidate_manifest(manifest), [])

    def test_missing_or_null_runtime_state_is_clean(self):
        self.assertEqual(ocand.validate_runtime_state(valid_manifest()), [])
        self.assertEqual(
            ocand.validate_runtime_state(valid_manifest(runtime_state=None)), []
        )
        self.assertEqual(
            ocand.validate_runtime_state(valid_manifest(delivered_roots=["app"])), []
        )

    def test_data_and_config_extensions_allowed(self):
        for name in (
            "note.txt",
            "app.log",
            "state.json",
            "conf.toml",
            "config.ini",
            "data.db",
            "data.sqlite",
            "table.csv",
            "README.md",
        ):
            with self.subTest(name=name):
                manifest = valid_manifest(
                    runtime_state=[state_item(path=f"app/{name}")],
                    delivered_roots=["app"],
                )
                self.assertEqual(ocand.validate_runtime_state(manifest), [])

    def test_source_and_executable_extensions_rejected(self):
        for suffix in sorted(ocand.SOURCE_EXEC_EXTENSIONS):
            with self.subTest(suffix=suffix):
                manifest = valid_manifest(
                    runtime_state=[state_item(path=f"app/state{suffix.upper()}")],
                    delivered_roots=["app"],
                )
                problems = ocand.validate_runtime_state(manifest)
                self.assertTrue(any("source or executable" in p for p in problems), problems)

    def test_negative_matrix(self):
        cases = []

        def case(label, items, needle, roots=("app",)):
            cases.append(
                (
                    label,
                    valid_manifest(runtime_state=items, delivered_roots=list(roots)),
                    needle,
                )
            )

        case("overlap with files", [state_item(path="app.py")], "overlaps")
        case("glob", [state_item(path="app/*.log")], "glob")
        case("absolute", [state_item(path="/var/state.log")], "absolute")
        case("parent escape", [state_item(path="app/../state.log")], "must not contain '..'")
        case("duplicate", [state_item(), state_item()], "duplicates")
        case(
            "duplicate after normalization",
            [state_item(path="app/note.txt"), state_item(path="app\\note.txt")],
            "duplicates",
        )
        unknown = state_item()
        unknown["extra"] = True
        case("unknown item field", [unknown], "unknown field")
        case("bad initial kind", [state_item(initial={"kind": "latest"})], ".kind")
        case(
            "absent with extra key",
            [state_item(initial={"kind": "absent", "sha256": "b" * 64})],
            "unknown field",
        )
        case(
            "bad sha256",
            [state_item(initial={"kind": "sha256", "sha256": "B" * 64})],
            ".sha256",
        )
        case(
            "short sha256",
            [state_item(initial={"kind": "sha256", "sha256": "abc"})],
            ".sha256",
        )
        case(
            "absolute ref",
            [state_item(initial={"kind": "ref", "ref": "/seed/note.txt"})],
            "absolute",
        )
        case("bad reset", [state_item(reset="keep")], ".reset")
        case("source extension", [state_item(path="app/state.py")], "source or executable")
        case("directory path", [state_item(path="app/logs/")], "must name a file")
        case("under mvp", [state_item(path=".opencode/mvp/state.log")], ".opencode/mvp")
        case("empty purpose", [state_item(purpose="")], ".purpose")
        case("not inside root", [state_item(path="data/state.log")], "delivered_root")
        case("root outside declared", [state_item()], "delivered_root", roots=("data",))
        case("delivered root absolute", [state_item()], "absolute", roots=("/app",))
        case("delivered root escape", [state_item()], "must not contain '..'", roots=("../app",))
        case("delivered root glob", [state_item()], "glob", roots=("app/*",))
        case("item not object", ["app/note.txt"], "must be an object")
        case("missing path", [{"purpose": "x", "initial": {"kind": "absent"}, "reset": "delete"}], "must be a non-empty string")
        case("missing initial", [{"path": "app/note.txt", "purpose": "x", "reset": "delete"}], "initial must be an object")
        case("missing reset", [{"path": "app/note.txt", "purpose": "x", "initial": {"kind": "absent"}}], ".reset")

        for label, manifest, needle in cases:
            with self.subTest(case=label):
                problems = ocand.validate_runtime_state(manifest)
                self.assertTrue(any(needle in p for p in problems), (label, problems))
                full = po.validate_candidate_manifest(manifest)
                self.assertTrue(any(needle in p for p in full), (label, full))

    def test_container_types(self):
        for value in ({}, 0, True, "text", 1.5):
            with self.subTest(value=repr(value)):
                manifest = valid_manifest(runtime_state=value)
                problems = ocand.validate_runtime_state(manifest)
                self.assertTrue(any("must be an array" in p for p in problems), problems)
        for value in ({}, 0, True, "text"):
            with self.subTest(roots=repr(value)):
                manifest = valid_manifest(runtime_state=[state_item()], delivered_roots=value)
                problems = ocand.validate_runtime_state(manifest)
                self.assertTrue(
                    any("delivered_roots must be an array" in p for p in problems),
                    problems,
                )

    def test_runtime_state_paths_normalizes(self):
        self.assertEqual(
            ocand.runtime_state_paths(
                {"runtime_state": [{"path": "./app\\note.txt"}]}
            ),
            {"app/note.txt"},
        )
        self.assertEqual(ocand.runtime_state_paths({}), set())
        self.assertEqual(ocand.runtime_state_paths({"runtime_state": None}), set())
        self.assertEqual(ocand.runtime_state_paths({"runtime_state": {"bad": 1}}), set())


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = self.tmp / "proj"
        self.app = self.project / "app"
        self.app.mkdir(parents=True)

    def manifest(self, path="app/note.txt", roots=None):
        data = {
            "files": [{"path": "app.py", "sha256": "a" * 64}],
            "runtime_state": [state_item(path=path)],
        }
        if roots is not None:
            data["delivered_roots"] = roots
        return data

    def _file_link(self, target, link):
        try:
            os.symlink(target, link)
            return True
        except OSError:
            pass
        if os.name == "nt":
            try:
                result = subprocess.run(
                    ["cmd", "/c", "mklink", str(link), str(target)],
                    capture_output=True,
                    text=True,
                )
            except OSError:
                return False
            return result.returncode == 0 and link.exists()
        return False

    def _dir_link(self, target, link):
        try:
            os.symlink(target, link, target_is_directory=True)
            return True
        except OSError:
            pass
        if os.name == "nt":
            try:
                result = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                    capture_output=True,
                    text=True,
                )
            except OSError:
                return False
            return result.returncode == 0 and link.exists()
        return False

    def test_existing_file_inside_root_passes(self):
        (self.app / "note.txt").write_text("state\n", encoding="utf-8")
        self.assertEqual(
            ocand.runtime_state_scope_problems(self.project, self.manifest(roots=["app"])),
            [],
        )

    def test_missing_target_inside_root_passes(self):
        self.assertEqual(
            ocand.runtime_state_scope_problems(self.project, self.manifest(roots=["app"])),
            [],
        )

    def test_symlinked_file_escaping_project_reported(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "note.txt").write_text("state\n", encoding="utf-8")
        if not self._file_link(outside / "note.txt", self.app / "note.txt"):
            self.skipTest("cannot create file symlinks on this account (OSError)")
        problems = ocand.runtime_state_scope_problems(
            self.project, self.manifest(roots=["app"])
        )
        self.assertTrue(
            any("outside the project root" in p for p in problems), problems
        )

    def test_junction_directory_escape_reported(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "state.log").write_text("state\n", encoding="utf-8")
        if not self._dir_link(outside, self.app / "linked"):
            self.skipTest("cannot create directory symlink/junction on this account (OSError)")
        problems = ocand.runtime_state_scope_problems(
            self.project, self.manifest(path="app/linked/state.log", roots=["app"])
        )
        self.assertTrue(
            any("outside the project root" in p for p in problems), problems
        )

    def test_file_escaping_delivered_root_reported(self):
        (self.project / "other.txt").write_text("state\n", encoding="utf-8")
        if not self._file_link(self.project / "other.txt", self.app / "note.txt"):
            self.skipTest("cannot create file symlinks on this account (OSError)")
        problems = ocand.runtime_state_scope_problems(
            self.project, self.manifest(roots=["app"])
        )
        self.assertTrue(
            any("outside delivered_root" in p for p in problems), problems
        )

    def test_junction_escaping_delivered_root_reported(self):
        other = self.project / "other"
        other.mkdir()
        (other / "state.log").write_text("state\n", encoding="utf-8")
        if not self._dir_link(other, self.app / "linked"):
            self.skipTest(
                "cannot create directory symlink/junction on this account (OSError)"
            )
        problems = ocand.runtime_state_scope_problems(
            self.project, self.manifest(path="app/linked/state.log", roots=["app"])
        )
        self.assertTrue(
            any("outside delivered_root" in p for p in problems), problems
        )


class UndeclaredDeliveredFilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = self.tmp / "proj"
        self.app = self.project / "app"
        self.app.mkdir(parents=True)

    def manifest(self, files=None, runtime=None, roots=("app",)):
        data = {
            "files": files
            if files is not None
            else [{"path": "app.py", "sha256": "a" * 64}],
        }
        if runtime is not None:
            data["runtime_state"] = runtime
        if roots is not None:
            data["delivered_roots"] = list(roots)
        return data

    def test_reports_undeclared_files_sorted(self):
        (self.app / "new_b.log").write_text("b\n", encoding="utf-8")
        (self.app / "new_a.log").write_text("a\n", encoding="utf-8")
        found = ocand.undeclared_delivered_files(
            self.project,
            self.manifest(runtime=[state_item(path="app/note.txt")]),
        )
        self.assertEqual(found, ["app/new_a.log", "app/new_b.log"])

    def test_declared_files_are_not_reported(self):
        (self.app / "keep.log").write_text("k\n", encoding="utf-8")
        (self.app / "note.txt").write_text("n\n", encoding="utf-8")
        found = ocand.undeclared_delivered_files(
            self.project,
            self.manifest(
                files=[
                    {"path": "app.py", "sha256": "a" * 64},
                    {"path": "app\\keep.log", "sha256": "b" * 64},
                ],
                runtime=[state_item(path="./app/note.txt")],
            ),
        )
        self.assertEqual(found, [])

    def test_without_delivered_roots_returns_empty(self):
        (self.app / "extra.log").write_text("x\n", encoding="utf-8")
        self.assertEqual(
            ocand.undeclared_delivered_files(self.project, self.manifest(roots=None)),
            [],
        )

    def test_internal_directories_are_skipped(self):
        for relative in (
            ".git/config",
            ".hg/hgrc",
            ".svn/entries",
            ".opencode/state.json",
            "__pycache__/mod.pyc",
            "node_modules/pkg/index.js",
            ".venv/lib.py",
            "venv/lib.py",
        ):
            target = self.app / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n", encoding="utf-8")
        self.assertEqual(
            ocand.undeclared_delivered_files(self.project, self.manifest()),
            [],
        )

    def test_directories_are_not_files(self):
        (self.app / "empty").mkdir()
        self.assertEqual(
            ocand.undeclared_delivered_files(self.project, self.manifest()),
            [],
        )


class RuntimeStateEndToEndTests(tpo.ObservationProject):
    def setUp(self):
        super().setUp()
        self.delivered = self.root / "app"
        self.delivered.mkdir()
        self.note = self.delivered / "note.txt"
        self.note.write_text("v1\n", encoding="utf-8")

    def _runtime_item(self):
        return {
            "path": "app/note.txt",
            "purpose": "notes the product rewrites while running",
            "initial": {"kind": "sha256", "sha256": sha(self.note.read_bytes())},
            "reset": "restore-initial",
        }

    def _write_candidate(self):
        manifest = {
            "schema": po.CANDIDATE_SCHEMA,
            "candidate_id": "cand-1",
            "entry": "python app.py",
            "environment": "local windows",
            "backend": "agent-browser",
            "files": [{"path": "app.py", "sha256": sha(self.app.read_bytes())}],
            "test_data": [],
            "channels": [],
            "baseline": {"kind": "none", "refs": []},
            "runtime_state": [self._runtime_item()],
            "delivered_roots": ["app"],
        }
        (self.cdir / "candidate.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8", newline="\n"
        )
        return manifest

    def test_valid_round_with_runtime_state_passes(self):
        self._full_valid_round()
        self.assertEqual(self._collect(), [])

    def test_runtime_state_write_does_not_invalidate(self):
        self._full_valid_round()
        self.note.write_text("v2 changed by the product\n", encoding="utf-8")
        self.assertEqual(self._collect(), [])

    def test_bound_file_change_still_reported(self):
        self._full_valid_round()
        self.app.write_text("print('changed')\n", encoding="utf-8")
        problems = self._collect()
        self.assertTrue(any("changed after binding" in p for p in problems), problems)

    def test_undeclared_delivered_file_reported(self):
        self._full_valid_round()
        (self.delivered / "extra.log").write_text("x\n", encoding="utf-8")
        problems = self._collect()
        self.assertTrue(
            any("undeclared delivered file: app/extra.log" in p for p in problems),
            problems,
        )

    def test_hash_semantics_independent_of_runtime_state(self):
        self._full_valid_round()
        self.app.write_text("print('changed')\n", encoding="utf-8")
        self.assertTrue(
            any("changed after binding" in p for p in self._collect())
        )
        tpo.ObservationProject._write_candidate(self)
        self.assertEqual(
            [p for p in self._collect() if "changed after binding" in p], []
        )
        self.note.write_text("v2\n", encoding="utf-8")
        self.assertEqual(self._collect(), [])
        self._write_candidate()
        self.note.write_text("v3\n", encoding="utf-8")
        self.assertEqual(self._collect(), [])


if __name__ == "__main__":
    unittest.main()

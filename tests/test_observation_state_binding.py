"""S07: runtime-state policy across verification, evidence and workspace binding.

Covers the policy module contract (strict structure, exact file paths,
no globs/directories/source, fail closed), the end-to-end stateful goal flow
(no policy → ``workspace_changed``; policy → state writes are excluded and the
binding is recorded in evidence), stale detection when the policy changes
after verification, reuse under policy equivalence, and candidate/policy
alignment at the observation gate.
"""

import hashlib
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

import runtime_state_policy as rsp  # noqa: E402
from scripts import check  # noqa: E402


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


STATE_WRITE_SCRIPT = (
    "import os; os.makedirs('app', exist_ok=True); "
    "open('app/note.txt', 'a', encoding='utf-8').write('state\\n'); "
    "print('Hello user')"
)


def state_write_command():
    return '"{}" -c "{}"'.format(sys.executable, STATE_WRITE_SCRIPT)


def make_stateful_goal(root, outcome_count=1):
    _, goal = check.read_artifact(ROOT / "tests/fixtures/goal-valid.md", "goal")
    goal["outcomes"][0]["verification"]["command"] = state_write_command()
    goal["outcomes"][0]["verification"]["timeout_seconds"] = 60
    for index in range(1, outcome_count):
        clone = json.loads(json.dumps(goal["outcomes"][0]))
        clone["id"] = f"O-0{index + 1}"
        clone["statement"] = f"Stateful variant {index + 1}"
        clone["user_entry"] = False
        goal["outcomes"].append(clone)
    card = root / ".opencode" / "mvp" / "g-state.md"
    card.parent.mkdir(parents=True, exist_ok=True)
    (root / "app").mkdir(exist_ok=True)
    (root / "app" / "main.py").write_text("print('Hello user')\n", encoding="utf-8")
    card.write_text(check.render_goal(goal), encoding="utf-8", newline="\n")
    return card


def write_policy(goal_path, paths, goal_id="G-FIXTURE", note=None, raw=None):
    path = rsp.policy_path(goal_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        path.write_text(raw, encoding="utf-8", newline="\n")
        return path
    data = {"schema": rsp.POLICY_SCHEMA, "goal_id": goal_id, "paths": list(paths)}
    if note is not None:
        data["note"] = note
    path.write_text(json.dumps(data, indent=2), encoding="utf-8", newline="\n")
    return path


class PolicyModuleTests(unittest.TestCase):
    def test_valid_policies_pass(self):
        self.assertEqual(
            rsp.validate_policy(
                {
                    "schema": rsp.POLICY_SCHEMA,
                    "goal_id": "G-X",
                    "paths": ["app/note.txt", "data/state.json"],
                    "note": "product rewrites these while running",
                }
            ),
            [],
        )
        self.assertEqual(
            rsp.validate_policy(
                {"schema": rsp.POLICY_SCHEMA, "goal_id": "G-X", "paths": []}
            ),
            [],
        )
        self.assertEqual(
            rsp.validate_policy(
                {"schema": rsp.POLICY_SCHEMA, "goal_id": "G-X", "paths": ["app\\note.txt"]}
            ),
            [],
        )
        self.assertEqual(
            rsp.validate_policy(
                {"schema": rsp.POLICY_SCHEMA, "goal_id": "G-X", "paths": ["app/note.txt"]},
                "G-X",
            ),
            [],
        )

    def test_schema_and_goal_id_problems(self):
        self.assertTrue(
            any(
                "schema must be" in p
                for p in rsp.validate_policy(
                    {"schema": "runtime-state-policy/2", "goal_id": "G-X", "paths": []}
                )
            )
        )
        self.assertTrue(
            any(
                "goal_id must be a non-empty string" in p
                for p in rsp.validate_policy({"schema": rsp.POLICY_SCHEMA, "paths": []})
            )
        )
        self.assertTrue(
            any(
                "goal_id must be a non-empty string" in p
                for p in rsp.validate_policy(
                    {"schema": rsp.POLICY_SCHEMA, "goal_id": "  ", "paths": []}
                )
            )
        )
        self.assertTrue(
            any(
                "does not match goal" in p
                for p in rsp.validate_policy(
                    {"schema": rsp.POLICY_SCHEMA, "goal_id": "G-X", "paths": []},
                    "G-Y",
                )
            )
        )
        self.assertTrue(
            any(
                "note must be a string" in p
                for p in rsp.validate_policy(
                    {"schema": rsp.POLICY_SCHEMA, "goal_id": "G-X", "paths": [], "note": 3}
                )
            )
        )

    def test_unknown_fields_are_rejected(self):
        problems = rsp.validate_policy(
            {"schema": rsp.POLICY_SCHEMA, "goal_id": "G-X", "paths": [], "extra": True}
        )
        self.assertTrue(any("unknown field" in p for p in problems), problems)
        missing = rsp.validate_policy({"schema": rsp.POLICY_SCHEMA, "goal_id": "G-X"})
        self.assertTrue(any("paths must be an array" in p for p in missing), missing)

    def test_path_shape_matrix(self):
        bad_paths = {
            "empty": "",
            "not a string": 7,
            "glob star": "app/*.log",
            "glob recursive": "app/**",
            "glob question": "app/note?.txt",
            "glob class": "app/[ab].txt",
            "absolute": "/var/state.log",
            "windows absolute": "C:/state.log",
            "parent": "app/../state.log",
            "directory": "app/logs/",
            "source": "app/state.py",
            "source uppercase": "app/state.PY",
            "executable": "app/state.exe",
            "under mvp": ".opencode/mvp/state.log",
        }
        for label, value in bad_paths.items():
            with self.subTest(case=label):
                problems = rsp.validate_policy(
                    {"schema": rsp.POLICY_SCHEMA, "goal_id": "G-X", "paths": [value]}
                )
                self.assertTrue(problems, (label, problems))

    def test_duplicates_are_rejected_after_normalization(self):
        problems = rsp.validate_policy(
            {
                "schema": rsp.POLICY_SCHEMA,
                "goal_id": "G-X",
                "paths": ["app/note.txt", "./app\\note.txt"],
            }
        )
        self.assertTrue(any("duplicates" in p for p in problems), problems)

    def test_paths_container_problems(self):
        self.assertTrue(
            any(
                "paths must be an array" in p
                for p in rsp.validate_policy(
                    {"schema": rsp.POLICY_SCHEMA, "goal_id": "G-X", "paths": "app/note.txt"}
                )
            )
        )
        self.assertTrue(
            any(
                "must be a non-empty string" in p
                for p in rsp.validate_policy(
                    {"schema": rsp.POLICY_SCHEMA, "goal_id": "G-X", "paths": ["  "]}
                )
            )
        )

    def test_load_policy_missing_is_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            card = Path(tmp) / ".opencode" / "mvp" / "g.md"
            card.parent.mkdir(parents=True)
            self.assertEqual(rsp.load_policy(card, "G-X"), (None, []))

    def test_load_policy_returns_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            card = Path(tmp) / ".opencode" / "mvp" / "g-a.md"
            card.parent.mkdir(parents=True)
            path = write_policy(
                card, ["data/state.json", "app/note.txt"], note="stateful demo"
            )
            binding, problems = rsp.load_policy(card, "G-FIXTURE")
            self.assertEqual(problems, [])
            self.assertEqual(binding["path"], ".opencode/mvp/g-a.runtime-state.json")
            self.assertEqual(binding["sha256"], sha256_file(path))
            self.assertEqual(binding["paths"], ["app/note.txt", "data/state.json"])

    def test_load_policy_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            card = Path(tmp) / ".opencode" / "mvp" / "g-a.md"
            card.parent.mkdir(parents=True)
            write_policy(card, [], raw="{not json")
            binding, problems = rsp.load_policy(card)
            self.assertIsNone(binding)
            self.assertTrue(any("not valid JSON" in p for p in problems), problems)

            write_policy(
                card,
                [],
                raw=(
                    '{"schema": "runtime-state-policy/1", "goal_id": "G-X", '
                    '"paths": ["a.txt"], "paths": ["b.txt"]}'
                ),
            )
            binding, problems = rsp.load_policy(card)
            self.assertIsNone(binding)
            self.assertTrue(any("duplicate key" in p for p in problems), problems)

            write_policy(card, ["app/state.py"])
            binding, problems = rsp.load_policy(card)
            self.assertIsNone(binding)
            self.assertTrue(any("source or executable" in p for p in problems), problems)

            write_policy(card, ["app/note.txt"], goal_id="G-OTHER")
            binding, problems = rsp.load_policy(card, "G-X")
            self.assertIsNone(binding)
            self.assertTrue(any("does not match goal" in p for p in problems), problems)

    def test_snapshot_excludes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            self.assertEqual(rsp.snapshot_excludes(root, None), [])
            self.assertEqual(rsp.snapshot_excludes(root, {}), [])
            exclusion = root / "app" / "note.txt"
            self.assertEqual(
                rsp.snapshot_excludes(
                    root, {"paths": ["app/note.txt"]}
                ),
                [exclusion.resolve()],
            )

    def test_candidate_policy_alignment(self):
        self.assertEqual(rsp.candidate_policy_alignment_problems(set(), None), [])
        missing = rsp.candidate_policy_alignment_problems({"app/note.txt"}, None)
        self.assertEqual(len(missing), 1)
        self.assertIn("no runtime-state policy exists", missing[0])
        self.assertIn("write", missing[0])
        uncovered = rsp.candidate_policy_alignment_problems(
            {"app/note.txt", "app/audit.log"}, {"paths": ["app/note.txt"]}
        )
        self.assertEqual(
            uncovered,
            ["runtime state path not covered by the runtime-state policy: app/audit.log"],
        )
        self.assertEqual(
            rsp.candidate_policy_alignment_problems(
                {"app/note.txt"}, {"paths": ["app/audit.log", "app/note.txt"]}
            ),
            [],
        )
        self.assertEqual(
            rsp.candidate_policy_alignment_problems(set(), {"paths": ["app/note.txt"]}),
            [],
        )


class EndToEndStatefulTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "proj"
        self.root.mkdir()
        self.card = make_stateful_goal(self.root)
        self.note = self.root / "app" / "note.txt"

    def _evidence(self, name):
        return f".opencode/mvp/evidence/{name}.json"

    def _verify(self, outcome="O-01", name="O-01-01"):
        return check.verify_goal_outcome(self.card, outcome, self._evidence(name))

    def test_without_policy_state_write_fails_workspace_binding(self):
        updated, payload = self._verify()
        self.assertTrue(payload["workspace_changed"])
        self.assertEqual(payload["result"], "failed")
        self.assertNotIn("runtime_state_policy", payload)
        by_id = {item["id"]: item for item in updated["outcomes"]}
        self.assertEqual(by_id["O-01"]["status"], "blocked")

    def test_policy_excludes_state_write_and_binds_evidence(self):
        policy = write_policy(self.card, ["app/note.txt"])
        updated, payload = self._verify()
        self.assertFalse(payload["workspace_changed"])
        self.assertEqual(payload["result"], "passed")
        binding = payload["runtime_state_policy"]
        self.assertEqual(binding["paths"], ["app/note.txt"])
        self.assertEqual(binding["sha256"], sha256_file(policy))
        self.assertEqual(binding["path"], ".opencode/mvp/g-state.runtime-state.json")
        by_id = {item["id"]: item for item in updated["outcomes"]}
        self.assertEqual(by_id["O-01"]["status"], "verified")

    def test_state_write_after_verification_is_tolerated(self):
        write_policy(self.card, ["app/note.txt"])
        self._verify()
        subprocess.run(
            [sys.executable, "-c", STATE_WRITE_SCRIPT], cwd=self.root, check=True
        )
        self.assertEqual(check.finish_goal(self.card)["status"], "complete")
        self.assertEqual(check.check_current(self.card)["status"], "complete")

    def test_product_change_after_verification_fails(self):
        write_policy(self.card, ["app/note.txt"])
        self._verify()
        (self.root / "app" / "main.py").write_text(
            "print('Hello changed')\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(
            check.ValidationError, "workspace changed after verification"
        ):
            check.check_current(self.card)

    def test_policy_change_after_verification_is_stale(self):
        policy = write_policy(self.card, ["app/note.txt"])
        self._verify()
        write_policy(self.card, ["app/note.txt"], note="edited after verification")
        with self.assertRaisesRegex(
            check.ValidationError, "runtime-state policy changed after verification"
        ):
            check.check_current(self.card)
        write_policy(self.card, ["app/note.txt", "app/audit.log"])
        with self.assertRaisesRegex(
            check.ValidationError, "runtime-state policy changed after verification"
        ):
            check.check_current(self.card)
        policy.unlink()
        with self.assertRaisesRegex(
            check.ValidationError, "runtime-state policy changed after verification"
        ):
            check.check_current(self.card)

    def test_invalid_policy_fails_verification(self):
        write_policy(self.card, ["app/**"])
        with self.assertRaisesRegex(
            check.ValidationError, "runtime-state policy is invalid"
        ):
            self._verify()
        self.assertFalse((self.root / self._evidence("O-01-01")).exists())


class ReuseStatePolicyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "proj"
        self.root.mkdir()
        self.card = make_stateful_goal(self.root, outcome_count=2)

    def _verify(self, outcome, name, reuse=None):
        return check.verify_goal_outcome(
            self.card,
            outcome,
            f".opencode/mvp/evidence/{name}.json",
            reuse_from=reuse,
        )

    def test_reuse_requires_identical_policy(self):
        write_policy(self.card, ["app/note.txt"])
        self._verify("O-01", "O-01-01")
        _, payload = self._verify(
            "O-02", "O-02-01", reuse=".opencode/mvp/evidence/O-01-01.json"
        )
        self.assertEqual(payload["result"], "passed")
        self.assertEqual(payload["reuse_policy"], "immutable-inputs")
        self.assertEqual(payload["runtime_state_policy"]["paths"], ["app/note.txt"])

    def test_reuse_refused_after_policy_change(self):
        write_policy(self.card, ["app/note.txt"])
        self._verify("O-01", "O-01-01")
        write_policy(self.card, ["app/note.txt", "app/audit.log"])
        with self.assertRaisesRegex(check.ValidationError, "not strictly equivalent"):
            self._verify(
                "O-02", "O-02-01", reuse=".opencode/mvp/evidence/O-01-01.json"
            )
        self.assertFalse((self.root / ".opencode/mvp/evidence/O-02-01.json").exists())

    def test_reuse_refused_after_policy_removal(self):
        policy = write_policy(self.card, ["app/note.txt"])
        self._verify("O-01", "O-01-01")
        policy.unlink()
        with self.assertRaisesRegex(check.ValidationError, "not strictly equivalent"):
            self._verify(
                "O-02", "O-02-01", reuse=".opencode/mvp/evidence/O-01-01.json"
            )


class GateAlignmentIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "proj"
        self.mvp = self.root / ".opencode" / "mvp"
        self.mvp.mkdir(parents=True)
        self.card = self.mvp / "g-obs.md"
        self.card.write_text("placeholder card\n", encoding="utf-8")
        self.candidate_dir = (
            self.mvp / "observation" / "G-OBS" / "cand-1"
        )
        self.candidate_dir.mkdir(parents=True)
        (self.mvp / "g-obs.product-audit.json").write_text(
            json.dumps(
                {
                    "schema": "product-audit/2",
                    "goal_id": "G-OBS",
                    "current_candidate": "cand-1",
                    "rounds": [{"candidate_id": "cand-1"}],
                }
            ),
            encoding="utf-8",
        )
        self.manifest_path = self.candidate_dir / "candidate.json"

    def _goal(self, schema_version=2, required=True):
        goal = {
            "schema_version": schema_version,
            "id": "G-OBS",
        }
        if schema_version == 2:
            goal["product_observation"] = {"required": required}
        return goal

    def _write_manifest(self, paths):
        manifest = {
            "schema": "product-candidate/2",
            "candidate_id": "cand-1",
            "runtime_state": [
                {"path": path, "purpose": "state", "initial": {"kind": "absent"}, "reset": "delete"}
                for path in paths
            ],
        }
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_candidate_without_policy_blocks(self):
        self._write_manifest(["app/note.txt"])
        problems = check.observation_state_policy_problems(self.card, self._goal())
        self.assertEqual(len(problems), 1)
        self.assertIn("no runtime-state policy exists", problems[0])

    def test_policy_coverage_dimensions(self):
        self._write_manifest(["app/note.txt"])
        write_policy(self.card, ["app/note.txt"], goal_id="G-OBS")
        self.assertEqual(
            check.observation_state_policy_problems(self.card, self._goal()), []
        )
        self._write_manifest(["app/note.txt", "app/audit.log"])
        problems = check.observation_state_policy_problems(self.card, self._goal())
        self.assertEqual(
            problems,
            ["runtime state path not covered by the runtime-state policy: app/audit.log"],
        )
        self._write_manifest([])
        self.assertEqual(
            check.observation_state_policy_problems(self.card, self._goal()), []
        )

    def test_schema1_or_not_required_is_skipped(self):
        self._write_manifest(["app/note.txt"])
        self.assertEqual(
            check.observation_state_policy_problems(
                self.card, self._goal(schema_version=1)
            ),
            [],
        )
        self.assertEqual(
            check.observation_state_policy_problems(
                self.card, self._goal(required=False)
            ),
            [],
        )

    def test_invalid_policy_reported(self):
        self._write_manifest(["app/note.txt"])
        write_policy(self.card, ["app/*.log"], goal_id="G-OBS")
        problems = check.observation_state_policy_problems(self.card, self._goal())
        self.assertTrue(any("glob" in p for p in problems), problems)

    def test_missing_sidecar_or_manifest_is_not_double_reported(self):
        self._write_manifest(["app/note.txt"])
        write_policy(self.card, ["app/note.txt"], goal_id="G-OBS")
        (self.mvp / "g-obs.product-audit.json").unlink()
        self.assertEqual(
            check.observation_state_policy_problems(self.card, self._goal()), []
        )


class PolicyPathSymlinkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.root = self.tmp / "proj"
        self.app = self.root / "app"
        self.app.mkdir(parents=True)
        self.outside = self.tmp / "outside"
        self.outside.mkdir()

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

    def test_symlinked_policy_path_resolves_to_its_target(self):
        target = self.outside / "note.txt"
        target.write_text("state\n", encoding="utf-8")
        if not self._file_link(target, self.app / "note.txt"):
            self.skipTest("cannot create file symlinks on this account (OSError)")
        binding = {
            "path": ".opencode/mvp/g-state.runtime-state.json",
            "sha256": "a" * 64,
            "paths": ["app/note.txt"],
        }
        excludes = rsp.snapshot_excludes(self.root, binding)
        self.assertEqual(excludes, [self.app.joinpath("note.txt").resolve()])
        self.assertTrue(str(excludes[0]).startswith(str(self.outside.resolve())))


if __name__ == "__main__":
    unittest.main()

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import observation_contract as contract  # noqa: E402
import product_observation as po  # noqa: E402
import workflow_packets as wp  # noqa: E402

from scripts import check  # noqa: E402

GOAL_V2 = {
    "schema_version": 2,
    "id": "G-OBS",
    "status": "active",
    "source": {"type": "direct", "raw_request": "Deliver the demo app."},
    "goal": "A user can use the demo app end to end",
    "rigor": "normal",
    "risk": {"factors": ["none"], "rationale": "Local disposable demonstration"},
    "first_slice": "CLI entry",
    "demo": "Run the app entry",
    "constraints": [],
    "deferred": [],
    "product_observation": {"required": True},
    "outcomes": [{
        "id": "O-01",
        "statement": "The app entry runs",
        "status": "pending",
        "user_entry": True,
        "verification": {
            "command": "python app.py",
            "expected": "The app runs",
            "assertion_kind": "user-visible",
            "empty_result_policy": "Empty stdout fails",
            "assertion": {"type": "stdout-contains", "literal": "ok"},
            "timeout_seconds": 5,
        },
    }],
}


def write_goal(goal_path: Path, goal: dict) -> None:
    body = (
        "---\nstatus: active\n---\n\n# Goal\n\n```json goal\n"
        + json.dumps(goal, indent=2, ensure_ascii=False)
        + "\n```\n"
    )
    goal_path.write_text(body, encoding="utf-8", newline="\n")


def discover_report():
    return {
        "schema": po.REPORT_SCHEMA,
        "phase": "discover",
        "stop_reason": "coverage-completed",
        "surfaces": [
            {"id": "S-01", "name": "main entry", "importance": "material"}
        ],
        "journeys": [
            {
                "id": "J-01",
                "surface_ids": ["S-01"],
                "evidence_refs": ["evidence/j01.png"],
                "outcome": "covered",
            }
        ],
        "findings": [],
        "unobserved": [],
        "capability_gaps": [],
        "continuation": None,
        "evidence_refs": ["evidence/round.txt"],
        "goal_id": "G-OBS",
        "candidate_id": "cand-1",
        "observer_session_id": "ses_observer",
        "model": "provider/model",
        "packet_hash": "0" * 64,
        "received_at": "2026-09-21T00:00:00Z",
        "attempt": 1,
    }


def preflight_payload(model_status="passed", provider_id="openai", model_id="gpt-5.6-luna"):
    payload = {
        "schema": wp.PREFLIGHT_SCHEMA,
        "performed_at": "2026-09-21T00:00:00Z",
        "performed_by": "controller",
        "covers": {
            "host": {"status": "passed", "detail": "local host probe"},
            "model": {"status": model_status},
            "candidate": {"status": "passed"},
            "session": {"status": "passed"},
        },
    }
    if model_status == "passed":
        payload["covers"]["model"]["provider_id"] = provider_id
        payload["covers"]["model"]["model_id"] = model_id
    return payload


def walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)


class ObserverPacketTests(unittest.TestCase):
    def setUp(self):
        import shutil

        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = self.tmp / "proj"
        (self.root / ".opencode" / "mvp").mkdir(parents=True)
        self.goal_path = self.root / ".opencode" / "mvp" / "g-obs.md"
        write_goal(self.goal_path, GOAL_V2)
        self.cdir = self.root / ".opencode" / "mvp" / "observation" / "G-OBS" / "cand-1"
        (self.cdir / "evidence").mkdir(parents=True)
        manifest = {
            "schema": po.CANDIDATE_SCHEMA,
            "candidate_id": "cand-1",
            "entry": "python app.py",
            "environment": "local",
            "backend": "agent-browser",
            "files": [{"path": "app.py", "sha256": "0" * 64}],
            "test_data": [],
            "channels": [],
            "baseline": {"kind": "none", "refs": []},
        }
        (self.cdir / "candidate.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8", newline="\n"
        )
        sidecar = {
            "schema": po.AUDIT_SIDECAR_SCHEMA,
            "goal_id": "G-OBS",
            "current_candidate": "cand-1",
            "rounds": [
                {
                    "candidate_id": "cand-1",
                    "discover_ref": ".opencode/mvp/observation/G-OBS/cand-1/discover.result.json",
                    "compare_ref": ".opencode/mvp/observation/G-OBS/cand-1/compare.result.json",
                    "review_ref": ".opencode/mvp/observation/G-OBS/cand-1/review.result.json",
                }
            ],
        }
        (self.root / ".opencode" / "mvp" / "g-obs.product-audit.json").write_text(
            json.dumps(sidecar, indent=2), encoding="utf-8", newline="\n"
        )

    def _write_discover(self, report=None):
        (self.cdir / "discover.result.json").write_text(
            json.dumps(report if report is not None else discover_report(), indent=2),
            encoding="utf-8",
            newline="\n",
        )

    def _write_preflight(self, **kwargs):
        path = self.cdir / "preflight.json"
        path.write_text(
            json.dumps(preflight_payload(**kwargs), indent=2),
            encoding="utf-8",
            newline="\n",
        )
        return path

    def _write_packet(self, packet, name):
        out = self.tmp / name
        wp._write(packet, out)
        return out

    # ---------------------------------------------------------------- discover

    def test_discover_packet_schema_v2_blind_and_valid(self):
        self._write_discover()
        packet = wp.build_observer_packet(self.goal_path, "discover")
        self.assertEqual(packet["schema"], "workflow-observer-packet/2")
        self.assertEqual(packet["schema"], contract.SCHEMA_PACKET)
        self.assertEqual(packet["phase"], "discover")
        self.assertEqual(packet["goal_id"], "G-OBS")
        self.assertNotIn("original", packet)
        for field in wp.OBSERVER_FORBIDDEN_FIELDS:
            self.assertNotIn(field, packet)
        goal_file = str(self.goal_path).replace("\\", "/")
        dump = json.dumps(packet, ensure_ascii=False).lower()
        for text in walk_strings(packet):
            self.assertNotIn(self.goal_path.name.lower(), text.lower(), packet)
            self.assertNotIn(goal_file.lower(), text.replace("\\", "/").lower())
        self.assertNotIn("g-obs.md", dump)
        self.assertNotIn(goal_file.lower(), dump)
        out = self._write_packet(packet, "discover.packet.json")
        self.assertEqual(wp.validate_packet(out, self.goal_path), [])

    def test_discover_brief_is_public_and_complete(self):
        self._write_discover()
        packet = wp.build_observer_packet(self.goal_path, "discover")
        brief = packet["brief"]
        self.assertEqual(
            set(brief), {"purpose", "demo", "first_slice", "raw_request"}
        )
        self.assertEqual(brief["purpose"], GOAL_V2["goal"])
        self.assertEqual(brief["demo"], GOAL_V2["demo"])
        self.assertEqual(brief["first_slice"], GOAL_V2["first_slice"])
        self.assertEqual(brief["raw_request"], GOAL_V2["source"]["raw_request"])
        self.assertNotIn("verification", brief)
        self.assertNotIn("outcomes", brief)

    def test_discover_output_template_and_rules(self):
        self._write_discover()
        packet = wp.build_observer_packet(self.goal_path, "discover")
        output = packet["output"]
        self.assertEqual(output["schema"], "product-observation/2")
        self.assertEqual(contract.validate_result_payload(output["template"], "discover"), [])
        self.assertEqual(
            output["repair_reference"], "product-observer/references/format-repair.md"
        )
        rules = output["rules"]
        self.assertTrue(rules.strip())
        for token in (
            "coverage-completed",
            "blocked",
            "budget-exhausted",
            "evidence",
            "controller",
            ".opencode/mvp",
            "```json",
            "format-repair.md",
            "diff",
        ):
            self.assertIn(token, rules)

    def test_discover_model_defaults_null_and_parses(self):
        self._write_discover()
        default = wp.build_observer_packet(self.goal_path, "discover")
        self.assertIsNone(default["model"])
        parsed = wp.build_observer_packet(
            self.goal_path, "discover", model="openai/gpt-5.6-luna"
        )
        self.assertEqual(
            parsed["model"], {"provider_id": "openai", "model_id": "gpt-5.6-luna"}
        )
        self.assertIsNone(parsed["preflight"])

    def test_model_must_be_provider_slash_model(self):
        self._write_discover()
        with self.assertRaises(ValueError):
            wp.build_observer_packet(self.goal_path, "discover", model="no-slash")

    def test_discover_packet_rejects_goal_history(self):
        self._write_discover()
        packet = wp.build_observer_packet(self.goal_path, "discover")
        packet["original"] = {"goal": "smuggled"}
        out = self._write_packet(packet, "bad.packet.json")
        problems = wp.validate_packet(out, self.goal_path)
        self.assertTrue(any("must not carry goal-history material" in p for p in problems), problems)

    # --------------------------------------------------------------- preflight

    def test_preflight_absent_is_null(self):
        self._write_discover()
        packet = wp.build_observer_packet(self.goal_path, "discover")
        self.assertIsNone(packet["preflight"])
        out = self._write_packet(packet, "nopreflight.packet.json")
        self.assertEqual(wp.validate_packet(out, self.goal_path), [])

    def test_preflight_embedded_with_sha(self):
        self._write_discover()
        preflight = self._write_preflight()
        packet = wp.build_observer_packet(
            self.goal_path, "discover", model="openai/gpt-5.6-luna"
        )
        embedded = packet["preflight"]
        expected_sha = hashlib.sha256(preflight.read_bytes()).hexdigest()
        self.assertEqual(embedded["sha256"], expected_sha)
        self.assertEqual(embedded["performed_at"], "2026-09-21T00:00:00Z")
        self.assertEqual(embedded["performed_by"], "controller")
        self.assertEqual(embedded["covers"]["model"]["status"], "passed")
        self.assertFalse(Path(embedded["path"]).is_absolute())
        self.assertTrue(embedded["path"].endswith("preflight.json"))
        self.assertNotIn("\\", embedded["path"])
        out = self._write_packet(packet, "preflight.packet.json")
        self.assertEqual(wp.validate_packet(out, self.goal_path), [])

    def test_preflight_model_mismatch_rejected(self):
        self._write_discover()
        self._write_preflight()
        with self.assertRaises(ValueError):
            wp.build_observer_packet(
                self.goal_path, "discover", model="other/model"
            )

    def test_preflight_passed_without_model_rejected(self):
        self._write_discover()
        self._write_preflight()
        with self.assertRaises(ValueError):
            wp.build_observer_packet(self.goal_path, "discover")

    def test_preflight_sha_mismatch_detected(self):
        self._write_discover()
        preflight = self._write_preflight()
        packet = wp.build_observer_packet(
            self.goal_path, "discover", model="openai/gpt-5.6-luna"
        )
        out = self._write_packet(packet, "preflight-stale.packet.json")
        payload = json.loads(preflight.read_text(encoding="utf-8"))
        payload["performed_by"] = "someone-else"
        preflight.write_text(
            json.dumps(payload, indent=2), encoding="utf-8", newline="\n"
        )
        problems = wp.validate_packet(out, self.goal_path)
        self.assertTrue(any("preflight file changed" in p for p in problems), problems)

    # ----------------------------------------------------------------- compare

    def test_compare_requires_saved_discover(self):
        with self.assertRaises(ValueError):
            wp.build_observer_packet(self.goal_path, "compare")

    def test_compare_packet_carries_goal_history(self):
        self._write_discover()
        packet = wp.build_observer_packet(self.goal_path, "compare")
        self.assertIn("original", packet)
        original = packet["original"]
        self.assertEqual(original["baselines"]["kind"], "none")
        self.assertEqual(original["goal"], GOAL_V2["goal"])
        self.assertEqual(original["raw_request"], GOAL_V2["source"]["raw_request"])
        self.assertNotIn("approved_changes", original)
        discover_ref = original["discover_result"]["path"]
        self.assertEqual(
            discover_ref,
            ".opencode/mvp/observation/G-OBS/cand-1/discover.result.json",
        )
        expected_sha = hashlib.sha256(
            (self.cdir / "discover.result.json").read_bytes()
        ).hexdigest()
        self.assertEqual(original["discover_result"]["sha256"], expected_sha)
        out = self._write_packet(packet, "compare.packet.json")
        self.assertEqual(wp.validate_packet(out, self.goal_path), [])
        self.assertEqual(wp.validate_packet(out), [])

    def test_compare_rejects_malformed_discover_payload(self):
        report = discover_report()
        report["journeys"][0].pop("outcome")
        self._write_discover(report)
        with self.assertRaises(ValueError):
            wp.build_observer_packet(self.goal_path, "compare")

    def test_compare_rejects_missing_discover_file(self):
        self.assertFalse((self.cdir / "discover.result.json").is_file())
        with self.assertRaises(ValueError):
            wp.build_observer_packet(self.goal_path, "compare")

    # ------------------------------------------------------------------ basics

    def test_forbidden_field_rejected(self):
        self._write_discover()
        packet = wp.build_observer_packet(self.goal_path, "discover")
        packet["diff"] = "app.py changed"
        out = self._write_packet(packet, "bad2.packet.json")
        problems = wp.validate_packet(out, self.goal_path)
        self.assertTrue(any("forbidden field 'diff'" in p for p in problems), problems)

    def test_stale_goal_card_detected(self):
        self._write_discover()
        packet = wp.build_observer_packet(self.goal_path, "discover")
        out = self._write_packet(packet, "stale.packet.json")
        goal = json.loads(json.dumps(GOAL_V2))
        goal["goal"] = "changed purpose"
        write_goal(self.goal_path, goal)
        problems = wp.validate_packet(out, self.goal_path)
        self.assertTrue(any("goal card changed" in p for p in problems), problems)

    def test_discover_binding_requires_goal(self):
        self._write_discover()
        packet = wp.build_observer_packet(self.goal_path, "discover")
        out = self._write_packet(packet, "nobinding.packet.json")
        problems = wp.validate_packet(out)
        self.assertTrue(
            any("cannot be verified without --goal" in p for p in problems), problems
        )
        self.assertEqual(wp.validate_packet(out, self.goal_path), [])

    def test_stale_candidate_manifest_detected(self):
        self._write_discover()
        packet = wp.build_observer_packet(self.goal_path, "discover")
        out = self._write_packet(packet, "stale-manifest.packet.json")
        manifest = json.loads((self.cdir / "candidate.json").read_text(encoding="utf-8"))
        manifest["entry"] = "python app2.py"
        (self.cdir / "candidate.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8", newline="\n"
        )
        problems = wp.validate_packet(out, self.goal_path)
        self.assertTrue(any("candidate manifest changed" in p for p in problems), problems)

    def test_schema1_goal_rejected_for_packets(self):
        legacy = json.loads(json.dumps(GOAL_V2))
        legacy["schema_version"] = 1
        legacy.pop("product_observation")
        write_goal(self.goal_path, legacy)
        with self.assertRaises(ValueError):
            wp.build_observer_packet(self.goal_path, "discover")

    def test_unknown_phase_rejected(self):
        self._write_discover()
        with self.assertRaises(ValueError):
            wp.build_observer_packet(self.goal_path, "verify")

    def test_validate_packet_never_raises_on_malformed(self):
        self._write_discover()
        packet = wp.build_observer_packet(self.goal_path, "discover")
        out = self._write_packet(packet, "malformed.packet.json")
        mutations = (
            lambda payload: payload.update({"candidate": []}),
            lambda payload: payload.update({"output": "nope"}),
            lambda payload: payload.update({"goal_binding": []}),
            lambda payload: payload.update({"preflight": {"path": "a\x00b", "sha256": "x"}}),
            lambda payload: payload.update(
                {"original": {"discover_result": {"path": "a\x00b"}}}
            ),
            lambda payload: payload.update({"phase": "discover", "original": {}}),
        )
        for mutate in mutations:
            payload = json.loads(out.read_text(encoding="utf-8"))
            mutate(payload)
            broken = self._write_packet(payload, "broken.packet.json")
            problems = wp.validate_packet(broken, self.goal_path)
            self.assertTrue(problems, payload)

    def test_cli_observer_command_writes_packet(self):
        self._write_discover()
        out = self.tmp / "cli.packet.json"
        code = wp.main([
            "observer", str(self.goal_path), "--phase", "discover",
            "--model", "openai/gpt-5.6-luna", "--out", str(out),
        ])
        self.assertEqual(code, 0)
        self.assertTrue(out.is_file())
        packet = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(
            packet["model"], {"provider_id": "openai", "model_id": "gpt-5.6-luna"}
        )
        code = wp.main([
            "validate", str(out), "--goal", str(self.goal_path),
        ])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()

"""S09: format-repair state machine -- repair_prompt and run_format_repair.

Covers the first answer plus at-most-two format-only repairs, the
``needs-observation`` marker outcome, send failures, attempt recording, and a
replay of the 21-file v1 corpus. The replay writes every terminal state to
``docs/po-repair/baseline/s09-corpus-repair.json``; the corpus files
themselves are never written (their digests are asserted unchanged).
"""

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import observation_contract as contract  # noqa: E402
import observation_results as ors  # noqa: E402

CORPUS_DIR = ROOT / "docs" / "po-repair" / "corpus"
BASELINE_PATH = ROOT / "docs" / "po-repair" / "baseline" / "s09-corpus-repair.json"

_MARKER = {"repair_outcome": "needs-observation", "reason": "缺少证据目录的原始引用"}


def block(value):
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False)
    return f"```json\n{value}\n```\n"


def fresh_payload(phase="discover"):
    return json.loads(json.dumps(contract.result_template(phase)))


def broken_payload(phase="discover"):
    payload = fresh_payload(phase)
    payload["surfaces"][0]["importance"] = "primary"
    return payload


class RepairPromptTests(unittest.TestCase):
    def test_prompt_contains_every_required_part(self):
        payload = broken_payload("discover")
        problems = [
            "result.surfaces[0].importance must be one of ('material', 'peripheral')",
            "result.notes must be a non-empty string when present",
        ]
        text = ors.repair_prompt("discover", payload, problems, 1, max_repairs=2)

        self.assertIn("第 1/2 次格式纠偏", text)
        self.assertIn(json.dumps(payload, ensure_ascii=False, indent=2), text)
        for problem in problems:
            self.assertIn(problem, text)

        template_json = json.dumps(
            contract.result_template("discover"), ensure_ascii=False, indent=2
        )
        self.assertIn(template_json, text)
        template = json.loads(template_json)
        self.assertEqual(contract.validate_result_payload(template, "discover"), [])

        for keyword in (
            "不要操作产品",
            "不要新增",
            "不要改变",
            "不要猜",
            "controller",
            "needs-observation",
            "product-observation/2",
            "format-repair.md",
        ):
            self.assertIn(keyword, text)

    def test_compare_template_validates(self):
        text = ors.repair_prompt(
            "compare", broken_payload("compare"), ["result.notes"], 2, max_repairs=2
        )
        self.assertIn("第 2/2 次格式纠偏", text)
        template_json = json.dumps(
            contract.result_template("compare"), ensure_ascii=False, indent=2
        )
        self.assertIn(template_json, text)
        self.assertEqual(
            contract.validate_result_payload(json.loads(template_json), "compare"), []
        )

    def test_unknown_phase_and_odd_problems_never_raise(self):
        cases = (
            ("review", {"schema": "product-observation/1"}, None),
            ("discover", None, "single problem"),
            ("discover", "raw text is not a payload", []),
            (None, {}, 3),
        )
        for phase, payload, problems in cases:
            text = ors.repair_prompt(phase, payload, problems, 1)
            self.assertIsInstance(text, str)
            self.assertIn("format repair", text)


class RunFormatRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def sender(self, replies, calls=None):
        if calls is None:
            calls = []
        replies = list(replies)

        def send(prompt):
            calls.append(prompt)
            return replies.pop(0)

        return send, calls

    def test_first_valid_is_adopted(self):
        payload = fresh_payload("discover")
        send, calls = self.sender([])
        result = ors.run_format_repair("discover", block(payload), send)
        self.assertEqual(result["status"], "adopted")
        self.assertEqual(result["payload"], payload)
        self.assertEqual(result["problems"], [])
        self.assertEqual(result["repair_count"], 0)
        self.assertEqual(result["attempts"], 1)
        self.assertIsNone(result["reason"])
        self.assertEqual(calls, [])

    def test_invalid_then_valid_adopts(self):
        send, calls = self.sender([block(fresh_payload("discover"))])
        result = ors.run_format_repair(
            "discover", block(broken_payload("discover")), send
        )
        self.assertEqual(result["status"], "adopted")
        self.assertEqual(result["payload"], fresh_payload("discover"))
        self.assertEqual(result["repair_count"], 1)
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(len(calls), 1)
        self.assertIn("第 1/2 次格式纠偏", calls[0])
        self.assertIn(
            "result.surfaces[0].importance", calls[0]
        )

    def test_two_repairs_then_valid_adopts(self):
        send, calls = self.sender(
            [block(broken_payload("discover")), block(fresh_payload("discover"))]
        )
        result = ors.run_format_repair(
            "discover", block(broken_payload("discover")), send
        )
        self.assertEqual(result["status"], "adopted")
        self.assertEqual(result["repair_count"], 2)
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(len(calls), 2)
        self.assertIn("第 2/2 次格式纠偏", calls[1])

    def test_repair_cap_stops_as_needs_observation(self):
        send, calls = self.sender(
            [block(broken_payload("discover")), block(broken_payload("discover"))]
        )
        result = ors.run_format_repair(
            "discover", block(broken_payload("discover")), send
        )
        self.assertEqual(result["status"], "needs-observation")
        self.assertIsNone(result["payload"])
        self.assertEqual(result["repair_count"], 2)
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(len(calls), 2)
        self.assertTrue(result["problems"])
        self.assertIn("limit", result["reason"])

    def test_fix_from_template_patch_is_adopted(self):
        first = broken_payload("discover")
        first.pop("notes", None)
        corrected = fresh_payload("discover")
        corrected["notes"] = "format-only correction of the same observations"
        send, calls = self.sender([block(corrected)])
        result = ors.run_format_repair("discover", block(first), send)
        self.assertEqual(result["status"], "adopted")
        self.assertEqual(result["payload"], corrected)
        self.assertEqual(result["repair_count"], 1)
        self.assertEqual(len(calls), 1)

    def test_marker_stops_with_reason(self):
        send, _calls = self.sender([block(_MARKER)])
        result = ors.run_format_repair(
            "discover", block(broken_payload("discover")), send
        )
        self.assertEqual(result["status"], "needs-observation")
        self.assertIsNone(result["payload"])
        self.assertEqual(result["reason"], _MARKER["reason"])
        self.assertEqual(result["repair_count"], 1)
        self.assertEqual(result["attempts"], 2)
        self.assertNotIn("S-01", result["reason"])
        self.assertNotIn("J-01", result["reason"])
        self.assertNotIn("F-01", result["reason"])

    def test_marker_without_reason_still_stops(self):
        marker = {"repair_outcome": "needs-observation"}
        send, _calls = self.sender([block(marker)])
        result = ors.run_format_repair(
            "discover", block(broken_payload("discover")), send
        )
        self.assertEqual(result["status"], "needs-observation")
        self.assertIsInstance(result["reason"], str)
        self.assertTrue(result["reason"])

    def test_marker_variants_never_raise(self):
        variants = (
            {"repair_outcome": "needs-observation"},
            {"repair_outcome": "needs-observation", "reason": 42},
            {"repair_outcome": "needs-observation", "reason": "   "},
            {"repair_outcome": "needs-observation", "extra": [1, 2]},
        )
        for variant in variants:
            send, _calls = self.sender([block(variant)])
            result = ors.run_format_repair(
                "discover", block(broken_payload("discover")), send
            )
            self.assertEqual(result["status"], "needs-observation", variant)
            self.assertIsInstance(result["reason"], str, variant)
            self.assertIsNone(result["payload"], variant)

    def test_non_marker_repair_outcome_is_not_a_marker(self):
        send, calls = self.sender([])
        result = ors.run_format_repair(
            "discover",
            block({"repair_outcome": "ok"}),
            send,
            max_repairs=0,
        )
        self.assertEqual(result["status"], "needs-observation")
        self.assertEqual(result["repair_count"], 0)
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(calls, [])

    def test_max_repairs_zero_sends_nothing(self):
        send, calls = self.sender([])
        result = ors.run_format_repair(
            "discover", block(broken_payload("discover")), send, max_repairs=0
        )
        self.assertEqual(result["status"], "needs-observation")
        self.assertEqual(result["repair_count"], 0)
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(calls, [])

    def test_send_exception_is_failed(self):
        def explode(_prompt):
            raise RuntimeError("mod-script-pipe closed")

        result = ors.run_format_repair(
            "discover", block(broken_payload("discover")), explode
        )
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["payload"])
        self.assertIn("mod-script-pipe closed", result["reason"])
        self.assertEqual(result["repair_count"], 1)
        self.assertEqual(result["attempts"], 1)

    def test_odd_first_texts_never_raise(self):
        texts = (
            None,
            7,
            "",
            "no fence at all",
            block("[1, 2, 3]"),
            block("null"),
            block("{not json}"),
            "x" * 200000,
            block("y" * 200000),
        )
        for text in texts:
            send, _calls = self.sender([block(_MARKER)])
            result = ors.run_format_repair("discover", text, send)
            self.assertIn(result["status"], ("needs-observation", "failed"))
            self.assertLessEqual(result["attempts"], 3)
            self.assertLessEqual(result["repair_count"], 2)

    def test_phase_mismatch_is_repaired_not_adopted(self):
        compare_payload = fresh_payload("compare")
        send, _calls = self.sender([block(compare_payload)])
        result = ors.run_format_repair(
            "discover", block(compare_payload), send, max_repairs=1
        )
        self.assertEqual(result["status"], "needs-observation")
        self.assertEqual(result["repair_count"], 1)
        self.assertEqual(result["attempts"], 2)


class RunFormatRepairRecordingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.run_dir = self.tmp / "discover" / "run-001"
        self.received_at = "2026-09-21T12:00:00Z"

    def test_run_dir_records_each_attempt_with_incrementing_ids(self):
        replies = [block(broken_payload("discover")), block(fresh_payload("discover"))]
        sent = []

        def send(prompt):
            sent.append(prompt)
            return replies.pop(0)

        result = ors.run_format_repair(
            "discover",
            block(broken_payload("discover")),
            send,
            run_dir=self.run_dir,
            received_at=self.received_at,
        )
        self.assertEqual(result["status"], "adopted")
        self.assertEqual(result["attempts"], 3)

        attempts = self.run_dir / "attempts"
        names = sorted(path.name for path in attempts.iterdir())
        self.assertEqual(
            names,
            [
                "attempt-001.attempt.json",
                "attempt-001.errors.json",
                "attempt-002.attempt.json",
                "attempt-002.errors.json",
                "attempt-003.attempt.json",
                "attempt-003.errors.json",
            ],
        )

        first = json.loads(
            (attempts / "attempt-001.attempt.json").read_text(encoding="utf-8")
        )
        self.assertEqual(first["received_at"], self.received_at)
        first_errors = json.loads(
            (attempts / "attempt-001.errors.json").read_text(encoding="utf-8")
        )
        self.assertFalse(first_errors["parsed_ok"])
        self.assertTrue(first_errors["errors"])

        second = json.loads(
            (attempts / "attempt-002.attempt.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            second["raw_text"], block(broken_payload("discover"))
        )

        last_errors = json.loads(
            (attempts / "attempt-003.errors.json").read_text(encoding="utf-8")
        )
        self.assertTrue(last_errors["parsed_ok"])
        self.assertEqual(last_errors["errors"], [])

    def test_run_dir_continues_existing_numbering(self):
        attempts = self.run_dir / "attempts"
        attempts.mkdir(parents=True)
        (attempts / "attempt-001.attempt.json").write_text("{}", encoding="utf-8")

        result = ors.run_format_repair(
            "discover",
            block(fresh_payload("discover")),
            lambda _prompt: block(_MARKER),
            run_dir=self.run_dir,
            received_at=self.received_at,
        )
        self.assertEqual(result["status"], "adopted")
        self.assertTrue((attempts / "attempt-002.attempt.json").is_file())
        self.assertTrue((attempts / "attempt-002.errors.json").is_file())

    def test_marker_attempt_is_recorded_parsed_ok(self):
        result = ors.run_format_repair(
            "discover",
            block(broken_payload("discover")),
            lambda _prompt: block(_MARKER),
            run_dir=self.run_dir,
            received_at=self.received_at,
        )
        self.assertEqual(result["status"], "needs-observation")
        attempts = self.run_dir / "attempts"
        marker_errors = json.loads(
            (attempts / "attempt-002.errors.json").read_text(encoding="utf-8")
        )
        self.assertTrue(marker_errors["parsed_ok"])


class CorpusReplayTests(unittest.TestCase):
    def test_corpus_replay_terminates_and_records_baseline(self):
        paths = sorted(CORPUS_DIR.rglob("*.result.json"))
        self.assertEqual(len(paths), 21)
        digests_before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
        }

        entries = []
        for path in paths:
            phase = path.name.split(".")[0]
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            first_text = json.dumps(value, ensure_ascii=False)

            payload_errors = len(contract.validate_result_payload(value, phase))
            payload, parse_problems = ors.parse_single_payload(first_text)
            initial_errors = (
                len(parse_problems) if payload is None else payload_errors
            )

            result = ors.run_format_repair(
                phase, first_text, lambda _prompt, text=first_text: text
            )
            self.assertIn(
                result["status"], ("adopted", "needs-observation", "failed"), path
            )
            self.assertLessEqual(result["attempts"], 3, path)
            self.assertLessEqual(result["repair_count"], 2, path)
            if result["status"] == "needs-observation":
                self.assertTrue(result["reason"], path)

            entries.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "phase": phase,
                    "initial_errors": initial_errors,
                    "payload_errors": payload_errors,
                    "status": result["status"],
                    "repair_count": result["repair_count"],
                    "attempts": result["attempts"],
                }
            )

        baseline = {
            "contract": "product-observation/2",
            "generated_by": "tests/test_observation_format_repair.py (S09 replay)",
            "files": entries,
        }
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_bytes(
            (json.dumps(baseline, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            .encode("utf-8")
        )
        reloaded = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(reloaded["files"], entries)

        digests_after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
        }
        self.assertEqual(digests_before, digests_after)


if __name__ == "__main__":
    unittest.main()

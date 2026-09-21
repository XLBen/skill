"""S08a-1: observation result store -- payload parsing, run/attempt ids, and
create-only atomic attempt recording."""

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

_UNSET = object()


def block(payload_text):
    return f"```json\n{payload_text}\n```\n"


class ParseSinglePayloadTests(unittest.TestCase):
    def test_single_block_parses_to_object(self):
        payload, problems = ors.parse_single_payload(
            'here is the result:\n```json\n{"a": 1, "b": 2}\n```\n'
        )
        self.assertEqual(problems, [])
        self.assertEqual(payload, {"a": 1, "b": 2})

    def test_zero_blocks_is_a_problem(self):
        payload, problems = ors.parse_single_payload('{"a": 1}')
        self.assertIsNone(payload)
        self.assertEqual(len(problems), 1)
        self.assertIn("no ```json fenced block", problems[0])

    def test_two_blocks_are_rejected(self):
        text = block('{"a": 1}') + block('{"a": 2}')
        payload, problems = ors.parse_single_payload(text)
        self.assertIsNone(payload)
        self.assertTrue(any("more than one" in p for p in problems), problems)

    def test_trailing_garbage_is_rejected(self):
        text = block('{"a": 1}') + "that's all\n"
        payload, problems = ors.parse_single_payload(text)
        self.assertIsNone(payload)
        self.assertTrue(any("content after" in p for p in problems), problems)

    def test_invalid_json_is_rejected(self):
        payload, problems = ors.parse_single_payload(block("{not json}"))
        self.assertIsNone(payload)
        self.assertTrue(any("invalid JSON" in p for p in problems), problems)

    def test_non_object_is_rejected(self):
        payload, problems = ors.parse_single_payload(block("[1, 2, 3]"))
        self.assertIsNone(payload)
        self.assertTrue(any("not a JSON object" in p for p in problems), problems)

    def test_whitespace_after_the_block_is_fine(self):
        payload, problems = ors.parse_single_payload('```json\n{"ok": true}\n```  \n\n')
        self.assertEqual(problems, [])
        self.assertEqual(payload, {"ok": True})


class RunLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.cdir = self.tmp / "cand"

    def test_path_helpers(self):
        self.assertEqual(ors.run_dir(self.cdir, "discover", "run-001"), self.cdir / "discover" / "run-001")
        self.assertEqual(
            ors.result_path(self.cdir, "discover", "run-001"),
            self.cdir / "discover" / "run-001" / "result.json",
        )
        self.assertEqual(
            ors.attempts_dir(self.cdir / "discover" / "run-001"),
            self.cdir / "discover" / "run-001" / "attempts",
        )

    def test_allocate_run_id_starts_at_one(self):
        self.assertEqual(ors.allocate_run_id(self.cdir, "discover"), "run-001")

    def test_allocate_run_id_increments_existing(self):
        phase = self.cdir / "discover"
        (phase / "run-001").mkdir(parents=True)
        (phase / "run-002").mkdir()
        self.assertEqual(ors.allocate_run_id(self.cdir, "discover"), "run-003")

    def test_allocate_run_id_ignores_non_run_entries(self):
        phase = self.cdir / "discover"
        (phase / "notes").mkdir(parents=True)
        (phase / "run-abc").mkdir()
        (phase / "run-001.tmp").write_text("x", encoding="utf-8")
        self.assertEqual(ors.allocate_run_id(self.cdir, "discover"), "run-001")

    def test_allocate_run_id_pads_and_expands(self):
        phase = self.cdir / "discover"
        (phase / "run-099").mkdir(parents=True)
        self.assertEqual(ors.allocate_run_id(self.cdir, "discover"), "run-100")

    def test_next_attempt_id_starts_at_one(self):
        self.assertEqual(ors.next_attempt_id(self.cdir / "discover" / "run-001"), "attempt-001")

    def test_next_attempt_id_increments_existing(self):
        attempts = self.cdir / "discover" / "run-001" / "attempts"
        attempts.mkdir(parents=True)
        (attempts / "attempt-001.attempt.json").write_text("{}", encoding="utf-8")
        self.assertEqual(ors.next_attempt_id(self.cdir / "discover" / "run-001"), "attempt-002")

    def test_next_attempt_id_ignores_errors_and_foreign_files(self):
        attempts = self.cdir / "discover" / "run-001" / "attempts"
        attempts.mkdir(parents=True)
        (attempts / "attempt-007.errors.json").write_text("{}", encoding="utf-8")
        (attempts / "attempt-two.attempt.json").write_text("{}", encoding="utf-8")
        (attempts / "notes.txt").write_text("x", encoding="utf-8")
        self.assertEqual(ors.next_attempt_id(self.cdir / "discover" / "run-001"), "attempt-001")


class RecordAttemptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.run_dir = self.tmp / "discover" / "run-001"

    def _record(self, attempt_id="attempt-001", errors=None, parsed=_UNSET):
        return ors.record_attempt(
            self.run_dir,
            attempt_id,
            "```json\n{\"a\": 1}\n```\n",
            {"a": 1} if parsed is _UNSET else parsed,
            [] if errors is None else errors,
            "2026-09-21T10:00:00Z",
        )

    def test_writes_attempt_and_errors_files(self):
        attempt_path, errors_path = self._record()
        self.assertEqual(attempt_path.name, "attempt-001.attempt.json")
        self.assertEqual(errors_path.name, "attempt-001.errors.json")

        attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
        self.assertEqual(
            attempt,
            {
                "attempt_id": "attempt-001",
                "raw_text": "```json\n{\"a\": 1}\n```\n",
                "parsed": {"a": 1},
                "received_at": "2026-09-21T10:00:00Z",
            },
        )
        errors = json.loads(errors_path.read_text(encoding="utf-8"))
        self.assertEqual(
            errors,
            {"attempt_id": "attempt-001", "errors": [], "parsed_ok": True},
        )

    def test_failed_parse_is_recorded_as_not_ok(self):
        attempt_path, errors_path = self._record(
            errors=["no ```json fenced block found"], parsed=None
        )
        attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
        self.assertIsNone(attempt["parsed"])
        errors = json.loads(errors_path.read_text(encoding="utf-8"))
        self.assertEqual(errors["errors"], ["no ```json fenced block found"])
        self.assertFalse(errors["parsed_ok"])

    def test_duplicate_attempt_id_is_refused_without_overwriting(self):
        attempt_path, errors_path = self._record()
        before = (attempt_path.read_bytes(), errors_path.read_bytes())
        with self.assertRaises(ValueError):
            self._record(parsed={"a": 2})
        self.assertEqual(attempt_path.read_bytes(), before[0])
        self.assertEqual(errors_path.read_bytes(), before[1])

    def test_duplicate_does_not_leave_temporary_files(self):
        attempt_path, _ = self._record()
        with self.assertRaises(ValueError):
            self._record()
        leftovers = [p.name for p in attempt_path.parent.iterdir() if ".tmp" in p.name]
        self.assertEqual(leftovers, [])

    def test_existing_errors_file_rolls_back_the_attempt_file(self):
        target_dir = ors.attempts_dir(self.run_dir)
        target_dir.mkdir(parents=True)
        (target_dir / "attempt-001.errors.json").write_text(
            "{}\n", encoding="utf-8", newline="\n"
        )
        with self.assertRaises(ValueError):
            self._record()
        self.assertFalse((target_dir / "attempt-001.attempt.json").exists())

    def test_success_leaves_no_temporary_files(self):
        self._record()
        self.assertEqual(
            sorted(p.name for p in ors.attempts_dir(self.run_dir).iterdir()),
            ["attempt-001.attempt.json", "attempt-001.errors.json"],
        )

    def test_invalid_attempt_id_is_refused(self):
        with self.assertRaises(ValueError):
            self._record(attempt_id="attempt-1")
        self.assertFalse(self.run_dir.exists())


class CanonicalBytesTests(unittest.TestCase):
    def test_key_order_is_irrelevant(self):
        self.assertEqual(
            ors.canonical_bytes({"b": 1, "a": [1, 2]}),
            ors.canonical_bytes({"a": [1, 2], "b": 1}),
        )

    def test_whitespace_is_irrelevant(self):
        first = json.loads('{"a": 1, "b": {"c": [1, 2]}}')
        second = json.loads('{\n  "b": {"c": [1, 2]},\n  "a": 1\n}\n')
        self.assertEqual(ors.canonical_bytes(first), ors.canonical_bytes(second))

    def test_different_values_differ(self):
        self.assertNotEqual(
            ors.canonical_bytes({"a": 1}), ors.canonical_bytes({"a": 2})
        )

    def test_non_ascii_is_utf8_not_escaped(self):
        data = ors.canonical_bytes({"note": "中文"})
        self.assertIn("中文".encode("utf-8"), data)
        self.assertNotIn(b"\\u4e2d", data)


# ---------------------------------------------------------------------------
# S08a-2: envelope validation, provenance/evidence gates, adoption
# ---------------------------------------------------------------------------


def make_payload(phase="discover"):
    return json.loads(json.dumps(contract.result_template(phase)))


def make_envelope(**overrides):
    envelope = {
        "goal_id": "G-OBS",
        "candidate_id": "C-01",
        "observer_session_id": "ses_observer",
        "model": "test-model",
        "packet_hash": "a" * 64,
        "attempt": 1,
    }
    envelope.update(overrides)
    return envelope


def make_trace(session_id="ses_observer", skill="product-observer", status="completed"):
    return {
        "sessions": [{"id": session_id, "parent_id": None}],
        "skill_events": [{"session_id": session_id, "skill": skill, "status": status}],
    }


class ValidateEnvelopeTests(unittest.TestCase):
    def test_valid_envelope_has_no_problems(self):
        self.assertEqual(ors.validate_envelope(make_envelope()), [])

    def test_non_dict_envelope_is_rejected(self):
        for envelope in (None, [], "envelope", 3):
            problems = ors.validate_envelope(envelope)
            self.assertEqual(len(problems), 1)

    def test_missing_fields_are_reported(self):
        for field in ("goal_id", "candidate_id", "observer_session_id", "model"):
            envelope = make_envelope()
            del envelope[field]
            problems = ors.validate_envelope(envelope)
            self.assertTrue(any(field in p for p in problems), (field, problems))
            self.assertTrue(
                any("must be a non-empty string" in p for p in problems), problems
            )

    def test_blank_fields_are_reported(self):
        for field in ("goal_id", "candidate_id", "observer_session_id", "model"):
            problems = ors.validate_envelope(make_envelope(**{field: "   "}))
            self.assertTrue(any(field in p for p in problems), (field, problems))

    def test_packet_hash_must_be_lowercase_sha256(self):
        for value in ("A" * 64, "a" * 63, "a" * 65, "g" * 64, 64, None):
            problems = ors.validate_envelope(make_envelope(packet_hash=value))
            self.assertTrue(
                any("packet_hash" in p for p in problems), (value, problems)
            )

    def test_attempt_must_be_positive_int(self):
        for value in (True, False, 0, -1, "1", None, 1.0, 1.5):
            problems = ors.validate_envelope(make_envelope(attempt=value))
            self.assertTrue(any("attempt" in p for p in problems), (value, problems))

    def test_positive_attempt_int_is_fine(self):
        self.assertEqual(ors.validate_envelope(make_envelope(attempt=3)), [])


class AdoptTestCase(unittest.TestCase):
    received_at = "2026-09-21T10:00:00Z"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.cdir = self.tmp / "cand"
        self.project_root = self.tmp / "project"
        self.project_root.mkdir()

    def materialize_evidence(self, *names):
        for name in names:
            target = self.cdir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"evidence")

    def materialize_round_evidence(self):
        self.materialize_evidence("evidence/j01.png", "evidence/round.md")

    def adopt(self, payload=None, envelope=None, trace=_UNSET, phase="discover", **kwargs):
        if payload is None:
            payload = make_payload(phase)
        if envelope is None:
            envelope = make_envelope()
        if trace is _UNSET:
            trace = make_trace()
        kwargs.setdefault("received_at", self.received_at)
        return ors.adopt_result(
            self.cdir, self.project_root, phase, payload, envelope, trace, **kwargs
        )


class AdoptSuccessTests(AdoptTestCase):
    def test_adoption_writes_result_attempt_and_errors(self):
        self.materialize_round_evidence()
        payload = make_payload("discover")
        path, problems = self.adopt(payload=payload)
        self.assertEqual(problems, [])
        self.assertEqual(path, self.cdir / "discover" / "run-001" / "result.json")

        stored = json.loads(path.read_text(encoding="utf-8"))
        for field, value in make_envelope().items():
            self.assertEqual(stored[field], value)
        self.assertEqual(stored["received_at"], self.received_at)
        self.assertEqual(stored["surfaces"], payload["surfaces"])
        self.assertEqual(stored["journeys"], payload["journeys"])
        self.assertEqual(stored["findings"], payload["findings"])

        attempts = path.parent / "attempts"
        attempt = json.loads(
            (attempts / "attempt-001.attempt.json").read_text(encoding="utf-8")
        )
        self.assertEqual(attempt["attempt_id"], "attempt-001")
        self.assertEqual(json.loads(attempt["raw_text"]), payload)
        self.assertEqual(attempt["received_at"], self.received_at)
        errors = json.loads(
            (attempts / "attempt-001.errors.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            errors, {"attempt_id": "attempt-001", "errors": [], "parsed_ok": True}
        )

    def test_compare_payload_adopts(self):
        self.materialize_evidence(
            "evidence/j01.png", "evidence/round.md", "evidence/f01.png"
        )
        payload = make_payload("compare")
        path, problems = self.adopt(payload=payload, phase="compare")
        self.assertEqual(problems, [])
        self.assertEqual(path, self.cdir / "compare" / "run-001" / "result.json")
        stored = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(stored["findings"], payload["findings"])

    def test_matching_controller_field_in_payload_is_allowed(self):
        self.materialize_round_evidence()
        payload = make_payload("discover")
        payload["model"] = make_envelope()["model"]
        path, problems = self.adopt(payload=payload)
        self.assertEqual(problems, [])
        self.assertIsNotNone(path)


class AdoptRejectionTests(AdoptTestCase):
    def assert_rejected(self, payload, envelope=None, trace=_UNSET, phase="discover"):
        path, problems = self.adopt(
            payload=payload, envelope=envelope, trace=trace, phase=phase, run_id="run-001"
        )
        self.assertIsNone(path)
        self.assertTrue(problems)
        run = self.cdir / phase / "run-001"
        self.assertFalse((run / "result.json").exists())
        self.assertTrue(
            (run / "attempts" / "attempt-001.attempt.json").is_file(), problems
        )
        return problems

    def test_payload_phase_mismatch_is_rejected(self):
        self.materialize_round_evidence()
        problems = self.assert_rejected(make_payload("compare"))
        self.assertTrue(any("expected 'discover'" in p for p in problems), problems)

    def test_payload_envelope_conflict_is_rejected(self):
        self.materialize_round_evidence()
        payload = make_payload("discover")
        payload["model"] = "model-from-payload"
        problems = self.assert_rejected(payload)
        self.assertTrue(
            any("conflicts with the controller envelope" in p for p in problems),
            problems,
        )

    def test_envelope_missing_field_is_rejected(self):
        self.materialize_round_evidence()
        envelope = make_envelope()
        del envelope["model"]
        problems = self.assert_rejected(make_payload("discover"), envelope=envelope)
        self.assertTrue(any("model" in p for p in problems), problems)

    def test_envelope_bad_attempt_is_rejected(self):
        self.materialize_round_evidence()
        envelope = make_envelope(attempt="1")
        problems = self.assert_rejected(make_payload("discover"), envelope=envelope)
        self.assertTrue(any("attempt" in p for p in problems), problems)

    def test_missing_evidence_is_rejected(self):
        self.materialize_evidence("evidence/j01.png")
        problems = self.assert_rejected(make_payload("discover"))
        self.assertTrue(any("not found" in p for p in problems), problems)

    def test_escaping_evidence_is_rejected(self):
        self.materialize_round_evidence()
        payload = make_payload("discover")
        payload["evidence_refs"] = ["../outside.md"]
        problems = self.assert_rejected(payload)
        self.assertTrue(
            any("escapes the candidate evidence scope" in p for p in problems),
            problems,
        )

    def test_absolute_evidence_is_rejected(self):
        self.materialize_round_evidence()
        payload = make_payload("discover")
        payload["evidence_refs"] = [str(self.tmp / "outside.md")]
        problems = self.assert_rejected(payload)
        self.assertTrue(
            any("escapes the candidate evidence scope" in p for p in problems),
            problems,
        )

    def test_finding_evidence_is_checked(self):
        self.materialize_evidence("evidence/j01.png", "evidence/round.md")
        problems = self.assert_rejected(make_payload("compare"), phase="compare")
        self.assertTrue(any("not found" in p for p in problems), problems)

    def test_missing_session_is_rejected(self):
        self.materialize_round_evidence()
        problems = self.assert_rejected(
            make_payload("discover"), trace=make_trace(session_id="ses_other")
        )
        self.assertTrue(
            any("not found in the runtime trace" in p for p in problems), problems
        )

    def test_missing_skill_load_is_rejected(self):
        self.materialize_round_evidence()
        problems = self.assert_rejected(
            make_payload("discover"), trace=make_trace(status="failed")
        )
        self.assertTrue(
            any("no completed product-observer skill load" in p for p in problems),
            problems,
        )

    def test_unusable_trace_is_rejected(self):
        self.materialize_round_evidence()
        for trace in (None, [], "trace"):
            problems = self.assert_rejected(make_payload("discover"), trace=trace)
            self.assertTrue(any("unavailable" in p for p in problems), problems)


class AdoptCreateOnlyTests(AdoptTestCase):
    def test_identical_result_is_idempotent(self):
        self.materialize_round_evidence()
        first_path, problems = self.adopt(run_id="run-001")
        self.assertEqual(problems, [])
        original = first_path.read_bytes()

        second_path, problems = self.adopt(run_id="run-001")
        self.assertEqual(problems, [])
        self.assertEqual(second_path, first_path)
        self.assertEqual(first_path.read_bytes(), original)
        self.assertTrue(
            (first_path.parent / "attempts" / "attempt-002.attempt.json").is_file()
        )

    def test_different_result_conflicts_and_keeps_the_file(self):
        self.materialize_round_evidence()
        first_path, _ = self.adopt(run_id="run-001")
        original = first_path.read_bytes()

        payload = make_payload("discover")
        payload["notes"] = "changed after review"
        second_path, problems = self.adopt(payload=payload, run_id="run-001")
        self.assertIsNone(second_path)
        self.assertTrue(any("conflict" in p for p in problems), problems)
        self.assertEqual(first_path.read_bytes(), original)

    def test_stale_temp_is_removed_and_no_result_is_written(self):
        self.materialize_evidence("evidence/j01.png")
        run = self.cdir / "discover" / "run-001"
        run.mkdir(parents=True)
        (run / "result.json.tmp").write_text("junk", encoding="utf-8")
        (run / ".result.json.abc.tmp").write_text("junk", encoding="utf-8")

        path, problems = self.adopt(run_id="run-001")
        self.assertIsNone(path)
        self.assertTrue(problems)
        self.assertFalse((run / "result.json").exists())
        self.assertFalse((run / "result.json.tmp").exists())
        self.assertFalse((run / ".result.json.abc.tmp").exists())


class AdoptRunAllocationTests(AdoptTestCase):
    def test_second_run_gets_run_002(self):
        self.materialize_round_evidence()
        first_path, problems = self.adopt()
        self.assertEqual(problems, [])

        payload = make_payload("discover")
        payload["notes"] = "second run payload"
        second_path, problems = self.adopt(payload=payload)
        self.assertEqual(problems, [])

        self.assertEqual(first_path, self.cdir / "discover" / "run-001" / "result.json")
        self.assertEqual(
            second_path, self.cdir / "discover" / "run-002" / "result.json"
        )

    def test_attempt_ids_increment_within_a_run(self):
        self.materialize_evidence("evidence/j01.png")
        path, problems = self.adopt(run_id="run-001")
        self.assertIsNone(path)
        self.assertTrue(problems)

        self.materialize_evidence("evidence/round.md")
        path, problems = self.adopt(run_id="run-001")
        self.assertEqual(problems, [])
        attempts = path.parent / "attempts"
        self.assertTrue((attempts / "attempt-001.attempt.json").is_file())
        self.assertTrue((attempts / "attempt-002.attempt.json").is_file())


class EvidenceAndProvenanceSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_evidence_ref_problems_never_raise(self):
        payloads = (
            None,
            {},
            [],
            "text",
            3,
            {"evidence_refs": {}},
            {"journeys": "x"},
            {"journeys": [None]},
            {"findings": [3]},
            {"evidence_refs": [None, "", 0]},
        )
        for payload in payloads:
            problems = ors.evidence_ref_problems(self.tmp, self.tmp, payload)
            self.assertIsInstance(problems, list)

    def test_provenance_problems_never_raise(self):
        traces = (
            None,
            {},
            [],
            "text",
            3,
            {"sessions": "x", "skill_events": []},
            {"sessions": [1], "skill_events": [None]},
        )
        for trace in traces:
            problems = ors.provenance_problems(trace, None)
            self.assertIsInstance(problems, list)

    def test_provenance_accepts_minimal_valid_trace(self):
        self.assertEqual(ors.provenance_problems(make_trace(), "ses_observer"), [])


class LoadResultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_reads_bom_encoded_object(self):
        target = self.tmp / "result.json"
        target.write_bytes(b"\xef\xbb\xbf" + b'{"a": 1}\n')
        value, problems = ors.load_result(target)
        self.assertEqual(problems, [])
        self.assertEqual(value, {"a": 1})

    def test_invalid_json_is_reported(self):
        target = self.tmp / "result.json"
        target.write_text("{not json", encoding="utf-8")
        value, problems = ors.load_result(target)
        self.assertIsNone(value)
        self.assertTrue(any("invalid JSON" in p for p in problems), problems)

    def test_missing_file_is_reported(self):
        value, problems = ors.load_result(self.tmp / "missing.json")
        self.assertIsNone(value)
        self.assertTrue(problems)

    def test_non_object_is_reported(self):
        target = self.tmp / "result.json"
        target.write_text("[1, 2]", encoding="utf-8")
        value, problems = ors.load_result(target)
        self.assertIsNone(value)
        self.assertTrue(any("JSON object" in p for p in problems), problems)


# ---------------------------------------------------------------------------
# S08b: file locking, product-audit sidecar updates, review adoption
# ---------------------------------------------------------------------------

import hashlib
import os
import threading
import time
from unittest import mock

_REVIEW_NOTES = "S08b review: both phases were checked against the packet."


def make_review_payload(**overrides):
    payload = json.loads(json.dumps(contract.review_template()))
    payload["notes"] = overrides.pop("notes", _REVIEW_NOTES)
    payload.update(overrides)
    return payload


def make_review_envelope(**overrides):
    envelope = {
        "reviewer_session_id": "ses_reviewer",
        "model": "test-model",
        "attempt": 1,
    }
    envelope.update(overrides)
    return envelope


def make_review_trace(
    session_id="ses_reviewer", skill="reviewer", status="completed"
):
    return {
        "sessions": [{"id": session_id, "parent_id": None}],
        "skill_events": [{"session_id": session_id, "skill": skill, "status": status}],
    }


class FileLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.lock = self.tmp / "resource.lock"

    def test_lock_can_be_reacquired_after_release(self):
        with ors.file_lock(self.lock):
            self.assertTrue(self.lock.exists())
        self.assertFalse(self.lock.exists())
        with ors.file_lock(self.lock):
            self.assertTrue(self.lock.exists())
        self.assertFalse(self.lock.exists())

    def test_timeout_names_the_lock_path(self):
        with ors.file_lock(self.lock):
            with self.assertRaises(TimeoutError) as caught:
                with ors.file_lock(self.lock, timeout=0.05):
                    self.fail("second acquisition should not succeed")
        self.assertIn(str(self.lock), str(caught.exception))

    def test_stale_lock_is_reclaimed(self):
        self.lock.write_text("held by a dead process", encoding="utf-8")
        old = time.time() - 3600
        os.utime(self.lock, (old, old))
        with ors.file_lock(self.lock, timeout=1.0, stale_after=60.0):
            self.assertTrue(self.lock.exists())
        self.assertFalse(self.lock.exists())

    def test_lock_is_exclusive_across_threads(self):
        active = 0
        peak = 0
        guard = threading.Lock()

        def worker():
            nonlocal active, peak
            for _ in range(15):
                with ors.file_lock(self.lock, timeout=10.0):
                    with guard:
                        active += 1
                        peak = max(peak, active)
                    time.sleep(0.001)
                    with guard:
                        active -= 1

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(peak, 1)
        self.assertFalse(self.lock.exists())


class SidecarUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.sidecar = self.tmp / "G-OBS.product-audit.json"

    def update(
        self,
        phase="discover",
        candidate_id="C-01",
        rel="discover/run-001/result.json",
        goal_id="G-OBS",
    ):
        return ors.update_sidecar(self.sidecar, goal_id, candidate_id, phase, rel)

    def test_creates_a_v2_sidecar(self):
        value, problems = self.update()
        self.assertEqual(problems, [])
        self.assertEqual(value["schema"], "product-audit/2")
        self.assertEqual(value["goal_id"], "G-OBS")
        self.assertEqual(value["current_candidate"], "C-01")
        self.assertEqual(len(value["rounds"]), 1)
        entry = value["rounds"][0]
        self.assertEqual(entry["candidate_id"], "C-01")
        self.assertEqual(entry["discover_ref"], "discover/run-001/result.json")
        self.assertEqual(entry["compare_ref"], "")
        self.assertEqual(entry["review_ref"], "")
        on_disk = json.loads(self.sidecar.read_text(encoding="utf-8"))
        self.assertEqual(on_disk, value)
        self.assertFalse((self.tmp / (self.sidecar.name + ".lock")).exists())

    def test_second_phase_keeps_the_first(self):
        self.update()
        value, problems = self.update(
            phase="compare", rel="compare/run-001/result.json"
        )
        self.assertEqual(problems, [])
        entry = value["rounds"][0]
        self.assertEqual(entry["discover_ref"], "discover/run-001/result.json")
        self.assertEqual(entry["compare_ref"], "compare/run-001/result.json")
        self.assertEqual(entry["review_ref"], "")

    def test_review_phase_ref_is_recorded(self):
        self.update()
        value, problems = self.update(rel="review/run-001/result.json", phase="review")
        self.assertEqual(problems, [])
        self.assertEqual(
            value["rounds"][0]["review_ref"], "review/run-001/result.json"
        )

    def test_history_rounds_are_preserved_in_order(self):
        self.update(candidate_id="C-01")
        self.update(
            phase="compare", candidate_id="C-01", rel="compare/run-001/result.json"
        )
        value, problems = self.update(
            candidate_id="C-02", rel="discover/run-001/result.json"
        )
        self.assertEqual(problems, [])
        self.assertEqual(value["current_candidate"], "C-02")
        rounds = value["rounds"]
        self.assertEqual([r["candidate_id"] for r in rounds], ["C-01", "C-02"])
        self.assertEqual(rounds[0]["discover_ref"], "discover/run-001/result.json")
        self.assertEqual(rounds[0]["compare_ref"], "compare/run-001/result.json")
        self.assertEqual(rounds[1]["discover_ref"], "discover/run-001/result.json")
        self.assertEqual(rounds[1]["compare_ref"], "")

    def test_unknown_sidecar_fields_survive(self):
        self.update()
        raw = json.loads(self.sidecar.read_text(encoding="utf-8"))
        raw["note"] = "keep me"
        self.sidecar.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        value, problems = self.update(
            phase="compare", rel="compare/run-001/result.json"
        )
        self.assertEqual(problems, [])
        self.assertEqual(value["note"], "keep me")

    def test_invalid_result_rel_paths_are_rejected(self):
        bad_paths = (
            "",
            "   ",
            "../escape/result.json",
            "evidence/../escape.json",
            str(self.tmp / "absolute" / "result.json"),
            "evidence\\result.json",
            3,
            None,
        )
        for rel in bad_paths:
            value, problems = self.update(rel=rel)
            self.assertIsNone(value, rel)
            self.assertTrue(problems, rel)
        self.assertFalse(self.sidecar.exists())

    def test_invalid_phase_is_rejected(self):
        value, problems = self.update(phase="observe")
        self.assertIsNone(value)
        self.assertTrue(any("phase" in p for p in problems), problems)
        self.assertFalse(self.sidecar.exists())

    def test_invalid_identity_is_rejected(self):
        for kwargs in ({"goal_id": ""}, {"candidate_id": " "}):
            value, problems = self.update(**kwargs)
            self.assertIsNone(value, kwargs)
            self.assertTrue(problems, kwargs)
        self.assertFalse(self.sidecar.exists())

    def test_failed_replace_keeps_original_bytes(self):
        value, problems = self.update()
        self.assertEqual(problems, [])
        before = self.sidecar.read_bytes()
        with mock.patch.object(ors.os, "replace", side_effect=OSError("disk full")):
            value, problems = self.update(
                phase="compare", rel="compare/run-001/result.json"
            )
        self.assertIsNone(value)
        self.assertTrue(any("failed to write sidecar" in p for p in problems), problems)
        self.assertEqual(self.sidecar.read_bytes(), before)
        leftovers = [p.name for p in self.tmp.iterdir() if ".tmp" in p.name]
        self.assertEqual(leftovers, [])

    def test_unreadable_sidecar_fails_closed(self):
        for raw in ("{not json", "[1, 2, 3]"):
            self.sidecar.write_text(raw, encoding="utf-8")
            before = self.sidecar.read_bytes()
            value, problems = self.update()
            self.assertIsNone(value, raw)
            self.assertTrue(problems, raw)
            self.assertEqual(self.sidecar.read_bytes(), before)

    def test_concurrent_updates_do_not_corrupt_the_sidecar(self):
        results = []
        errors = []

        def writer(phase, rel):
            try:
                results.append(
                    ors.update_sidecar(self.sidecar, "G-OBS", "C-01", phase, rel)
                )
            except Exception as exc:  # noqa: BLE001 - surfaced via errors list
                errors.append(exc)

        threads = [
            threading.Thread(target=writer, args=("discover", "discover/run-001/result.json")),
            threading.Thread(target=writer, args=("compare", "compare/run-001/result.json")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        for value, problems in results:
            self.assertEqual(problems, [])
            self.assertIsNotNone(value)
        stored = json.loads(self.sidecar.read_text(encoding="utf-8"))
        self.assertEqual(stored["schema"], "product-audit/2")
        self.assertEqual(len(stored["rounds"]), 1)
        entry = stored["rounds"][0]
        self.assertEqual(entry["discover_ref"], "discover/run-001/result.json")
        self.assertEqual(entry["compare_ref"], "compare/run-001/result.json")
        self.assertFalse((self.tmp / (self.sidecar.name + ".lock")).exists())


class LoadSidecarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_missing_sidecar_is_empty_success(self):
        value, problems = ors.load_sidecar(self.tmp / "missing.json")
        self.assertIsNone(value)
        self.assertEqual(problems, [])

    def test_valid_sidecar_is_returned(self):
        target = self.tmp / "sidecar.json"
        target.write_text('{"schema": "product-audit/2"}', encoding="utf-8")
        value, problems = ors.load_sidecar(target)
        self.assertEqual(problems, [])
        self.assertEqual(value, {"schema": "product-audit/2"})

    def test_bom_is_accepted(self):
        target = self.tmp / "sidecar.json"
        target.write_bytes(b"\xef\xbb\xbf" + b'{"a": 1}\n')
        value, problems = ors.load_sidecar(target)
        self.assertEqual(problems, [])
        self.assertEqual(value, {"a": 1})

    def test_invalid_json_is_reported(self):
        target = self.tmp / "sidecar.json"
        target.write_text("{oops", encoding="utf-8")
        value, problems = ors.load_sidecar(target)
        self.assertIsNone(value)
        self.assertTrue(any("invalid JSON" in p for p in problems), problems)

    def test_non_object_is_reported(self):
        target = self.tmp / "sidecar.json"
        target.write_text("[]", encoding="utf-8")
        value, problems = ors.load_sidecar(target)
        self.assertIsNone(value)
        self.assertTrue(any("JSON object" in p for p in problems), problems)


class AdoptReviewTests(unittest.TestCase):
    received_at = "2026-09-21T11:00:00Z"
    discover_bytes = b"discover-result-bytes"
    compare_bytes = b"compare-result-bytes"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.cdir = self.tmp / "cand"
        self.project_root = self.tmp / "project"
        self.project_root.mkdir()
        self.discover_path = self.cdir / "discover.json"
        self.compare_path = self.cdir / "compare.json"
        self.cdir.mkdir(parents=True, exist_ok=True)
        self.discover_path.write_bytes(self.discover_bytes)
        self.compare_path.write_bytes(self.compare_bytes)

    @property
    def discover_hash(self):
        return hashlib.sha256(self.discover_bytes).hexdigest()

    @property
    def compare_hash(self):
        return hashlib.sha256(self.compare_bytes).hexdigest()

    def adopt(
        self,
        payload=None,
        envelope=None,
        trace=_UNSET,
        discover_path=_UNSET,
        compare_path=_UNSET,
        **kwargs,
    ):
        if payload is None:
            payload = make_review_payload()
        if envelope is None:
            envelope = make_review_envelope()
        if trace is _UNSET:
            trace = make_review_trace()
        if discover_path is _UNSET:
            discover_path = self.discover_path
        if compare_path is _UNSET:
            compare_path = self.compare_path
        kwargs.setdefault("received_at", self.received_at)
        return ors.adopt_review(
            self.cdir,
            self.project_root,
            payload,
            envelope,
            discover_path,
            compare_path,
            trace,
            **kwargs,
        )

    def assert_rejected(self, payload, envelope=None, trace=_UNSET, **kwargs):
        path, problems = self.adopt(
            payload=payload, envelope=envelope, trace=trace, run_id="run-001", **kwargs
        )
        self.assertIsNone(path)
        self.assertTrue(problems)
        run = self.cdir / "review" / "run-001"
        self.assertFalse((run / "result.json").exists())
        self.assertTrue(
            (run / "attempts" / "attempt-001.attempt.json").is_file(), problems
        )
        return problems

    def test_adoption_writes_result_with_computed_hashes(self):
        payload = make_review_payload()
        path, problems = self.adopt(payload=payload)
        self.assertEqual(problems, [])
        self.assertEqual(path, self.cdir / "review" / "run-001" / "result.json")

        stored = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(stored["discover_hash"], self.discover_hash)
        self.assertEqual(stored["compare_hash"], self.compare_hash)
        self.assertEqual(stored["reviewer_session_id"], "ses_reviewer")
        self.assertEqual(stored["model"], "test-model")
        self.assertEqual(stored["attempt"], 1)
        self.assertEqual(stored["received_at"], self.received_at)
        self.assertEqual(stored["verdict"], payload["verdict"])
        self.assertEqual(stored["notes"], payload["notes"])

        attempts = path.parent / "attempts"
        attempt = json.loads(
            (attempts / "attempt-001.attempt.json").read_text(encoding="utf-8")
        )
        self.assertEqual(json.loads(attempt["raw_text"]), payload)
        errors = json.loads(
            (attempts / "attempt-001.errors.json").read_text(encoding="utf-8")
        )
        self.assertEqual(errors["parsed_ok"], True)

    def test_payload_carried_correct_hash_is_allowed(self):
        payload = make_review_payload(discover_hash=self.discover_hash)
        path, problems = self.adopt(payload=payload)
        self.assertEqual(problems, [])
        self.assertIsNotNone(path)

    def test_payload_carried_conflicting_hash_is_rejected(self):
        payload = make_review_payload(discover_hash="b" * 64)
        problems = self.assert_rejected(payload)
        self.assertTrue(any("conflicts" in p for p in problems), problems)

    def test_envelope_carried_conflicting_hash_is_rejected(self):
        envelope = make_review_envelope(compare_hash="c" * 64)
        problems = self.assert_rejected(make_review_payload(), envelope=envelope)
        self.assertTrue(any("conflicts" in p for p in problems), problems)

    def test_missing_hash_source_is_rejected(self):
        problems = self.assert_rejected(
            make_review_payload(), discover_path=self.cdir / "missing.json"
        )
        self.assertTrue(any("cannot hash" in p for p in problems), problems)

    def test_reviewer_skill_load_is_required(self):
        problems = self.assert_rejected(
            make_review_payload(), trace=make_review_trace(skill="product-observer")
        )
        self.assertTrue(
            any("no completed reviewer skill load" in p for p in problems), problems
        )

    def test_missing_reviewer_session_is_rejected(self):
        problems = self.assert_rejected(
            make_review_payload(), trace=make_review_trace(session_id="ses_other")
        )
        self.assertTrue(
            any("not found in the runtime trace" in p for p in problems), problems
        )

    def test_envelope_missing_fields_are_rejected(self):
        for field in ("reviewer_session_id", "model"):
            envelope = make_review_envelope()
            del envelope[field]
            problems = self.assert_rejected(make_review_payload(), envelope=envelope)
            self.assertTrue(any(field in p for p in problems), (field, problems))

    def test_envelope_bad_attempt_is_rejected(self):
        for value in ("1", 0, True):
            problems = self.assert_rejected(
                make_review_payload(), envelope=make_review_envelope(attempt=value)
            )
            self.assertTrue(any("attempt" in p for p in problems), (value, problems))

    def test_goal_and_candidate_are_preserved_from_envelope(self):
        envelope = make_review_envelope(goal_id="G-OBS", candidate_id="C-01")
        path, problems = self.adopt(envelope=envelope)
        self.assertEqual(problems, [])
        stored = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(stored["goal_id"], "G-OBS")
        self.assertEqual(stored["candidate_id"], "C-01")

    def test_invalid_goal_id_in_envelope_is_rejected(self):
        problems = self.assert_rejected(
            make_review_payload(), envelope=make_review_envelope(goal_id=3)
        )
        self.assertTrue(any("goal_id" in p for p in problems), problems)

    def test_identical_review_is_idempotent(self):
        first_path, problems = self.adopt(run_id="run-001")
        self.assertEqual(problems, [])
        original = first_path.read_bytes()

        second_path, problems = self.adopt(run_id="run-001")
        self.assertEqual(problems, [])
        self.assertEqual(second_path, first_path)
        self.assertEqual(first_path.read_bytes(), original)
        self.assertTrue(
            (first_path.parent / "attempts" / "attempt-002.attempt.json").is_file()
        )

    def test_different_review_conflicts_and_keeps_the_file(self):
        first_path, _ = self.adopt(run_id="run-001")
        original = first_path.read_bytes()

        payload = make_review_payload(notes="changed after review")
        second_path, problems = self.adopt(payload=payload, run_id="run-001")
        self.assertIsNone(second_path)
        self.assertTrue(any("conflict" in p for p in problems), problems)
        self.assertEqual(first_path.read_bytes(), original)

    def test_second_run_gets_run_002(self):
        first_path, problems = self.adopt(payload=make_review_payload(notes="first"))
        self.assertEqual(problems, [])
        second_path, problems = self.adopt(payload=make_review_payload(notes="second"))
        self.assertEqual(problems, [])
        self.assertEqual(
            first_path, self.cdir / "review" / "run-001" / "result.json"
        )
        self.assertEqual(
            second_path, self.cdir / "review" / "run-002" / "result.json"
        )

    def test_invalid_payload_is_recorded_but_not_adopted(self):
        payload = make_review_payload()
        payload["verdict"] = "maybe"
        problems = self.assert_rejected(payload)
        self.assertTrue(any("verdict" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
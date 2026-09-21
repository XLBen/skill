"""S12a: observation dispatch model provenance.

Covers the session-model normalization shared by the runtime trace export and
the observation provenance gate (``observation_results.parse_session_model`` /
``model_mismatch_problems`` / ``provenance_problems(expected_model=...)``) plus
the native-store verify round trip on a temporary SQLite session store.
"""

import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import observation_results as ors  # noqa: E402
from runtime_trace import export_trace, verify_native_trace  # noqa: E402

STORE_MODEL = '{"id":"gpt-5.6-sol","providerID":"openai","variant":"high"}'
OTHER_MODEL = '{"id":"deepseek-flash","providerID":"deepseek","variant":"max"}'
NORMALIZED = {"provider_id": "openai", "model_id": "gpt-5.6-sol", "variant": "high"}


def session_entry(model=STORE_MODEL, sid="ses_obs"):
    return {"id": sid, "model": model}


def make_trace(
    session_id="ses_obs",
    model=STORE_MODEL,
    skill="product-observer",
    status="completed",
):
    return {
        "sessions": [{"id": session_id, "parent_id": None, "model": model}],
        "skill_events": [{"session_id": session_id, "skill": skill, "status": status}],
    }


class ParseSessionModelTests(unittest.TestCase):
    def test_json_string_is_normalized(self):
        self.assertEqual(ors.parse_session_model(STORE_MODEL), NORMALIZED)

    def test_store_style_dict_is_normalized(self):
        value = {"id": "deepseek-flash", "providerID": "deepseek", "variant": "max"}
        self.assertEqual(
            ors.parse_session_model(value),
            {"provider_id": "deepseek", "model_id": "deepseek-flash", "variant": "max"},
        )

    def test_normalized_dict_round_trips(self):
        self.assertEqual(ors.parse_session_model(NORMALIZED), NORMALIZED)

    def test_missing_variant_normalizes_to_none(self):
        self.assertEqual(
            ors.parse_session_model('{"id":"m","providerID":"p"}'),
            {"provider_id": "p", "model_id": "m", "variant": None},
        )

    def test_blank_variant_normalizes_to_none(self):
        self.assertEqual(
            ors.parse_session_model('{"id":"m","providerID":"p","variant":"  "}'),
            {"provider_id": "p", "model_id": "m", "variant": None},
        )

    def test_invalid_inputs_return_none(self):
        for value in (
            None,
            "",
            "not json",
            '["openai"]',
            '{"providerID":"openai"}',
            '{"id":"gpt-5.6-sol"}',
            '{"id":"","providerID":"openai"}',
            {"provider_id": "", "model_id": "m"},
            {"provider_id": "p", "model_id": ""},
            3,
            [],
        ):
            with self.subTest(value=value):
                self.assertIsNone(ors.parse_session_model(value))


class ModelMismatchTests(unittest.TestCase):
    def test_matching_string_expected_model_passes(self):
        self.assertEqual(
            ors.model_mismatch_problems(session_entry(), "openai/gpt-5.6-sol"), []
        )

    def test_matching_dict_expected_model_passes(self):
        self.assertEqual(
            ors.model_mismatch_problems(
                session_entry(), {"provider_id": "openai", "model_id": "gpt-5.6-sol"}
            ),
            [],
        )

    def test_variant_difference_is_ignored(self):
        entry = session_entry(
            '{"id":"gpt-5.6-sol","providerID":"openai","variant":"low"}'
        )
        self.assertEqual(
            ors.model_mismatch_problems(entry, "openai/gpt-5.6-sol"), []
        )

    def test_provider_mismatch_names_expected_and_actual(self):
        problems = ors.model_mismatch_problems(session_entry(), "anthropic/gpt-5.6-sol")
        self.assertTrue(
            any("anthropic" in p and "openai" in p for p in problems), problems
        )

    def test_model_mismatch_names_expected_and_actual(self):
        problems = ors.model_mismatch_problems(session_entry(), "openai/gpt-5.0")
        self.assertTrue(
            any("gpt-5.0" in p and "gpt-5.6-sol" in p for p in problems), problems
        )

    def test_missing_trace_model_is_reported(self):
        for model in (None, "not json", '{"providerID":"openai"}'):
            with self.subTest(model=model):
                problems = ors.model_mismatch_problems(
                    session_entry(model), "openai/gpt-5.6-sol"
                )
                self.assertEqual(
                    problems,
                    ["trace does not record a parsable model for session ses_obs"],
                )

    def test_unparsable_expected_model_fails_closed(self):
        for expected in (None, "", "gpt-5.6-sol", {"provider_id": "openai"}):
            with self.subTest(expected=expected):
                problems = ors.model_mismatch_problems(session_entry(), expected)
                self.assertTrue(any("expected model" in p for p in problems), problems)


class ProvenanceModelTests(unittest.TestCase):
    def test_expected_model_match_passes(self):
        self.assertEqual(
            ors.provenance_problems(
                make_trace(), "ses_obs", expected_model="openai/gpt-5.6-sol"
            ),
            [],
        )

    def test_expected_model_dict_is_accepted(self):
        self.assertEqual(
            ors.provenance_problems(
                make_trace(),
                "ses_obs",
                expected_model={"provider_id": "openai", "model_id": "gpt-5.6-sol"},
            ),
            [],
        )

    def test_expected_model_mismatch_is_reported(self):
        problems = ors.provenance_problems(
            make_trace(), "ses_obs", expected_model="deepseek/deepseek-flash"
        )
        self.assertTrue(
            any("does not match expected" in p for p in problems), problems
        )

    def test_default_none_keeps_legacy_behavior(self):
        trace = make_trace(model=None)
        self.assertEqual(ors.provenance_problems(trace, "ses_obs"), [])
        self.assertTrue(
            ors.provenance_problems(
                trace, "ses_obs", expected_model="openai/gpt-5.6-sol"
            )
        )

    def test_unknown_session_reports_only_the_missing_session(self):
        problems = ors.provenance_problems(
            make_trace(), "ses_missing", expected_model="openai/gpt-5.6-sol"
        )
        self.assertTrue(any("not found" in p for p in problems), problems)
        self.assertFalse(any("parsable model" in p for p in problems), problems)

    def test_skill_problem_and_model_problem_are_both_reported(self):
        problems = ors.provenance_problems(
            make_trace(status="error"),
            "ses_obs",
            expected_model="deepseek/deepseek-flash",
        )
        self.assertTrue(
            any("no completed product-observer skill load" in p for p in problems),
            problems,
        )
        self.assertTrue(
            any("does not match expected" in p for p in problems), problems
        )


def make_model_db(path, sessions):
    con = sqlite3.connect(path)
    con.executescript(
        """
        create table session (
            id text primary key, parent_id text, directory text,
            agent text, model text, time_created integer, time_updated integer
        );
        create table part (
            id text primary key, message_id text, session_id text,
            time_created integer, time_updated integer, data text
        );
        """
    )
    for s in sessions:
        con.execute(
            "insert into session (id, parent_id, directory, agent, model, time_created, time_updated) "
            "values (?,?,?,?,?,?,?)",
            (
                s["id"],
                s.get("parent_id"),
                s.get("directory", "D:/proj"),
                s.get("agent"),
                s.get("model"),
                1,
                1,
            ),
        )
    con.commit()
    con.close()


class ExportModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.db = self.tmp / "opencode.db"
        make_model_db(
            self.db,
            [
                {"id": "ses_ctrl", "agent": "build", "model": STORE_MODEL},
                {
                    "id": "ses_obs",
                    "parent_id": "ses_ctrl",
                    "agent": "product-observer",
                    "model": OTHER_MODEL,
                },
                {
                    "id": "ses_nomodel",
                    "parent_id": "ses_ctrl",
                    "agent": "general",
                    "model": None,
                },
            ],
        )

    def export(self):
        return export_trace(Path("D:/proj"), str(self.db), None)

    def test_export_records_parsed_model_and_raw(self):
        trace = self.export()
        by_id = {s["id"]: s for s in trace["sessions"]}
        self.assertEqual(by_id["ses_ctrl"]["model"], NORMALIZED)
        self.assertEqual(by_id["ses_ctrl"]["model_raw"], STORE_MODEL)
        self.assertEqual(
            by_id["ses_obs"]["model"],
            {"provider_id": "deepseek", "model_id": "deepseek-flash", "variant": "max"},
        )
        self.assertEqual(by_id["ses_obs"]["model_raw"], OTHER_MODEL)
        self.assertIsNone(by_id["ses_nomodel"]["model"])
        self.assertIsNone(by_id["ses_nomodel"]["model_raw"])
        for entry in trace["sessions"]:
            self.assertEqual(
                entry["model"], ors.parse_session_model(entry["model_raw"])
            )

    def test_verify_accepts_matching_models(self):
        self.assertEqual(verify_native_trace(self.export()), [])

    def test_verify_rejects_tampered_variant(self):
        trace = self.export()
        entry = next(s for s in trace["sessions"] if s["id"] == "ses_obs")
        entry["model"]["variant"] = "low"
        problems = verify_native_trace(trace)
        self.assertTrue(
            any("ses_obs" in p and "variant" in p and "max" in p for p in problems),
            problems,
        )

    def test_verify_rejects_tampered_provider_and_model(self):
        trace = self.export()
        entry = next(s for s in trace["sessions"] if s["id"] == "ses_obs")
        entry["model"]["provider_id"] = "openai"
        entry["model"]["model_id"] = "gpt-5.6-sol"
        problems = verify_native_trace(trace)
        self.assertTrue(any("provider_id" in p for p in problems), problems)
        self.assertTrue(any("model_id" in p for p in problems), problems)

    def test_verify_rejects_missing_model_against_store(self):
        trace = self.export()
        entry = next(s for s in trace["sessions"] if s["id"] == "ses_obs")
        entry["model"] = None
        problems = verify_native_trace(trace)
        self.assertTrue(
            any("records no model but the source store has one" in p for p in problems),
            problems,
        )

    def test_verify_rejects_model_when_store_is_empty(self):
        trace = self.export()
        entry = next(s for s in trace["sessions"] if s["id"] == "ses_nomodel")
        entry["model"] = ors.parse_session_model(STORE_MODEL)
        problems = verify_native_trace(trace)
        self.assertTrue(
            any("empty model in the source store" in p for p in problems), problems
        )

    def test_verify_rejects_unparsable_trace_model(self):
        trace = self.export()
        entry = next(s for s in trace["sessions"] if s["id"] == "ses_ctrl")
        entry["model"] = "garbage"
        problems = verify_native_trace(trace)
        self.assertTrue(any("not a parsable" in p for p in problems), problems)

    def test_older_trace_without_model_key_is_untouched(self):
        trace = self.export()
        for entry in trace["sessions"]:
            entry.pop("model", None)
            entry.pop("model_raw", None)
        self.assertEqual(verify_native_trace(trace), [])


if __name__ == "__main__":
    unittest.main()

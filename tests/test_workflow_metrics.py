import contextlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from workflow_metrics import (  # noqa: E402
    METRICS_SCHEMA,
    command_digest,
    compare_metrics,
    export_metrics,
    main,
    merge_intervals,
    normalize_command,
    parse_model,
)

T0 = 1_700_000_000_000


def make_db(path, sessions, messages=(), parts=(), full=True):
    con = sqlite3.connect(path)
    if full:
        con.executescript(
            """
            create table session (
                id text primary key, parent_id text, directory text, agent text,
                model text, cost real, tokens_input integer, tokens_output integer,
                tokens_reasoning integer, tokens_cache_read integer,
                tokens_cache_write integer, time_created integer, time_updated integer
            );
            """
        )
    else:
        con.executescript(
            """
            create table session (
                id text primary key, parent_id text, directory text, agent text,
                time_created integer, time_updated integer
            );
            """
        )
    con.executescript(
        """
        create table message (
            id text primary key, session_id text, time_created integer,
            time_updated integer, data text
        );
        create table part (
            id text primary key, message_id text, session_id text,
            time_created integer, time_updated integer, data text
        );
        """
    )
    for s in sessions:
        columns = ["id", "parent_id", "directory", "agent", "time_created", "time_updated"]
        values = [
            s["id"],
            s.get("parent_id"),
            s.get("directory", "D:/proj"),
            s.get("agent"),
            s.get("time_created", T0),
            s.get("time_updated", T0 + 60_000),
        ]
        if full:
            columns += [
                "model", "cost", "tokens_input", "tokens_output",
                "tokens_reasoning", "tokens_cache_read", "tokens_cache_write",
            ]
            values += [
                s.get("model"),
                s.get("cost"),
                s.get("tokens_input"),
                s.get("tokens_output"),
                s.get("tokens_reasoning"),
                s.get("tokens_cache_read"),
                s.get("tokens_cache_write"),
            ]
        placeholders = ",".join("?" * len(columns))
        con.execute(
            f"insert into session ({','.join(columns)}) values ({placeholders})", values
        )
    for index, m in enumerate(messages):
        con.execute(
            "insert into message (id, session_id, time_created, time_updated, data) values (?,?,?,?,?)",
            (
                m.get("id", f"m{index}"),
                m["session_id"],
                m.get("time_created", T0),
                m.get("time_updated", T0),
                json.dumps(m["data"]),
            ),
        )
    for index, p in enumerate(parts):
        con.execute(
            "insert into part (id, message_id, session_id, time_created, time_updated, data) values (?,?,?,?,?,?)",
            (
                p.get("id", f"p{index}"),
                "m-" + str(index),
                p["session_id"],
                p.get("time_created", T0),
                p.get("time_updated", T0),
                json.dumps(p["data"]),
            ),
        )
    con.commit()
    con.close()


def assistant_message(session, created, completed, tokens=None, cost=None, model=None, error=None):
    data = {
        "role": "assistant",
        "time": {"created": created, "completed": completed},
    }
    if tokens:
        data["tokens"] = tokens
    if cost is not None:
        data["cost"] = cost
    if model:
        data["modelID"] = model[0]
        data["providerID"] = model[1]
    if error:
        data["error"] = error
    return {"session_id": session, "data": data}


def bash_part(session, start, end, command, call_id="call_1", status="completed"):
    return {
        "session_id": session,
        "data": {
            "type": "tool",
            "tool": "bash",
            "callID": call_id,
            "state": {
                "status": status,
                "input": {"command": command},
                "time": {"start": start, "end": end},
            },
        },
        "time_created": start,
        "time_updated": end,
    }


class IntervalTests(unittest.TestCase):
    def test_merge_overlapping_and_adjacent(self):
        total, merged = merge_intervals([(0, 100), (50, 150), (150, 200), (500, 600)])
        self.assertEqual(total, 300)
        self.assertEqual(merged, [(0, 200), (500, 600)])

    def test_merge_ignores_invalid_intervals(self):
        total, merged = merge_intervals([(10, 5), (None, 3), (0, 10)])
        self.assertEqual(total, 10)
        self.assertEqual(merged, [(0, 10)])


class ModelParsingTests(unittest.TestCase):
    def test_parses_json_string_plain_string_and_object(self):
        self.assertEqual(
            parse_model('{"id":"glm-5.3","providerID":"zhipuai-coding-plan","variant":"max"}'),
            {"id": "glm-5.3", "provider": "zhipuai-coding-plan", "variant": "max"},
        )
        self.assertEqual(parse_model("deepseek-v4-flash"), {"id": "deepseek-v4-flash", "provider": None, "variant": None})
        self.assertEqual(parse_model({"modelID": "gpt-5.6-luna"}), {"id": "gpt-5.6-luna", "provider": None, "variant": None})
        self.assertIsNone(parse_model(None))
        self.assertIsNone(parse_model("  "))


class ExportTests(unittest.TestCase):
    def test_export_summarizes_sessions_messages_and_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            db = tmp / "opencode.db"
            make_db(
                db,
                sessions=[
                    {
                        "id": "ses_ctrl",
                        "agent": None,
                        "model": '{"id":"deepseek-v4-flash","providerID":"deepseek","variant":"max"}',
                        "time_created": T0,
                        "time_updated": T0 + 600_000,
                    },
                    {
                        "id": "ses_worker",
                        "parent_id": "ses_ctrl",
                        "agent": "mvp-worker",
                        "time_created": T0 + 100_000,
                        "time_updated": T0 + 500_000,
                    },
                ],
                messages=[
                    assistant_message(
                        "ses_ctrl", T0, T0 + 50_000,
                        tokens={"input": 1000, "output": 100, "reasoning": 10, "cache": {"read": 500, "write": 0}},
                        cost=0.01,
                        model=("deepseek-v4-flash", "deepseek"),
                    ),
                    assistant_message(
                        "ses_worker", T0 + 120_000, T0 + 480_000,
                        tokens={"input": 2000, "output": 200, "reasoning": 20, "cache": {"read": 800, "write": 0}},
                        cost=0.02,
                        model=("deepseek-v4-flash", "deepseek"),
                    ),
                ],
                parts=[
                    bash_part("ses_ctrl", T0 + 10_000, T0 + 20_000, "pytest -q"),
                    bash_part("ses_worker", T0 + 150_000, T0 + 450_000, "npm test", call_id="call_2"),
                ],
            )
            report = export_metrics(Path("D:/proj"), str(db), None)
            self.assertEqual(report["schema"], METRICS_SCHEMA)
            self.assertTrue(report["availability"]["database"])
            self.assertTrue(report["availability"]["message_tokens"])
            self.assertTrue(report["availability"]["tool_times"])
            self.assertEqual(report["totals"]["sessions"], 2)
            self.assertEqual(report["totals"]["child_sessions"], 1)
            self.assertEqual(report["totals"]["assistant_turns"], 2)
            self.assertEqual(report["totals"]["input_tokens"], 3000)
            self.assertEqual(report["totals"]["output_tokens"], 300)
            self.assertEqual(report["totals"]["cache_read"], 1300)
            self.assertAlmostEqual(report["totals"]["cost"], 0.03, places=6)
            self.assertEqual(len(report["tools"]), 2)
            worker_bash = next(
                t for t in report["tools"] if t["session_id"] == "ses_worker" and t["tool"] == "bash"
            )
            self.assertAlmostEqual(worker_bash["duration_sum_seconds"], 300.0)
            self.assertIn("deepseek/deepseek-v4-flash", report["models"])
            # message intervals: 50s + 360s; tool intervals: 10s + 300s
            # union: [T0, T0+50s] + [T0+120s, T0+480s] => 410s active
            self.assertAlmostEqual(report["totals"]["active_seconds"], 410.0)
            self.assertAlmostEqual(report["totals"]["span_seconds"], 480.0)
            by_id = {s["id"]: s for s in report["sessions"]}
            self.assertFalse(by_id["ses_ctrl"]["interrupted"])
            self.assertFalse(by_id["ses_worker"]["interrupted"])
            self.assertEqual(by_id["ses_worker"]["parent_id"], "ses_ctrl")

    def test_parallel_overlap_does_not_double_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "opencode.db"
            make_db(
                db,
                sessions=[
                    {"id": "ses_a", "time_created": T0, "time_updated": T0 + 200_000},
                    {"id": "ses_b", "parent_id": "ses_a", "agent": "mvp-worker", "time_created": T0 + 50_000, "time_updated": T0 + 250_000},
                ],
                messages=[
                    assistant_message("ses_a", T0, T0 + 200_000),
                    assistant_message("ses_b", T0 + 50_000, T0 + 250_000),
                ],
            )
            report = export_metrics(Path("D:/proj"), str(db), None)
            # 200s and 200s overlap by 150s => union 250s, never 400s
            self.assertAlmostEqual(report["totals"]["active_seconds"], 250.0)
            self.assertAlmostEqual(report["totals"]["span_seconds"], 250.0)

    def test_missing_columns_times_and_interrupted_sessions_degrade_honestly(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "opencode.db"
            make_db(
                db,
                sessions=[
                    {"id": "ses_old", "time_created": T0, "time_updated": T0 + 60_000},
                ],
                messages=[
                    {
                        "session_id": "ses_old",
                        "data": {"role": "assistant", "time": {"created": T0}},  # never completed
                    },
                ],
                parts=[
                    {
                        "session_id": "ses_old",
                        "data": {"type": "tool", "tool": "bash", "state": {"status": "running", "input": {"command": "long-task"}}},
                    },
                ],
                full=False,
            )
            report = export_metrics(Path("D:/proj"), str(db), None)
            availability = report["availability"]
            self.assertTrue(availability["database"])
            self.assertFalse(availability["session_columns"])
            self.assertFalse(availability["message_tokens"])
            self.assertFalse(availability["message_times"])
            self.assertFalse(availability["tool_times"])
            self.assertIsNone(report["totals"]["input_tokens"])
            self.assertIsNone(report["totals"]["cost"])
            self.assertTrue(any("unavailable" in note for note in report["notes"]))
            session = report["sessions"][0]
            self.assertTrue(session["interrupted"])
            self.assertIsNone(session["tokens"])
            # fallback interval uses session row timestamps
            self.assertAlmostEqual(report["totals"]["active_seconds"], 60.0)

    def test_interrupted_session_with_no_finished_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "opencode.db"
            make_db(
                db,
                sessions=[{"id": "ses_alive", "time_created": T0, "time_updated": T0 + 10_000}],
                messages=[assistant_message("ses_alive", T0, None)],
            )
            report = export_metrics(Path("D:/proj"), str(db), None)
            self.assertTrue(report["sessions"][0]["interrupted"])

    def test_duplicate_command_candidates_flag_repeats_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "opencode.db"
            make_db(
                db,
                sessions=[
                    {"id": "ses_ctrl", "time_created": T0, "time_updated": T0 + 300_000},
                    {"id": "ses_worker", "parent_id": "ses_ctrl", "agent": "mvp-worker"},
                ],
                parts=[
                    bash_part("ses_ctrl", T0, T0 + 1_000, "pytest   -q  tests/a.py", call_id="c1"),
                    bash_part("ses_ctrl", T0 + 10_000, T0 + 11_000, "pytest -q tests/a.py", call_id="c2"),
                    bash_part("ses_worker", T0 + 20_000, T0 + 21_000, "python scripts/check.py --selftest", call_id="c3"),
                ],
            )
            report = export_metrics(Path("D:/proj"), str(db), None)
            candidates = report["duplicate_command_candidates"]
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["runs"], 2)
            self.assertIn("suspect-reusable", candidates[0]["note"])
            self.assertEqual(candidates[0]["digest"], command_digest("pytest -q tests/a.py"))

    def test_export_without_database_reports_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "metrics.json"
            code = main(["export", str(Path(tmp) / "proj"), "--db", str(Path(tmp) / "missing.db"), "--out", str(out)])
            self.assertEqual(code, 2)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertFalse(report["availability"]["database"])
            self.assertIn("export_error", report)

    def test_main_export_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            db = tmp / "opencode.db"
            make_db(db, sessions=[{"id": "ses_a"}], messages=[assistant_message("ses_a", T0, T0 + 1000)])
            out = tmp / "metrics.json"
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = main(["export", "D:/proj", "--db", str(db), "--out", str(out)])
            self.assertEqual(code, 0)
            self.assertIn("metrics written", stdout.getvalue())
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["schema"], METRICS_SCHEMA)


class CompareTests(unittest.TestCase):
    def test_compare_reports_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "opencode.db"
            make_db(
                db,
                sessions=[{"id": "ses_a"}],
                messages=[
                    assistant_message(
                        "ses_a", T0, T0 + 100_000,
                        tokens={"input": 1000, "output": 100, "reasoning": 0, "cache": {"read": 0, "write": 0}},
                    )
                ],
            )
            baseline = export_metrics(Path("D:/proj"), str(db), None)

            db2 = Path(tmp) / "opencode2.db"
            make_db(
                db2,
                sessions=[{"id": "ses_a"}],
                messages=[
                    assistant_message(
                        "ses_a", T0, T0 + 50_000,
                        tokens={"input": 500, "output": 50, "reasoning": 0, "cache": {"read": 0, "write": 0}},
                    )
                ],
            )
            candidate = export_metrics(Path("D:/proj"), str(db2), None)
            comparison = compare_metrics(baseline, candidate)
            self.assertEqual(comparison["schema"], "workflow-metrics-compare/1")
            self.assertEqual(comparison["deltas"]["input_tokens"]["delta"], -500)
            self.assertEqual(comparison["deltas"]["input_tokens"]["delta_percent"], -50.0)
            self.assertEqual(comparison["deltas"]["active_seconds"]["delta"], -50.0)
            self.assertIn("same task", comparison["note"])

    def test_compare_treats_missing_values_as_unavailable(self):
        comparison = compare_metrics(
            {"schema": METRICS_SCHEMA, "totals": {"span_seconds": None}},
            {"schema": METRICS_SCHEMA, "totals": {"span_seconds": 10}},
        )
        self.assertIsNone(comparison["deltas"]["span_seconds"]["delta"])

    def test_main_compare_invalid_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{}", encoding="utf-8")
            code = main(["compare", str(bad), str(bad)])
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()

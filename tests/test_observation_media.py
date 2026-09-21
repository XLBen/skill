"""S17: offline media capture surface -- ffmpeg/ffprobe argv, probe parsing,
media records, capture-chain verdicts and silence claims.

Everything here is offline: every process call is an injected fake runner.
Real ffmpeg/ffprobe execution, real recordings and real model perception are
S21 and remain BLOCKED until run there.
"""

import json
import sys
import unittest
import unittest.mock as mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import observation_media as om  # noqa: E402

HASH = "a" * 64


def probe_payload(has_video=True, has_audio=True, duration="12.5", format_name="mov,mp4"):
    streams = []
    if has_video:
        streams.append({"index": 0, "codec_type": "video", "codec_name": "h264", "width": 640})
    if has_audio:
        streams.append(
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
            }
        )
    format_block = {}
    if format_name is not None:
        format_block["format_name"] = format_name
    if duration is not None:
        format_block["duration"] = duration
    return {"format": format_block, "streams": streams}


def probe_run(payload=None, *, exit_code=0, timed_out=False, stdout=None, stderr=b""):
    if stdout is None:
        stdout = json.dumps(payload if payload is not None else {}).encode("utf-8")
    return {
        "exit_code": exit_code,
        "stdout_bytes": stdout,
        "stderr_bytes": stderr,
        "timed_out": timed_out,
    }


class FakeRunner:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, argv, timeout):
        self.calls.append((list(argv), timeout))
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def probe_media_result(has_video=True, has_audio=True):
    return {
        "ok": True,
        "has_video": has_video,
        "has_audio": has_audio,
        "duration_seconds": 12.5,
        "format_name": "mov,mp4",
        "streams": [],
        "problems": [],
    }


def media_record(kind, **overrides):
    return om.build_media_record(
        kind,
        "media/input.mp4",
        HASH,
        probe_media_result(),
        **overrides,
    )


def legal_audio_track(**overrides):
    record = om.build_media_record(
        "audio-track",
        "media/audio.wav",
        HASH,
        probe_media_result(has_video=False),
        audio_source="capture",
        commands=["ffmpeg -i product.mp4 -vn -acodec pcm_s16le product.wav"],
        perception_model="qwen3-omni",
        **overrides,
    )
    record["capture_chain"] = {
        "verdict": "product-silent",
        "evidence_ref": "evidence/capture-chain.json",
    }
    return record


def probe_with(signal, ok=True):
    return {"probe_media": {"ok": ok}, "signal": signal}


class ConstantsTests(unittest.TestCase):
    def test_media_kinds(self):
        self.assertEqual(
            om.MEDIA_KINDS,
            (
                "native-video",
                "frame-sampled",
                "audio-track",
                "audio-transcript",
                "audio-caption",
            ),
        )

    def test_record_schema_and_verdicts(self):
        self.assertEqual(om.MEDIA_RECORD_SCHEMA, "media-record/1")
        self.assertEqual(om.AUDIO_SOURCES, ("capture", "extract"))
        self.assertEqual(
            om.CAPTURE_VERDICTS, ("sound-present", "product-silent", "capture-unverified")
        )

    def test_media_model_env(self):
        self.assertEqual(
            om.MEDIA_MODEL_ENV,
            ("MEDIA_MODEL_BASE_URL", "MEDIA_MODEL_API_KEY", "MEDIA_MODEL_NAME"),
        )


class ArgvTests(unittest.TestCase):
    def test_ffprobe_argv_exact(self):
        self.assertEqual(
            om.ffprobe_argv("in.mp4"),
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                "in.mp4",
            ],
        )

    def test_extract_audio_argv_exact(self):
        self.assertEqual(
            om.extract_audio_argv("in.mp4", "out.wav"),
            ["ffmpeg", "-y", "-i", "in.mp4", "-vn", "-acodec", "pcm_s16le", "out.wav"],
        )

    def test_extract_frames_argv_with_fps(self):
        self.assertEqual(
            om.extract_frames_argv("in.mp4", "frames/%04d.png", fps=2),
            ["ffmpeg", "-y", "-i", "in.mp4", "-vf", "fps=2", "frames/%04d.png"],
        )

    def test_extract_frames_argv_with_interval(self):
        self.assertEqual(
            om.extract_frames_argv("in.mp4", "frames/%04d.png", interval=0.5),
            ["ffmpeg", "-y", "-i", "in.mp4", "-vf", "fps=1/0.5", "frames/%04d.png"],
        )

    def test_extract_frames_requires_exactly_one_selector(self):
        with self.assertRaises(ValueError):
            om.extract_frames_argv("in.mp4", "f.png", interval=1, fps=1)
        with self.assertRaises(ValueError):
            om.extract_frames_argv("in.mp4", "f.png")

    def test_extract_frames_rejects_non_positive_or_non_numeric(self):
        for value in (0, -1, 0.0, True, "x", None):
            with self.assertRaises(ValueError):
                om.extract_frames_argv("in.mp4", "f.png", fps=value)
            with self.assertRaises(ValueError):
                om.extract_frames_argv("in.mp4", "f.png", interval=value)

    def test_clip_argv_exact(self):
        self.assertEqual(
            om.clip_argv("in.mp4", 10, 20, "out.mp4"),
            [
                "ffmpeg",
                "-y",
                "-ss",
                "10",
                "-to",
                "20",
                "-i",
                "in.mp4",
                "-c",
                "copy",
                "out.mp4",
            ],
        )

    def test_clip_argv_accepts_numeric_strings_and_decimal(self):
        self.assertEqual(
            om.clip_argv("in.mp4", "0.5", 1.25, "out.mp4"),
            ["ffmpeg", "-y", "-ss", "0.5", "-to", "1.25", "-i", "in.mp4", "-c", "copy", "out.mp4"],
        )

    def test_clip_argv_rejects_bad_range(self):
        with self.assertRaises(ValueError):
            om.clip_argv("in.mp4", 20, 10, "out.mp4")
        with self.assertRaises(ValueError):
            om.clip_argv("in.mp4", 10, 10, "out.mp4")
        with self.assertRaises(ValueError):
            om.clip_argv("in.mp4", -1, 10, "out.mp4")

    def test_empty_or_malformed_paths_rejected(self):
        for builder, args in (
            (om.ffprobe_argv, ("",)),
            (om.ffprobe_argv, ("  ",)),
            (om.ffprobe_argv, (None,)),
            (om.ffprobe_argv, (7,)),
            (om.extract_audio_argv, ("in.mp4", "")),
            (om.extract_audio_argv, (None, "out.wav")),
            (om.extract_frames_argv, ("", "f.png")),
            (om.extract_frames_argv, ("in.mp4", " ")),
            (om.clip_argv, ("in.mp4", 0, 1, "")),
            (om.clip_argv, ("", 0, 1, "out.mp4")),
        ):
            with self.assertRaises(ValueError):
                builder(*args)

    def test_nul_rejected(self):
        with self.assertRaises(ValueError):
            om.ffprobe_argv("bad\x00name.mp4")
        with self.assertRaises(ValueError):
            om.extract_audio_argv("bad\x00name.mp4", "out.wav")

    def test_builder_does_not_touch_filesystem(self):
        argv = om.ffprobe_argv("missing-file.mp4")
        self.assertEqual(argv[-1], "missing-file.mp4")


class ProbeMediaTests(unittest.TestCase):
    def test_valid_probe_with_video_and_audio(self):
        runner = FakeRunner(probe_run(probe_payload()))
        result = om.probe_media("in.mp4", runner)
        self.assertTrue(result["ok"])
        self.assertTrue(result["has_video"])
        self.assertTrue(result["has_audio"])
        self.assertEqual(result["duration_seconds"], 12.5)
        self.assertEqual(result["format_name"], "mov,mp4")
        self.assertEqual(result["problems"], [])
        self.assertEqual(
            result["streams"][0],
            {"index": 0, "codec_type": "video", "codec_name": "h264"},
        )
        self.assertEqual(
            result["streams"][1],
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": 48000,
                "channels": 2,
            },
        )

    def test_runner_receives_ffprobe_argv_and_timeout(self):
        runner = FakeRunner(probe_run(probe_payload()))
        om.probe_media("in.mp4", runner)
        self.assertEqual(runner.calls, [(om.ffprobe_argv("in.mp4"), om.PROBE_TIMEOUT_SECONDS)])

    def test_no_audio_stream(self):
        runner = FakeRunner(probe_run(probe_payload(has_audio=False)))
        result = om.probe_media("in.mp4", runner)
        self.assertTrue(result["ok"])
        self.assertTrue(result["has_video"])
        self.assertFalse(result["has_audio"])
        self.assertEqual([s["codec_type"] for s in result["streams"]], ["video"])

    def test_empty_stream_list_is_still_a_successful_probe(self):
        runner = FakeRunner(probe_run({"format": {"format_name": "wav", "duration": "1.0"}, "streams": []}))
        result = om.probe_media("in.wav", runner)
        self.assertTrue(result["ok"])
        self.assertFalse(result["has_video"])
        self.assertFalse(result["has_audio"])

    def test_invalid_json(self):
        runner = FakeRunner(probe_run(stdout=b"{not json"))
        result = om.probe_media("in.mp4", runner)
        self.assertFalse(result["ok"])
        self.assertTrue(any("not valid JSON" in problem for problem in result["problems"]))

    def test_non_object_json(self):
        runner = FakeRunner(probe_run(stdout=b"[1, 2]"))
        result = om.probe_media("in.mp4", runner)
        self.assertFalse(result["ok"])
        self.assertTrue(any("JSON object" in problem for problem in result["problems"]))

    def test_invalid_utf8_never_raises(self):
        runner = FakeRunner(probe_run(stdout=b"\xff\xfe{\xff}"))
        result = om.probe_media("in.mp4", runner)
        self.assertFalse(result["ok"])
        self.assertIsInstance(result["problems"], list)

    def test_timeout(self):
        runner = FakeRunner(probe_run(probe_payload(), timed_out=True, stdout=b""))
        result = om.probe_media("in.mp4", runner)
        self.assertFalse(result["ok"])
        self.assertTrue(any("timed out" in problem for problem in result["problems"]))

    def test_nonzero_exit_reports_stderr(self):
        runner = FakeRunner(
            probe_run(exit_code=1, stdout=b"", stderr=b"in.mp4: No such file or directory")
        )
        result = om.probe_media("in.mp4", runner)
        self.assertFalse(result["ok"])
        self.assertTrue(any("exit code 1" in problem for problem in result["problems"]))
        self.assertTrue(any("No such file" in problem for problem in result["problems"]))

    def test_missing_exit_code(self):
        runner = FakeRunner({"stdout_bytes": b"{}", "stderr_bytes": b"", "timed_out": False})
        result = om.probe_media("in.mp4", runner)
        self.assertFalse(result["ok"])
        self.assertTrue(any("exit code" in problem for problem in result["problems"]))

    def test_runner_returning_non_object(self):
        runner = FakeRunner(["not", "a", "dict"])
        result = om.probe_media("in.mp4", runner)
        self.assertFalse(result["ok"])
        self.assertTrue(any("expected an object" in problem for problem in result["problems"]))

    def test_runner_raising_never_propagates(self):
        runner = FakeRunner(RuntimeError("boom"))
        result = om.probe_media("in.mp4", runner)
        self.assertFalse(result["ok"])
        self.assertTrue(any("RuntimeError" in problem for problem in result["problems"]))

    def test_non_callable_runner(self):
        result = om.probe_media("in.mp4", None)
        self.assertFalse(result["ok"])
        self.assertTrue(any("callable" in problem for problem in result["problems"]))

    def test_bad_paths_do_not_call_runner(self):
        runner = FakeRunner(probe_run(probe_payload()))
        for path in ("", "  ", None, 5, "bad\x00name"):
            result = om.probe_media(path, runner)
            self.assertFalse(result["ok"])
        self.assertEqual(runner.calls, [])

    def test_missing_streams_key(self):
        runner = FakeRunner(probe_run({"format": {"format_name": "wav"}}))
        result = om.probe_media("in.wav", runner)
        self.assertFalse(result["ok"])
        self.assertTrue(any("streams" in problem for problem in result["problems"]))

    def test_non_object_stream_entry(self):
        runner = FakeRunner(probe_run({"format": {"format_name": "wav"}, "streams": ["nope"]}))
        result = om.probe_media("in.wav", runner)
        self.assertFalse(result["ok"])
        self.assertTrue(any("stream entry" in problem for problem in result["problems"]))

    def test_missing_format_object(self):
        runner = FakeRunner(probe_run({"streams": []}))
        result = om.probe_media("in.mp4", runner)
        self.assertFalse(result["ok"])
        self.assertTrue(any("format" in problem for problem in result["problems"]))

    def test_duration_falls_back_to_stream_duration(self):
        payload = {
            "format": {"format_name": "mpegts"},
            "streams": [{"index": 0, "codec_type": "video", "codec_name": "h264", "duration": "3.25"}],
        }
        result = om.probe_media("in.ts", FakeRunner(probe_run(payload)))
        self.assertTrue(result["ok"])
        self.assertEqual(result["duration_seconds"], 3.25)

    def test_process_runner_wraps_observation_process(self):
        calls = []

        def fake_run(argv, cwd, timeout, env=None):
            calls.append((argv, cwd, timeout))
            return {
                "exit_code": 0,
                "stdout_bytes": b"{}",
                "stderr_bytes": b"err",
                "timed_out": False,
                "cleanup": {},
            }

        import observation_process

        with mock.patch.object(observation_process, "run_process", fake_run):
            result = om.process_runner(["ffprobe", "in.mp4"], 5)
        self.assertEqual(
            result,
            {"exit_code": 0, "stdout_bytes": b"{}", "stderr_bytes": b"err", "timed_out": False},
        )
        self.assertEqual(calls, [(["ffprobe", "in.mp4"], None, 5)])


class MediaRecordTests(unittest.TestCase):
    def test_each_valid_kind(self):
        records = [
            media_record("native-video"),
            media_record("native-video", time_range={"start": 0, "end": 12.5}),
            media_record(
                "frame-sampled",
                frame_params={"fps": 2, "limit": 12},
                derived_from={"path": "media/input.mp4", "sha256": HASH},
                time_range={"start": 0, "end": 6},
            ),
            media_record(
                "frame-sampled",
                frame_params={"interval": 0.5, "limit": 8},
                derived_from={"path": "media/input.mp4", "sha256": HASH},
            ),
            om.build_media_record(
                "audio-track",
                "media/audio.wav",
                HASH,
                probe_media_result(has_video=False),
                audio_source="extract",
                derived_from={"path": "media/input.mp4", "sha256": HASH},
                commands=["ffmpeg -i in.mp4 -vn -acodec pcm_s16le out.wav"],
                perception_model="qwen3-omni",
                session_id="ses_1",
                created_at="2026-09-21T00:00:00Z",
            ),
            om.build_media_record(
                "audio-transcript",
                "media/transcript.json",
                HASH,
                probe_media_result(has_video=False, has_audio=False),
                derived_from={"path": "media/audio.wav", "sha256": HASH},
                audio_source="extract",
                commands=["whisper audio.wav"],
                perception_model="whisper-large",
            ),
            media_record("audio-caption"),
        ]
        for record in records:
            self.assertEqual(om.validate_media_record(record), [], record["kind"])

    def test_builder_structure(self):
        record = media_record("native-video")
        self.assertEqual(record["schema"], om.MEDIA_RECORD_SCHEMA)
        self.assertEqual(record["kind"], "native-video")
        self.assertEqual(record["source"], {"path": "media/input.mp4", "sha256": HASH})
        self.assertEqual(
            record["media"],
            {
                "probe_ok": True,
                "has_video": True,
                "has_audio": True,
                "duration_seconds": 12.5,
                "format_name": "mov,mp4",
            },
        )
        self.assertIsNone(record["derived_from"])
        self.assertIsNone(record["time_range"])
        self.assertIsNone(record["frame_params"])
        self.assertIsNone(record["audio_source"])
        self.assertEqual(record["commands"], [])
        self.assertIsNone(record["perception_model"])
        self.assertIsNone(record["session_id"])
        self.assertIsNone(record["created_at"])

    def test_builder_refuses_unknown_kind(self):
        with self.assertRaises(ValueError):
            om.build_media_record("gif", "in.gif", HASH, {})
        with self.assertRaises(ValueError):
            om.build_media_record(None, "in.gif", HASH, {})

    def test_builder_failed_probe_keeps_facts_false(self):
        failed = {"ok": False, "problems": ["ffprobe failed"], "streams": []}
        record = om.build_media_record("native-video", "in.mp4", HASH, failed)
        self.assertFalse(record["media"]["probe_ok"])
        self.assertFalse(record["media"]["has_video"])
        self.assertFalse(record["media"]["has_audio"])
        self.assertIsNone(record["media"]["duration_seconds"])
        om_no_probe = om.build_media_record("native-video", "in.mp4", HASH, None)
        self.assertFalse(om_no_probe["media"]["probe_ok"])

    def test_builder_commands_defaults_are_independent_lists(self):
        first = media_record("native-video")
        second = media_record("native-video")
        self.assertIsNot(first["commands"], second["commands"])

    def test_builder_copies_command_list(self):
        commands = ["ffmpeg -i in.mp4 out.wav"]
        record = media_record("audio-track", audio_source="extract", commands=commands)
        commands.append("extra")
        self.assertEqual(record["commands"], ["ffmpeg -i in.mp4 out.wav"])

    def test_frame_sampled_requires_frame_params(self):
        record = media_record("frame-sampled")
        problems = om.validate_media_record(record)
        self.assertTrue(any("frame_params" in problem for problem in problems))
        self.assertTrue(any("continuous coverage" in problem for problem in problems))

    def test_frame_params_requires_rate_and_limit(self):
        record = media_record("frame-sampled", frame_params={"limit": 5})
        problems = om.validate_media_record(record)
        self.assertTrue(any("interval or fps" in problem for problem in problems))

        record = media_record("frame-sampled", frame_params={"fps": 2})
        problems = om.validate_media_record(record)
        self.assertTrue(any("limit" in problem for problem in problems))

        record = media_record("frame-sampled", frame_params={"fps": 2, "interval": 1, "limit": 5})
        problems = om.validate_media_record(record)
        self.assertTrue(any("exactly one" in problem for problem in problems))

        record = media_record("frame-sampled", frame_params={"fps": -1, "limit": 5})
        problems = om.validate_media_record(record)
        self.assertTrue(any("positive" in problem for problem in problems))

    def test_native_video_must_not_claim_audio(self):
        record = media_record("native-video", audio_source="capture")
        problems = om.validate_media_record(record)
        self.assertTrue(any("must not claim audio" in problem for problem in problems))

        record = media_record(
            "frame-sampled", frame_params={"fps": 2, "limit": 4}, audio_source="extract"
        )
        problems = om.validate_media_record(record)
        self.assertTrue(any("must not claim audio" in problem for problem in problems))

    def test_audio_track_requires_audio_source(self):
        record = media_record("audio-track")
        problems = om.validate_media_record(record)
        self.assertTrue(any("audio_source" in problem for problem in problems))

    def test_invalid_audio_source_value(self):
        record = media_record("native-video", audio_source="recorded")
        problems = om.validate_media_record(record)
        self.assertTrue(any("capture, extract, or null" in problem for problem in problems))

    def test_time_range_rules(self):
        record = media_record("native-video", time_range={"start": 5, "end": 1})
        self.assertTrue(any("greater" in p for p in om.validate_media_record(record)))
        record = media_record("native-video", time_range=["0", "1"])
        self.assertTrue(any("time_range" in p for p in om.validate_media_record(record)))
        record = media_record("native-video", time_range={"start": "0", "end": 1})
        self.assertTrue(any("start" in p for p in om.validate_media_record(record)))

    def test_malformed_records_never_raise(self):
        malformed = [
            None,
            "media",
            5,
            [],
            {},
            {"schema": om.MEDIA_RECORD_SCHEMA},
            {"schema": 7, "kind": ["native-video"], "source": "x", "media": []},
            {
                "schema": om.MEDIA_RECORD_SCHEMA,
                "kind": "native-video",
                "source": {"path": None, "sha256": "zz"},
                "media": {"probe_ok": "yes", "has_video": 1, "has_audio": None},
                "derived_from": [],
                "time_range": "0-1",
                "frame_params": "fps=2",
                "audio_source": 5,
                "commands": "run",
                "perception_model": 7,
                "session_id": [],
                "created_at": {},
            },
        ]
        for record in malformed:
            problems = om.validate_media_record(record)
            self.assertIsInstance(problems, list)
            self.assertTrue(problems)

    def test_malformed_sha_and_command_entries(self):
        record = media_record("native-video")
        record["source"]["sha256"] = "not-a-hash"
        record["commands"] = ["ok", 5, ""]
        problems = om.validate_media_record(record)
        self.assertTrue(any("source.sha256" in problem for problem in problems))
        self.assertTrue(any("commands[1]" in problem for problem in problems))
        self.assertTrue(any("commands[2]" in problem for problem in problems))


class CaptureChainVerdictTests(unittest.TestCase):
    def test_missing_control_is_never_a_silence_verdict(self):
        for product in (probe_with("silent"), probe_with("present"), None):
            result = om.capture_chain_verdict(None, product)
            self.assertEqual(result["verdict"], "capture-unverified")
            self.assertTrue(result["reason"])

    def test_silent_control_never_blames_product(self):
        for product in (probe_with("silent"), probe_with("present")):
            result = om.capture_chain_verdict(probe_with("silent"), product)
            self.assertEqual(result["verdict"], "capture-unverified")

    def test_unknown_control_never_blames_product(self):
        result = om.capture_chain_verdict(probe_with("unknown"), probe_with("silent"))
        self.assertEqual(result["verdict"], "capture-unverified")

    def test_failed_control_probe_is_unverified(self):
        result = om.capture_chain_verdict(probe_with("present", ok=False), probe_with("silent"))
        self.assertEqual(result["verdict"], "capture-unverified")

    def test_control_present_product_silent(self):
        result = om.capture_chain_verdict(probe_with("present"), probe_with("silent"))
        self.assertEqual(result["verdict"], "product-silent")
        self.assertEqual(result["control_signal"], "present")
        self.assertEqual(result["product_signal"], "silent")

    def test_control_present_product_present(self):
        result = om.capture_chain_verdict(probe_with("present"), probe_with("present"))
        self.assertEqual(result["verdict"], "sound-present")

    def test_control_present_product_unknown(self):
        result = om.capture_chain_verdict(probe_with("present"), probe_with("unknown"))
        self.assertEqual(result["verdict"], "capture-unverified")

    def test_control_present_product_missing(self):
        result = om.capture_chain_verdict(probe_with("present"), None)
        self.assertEqual(result["verdict"], "capture-unverified")

    def test_failed_product_probe_is_unverified(self):
        result = om.capture_chain_verdict(probe_with("present"), probe_with("silent", ok=False))
        self.assertEqual(result["verdict"], "capture-unverified")

    def test_matrix(self):
        expected = {
            (None, "silent"): "capture-unverified",
            (None, "present"): "capture-unverified",
            ("silent", "silent"): "capture-unverified",
            ("silent", "present"): "capture-unverified",
            ("unknown", "silent"): "capture-unverified",
            ("unknown", "present"): "capture-unverified",
            ("present", "silent"): "product-silent",
            ("present", "present"): "sound-present",
            ("present", "unknown"): "capture-unverified",
            ("present", None): "capture-unverified",
        }
        for (control_signal, product_signal), verdict in expected.items():
            control = None if control_signal is None else probe_with(control_signal)
            product = None if product_signal is None else probe_with(product_signal)
            result = om.capture_chain_verdict(control, product)
            self.assertEqual(result["verdict"], verdict, (control_signal, product_signal))

    def test_malformed_inputs_never_raise(self):
        for control, product in (("present", "silent"), (7, []), ([], {}), ({}, "silent")):
            result = om.capture_chain_verdict(control, product)
            self.assertEqual(result["verdict"], "capture-unverified")


class SilenceClaimTests(unittest.TestCase):
    def test_empty_transcript_is_not_silence_evidence(self):
        record = om.build_media_record(
            "audio-transcript",
            "media/transcript.json",
            HASH,
            probe_media_result(has_video=False),
            derived_from={"path": "media/audio.wav", "sha256": HASH},
            audio_source="extract",
            commands=["whisper audio.wav"],
            perception_model="whisper-large",
        )
        record["text"] = ""
        problems = om.silence_claim_problems(record)
        self.assertTrue(any("transcript" in problem for problem in problems))
        self.assertTrue(any("not absence of sound" in problem for problem in problems))

    def test_audio_stream_existing_is_not_silence_evidence(self):
        record = media_record("native-video")
        self.assertTrue(record["media"]["has_audio"])
        self.assertEqual(om.validate_media_record(record), [])
        problems = om.silence_claim_problems(record)
        self.assertTrue(any("audio-track" in problem for problem in problems))

    def test_audio_track_needs_capture_chain(self):
        record = om.build_media_record(
            "audio-track",
            "media/audio.wav",
            HASH,
            probe_media_result(has_video=False),
            audio_source="capture",
            commands=["ffmpeg ... volumedetect"],
            perception_model="qwen3-omni",
        )
        problems = om.silence_claim_problems(record)
        self.assertTrue(any("capture_chain" in problem for problem in problems))

    def test_audio_track_needs_commands_and_model(self):
        record = om.build_media_record(
            "audio-track",
            "media/audio.wav",
            HASH,
            probe_media_result(has_video=False),
            audio_source="capture",
        )
        record["capture_chain"] = {
            "verdict": "product-silent",
            "evidence_ref": "evidence/chain.json",
        }
        problems = om.silence_claim_problems(record)
        self.assertTrue(any("commands" in problem for problem in problems))
        self.assertTrue(any("perception_model" in problem for problem in problems))

    def test_capture_chain_must_be_product_silent(self):
        record = legal_audio_track()
        record["capture_chain"]["verdict"] = "sound-present"
        problems = om.silence_claim_problems(record)
        self.assertTrue(any("product-silent" in problem for problem in problems))

        record = legal_audio_track()
        record["capture_chain"]["evidence_ref"] = ""
        problems = om.silence_claim_problems(record)
        self.assertTrue(any("evidence_ref" in problem for problem in problems))

    def test_legal_chain_passes(self):
        record = legal_audio_track()
        self.assertEqual(om.validate_media_record(record), [])
        self.assertEqual(om.silence_claim_problems(record), [])

    def test_non_silent_claim_is_rejected(self):
        record = legal_audio_track()
        problems = om.silence_claim_problems(record, claim="present")
        self.assertTrue(any("'silent'" in problem for problem in problems))

    def test_malformed_records_return_structural_problems(self):
        self.assertEqual(
            om.silence_claim_problems(None), ["media record must be a JSON object"]
        )
        problems = om.silence_claim_problems({"schema": "media-record/1"})
        self.assertTrue(problems)
        self.assertIsInstance(problems, list)


class MediaEndpointTests(unittest.TestCase):
    def test_all_present_hides_api_key(self):
        env = {
            "MEDIA_MODEL_BASE_URL": "https://example.invalid/v1",
            "MEDIA_MODEL_API_KEY": "super-secret-key",
            "MEDIA_MODEL_NAME": "qwen3-omni",
        }
        result = om.media_endpoint(env)
        self.assertEqual(
            result,
            {
                "available": True,
                "base_url": "https://example.invalid/v1",
                "model": "qwen3-omni",
            },
        )
        self.assertNotIn("api_key", result)
        self.assertNotIn("super-secret-key", json.dumps(result))

    def test_missing_key_lists_only_that_key(self):
        env = {
            "MEDIA_MODEL_BASE_URL": "https://example.invalid/v1",
            "MEDIA_MODEL_NAME": "qwen3-omni",
        }
        self.assertEqual(
            om.media_endpoint(env),
            {"available": False, "missing": ["MEDIA_MODEL_API_KEY"]},
        )

    def test_blank_values_count_as_missing(self):
        env = {name: "   " for name in om.MEDIA_MODEL_ENV}
        self.assertEqual(
            om.media_endpoint(env),
            {"available": False, "missing": list(om.MEDIA_MODEL_ENV)},
        )

    def test_none_or_non_mapping_env(self):
        for env in (None, ["MEDIA_MODEL_NAME"], "MEDIA_MODEL_NAME"):
            self.assertEqual(
                om.media_endpoint(env),
                {"available": False, "missing": list(om.MEDIA_MODEL_ENV)},
            )

    def test_partial_missing_lists_all_absent(self):
        result = om.media_endpoint({"MEDIA_MODEL_NAME": "qwen3-omni"})
        self.assertEqual(
            result["missing"],
            ["MEDIA_MODEL_BASE_URL", "MEDIA_MODEL_API_KEY"],
        )

    def test_no_key_configured_is_not_an_error(self):
        result = om.media_endpoint({})
        self.assertFalse(result["available"])


if __name__ == "__main__":
    unittest.main()

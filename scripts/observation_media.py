#!/usr/bin/env python3
"""S17 offline media surface: ffmpeg/ffprobe argv, probe parsing, media records.

FFmpeg/ffprobe are the capture and processing tools. Probing, audio
extraction, frame sampling and clipping happen only through explicit argv
arrays (``ffprobe_argv``, ``extract_audio_argv``, ``extract_frames_argv``,
``clip_argv``) executed by an injected runner, so every test here stays
offline; the production runner wraps ``observation_process.run_process``
(``process_runner``).

This module decides nothing about what was recorded. Semantic judgement --
"the product was silent", "the transcript says X" -- belongs to a perception
model that the host actually supports (see ``media_endpoint`` and
``MEDIA_MODEL_ENV``); nothing here installs a model, opens a network
connection or buys a subscription. A ``record start/stop`` product is raw
material: a video file existing, or even exposing an audio stream, proves
neither that the capture chain worked nor that the product produced sound.
Silence claims must cite an ``audio-track`` record plus a
``capture_chain_verdict`` of ``product-silent``; an empty ASR transcript is
never evidence of silence.
"""

import json
import math
import os
import re
from typing import Any, Callable, Mapping, Optional

MEDIA_RECORD_SCHEMA = "media-record/1"
MEDIA_KINDS = (
    "native-video",
    "frame-sampled",
    "audio-track",
    "audio-transcript",
    "audio-caption",
)
AUDIO_KINDS = ("audio-track", "audio-transcript", "audio-caption")
AUDIO_SOURCES = ("capture", "extract")
SIGNALS = ("present", "silent", "unknown")
CAPTURE_VERDICTS = ("sound-present", "product-silent", "capture-unverified")
MEDIA_MODEL_ENV = ("MEDIA_MODEL_BASE_URL", "MEDIA_MODEL_API_KEY", "MEDIA_MODEL_NAME")
PROBE_TIMEOUT_SECONDS = 30.0

_HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + " must be a non-empty string")
    if "\x00" in value:
        raise ValueError(label + " must not contain NUL")
    return value


def _number_text(number: float) -> str:
    if number == int(number):
        return str(int(number))
    return repr(float(number))


def _positive_number_text(value: Any, label: str) -> str:
    if isinstance(value, bool) or value is None:
        raise ValueError(label + " must be a positive number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(label + " must be a positive number")
    if not math.isfinite(number) or number <= 0:
        raise ValueError(label + " must be a positive number")
    return _number_text(number)


def _time_text(value: Any, label: str) -> str:
    if isinstance(value, bool) or value is None:
        raise ValueError(label + " must be a non-negative number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(label + " must be a non-negative number")
    if not math.isfinite(number) or number < 0:
        raise ValueError(label + " must be a non-negative number")
    return _number_text(number)


def ffprobe_argv(path: Any) -> list:
    """Probe ``path``: JSON on stdout with format and stream facts."""
    return [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        _require_text(path, "path"),
    ]


def extract_audio_argv(video: Any, out: Any) -> list:
    """Extract a 16-bit PCM WAV track from ``video``."""
    return [
        "ffmpeg",
        "-y",
        "-i",
        _require_text(video, "video"),
        "-vn",
        "-acodec",
        "pcm_s16le",
        _require_text(out, "out"),
    ]


def extract_frames_argv(video: Any, out_pattern: Any, interval: Any = None, fps: Any = None) -> list:
    """Sample frames with ffmpeg's ``fps`` filter.

    Exactly one of ``interval`` (seconds between frames) or ``fps`` (frames
    per second) must be given. Sampled frames are discrete stills, never
    continuous coverage.
    """
    video_text = _require_text(video, "video")
    pattern_text = _require_text(out_pattern, "out_pattern")
    if (interval is None) == (fps is None):
        raise ValueError("exactly one of interval or fps must be given")
    if fps is not None:
        filter_text = "fps=" + _positive_number_text(fps, "fps")
    else:
        filter_text = "fps=1/" + _positive_number_text(interval, "interval")
    return ["ffmpeg", "-y", "-i", video_text, "-vf", filter_text, pattern_text]


def clip_argv(video: Any, start: Any, end: Any, out: Any) -> list:
    """Clip ``video`` between ``start`` and ``end`` seconds without re-encoding."""
    video_text = _require_text(video, "video")
    out_text = _require_text(out, "out")
    start_text = _time_text(start, "start")
    end_text = _time_text(end, "end")
    if float(end_text) <= float(start_text):
        raise ValueError("end must be greater than start")
    return [
        "ffmpeg",
        "-y",
        "-ss",
        start_text,
        "-to",
        end_text,
        "-i",
        video_text,
        "-c",
        "copy",
        out_text,
    ]


def process_runner(argv: list, timeout: float) -> dict:
    """Production runner: wrap ``observation_process.run_process``.

    Returns exactly the shape ``probe_media`` consumes. The import is local so
    this module keeps working (and testing) without a host process boundary.
    """
    import observation_process

    run = observation_process.run_process(list(argv), None, timeout)
    return {
        "exit_code": run.get("exit_code"),
        "stdout_bytes": run.get("stdout_bytes", b""),
        "stderr_bytes": run.get("stderr_bytes", b""),
        "timed_out": bool(run.get("timed_out")),
    }


def _decode(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw).decode("utf-8", errors="replace")
    return ""


def _parse_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer():
            return int(value)
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            pass
        try:
            number = float(text)
        except ValueError:
            return None
        if math.isfinite(number) and number.is_integer():
            return int(number)
    return None


def _parse_float(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(number):
        return None
    return number


def _probe_failure(problems: list) -> dict:
    return {
        "ok": False,
        "has_video": False,
        "has_audio": False,
        "duration_seconds": None,
        "format_name": None,
        "streams": [],
        "problems": list(problems),
    }


def probe_media(path: Any, runner: Callable[[list, float], dict]) -> dict:
    """Run ffprobe through ``runner`` and parse its JSON into a probe result.

    ``runner(argv, timeout)`` is injected (tests use fakes; production passes
    :func:`process_runner`) and must return
    ``{"exit_code", "stdout_bytes", "stderr_bytes", "timed_out"}``. Any
    failure -- unusable path, missing/raised runner, timeout, non-zero exit,
    non-JSON stdout, malformed streams -- returns ``ok=False`` with
    ``problems`` and never raises.
    """
    if not isinstance(path, str) or not path.strip() or "\x00" in path:
        return _probe_failure(["path must be a non-empty string"])
    if not callable(runner):
        return _probe_failure(["runner must be callable"])
    argv = ffprobe_argv(path)
    try:
        run = runner(argv, PROBE_TIMEOUT_SECONDS)
    except Exception as exc:  # boundary guarantee: never raise
        return _probe_failure(["ffprobe runner raised " + type(exc).__name__ + ": " + str(exc)])
    if not isinstance(run, dict):
        return _probe_failure(
            ["ffprobe runner returned " + type(run).__name__ + ", expected an object"]
        )
    if run.get("timed_out") is True:
        return _probe_failure(["ffprobe timed out"])
    exit_code = run.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        return _probe_failure(["ffprobe did not report an exit code"])
    if exit_code != 0:
        stderr_text = _decode(run.get("stderr_bytes")).strip()
        message = "ffprobe failed with exit code " + str(exit_code)
        if stderr_text:
            message += ": " + stderr_text
        return _probe_failure([message])

    try:
        payload = json.loads(_decode(run.get("stdout_bytes")))
    except ValueError as exc:
        return _probe_failure(["ffprobe output is not valid JSON: " + str(exc)])
    if not isinstance(payload, dict):
        return _probe_failure(["ffprobe output must be a JSON object"])

    problems = []
    streams_out = []
    has_video = False
    has_audio = False
    stream_durations = []
    raw_streams = payload.get("streams")
    if not isinstance(raw_streams, list):
        problems.append("ffprobe output has no streams list")
        raw_streams = []
    for raw in raw_streams:
        if not isinstance(raw, dict):
            problems.append("ffprobe stream entry is not an object")
            continue
        codec_type = raw.get("codec_type")
        if not isinstance(codec_type, str):
            codec_type = ""
        if codec_type == "video":
            has_video = True
        elif codec_type == "audio":
            has_audio = True
        index = raw.get("index")
        if isinstance(index, bool) or not isinstance(index, int):
            index = None
        codec_name = raw.get("codec_name")
        if not isinstance(codec_name, str):
            codec_name = ""
        entry = {"index": index, "codec_type": codec_type, "codec_name": codec_name}
        sample_rate = _parse_int(raw.get("sample_rate"))
        if sample_rate is not None:
            entry["sample_rate"] = sample_rate
        channels = _parse_int(raw.get("channels"))
        if channels is not None:
            entry["channels"] = channels
        stream_durations.append(_parse_float(raw.get("duration")))
        streams_out.append(entry)

    format_name = None
    duration_seconds = None
    raw_format = payload.get("format")
    if not isinstance(raw_format, dict):
        problems.append("ffprobe output has no format object")
    else:
        raw_name = raw_format.get("format_name")
        if isinstance(raw_name, str) and raw_name.strip():
            format_name = raw_name
        duration_seconds = _parse_float(raw_format.get("duration"))
    if duration_seconds is None:
        known = [value for value in stream_durations if value is not None]
        if known:
            duration_seconds = max(known)

    return {
        "ok": not problems,
        "has_video": has_video,
        "has_audio": has_audio,
        "duration_seconds": duration_seconds,
        "format_name": format_name,
        "streams": streams_out,
        "problems": problems,
    }


def _plain(value: Any) -> Any:
    if isinstance(value, os.PathLike):
        try:
            return os.fsdecode(os.fspath(value))
        except (TypeError, ValueError):
            return value
    return value


def build_media_record(
    kind: Any,
    source_path: Any,
    sha256: Any,
    ffprobe_result: Any,
    *,
    derived_from: Any = None,
    time_range: Any = None,
    frame_params: Any = None,
    audio_source: Any = None,
    commands: Any = None,
    perception_model: Any = None,
    session_id: Any = None,
    created_at: Any = None,
) -> dict:
    """Assemble a ``media-record/1`` claim from probe facts and caller input.

    The builder only refuses an unknown ``kind``; everything else is copied
    (or passed through) so :func:`validate_media_record` can report malformed
    fields instead of the builder guessing. ``media`` records what the probe
    saw, never more: a failed probe means ``probe_ok=False`` and no audio/video
    facts. Fields left as ``None`` stay ``None``.
    """
    if not isinstance(kind, str) or kind not in MEDIA_KINDS:
        raise ValueError("unsupported media kind: " + repr(kind))
    probe = ffprobe_result if isinstance(ffprobe_result, dict) else {}
    if isinstance(derived_from, dict):
        derived = {"path": _plain(derived_from.get("path")), "sha256": _plain(derived_from.get("sha256"))}
    else:
        derived = derived_from
    if isinstance(time_range, dict):
        time = {"start": time_range.get("start"), "end": time_range.get("end")}
    else:
        time = time_range
    if isinstance(frame_params, dict):
        frames = dict(frame_params)
    else:
        frames = frame_params
    if commands is None:
        command_list = []
    elif isinstance(commands, (list, tuple)):
        command_list = list(commands)
    else:
        command_list = commands
    return {
        "schema": MEDIA_RECORD_SCHEMA,
        "kind": kind,
        "source": {"path": _plain(source_path), "sha256": _plain(sha256)},
        "media": {
            "probe_ok": probe.get("ok") is True,
            "has_video": probe.get("has_video") is True,
            "has_audio": probe.get("has_audio") is True,
            "duration_seconds": _parse_float(probe.get("duration_seconds")),
            "format_name": (
                probe.get("format_name")
                if isinstance(probe.get("format_name"), str) and probe["format_name"].strip()
                else None
            ),
        },
        "derived_from": derived,
        "time_range": time,
        "frame_params": frames,
        "audio_source": audio_source,
        "commands": command_list,
        "perception_model": perception_model,
        "session_id": session_id,
        "created_at": created_at,
    }


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def _is_positive(value: Any) -> bool:
    return _is_number(value) and float(value) > 0


def _hash_problem(value: Any, label: str) -> Optional[str]:
    if not isinstance(value, str) or not _HASH_RE.match(value):
        return label + " must be a 64-character hex digest"
    return None


def _time_range_problems(value: Any) -> list:
    if value is None:
        return []
    if not isinstance(value, dict):
        return ["time_range must be an object or null"]
    problems = []
    start_ok = _is_number(value.get("start"))
    end_ok = _is_number(value.get("end"))
    if not start_ok:
        problems.append("time_range.start must be a number")
    if not end_ok:
        problems.append("time_range.end must be a number")
    if start_ok and end_ok and float(value["end"]) <= float(value["start"]):
        problems.append("time_range.end must be greater than time_range.start")
    return problems


def _frame_params_problems(value: Any) -> list:
    if value is None:
        return []
    if not isinstance(value, dict):
        return ["frame_params must be an object or null"]
    problems = []
    has_interval = value.get("interval") is not None
    has_fps = value.get("fps") is not None
    if has_interval == has_fps:
        problems.append("frame_params must set exactly one of interval or fps")
    for key in ("interval", "fps"):
        if value.get(key) is not None and not _is_positive(value.get(key)):
            problems.append("frame_params." + key + " must be a positive number")
    limit = value.get("limit")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        problems.append("frame_params.limit must be a positive integer")
    return problems


def validate_media_record(record: Any) -> list:
    """Return structural problems for a media record (never raises).

    Checks only completeness and type safety. Cross-record honesty lives in
    :func:`silence_claim_problems`: in particular a ``frame-sampled`` record
    must carry ``frame_params`` (interval or fps plus limit) because sampled
    stills are not continuous coverage, and ``native-video``/``frame-sampled``
    must not claim audio evidence.
    """
    problems = []
    if not isinstance(record, dict):
        return ["media record must be a JSON object"]
    if record.get("schema") != MEDIA_RECORD_SCHEMA:
        problems.append("schema must be " + MEDIA_RECORD_SCHEMA)
    kind = record.get("kind")
    if kind not in MEDIA_KINDS:
        problems.append("kind must be one of: " + ", ".join(MEDIA_KINDS))

    source = record.get("source")
    if not isinstance(source, dict):
        problems.append("source must be an object with path and sha256")
    else:
        if not _nonempty(source.get("path")):
            problems.append("source.path must be a non-empty string")
        sha_problem = _hash_problem(source.get("sha256"), "source.sha256")
        if sha_problem:
            problems.append(sha_problem)

    media = record.get("media")
    if not isinstance(media, dict):
        problems.append("media must be an object with probe facts")
    else:
        for flag in ("probe_ok", "has_video", "has_audio"):
            if not isinstance(media.get(flag), bool):
                problems.append("media." + flag + " must be a boolean")
        if media.get("duration_seconds") is not None and not _is_number(media.get("duration_seconds")):
            problems.append("media.duration_seconds must be a number or null")
        if media.get("format_name") is not None and not _nonempty(media.get("format_name")):
            problems.append("media.format_name must be a non-empty string or null")

    derived = record.get("derived_from")
    if derived is not None:
        if not isinstance(derived, dict):
            problems.append("derived_from must be an object or null")
        else:
            if not _nonempty(derived.get("path")):
                problems.append("derived_from.path must be a non-empty string")
            sha_problem = _hash_problem(derived.get("sha256"), "derived_from.sha256")
            if sha_problem:
                problems.append(sha_problem)

    problems.extend(_time_range_problems(record.get("time_range")))
    problems.extend(_frame_params_problems(record.get("frame_params")))

    audio_source = record.get("audio_source")
    if audio_source is not None and audio_source not in AUDIO_SOURCES:
        problems.append("audio_source must be capture, extract, or null")
    if kind == "audio-track" and audio_source not in AUDIO_SOURCES:
        problems.append("audio-track requires audio_source to be capture or extract")
    if kind in ("native-video", "frame-sampled") and audio_source is not None:
        problems.append(kind + " must not claim audio evidence (audio_source must be null)")

    commands = record.get("commands")
    if not isinstance(commands, list):
        problems.append("commands must be a list of non-empty strings")
    else:
        for position, command in enumerate(commands):
            if not _nonempty(command):
                problems.append("commands[" + str(position) + "] must be a non-empty string")

    for field in ("perception_model", "session_id", "created_at"):
        value = record.get(field)
        if value is not None and not _nonempty(value):
            problems.append(field + " must be a non-empty string or null")

    if kind == "frame-sampled" and not isinstance(record.get("frame_params"), dict):
        problems.append(
            "frame-sampled requires frame_params with interval or fps and limit; "
            "sampled frames are not continuous coverage"
        )
    return problems


def _usable_probe(probe: Any) -> bool:
    return (
        isinstance(probe, dict)
        and isinstance(probe.get("probe_media"), dict)
        and probe["probe_media"].get("ok") is True
        and probe.get("signal") in SIGNALS
    )


def capture_chain_verdict(control_probe: Any, product_probe: Any) -> dict:
    """Judge a silence claim from a verified control and the product probe.

    ``control_probe``/``product_probe`` are
    ``{"probe_media": <probe_media result>, "signal": "present"|"silent"|"unknown"}``
    where the signal comes from the caller (volumedetect etc.). Fail closed:
    without a usable control probe whose signal is ``present`` the verdict is
    always ``capture-unverified``, and a product ``silent`` signal only becomes
    ``product-silent`` when its own probe succeeded. Nothing here inspects the
    probes themselves beyond validity.
    """
    if not _usable_probe(control_probe) or control_probe.get("signal") != "present":
        signal = control_probe.get("signal") if isinstance(control_probe, dict) else None
        if not isinstance(control_probe, dict):
            reason = "control probe is missing; a silence claim cannot be verified without it"
        elif not isinstance(control_probe.get("probe_media"), dict) or control_probe["probe_media"].get("ok") is not True:
            reason = "control probe did not succeed; the capture chain is unverified"
        elif signal == "silent":
            reason = "control probe is silent; the capture chain cannot be trusted"
        elif signal == "unknown":
            reason = "control probe signal is unknown; the capture chain is unverified"
        else:
            reason = "control probe signal is " + repr(signal) + "; the capture chain is unverified"
        return {
            "verdict": "capture-unverified",
            "reason": reason,
            "control_signal": signal,
            "product_signal": product_probe.get("signal") if isinstance(product_probe, dict) else None,
        }

    product_signal = product_probe.get("signal") if isinstance(product_probe, dict) else None
    if product_signal == "silent":
        if _usable_probe(product_probe):
            return {
                "verdict": "product-silent",
                "reason": "control probe is present and the product probe is silent",
                "control_signal": "present",
                "product_signal": "silent",
            }
        return {
            "verdict": "capture-unverified",
            "reason": "product probe did not succeed; silence is unverified",
            "control_signal": "present",
            "product_signal": "silent",
        }
    if product_signal == "present":
        if _usable_probe(product_probe):
            return {
                "verdict": "sound-present",
                "reason": "control probe is present and the product probe carries signal",
                "control_signal": "present",
                "product_signal": "present",
            }
        return {
            "verdict": "capture-unverified",
            "reason": "product probe did not succeed; sound presence is unverified",
            "control_signal": "present",
            "product_signal": "present",
        }
    return {
        "verdict": "capture-unverified",
        "reason": "product signal is " + repr(product_signal) + "; silence is unverified",
        "control_signal": "present",
        "product_signal": product_signal,
    }


def silence_claim_problems(record: Any, claim: Any = "silent") -> list:
    """Check whether a media record may support a silence claim.

    An ``audio-transcript`` record never does, empty text or not: ASR
    emptiness is not absence of sound. Neither does a file merely existing or
    exposing an audio stream. The only accepted basis is an ``audio-track``
    record carrying the capture commands, the perception model that judged the
    probes, and a ``capture_chain`` reference whose verdict is
    ``product-silent``. Malformed records return their structural problems.
    """
    structural = validate_media_record(record)
    if structural:
        return structural
    if claim != "silent":
        return ["silence_claim_problems only supports the 'silent' claim, got " + repr(claim)]

    kind = record["kind"]
    problems = []
    if kind == "audio-transcript":
        text = record.get("text")
        if isinstance(text, str) and text.strip():
            problems.append("audio-transcript contains text and cannot support a silent claim")
        else:
            problems.append(
                "audio-transcript does not establish silence: empty ASR text is not absence of sound"
            )
    if kind != "audio-track":
        problems.append(
            "silence requires an audio-track record with a product-silent capture-chain verdict; "
            "kind is " + repr(kind)
        )
        return problems

    if not record.get("commands"):
        problems.append("audio-track silence evidence needs the capture commands recorded")
    if not _nonempty(record.get("perception_model")):
        problems.append("audio-track silence evidence needs the perception_model that judged the probes")
    chain = record.get("capture_chain")
    if not isinstance(chain, dict):
        problems.append("audio-track silence evidence needs a capture_chain verdict reference")
        return problems
    if chain.get("verdict") != "product-silent":
        problems.append(
            "capture_chain.verdict must be product-silent, got " + repr(chain.get("verdict"))
        )
    if not _nonempty(chain.get("evidence_ref")):
        problems.append("capture_chain.evidence_ref must be a non-empty evidence reference")
    return problems


def media_endpoint(env: Any = None) -> dict:
    """Describe the optional external media model, if the environment has one.

    ``MEDIA_MODEL_BASE_URL`` / ``MEDIA_MODEL_API_KEY`` / ``MEDIA_MODEL_NAME``
    must all be non-empty. The API key is consumed for availability only and
    is never echoed; when anything is missing the result lists exactly what is
    missing. This function performs no installation, no download and no
    network call -- Qwen3-Omni or any other model is only a candidate.
    """
    env_map: Mapping = env if isinstance(env, dict) else {}
    present = {}
    missing = []
    for name in MEDIA_MODEL_ENV:
        value = env_map.get(name)
        if isinstance(value, str) and value.strip():
            present[name] = value
        else:
            missing.append(name)
    if missing:
        return {"available": False, "missing": missing}
    return {
        "available": True,
        "base_url": present["MEDIA_MODEL_BASE_URL"],
        "model": present["MEDIA_MODEL_NAME"],
    }

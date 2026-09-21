#!/usr/bin/env python3
"""S21 calibration runner for CLI observation cases (A/B term fixtures).

Executes the README §3 flow with real nested `opencode run` dispatches:

  1. copy fixture -> <project>/app
  2. write goal card + runtime-state policy (when the fixture writes state)
  3. freeze candidate manifest + product-audit sidecar
  4. build+validate the phase packet (engine CLI)
  5. dispatch the primary-mirror observer via `opencode run`
  6. single-channel adoption (observation_results) + sidecar update
  7. repeat for compare, then dispatch the reviewer mirror
  8. export native trace and run `check.py product-audit-gate`

Raw stdout/stderr and metrics are archived under runs/<case>/<cid>/.
Never writes to the original sandbox; only the target project and runs/.
"""

from __future__ import annotations

import argparse
import atexit
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(REPO / "validation" / "observation-calibration"))
sys.path.insert(0, str(SCRIPTS))

import driver_core as dc  # noqa: E402
import observation_contract as ocontract  # noqa: E402
import observation_process as op  # noqa: E402
import observation_results as ores  # noqa: E402

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
SANDBOX_APPS = Path(r"E:\MISC\代码项目\po-validation-sandbox\apps")

CASES = {
    "A-term": {
        "goal": "A user can play the Duel Blocks demo end to end",
        "demo": "Run `python app/app.py --mode a` and `--mode b`",
        "smoke": ["--smoke"],
        "state_paths": [],
        "channels": ["audio"],
        "entry": "python app/app.py",
    },
    "B-term": {
        "goal": "A user can save a note and read it back end to end",
        "demo": "Run `python app/app.py save hello` then `python app/app.py show`",
        "smoke": ["--smoke"],
        "state_paths": ["app/note.txt"],
        "entry": "python app/app.py",
    },
    "C-term": {
        "goal": "A user can browse every documented portal section through the menu",
        "demo": "Run `python app/app.py menu` then `python app/app.py open <section>`",
        "smoke": ["--smoke"],
        "state_paths": [],
        "entry": "python app/app.py",
    },
    "D-term": {
        "goal": "A user can set a theme and see it applied when viewing the notes page",
        "demo": "Run `python app/app.py set-theme dark` then `python app/app.py view`",
        "smoke": ["--smoke"],
        "state_paths": ["app/theme.cfg"],
        "entry": "python app/app.py",
    },
    "E-term": {
        "goal": "A user can add a task and see it in the list afterwards",
        "demo": "Run `python app/app.py list` then `python app/app.py add buy milk` then `list`",
        "smoke": ["--smoke"],
        "state_paths": [],
        "entry": "python app/app.py",
    },
    "F-term": {
        "goal": "A user can save a note and read it back reliably on every attempt",
        "demo": "Run `python app/app.py save hello` then `python app/app.py show` repeatedly",
        "smoke": ["--smoke"],
        "state_paths": ["app/note.txt", "app/.tries"],
        "entry": "python app/app.py",
    },
    "B-web": {
        "goal": "A user can write a note and save it from the Notes page",
        "demo": "Open http://127.0.0.1:8907/ in a browser, edit the note, click Save",
        "smoke": [],
        "smoke_cmd": None,
        "state_paths": [],
        "entry": "http://127.0.0.1:8907/",
        "web": True,
        "port": 8907,
        "backend": "agent-browser",
        "channels": ["visual", "console"],
    },
}

DISPATCH_TIMEOUT = 1500


def now_ms() -> int:
    return int(time.time() * 1000)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def jdump(value, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def jload(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def find_db() -> Path | None:
    for candidate in (
        Path.home() / "AppData" / "Local" / "opencode" / "opencode.db",
        Path.home() / ".local" / "share" / "opencode" / "opencode.db",
    ):
        if candidate.is_file():
            return candidate
    return None


def find_dispatch_session(project: Path, agent: str, since_ms: int) -> str | None:
    db = find_db()
    if db is None:
        return None
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        target = str(project).replace("\\", "/").lower()
        rows = con.execute(
            "select id, agent, directory, time_created from session "
            "where time_created >= ? order by time_created desc limit 60",
            (since_ms - 5000,),
        ).fetchall()
        for row in rows:
            directory = (row["directory"] or "").replace("\\", "/").lower()
            if directory == target and row["agent"] == agent:
                return row["id"]
    finally:
        con.close()
    return None


def export_trace(project: Path) -> tuple[dict | None, str]:
    out = project / ".opencode" / "mvp" / "trace.json"
    engine = project / ".opencode" / "workflow" / "scripts" / "runtime_trace.py"
    result = op.run_process(
        [sys.executable, str(engine), "export", str(project), "--out", str(out)],
        cwd=project, timeout=120,
    )
    if result["exit_code"] != 0:
        return None, op.text_of(result["stderr_bytes"])
    try:
        return jload(out), ""
    except (OSError, ValueError) as exc:
        return None, str(exc)


def run_open(build, args, cwd, timeout):
    return build.returncode, build.stdout, build.stderr


def opencode_executable() -> str:
    """Resolve the real executable; never rely on shell shims."""
    direct = (Path.home() / "AppData" / "Roaming" / "npm" / "node_modules"
              / "opencode-ai" / "bin" / "opencode.exe")
    if direct.is_file():
        return str(direct)
    found = shutil.which("opencode")
    if found:
        return found
    raise RuntimeError("opencode executable not found")


def dispatch(project: Path, agent: str, model: str, prompt: str, timeout: int, raw_path: Path) -> dict:
    env = dict(os.environ, OPENCODE_DISABLE_AUTOUPDATE="1")
    argv = [opencode_executable(), "run", "--auto", "--model", model, "--agent", agent,
            "--format", "default", prompt]
    result = op.run_process(argv, cwd=project, timeout=timeout, env=env)
    text = op.text_of(result["stdout_bytes"])
    err = op.text_of(result["stderr_bytes"])
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(text + "\n--stderr--\n" + err, encoding="utf-8")
    return {
        "exit_code": result["exit_code"],
        "timed_out": result["timed_out"],
        "elapsed": result["elapsed_seconds"],
        "text": strip_ansi(text),
        "stderr": err,
    }


def make_goal(case: str, cfg: dict) -> dict:
    if cfg.get("web"):
        command = f'"{sys.executable}" -c "print(\'SMOKE-OK\')"'
    else:
        smoke = " ".join(cfg["smoke"])
        command = f'"{sys.executable}" app/app.py {smoke}'
    return {
        "schema_version": 2,
        "id": "G-OBS",
        "status": "active",
        "source": {"type": "direct", "raw_request": cfg["goal"]},
        "goal": cfg["goal"],
        "rigor": "normal",
        "risk": {"factors": ["none"], "rationale": "Local calibration fixture"},
        "first_slice": "CLI entry",
        "demo": cfg["demo"],
        "constraints": [],
        "deferred": [],
        "product_observation": {"required": True, "reason": "delivered behavior"},
        "outcomes": [{
            "id": "O-01",
            "statement": "The app entry runs",
            "status": "pending",
            "user_entry": True,
            "verification": {
                "command": command,
                "expected": "The app smoke entry prints SMOKE-OK",
                "assertion_kind": "user-visible",
                "empty_result_policy": "empty output fails",
                "assertion": {"type": "stdout-contains", "literal": "SMOKE-OK"},
                "timeout_seconds": 60,
            },
        }],
    }


def render_goal(goal: dict) -> str:
    return (
        "---\nstatus: active\n---\n\n# Goal\n\n```json goal\n"
        + json.dumps(goal, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n```\n"
    )


def prepare_project(project: Path, case: str, variant: str, cid: str) -> dict:
    cfg = CASES[case]
    mvp = project / ".opencode" / "mvp"
    mvp.mkdir(parents=True, exist_ok=True)
    app_src = SANDBOX_APPS / case / variant
    app_dst = project / "app"
    if app_dst.exists():
        shutil.rmtree(app_dst)
    shutil.copytree(app_src, app_dst)
    # state reset for stateful fixtures (declared before the candidate freeze)
    state_paths = list(cfg.get("state_paths") or [])
    for rel in state_paths:
        state = project / rel
        if state.exists():
            state.unlink()
    goal_path = mvp / "g-obs.md"
    goal_path.write_text(render_goal(make_goal(case, cfg)), encoding="utf-8", newline="\n")

    cdir = mvp / "observation" / "G-OBS" / cid
    (cdir / "evidence").mkdir(parents=True, exist_ok=True)
    state_set = {path.replace("\\", "/") for path in state_paths}
    files = []
    for path in sorted(app_dst.rglob("*")):
        if path.is_file():
            rel = path.relative_to(project).as_posix()
            if rel in state_set:
                continue
            files.append({"path": rel, "sha256": sha256_file(path)})
    manifest = {
        "schema": "product-candidate/2",
        "candidate_id": cid,
        "entry": cfg["entry"],
        "environment": "windows-local calibration",
        "backend": cfg.get("backend", "cli"),
        "files": files,
        "test_data": [],
        "channels": cfg.get("channels", []),
        "baseline": {"kind": "none", "refs": []},
        "delivered_roots": ["app"],
    }
    if state_paths:
        manifest["runtime_state"] = [{
            "path": rel.replace("\\", "/"),
            "purpose": "state persisted by the fixture during normal use",
            "initial": {"kind": "absent"},
            "reset": "delete",
        } for rel in state_paths]
    jdump(manifest, cdir / "candidate.json")
    if state_paths:
        jdump({
            "schema": "runtime-state-policy/1",
            "goal_id": "G-OBS",
            "paths": [rel.replace("\\", "/") for rel in state_paths],
            "note": "calibration fixture writes these state files",
        }, mvp / "g-obs.runtime-state.json")
    rel = cdir.relative_to(project).as_posix()
    sidecar = {
        "schema": "product-audit/2",
        "goal_id": "G-OBS",
        "current_candidate": cid,
        "rounds": [{
            "candidate_id": cid,
            "discover_ref": f"{rel}/discover/run-001/result.json",
            "compare_ref": f"{rel}/compare/run-001/result.json",
            "review_ref": f"{rel}/review/run-001/result.json",
        }],
    }
    jdump(sidecar, mvp / "g-obs.product-audit.json")
    return {"cdir": cdir, "goal_path": goal_path, "config": cfg, "files": len(files)}


def build_packet(project: Path, goal_path: Path, phase: str, cdir: Path, model: str) -> tuple[Path | None, str]:
    engine = project / ".opencode" / "workflow" / "scripts" / "workflow_packets.py"
    out = cdir / f"{phase}.packet.json"
    argv = [sys.executable, str(engine), "observer", str(goal_path),
            "--phase", phase, "--model", model, "--out", str(out)]
    result = op.run_process(argv, cwd=project, timeout=120)
    if result["exit_code"] != 0:
        return None, op.text_of(result["stderr_bytes"])
    verify = op.run_process(
        [sys.executable, str(engine), "validate", str(out), "--goal", str(goal_path)],
        cwd=project, timeout=60,
    )
    if verify["exit_code"] != 0:
        return None, op.text_of(verify["stdout_bytes"]) + op.text_of(verify["stderr_bytes"])
    guard = dc.packet_guard(True)
    if guard["abort"]:
        return None, guard["reason"]
    return out, ""


def dispatch_resume(project: Path, session_id: str, agent: str, model: str,
                    prompt: str, timeout: int, raw_path: Path) -> dict:
    env = dict(os.environ, OPENCODE_DISABLE_AUTOUPDATE="1")
    argv = [opencode_executable(), "run", "--auto", "--model", model, "--agent", agent,
            "--session", session_id, "--format", "default", prompt]
    result = op.run_process(argv, cwd=project, timeout=timeout, env=env)
    text = op.text_of(result["stdout_bytes"])
    err = op.text_of(result["stderr_bytes"])
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(text + "\n--stderr--\n" + err, encoding="utf-8")
    return {
        "exit_code": result["exit_code"],
        "timed_out": result["timed_out"],
        "elapsed": result["elapsed_seconds"],
        "text": strip_ansi(text),
        "stderr": err,
    }


def adopt(project: Path, cdir: Path, phase: str, raw_text: str, model: str,
          since_ms: int, runs_dir: Path, session_id: str | None = None,
          attempt: int = 1, payload: dict | None = None) -> dict:
    problems = dc.result_source_is_single(raw_text)
    if problems:
        return {"ok": False, "stage": "single-channel", "problems": problems}
    if payload is None:
        payload, parse_problems = ores.parse_single_payload(raw_text)
        if payload is None:
            return {"ok": False, "stage": "parse", "problems": parse_problems}
    if session_id is None:
        session_id = find_dispatch_session(project, "po-observer", since_ms)
    if session_id is None:
        return {"ok": False, "stage": "session", "problems": ["no po-observer session found in store"]}
    trace, trace_error = export_trace(project)
    if trace is None:
        return {"ok": False, "stage": "trace", "problems": [trace_error]}
    if not any(s.get("id") == session_id for s in trace.get("sessions", [])):
        return {"ok": False, "stage": "trace-session", "problems": ["session missing from trace"]}
    envelope = {
        "goal_id": "G-OBS",
        "candidate_id": cdir.name,
        "observer_session_id": session_id,
        "model": model,
        "packet_hash": sha256_file(cdir / f"{phase}.packet.json"),
        "attempt": attempt,
    }
    result_path, adopt_problems = ores.adopt_result(
        cdir, project, phase, payload, envelope, trace,
    )
    if result_path is None:
        return {"ok": False, "stage": "adopt", "problems": adopt_problems, "session": session_id}
    sidecar = project / ".opencode" / "mvp" / "g-obs.product-audit.json"
    rel = result_path.relative_to(project).as_posix()
    _, sidecar_problems = ores.update_sidecar(sidecar, "G-OBS", cdir.name, phase, rel)
    if sidecar_problems:
        return {"ok": False, "stage": "sidecar", "problems": sidecar_problems, "session": session_id}
    jdump(payload, runs_dir / f"{phase}.payload.json")
    return {
        "ok": True, "path": str(result_path), "session": session_id,
        "stop_reason": payload.get("stop_reason"),
        "findings": [{
            "id": f.get("id"), "severity": f.get("severity"), "status": f.get("status"),
            "classification": f.get("difference_classification"),
            "observed": (f.get("observed") or "")[:200],
        } for f in (payload.get("findings") or [])],
        "surfaces": len(payload.get("surfaces") or []),
        "journeys": len(payload.get("journeys") or []),
    }


def discover_prompt(packet: Path, phase: str) -> str:
    return (
        "Load the skill tool `product-observer`, then read your phase packet at:\n"
        f"{packet}\n\n"
        f"Execute the {phase.upper()} phase exactly as the packet instructs, using only the "
        "packet's inputs. Operate the delivered product through its real entry point.\n\n"
        "Your final reply must end with exactly ONE fenced ```json block (nothing after it) "
        "and contain no other fenced block. The block is the product-observation/2 result."
    )


def review_prompt(goal: Path, discover: Path, compare: Path) -> str:
    return (
        "Load the skill tool `reviewer`. Judge the product observation evidence read-only.\n"
        f"goal card: {goal}\ndiscover result: {discover}\ncompare result: {compare}\n\n"
        "Do not operate any UI. End your reply with exactly ONE fenced ```json block "
        "(nothing after it) shaped as product-observation-review/2: schema, "
        "findings_validity (sufficient|insufficient), coverage_adequacy "
        "(sufficient|insufficient), verdict (sufficient|needs-observation|needs-repair|blocked), "
        "notes, related_finding_ids (optional)."
    )


def stop_server(server) -> None:
    if server is None or server.poll() is not None:
        return
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()


def run(args) -> int:
    project = Path(args.project).resolve()
    case = args.case
    model = args.model
    cid = args.cid
    phases = [p.strip() for p in args.phases.split(",") if p.strip()]
    runs_dir = Path(__file__).resolve().parent / "runs" / case / cid
    runs_dir.mkdir(parents=True, exist_ok=True)
    summary: dict = {
        "case": case, "variant": args.variant, "model": model, "cid": cid,
        "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "phases": {}, "gate": None, "status": "running",
    }

    if args.no_prepare:
        mvp = project / ".opencode" / "mvp"
        prepared = {
            "cdir": mvp / "observation" / "G-OBS" / cid,
            "goal_path": mvp / "g-obs.md",
            "config": CASES[case],
            "files": 0,
        }
    else:
        prepared = prepare_project(project, case, args.variant, cid)
    cdir = prepared["cdir"]
    if prepared["config"].get("web") and not args.no_prepare:
        port = prepared["config"]["port"]
        server = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
             "--directory", str(project / "app")],
            cwd=project, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        atexit.register(stop_server, server)
        time.sleep(1.5)
        summary["server"] = {"port": port, "pid": server.pid}
    # primary mirrors from the installed agent files
    agents = project / ".opencode" / "agents"
    for source, dest in (("mvp-product-observer.md", "po-observer.md"),
                         ("mvp-reviewer.md", "po-reviewer.md")):
        text = (agents / source).read_text(encoding="utf-8")
        mirror = dc.make_primary_mirror(text)
        (agents / dest).write_text(mirror, encoding="utf-8", newline="\n")
    summary["candidate"] = {"id": cid, "files": prepared["files"]}

    for phase in [p for p in phases if p in ("discover", "compare")]:
        packet, packet_error = build_packet(project, prepared["goal_path"], phase, cdir, model)
        if packet is None:
            summary["phases"][phase] = {"ok": False, "stage": "packet", "problems": [packet_error]}
            summary["status"] = "failed"
            jdump(summary, runs_dir / "metrics.json")
            return 2
        since = now_ms()
        t0 = time.time()
        dispatch_result = dispatch(project, "po-observer", model, discover_prompt(packet, phase),
                                   args.timeout, runs_dir / f"{phase}.raw.txt")
        session_id = find_dispatch_session(project, "po-observer", since)
        raw = dispatch_result["text"]
        payload, parse_problems = ores.parse_single_payload(raw)
        structural = (ocontract.validate_result_payload(payload, phase)
                      if isinstance(payload, dict) else [])
        repairs = 0
        repair_log: list[dict] = []
        while structural and repairs < 2 and isinstance(payload, dict):
            if not session_id:
                break
            repairs += 1
            repair_prompt = ores.repair_prompt(phase, payload, structural, repairs)
            repaired = dispatch_resume(project, session_id, "po-observer", model, repair_prompt,
                                       args.timeout, runs_dir / f"{phase}.repair{repairs}.raw.txt")
            new_payload, new_problems = ores.parse_single_payload(repaired["text"])
            repair_log.append({
                "attempt": repairs,
                "problems_before": structural[:12],
                "exit_code": repaired["exit_code"],
                "timed_out": repaired["timed_out"],
            })
            if isinstance(new_payload, dict) and new_payload.get("repair_outcome") == "needs-observation":
                repair_log[-1]["marker_reason"] = new_payload.get("reason")
                structural = ["repair marker: needs-observation"]
                payload = None
                break
            if not isinstance(new_payload, dict):
                structural = new_problems or ["repair reply had no parsable payload"]
                payload = None
                break
            payload = new_payload
            structural = ocontract.validate_result_payload(payload, phase)
        if structural or not isinstance(payload, dict):
            adopted = {
                "ok": False,
                "stage": "repair" if repairs else "schema",
                "problems": structural or parse_problems,
                "repairs": repairs,
                "session": session_id,
                "repair_log": repair_log,
                "dispatch": {
                    "exit_code": dispatch_result["exit_code"],
                    "timed_out": dispatch_result["timed_out"],
                    "elapsed_seconds": round(time.time() - t0, 1),
                },
            }
        else:
            fenced = "```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"
            adopted = adopt(project, cdir, phase, fenced, model, since, runs_dir,
                            session_id=session_id, attempt=repairs + 1, payload=payload)
            adopted["repairs"] = repairs
            adopted["repair_log"] = repair_log
            adopted["dispatch"] = {
                "exit_code": dispatch_result["exit_code"],
                "timed_out": dispatch_result["timed_out"],
                "elapsed_seconds": round(time.time() - t0, 1),
            }
        summary["phases"][phase] = adopted
        if not adopted.get("ok"):
            summary["status"] = "failed"
            jdump(summary, runs_dir / "metrics.json")
            return 2

    if "review" in phases or phases == ["review"]:
        if not (cdir / "discover" / "run-001" / "result.json").is_file() or \
           not (cdir / "compare" / "run-001" / "result.json").is_file():
            summary["status"] = "failed"
            summary["review"] = {"ok": False, "problems": ["discover/compare result missing"]}
            jdump(summary, runs_dir / "metrics.json")
            return 2
        prompt = review_prompt(
            prepared["goal_path"],
            cdir / "discover" / "run-001" / "result.json",
            cdir / "compare" / "run-001" / "result.json",
        )
        since = now_ms()
        review_dispatch = dispatch(project, "po-reviewer", model, prompt, args.timeout,
                                   runs_dir / "review.raw.txt")
        session_id = find_dispatch_session(project, "po-reviewer", since)
        trace, trace_error = export_trace(project)
        review_failures: list[str] = []
        review_payload, parse_problems = ores.parse_single_payload(review_dispatch["text"])
        if parse_problems:
            review_failures.extend(parse_problems)
        if session_id is None:
            review_failures.append("no po-reviewer session found")
        if trace is None:
            review_failures.append(trace_error)
        if not review_failures and review_payload is not None and trace is not None:
            envelope = {"reviewer_session_id": session_id, "model": model, "attempt": 1}
            review_path, adopt_problems = ores.adopt_review(
                cdir, project, review_payload, envelope,
                cdir / "discover" / "run-001" / "result.json",
                cdir / "compare" / "run-001" / "result.json",
                trace,
            )
            if review_path is None:
                review_failures.extend(adopt_problems)
            else:
                sidecar = project / ".opencode" / "mvp" / "g-obs.product-audit.json"
                _, sidecar_problems = ores.update_sidecar(
                    sidecar, "G-OBS", cid, "review", review_path.relative_to(project).as_posix())
                review_failures.extend(sidecar_problems)
                jdump(review_payload, runs_dir / "review.payload.json")
                summary["review"] = {"ok": True, "verdict": review_payload.get("verdict"),
                                     "findings_validity": review_payload.get("findings_validity"),
                                     "coverage_adequacy": review_payload.get("coverage_adequacy")}
        if review_failures:
            summary.setdefault("review", {})
            summary["review"].update({"ok": False, "problems": review_failures})

    if args.gate:
        trace_exported, trace_error = export_trace(project)
        engine = project / ".opencode" / "workflow" / "scripts" / "check.py"
        gate = op.run_process(
            [sys.executable, str(engine), "product-audit-gate", str(prepared["goal_path"]),
             "--trace", str(project / ".opencode" / "mvp" / "trace.json")],
            cwd=project, timeout=180,
        )
        gate_out = op.text_of(gate["stdout_bytes"]) + op.text_of(gate["stderr_bytes"])
        (runs_dir / "gate.txt").write_text(gate_out, encoding="utf-8")
        summary["gate"] = {"exit_code": gate["exit_code"], "output": gate_out.strip()[:4000]}
        if trace_exported is None:
            summary["gate"]["trace_error"] = trace_error

    summary["status"] = "completed" if all(
        item.get("ok") for item in summary["phases"].values()
    ) else "failed"
    summary["finished_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    jdump(summary, runs_dir / "metrics.json")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "completed" else 2


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--case", required=True, choices=sorted(CASES))
    parser.add_argument("--variant", default="good", choices=("good", "bad", "redesign"))
    parser.add_argument("--model", default="openai/gpt-5.6-luna")
    parser.add_argument("--cid", default="cand-calib-1")
    parser.add_argument("--phases", default="discover,compare,review")
    parser.add_argument("--timeout", type=int, default=DISPATCH_TIMEOUT)
    parser.add_argument("--no-prepare", action="store_true",
                        help="skip fixture/goal/candidate reset (continue an existing round)")
    parser.add_argument("--no-gate", dest="gate", action="store_false")
    parser.set_defaults(gate=True)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())

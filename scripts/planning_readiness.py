"""Readiness conditions, declared probe dependencies and durable owner decisions.

Checks deterministic obligations, NOT feasibility, informed consent or semantic
review quality. Decision excerpts are locally attributed references, not native
identity authentication. Existing native trace/reviewer gates remain necessary.
"""
import hashlib
import json
import re
import time
from pathlib import Path, PureWindowsPath

import runtime_trace


def text(value):
    return isinstance(value, str) and bool(value.strip())


def names(value, empty=False):
    return isinstance(value, list) and (empty or bool(value)) and all(text(x) for x in value)


def relative(value):
    return text(value) and not Path(value).is_absolute() and not PureWindowsPath(value).drive and ".." not in value.replace("\\", "/").split("/")


def ancestry(steps):
    result = {s: set() for s in steps}
    for _ in steps:
        for sid, step in steps.items():
            for dep in step["depends_on"]:
                result[sid].add(dep)
                result[sid].update(result.get(dep, set()))
    return result


def validate(plan, goal, groups):
    """Base validation has already passed, so references used here are typed."""
    errors, steps = [], groups["steps"]
    before = ancestry(steps)
    conditions = plan.get("conditions")
    if not isinstance(conditions, list):
        return ["conditions must be an explicit array (empty when no open prerequisites)"]
    by_id = {}
    for c in conditions:
        if not isinstance(c, dict) or not re.fullmatch(r"Q-\d{2,}", str(c.get("id", ""))):
            errors.append("invalid condition id")
            continue
        cid = c["id"]
        if cid in by_id:
            errors.append("duplicate condition " + cid)
        by_id[cid] = c
        if c.get("kind") not in ("check", "owner", "review"):
            errors.append(f"{cid}: kind must be check/owner/review")
        if any(not text(c.get(k)) for k in ("claim", "criterion")):
            errors.append(f"{cid}: claim and criterion required")
        affected = c.get("affects")
        if not names(affected) or any(s not in steps for s in affected):
            errors.append(f"{cid}: affects must reference real steps")
            continue
        if type(c.get("evidence_required")) is not bool:
            errors.append(f"{cid}: evidence_required must be boolean")
        if c.get("kind") == "check":
            resolver = c.get("resolver")
            if not isinstance(resolver, dict) or not text(resolver.get("step")) or not text(resolver.get("check")):
                errors.append(f"{cid}: resolver needs step/check")
                continue
            provider = resolver["step"]
            checks = steps.get(provider, {}).get("checks", [])
            if not any(chk["id"] == resolver["check"] for chk in checks):
                errors.append(f"{cid}: resolver check does not exist")
            if any(provider not in before[s] for s in affected):
                errors.append(f"{cid}: resolver must precede every affected step (no self-dependent condition)")
    for decision in plan["decisions"]:
        if (type(decision.get("critical")) is not bool or decision.get("evidence_level") not in ("assumed", "documented", "measured")
                or not text(decision.get("scope")) or not text(decision.get("invalidated_by"))):
            errors.append("decision needs critical, evidence_level, scope and invalidated_by")
        if decision.get("critical") is True and decision.get("evidence_level") != "measured":
            if not text(decision.get("condition")) or decision["condition"] not in by_id:
                errors.append("critical unmeasured decision needs a blocking condition")
    review = plan.get("design_review")
    if not isinstance(review, dict) or review.get("mode") not in ("self", "independent") or not text(review.get("reason")):
        errors.append("design_review needs mode=self|independent and reason")
    elif review["mode"] == "independent":
        cid = review.get("condition")
        c = by_id.get(cid, {}) if text(cid) else {}
        if c.get("kind") != "review":
            errors.append("independent design_review must name a review condition")
        elif names(c.get("affects")):
            for sid, step in steps.items():
                if step.get("kind") != "probe" and not (set(c["affects"]) & (before[sid] | {sid})):
                    errors.append(f"{sid}: implementation is not gated by independent design review")
    elif goal["rigor"] in ("guarded", "audited"):
        errors.append("guarded/audited design requires independent review; probe tasks may run before it")
    for sid, step in steps.items():
        if step.get("kind") not in ("probe", "implementation"):
            errors.append(f"{sid}: kind must be probe or implementation")
    for bid, boundary in groups["boundaries"].items():
        if not boundary["external"]:
            continue
        requires = boundary["probe"].get("requires_files")
        if not isinstance(requires, list):
            errors.append(f"{bid}: preflight probe requires_files must be explicit (may be empty)")
            continue
        for item in requires:
            if not isinstance(item, dict) or not relative(item.get("path")) or not text(item.get("provided_by")):
                errors.append(f"{bid}: invalid preflight file prerequisite")
                continue
            provider = item["provided_by"]
            if provider != "existing":
                if provider not in steps or item["path"] not in steps.get(provider, {}).get("files", []):
                    errors.append(f"{bid}: preflight producer does not declare the required file")
                for sid, step in steps.items():
                    if bid in step["preflight_boundary_ids"] and provider not in before[sid]:
                        errors.append(f"{sid}: preflight depends on a tool created by itself or a later/non-dependent step ({provider})")
    return errors


def _read(path, engine):
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError("object required")
        return value
    except (OSError, ValueError) as exc:
        raise engine.ValidationError(f"decision record unreadable: {path}: {exc}") from exc


def _file(root, ref, engine):
    if not relative(ref):
        raise engine.ValidationError("decision source/evidence must be project-relative")
    path = (root / ref).resolve()
    try:
        path.relative_to(root)
        data = path.read_bytes()
        if not data:
            raise ValueError("empty file")
        return path, hashlib.sha256(data).hexdigest()
    except (ValueError, OSError) as exc:
        raise engine.ValidationError(f"decision source/evidence unavailable: {ref}: {exc}") from exc


def _verify_source(root, source, role, engine):
    if not isinstance(source, dict) or not isinstance(source.get("native_message"), dict):
        raise engine.ValidationError("decision must reference an actual native conversation message")
    trace_ref = source.get("trace_path")
    if not relative(trace_ref):
        raise engine.ValidationError("native decision trace must be project-relative")
    trace_path = (root / trace_ref).resolve()
    try:
        trace_path.relative_to(root)
        raw = trace_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != source.get("trace_sha256"):
            raise ValueError("trace hash mismatch")
        trace = runtime_trace.load_trace(trace_path)
        event, problems = runtime_trace.verify_conversation_reference(
            trace, source["native_message"], root, role=role)
        if problems:
            raise ValueError("; ".join(problems))
        return event, hashlib.sha256(raw).hexdigest(), trace
    except (OSError, ValueError, runtime_trace.TraceValidationError) as exc:
        raise engine.ValidationError(f"native decision evidence invalid: {exc}") from exc


def _response(root, path, binding, engine, role="user"):
    versions = _versions(path)
    if not versions:
        return None
    previous = None
    for version in versions:
        result = _read(version, engine)
        if result.get("binding") != binding or result.get("previous_sha256") != previous:
            raise engine.ValidationError("decision history binding/chain mismatch")
        previous = hashlib.sha256(version.read_bytes()).hexdigest()
    if result.get("binding") != binding or result.get("decision") not in ("accept", "reject", "revise"):
        raise engine.ValidationError("decision identity or outcome mismatch")
    source = result.get("source")
    event, trace_sha, trace = _verify_source(root, source, role, engine)
    if result.get("source_trace_sha256") != trace_sha or result.get("source_time_ms") != event.get("time_ms"):
        raise engine.ValidationError("native decision source binding changed")
    if not isinstance(result.get("evidence"), list) or not text(result.get("reason")):
        raise engine.ValidationError("decision evidence/reason malformed")
    for ev in result["evidence"]:
        if not isinstance(ev, dict) or _file(root, ev.get("path"), engine)[1] != ev.get("sha256"):
            raise engine.ValidationError("decision evidence changed")
    # Ephemeral only: do not copy the conversation into the decision artifact.
    result["_verified_trace"] = trace
    return result


def _versions(path):
    home = path.with_suffix("")
    return sorted(p for p in home.glob("*.json") if p.is_file() and re.fullmatch(r"\d{6}\.json", p.name))


def request_home(goal_path, goal_id):
    return Path(goal_path).parent / "decisions" / goal_id


def requests(root, goal_path, goal, engine):
    home = request_home(goal_path, goal["id"])
    for path in sorted((home / "requests").glob("D-*.json")):
        req = _read(path, engine)
        if (not re.fullmatch(r"D-\d{2,}", str(req.get("id", ""))) or req.get("goal_id") != goal["id"]
                or path.stem != req["id"]):
            raise engine.ValidationError("owner request identity mismatch")
        binding = engine.digest(req, "decision-request")
        response = _response(root, home / "responses" / (req["id"] + ".json"), binding, engine, role="user")
        if response and response.get("actor") != "owner":
            raise engine.ValidationError("owner request resolved by wrong actor")
        if response and response.get("source_time_ms", 0) < req.get("requested_at_ms", 0):
            raise engine.ValidationError("owner response predates the request")
        yield req, response


def publication_guard(root, goal_path, goal, engine):
    for req, response in requests(root, goal_path, goal, engine):
        if response is None or response["decision"] == "reject":
            raise engine.ValidationError("owner decision pending/rejected; resolve " + req["id"] + " before publishing another plan")


class Readiness:
    def __init__(self, cycles):
        self.c = cycles
        self.e = cycles.e
        self.conditions = {x["id"]: x for x in cycles.plan.get("conditions", [])} if cycles.plan["schema"] == "engineering-plan/3" else {}
        self.before = ancestry(cycles.steps)

    def hold(self):
        for req, response in requests(self.c.root, self.c.path, self.c.goal, self.e):
            if response is None:
                return {"action": "owner-decision", "request": req}
            if response["decision"] == "reject":
                return {"action": "blocked", "request": req, "resolution": response}
            if response["decision"] == "revise" and req["definition"] == self.c.definition:
                return {"action": "replan", "request": req, "resolution": response}
        return None

    def guard(self):
        hold = self.hold()
        if hold:
            self.c.fail("owner intervention requires " + hold["action"] + "; request " + hold["request"]["id"])

    def pending(self, sid, completed):
        pending = []
        for condition in self.conditions.values():
            if not (set(condition["affects"]) & (self.before[sid] | {sid})):
                continue
            if condition["kind"] == "check":
                # history() already rechecks all receipts of completed provider steps.
                ready = condition["resolver"]["step"] in completed
            else:
                record = self._condition_response(condition)
                ready = record is not None and record["decision"] == "accept"
            if not ready:
                pending.append(condition)
        return pending

    def missing_files(self, sid):
        missing = []
        for bid in self.c.steps[sid].get("preflight_boundary_ids", []):
            for item in self.c.boundaries[bid].get("probe", {}).get("requires_files", []):
                path = (self.c.root / item["path"]).resolve()
                if not path.is_relative_to(self.c.root) or not path.is_file():
                    missing.append(item)
        return missing

    def _condition_response(self, condition):
        binding = self.e.digest({"identity": self.c.identity, "condition": condition}, "plan-condition")
        role = "assistant" if condition["kind"] == "review" else "user"
        result = _response(self.c.root, self.c.home / "decisions" / (condition["id"] + ".json"), binding, self.e, role=role)
        if result:
            actor = "reviewer" if condition["kind"] == "review" else "owner"
            if result.get("actor") != actor:
                self.c.fail("condition decision actor mismatch")
            if condition["evidence_required"] and result["decision"] == "accept" and not result["evidence"]:
                self.c.fail("condition accepted without required evidence")
            if actor == "reviewer" and (not text(result.get("author_session")) or not text(result.get("reviewer_session"))
                                        or result["author_session"] == result["reviewer_session"]):
                self.c.fail("independent review lacks distinct session references")
            if actor == "reviewer":
                trace = result.get("_verified_trace")
                session = next((s for s in trace.get("sessions", []) if s.get("id") == result["reviewer_session"]), {}) if trace else {}
                if session.get("agent") != "mvp-reviewer" or session.get("parent_id") != result["author_session"]:
                    self.c.fail("review evidence is not from a native mvp-reviewer child session")
        return result

    def request(self, data):
        if (not isinstance(data, dict) or not re.fullmatch(r"D-\d{2,}", str(data.get("id", "")))
                or any(not text(data.get(k)) for k in ("question", "basis"))
                or not names(data.get("affects")) or any(x not in self.c.steps for x in data["affects"])):
            self.c.fail("owner request requires D-NN id, question, basis and affected step ids")
        # This is an interruption, not a test failure or approval; no cycle is falsely completed.
        record = {k: data[k] for k in ("id", "question", "basis", "affects")}
        if type(data.get("evidence_required")) is not bool:
            self.c.fail("owner request must explicitly declare evidence_required")
        record.update(goal_id=self.c.goal["id"], definition=self.c.definition,
                      requested_at=self.e._now_iso(), requested_at_ms=int(time.time() * 1000),
                      evidence_required=data["evidence_required"])
        self.c.write(request_home(self.c.path, self.c.goal["id"]) / "requests" / (data["id"] + ".json"), record)
        return {"action": "owner-decision", "request": record}

    def resolve(self, subject, data):
        home = request_home(self.c.path, self.c.goal["id"])
        condition = self.conditions.get(subject)
        if condition:
            if condition["kind"] == "check":
                self.c.fail("technical condition requires an actual observed check; decisions cannot waive it")
            actor = "reviewer" if condition["kind"] == "review" else "owner"
            binding = self.e.digest({"identity": self.c.identity, "condition": condition}, "plan-condition")
            dest = self.c.home / "decisions" / (subject + ".json")
            needs_evidence = condition["evidence_required"]
        elif re.fullmatch(r"D-\d{2,}", subject):
            request = _read(home / "requests" / (subject + ".json"), self.e)
            actor, needs_evidence = "owner", request.get("evidence_required") is True
            binding = self.e.digest(request, "decision-request")
            dest = home / "responses" / (subject + ".json")
        else:
            self.c.fail("unknown decision subject")
        if (not isinstance(data, dict) or data.get("decision") not in ("accept", "reject", "revise")
                or data.get("actor") != actor or not text(data.get("reason"))):
            self.c.fail("decision requires matching actor, accept/reject/revise and reason")
        source = data.get("source")
        event, trace_sha, trace = _verify_source(self.c.root, source, "assistant" if actor == "reviewer" else "user", self.e)
        refs = data.get("evidence_refs", [])
        if not names(refs, empty=not (needs_evidence and data["decision"] == "accept")):
            self.c.fail("acceptance requires demonstration/review evidence references")
        if actor == "reviewer":
            native_session = next((s for s in trace.get("sessions", []) if s.get("id") == source["native_message"]["session_id"]), {})
            if (native_session.get("agent") != "mvp-reviewer" or native_session.get("id") != data.get("reviewer_session")
                    or native_session.get("parent_id") != data.get("author_session")):
                self.c.fail("review reply is not from the dispatched native mvp-reviewer child session")
            dispatched = any(t.get("child_session") == data["reviewer_session"]
                             and t.get("controller_session") == data["author_session"]
                             and t.get("requested_agent") == "mvp-reviewer" and t.get("status") == "completed"
                             for t in trace.get("task_events", []))
            if not dispatched:
                self.c.fail("reviewer session lacks a completed native mvp-reviewer dispatch from the design author")
        record = {"subject": subject, "binding": binding, "decision": data["decision"], "actor": actor,
                  "reason": data["reason"], "recorded_at": self.e._now_iso(),
                  "source": source, "source_trace_sha256": trace_sha, "source_time": event.get("time"),
                  "source_time_ms": event.get("time_ms"),
                  "evidence": [{"path": ref, "sha256": _file(self.c.root, ref, self.e)[1]} for ref in refs],
                  "provenance": "native-session-message-verified; semantic-intent-still-reviewed"}
        if actor == "reviewer":
            if (not text(data.get("author_session")) or not text(data.get("reviewer_session"))
                    or data["author_session"] == data["reviewer_session"]):
                self.c.fail("independent review needs distinct author/reviewer session references; native provenance still required at audit")
            record.update(author_session=data["author_session"], reviewer_session=data["reviewer_session"])
        versions = _versions(dest)
        record["previous_sha256"] = hashlib.sha256(versions[-1].read_bytes()).hexdigest() if versions else None
        self.c.write(dest.with_suffix("") / f"{len(versions) + 1:06d}.json", record)
        return record

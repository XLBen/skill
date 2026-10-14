#!/usr/bin/env python3
"""Sealed local HTTP boundary used by the L3 benchmark."""

from __future__ import annotations

import argparse
import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


TOKEN = "benchmark-token"


class BoundaryState:
    def __init__(self, scenario_file: Path):
        self.scenario_file = scenario_file
        self.lock = threading.Lock()
        self.counts: dict[str, int] = {}

    def scenario(self) -> str:
        return self.scenario_file.read_text(encoding="utf-8").strip()

    def increment(self, scenario: str, cursor: str) -> int:
        key = f"{scenario}:{cursor or '<root>'}"
        with self.lock:
            value = self.counts.get(key, 0) + 1
            self.counts[key] = value
            return value

    def snapshot(self) -> dict[str, int]:
        with self.lock:
            return dict(sorted(self.counts.items()))


class Handler(BaseHTTPRequestHandler):
    server_version = "SkillBenchmarkBoundary/1.0"

    @property
    def state(self) -> BoundaryState:
        return self.server.state  # type: ignore[attr-defined]

    def send_json(self, status: int, payload: object, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path == "/health":
            self.send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if parsed.path == "/__stats":
            self.send_json(
                HTTPStatus.OK,
                {"counts": self.state.snapshot(), "scenario": self.state.scenario()},
            )
            return
        if parsed.path != "/v1/catalog":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not-found"})
            return
        if self.headers.get("X-Client-Token") != TOKEN:
            self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return

        query = parse_qs(parsed.query, keep_blank_values=True)
        cursor = query.get("cursor", [""])[0]
        scenario = self.state.scenario()
        attempt = self.state.increment(scenario, cursor)
        if scenario == "outage":
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "upstream-unavailable"})
            return
        if attempt % 2 == 1:
            self.send_json(
                HTTPStatus.TOO_MANY_REQUESTS,
                {"error": "rate-limited"},
                {"Retry-After": "0"},
            )
            return

        if cursor not in {"", "c2"}:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid-cursor"})
            return
        if scenario == "invalid-schema":
            self.send_json(
                HTTPStatus.OK,
                {
                    "items": [{"id": "", "name": "Broken", "price_cents": "NaN", "version": 1}],
                    "next_cursor": None,
                },
            )
            return

        if cursor == "":
            rows = [
                {"id": "p1", "name": "Alpha", "price_cents": 100, "version": 1},
                {"id": "p2", "name": "Beta", "price_cents": 200, "version": 1},
            ]
            next_cursor: str | None = "c2"
        else:
            rows = [
                {"id": "p2", "name": "Beta Prime", "price_cents": 250, "version": 2},
                {"id": "p3", "name": "Gamma", "price_cents": 300, "version": 1},
            ]
            next_cursor = None
        if scenario == "schema-v2":
            rows = [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "price": str(row["price_cents"]),
                    "version": row["version"],
                }
                for row in rows
            ]
        self.send_json(HTTPStatus.OK, {"items": rows, "next_cursor": next_cursor})

    def log_message(self, format_string: str, *args: object) -> None:
        print(f"boundary {self.address_string()} {format_string % args}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--scenario-file",
        type=Path,
        default=Path(__file__).resolve().with_name("scenario.txt"),
    )
    args = parser.parse_args()
    state = BoundaryState(args.scenario_file.resolve())
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.state = state  # type: ignore[attr-defined]
    print(f"boundary-ready http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

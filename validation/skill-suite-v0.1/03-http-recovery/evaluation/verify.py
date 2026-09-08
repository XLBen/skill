#!/usr/bin/env python3
"""Owner-only black-box oracle for the L3 catalog mirror."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROGRAM = ROOT / "src" / "catalog_sync.py"
SERVER = ROOT / "boundary" / "server.py"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def fetch_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


def compact(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def output_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def expected_catalog() -> dict[str, object]:
    return {
        "count": 3,
        "items": [
            {"id": "p1", "name": "Alpha", "price_cents": 100, "version": 1},
            {"id": "p2", "name": "Beta Prime", "price_cents": 250, "version": 2},
            {"id": "p3", "name": "Gamma", "price_cents": 300, "version": 1},
        ],
    }


def main() -> int:
    failures: list[str] = []
    checks = 0

    def require(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(message)

    require(PROGRAM.is_file(), "src/catalog_sync.py is missing")
    if not PROGRAM.is_file():
        print("L3 ORACLE FAIL")
        print("- src/catalog_sync.py is missing")
        return 1

    with tempfile.TemporaryDirectory(prefix="skill-l3-") as raw_temp:
        temp = Path(raw_temp)
        scenario_file = temp / "scenario.txt"
        scenario_file.write_text("normal\n", encoding="utf-8")
        port = free_port()
        base_url = f"http://127.0.0.1:{port}"
        server = subprocess.Popen(
            [
                sys.executable,
                str(SERVER),
                "--port",
                str(port),
                "--scenario-file",
                str(scenario_file),
            ],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 5
            while True:
                try:
                    fetch_json(base_url + "/health")
                    break
                except Exception:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("benchmark boundary did not become ready")
                    time.sleep(0.05)

            output = temp / "catalog.json"

            def sync(*extra: str, token: str | None = "benchmark-token") -> subprocess.CompletedProcess[str]:
                env = os.environ.copy()
                if token is None:
                    env.pop("CATALOG_TOKEN", None)
                else:
                    env["CATALOG_TOKEN"] = token
                return subprocess.run(
                    [
                        sys.executable,
                        str(PROGRAM),
                        "--base-url",
                        base_url,
                        "--output",
                        str(output),
                        *extra,
                    ],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    timeout=10,
                    check=False,
                )

            one_page = sync("--max-pages", "1")
            one_expected = {
                "count": 2,
                "items": [
                    {"id": "p1", "name": "Alpha", "price_cents": 100, "version": 1},
                    {"id": "p2", "name": "Beta", "price_cents": 200, "version": 1},
                ],
            }
            require(one_page.returncode == 0, "single-page sync failed")
            require(one_page.stdout == "", "successful single-page sync wrote stdout")
            require(output_bytes(output) == compact(one_expected), "single-page output is wrong or non-deterministic")

            full = sync()
            require(full.returncode == 0, "normal multi-page sync failed")
            require(output_bytes(output) == compact(expected_catalog()), "pagination/dedup output is wrong")
            stable = output_bytes(output)

            scenario_file.write_text("outage\n", encoding="utf-8")
            started = time.monotonic()
            outage = sync()
            elapsed = time.monotonic() - started
            require(outage.returncode != 0, "permanent 503 outage succeeded")
            require(outage.stdout == "", "503 failure wrote stdout")
            require(output_bytes(output) == stable, "503 failure replaced the previous output")
            require(elapsed < 8, "503 retry policy was not bounded")
            stats = fetch_json(base_url + "/__stats")
            outage_count = int(stats["counts"].get("outage:<root>", 0))  # type: ignore[index,union-attr]
            require(outage_count == 3, f"503 attempts were {outage_count}, expected exactly 3")

            scenario_file.write_text("schema-v2\n", encoding="utf-8")
            schema_v2 = sync()
            require(schema_v2.returncode == 0, "owner-approved schema-v2 sync failed")
            require(output_bytes(output) == compact(expected_catalog()), "schema-v2 normalization is wrong")
            stable_v2 = output_bytes(output)

            scenario_file.write_text("invalid-schema\n", encoding="utf-8")
            invalid = sync()
            require(invalid.returncode != 0, "invalid schema succeeded")
            require(invalid.stdout == "", "invalid schema wrote stdout")
            require(output_bytes(output) == stable_v2, "invalid schema replaced the previous output")

            missing_token = sync(token=None)
            require(missing_token.returncode != 0, "missing token succeeded")
            require(missing_token.stdout == "", "missing token wrote stdout")
            require(output_bytes(output) == stable_v2, "missing token changed output")
        finally:
            server.terminate()
            try:
                server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=3)

    if failures:
        print(f"L3 ORACLE FAIL ({len(failures)}/{checks} checks failed)")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"L3 ORACLE PASS ({checks} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

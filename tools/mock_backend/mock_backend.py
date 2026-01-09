#!/usr/bin/env python3
"""
Minimal mock backend for ECS worker POC.

Endpoints:
- GET /jobs/<job_id>
- PUT /data
- PUT /end
"""

from __future__ import annotations

import argparse
import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class JobStore:
    def __init__(self, jobs: dict[str, dict[str, Any]]):
        self._jobs = jobs
        self._data_updates: list[dict[str, Any]] = []
        self._end_updates: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self._jobs.get(job_id)

    def record_data(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._data_updates.append(payload)

    def record_end(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._end_updates.append(payload)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "data_updates": list(self._data_updates),
                "end_updates": list(self._end_updates),
            }


class MockBackendHandler(BaseHTTPRequestHandler):
    store: JobStore
    logger: logging.Logger
    log_path: Path | None = None

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _log_payload(self, label: str, payload: dict[str, Any]) -> None:
        self.logger.info("%s %s", label, payload)
        if self.log_path:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"label": label, "payload": payload}) + "\n")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json({"status": "ok"})
            return

        if parsed.path.count("/") == 1 and parsed.path != "/":
            job_id = parsed.path.lstrip("/")
            job = self.store.get_job(job_id)
            if not job:
                self._send_json({"error": "job not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(job)
            return

        if parsed.path.startswith("/jobs/"):
            job_id = parsed.path.split("/", 2)[2]
            job = self.store.get_job(job_id)
            if not job:
                self._send_json({"error": "job not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(job)
            return

        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        payload = self._read_json()
        if parsed.path == "/data":
            self.store.record_data(payload)
            self._log_payload("data", payload)
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/end":
            self.store.record_end(payload)
            self._log_payload("end", payload)
            self._send_json({"status": "ok"})
            return

        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        self.logger.info("%s - %s", self.address_string(), format % args)


def load_jobs(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Jobs file must be a JSON object keyed by job id.")
    return {str(key): value for key, value in data.items()}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mock backend for ECS worker POC")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--jobs-file",
        type=Path,
        default=Path(__file__).with_name("sample_jobs.json"),
        help="Path to JSON file keyed by job id",
    )
    parser.add_argument("--log-file", type=Path, default=Path("mock_backend.log"))
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("mock-backend")

    jobs = load_jobs(args.jobs_file)
    store = JobStore(jobs)

    MockBackendHandler.store = store
    MockBackendHandler.logger = logger
    MockBackendHandler.log_path = args.log_file

    server = ThreadingHTTPServer((args.host, args.port), MockBackendHandler)
    logger.info("Mock backend listening on %s:%s", args.host, args.port)
    logger.info("Jobs loaded: %s", ", ".join(jobs.keys()))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

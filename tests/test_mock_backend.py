import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

import logging

from tools.mock_backend.mock_backend import JobStore, MockBackendHandler, ThreadingHTTPServer, load_jobs


def _start_server(tmp_path: Path) -> tuple[ThreadingHTTPServer, int]:
    jobs_path = tmp_path / "jobs.json"
    jobs_path.write_text(
        json.dumps(
            {
                "job-test": {
                    "data": {
                        "job": {
                            "workflowName": "workflow-fuzzing-scouting",
                            "additionalData": {"jobType": "workflowName"},
                        },
                        "repoAccessData": {"url": "https://github.com/transmissions11/solmate"},
                        "claudeAccessData": {"url": "https://github.com/Recon-Fuzz/ai-agent-primers"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    store = JobStore(load_jobs(jobs_path))
    MockBackendHandler.store = store  # type: ignore[attr-defined]
    MockBackendHandler.logger = logging.getLogger("test-mock-backend")  # type: ignore[attr-defined]
    MockBackendHandler.log_path = None  # type: ignore[attr-defined]

    server = ThreadingHTTPServer(("127.0.0.1", 0), MockBackendHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    return server, port


def test_mock_backend_routes(tmp_path: Path) -> None:
    server, port = _start_server(tmp_path)
    try:
        conn = HTTPConnection("127.0.0.1", port)

        conn.request("GET", "/jobs/job-test")
        response = conn.getresponse()
        assert response.status == 200
        payload = json.loads(response.read().decode("utf-8"))
        assert payload["data"]["job"]["workflowName"] == "workflow-fuzzing-scouting"

        body = json.dumps({"jobId": "job-test", "resultData": {"steps": [{"name": "Step 1"}]}})
        conn.request("PUT", "/data", body=body, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        assert response.status == 200

        body = json.dumps({"jobId": "job-test", "status": "success"})
        conn.request("PUT", "/end", body=body, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        assert response.status == 200
    finally:
        server.shutdown()

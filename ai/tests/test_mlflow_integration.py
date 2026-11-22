"""Real disposable MLflow persistence; optional isolated server dependency."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError

import pytest

from roleready_ai.tracking import TrackingClient

pytestmark = pytest.mark.skipif(importlib.util.find_spec("mlflow") is None,
                               reason="Run with isolated MLflow requirements; never install implicitly")


def test_real_server_persists_runs_and_artifacts_and_idempotent_import(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
    uri = f"http://127.0.0.1:{port}"
    client = TrackingClient(uri)
    command = [sys.executable, "-m", "mlflow", "server", "--host", "127.0.0.1", "--port", str(port),
               "--backend-store-uri", "sqlite:///" + (tmp_path / "runs.db").as_posix(),
               "--artifacts-destination", str(tmp_path / "artifacts"), "--workers", "1"]
    def start():
        log = (tmp_path / "server.log").open("ab")
        process = subprocess.Popen(command, cwd=tmp_path, stdout=log, stderr=log,
            env={**os.environ, "DO_NOT_TRACK": "true"},
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        for _ in range(120):
            try:
                client.experiment("integration-fixture")
                return process, log
            except (URLError, ConnectionError):
                if process.poll() is not None:
                    pytest.fail((tmp_path / "server.log").read_text(errors="replace"))
                time.sleep(.25)
        process.terminate(); pytest.fail("MLflow startup timeout")
    process, log = start()
    def stop(process, log):
        import psutil
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            child.terminate()
        process.terminate()
        process.wait(timeout=20)
        psutil.wait_procs(children, timeout=10)
        log.close()
    try:
        args = dict(experiment="integration-fixture", key="authored-fixture", params={"condition": "none"},
                    metrics={"requests": 1, "quality": None}, artifact={"quality_metrics": None})
        first = client.log(**args)
        assert client.log(**args) == first
        run = client.request("/api/2.0/mlflow/runs/get?run_id=" + first)["run"]
        assert [m["key"] for m in run["data"]["metrics"]] == ["requests"]
        path = run["info"]["artifact_uri"].split(":", 1)[1].lstrip("/")
        assert client.request("/api/2.0/mlflow-artifacts/artifacts/" + path + "/record.json") == {"quality_metrics": None}
    finally:
        stop(process, log)
    process, log = start()
    try:
        assert client.log(**args) == first
    finally:
        stop(process, log)

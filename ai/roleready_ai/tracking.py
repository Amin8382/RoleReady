"""Local-only MLflow REST transport; inference needs no MLflow dependency.

The immutable JSON records on disk are the source of truth. Replaying a record
uses a content-derived key, so an interrupted upload never requires inference.
"""
from __future__ import annotations

import json
import math
import time
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


def digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if exclusive:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    else:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8", newline="\n")
        temporary.replace(path)


def local_url(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Experiment endpoints must be local HTTP without credentials/query")
    return url.rstrip("/")


class TrackingClient:
    def __init__(self, uri: str = "http://127.0.0.1:5000"):
        self.uri = local_url(uri)

    def request(self, path: str, data=None, *, method: str | None = None, raw: bytes | None = None):
        body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
        request = Request(self.uri + path, data=body,
                          headers={"Content-Type": "application/octet-stream" if raw is not None else "application/json"},
                          method=method or ("POST" if body is not None else "GET"))
        with urlopen(request, timeout=30) as response:
            result = response.read()
        return json.loads(result) if result else {}

    def experiment(self, name: str) -> str:
        found = self.request("/api/2.0/mlflow/experiments/search", {"filter": f"name = '{name}'", "max_results": 1000})
        if found.get("experiments"):
            return found["experiments"][0]["experiment_id"]
        return self.request("/api/2.0/mlflow/experiments/create", {"name": name})["experiment_id"]

    def log(self, *, experiment: str, key: str, params: dict, metrics: dict,
            artifact: dict, tags: dict | None = None, parent: str | None = None,
            status: str = "FINISHED") -> str:
        experiment_id = self.experiment(experiment)
        # Keys are generated hashes, never interpolated candidate input.
        key = digest({"key": key})
        found = self.request("/api/2.0/mlflow/runs/search", {
            "experiment_ids": [experiment_id], "filter": f"tags.record_key = '{key}'", "max_results": 1000})
        if found.get("runs"):
            run = found["runs"][0]
            if run["info"]["status"] == "FINISHED" and status == "FINISHED":
                return run["info"]["run_id"]
        else:
            run_tags = {"record_key": key, "mlflow.runName": str(params.get("condition", experiment)), **(tags or {})}
            if parent:
                run_tags["mlflow.parentRunId"] = parent
            run = self.request("/api/2.0/mlflow/runs/create", {
                "experiment_id": experiment_id, "start_time": int(time.time() * 1000),
                "tags": [{"key": k, "value": str(v)} for k, v in run_tags.items()]})["run"]
        run_id = run["info"]["run_id"]
        numeric = {k: v for k, v in metrics.items()
                   if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)}
        self.request("/api/2.0/mlflow/runs/log-batch", {
            "run_id": run_id,
            "params": [{"key": k, "value": str(v)} for k, v in params.items() if v is not None],
            "metrics": [{"key": k, "value": v, "timestamp": int(time.time() * 1000), "step": 0}
                        for k, v in numeric.items()], "tags": []})
        uri = run["info"]["artifact_uri"]
        if not uri.startswith("mlflow-artifacts:/"):
            raise ValueError("Configure the local server with proxied local artifacts")
        artifact_path = uri.split(":", 1)[1].lstrip("/")
        self.request("/api/2.0/mlflow-artifacts/artifacts/" + quote(artifact_path + "/record.json", safe="/"),
                     raw=json.dumps(artifact, ensure_ascii=False, allow_nan=False).encode(), method="PUT")
        self.request("/api/2.0/mlflow/runs/update", {
            "run_id": run_id, "status": status, **({"end_time": int(time.time() * 1000)} if status != "RUNNING" else {})})
        return run_id

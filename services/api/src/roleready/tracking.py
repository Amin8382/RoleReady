"""Explicit MLflow runs. Never log CVs, audio, transcripts or provider error bodies."""

import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from roleready.paths import ROOT, write_json


def code_identity() -> dict[str, str]:
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT))
        return {"git_commit": sha, "working_tree_dirty": str(dirty).lower()}
    except (OSError, subprocess.SubprocessError):
        return {"git_commit": "unknown", "working_tree_dirty": "unknown"}


def tracking_uri() -> str:
    (ROOT / ".state").mkdir(exist_ok=True)
    return os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///" + str(ROOT / ".state/mlflow.db"))


class Run:
    def __init__(self, client: MlflowClient, run_id: str):
        self.client, self.id = client, run_id
        self.values: dict[str, float] = {}

    def metrics(self, values: dict[str, float]) -> None:
        for key, value in values.items():
            self.client.log_metric(self.id, key, float(value))
            self.values[key] = float(value)

    def artifact(self, path: Path) -> None:
        self.client.log_artifact(self.id, str(path))


@contextmanager
def experiment(name: str, params: dict[str, object], *, export: bool = True):
    uri = tracking_uri()
    client = MlflowClient(tracking_uri=uri)
    experiment_name = os.environ.get("MLFLOW_EXPERIMENT_NAME", "roleready")
    exp = client.get_experiment_by_name(experiment_name)
    if exp is None:
        kwargs = {}
        if uri.startswith("sqlite:"):
            kwargs["artifact_location"] = (ROOT / ".state/mlflow-artifacts").as_uri()
        try:
            experiment_id = client.create_experiment(experiment_name, **kwargs)
        except MlflowException:
            exp = client.get_experiment_by_name(experiment_name)
            if exp is None:
                raise
            experiment_id = exp.experiment_id
    else:
        experiment_id = exp.experiment_id
    identity = code_identity()
    item = client.create_run(experiment_id, tags={"mlflow.runName": name, **identity})
    run = Run(client, item.info.run_id)
    started = time.perf_counter()
    status = "FAILED"
    try:
        for key, value in params.items():
            client.log_param(run.id, key, str(value))
        yield run
        status = "FINISHED"
    except Exception as exc:
        client.set_tag(run.id, "failure_type", type(exc).__name__)
        raise
    finally:
        run.metrics({"duration_seconds": time.perf_counter() - started})
        client.set_terminated(run.id, status=status)
        if export:
            write_json(
                ROOT / "reports/experiments" / f"{name}-{run.id}.json",
                {
                    "run_id": run.id,
                    "name": name,
                    "status": status,
                    **identity,
                    "params": params,
                    "metrics": run.values,
                },
            )

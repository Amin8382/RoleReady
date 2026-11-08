"""DagsHub uses the ordinary MLflow protocol; no credentials are committed."""

import os
from urllib.parse import urlparse


def check_dagshub() -> dict:
    from mlflow import MlflowClient

    uri = os.environ.get("MLFLOW_TRACKING_URI", "")
    if urlparse(uri).hostname != "dagshub.com":
        return {
            "connected": False,
            "reason": "Set MLFLOW_TRACKING_URI to the repository's DagsHub MLflow URL.",
        }
    if not os.environ.get("MLFLOW_TRACKING_USERNAME") or not os.environ.get("MLFLOW_TRACKING_PASSWORD"):
        return {"connected": False, "reason": "DagsHub MLflow credentials are not configured."}
    client = MlflowClient(tracking_uri=uri)
    client.search_experiments(max_results=1)
    return {"connected": True, "service": "DagsHub MLflow"}

"""Wait for teacher completion and snapshot the local synthetic pilot with DVC.

No remote, credentials, cloud upload, human approval or model training.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / "ai"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    args = parser.parse_args()
    dataset = args.dataset.resolve()
    if not dataset.is_relative_to(AI / "data/fine_tuning"):
        raise SystemExit("Dataset must stay inside the local fine-tuning data directory")
    while not (dataset / "completion.json").exists() or (dataset / "runner.lock").exists():
        time.sleep(10)
    env = {**os.environ, "DVC_NO_ANALYTICS": "true", "DVC_SITE_CACHE_DIR": str(AI / ".runtime/dvc-site-cache"),
           "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory", "GIT_CONFIG_VALUE_0": ROOT.as_posix()}
    dvc = AI / ".runtime/dvc-env/Scripts/dvc.exe"
    subprocess.run([str(dvc), "add", str(dataset)], cwd=ROOT, env=env, check=True)
    pointer = dataset.with_suffix(".dvc")
    result = {"dataset": str(dataset), "pointer": str(pointer),
              "pointer_sha256": sha256(pointer.read_bytes()).hexdigest(), "remote_upload": False,
              "review_status": "pending", "ready_for_training": False}
    output = AI / ".runtime/training-data/dvc-snapshot.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

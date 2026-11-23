"""Supervise an existing batch; export final unjudged review forms locally.

No freeze changes, human approvals, or replacement of completed results.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

import psutil

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / "ai"
PYTHON = AI / ".venv311/Scripts/python.exe"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--review-out", type=Path, required=True)
    args = parser.parse_args()
    experiment = args.experiment.resolve()
    review_out = args.review_out.resolve()
    if not experiment.is_relative_to(AI / "outputs/ablation") or not review_out.is_relative_to(AI / "data/private"):
        raise SystemExit("Destinations must stay in ignored project output/private directories")
    read = lambda p: json.loads(p.read_text(encoding="utf-8"))
    env = {**os.environ, "HF_HOME": str(AI / ".runtime/huggingface"),
           "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"}
    own_child = None
    while True:
        lock = experiment / "runner.lock"
        report_path = experiment / "summary.json"
        report = read(report_path) if report_path.exists() else {}
        if report.get("completed_sets") == 288 and not lock.exists():
            break
        if lock.exists():
            state = read(lock)
            try:
                process = psutil.Process(state["pid"])
                if "roleready_ai.ablation" not in process.cmdline():
                    raise SystemExit("Runner PID was reused; manual inspection required")
                time.sleep(10)
                continue
            except psutil.NoSuchProcess:
                if read(lock)["pid"] != state["pid"]:
                    raise SystemExit("Runner lock changed during inspection")
                lock.unlink()
        if own_child is not None and own_child.poll() is not None and own_child.returncode != 0:
            raise SystemExit("Supervised runner failed; inspect continuation.log")
        with (experiment / "continuation.log").open("ab") as log:
            own_child = subprocess.Popen([str(PYTHON), "-u", "-m", "roleready_ai.ablation", "resume",
                "--manifest", str(experiment / "freeze.json"), "--out", str(experiment)], cwd=AI,
                env=env, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        time.sleep(10)
    def invoke(*arguments):
        completed = subprocess.run([str(PYTHON), "-m", *arguments], cwd=AI, env=env,
                                   text=True, capture_output=True, check=True)
        return json.loads(completed.stdout)
    synced = invoke("roleready_ai.ablation", "sync", "--out", str(experiment))
    exported = invoke("roleready_ai.question_review", "export", "--experiment", str(experiment), "--out", str(review_out))
    analyzed = invoke("roleready_ai.question_review", "analyze", "--bundle", str(review_out),
                      "--out", str(experiment / "pending-human-analysis.json"),
                      "--tracking-uri", "http://127.0.0.1:5000")
    receipt = {"summary": read(experiment / "summary.json"), "tracking": synced,
               "review_export": exported, "review_directory": str(review_out),
               "quality_metrics": analyzed["quality_metrics"], "paired_analysis": analyzed["paired_analysis"]}
    with (experiment / "completion.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
    print(json.dumps({"completed_sets": receipt["summary"]["completed_sets"],
                      "quality_metrics": None, "review_directory": str(review_out)}, indent=2))


if __name__ == "__main__":
    main()

"""Start/stop/backup only this checkout's loopback MLflow server."""
from pathlib import Path
import argparse
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "ai/.runtime/mlflow"
PID = STATE / "server.json"


def health():
    with urlopen("http://127.0.0.1:5000/health", timeout=2) as response:
        return response.read().decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start", "health", "stop", "backup"])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    if args.command == "start":
        if PID.exists():
            raise SystemExit("Server state exists; inspect health/PID before starting another process")
        try:
            health()
        except OSError:
            pass
        else:
            raise SystemExit("Port 5000 is already serving a process; do not replace it")
        command = [sys.executable, "-m", "mlflow", "server", "--host", "127.0.0.1", "--port", "5000",
                   "--backend-store-uri", "sqlite:///" + (STATE / "mlflow.db").as_posix(),
                   "--artifacts-destination", str(STATE / "artifacts"), "--workers", "1"]
        env = {**os.environ, "DO_NOT_TRACK": "true", "MLFLOW_DISABLE_AGENT_HINT": "1",
               "MLFLOW_ENABLE_SYSTEM_METRICS_LOGGING": "false"}
        with (STATE / "server.log").open("ab") as log:
            process = subprocess.Popen(command, cwd=STATE, env=env, stdout=log, stderr=log,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        PID.write_text(json.dumps({"pid": process.pid, "command": command, "started": time.time()}))
        for _ in range(60):
            if process.poll() is not None:
                raise SystemExit("MLflow exited; inspect .runtime/mlflow/server.log")
            try:
                print(health())
                return
            except OSError:
                time.sleep(.5)
        raise SystemExit("Server startup timed out; inspect recorded PID/log, do not start another server")
    elif args.command == "health":
        print(health())
    elif args.command == "stop":
        data = json.loads(PID.read_text())
        # psutil is an MLflow dependency, used here only in the isolated server env.
        import psutil
        process = psutil.Process(data["pid"])
        actual = process.cmdline()
        if actual != data["command"] or process.create_time() < data["started"] - 10:
            raise SystemExit("PID identity changed; refusing to stop an unrelated process")
        children = process.children(recursive=True)
        for child in reversed(children):
            child.terminate()
        process.terminate()
        psutil.wait_procs(children + [process], timeout=10)
        PID.unlink()
    else:
        if args.out is None or args.out.exists():
            raise SystemExit("Backup requires a new --out directory")
        if list((ROOT / "ai/outputs/ablation").glob("*/runner.lock")):
            raise SystemExit("Pause experiment execution before creating a consistent artifact backup")
        args.out.mkdir(parents=True)
        with sqlite3.connect(STATE / "mlflow.db") as source, sqlite3.connect(args.out / "mlflow.db") as target:
            source.backup(target)
        shutil.copytree(STATE / "artifacts", args.out / "artifacts")
        print(args.out)


if __name__ == "__main__":
    main()

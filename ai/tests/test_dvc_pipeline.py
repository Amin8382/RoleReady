"""Actual DVC smoke test in a disposable Git repository, using authored data only."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from hashlib import sha256

import pytest

from roleready_ai.acquisition import file_sha256

DVC = os.environ.get("DVC_BIN") or shutil.which("dvc")


@pytest.mark.skipif(not DVC, reason="Set DVC_BIN or install isolated requirements-data-tools.txt; no implicit tool installation")
def test_dvc_repro_is_deterministic_and_detects_changed_raw_snapshot(source_fixture):
    f = source_fixture
    f.add([f.row()])
    env = {**os.environ, "DVC_NO_ANALYTICS": "true"}
    # Module code remains the installed project; all data/Git/DVC writes are scoped to tmp_path.
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    def invoke(args, success=True):
        result = subprocess.run(args, cwd=f.tmp, env=env, text=True, capture_output=True, timeout=120)
        if success:
            assert result.returncode == 0, result.stdout + result.stderr
        return result
    invoke(["git", "init", "-q"])
    invoke([DVC, "init", "-q"])
    # DVC run-cache filenames are long. Keep the disposable test cache short on
    # Windows instead of changing the machine's long-path/security settings.
    cache = f.tmp.parent / ("c" + sha256(str(f.tmp).encode()).hexdigest()[:6])
    invoke([DVC, "config", "cache.dir", str(cache)])
    arguments = [sys.executable, "-m", "roleready_ai.corpus", "--registry", "sources.json",
                 "--raw", "raw", "--out", "processed"]
    command = subprocess.list2cmdline(arguments) if os.name == "nt" else shlex.join(arguments)
    (f.tmp / "dvc.yaml").write_text(json.dumps({"stages": {"prepare": {
        "cmd": command, "deps": ["sources.json", "raw"], "outs": ["processed"]}}}), encoding="utf-8")
    invoke([DVC, "repro"])
    first = {p.name: file_sha256(p) for p in (f.tmp / "processed").iterdir()}
    invoke([DVC, "repro", "--force"])
    assert first == {p.name: file_sha256(p) for p in (f.tmp / "processed").iterdir()}
    assert (f.tmp / "dvc.lock").is_file()
    assert json.loads(invoke([DVC, "status", "--json"]).stdout) == {}
    assert not invoke([DVC, "remote", "list"]).stdout.strip()
    source = next((f.tmp / "raw").glob("**/*.jsonl"))
    with source.open("ab") as stream:
        stream.write(b"\n")
    result = invoke([DVC, "repro"], success=False)
    assert result.returncode != 0 and "checksum mismatch" in result.stdout + result.stderr

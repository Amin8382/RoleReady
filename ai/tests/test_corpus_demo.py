import json

import pytest

from roleready_ai.corpus_demo import run, SCENARIOS


def test_generation_scenarios_are_separate_new_synthetic_evaluation_inputs():
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    old = json.loads((SCENARIOS.parents[1] / "mission002/scenarios.json").read_text(encoding="utf-8"))
    assert len(scenarios) == 3 and len({s["scenario_id"] for s in scenarios}) == 3
    assert all(s["purpose"] == "generation_evaluation" and s["cv_text"].startswith("Synthetic candidate:") for s in scenarios)
    assert not {s["cv_text"] for s in scenarios} & {s["cv_text"] for s in old}


@pytest.mark.parametrize("url", ["https://remote.example/v1", "http://127.0.0.1/api", "http://key:secret@localhost/v1"])
def test_corpus_demo_never_sends_synthetic_or_candidate_context_to_remote_endpoint(tmp_path, url):
    with pytest.raises(ValueError, match="local"):
        run(corpus=tmp_path / "absent", index=tmp_path, output=tmp_path / "out", base_url=url)


def test_corpus_demo_never_pulls_missing_model_or_overwrites_existing_runs(tmp_path, monkeypatch):
    calls = []
    def api(origin, path):
        calls.append(path)
        return {"models": []}
    monkeypatch.setattr("roleready_ai.corpus_demo.local_api", api)
    with pytest.raises(ValueError, match="never pulls"):
        run(corpus=tmp_path / "absent", index=tmp_path, output=tmp_path / "new")
    assert calls == ["/api/tags"]
    with pytest.raises(FileExistsError):
        run(corpus=tmp_path / "absent", index=tmp_path, output=tmp_path)

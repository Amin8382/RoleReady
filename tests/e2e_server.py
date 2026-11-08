"""Browser-test server only. Binds separately; fixtures are visibly synthetic."""

from pathlib import Path

from roleready.api import create_app
from roleready.settings import Settings
from tests.conftest import FixtureEngine, FixtureVoice

state = Path(".state/e2e")
bank = state / "data/processed/bank.jsonl"
bank.parent.mkdir(parents=True, exist_ok=True)
bank.touch()
settings = Settings(
    _env_file=None,
    data_root=state,
    state_dir=state,
    track_api_metrics=False,
    retriever="tfidf",
    generation_url="http://test-fixture.invalid/v1",
    evaluation_url="http://test-fixture.invalid/v1",
    voice_enabled=False,
)
app = create_app(settings=settings, engine=FixtureEngine(), voice=FixtureVoice())

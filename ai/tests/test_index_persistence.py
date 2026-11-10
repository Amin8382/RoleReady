"""Real FAISS I/O with a tiny deterministic encoder; never downloads weights."""
import json

import pytest

np = pytest.importorskip("numpy")
faiss = pytest.importorskip("faiss")

from roleready_ai.datasets import QuestionRecord
from roleready_ai.retrieval import BGEFaissRetriever


class Encoder:
    def __init__(self): self.calls = 0
    def encode(self, texts, **kwargs):
        self.calls += 1
        return np.array([[1.0 + text.lower().count("sql"), 1.0 + text.lower().count("api"), 0.5]
                         for text in texts], dtype="float32")


def build(tmp_path):
    encoder = Encoder()
    records = [QuestionRecord("sql", "How would you validate a SQL query?", "Data Engineer", "fixture", "train"),
               QuestionRecord("api", "How would you test an API endpoint?", "Backend Developer", "fixture", "train")]
    engine = BGEFaissRetriever(records, embedding_model=encoder, model_name="fixture-encoder",
                               model_revision="fixture-v1", corpus_sha256="a" * 64)
    engine.save(tmp_path)
    return engine, encoder


def test_load_preserves_vectors_mapping_and_never_reembeds(tmp_path):
    engine, encoder = build(tmp_path)
    count = encoder.calls
    loaded = BGEFaissRetriever.load(tmp_path, embedding_model=encoder,
                                    expected_corpus_sha256="a" * 64, expected_model_revision="fixture-v1")
    assert encoder.calls == count
    assert loaded.index.ntotal == 2 and loaded.index.d == 3
    assert np.allclose(np.linalg.norm(loaded.index.reconstruct_n(0, 2), axis=1), 1.0)
    before = engine.search(query="SQL query", role="Data Engineer")
    after = loaded.search(query="SQL query", role="Data Engineer")
    assert [(h.record.record_id, h.record.question) for h in before] == [(h.record.record_id, h.record.question) for h in after]


@pytest.mark.parametrize("field,value,error", [
    ("corpus_sha256", "b" * 64, "Corpus revision"),
    ("model_revision", "wrong", "model revision"),
    ("vector_id_sha256", "wrong", "mapping checksum"),
    ("taxonomy_version", "wrong", "taxonomy revision"),
    ("dimension", 17, "dimensions"),
])
def test_version_and_mapping_mismatches_fail_before_querying(tmp_path, field, value, error):
    _, encoder = build(tmp_path)
    path = tmp_path / "questions.meta.json"
    metadata = json.loads(path.read_text())
    metadata[field] = value
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match=error):
        BGEFaissRetriever.load(tmp_path, embedding_model=encoder,
                              expected_corpus_sha256="a" * 64, expected_model_revision="fixture-v1")


def test_corrupted_index_is_rejected_before_binary_loading(tmp_path):
    _, encoder = build(tmp_path)
    with (tmp_path / "questions.faiss").open("ab") as stream: stream.write(b"corrupt")
    with pytest.raises(ValueError, match="index checksum"):
        BGEFaissRetriever.load(tmp_path, embedding_model=encoder)


def test_changed_record_text_is_rejected(tmp_path):
    _, encoder = build(tmp_path)
    path = tmp_path / "questions.meta.json"
    metadata = json.loads(path.read_text())
    metadata["records"][0]["question"] = "An unrelated question"
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="record metadata checksum"):
        BGEFaissRetriever.load(tmp_path, embedding_model=encoder)


def test_nonfinite_embeddings_are_rejected(tmp_path):
    class Invalid:
        def encode(self, texts, **kwargs): return np.full((len(texts), 3), np.nan, dtype="float32")
    with pytest.raises(ValueError, match="finite"):
        BGEFaissRetriever([QuestionRecord("x", "Explain SQL joins?", "Data Engineer", "test", "train")],
                          embedding_model=Invalid(), model_name="fixture-encoder")

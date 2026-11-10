import json

import pytest

from roleready_ai.corpus import prepare_corpus
from roleready_ai.retrieval import LexicalRetriever, BGE_REVISION
from roleready_ai.run import run

TEXTS = ["How would you validate missing rows in a sales report?",
         "How would you choose a SQL aggregation for a business metric?",
         "How would you explain uncertainty to a nontechnical audience?",
         "How would you test a transformation before releasing it?",
         "How would you prioritize an ambiguous reporting request?",
         "How would you prevent double counting in joins?",
         "How would you learn an unfamiliar reporting tool?"]


def setup(f, monkeypatch):
    f.add([f.row()])
    prepare_corpus(registry_path=f.registry, raw=f.raw, output=f.tmp / "processed")
    session = f.tmp / "session.json"
    session.write_text(json.dumps({"target_role": "Data Analyst", "experience_level": "junior",
                                  "cv_text": "Synthetic candidate: I built a dashboard with Python and SQL.",
                                  "job_description": "The role requires SQL joins and validation for clear reports."}))
    prompts = []
    class Model:
        model = "synthetic-test-only"
        last_response = {"finish_reason": "stop"}
        def __init__(self, **kwargs): pass
        def complete_json(self, *, system, user):
            context = json.loads(user[user.index("{"):])
            prompts.append(context)
            ids = context["retrieved_source_ids"][:1]
            return {"questions": [{"text": text, "target_skill": "analysis", "difficulty": "medium",
                                   "reason_for_asking": "CV: [Python and SQL]; Job: [SQL joins]. Practice the job requirement using documented CV context; missing ability is not inferred.",
                                   "reference_criteria": ["The answer should describe a proposed validation method."], "source_ids": ids}
                                  for text in TEXTS]}
    monkeypatch.setattr("roleready_ai.run.OpenAICompatibleQwen", Model)
    return session, f.tmp / "processed/corpus.jsonl", prompts


def test_public_cli_loads_explicit_corpus_and_passes_real_source_text(source_fixture, monkeypatch):
    f = source_fixture
    session, bank, prompts = setup(f, monkeypatch)
    result = run(input_file=session, question_bank=bank, output_file=f.tmp / "result.json", bank_format="corpus")
    assert len(result["questions"]) == 7 and result["bank_format"] == "corpus"
    assert prompts[0]["retrieved_sources"][0]["question"] == f.row()["question"]
    assert prompts[0]["retrieved_sources"][0]["purpose"] == "retrieval_corpus"


def test_no_retrieval_comparison_supplies_no_corpus_examples(source_fixture, monkeypatch):
    f = source_fixture
    session, bank, prompts = setup(f, monkeypatch)
    result = run(input_file=session, question_bank=bank, output_file=f.tmp / "result.json",
                 bank_format="corpus", retrieval_mode="none")
    assert result["generation_mode"] == "qwen_no_retrieval"
    assert prompts[0]["retrieved_sources"] == [] and not result["retrieved_source_ids"]


def test_persisted_index_cli_checks_corpus_and_model_version_without_rebuilding(source_fixture, monkeypatch):
    from roleready_ai.corpus import load_corpus
    from roleready_ai.acquisition import file_sha256
    f = source_fixture
    session, bank, _ = setup(f, monkeypatch)
    calls = []
    class Persisted:
        def __init__(self, *args, **kwargs): raise AssertionError("Do not rebuild an existing index")
        @classmethod
        def load(cls, path, **kwargs):
            calls.append((path, kwargs))
            return LexicalRetriever(load_corpus(bank))
    monkeypatch.setattr("roleready_ai.run.BGEFaissRetriever", Persisted)
    result = run(input_file=session, question_bank=bank, output_file=f.tmp / "result.json",
                 bank_format="corpus", retrieval_mode="bge-faiss", index_path=f.tmp / "index")
    assert len(result["questions"]) == 7
    assert calls[0][1] == {"expected_corpus_sha256": file_sha256(bank), "expected_model_revision": BGE_REVISION}

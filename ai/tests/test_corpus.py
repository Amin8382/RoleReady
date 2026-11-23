from dataclasses import asdict, replace
from hashlib import sha256
import json

import pytest

from roleready_ai.corpus import CorpusRecord, clean_text, duplicate_key, load_corpus, prepare_corpus, stable_id
from roleready_ai.retrieval import LexicalRetriever
from roleready_ai.taxonomy import canonical_roles, search_compatible
from roleready_ai.datasets import load_jsonl


def prepare(f, out="processed"):
    return prepare_corpus(registry_path=f.registry, raw=f.raw, output=f.tmp / out)


def test_unicode_whitespace_and_code_punctuation_are_preserved():
    assert clean_text("  ＳＱＬ\t joins \n test  ") == "SQL joins test"
    assert duplicate_key("What is C++?") != duplicate_key("What is C?")
    assert stable_id("WHAT is SQL? ") == stable_id("What is SQL!")
    assert "\n    return" in clean_text("```python\ndef f():\n    return 1\n```")


def test_exact_duplicates_merge_roles_and_every_source_occurrence(source_fixture):
    f = source_fixture
    f.add([f.row(), f.row("  HOW would you validate a SQL join with duplicate customer keys!", role="Data Engineer")])
    f.add([f.row()], source_id="second-source")
    manifest = prepare(f)
    records = load_corpus(f.tmp / "processed/corpus.jsonl")
    assert len(records) == 1 and len(records[0].provenance) == 3
    assert set(records[0].roles) == {"Data Analyst", "Data Engineer"}
    assert sum(s["curation"]["exact_duplicate"] for s in manifest["sources"]) == 2
    assert {p["source_id"] for p in records[0].provenance} == {"fixture-0", "second-source"}


def test_processing_is_byte_deterministic_and_keeps_answers_separate(source_fixture):
    f = source_fixture
    f.add([f.row(answer="An unreviewed synthetic reference.")])
    a, b = prepare(f, "a"), prepare(f, "b")
    assert a == b
    assert {p.name: sha256(p.read_bytes()).hexdigest() for p in (f.tmp / "a").iterdir()} == {
        p.name: sha256(p.read_bytes()).hexdigest() for p in (f.tmp / "b").iterdir()}
    record = load_corpus(f.tmp / "a/corpus.jsonl")[0]
    assert record.reference_answer is None and record.reviewed is False
    assert "An unreviewed" not in (f.tmp / "a/corpus.jsonl").read_text()
    assert "An unreviewed" in (f.tmp / "a/references.unreviewed.jsonl").read_text()
    assert LexicalRetriever([record]).search(query="SQL", role="Data Analyst")[0].as_prompt_record()["reference_answer"] is None


def test_evaluation_and_quarantine_never_become_corpus_even_with_upstream_train_split(source_fixture):
    f = source_fixture
    f.add([f.row(), f.row("How would you plan a safe model registry rollout?", role="MLOps Engineer")])
    f.add([f.row(follow_up_questions=["How would you diagnose a serving failure?"])], usage="evaluation_only", source_id="bench")
    f.add([f.row("How would you implement an API?", role="Backend Developer")], usage="quarantine", source_id="uncertain")
    m = prepare(f)
    records = load_corpus(f.tmp / "processed/corpus.jsonl")
    assert len(records) == 1 and records[0].role == "MLOps Engineer"
    assert m["sources"][1]["curation"]["evaluation_overlap"] == 1  # fixture-0 follows bench alphabetically.
    assert all(p["source_id"] == "fixture-0" for p in records[0].provenance)


def test_invalid_rows_and_unknown_roles_are_counted_not_promoted_to_general(source_fixture):
    f = source_fixture
    f.add([f.row(), f.row("No"), f.row(role="Unknown futuristic title"),
           {"role": "Data Analyst"}, ["not an object"]])
    m = prepare(f)
    c = m["sources"][0]["curation"]
    assert c["invalid"] == 3 and c["out_of_scope"] == 1 and c["retained_unique_primary"] == 1


def test_unknown_metadata_is_explicit_not_invented(source_fixture):
    f = source_fixture
    f.add([f.row(question_category=None, question_level="unmapped", keywords="unknown")])
    prepare(f)
    record = load_corpus(f.tmp / "processed/corpus.jsonl")[0]
    assert record.topic is None and record.difficulty is None and record.question_type is None
    assert not record.competencies


def test_unapproved_retrieval_source_fails_closed(source_fixture):
    f = source_fixture
    f.add([f.row()], license_verified=False)
    with pytest.raises(ValueError, match="license"):
        prepare(f)


def test_corpus_is_not_an_sft_training_partition_and_purpose_checks_are_enforced(source_fixture):
    f = source_fixture
    f.add([f.row()])
    prepare(f)
    record = load_corpus(f.tmp / "processed/corpus.jsonl")[0]
    assert record.split == "corpus" and "split" not in asdict(record)
    for purpose in ("evaluation_only", "quarantine"):
        with pytest.raises(ValueError, match="evaluation-only"):
            LexicalRetriever([replace(record, purpose=purpose)])
    value = json.loads(json.dumps(asdict(record)))
    value["provenance"][0]["usage"] = "evaluation_only"
    with pytest.raises(ValueError, match="cannot enter retrieval"):
        CorpusRecord.from_dict(value)


@pytest.mark.parametrize("label,expected", [("AI/ML Engineer", ("Machine Learning Engineer", "AI Engineer")),
                                            ("ML Engineer", ("Machine Learning Engineer",)),
                                            ("QA Automation Engineer", ("Test Automation Engineer",)),
                                            ("Unknown", ())])
def test_role_mapping_is_explicit(label, expected):
    assert canonical_roles(label) == expected


def test_search_families_do_not_relabel_source_documents():
    assert search_compatible("Junior Software Engineer", "Backend Developer")
    assert search_compatible("AI Engineer", "Computer Vision Engineer")
    assert not search_compatible("Data Analyst", "Backend Developer")


def test_explicit_evaluation_rows_are_rejected_even_inside_an_eligible_source(source_fixture):
    f = source_fixture
    f.add([f.row(), f.row("How would you choose a model threshold?", purpose="generation_evaluation")])
    m = prepare(f)
    assert m["retained_records"] == 1 and m["sources"][0]["curation"]["excluded_usage"] == 1


def test_corpus_cannot_silently_enter_legacy_sft_loader(source_fixture):
    f = source_fixture
    f.add([f.row()])
    prepare(f)
    with pytest.raises(ValueError, match="not an SFT"):
        load_jsonl(f.tmp / "processed/corpus.jsonl", split="train")

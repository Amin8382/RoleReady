from copy import deepcopy
import math

import pytest

from roleready_ai.retrieval_evaluation import retrieval_metrics, reviewed_metrics, import_human_review
import csv


def test_ranked_metrics_with_graded_relevance_have_known_values():
    relevance = {"a": 3, "b": 2, "c": 1, "x": 0}
    actual = retrieval_metrics(["x", "a", "b", "c"], relevance)
    assert actual["precision_at_5"] == pytest.approx(3/5)
    assert actual["recall_at_5"] == actual["recall_at_10"] == 1
    assert actual["mrr_at_10"] == 0.5
    dcg = 7/math.log2(3) + 3/math.log2(4) + 1/math.log2(5)
    ideal = 7 + 3/math.log2(3) + 1/math.log2(4)
    assert actual["ndcg_at_10"] == pytest.approx(dcg/ideal)


def test_missing_results_count_as_nonrelevant_and_recall_has_assessed_denominator():
    actual = retrieval_metrics(["a"], {"a": 1, "b": 1})
    assert actual["precision_at_5"] == 0.2 and actual["recall_at_5"] == 0.5


def test_mrr_is_explicitly_truncated_at_rank_ten():
    actual = retrieval_metrics([str(i) for i in range(10)] + ["a"], {"a": 1})
    assert actual["mrr_at_10"] == actual["recall_at_10"] == 0


@pytest.mark.parametrize("ranking,relevance", [(["a", "a"], {"a": 1}), (["a"], {"a": True}),
                                             (["a"], {"a": 4}), (["a"], {"a": 0})])
def test_invalid_or_unassessed_metric_inputs_fail(ranking, relevance):
    with pytest.raises(ValueError): retrieval_metrics(ranking, relevance)


def evaluation_fixture():
    rankings = {"corpus_sha256": "a" * 64, "queries_sha256": "b" * 64,
                "corpus_record_ids": ["a", "b"], "queries": [{"query_id": "q1", "rankings": {
                    "lexical": [{"source_id": "a"}, {"source_id": "b"}],
                    "bge-faiss": [{"source_id": "b"}, {"source_id": "a"}]}}]}
    judgments = {"corpus_sha256": "a" * 64, "queries_sha256": "b" * 64,
                 "fully_reviewed_query_pools": ["q1"], "judgments": [
                     {"query_id": "q1", "record_id": "a", "relevance": 3,
                      "label_status": "human_reviewed", "reviewer": "synthetic-test-only", "reviewed_at": "2026-01-01"},
                     {"query_id": "q1", "record_id": "b", "relevance": 0,
                      "label_status": "human_reviewed", "reviewer": "synthetic-test-only", "reviewed_at": "2026-01-01"}]}
    return rankings, judgments


def test_reviewed_fixture_metrics_require_complete_pools_and_explicit_review_metadata():
    ranks, labels = evaluation_fixture()
    report = reviewed_metrics(ranks, labels)
    assert report["reviewed_query_count"] == 1
    assert report["official_metrics"]["lexical"]["mrr_at_10"] == 1
    assert report["official_metrics"]["bge-faiss"]["mrr_at_10"] == 0.5


@pytest.mark.parametrize("mutation", ["provisional", "missing_reviewer", "partial_pool", "unapproved_pool"])
def test_ai_suggestions_and_partial_labels_never_become_official_ground_truth(mutation):
    ranks, labels = evaluation_fixture()
    if mutation == "provisional": labels["judgments"][0]["label_status"] = "agent_provisional"
    elif mutation == "missing_reviewer": labels["judgments"][0]["reviewer"] = None
    elif mutation == "partial_pool": labels["judgments"].pop()
    else: labels["fully_reviewed_query_pools"] = []
    report = reviewed_metrics(ranks, labels)
    assert report["official_metrics"] is None and report["status"] == "human_review_required"


@pytest.mark.parametrize("mutation", ["corpus_revision", "queries_revision", "outside_corpus", "duplicate", "bad_grade"])
def test_relevance_provenance_mismatches_are_not_silently_accepted(mutation):
    ranks, labels = evaluation_fixture()
    if mutation == "corpus_revision": labels["corpus_sha256"] = "c" * 64
    elif mutation == "queries_revision": labels["queries_sha256"] = "c" * 64
    elif mutation == "outside_corpus": labels["judgments"][0]["record_id"] = "invented"
    elif mutation == "duplicate": labels["judgments"].append(deepcopy(labels["judgments"][0]))
    else: labels["judgments"][0]["relevance"] = 99
    with pytest.raises(ValueError): reviewed_metrics(ranks, labels)


def review_csv(tmp_path, rows):
    path = tmp_path / "review.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["query_id", "record_id", "relevance", "label_status", "reviewer", "reviewed_at", "rationale"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_csv_review_import_requires_every_pool_row_to_be_explicitly_approved(tmp_path):
    _, pool = evaluation_fixture()
    rows = deepcopy(pool["judgments"])
    for row in pool["judgments"]:
        row.update(relevance=None, label_status="unjudged", reviewer=None, reviewed_at=None)
    path = review_csv(tmp_path, rows)
    approved = import_human_review(pool, path)
    assert approved["fully_reviewed_query_pools"] == ["q1"]
    rows[1]["label_status"] = "agent_provisional"
    assert import_human_review(pool, review_csv(tmp_path, rows))["fully_reviewed_query_pools"] == []


@pytest.mark.parametrize("mutation", ["unknown_pair", "missing_reviewer", "invalid_grade"])
def test_bad_csv_approval_is_not_accepted(tmp_path, mutation):
    _, pool = evaluation_fixture()
    rows = deepcopy(pool["judgments"])
    if mutation == "unknown_pair": rows[0]["record_id"] = "invented"
    elif mutation == "missing_reviewer": rows[0]["reviewer"] = ""
    else: rows[0]["relevance"] = 7
    with pytest.raises(ValueError): import_human_review(pool, review_csv(tmp_path, rows))

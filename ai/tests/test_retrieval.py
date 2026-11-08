import pytest
from roleready_ai.datasets import QuestionRecord
from roleready_ai.retrieval import LexicalRetriever, compatible_role


def record(id: str, question: str, role: str, split: str = "train") -> QuestionRecord:
    return QuestionRecord(record_id=id, question=question, role=role, source_id="sample", split=split)


def test_lexical_search_is_role_aware():
    retriever = LexicalRetriever([
        record("sql", "Explain a SQL optimization problem you solved.", "Data Engineer"),
        record("ui", "Explain a complex React user interface you built.", "Frontend Engineer"),
        record("team", "How do you collaborate under pressure?", "general"),
    ])
    result = retriever.search(query="SQL pipeline query optimization", role="Data Engineer", k=2)
    assert result[0].record.record_id == "sql"
    assert "ui" not in [hit.record.record_id for hit in result]
    assert compatible_role("Data Engineer", "general")


def test_holdout_documents_cannot_be_indexed():
    with pytest.raises(ValueError, match="validation/test"):
        LexicalRetriever([record("leak", "Describe the pipeline?", "Data Engineer", "test")])


def test_unreviewed_reference_answer_is_not_passed_to_llm():
    r = QuestionRecord("x", "How would you use Python in production?", "ML Engineer", "sample", "train", "Private reference", reviewed=False)
    result = LexicalRetriever([r]).search(query="Python", role="ML Engineer")
    assert result[0].as_prompt_record()["reference_answer"] is None

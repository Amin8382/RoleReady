"""Network-free endpoint and generation regressions; no model downloads."""
from copy import deepcopy
from io import BytesIO
import json
from urllib.error import HTTPError

import pytest

from roleready_ai.generation import SYSTEM_PROMPT, QUESTION_RESPONSE_SCHEMA, generate_questions, validate_questions, validate_evidence, evidence_excerpts, question_response_schema
import re
from roleready_ai.model import InvalidModelResponse, ModelUnavailable, OpenAICompatibleQwen, strict_json
from roleready_ai.datasets import QuestionRecord
from roleready_ai.retrieval import LexicalRetriever

TEXTS = [
    "How would you validate data quality in a sales CSV?",
    "How would you choose between SQL joins and a pandas merge?",
    "How would you communicate an uncertain dashboard result?",
    "What would you test to catch errors in an aggregation function?",
    "How would you resolve a disagreement about project priorities?",
    "What would you investigate if a database query became slow?",
    "How would you learn an unfamiliar reporting tool for this role?",
]


def payload():
    return {"questions": [{
        "text": text, "target_skill": "analytics", "difficulty": "medium",
        "reason_for_asking": "CV: [sales dashboard]; Job: [SQL joins]. Practice the job requirement using documented CV context; missing ability is not inferred.",
        "reference_criteria": ["The answer should describe a concrete approach.", "The answer should explain tradeoffs."], "source_ids": ["train-sql"],
    } for text in TEXTS]}


def envelope(content, **changes):
    result = {"model": "local-qwen", "choices": [{"finish_reason": "stop", "message": {"content": content}}]}
    result.update(changes)
    return result


def mock_response(monkeypatch, value, captured=None):
    def open_response(request, timeout):
        if captured is not None:
            captured.append(json.loads(request.data))
        return BytesIO(json.dumps(value).encode())
    monkeypatch.setattr("roleready_ai.model.urlopen", open_response)


def test_openai_schema_and_non_thinking_are_explicit(monkeypatch):
    requests = []
    mock_response(monkeypatch, envelope(json.dumps(payload())), requests)
    model = OpenAICompatibleQwen(base_url="http://127.0.0.1:11434/v1", model="local-qwen",
                                response_schema=QUESTION_RESPONSE_SCHEMA, reasoning_effort="none")
    result = model.complete_json(system="JSON only", user="Synthetic data")
    assert len(result["questions"]) == 7
    assert requests[0]["reasoning_effort"] == "none"
    assert requests[0]["response_format"]["json_schema"]["schema"]["properties"]["questions"]["maxItems"] == 7
    assert model.last_response["finish_reason"] == "stop"


@pytest.mark.parametrize("content", ['{"ok":true,"ok":false}', '{"score":NaN}', '```json\n{"ok":true}\n```', '[]', '<think>reasoning</think>{"ok":true}'])
def test_invalid_json_is_not_repaired_or_silently_accepted(monkeypatch, content):
    mock_response(monkeypatch, envelope(content))
    with pytest.raises(InvalidModelResponse):
        OpenAICompatibleQwen(base_url="http://localhost/v1", model="local-qwen").complete_json(system="", user="")


@pytest.mark.parametrize("value", [
    envelope('{"ok":true}', model="wrong-model"),
    {"model": "local-qwen", "choices": [{"finish_reason": "length", "message": {"content": '{"ok":true}'}}]},
    {"model": "local-qwen", "choices": []},
    {"model": "local-qwen", "choices": [{"finish_reason": "stop", "message": {"content": None, "reasoning": "only thinking"}}]},
])
def test_incomplete_or_wrong_identity_is_rejected(monkeypatch, value):
    mock_response(monkeypatch, value)
    with pytest.raises(InvalidModelResponse):
        OpenAICompatibleQwen(base_url="http://localhost/v1", model="local-qwen").complete_json(system="", user="")


@pytest.mark.parametrize("url", ["http://example.org/v1", "https://key:secret@example.org/v1", "https://example.org/v1?key=secret", "https://example.org/v1#secret"])
def test_endpoint_privacy_validation(url):
    with pytest.raises(ModelUnavailable):
        OpenAICompatibleQwen(base_url=url)


def test_http_error_does_not_silently_disable_schema(monkeypatch):
    calls = []
    def fail(request, timeout):
        calls.append(request)
        raise HTTPError(request.full_url, 400, "Unsupported schema", {}, None)
    monkeypatch.setattr("roleready_ai.model.urlopen", fail)
    with pytest.raises(ModelUnavailable):
        OpenAICompatibleQwen(base_url="http://localhost/v1", response_schema=QUESTION_RESPONSE_SCHEMA).complete_json(system="", user="")
    assert len(calls) == 1


@pytest.mark.parametrize("count", [0, 6, 8])
def test_exactly_seven_required(count):
    data = payload()
    data["questions"] = (data["questions"] * 2)[:count]
    with pytest.raises(ValueError, match="exactly seven"):
        validate_questions(data, allowed_source_ids={"train-sql"})


@pytest.mark.parametrize("mutation", ["extra_root", "extra_question", "missing_field", "wrong_type", "repeated_source", "unknown_source", "numbered_duplicate"])
def test_structural_and_citation_regressions(mutation):
    data = payload()
    first = data["questions"][0]
    if mutation == "extra_root": data["analysis"] = "unexpected"
    elif mutation == "extra_question": first["cv_fact"] = "invented"
    elif mutation == "missing_field": del first["difficulty"]
    elif mutation == "wrong_type": first["reference_criteria"] = "not an array"
    elif mutation == "repeated_source": first["source_ids"] = ["train-sql", "train-sql"]
    elif mutation == "unknown_source": first["source_ids"] = ["invented"]
    else: data["questions"][1]["text"] = first["text"] + " 2!"
    with pytest.raises(ValueError):
        validate_questions(data, allowed_source_ids={"train-sql"})


class RecordingModel:
    model = "test-qwen"
    def __init__(self, results):
        self.results = iter(results)
        self.prompts = []
    def complete_json(self, *, system, user):
        self.prompts.append(user)
        return next(self.results)


def generate(model, **kwargs):
    return generate_questions(
        model=model, retriever=LexicalRetriever([
            QuestionRecord("train-sql", "Explain SQL aggregation and joins.", "Data Analyst", "synthetic", "train"),
        ]), cv_text="I built a small sales dashboard using Python, pandas and SQL.",
        job_description="A Data Analyst will use SQL joins, dashboards and careful data validation.",
        role="Junior Data Analyst", experience_level="junior", **kwargs,
    )


def test_bounded_retry_keeps_real_retrieved_text_and_ids():
    bad = deepcopy(payload())
    bad["questions"][0]["source_ids"] = ["invented"]
    model = RecordingModel([bad, payload()])
    result = generate(model)
    assert result.attempts == 2 and len(result.rejected_attempts) == 1
    assert len(result.questions) == 7
    assert all("Explain SQL aggregation and joins." in prompt and "train-sql" in prompt for prompt in model.prompts)
    assert "non-retrieved source" in model.prompts[1]


def test_retry_exhaustion_is_a_failure():
    model = RecordingModel([{"questions": []}] * 3)
    with pytest.raises(ValueError, match="rejected after 2 attempts"):
        generate(model)
    assert len(model.prompts) == 2


def test_no_unbounded_retries():
    with pytest.raises(ValueError, match="max_attempts"):
        generate(RecordingModel([]), max_attempts=4)


@pytest.mark.parametrize("claim", ["Why do you lack AWS experience?", "Explain your lack of cloud expertise.", "Since you have no deployment knowledge, what can you offer?"])
def test_missing_cv_evidence_is_not_a_missing_ability_claim(claim):
    data = payload()
    data["questions"][0]["text"] = claim
    with pytest.raises(ValueError, match="missing ability"):
        validate_questions(data, allowed_source_ids={"train-sql"})


def test_hypothetical_learning_question_is_allowed():
    data = payload()
    data["questions"][0]["text"] = "How would you learn dbt for this role?"
    data["questions"][0]["reason_for_asking"] = "dbt is a job requirement not evidenced by the CV."
    assert len(validate_questions(data, allowed_source_ids={"train-sql"})) == 7


@pytest.mark.parametrize("reason", [
    "CV: [deployed on AWS]; Job: [SQL joins]. Practice the job requirement using documented CV context; missing ability is not inferred.",
    "CV: [sales dashboard]; Job: [Kubernetes management]. Practice the job requirement using documented CV context; missing ability is not inferred.",
    "Related to the CV and job, but without traceable excerpts.",
    "CV: [sales dashboard]; CV: [sales dashboard]; Job: [SQL joins].",
])
def test_invented_or_missing_evidence_is_rejected(reason):
    data = payload()
    data["questions"][0]["reason_for_asking"] = reason
    questions = validate_questions(data, allowed_source_ids={"train-sql"})
    with pytest.raises(ValueError, match="evidence"):
        validate_evidence(questions, cv_text="A sales dashboard using Python.", job_description="The job requires SQL joins and careful reporting.")


def test_input_derived_grammar_cannot_invent_or_combine_evidence_or_citations():
    cv = "I cleaned sales rows, investigated missing values and queried SQLite."
    job = "The role requires SQL joins, dashboard validation and communication."
    cv_options, job_options = evidence_excerpts(cv), evidence_excerpts(job)
    assert all(value in cv and 8 <= len(value) <= 160 for value in cv_options)
    assert all(value in job and 8 <= len(value) <= 160 for value in job_options)
    schema = question_response_schema(cv_excerpts=cv_options, job_excerpts=job_options, source_ids={"train-sql"})
    properties = schema["properties"]["questions"]["items"]["properties"]
    pattern = properties["reason_for_asking"]["pattern"]
    assert re.fullmatch(pattern, f"CV: [{cv_options[0]}]; Job: [{job_options[0]}]. Practice the job requirement using documented CV context; missing ability is not inferred.")
    assert not re.fullmatch(pattern, f"CV: [I deployed on AWS]; Job: [{job_options[0]}]. Practice the job requirement using documented CV context; missing ability is not inferred.")
    assert properties["source_ids"]["items"]["enum"] == ["train-sql"]
    assert "pattern" in QUESTION_RESPONSE_SCHEMA["properties"]["questions"]["items"]["properties"]["text"]


def test_empty_retrieval_grammar_only_permits_empty_citations():
    schema = question_response_schema(cv_excerpts=["sales dashboard"], job_excerpts=["SQL joins"], source_ids=set())
    assert schema["properties"]["questions"]["items"]["properties"]["source_ids"]["maxItems"] == 0


def test_evidence_excerpts_are_bounded_even_for_long_inputs():
    text = ("a literal clause for this candidate, " * 100) + ("word " * 500)
    result = evidence_excerpts(text)
    assert len(result) <= 24
    assert all(value in text and 8 <= len(value) <= 160 for value in result)


def test_first_person_cv_preface_is_not_an_interviewer_question():
    data = payload()
    data["questions"][0]["text"] = "I documented the metric definitions. How would you explain them?"
    with pytest.raises(ValueError, match="interviewer"):
        validate_questions(data, allowed_source_ids={"train-sql"})


def test_reference_criteria_cannot_assume_a_skill_gap():
    data = payload()
    data["questions"][0]["reference_criteria"] = ["Demonstrates self-awareness regarding skill gaps"]
    with pytest.raises(ValueError, match="missing ability"):
        validate_questions(data, allowed_source_ids={"train-sql"})


def test_rationale_does_not_add_unverified_claims_after_valid_evidence():
    data = payload()
    data["questions"][0]["reason_for_asking"] = "CV: [sales dashboard]; Job: [SQL joins]. The candidate has proven large-scale experience."
    questions = validate_questions(data, allowed_source_ids={"train-sql"})
    with pytest.raises(ValueError, match="evidence"):
        validate_evidence(questions, cv_text="A sales dashboard using Python.", job_description="The job requires SQL joins and careful reporting.")


def test_hypothetical_incident_is_not_presented_as_documented_history():
    data = payload()
    data["questions"][0]["text"] = "How would you optimize a slow query found during your university project?"
    with pytest.raises(ValueError, match="hypothetical"):
        validate_questions(data, allowed_source_ids={"train-sql"})


def test_reference_criteria_do_not_assume_undocumented_past_actions():
    data = payload()
    data["questions"][0]["reference_criteria"] = ["Describe how you handled temporal dependencies"]
    with pytest.raises(ValueError, match="prospective"):
        validate_questions(data, allowed_source_ids={"train-sql"})


def test_lack_of_experience_is_not_inferred_from_missing_cv_evidence():
    data = payload()
    data["questions"][0]["text"] = "How would you monitor drift, given the lack of production monitoring experience?"
    with pytest.raises(ValueError, match="not evidenced"):
        validate_questions(data, allowed_source_ids={"train-sql"})


@pytest.mark.parametrize("timeout", [0, 601])
def test_invalid_timeout_is_a_configuration_error(timeout):
    with pytest.raises(ValueError, match="timeout"):
        OpenAICompatibleQwen(base_url="http://localhost/v1", timeout=timeout)


@pytest.mark.parametrize("criterion", [
    "The answer should discuss signals beyond those tested in the course project.",
    "The answer should explain how you verified leakage in training.",
    "The answer should describe previously deployed monitors.",
])
def test_criteria_cannot_presume_candidate_history(criterion):
    data = payload()
    data["questions"][0]["reference_criteria"] = [criterion]
    with pytest.raises(ValueError, match="candidate-independent"):
        validate_questions(data, allowed_source_ids={"train-sql"})


def test_prospective_criteria_and_unfamiliar_tool_hypothetical_are_allowed():
    data = payload()
    data["questions"][0]["text"] = "How would you learn dbt if the tool is unfamiliar?"
    data["questions"][0]["reference_criteria"] = [
        "The answer should outline a small transformation exercise and a validation check."]
    assert len(validate_questions(data, allowed_source_ids={"train-sql"})) == 7


def test_without_prior_experience_is_not_inferred_from_undocumented_experience():
    data = payload()
    data["questions"][0]["text"] = "How would you learn dbt without prior professional experience?"
    with pytest.raises(ValueError, match="missing experience"):
        validate_questions(data, allowed_source_ids={"train-sql"})


def test_criteria_count_is_bounded_in_schema_and_validation():
    data = payload()
    data["questions"][0]["reference_criteria"] = [
        f"The answer should explain constraint {index}." for index in range(4)]
    with pytest.raises(ValueError, match="at most three"):
        validate_questions(data, allowed_source_ids={"train-sql"})
    assert QUESTION_RESPONSE_SCHEMA["properties"]["questions"]["items"]["properties"]["reference_criteria"]["maxItems"] == 3


@pytest.mark.parametrize("level", ["entry", "junior"])
def test_foundational_practice_difficulty_policy_is_enforced(level):
    schema = question_response_schema(cv_excerpts=["sales dashboard"], job_excerpts=["SQL joins"],
                                     source_ids={"train-sql"}, experience_level=level)
    assert schema["properties"]["questions"]["items"]["properties"]["difficulty"]["enum"] == ["easy", "medium"]
    data = payload()
    data["questions"][0]["difficulty"] = "hard"
    with pytest.raises(ValueError, match="Entry/junior"):
        validate_questions(data, allowed_source_ids={"train-sql"}, experience_level=level)
    assert len(validate_questions(data, allowed_source_ids={"train-sql"}, experience_level="senior")) == 7
    assert "hard" in QUESTION_RESPONSE_SCHEMA["properties"]["questions"]["items"]["properties"]["difficulty"]["enum"]


def test_past_method_question_is_rejected_before_assuming_sql_joins_were_used():
    data = payload()
    data["questions"][0]["text"] = "When you queried SQLite, what specific SQL joins did you use?"
    with pytest.raises(ValueError, match="interviewer"):
        validate_questions(data, allowed_source_ids={"train-sql"})


def test_prospective_criterion_cannot_assume_missing_prior_experience():
    data = payload()
    data["questions"][0]["reference_criteria"] = [
        "The answer should list AWS services for hosting a Python API without prior experience."]
    with pytest.raises(ValueError, match="missing experience"):
        validate_questions(data, allowed_source_ids={"train-sql"})


def test_secondary_citation_padding_is_rejected_without_truncating_output():
    data = payload()
    data["questions"][0]["source_ids"] = ["train-sql", "train-drift"]
    with pytest.raises(ValueError, match="one primary"):
        validate_questions(data, allowed_source_ids={"train-sql", "train-drift"})
    assert data["questions"][0]["source_ids"] == ["train-sql", "train-drift"]


@pytest.mark.parametrize("field,value", [
    ("text", "How would you " + "extend this proposed analysis " * 20),
    ("target_skill", "x" * 81),
    ("reference_criteria", ["The answer should " + "explain a verification step " * 20]),
])
def test_bounded_question_fields_prevent_unbounded_structured_generation(field, value):
    data = payload()
    data["questions"][0][field] = value
    with pytest.raises(ValueError, match="Overlong"):
        validate_questions(data, allowed_source_ids={"train-sql"})


def test_shared_prompt_does_not_seed_role_specific_tools_or_experience():
    # A concrete SQLite example leaked into an unrelated ML scenario in a real run.
    # Candidate/tool context belongs to the supplied input, not the shared instructions.
    assert all(tool not in SYSTEM_PROMPT for tool in ("SQLite", "Power BI", "FastAPI"))


def test_prospective_peer_feedback_criterion_is_not_a_past_experience_claim():
    data = payload()
    data["questions"][0]["reference_criteria"] = [
        "The answer should outline a validation method where peers explain the dashboard logic back to you."]
    assert len(validate_questions(data, allowed_source_ids={"train-sql"})) == 7


def test_criterion_must_not_require_undocumented_current_implementation_details():
    data = payload()
    data["questions"][0]["reference_criteria"] = [
        "The answer should explain how the current FastAPI implementation interacts with PostgreSQL transactions."]
    with pytest.raises(ValueError, match="candidate-independent"):
        validate_questions(data, allowed_source_ids={"train-sql"})


def test_documented_project_context_is_allowed_in_prospective_criteria():
    data = payload()
    data["questions"][0]["reference_criteria"] = [
        "The answer should detail a workflow for identifying gaps in the 5000 sales rows previously cleaned.",
        "The answer should explain how to combine tables from the previously queried SQLite database."]
    assert len(validate_questions(data, allowed_source_ids={"train-sql"})) == 7


@pytest.mark.parametrize("criterion,error", [
    ("The answer should ensure the validation set does not contain information available at prediction time.", "unavailable/future"),
    ("The answer should avoid any method that uses the target variable during feature engineering.", "training-fold"),
    ("The answer should identify specific data distribution metrics that indicate concept drift over time.", "concept drift"),
])
def test_observed_ml_criteria_misconceptions_are_rejected(criterion, error):
    data = payload()
    data["questions"][0]["reference_criteria"] = [criterion]
    with pytest.raises(ValueError, match=error):
        validate_questions(data, allowed_source_ids={"train-sql"})


def test_prediction_time_features_and_fold_fitted_target_encoding_are_allowed():
    data = payload()
    data["questions"][0]["reference_criteria"] = [
        "The answer should use features available at prediction time and fit target encoding inside each training fold.",
        "The answer should distinguish input distribution shifts from changes in feature-outcome relationships."]
    assert len(validate_questions(data, allowed_source_ids={"train-sql"})) == 7

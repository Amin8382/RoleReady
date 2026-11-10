import json

from roleready_ai.generation import QUESTION_RESPONSE_SCHEMA
from roleready_ai.run import run


def test_existing_cli_pipeline_writes_only_validated_questions(monkeypatch, tmp_path):
    captured = []
    class Model:
        model = "synthetic-stand-in"
        last_response = {"finish_reason": "stop"}
        def __init__(self, **kwargs):
            captured.append(kwargs)
        def complete_json(self, *, system, user):
            texts = [
                "How would you verify missing values before analysis?",
                "How would you choose an aggregation for a sales metric?",
                "How would you design a dashboard for a nontechnical audience?",
                "How would you test a data cleaning function before deployment?",
                "How would you resolve an ambiguous business request?",
                "How would you detect a join producing duplicate sales records?",
                "What would you consider when learning an unfamiliar reporting tool?",
            ]
            return {"questions": [{
                "text": text, "target_skill": "analytics", "difficulty": "medium",
                "reason_for_asking": "CV: [sales dashboard]; Job: [SQL joins]. Practice the job requirement using documented CV context; missing ability is not inferred.",
                "reference_criteria": ["The answer should provide concrete reasoning."], "source_ids": ["train-sql"],
            } for text in texts]}

    monkeypatch.setattr("roleready_ai.run.OpenAICompatibleQwen", Model)
    session = tmp_path / "session.json"
    session.write_text(json.dumps({
        "cv_text": "I built a sales dashboard with Python and SQL in a university project.",
        "job_description": "The Data Analyst role requires SQL joins and clear reporting for stakeholders.",
        "target_role": "Data Analyst", "experience_level": "junior",
    }))
    bank = tmp_path / "train.jsonl"
    bank.write_text(json.dumps({"record_id": "train-sql", "question": "Explain SQL joins.",
                                "role": "Data Analyst", "source_id": "synthetic", "split": "train"}) + "\n")
    output = tmp_path / "output.json"
    result = run(input_file=session, question_bank=bank, output_file=output)
    assert captured == [{"response_schema": QUESTION_RESPONSE_SCHEMA}]
    assert result["attempts"] == 1 and len(result["questions"]) == 7
    assert result["quality_status"] == "unreviewed_model_output"
    assert json.loads(output.read_text())["retrieved_source_ids"] == ["train-sql"]

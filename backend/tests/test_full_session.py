from fastapi import status


def test_full_session_flow_end_to_end(client):
    # 1. Create candidate session
    create_res = client.post(
        "/sessions",
        data={
            "target_role": "Machine Learning Engineer",
            "experience_level": "mid",
            "job_text": "We are seeking an ML Engineer experienced in FAISS, LLM evaluation, and PyTorch.",
            "cv_text": "Jane Doe - 3 years experience building vector search engines and NLP pipelines.",
        },
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    session_id = create_res.json()["session_id"]

    # 2. Trigger CV vs Job analysis
    analysis_res = client.post(f"/sessions/{session_id}/analysis")
    assert analysis_res.status_code == status.HTTP_200_OK
    analysis_data = analysis_res.json()
    assert len(analysis_data["strengths"]) > 0
    assert len(analysis_data["requirements_not_evidenced"]) > 0

    # 3. Retrieve the 7 generated questions
    q_res = client.get(f"/sessions/{session_id}/questions")
    assert q_res.status_code == status.HTTP_200_OK
    q_data = q_res.json()
    assert q_data["total_questions"] == 7
    questions = q_data["questions"]

    # 4. Answer all 7 questions (Whisper raw + corrected transcript)
    sample_answers = [
        "I would implement an inverted file index (IVF) with product quantization (PQ) to scale memory.",
        "We enforce strict chronological time splits and train pipeline scalers exclusively on train data.",
        "I build REST endpoints with idempotent operations, database connection pooling, and Pydantic validation.",
        "We anchor rubric descriptions with clear reference examples and calibrate correlation using Pearson metrics.",
        "When we disagreed on the message queue, I ran latency benchmarks and presented factual trade-offs to reach consensus.",
        "We implement voice activity detection, streaming audio chunking, and beam search decoding.",
        "We track p95 latency, error rates, and monitor vector drift with automated alert thresholds.",
    ]

    for idx, q in enumerate(questions):
        ans_payload = {
            "question_id": q["question_id"],
            "original_transcript": f"Raw whisper text for question {idx + 1}",
            "corrected_transcript": sample_answers[idx],
        }
        ans_res = client.post(f"/sessions/{session_id}/answers", json=ans_payload)
        assert ans_res.status_code == status.HTTP_200_OK
        eval_data = ans_res.json()
        assert 1.0 <= eval_data["scores"]["overall_score"] <= 5.0
        assert "practice performance" in eval_data["practice_notice"].lower()

    # 5. Verify results endpoint
    results_res = client.get(f"/sessions/{session_id}/results")
    assert results_res.status_code == status.HTTP_200_OK
    assert results_res.json()["total_evaluated"] == 7

    # 6. Generate final report and cheat sheet
    report_res = client.post(f"/sessions/{session_id}/report")
    assert report_res.status_code == status.HTTP_200_OK
    report_data = report_res.json()
    assert len(report_data["seven_results"]) == 7
    assert report_data["average_session_score"] >= 2.0
    assert "cheat_sheet_content" in report_data
    assert len(report_data["priority_improvements"]) > 0

    # 7. Check PDF download endpoint
    pdf_res = client.get(f"/sessions/{session_id}/pdf")
    assert pdf_res.status_code == status.HTTP_200_OK
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert b"%PDF" in pdf_res.content

    # 8. Test GDPR delete-my-data endpoint
    del_res = client.delete("/user/data")
    assert del_res.status_code == status.HTTP_200_OK
    assert del_res.json()["status"] == "success"

    # Verify session is gone
    check_res = client.get(f"/sessions/{session_id}")
    assert check_res.status_code == status.HTTP_404_NOT_FOUND


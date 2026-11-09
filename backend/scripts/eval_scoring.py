#!/usr/bin/env python3
"""
RoleReady Scoring Evaluation & Calibration Benchmark Script
Author: Oussema Ferchichi (Backend & Scoring Lead)

Evaluates the active scoring backend against a human-annotated benchmark dataset
of weak, partial, and strong candidate answers (1-5 practice rubric).
Calculates:
- Mean Absolute Error (MAE)
- Pearson Correlation Coefficient (r)
- Per-class average scores (Weak / Partial / Strong)
"""

import os
import sys
import csv
import asyncio
import numpy as np

# Ensure root backend is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.scoring.factory import get_scorer


async def run_evaluation(csv_path: str = "backend/data/eval_benchmark.csv"):
    if not os.path.exists(csv_path):
        print(f"Error: Benchmark file '{csv_path}' not found.")
        return

    scorer = get_scorer()
    print("=" * 70)
    print("RoleReady - Prometheus 7B Practice Scoring Calibration Benchmark")
    print(f"Active Scorer Engine: {scorer.__class__.__name__}")
    print(f"Benchmark Dataset:    {csv_path}")
    print("=" * 70)

    human_ratings = []
    predicted_ratings = []
    category_map = {"weak": [], "partial": [], "strong": []}

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\nRunning evaluation on {len(rows)} human-annotated test cases...\n")
    print(f"{'ID':<4} | {'Label':<8} | {'Human':<6} | {'Model':<6} | {'Diff':<6} | {'Feedback Snippet'}")
    print("-" * 75)

    for row in rows:
        case_id = row["case_id"]
        label = row["label"]
        q_text = row["question_text"]
        target_skill = row["target_skill"]
        ref_criteria = row["reference_criteria"]
        answer = row["candidate_answer"]
        human_score = float(row["human_rating"])

        # Evaluate through backend scoring interface
        eval_res = await scorer.evaluate_answer(
            session_id="eval_bench",
            question_id=f"case_{case_id}",
            question_text=q_text,
            target_skill=target_skill,
            reference_criteria=ref_criteria,
            original_transcript=answer,
            corrected_transcript=answer,
        )

        model_score = eval_res.scores.overall_score
        diff = round(abs(model_score - human_score), 2)

        human_ratings.append(human_score)
        predicted_ratings.append(model_score)
        category_map[label].append(model_score)

        feedback_snippet = (eval_res.feedback[:35] + "...") if len(eval_res.feedback) > 35 else eval_res.feedback
        print(f"{case_id:<4} | {label:<8} | {human_score:<6.2f} | {model_score:<6.2f} | {diff:<6.2f} | {feedback_snippet}")

    # Statistical Metrics
    y_true = np.array(human_ratings)
    y_pred = np.array(predicted_ratings)

    mae = float(np.mean(np.abs(y_true - y_pred)))
    std_err = float(np.std(np.abs(y_true - y_pred)))

    # Pearson correlation
    if np.std(y_pred) > 0 and np.std(y_true) > 0:
        correlation = float(np.corrcoef(y_true, y_pred)[0, 1])
    else:
        correlation = 0.0

    print("=" * 70)
    print("CALIBRATION & PERFORMANCE METRICS")
    print("=" * 70)
    print(f"Total Benchmark Cases:            {len(y_true)}")
    print(f"Mean Absolute Error (MAE):        {mae:.3f} (± {std_err:.3f})")
    print(f"Pearson Correlation (r):          {correlation:.3f}")
    print("-" * 70)
    print("Category Score Averages (1.0 to 5.0):")
    for cat in ["weak", "partial", "strong"]:
        scores = category_map[cat]
        avg = np.mean(scores) if scores else 0.0
        print(f"  • {cat.capitalize():<8}: Model Avg = {avg:.2f} / 5.0")
    print("=" * 70)
    print("Evaluation completed successfully.")


if __name__ == "__main__":
    asyncio.run(run_evaluation())

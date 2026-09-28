from __future__ import annotations

import pandas as pd

from cumap.gold.sample_answers import sample_pilot_answers


def _fake_answers(question_id: str, labels: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "answer_id": [f"a_{question_id}_{i}" for i in range(len(labels))],
            "question_id": [question_id] * len(labels),
            "verification_feedback": labels,
            "provided_answer": [f"answer {i}" for i in range(len(labels))],
        }
    )


def test_samples_target_counts_when_available():
    labels = ["Correct"] * 10 + ["Partially correct"] * 10 + ["Incorrect"] * 10
    df = _fake_answers("q_1", labels)
    sampled, notes = sample_pilot_answers(df, ["q_1"], seed=42)

    counts = sampled["verification_feedback"].value_counts().to_dict()
    assert counts == {"Correct": 3, "Partially correct": 4, "Incorrect": 3}
    assert notes == []


def test_backfills_shortfall_from_partially_correct():
    labels = ["Correct"] * 10 + ["Partially correct"] * 10  # zero Incorrect
    df = _fake_answers("q_2", labels)
    sampled, notes = sample_pilot_answers(df, ["q_2"], seed=42)

    counts = sampled["verification_feedback"].value_counts().to_dict()
    assert counts.get("Incorrect", 0) == 0
    assert counts["Partially correct"] == 7  # 4 target + 3 backfilled
    assert any("q_2" in n and "Incorrect" in n for n in notes)


def test_is_deterministic_given_same_seed():
    labels = ["Correct"] * 10 + ["Partially correct"] * 10 + ["Incorrect"] * 10
    df = _fake_answers("q_1", labels)
    first, _ = sample_pilot_answers(df, ["q_1"], seed=42)
    second, _ = sample_pilot_answers(df, ["q_1"], seed=42)
    assert list(first["answer_id"]) == list(second["answer_id"])


def test_no_duplicate_answers_across_labels():
    labels = ["Correct"] * 10 + ["Partially correct"] * 10 + ["Incorrect"] * 10
    df = _fake_answers("q_1", labels)
    sampled, _ = sample_pilot_answers(df, ["q_1"], seed=42)
    assert sampled["answer_id"].is_unique

"""`cumap gold sample-answers`: picks answers per pilot question from train only,
stratified by label, fixed seed (BUILD_PLAN M3 task 2). No LLM involved.
"""

from __future__ import annotations

import pandas as pd

DEFAULT_TARGET_PER_LABEL = {"Correct": 3, "Partially correct": 4, "Incorrect": 3}


def sample_pilot_answers(
    train_answers: pd.DataFrame,
    pilot_question_ids: list[str],
    seed: int,
    target_per_label: dict[str, int] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Returns (sampled_answers, shortfall_notes).

    If a question doesn't have enough answers in some label, that label's shortfall
    is backfilled from "Partially correct" (the largest, most diagnostically useful
    pool) rather than silently under-sampling; a note is returned either way so the
    caller can tell the human what happened.
    """
    target_per_label = target_per_label or DEFAULT_TARGET_PER_LABEL
    notes: list[str] = []
    sampled_frames = []

    for qid in pilot_question_ids:
        qdf = train_answers[train_answers["question_id"] == qid]
        taken_ids: set[str] = set()
        shortfall = 0

        for label, n in target_per_label.items():
            pool = qdf[qdf["verification_feedback"] == label]
            n_take = min(n, len(pool))
            if n_take < n:
                shortfall += n - n_take
                notes.append(
                    f"{qid}: only {len(pool)} '{label}' answers in train (wanted {n})"
                )
            if n_take > 0:
                sample = pool.sample(n=n_take, random_state=seed)
                sampled_frames.append(sample)
                taken_ids |= set(sample["answer_id"])

        if shortfall > 0:
            backfill_pool = qdf[
                (qdf["verification_feedback"] == "Partially correct")
                & (~qdf["answer_id"].isin(taken_ids))
            ]
            n_backfill = min(shortfall, len(backfill_pool))
            if n_backfill > 0:
                backfill = backfill_pool.sample(n=n_backfill, random_state=seed)
                sampled_frames.append(backfill)
                notes.append(f"{qid}: backfilled {n_backfill} shortfall slot(s) from 'Partially correct'")

    result = pd.concat(sampled_frames, ignore_index=True) if sampled_frames else train_answers.iloc[0:0]
    return result, notes

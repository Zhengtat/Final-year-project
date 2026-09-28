"""Shared helper: which textbook section(s) cover a pilot question.

Prefers the human's finalized data/gold/question_section_map.csv; falls back to
the reviewed draft in data/interim/suggestions/ if the human hasn't saved gold yet.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def section_ids_for_question(gold_dir: Path, interim_dir: Path, qid: str) -> list[str]:
    gold_csv = gold_dir / "question_section_map.csv"
    if gold_csv.exists():
        df = pd.read_csv(gold_csv)
        col = "verified_section_id" if "verified_section_id" in df.columns else "section_id"
        rows = df[df["question_id"] == qid]
        if len(rows):
            return str(rows.iloc[0][col]).split("+")

    draft_csv = interim_dir / "suggestions" / "pilot_question_section_map.csv"
    df = pd.read_csv(draft_csv)
    rows = df[df["question_id"] == qid]
    return str(rows.iloc[0]["verified_section_id"]).split("+")

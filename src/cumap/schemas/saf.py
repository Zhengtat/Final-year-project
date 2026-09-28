"""SAF Question/Answer schemas — matches data/saf.py's ingested tables.

`Answer.answer_feedback` is privileged (CLAUDE.md rule 10): only M4's silver-label
builder may read it. See `cumap.data.saf.drop_privileged_columns` for the
non-privileged view used everywhere else.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    question: str
    reference_answer: str


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_id: str
    question_id: str
    split: str
    provided_answer: str
    verification_feedback: str
    score: float
    answer_feedback: str | None = None  # privileged; None once dropped for non-M4 code

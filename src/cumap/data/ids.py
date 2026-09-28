"""Stable IDs for SAF questions and answers (BUILD_PLAN M1 task 2).

question_id = "q_" + sha1(normalised question text)[:8]
answer_id   = "a_" + sha1(question_id + provided_answer)[:10]

"Normalised" = stripped, internal whitespace collapsed, lower-cased — so two rows
with the same question text differing only in incidental whitespace/case get the
same question_id. IDs must be stable across runs (no randomness, no row order
dependence).
"""

from __future__ import annotations

import hashlib


def normalise_text(text: str) -> str:
    return " ".join(text.strip().split()).lower()


def question_id(question_text: str) -> str:
    digest = hashlib.sha1(normalise_text(question_text).encode("utf-8")).hexdigest()
    return f"q_{digest[:8]}"


def answer_id(qid: str, provided_answer: str) -> str:
    digest = hashlib.sha1((qid + provided_answer).encode("utf-8")).hexdigest()
    return f"a_{digest[:10]}"

"""Embedding-based question -> top-5 section suggestions, plus an LLM coverage guess.

Embeddings are local (sentence-transformers) and free; only the coverage-guess step
calls the LLM, so it is the only part gated by --dry-run/--limit and cost approval.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from cumap.llm.client import LLMClient
from cumap.textbook.parse import Section

TOP_K = 5


class CoverageGuessLLM(BaseModel):
    """Flat LLM-facing schema: every field required, no defaults, no extra properties."""

    model_config = ConfigDict(extra="forbid")

    coverage: str  # "full" | "partial" | "none"
    reason: str


class TopSectionMatch(NamedTuple):
    question_id: str
    question: str
    rank: int
    section_id: str
    section_title: str
    score: float


def embed_texts(texts: list[str], model_name: str) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


def top_k_sections_per_question(
    questions: pd.DataFrame,  # columns: question_id, question, reference_answer
    sections: list[Section],
    model_name: str,
    k: int = TOP_K,
) -> list[TopSectionMatch]:
    query_texts = (questions["question"] + " " + questions["reference_answer"]).tolist()
    section_texts = [s.text for s in sections]

    query_embs = embed_texts(query_texts, model_name)
    section_embs = embed_texts(section_texts, model_name)

    similarities = query_embs @ section_embs.T  # cosine, since both are normalised

    matches = []
    for qi, (_, qrow) in enumerate(questions.iterrows()):
        order = np.argsort(-similarities[qi])[:k]
        for rank, si in enumerate(order, start=1):
            matches.append(
                TopSectionMatch(
                    question_id=qrow["question_id"],
                    question=qrow["question"],
                    rank=rank,
                    section_id=sections[si].section_id,
                    section_title=sections[si].section_title,
                    score=float(similarities[qi, si]),
                )
            )
    return matches


def estimate_coverage_guess_cost(
    questions: pd.DataFrame,
    matches: list[TopSectionMatch],
    sections_by_id: dict[str, Section],
    *,
    assumed_usd_per_1k_input_tokens: float,
    assumed_usd_per_1k_output_tokens: float,
    assumed_output_tokens: int = 120,
) -> dict:
    """Rough token/cost estimate (chars/4 heuristic) for the coverage-guess LLM step.

    Pricing for the fictional configured models is not known; the caller must pass
    an explicit assumed rate and treat the dollar figure as an approximation only.
    """
    total_input_chars = 0
    for _, qrow in questions.iterrows():
        top_sections = [m for m in matches if m.question_id == qrow["question_id"]][:3]
        prompt_chars = len(qrow["question"]) + len(qrow["reference_answer"])
        for m in top_sections:
            prompt_chars += len(sections_by_id[m.section_id].text[:800])
        total_input_chars += prompt_chars

    n_calls = questions["question_id"].nunique()
    input_tokens = total_input_chars // 4
    output_tokens = n_calls * assumed_output_tokens
    cost = (
        input_tokens / 1000 * assumed_usd_per_1k_input_tokens
        + output_tokens / 1000 * assumed_usd_per_1k_output_tokens
    )
    return {
        "n_calls": int(n_calls),
        "est_input_tokens": int(input_tokens),
        "est_output_tokens": int(output_tokens),
        "est_usd": round(cost, 4),
    }


def run_coverage_guess(
    client: LLMClient,
    questions: pd.DataFrame,
    matches: list[TopSectionMatch],
    sections_by_id: dict[str, Section],
    *,
    prompt_template,
    limit: int | None = None,
) -> pd.DataFrame:
    rows = []
    qids = questions["question_id"].tolist()
    if limit is not None:
        qids = qids[:limit]

    for qid in qids:
        qrow = questions[questions["question_id"] == qid].iloc[0]
        top_sections = [m for m in matches if m.question_id == qid][:3]
        sections_block = "\n\n".join(
            f"[{m.section_id}] {m.section_title}\n{sections_by_id[m.section_id].text[:800]}"
            for m in top_sections
        )
        rendered = prompt_template.render(
            question=qrow["question"],
            reference_answer=qrow["reference_answer"],
            sections_block=sections_block,
        )
        result = client.parse(
            task="coverage_guess",
            prompt_version=prompt_template.version,
            messages=[{"role": "user", "content": rendered}],
            schema=CoverageGuessLLM,
            model_tier="strong",
        )
        rows.append(
            {
                "question_id": qid,
                "coverage": result.output.coverage,
                "reason": result.output.reason,
            }
        )
    return pd.DataFrame(rows)


def write_question_section_map(
    matches: list[TopSectionMatch],
    coverage_df: pd.DataFrame | None,
    out_path: Path,
) -> None:
    df = pd.DataFrame([m._asdict() for m in matches])
    if coverage_df is not None:
        df = df.merge(coverage_df, on="question_id", how="left")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

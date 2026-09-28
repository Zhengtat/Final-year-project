"""M5 task 1 (BUILD_PLAN): FACE-style candidate-term signals, no LLM. spaCy noun
chunks (1-4 tokens, stop-modifiers stripped), frequency per section and across the
slice, tf-idf, and in_heading/emphasized flags.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

_STOP_MODIFIERS = {
    "such",
    "many",
    "certain",
    "various",
    "several",
    "other",
    "same",
    "new",
    "some",
    "any",
    "these",
    "those",
    "this",
    "that",
}


@dataclass
class CandidateTerm:
    term: str
    section_id: str
    freq_in_section: int = 0
    in_heading: bool = False
    emphasized: bool = False
    tfidf: float = 0.0


def _strip_stop_modifier(chunk_text: str) -> str:
    words = chunk_text.split()
    while words and words[0].lower() in _STOP_MODIFIERS:
        words = words[1:]
    return " ".join(words)


def extract_candidate_terms(text: str, nlp) -> list[str]:
    """1-4 token noun-chunk candidates, lowercased, stop-modifiers stripped, deduped
    (order-preserving). `nlp` is a loaded spaCy pipeline (e.g. en_core_web_sm).
    """
    doc = nlp(text)
    seen: dict[str, None] = {}
    for chunk in doc.noun_chunks:
        cleaned = _strip_stop_modifier(chunk.text.strip())
        n_tokens = len(cleaned.split())
        if 1 <= n_tokens <= 4 and cleaned:
            seen.setdefault(cleaned.lower(), None)
    return list(seen.keys())


def compute_candidate_stats(
    section_texts: dict[str, str],
    nlp,
    *,
    heading_paths: dict[str, list[str]] | None = None,
    emphasized_terms: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """One row per (section_id, term): freq_in_section, in_heading, emphasized, tfidf
    (computed across the given sections as the corpus — the demo slice's own 37
    sections, not the whole book/IIR).
    """
    heading_paths = heading_paths or {}
    emphasized_terms = emphasized_terms or {}

    section_ids = list(section_texts.keys())
    candidates_by_section = {
        sid: extract_candidate_terms(text, nlp) for sid, text in section_texts.items()
    }

    vectorizer = TfidfVectorizer(
        vocabulary=None, lowercase=True, token_pattern=r"(?u)\b\w[\w\s]*\w\b|\b\w\b"
    )
    # Fit tf-idf on the raw section texts so scores are comparable across the slice;
    # look up each candidate term's score from the fitted vocabulary (0 if out-of-vocab,
    # e.g. because the vectorizer's own tokenizer split it differently).
    tfidf_matrix = vectorizer.fit_transform([section_texts[sid] for sid in section_ids])
    vocab = vectorizer.vocabulary_

    rows: list[CandidateTerm] = []
    for row_idx, sid in enumerate(section_ids):
        text_lower = section_texts[sid].lower()
        heading_text = " ".join(heading_paths.get(sid, [])).lower()
        emph_lower = {t.lower() for t in emphasized_terms.get(sid, [])}

        for term in candidates_by_section[sid]:
            freq = text_lower.count(term)
            tfidf_score = float(tfidf_matrix[row_idx, vocab[term]]) if term in vocab else 0.0
            rows.append(
                CandidateTerm(
                    term=term,
                    section_id=sid,
                    freq_in_section=freq,
                    in_heading=term in heading_text,
                    emphasized=term in emph_lower,
                    tfidf=tfidf_score,
                )
            )

    return pd.DataFrame([vars(r) for r in rows])

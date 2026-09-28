"""CR-005 §2 task 1 tests: candidate-term stats (no LLM, no network beyond the
already-downloaded spaCy model)."""

from __future__ import annotations

import pytest

from cumap.expert_kg.stats import compute_candidate_stats, extract_candidate_terms


@pytest.fixture(scope="module")
def nlp():
    import spacy

    return spacy.load("en_core_web_sm")


def test_extract_candidate_terms_finds_noun_chunks(nlp):
    terms = extract_candidate_terms("The congestion window controls how much data TCP can send.", nlp)
    assert any("congestion window" in t for t in terms)
    assert "tcp" in terms


def test_extract_candidate_terms_strips_stop_modifiers(nlp):
    terms = extract_candidate_terms("Such devices use certain protocols for various tasks.", nlp)
    assert "such devices" not in terms
    assert "certain protocols" not in terms
    assert "devices" in terms or "protocols" in terms


def test_extract_candidate_terms_limits_to_1_4_tokens(nlp):
    terms = extract_candidate_terms(
        "The very long and unnecessarily complicated congestion window management subsystem design exists.", nlp
    )
    assert all(1 <= len(t.split()) <= 4 for t in terms)


def test_compute_candidate_stats_basic_columns():
    import spacy

    nlp = spacy.load("en_core_web_sm")
    texts = {
        "s1": "TCP uses the congestion window to control sending.",
        "s2": "UDP does not use a congestion window at all.",
    }
    df = compute_candidate_stats(texts, nlp)
    assert set(df.columns) == {"term", "section_id", "freq_in_section", "in_heading", "emphasized", "tfidf"}
    assert (df["section_id"].isin(["s1", "s2"])).all()


def test_compute_candidate_stats_in_heading_flag():
    import spacy

    nlp = spacy.load("en_core_web_sm")
    texts = {"s1": "The congestion window grows during slow start."}
    df = compute_candidate_stats(texts, nlp, heading_paths={"s1": ["Chapter 6", "Slow Start"]})
    slow_start_rows = df[df["term"].str.contains("slow start", case=False, na=False)]
    assert not slow_start_rows.empty
    assert slow_start_rows.iloc[0]["in_heading"]


def test_compute_candidate_stats_emphasized_flag():
    import spacy

    nlp = spacy.load("en_core_web_sm")
    texts = {"s1": "Slow start doubles the window every RTT."}
    df = compute_candidate_stats(texts, nlp, emphasized_terms={"s1": ["slow start"]})
    matches = df[df["term"] == "slow start"]
    assert not matches.empty
    assert matches.iloc[0]["emphasized"]

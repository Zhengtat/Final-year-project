"""CR-005 §3.1 / §6 required test: "The FACE scorer's exact and lenient matching on
fixtures." Covers matching (exact/alias/lemma/embedding), micro/macro P/R/F1,
n-gram/role breakdowns, and error sampling.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from cumap.expert_kg.face_scorer import (
    GoldConcept,
    PredictedConcept,
    load_gold_concepts,
    macro_prf1,
    match_predictions,
    micro_prf1,
    precision_by_role,
    prf1_by_ngram_length,
    sample_errors,
)

REPO_ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def nlp():
    import spacy

    return spacy.load("en_core_web_sm")


def _fake_embed(text: str) -> np.ndarray:
    vocab = ["boolean", "retrieval", "model", "index", "inverted", "document", "query"]
    text_lower = text.lower()
    return np.array([1.0 if w in text_lower else 0.0 for w in vocab])


def test_load_gold_concepts_filters_to_is_gold_true(tmp_path):
    csv_path = tmp_path / "gold.csv"
    csv_path.write_text(
        "section_id,concept,aliases,n_annotators_yes,n_annotators_total,is_gold\n"
        "s1,information retrieval,[],3,3,True\n"
        "s1,documents,['document'],2,3,True\n"
        "s1,noise term,[],0,3,False\n"
    )
    concepts = load_gold_concepts(csv_path)
    assert len(concepts) == 2
    assert {c.concept for c in concepts} == {"information retrieval", "documents"}
    documents = next(c for c in concepts if c.concept == "documents")
    assert documents.aliases == ["document"]


def test_match_predictions_exact_match():
    gold = [GoldConcept("s1", "information retrieval")]
    predicted = [PredictedConcept("s1", "Information Retrieval", role="used")]
    results = match_predictions(predicted, gold, lenient=False)
    assert results[0].match_type == "exact"
    assert results[0].matched_gold is gold[0]


def test_match_predictions_exact_match_via_alias():
    gold = [GoldConcept("s1", "documents", aliases=["document"])]
    predicted = [PredictedConcept("s1", "document", role="used")]
    results = match_predictions(predicted, gold, lenient=False)
    assert results[0].match_type == "exact"


def test_match_predictions_no_match_when_lenient_disabled(nlp):
    gold = [GoldConcept("s1", "document")]
    predicted = [PredictedConcept("s1", "documents", role="used")]  # differs only by plural
    results = match_predictions(predicted, gold, lenient=False, nlp=nlp)
    assert results[0].match_type is None


def test_match_predictions_lenient_lemma_match(nlp):
    gold = [GoldConcept("s1", "document")]
    predicted = [PredictedConcept("s1", "documents", role="used")]
    results = match_predictions(predicted, gold, lenient=True, nlp=nlp)
    assert results[0].match_type == "lemma"


def test_match_predictions_lenient_embedding_match():
    gold = [GoldConcept("s1", "boolean retrieval model")]
    predicted = [
        PredictedConcept("s1", "boolean model retrieval", role="used")
    ]  # reordered, no exact/lemma hit
    results = match_predictions(
        predicted, gold, lenient=True, embed_fn=_fake_embed, embedding_threshold=0.9
    )
    assert results[0].match_type == "embedding"


def test_match_predictions_below_embedding_threshold_stays_unmatched():
    gold = [GoldConcept("s1", "boolean retrieval model")]
    predicted = [PredictedConcept("s1", "query", role="used")]  # shares no vocab with gold
    results = match_predictions(
        predicted, gold, lenient=True, embed_fn=_fake_embed, embedding_threshold=0.5
    )
    assert results[0].match_type is None


def test_one_gold_concept_matched_at_most_once():
    gold = [GoldConcept("s1", "index")]
    predicted = [
        PredictedConcept("s1", "index", role="defined"),
        PredictedConcept("s1", "index", role="used"),  # duplicate prediction, same gold target
    ]
    results = match_predictions(predicted, gold, lenient=False)
    matched = [r for r in results if r.matched_gold is not None]
    unmatched = [r for r in results if r.matched_gold is None]
    assert len(matched) == 1
    assert len(unmatched) == 1  # the second "index" becomes a false positive, not a double match


def test_micro_and_macro_prf1_known_values():
    gold = [
        GoldConcept("A", "information retrieval"),
        GoldConcept("A", "indexing"),
        GoldConcept("B", "boolean model"),
    ]
    predicted = [
        PredictedConcept("A", "information retrieval", role="defined"),  # TP
        PredictedConcept("A", "documents", role="used"),  # FP, no gold match
        PredictedConcept("B", "boolean model", role="defined"),  # TP
    ]
    results = match_predictions(predicted, gold, lenient=False)

    micro = micro_prf1(results, gold)
    assert micro.tp == 2 and micro.fp == 1 and micro.fn == 1
    assert micro.precision == pytest.approx(2 / 3)
    assert micro.recall == pytest.approx(2 / 3)

    macro = macro_prf1(results, gold)
    # section A: P=1/2=0.5, R=1/2=0.5; section B: P=1/1=1.0, R=1/1=1.0
    assert macro.precision == pytest.approx(0.75)
    assert macro.recall == pytest.approx(0.75)


def test_prf1_by_ngram_length_groups_by_gold_length():
    gold = [GoldConcept("s1", "index"), GoldConcept("s1", "inverted index list")]
    predicted = [PredictedConcept("s1", "index", role="used")]  # matches the 1-gram gold only
    results = match_predictions(predicted, gold, lenient=False)

    by_length = prf1_by_ngram_length(results, gold)
    assert by_length[1].tp == 1
    assert by_length[3].fn == 1  # "inverted index list" never matched


def test_precision_by_role_has_no_recall_meaning():
    gold = [GoldConcept("s1", "index")]
    predicted = [
        PredictedConcept("s1", "index", role="defined"),  # TP
        PredictedConcept("s1", "noise", role="mentioned"),  # FP
    ]
    results = match_predictions(predicted, gold, lenient=False)
    by_role = precision_by_role(results)
    assert by_role["defined"].precision == 1.0
    assert by_role["mentioned"].precision == 0.0


def test_sample_errors_returns_both_kinds():
    gold = [GoldConcept("s1", "indexing")]
    predicted = [PredictedConcept("s1", "documents", role="used")]  # FP; "indexing" becomes FN
    results = match_predictions(predicted, gold, lenient=False)
    errors = sample_errors(results, gold, n=10)
    kinds = {e.kind for e in errors}
    assert kinds == {"false_positive", "false_negative"}

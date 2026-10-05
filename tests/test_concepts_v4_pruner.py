"""CR-009 §5/§11: the pruner's training rows, leave-one-chapter-out discipline and the tau rule (no network)."""

import numpy as np
import spacy

from cumap.concepts_v4.pruner import P1Model, build_rows, choose_tau, is_value_like, term_features

NLP = spacy.load("en_core_web_sm")
GOLD = {"s1": {"inverted index", "postings"}, "s2": {"stemming"}, "s3": {"tokenization"}}
CAND = {
    "s1": {"inverted index", "the first example", "postings"},
    "s2": {"stemming", "a few terms"},
    "s3": {"tokenization", "the first example"},
}


def test_rows_are_deduplicated_and_gold_in_any_training_section_counts_as_growing():
    rows = dict(build_rows(GOLD, CAND, ["s1", "s2", "s3"]))
    assert (
        rows["inverted index"] == 1 and rows["the first example"] == 0 and rows["a few terms"] == 0
    )
    assert len(rows) == len(
        {t for t, _ in build_rows(GOLD, CAND, ["s1", "s2", "s3"])}
    )  # one row per term
    g = {
        **GOLD,
        "s2": GOLD["s2"] | {"the first example"},
    }  # gold in one section outranks a non-gold candidate elsewhere
    assert dict(build_rows(g, CAND, ["s1", "s2", "s3"]))["the first example"] == 1


def test_leave_one_chapter_out_rows_exclude_the_held_out_chapter_labels():
    rows = dict(build_rows(GOLD, CAND, ["s1", "s2"]))  # s3 held out
    assert "tokenization" not in rows  # its gold is not used to label training rows
    assert rows.get("the first example") == 0  # labelled only from the training chapters


def test_features_are_surface_only_and_bank_and_cso_are_features_not_rows():
    f = term_features("TCP", NLP, bank={"thing"}, cso=set())
    assert f[2] == 1.0 and f[4] == 0.0  # acronym; not in the bank
    assert term_features("thing", NLP, bank={"thing"})[4] == 1.0
    assert is_value_like("4 KB") and not is_value_like("inverted index")
    rows = build_rows(GOLD, CAND, ["s1", "s2", "s3"])
    assert all(
        t in set().union(*GOLD.values(), *CAND.values()) for t, _ in rows
    )  # nothing from the bank or CSO


def test_p1_fits_and_scores_growing_above_pruned():
    def emb(t):
        v = np.zeros(4)
        v[0] = float("index" in t or "post" in t or "stem" in t or "token" in t)
        v[1] = float("example" in t or "few" in t)
        return v

    m = P1Model(emb, NLP).fit(build_rows(GOLD, CAND, ["s1", "s2", "s3"]))
    assert m.p_growing("inverted index") > m.p_growing("the first example")


def test_tau_rule_highest_f1_with_recall_drop_at_most_001_else_zero():
    base = {"f1": 0.50, "recall": 0.60}
    table = {
        0.2: {"f1": 0.52, "recall": 0.595},
        0.4: {"f1": 0.55, "recall": 0.57},
        0.6: {"f1": 0.53, "recall": 0.60},
    }
    tau, tab = choose_tau([], lambda t: table[t], base, [0.2, 0.4, 0.6])
    assert tau == 0.6  # 0.4 has the best F1 but loses 0.03 recall; 0.6 beats 0.2 and keeps recall
    assert [r["eligible"] for r in tab] == [True, False, True]
    none, _ = choose_tau([], lambda t: {"f1": 0.4, "recall": 0.5}, base, [0.3])
    assert none == 0.0  # no tau > 0 qualifies: no pruning, reported honestly

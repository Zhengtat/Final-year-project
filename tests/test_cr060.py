"""CR-060: span identity at assembly (Part A) and the noun-phrase hint (Part B). No network, no key."""

import copy

from cumap.cr060 import span_identity as SI

TEXT = (
    "We compare GloVe with the GloVe model of prior work . The trigram model and a trigram baseline differ . "
    "Word sense disambiguation ( WSD ) is hard ."
)


def _cp(concepts, rows=()):
    return {"concepts": [{"concept_id": i, "canonical_name": n, "aliases": a, "mentions": [], "node_type": "Concept"}
                         for i, n, a in concepts],
            "relation_results_v3": [{"pair": {"concept_x_id": x, "concept_y_id": y}, "relation": rel, "outcome": "edge",
                                     "direction": "forward"} for x, y, rel in rows],
            "selection_stats": {}}  # fmt: skip


V_NAME = SI.Variant("A-name", "name_like", False, frozenset({"model", "models"}))
V_ALL = SI.Variant("A-all", "all", True, frozenset({"model", "models"}))


def test_a_name_like_form_gains_the_head_alias_with_its_evidence_and_the_input_is_untouched():
    cp0 = _cp([("g", "GloVe", []), ("t", "trigram", [])])
    before = copy.deepcopy(cp0)
    cp, rec = SI.apply(cp0, TEXT, V_NAME)
    assert cp0 == before
    by = {c["concept_id"]: c for c in cp["concepts"]}
    assert (
        by["g"]["aliases"] == ["GloVe model"] and by["t"]["aliases"] == []
    )  # "trigram" is not name-like
    assert rec["aliases"] == [
        {"node": "g", "alias": "GloVe model", "rule": "R-head", "evidence": "GloVe model"}
    ]
    assert "GloVe model" in TEXT and cp["selection_stats"]["span_identity"]["aliases"] == 1


def test_a_head_variant_node_merges_into_the_bare_form_with_rule_and_evidence():
    cp, rec = SI.apply(
        _cp([("t", "trigram", []), ("tm", "trigram model", [])], [("tm", "x", "usedFor")]),
        TEXT + " x",
        V_ALL,
    )
    assert [c["concept_id"] for c in cp["concepts"]] == ["t"]
    assert cp["concepts"][0]["aliases"] == ["trigram model"]
    assert rec["merges"][0] == {"into": "t", "merged": "tm", "merged_name": "trigram model", "rule": "R-head",
                                     "evidence": "trigram model"}  # fmt: skip
    assert cp["relation_results_v3"][0]["pair"]["concept_x_id"] == "t"


def test_the_acronym_rule_keeps_the_parenthesised_acronym_as_written():
    cp, rec = SI.apply(_cp([("w", "word sense disambiguation", [])]), TEXT, V_ALL)
    assert cp["concepts"][0]["aliases"] == ["Word sense disambiguation ( WSD )"]
    assert rec["aliases"][0]["rule"] == "R-acr"


def test_a_lexicon_different_pair_is_never_merged():
    cp, rec = SI.apply(_cp([("t", "trigram", []), ("tm", "trigram model", [])]), TEXT, V_ALL,
                       different={frozenset({"trigram", "trigram model"})})  # fmt: skip
    assert len(cp["concepts"]) == 2 and rec["merges"] == [] and rec["vetoed"]


def test_only_duplicates_and_self_loops_made_by_a_merge_are_dropped():
    rows = [("t", "a", "usedFor"), ("tm", "a", "usedFor"), ("t", "tm", "compareWith"), ("a", "b", "usedFor"),
            ("a", "b", "usedFor")]  # fmt: skip
    cp, rec = SI.apply(
        _cp(
            [("t", "trigram", []), ("tm", "trigram model", []), ("a", "A", []), ("b", "B", [])],
            rows,
        ),
        TEXT,
        V_ALL,
    )
    dropped = {d["row"]: d["reason"] for d in rec["edges_dropped"]}
    assert dropped == {
        1: "duplicate_after_merge",
        2: "self_loop_after_merge",
    }  # rows 3 / 4: a pre-existing duplicate stays
    assert all(not cp["relation_results_v3"][i].get("consolidated_into") for i in (0, 3, 4))


def test_the_committed_variants_load():
    for name in ("A-name", "A-all"):
        v = SI.load_variant(name)
        assert "model" in v.heads and v.name == name

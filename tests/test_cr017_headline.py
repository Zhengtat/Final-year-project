"""CR-017 STOP 3: unified five-metric evaluator fixtures (no model, no network)."""

import json
from pathlib import Path

import pytest

from cumap.cr012 import bootstrap as B
from cumap.cr012 import scoring as S
from cumap.cr012.types import (
    PRF,
    GoldConcept,
    GoldMention,
    GoldRelation,
    PredEdge,
    PredNode,
    UnitGold,
)
from cumap.cr017 import headline as HL

SP = {c: (i * 10, i * 10 + 3) for i, c in enumerate("ABCDE")}


def gold(rels):
    return UnitGold(
        "s",
        [GoldMention("s", SP[c], "Concept", c) for c in "ABCDE"],
        [GoldConcept(c, "s", c, "Concept") for c in "ABCDE"],
        [GoldRelation("s", r, src_concept=a, tgt_concept=b) for a, r, b in rels],
    )


def nodes(cs="ABCDE"):
    return [PredNode(f"n{c}", "s", "Concept", c, (SP[c],)) for c in cs]


def res(x, y, outcome="edge", rel=None, swap=False):
    s, t = (y, x) if swap else (x, y)
    return {"outcome": outcome, "relation": rel, "src": f"n{s}", "tgt": f"n{t}"}


def unit(rels, edges, proposed, classifier, cs="ABCDE"):
    es = [PredEdge("s", f"n{a}", f"n{b}", r) for a, r, b in edges]
    pp = {frozenset((f"n{a}", f"n{b}")) for a, b in proposed}
    cl = {frozenset((f"n{a}", f"n{b}")): v for (a, b), v in classifier.items()}
    return HL.UnitInput(gold(rels), nodes(cs), es, pp, cl)


# ------------------------------------------------------------ relation macro
def test_macro_perfect_and_wrong_class_and_no_prediction():
    rows = [{"gold": "uses", "pred": "uses", "outcome": "edge", "direction_ok": True}, {"gold": "uses", "pred": "requires", "outcome": "edge", "direction_ok": None},
            {"gold": "requires", "pred": HL.NO_PREDICTION, "outcome": "other", "direction_ok": None}, {"gold": "is_a", "pred": "is_a", "outcome": "edge", "direction_ok": True}]  # fmt: skip
    m = HL.macro_from_rows(rows)
    c = m["classes"]
    assert (c["uses"]["tp"], c["uses"]["fp"], c["uses"]["fn"]) == (1, 0, 1)
    assert (c["requires"]["tp"], c["requires"]["fp"], c["requires"]["fn"]) == (
        0,
        1,
        1,
    )  # one wrong prediction counted against it, one gold missed
    assert c["is_a"]["f1"] == 1.0
    assert m["macro_f1"] == pytest.approx((2 * 1 * 0.5 / 1.5 + 0.0 + 1.0) / 3)
    assert m["no_prediction_by_outcome"] == {"other": 1}


def test_no_relation_other_rejected_are_false_negatives_and_create_no_false_positive():
    rows = [
        {"gold": "uses", "pred": HL.NO_PREDICTION, "outcome": o, "direction_ok": None}
        for o in ("other", "no_relation", "rejected")
    ]
    m = HL.macro_from_rows(rows)
    assert (
        m["classes"]["uses"]["fn"] == 3 and m["classes"]["uses"]["fp"] == 0 and m["macro_f1"] == 0.0
    )
    assert set(m["classes"]) == {"uses"}  # no ontology class received a false positive


def test_macro_averages_only_classes_with_gold_support_and_flags_low_support():
    rows = [{"gold": "uses", "pred": "uses", "outcome": "edge", "direction_ok": True}] * 4 + [
        {"gold": "uses", "pred": "part_of", "outcome": "edge", "direction_ok": None}
    ]
    m = HL.macro_from_rows(rows)
    assert (
        "part_of" in m["classes"]
        and m["classes"]["part_of"]["support"] == 0
        and m["classes_in_macro"] == 1
    )  # predicted-only class is not in the macro mean
    assert m["classes"]["uses"]["low_support"] is False
    assert (
        HL.macro_from_rows(
            [{"gold": "a", "pred": "a", "outcome": "edge", "direction_ok": True}] * 3
        )["classes"]["a"]["low_support"]
        is True
    )


def test_empty_population_is_not_evaluable_not_zero():
    assert HL.macro_from_rows([])["macro_f1"] is None


def test_relation_rows_population_direction_and_outcomes():
    u = unit(
        [("A", "uses", "B"), ("A", "requires", "C"), ("A", "is_a", "D"), ("B", "part_of", "E")],
        edges=[("A", "uses", "B")],
        proposed=[("A", "B"), ("A", "C"), ("D", "A")],
        classifier={
            ("A", "B"): [res("A", "B", "edge", "uses")],
            ("A", "C"): [res("A", "C", "other")],
            ("A", "D"): [res("A", "D", "rejected")],
        },
    )
    rows = HL.relation_rows(u, symmetric=set())
    by = {r["gold"]: r for r in rows}
    assert set(by) == {
        "uses",
        "requires",
        "is_a",
    }  # (B, E) never reached the classifier: excluded (Pair Recall failure)
    assert by["uses"]["pred"] == "uses" and by["uses"]["direction_ok"] is True
    assert by["requires"]["pred"] == HL.NO_PREDICTION and by["requires"]["outcome"] == "other"
    assert by["is_a"]["outcome"] == "rejected"


def test_wrong_direction_is_a_diagnostic_not_a_label_error():
    u = unit(
        [("A", "uses", "B")],
        [("B", "uses", "A")],
        [("A", "B")],
        {("A", "B"): [res("A", "B", "edge", "uses", swap=True)]},
    )
    r = HL.relation_rows(u, symmetric=set())[0]
    assert r["pred"] == "uses" and r["direction_ok"] is False
    assert HL.macro_from_rows([r])["macro_f1"] == 1.0  # label correct
    assert (
        HL.relation_rows(u, symmetric={"uses"})[0]["direction_ok"] is True
    )  # symmetric relations ignore orientation


def test_gold_pair_with_missing_endpoint_is_excluded_from_the_relation_population():
    u = unit(
        [("A", "uses", "B")],
        [],
        [("A", "B")],
        {("A", "B"): [res("A", "B", "edge", "uses")]},
        cs="A",
    )  # B was never discovered
    assert HL.relation_rows(u, set()) == []


# ------------------------------------------------------------ evaluator wiring and reuse
def test_evaluate_reuses_frozen_strict_pair_and_concept_scorers():
    u = unit(
        [("A", "uses", "B"), ("C", "requires", "D")],
        [("A", "uses", "B"), ("A", "uses", "E")],
        [("A", "B"), ("A", "E")],
        {("A", "B"): [res("A", "B", "edge", "uses")], ("A", "E"): [res("A", "E", "edge", "uses")]},
    )
    out = HL.evaluate({"s": u}, set(), boot=False)
    ref = S.score_graph_unit(u.gold, u.nodes, u.edges, set(), proposed_pairs=u.proposed_pairs)
    h = out["headline"]
    assert (
        (
            h["strict_e2e_edge_f1"]["tp"],
            h["strict_e2e_edge_f1"]["fp"],
            h["strict_e2e_edge_f1"]["fn"],
        )
        == (ref["strict_e2e_edge"].tp, ref["strict_e2e_edge"].fp, ref["strict_e2e_edge"].fn)
        == (1, 1, 1)
    )
    assert (h["concept_f1"]["tp"], h["concept_f1"]["fp"], h["concept_f1"]["fn"]) == (
        ref["canonical_node"].tp,
        ref["canonical_node"].fp,
        ref["canonical_node"].fn,
    )
    assert (
        h["pair_recall"]["reached"] == ref["pair_recall"]["reached_classification"]
        and h["pair_recall"]["denominator"] == ref["pair_recall"]["denominator"]
    )
    assert set(h) == {
        "concept_f1",
        "ancestor_hierarchy_f1",
        "pair_recall",
        "relation_macro_f1",
        "strict_e2e_edge_f1",
    }
    assert (
        "legacy" in out["diagnostics"]
        and "canonical_node_typed" in out["diagnostics"]["legacy"]["s"]
        and "relation_conditional" in out["diagnostics"]["legacy"]["s"]
    )


def test_pair_recall_is_unordered_and_excludes_missing_endpoints():
    u = unit(
        [("A", "uses", "B"), ("C", "uses", "D")], [], [("B", "A")], {}, cs="ABC"
    )  # proposed as (B, A); D has no node
    p = HL.evaluate({"s": u}, set(), boot=False)["headline"]["pair_recall"]
    assert (p["reached"], p["denominator"], p["missing_endpoint_excluded"]) == (1, 1, 1) and p[
        "recall"
    ] == 1.0


def test_hierarchy_is_not_evaluable_without_hierarchy_gold_and_never_zero():
    u = unit([("A", "uses", "B")], [], [("A", "B")], {("A", "B"): [res("A", "B", "edge", "uses")]})
    h = HL.evaluate({"s": u}, set(), boot=False)["headline"]["ancestor_hierarchy_f1"]
    assert h == {
        "status": "NOT_EVALUABLE",
        "reason": "HIERARCHY_GOLD_GAP",
        "f1": None,
        "ci95": None,
    }


def test_hierarchy_scored_when_gold_has_is_a():
    u = unit(
        [("A", "is_a", "B"), ("B", "is_a", "C")],
        [("A", "is_a", "B")],
        [("A", "B")],
        {("A", "B"): [res("A", "B", "edge", "is_a")]},
    )
    h = HL.evaluate({"s": u}, set(), boot=False)["headline"]["ancestor_hierarchy_f1"]
    assert h["status"] == "OK" and (h["tp"], h["fp"], h["fn"]) == (1, 0, 2)


def test_section_bootstrap_matches_the_frozen_cr012_recipe():
    per = {f"u{i}": PRF(i + 1, 3, 4) for i in range(12)}
    mine = HL.bootstrap(HL._prf_stat(per, "f1"), list(per))
    ref = B.cluster_bootstrap(per)
    assert mine["ci95"] == pytest.approx(ref["ci"]["f1"]) and mine["ci_status"] == "OK"
    small = HL.bootstrap(HL._prf_stat({k: per[k] for k in list(per)[:7]}, "f1"), list(per)[:7])
    assert small["ci_status"] == "NOT_EVALUABLE_SMALL_N"


def test_composite_score_is_disabled_in_config():
    cfg = HL.load_config()
    assert (
        cfg["headline"]["composite_score"] is False
        and cfg["concept_f1"]["variant"] == "canonical_node_untyped"
        and cfg["hierarchy"]["relations"] == ["is_a"]
    )


# ------------------------------------------------------------ regression against the frozen CR-012 held-out results
FROZEN = Path("reports/cr012/stop4_heldout_results.json")
RUNS = Path("data/processed/kg/cr012_heldout_4_4_E0/checkpoint.json")


@pytest.mark.skipif(
    not (FROZEN.exists() and RUNS.exists()), reason="frozen CR-012 artefacts absent"
)
def test_reproduces_the_frozen_cr012_headline_numbers_exactly():
    from cumap.cr017.run import evaluate_run

    out = evaluate_run("heldout", "E0", boot=False)
    ref = json.loads(FROZEN.read_text())["pd"]["levels"]["E0"]
    h = out["headline"]
    assert (
        h["strict_e2e_edge_f1"]["tp"],
        h["strict_e2e_edge_f1"]["fp"],
        h["strict_e2e_edge_f1"]["fn"],
    ) == (
        ref["pooled_strict_e2e"]["tp"],
        ref["pooled_strict_e2e"]["fp"],
        ref["pooled_strict_e2e"]["fn"],
    )
    assert (h["concept_f1"]["tp"], h["concept_f1"]["fp"], h["concept_f1"]["fn"]) == (
        ref["pooled_canonical_node"]["tp"],
        ref["pooled_canonical_node"]["fp"],
        ref["pooled_canonical_node"]["fn"],
    )
    assert (
        h["pair_recall"]["reached"],
        h["pair_recall"]["denominator"],
        h["pair_recall"]["missing_endpoint_excluded"],
    ) == (
        ref["pair_recall_pooled"]["reached"],
        ref["pair_recall_pooled"]["reachable_denominator"],
        ref["pair_recall_pooled"]["missing_endpoint_excluded"],
    )
    assert h["strict_e2e_edge_f1"]["f1"] == pytest.approx(ref["pooled_strict_e2e"]["f1"])
    rc = ref["relation_given_correct_endpoints_pooled"]
    leg = out["diagnostics"]["legacy"]
    assert (
        sum(v["relation_conditional"].get("gold_with_proposed_edge", 0) for v in leg.values())
        == rc["gold_with_proposed_edge"]
    )

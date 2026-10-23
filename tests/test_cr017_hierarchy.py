"""CR-017 STOP 2: Ancestor Hierarchy F1 fixtures (no model, no network)."""

import pytest

from cumap.cr012.types import GoldConcept, GoldMention, GoldRelation, PredEdge, PredNode, UnitGold
from cumap.cr017 import hierarchy as H

SPANS = {c: (i * 10, i * 10 + 3) for i, c in enumerate("ABCDE")}


def gold(rels: list[tuple[str, str, str]], concepts: str = "ABCDE") -> UnitGold:
    return UnitGold(
        unit="s",
        mentions=[GoldMention("s", SPANS[c], "Concept", c) for c in concepts],
        concepts=[GoldConcept(c, "s", c, "Concept") for c in concepts],
        relations=[GoldRelation("s", r, src_concept=a, tgt_concept=b) for a, r, b in rels],
    )


def pred(
    nodes: str,
    rels: list[tuple[str, str, str]],
    extra_nodes: dict[str, tuple[int, int]] | None = None,
):
    ns = [PredNode(f"n{c}", "s", "Concept", c, (SPANS[c],)) for c in nodes]
    ns += [PredNode(k, "s", "Concept", k, (sp,)) for k, sp in (extra_nodes or {}).items()]
    es = [
        PredEdge(
            "s",
            a if a.startswith(("n", "x")) else f"n{a}",
            b if b.startswith(("n", "x")) else f"n{b}",
            r,
        )
        for a, r, b in rels
    ]
    return ns, es


def score(g: UnitGold, nodes, edges):
    return H.score_hierarchy_unit(g, nodes, edges)


def test_exact_hierarchy_gets_full_credit():
    g = gold([("A", "is_a", "B"), ("B", "is_a", "C")])
    r = score(g, *pred("ABC", [("A", "is_a", "B"), ("B", "is_a", "C")]))
    assert (
        r["ancestor_hierarchy"].precision,
        r["ancestor_hierarchy"].recall,
        r["ancestor_hierarchy"].f1,
    ) == (1.0, 1.0, 1.0)
    assert r["gold_ancestor_pairs"] == 3 and r["gold_direct_edges"] == 2  # (A,B) (B,C) (A,C)


def test_skipped_direct_parent_gets_ancestor_credit_but_misses_the_parent_pair():
    g = gold([("A", "is_a", "B"), ("B", "is_a", "C")])
    r = score(g, *pred("ABC", [("A", "is_a", "C")]))
    h = r["ancestor_hierarchy"]
    assert (h.tp, h.fp, h.fn) == (1, 0, 2)  # (A,C) credited; (A,B) and (B,C) missed
    d = r["direct_parent_diagnostic"]
    assert (d.tp, d.fp, d.fn) == (0, 1, 2)  # direct-parent scoring would have given nothing


def test_false_ancestor_is_a_false_positive():
    g = gold([("A", "is_a", "B"), ("B", "is_a", "C")])
    r = score(g, *pred("ABCD", [("A", "is_a", "B"), ("B", "is_a", "C"), ("A", "is_a", "D")]))
    h = r["ancestor_hierarchy"]
    assert (h.tp, h.fp, h.fn) == (3, 1, 0)


def test_missing_concept_loses_all_its_gold_pairs():
    g = gold([("A", "is_a", "B"), ("B", "is_a", "C")])
    r = score(g, *pred("AC", [("A", "is_a", "C")]))  # B was never discovered
    h = r["ancestor_hierarchy"]
    assert (h.tp, h.fp, h.fn) == (1, 0, 2)
    assert r["gold_pairs_with_an_endpoint_concept_absent_from_prediction"] == 2


def test_wrong_canonical_concept_gets_no_partial_credit():
    g = gold([("A", "is_a", "B")])
    r = score(g, *pred("ACB", [("A", "is_a", "C")]))  # right child, wrong parent
    h = r["ancestor_hierarchy"]
    assert (h.tp, h.fp, h.fn) == (0, 1, 1)


def test_only_the_frozen_relation_set_counts():
    g = gold([("A", "is_a", "B"), ("A", "part_of", "C"), ("B", "uses", "C")])
    assert H.gold_pairs(g).pairs == {("A", "B")}
    r = score(
        g,
        *pred(
            "ABC",
            [
                ("A", "is_a", "B"),
                ("A", "part_of", "C"),
                ("B", "requires", "C"),
                ("C", "has_property", "A"),
            ],
        ),
    )
    assert r["ancestor_hierarchy"].f1 == 1.0 and r["predicted_is_a_edges"] == 1


def test_instantiates_is_not_a_hierarchy_relation():
    assert "instantiates" not in H.HIERARCHY_RELATIONS and H.HIERARCHY_RELATIONS == {"is_a"}


def test_unmapped_predicted_node_pairs_can_only_be_false_positives():
    g = gold([("A", "is_a", "B")])
    ns, es = pred(
        "AB", [("A", "is_a", "B"), ("A", "is_a", "xZ")], extra_nodes={"xZ": (900, 903)}
    )  # xZ matches no gold concept
    r = score(g, ns, es)
    h = r["ancestor_hierarchy"]
    assert (h.tp, h.fp, h.fn) == (1, 1, 0) and r["nodes_in_hierarchy_without_a_gold_concept"] == 1


def test_false_merged_node_maps_to_nothing():
    g = gold([("A", "is_a", "B")])
    merged = PredNode(
        "nAB", "s", "Concept", "AB", (SPANS["A"], SPANS["B"])
    )  # one node covering two gold concepts
    r = score(
        g,
        [merged, PredNode("nC", "s", "Concept", "C", (SPANS["C"],))],
        [PredEdge("s", "nAB", "nC", "is_a")],
    )
    assert (
        r["ancestor_hierarchy"].tp == 0
        and r["ancestor_hierarchy"].fp == 1
        and r["ancestor_hierarchy"].fn == 1
    )


def test_split_node_cannot_add_duplicate_pairs():
    g = gold([("A", "is_a", "B")])
    a2 = PredNode(
        "nA2", "s", "Concept", "A2", (SPANS["A"],)
    )  # a second node for the same gold concept (a split)
    ns, es = pred("AB", [("A", "is_a", "B")])
    es.append(PredEdge("s", "nA2", "nB", "is_a"))
    r = score(g, [*ns, a2], es)
    h = r["ancestor_hierarchy"]
    assert (h.tp, h.fp, h.fn) == (1, 0, 0)


def test_cycle_is_detected_reported_and_closure_terminates():
    g = gold([("A", "is_a", "B")])
    r = score(g, *pred("ABC", [("A", "is_a", "B"), ("B", "is_a", "C"), ("C", "is_a", "A")]))
    assert r["predicted_cycles"] == [["A", "B", "C"]]
    cl = H.ancestor_closure({("A", "B"), ("B", "C"), ("C", "A")})
    assert cl.pairs == {
        ("A", "B"),
        ("A", "C"),
        ("B", "C"),
        ("B", "A"),
        ("C", "A"),
        ("C", "B"),
    }  # no (X, X) pair, bounded
    assert all(a != b for a, b in cl.pairs)


def test_cycle_handling_is_deterministic_and_each_cycle_reported_once():
    edges = {("A", "B"), ("B", "A"), ("C", "D"), ("D", "E"), ("E", "C")}
    first = [H.ancestor_closure(edges) for _ in range(3)]
    assert all(c.pairs == first[0].pairs and c.cycles == first[0].cycles for c in first)
    assert first[0].cycles == [("A", "B"), ("C", "D", "E")]


def test_self_loop_is_dropped_and_counted():
    cl = H.ancestor_closure({("A", "A"), ("A", "B")})
    assert cl.pairs == {("A", "B")} and cl.self_pairs_dropped == 1


def test_gold_without_hierarchy_has_no_pairs_and_zero_scores():
    g = gold([("A", "part_of", "B")])
    r = score(g, *pred("AB", [("A", "is_a", "B")]))
    h = r["ancestor_hierarchy"]
    assert (h.tp, h.fp, h.fn) == (0, 1, 0) and r["gold_ancestor_pairs"] == 0


def test_pooling_adds_counts_across_sections():
    g = gold([("A", "is_a", "B")])
    one = score(g, *pred("AB", [("A", "is_a", "B")]))
    two = score(g, *pred("AB", []))
    p = H.pool({"s1": one, "s2": two})
    assert (p.tp, p.fp, p.fn) == (1, 0, 1)


def test_real_gold_has_no_cycles_and_expected_support():
    from cumap.cr012 import pd_e2e as PD

    secs = {r["section_id"]: r["text"] for r in PD.load_sections()}
    try:
        gold_by, problems = PD.load_gold(
            __import__("pathlib").Path("data/gold/pd_e2e_test_blind.csv"), secs, PD.registry()
        )
    except FileNotFoundError:
        pytest.skip("local gold absent")
    assert not problems
    pairs = sum(len(H.gold_pairs(g).pairs) for g in gold_by.values())
    edges = sum(len(H.gold_pairs(g).direct_edges) for g in gold_by.values())
    assert edges == 64 and pairs == 75 and all(not H.gold_pairs(g).cycles for g in gold_by.values())

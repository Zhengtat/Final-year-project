"""CR-022 Part A scorers on small fixtures: hierarchy-set filtering, surface pseudo-node closure with a cycle, macro F1 with a low-support class,
unplaced edges as false positives, and the Part B mapping (direction swap, unmapped / not-approved labels). No network, no model."""

from collections import Counter

from cumap.cr012.types import GoldMention, GoldRelation, UnitGold
from cumap.cr017 import headline as HL
from cumap.cr022 import scoring as C
from cumap.cr022.mapping import MapEntry, apply_mapping

SYM = {"compareWith"}


class FakeDoc:
    """Characters are token spans scaled by one: token i is character i (text is a string of one-char tokens)."""

    def __init__(self, text: str):
        self.text = text

    def span_to_chars(self, sp):
        return sp


def gold(rels, mentions):
    return UnitGold(
        "u",
        mentions=[GoldMention("u", s, "method") for s in mentions],
        relations=[GoldRelation("u", r, src_span=a, tgt_span=b) for a, b, r in rels],
    )


A, B, Cc, D = (0, 1), (1, 2), (2, 3), (3, 4)


def placed(rels, unplaced=None, mentions=(A, B, Cc, D)):
    return C.Placed(
        [(a, b, r, "method", "method") for a, b, r in rels],
        [(m, "method") for m in mentions],
        Counter(unplaced or {}),
    )


def test_hierarchy_set_filtering_changes_both_gold_and_prediction():
    g = gold([(A, B, "subclassOf"), (B, Cc, "subtaskOf"), (A, Cc, "UsedFor")], [A, B, Cc])
    p = placed([(A, B, "subclassOf"), (B, Cc, "subtaskOf"), (A, Cc, "UsedFor")])
    h2, h1 = C.HIER_SETS["H2 {subclassOf, subtaskOf}"], C.HIER_SETS["H1 {subclassOf}"]
    r2 = C.direct_relation_prf(g, p, SYM, "IDX-P1", h2)
    r1 = C.direct_relation_prf(g, p, SYM, "IDX-P1", h1)
    assert (r2.tp, r2.fp, r2.fn) == (2, 0, 0) and (r1.tp, r1.fp, r1.fn) == (1, 0, 0)
    assert C.direct_relation_prf(g, p, SYM, "IDX-P1", None).tp == 3


def test_unplaced_edges_are_false_positives_by_label_except_in_frozen():
    g = gold([(A, B, "subclassOf")], [A, B])
    p = placed([(A, B, "subclassOf")], {"subclassOf": 2, "UsedFor": 1})
    h = C.HIER_SETS["H1 {subclassOf}"]
    assert C.direct_relation_prf(g, p, SYM, "FROZEN", h).fp == 0
    assert (
        C.direct_relation_prf(g, p, SYM, "IDX-P1", h).fp == 2
    )  # only the hierarchy-labelled unplaced edges
    assert C.direct_relation_prf(g, p, SYM, "IDX-P1", None).fp == 3


def test_surface_pseudo_nodes_merge_repeated_surfaces_and_close_the_hierarchy():
    doc = FakeDoc("xyxz")  # tokens: x y x z  (spans 0 and 2 share the surface "x")
    g = gold(
        [((0, 1), (1, 2), "subclassOf"), ((1, 2), (3, 4), "subclassOf")],
        [(0, 1), (1, 2), (2, 3), (3, 4)],
    )
    # prediction links the SECOND occurrence of x to y, and y to z: surfaces make it the same pair
    p = placed([((2, 3), (1, 2), "subclassOf"), ((1, 2), (3, 4), "subclassOf")])
    r = C.surface_hierarchy(doc, g, p, "IDX-P1", C.HIER_SETS["H1 {subclassOf}"])
    assert (
        r["gold_mentions"] == 4
        and r["gold_surface_nodes"] == 3
        and r["gold_surface_collisions"] == 1
    )
    assert (
        r["gold_closure_pairs"] == 3 and r["gold_pairs_added_by_closure"] == 1
    )  # x<y<z adds (x, z)
    # the prediction's second "x" and the gold's first "x" are one surface, and closure adds (x, z) on both sides
    assert (r["prf"].tp, r["prf"].fp, r["prf"].fn) == (3, 0, 0) and r["pred_closure_pairs"] == 3


def test_a_cycle_is_reported_and_closure_terminates():
    doc = FakeDoc("abc")
    g = gold([((0, 1), (1, 2), "subclassOf"), ((1, 2), (0, 1), "subclassOf")], [(0, 1), (1, 2)])
    p = placed([((0, 1), (1, 2), "subclassOf")])
    r = C.surface_hierarchy(doc, g, p, "IDX-P1", C.HIER_SETS["H1 {subclassOf}"])
    assert r["gold_cycles"] == [["a", "b"]] and r["pred_cycles"] == []
    assert r["gold_closure_pairs"] == 2 and r["prf"].tp == 1 and r["prf"].fn == 1


def test_unplaced_hierarchy_edges_add_false_positive_pairs_to_the_ancestor_score():
    doc = FakeDoc("ab")
    g = gold([((0, 1), (1, 2), "subclassOf")], [(0, 1), (1, 2)])
    p = placed([((0, 1), (1, 2), "subclassOf")], {"subclassOf": 2, "UsedFor": 5})
    h = C.HIER_SETS["H1 {subclassOf}"]
    assert C.surface_hierarchy(doc, g, p, "FROZEN", h)["prf"].fp == 0
    r = C.surface_hierarchy(doc, g, p, "IDX-P1", h)
    assert r["prf"].fp == 2 and r["unplaced_counted_as_fp"] == 2


def test_macro_rows_use_endpoint_placed_gold_only_and_flag_low_support_classes():
    g = gold([(A, B, "UsedFor"), (Cc, D, "compareWith"), (A, D, "partOf")], [A, B, Cc, D])
    p = placed([(A, B, "UsedFor"), (D, Cc, "compareWith")], mentions=(A, B, Cc, D))
    rows = C.relation_rows(FakeDoc("abcd"), g, p, SYM)
    assert [(r["gold"], r["pred"]) for r in rows] == [
        ("UsedFor", "UsedFor"),
        ("compareWith", "compareWith"),
        ("partOf", HL.NO_PREDICTION),
    ]
    assert rows[1]["direction_ok"] is True  # symmetric: reversed endpoints still count
    m = C.pooled_macro(rows)
    assert m["classes"]["partOf"]["low_support"] is True and m["classes"]["partOf"]["f1"] == 0.0
    assert abs(m["macro_f1"] - 2 / 3) < 1e-9


def test_gold_whose_endpoint_is_not_a_predicted_mention_is_outside_the_population():
    g = gold([(A, B, "UsedFor"), (Cc, D, "UsedFor")], [A, B, Cc, D])
    p = placed([(A, B, "UsedFor")], mentions=(A, B))
    assert len(C.relation_rows(FakeDoc("abcd"), g, p, SYM)) == 1


def test_mapping_applies_only_approved_entries_with_direction_swap_and_counts_the_rest():
    m = {
        "subclassOf": MapEntry("is_a", False, "clean", "approved"),
        "enhancedBy": MapEntry("uses", True, "close", "approved"),
        "UsedFor": MapEntry("has_purpose", False, "clean", "draft"),
        "MeasuredBy": MapEntry(None, False, "unmapped", "approved"),
    }
    rels = [
        ("a", "b", "subclassOf"),
        ("c", "d", "enhancedBy"),
        ("e", "f", "UsedFor"),
        ("g", "h", "MeasuredBy"),
        ("i", "j", "similarWith"),
    ]
    out, excl = apply_mapping(rels, m)
    assert out == [("a", "b", "is_a"), ("d", "c", "uses")]
    assert excl == Counter(
        {"not_approved:UsedFor": 1, "unmapped:MeasuredBy": 1, "unmapped:similarWith": 1}
    )

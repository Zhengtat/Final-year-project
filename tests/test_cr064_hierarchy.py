"""CR-064 Hierarchy F1 breakdown (`cumap.cr064.hierarchy`) on small fixtures. No network, no model."""

from collections import Counter

from cumap.cr012.types import PRF, GoldMention, GoldRelation, UnitGold
from cumap.cr022 import scoring as C
from cumap.cr064 import hierarchy as H

A, B, Cc, D, E = (0, 1), (1, 2), (2, 3), (3, 4), (4, 5)


def gold(rels, mentions):
    return UnitGold(
        "u",
        mentions=[GoldMention("u", s, "method") for s in mentions],
        relations=[GoldRelation("u", r, src_span=a, tgt_span=b) for a, b, r in rels],
    )


def placed(rels, mentions, unplaced=None):
    return C.Placed(
        [(a, b, r, "method", "method") for a, b, r in rels],
        [(m, "method") for m in mentions],
        Counter(unplaced or {}),
    )


def test_gold_outcomes_split_every_hierarchy_relation_once():
    g = gold(
        [(A, B, "subtaskOf"), (B, Cc, "subclassOf"), (Cc, D, "subclassOf"), (D, A, "subtaskOf"),
         (A, E, "subclassOf"), (B, D, "UsedFor")],
        [A, B, Cc, D, E],
    )  # fmt: skip
    p = placed([(A, B, "subclassOf"), (Cc, B, "subtaskOf"), (Cc, D, "similarWith")], [A, B, Cc, D])
    out, conf = H.gold_outcomes(g, p)
    assert out == {"hit": 1, "hit_needs_label_merge": 1, "miss_reversed": 1,
                   "miss_other_relation": 1, "miss_no_edge_at_pair": 1,
                   "miss_endpoint_not_extracted": 1}  # fmt: skip
    assert conf == {"subclassOf -> similarWith": 1}


def test_false_links_by_what_gold_has_at_the_pair():
    g = gold([(A, B, "subclassOf"), (Cc, D, "partOf")], [A, B, Cc, D])
    p = placed(
        [(A, B, "subtaskOf"), (B, A, "subclassOf"), (Cc, D, "subclassOf"), (A, D, "subtaskOf"),
         (B, Cc, "UsedFor")],
        [A, B, Cc, D],
        {"subclassOf": 2, "UsedFor": 1},
    )  # fmt: skip
    assert H.false_links(g, p) == {"reverse of a gold hierarchy relation": 1, "gold partOf": 1,
                                   "no gold relation at pair": 1, "unplaced": 2}  # fmt: skip
    assert sum(H.false_links(g, p).values()) == C.hierarchy_direction_prf(g, p, "IDX-P1", H.H2).fp


def test_bootstrap_interval_brackets_the_pooled_f1_and_is_seeded():
    per = [PRF(1, 1, 1), PRF(0, 2, 1), PRF(2, 0, 1), PRF(1, 0, 0)]
    lo, hi = H.bootstrap_f1(per, n=2000)
    assert lo <= H.pool(per).f1 <= hi and (lo, hi) == H.bootstrap_f1(per, n=2000)

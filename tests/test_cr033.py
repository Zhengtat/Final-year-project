"""CR-033: concept-level fact F1 `FACT-C1-SURF-R1` (no network, no key)."""

from test_cr032 import _doc

from cumap.cr012.types import GoldMention, GoldRelation, UnitGold
from cumap.cr032 import scinlp_t1 as ST
from cumap.cr033 import fact_f1 as F

TEXT = "prefix-tuning uses adapter . Prefixtuning uses adapter . prefix-tuning uses adapter . bert is similar to roberta . roberta is similar to bert ."


def _setup():
    doc = _doc("p", TEXT)
    ident, _ = ST.r1_identity(doc)
    t = doc.tokens
    spans = [(i, i + 1) for i in range(len(t))]
    return doc, ident, t, spans


def _gold(rels, doc):
    ms = sorted({sp for r in rels for sp in (r.src_span, r.tgt_span)})
    return UnitGold("p", mentions=[GoldMention("p", sp, "T") for sp in ms], relations=rels)


def test_a_relation_marked_in_three_sentences_is_one_gold_fact_and_one_predicted_edge_matches_once():
    doc, ident, t, _ = _setup()
    pt, ad = (
        [i for i, x in enumerate(t) if x.lower().startswith("prefix")],
        [i for i, x in enumerate(t) if x == "adapter"],
    )
    rels = [
        GoldRelation("p", "uses", src_span=(a, a + 1), tgt_span=(b, b + 1))
        for a, b in zip(pt, ad, strict=True)
    ]
    g = _gold(rels, doc)
    assert (
        len(F.gold_facts(g, ident, set())) == 1
    )  # 3 mentions, one fact (Prefixtuning = prefix-tuning by R1)
    pred = [(r.src_span, r.tgt_span, "uses", "T", "T") for r in rels[:1]]
    r = F.fact_score(g, pred, 0, "IDX-P1", ident, set())
    assert (
        (r["prf"].tp, r["prf"].fp, r["prf"].fn) == (1, 0, 0)
        and r["gold_facts"] == 1
        and r["gold_mention_relations"] == 3
    )
    # the same edge projected onto all three mentions is still one predicted fact
    r3 = F.fact_score(
        g, [(x.src_span, x.tgt_span, "uses", "T", "T") for x in rels], 0, "IDX-P1", ident, set()
    )
    assert r3["pred_facts"] == 1 and r3["prf"].tp == 1 and r3["prf"].fp == 0


def test_prefix_tuning_and_prefixtuning_are_one_pseudo_node():
    _, ident, t, _ = _setup()
    a, b = t.index("prefix-tuning"), t.index("Prefixtuning")
    assert ident((a, a + 1)) == ident((b, b + 1))


def test_symmetric_relation_matches_either_direction():
    doc, ident, t, _ = _setup()
    b1, r1 = (t.index("bert"), t.index("bert") + 1), (t.index("roberta"), t.index("roberta") + 1)
    g = _gold([GoldRelation("p", "similar", src_span=b1, tgt_span=r1)], doc)
    rev = [(r1, b1, "similar", "T", "T")]
    assert F.fact_score(g, rev, 0, "IDX-P1", ident, {"similar"})["prf"].tp == 1
    assert (
        F.fact_score(g, rev, 0, "IDX-P1", ident, set())["prf"].tp == 0
    )  # directed: reversed is wrong


def test_an_unmapped_predicted_node_gives_only_false_positives_and_a_missing_gold_node_loses_its_facts():
    doc, ident, t, _ = _setup()
    a, u = (
        (t.index("prefix-tuning"), t.index("prefix-tuning") + 1),
        (t.index("adapter"), t.index("adapter") + 1),
    )
    g = _gold([GoldRelation("p", "uses", src_span=a, tgt_span=u)], doc)
    other = (t.index("similar"), t.index("similar") + 1)  # a surface that is not a gold concept
    r = F.fact_score(g, [(a, other, "uses", "T", "T")], 0, "IDX-P1", ident, set())
    assert (r["prf"].tp, r["prf"].fp, r["prf"].fn) == (0, 1, 1) and r[
        "pred_facts_with_synthetic_concept"
    ] == 1
    r0 = F.fact_score(g, [], 0, "IDX-P1", ident, set())
    assert (r0["prf"].tp, r0["prf"].fn) == (0, 1)


def test_evidence_match_share_and_unplaced_policy():
    doc, ident, t, _ = _setup()
    pts = [i for i, x in enumerate(t) if x.lower().startswith("prefix")]
    ad = [i for i, x in enumerate(t) if x == "adapter"]
    gold_rel = GoldRelation("p", "uses", src_span=(pts[0], pts[0] + 1), tgt_span=(ad[0], ad[0] + 1))
    g = _gold([gold_rel], doc)
    same_spans = [((pts[0], pts[0] + 1), (ad[0], ad[0] + 1), "uses", "T", "T")]
    other_sentence = [((pts[1], pts[1] + 1), (ad[1], ad[1] + 1), "uses", "T", "T")]
    a = F.pool({"p": F.fact_score(g, same_spans, 0, "IDX-P1", ident, set())})
    b = F.pool({"p": F.fact_score(g, other_sentence, 0, "IDX-P1", ident, set())})
    assert a["evidence_match_share"] == 1.0
    assert b["prf"].tp == 1 and b["evidence_match_share"] == 0.0  # right fact, different sentence
    assert F.fact_score(g, same_spans, 3, "FROZEN", ident, set())["prf"].fp == 0
    assert F.fact_score(g, same_spans, 3, "IDX-P1", ident, set())["prf"].fp == 3

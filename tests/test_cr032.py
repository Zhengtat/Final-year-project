"""CR-032: HIER-T1 broader hierarchy F1 (no network, no key)."""

import pytest

from cumap.config import REPO_ROOT
from cumap.cr012.adapters import SciNLPDoc
from cumap.cr012.types import GoldMention, GoldRelation, PredEdge, PredNode, UnitGold
from cumap.cr017 import hierarchy as FH
from cumap.cr032 import hier_t1 as H
from cumap.cr032 import scinlp_t1 as ST
from cumap.schemas.relations import RelationRegistry

TYPED = frozenset({"part_of"})


def E(rel, a, b, pt=None):
    return (rel, pt, a, b)


def test_is_a_and_part_of_chains_are_closed_separately():
    c = H.closure(
        {
            E("is_a", "a", "b"),
            E("is_a", "b", "c"),
            E("part_of", "x", "y", "component"),
            E("part_of", "y", "z", "component"),
        },
        TYPED,
    )
    assert c.pairs == {("is_a", "a", "b"), ("is_a", "b", "c"), ("is_a", "a", "c"), ("part_of", "x", "y"), ("part_of", "y", "z"), ("part_of", "x", "z")}  # fmt: skip


def test_a_mixed_is_a_part_of_chain_gives_no_pair():
    c = H.closure({E("is_a", "a", "b"), E("part_of", "b", "c", "component")}, TYPED)
    assert c.pairs == {("is_a", "a", "b"), ("part_of", "b", "c")}  # no (a, c) pair


def test_part_of_component_then_phase_gives_no_pair():
    c = H.closure({E("part_of", "a", "b", "component"), E("part_of", "b", "c", "phase")}, TYPED)
    assert c.pairs == {("part_of", "a", "b"), ("part_of", "b", "c")}


def test_part_of_without_a_part_type_is_direct_only_and_never_chained():
    c = H.closure(
        {E("part_of", "a", "b"), E("part_of", "b", "c", "component"), E("part_of", "c", "d")}, TYPED
    )
    assert ("part_of", "a", "c") not in c.pairs and ("part_of", "b", "d") not in c.pairs
    assert c.direct_only_edges == 2 and ("part_of", "a", "b") in c.pairs


def test_untyped_relation_chains_as_one_when_not_typed():  # SciNLP partOf has no part type
    c = H.closure({E("partOf", "a", "b"), E("partOf", "b", "c")}, frozenset())
    assert ("partOf", "a", "c") in c.pairs


def test_unplaced_edges_are_false_positives_and_cycles_terminate():
    r = H.score_edges({E("is_a", "a", "b")}, {E("is_a", "a", "b")}, frozenset(), extra_fp=2)
    assert (r["prf"].tp, r["prf"].fp, r["prf"].fn) == (1, 2, 0)
    c = H.closure({E("is_a", "a", "b"), E("is_a", "b", "a")}, frozenset())
    assert c.cycles and ("is_a", "a", "b") in c.pairs


def _unit():
    g = UnitGold(
        "u",
        mentions=[GoldMention("u", (0, 3), "T", "c1"), GoldMention("u", (10, 13), "T", "c2"), GoldMention("u", (20, 23), "T", "c3")],
        relations=[
            GoldRelation("u", "is_a", src_concept="c1", tgt_concept="c2"),
            GoldRelation("u", "is_a", src_concept="c2", tgt_concept="c3"),
            GoldRelation("u", "part_of", src_concept="c1", tgt_concept="c3", qualifiers=(("part_type", "component"),)),
        ],
    )  # fmt: skip
    nodes = [PredNode("n1", "u", "T", "a", ((0, 3),)), PredNode("n2", "u", "T", "b", ((10, 13),)), PredNode("n3", "u", "T", "c", ((20, 23),)), PredNode("n9", "u", "T", "z", ((40, 43),))]  # fmt: skip
    edges = [
        PredEdge("u", "n1", "n2", "is_a"),
        PredEdge("u", "n2", "n9", "is_a"),
        PredEdge("u", "n1", "n3", "part_of"),
    ]
    return g, nodes, edges


def test_is_a_only_set_reproduces_the_frozen_cr017_result_exactly():
    g, nodes, edges = _unit()
    mine = H.pd_unit(g, nodes, edges, frozenset({"is_a"}), frozenset())
    frozen = FH.score_hierarchy_unit(g, nodes, edges)
    a, b = mine["prf"], frozen["ancestor_hierarchy"]
    assert (
        (a.tp, a.fp, a.fn) == (b.tp, b.fp, b.fn) == (1, 2, 2)
    )  # the node n9 maps to no gold concept: its pairs are false positives
    assert mine["gold_pairs"] == frozen["gold_ancestor_pairs"]


def test_t1_adds_part_of_pairs_and_reads_the_predicted_part_type():
    g, nodes, edges = _unit()
    pts = {("n1", "n3", "part_of"): "component"}
    r = H.pd_unit(g, nodes, edges, frozenset({"is_a", "part_of"}), TYPED, pts)
    assert r["per_relation"]["part_of"].tp == 1 and r["gold_pairs"] == 4
    r2 = H.pd_unit(
        g, nodes, edges, frozenset({"is_a", "part_of"}), TYPED
    )  # no predicted part type: direct only, still matches the direct gold pair
    assert r2["direct_only_edges"]["predicted"] == 1


def test_hierarchy_set_is_read_from_the_registry():
    v13 = RelationRegistry.from_yaml(REPO_ROOT / "configs/relations_v1.3.yaml")
    v14 = RelationRegistry.from_yaml(REPO_ROOT / "configs/relations_v1.4.yaml")
    assert H.hierarchy_relations(v13) == (frozenset({"is_a", "part_of"}), frozenset({"part_of"}))
    assert H.hierarchy_relations(v14)[0] == frozenset({"is_a", "part_of", "subtask_of"})
    names = H.hierarchy_relations(v13)[0]
    assert not names & {"precedes", "causes", "prerequisite_of"}


def _doc(key, text):
    toks = text.split()
    offs, pos = [], 0
    for t in toks:
        offs.append((pos, pos + len(t)))
        pos += len(t) + 1
    return SciNLPDoc(key, toks, [len(toks)], " ".join(toks), offs, len(toks))


def test_r1_pseudo_nodes_merge_prefix_tuning_variants_and_acronyms_only_within_a_paper():
    d1 = _doc(
        "p1",
        "We use prefix-tuning here . Prefixtuning works . A language model ( LM ) helps . The LM is large .",
    )
    ident, st = ST.r1_identity(d1)
    sp = lambda w, nth=0: [(i, i + 1) for i, t in enumerate(d1.tokens) if t == w][nth]
    assert ident(sp("prefix-tuning")) == ident(sp("Prefixtuning"))
    i_lm = ident(sp("LM"))
    long_form = (d1.tokens.index("language"), d1.tokens.index("model") + 1)
    assert st["acronym_pairs_merged"] == 1 and ident(long_form) == i_lm
    d2 = _doc(
        "p2", "The LM is small . A lemma model is odd ."
    )  # another paper: LM is not tied to 'language model' there
    ident2, st2 = ST.r1_identity(d2)
    assert st2["acronym_pairs_merged"] == 0
    assert ident2((1, 2)) != ident(long_form)


def test_scinlp_unit_counts_unplaced_edges_as_fp_except_frozen():
    g = UnitGold(
        "p",
        mentions=[],
        relations=[GoldRelation("p", "subclassOf", src_span=(0, 1), tgt_span=(2, 3))],
    )
    doc = _doc("p", "cat is animal")
    ident = ST.surface_identity(doc)
    rels = [((0, 1), (2, 3), "subclassOf", "T", "T")]
    labs = frozenset({"subclassOf"})
    assert ST.scinlp_unit(g, rels, {"subclassOf": 2}, "FROZEN", labs, ident)["prf"].fp == 0
    assert ST.scinlp_unit(g, rels, {"subclassOf": 2}, "IDX-P1", labs, ident)["prf"].fp == 2


def test_identity_sheet_is_blind_never_overwrites_and_never_writes_gold(tmp_path):
    doc = _doc("p", "cat is animal")
    g = UnitGold(
        "p",
        relations=[
            GoldRelation("p", "subclassOf", src_span=(0, 1), tgt_span=(2, 3)),
            GoldRelation("p", "uses", src_span=(0, 1), tgt_span=(1, 2)),
        ],
    )
    out = tmp_path / "sheet.csv"
    assert ST.write_identity_sheet({"p": doc}, {"p": g}, frozenset({"subclassOf"}), out) == 2
    text = out.read_text()
    assert (
        "subclassOf" not in text
        and "uses" not in text
        and text.splitlines()[0].split(",")[0] == "row_id"
    )
    with pytest.raises(FileExistsError):
        ST.write_identity_sheet({"p": doc}, {"p": g}, frozenset({"subclassOf"}), out)
    with pytest.raises(ValueError):
        ST.write_identity_sheet(
            {"p": doc}, {"p": g}, frozenset({"subclassOf"}), tmp_path / "gold" / "s.csv"
        )
    marked = tmp_path / "marked.csv"
    marked.write_text(text.replace("cat,0-1,", "cat,0-1,").replace(",,\n", ",G1,\n", 1))
    marks = ST.load_identity_marks(marked)
    assert marks == {"p": {(0, 1): "G1"}}
    ident = ST.sheet_identity("p", marks)
    assert ident((0, 1)) == "g:G1" and ident((2, 3)) == "span:2-3"

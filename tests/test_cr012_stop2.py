"""CR-012 STOP 2: strict scorers, pair-recall denominator, oracles and leakage, attribution, bootstrap, stability, budget, adapter and
P&D-E2E tooling. Synthetic fixtures only for scoring; SciNLP dev/train bytes for the adapter round trip (the test split is never read)."""

import csv
import math
from pathlib import Path

import pytest

from cumap.cr012 import attribution as A
from cumap.cr012 import bootstrap as BS
from cumap.cr012 import oracle as O
from cumap.cr012 import pd_e2e as PD
from cumap.cr012 import scoring as S
from cumap.cr012 import stability as ST
from cumap.cr012.adapters import SCINLP_DIR, SciNLPAdapter, detokenise
from cumap.cr012.budget import pair_budget
from cumap.cr012.types import (
    PRF,
    GoldConcept,
    GoldMention,
    GoldRelation,
    PredEdge,
    PredNode,
    UnitGold,
)

FX = Path("tests/fixtures/cr012")
SYM = {"compareWith", "similarWith", "connected_to", "contrasts_with"}


def gold_graph():
    g = UnitGold("u")
    g.concepts = [
        GoldConcept("A", "u", "router", "Component"),
        GoldConcept("B", "u", "packet", "DataUnit"),
        GoldConcept("C", "u", "TCP", "Protocol"),
    ]
    g.mentions = [
        GoldMention("u", (0, 6), "Component", "A"),
        GoldMention("u", (30, 37), "DataUnit", "B"),
        GoldMention("u", (50, 53), "Protocol", "C"),
        GoldMention("u", (80, 83), "Protocol", "C"),
    ]
    g.relations = [
        GoldRelation("u", "acts_on", src_concept="A", tgt_concept="B"),
        GoldRelation("u", "uses", src_concept="A", tgt_concept="C"),
    ]
    return g


def nodes_ok():
    return [
        PredNode("n1", "u", "Component", "router", ((0, 6),)),
        PredNode("n2", "u", "DataUnit", "packet", ((30, 37),)),
        PredNode("n3", "u", "Protocol", "TCP", ((50, 53), (80, 83))),
    ]


# ---------------------------------------------------------------- strict E2E edge
def test_correct_endpoints_relation_and_direction_pass():
    r = S.score_graph_unit(
        gold_graph(),
        nodes_ok(),
        [PredEdge("u", "n1", "n2", "acts_on"), PredEdge("u", "n1", "n3", "uses")],
        SYM,
    )
    assert r["strict_e2e_edge"] == PRF(2, 0, 0)


def test_wrong_relation_and_reversed_directional_edges_fail():
    wrong = S.score_graph_unit(gold_graph(), nodes_ok(), [PredEdge("u", "n1", "n2", "uses")], SYM)[
        "strict_e2e_edge"
    ]
    rev = S.score_graph_unit(gold_graph(), nodes_ok(), [PredEdge("u", "n2", "n1", "acts_on")], SYM)[
        "strict_e2e_edge"
    ]
    assert (wrong.tp, rev.tp) == (0, 0) and wrong.fp == 1 and rev.fp == 1 and wrong.fn == 2


def test_reversed_symmetric_relation_passes():
    g = gold_graph()
    g.relations = [GoldRelation("u", "connected_to", src_concept="A", tgt_concept="B")]
    r = S.score_graph_unit(g, nodes_ok(), [PredEdge("u", "n2", "n1", "connected_to")], SYM)[
        "strict_e2e_edge"
    ]
    assert r.tp == 1 and r.fp == 0


def test_wrong_endpoint_type_fails_the_typed_headline():
    nodes = nodes_ok()
    nodes[1] = PredNode("n2", "u", "Component", "packet", ((30, 37),))
    typed = S.score_graph_unit(gold_graph(), nodes, [PredEdge("u", "n1", "n2", "acts_on")], SYM)[
        "strict_e2e_edge"
    ]
    untyped = S.score_graph_unit(
        gold_graph(), nodes, [PredEdge("u", "n1", "n2", "acts_on")], SYM, typed=False
    )["strict_e2e_edge"]
    assert typed.tp == 0 and untyped.tp == 1


def test_partial_span_does_not_match_a_gold_mention():
    nodes = nodes_ok()
    nodes[0] = PredNode("n1", "u", "Component", "router", ((0, 5),))  # one character short
    r = S.score_graph_unit(gold_graph(), nodes, [PredEdge("u", "n1", "n2", "acts_on")], SYM)
    assert r["strict_e2e_edge"].tp == 0 and r["alignment"]["unmatched_nodes"] == ["n1"]


# ---------------------------------------------------------------- canonicalisation / identity
def test_aliases_resolve_to_one_node_and_split_nodes_cost_precision():
    r = S.score_graph_unit(gold_graph(), nodes_ok(), [], SYM)
    assert r["canonical_node"] == PRF(3, 0, 0) and r["identity"]["pairwise"]["fn"] == 0
    split = nodes_ok()[:2] + [
        PredNode("n3", "u", "Protocol", "TCP", ((50, 53),)),
        PredNode("n4", "u", "Protocol", "transmission control protocol", ((80, 83),)),
    ]
    r2 = S.score_graph_unit(gold_graph(), split, [], SYM)
    assert (
        r2["alignment"]["split_concepts"] == ["C"]
        and r2["canonical_node"].fp == 1
        and r2["identity"]["pairwise"]["fn"] == 1
    )


def test_false_merge_of_different_concepts_is_an_identity_error_not_a_match():
    merged = [PredNode("n1", "u", "Component", "router+packet", ((0, 6), (30, 37)))] + nodes_ok()[
        2:
    ]
    r = S.score_graph_unit(gold_graph(), merged, [], SYM)
    assert r["alignment"]["false_merge_nodes"] == ["n1"] and r["identity"]["pairwise"]["fp"] >= 1
    assert r["canonical_node"].tp == 1  # only TCP is a clean node


# ---------------------------------------------------------------- pair recall
def test_pair_recall_denominator_excludes_gold_edges_with_a_missing_endpoint():
    nodes = [
        n for n in nodes_ok() if n.node_id != "n3"
    ]  # TCP node missing -> a node failure, not a pair failure
    pairs = {frozenset(("n1", "n2"))}
    r = S.score_graph_unit(gold_graph(), nodes, [], SYM, proposed_pairs=pairs)["pair_recall"]
    assert (
        r["gold_edges"] == 2
        and r["missing_endpoint_excluded"] == 1
        and r["denominator"] == 1
        and r["pair_recall"] == 1.0
    )
    none = S.score_graph_unit(gold_graph(), nodes_ok(), [], SYM, proposed_pairs=set())[
        "pair_recall"
    ]
    assert none["denominator"] == 2 and none["pair_recall"] == 0.0


# ---------------------------------------------------------------- SciNLP strict scorer
def scinlp_gold():
    g = UnitGold("d")
    g.mentions = [
        GoldMention("d", (0, 2), "method"),
        GoldMention("d", (5, 6), "task"),
        GoldMention("d", (9, 10), "method"),
    ]
    g.relations = [
        GoldRelation("d", "UsedFor", src_span=(0, 2), tgt_span=(5, 6)),
        GoldRelation("d", "compareWith", src_span=(0, 2), tgt_span=(9, 10)),
    ]
    return g


def test_scinlp_entity_strict_needs_exact_span_and_type_for_typed():
    pm = [((0, 2), "method"), ((5, 6), "metric"), ((9, 11), "method")]
    r = S.score_scinlp_unit(scinlp_gold(), pm, [], {"compareWith"})
    assert r["entity_strict"] == PRF(2, 1, 1) and r["entity_typed"] == PRF(1, 2, 2)


def test_scinlp_relation_direction_symmetry_and_rel_plus():
    ok = [
        ((0, 2), (5, 6), "UsedFor", "method", "task"),
        ((9, 10), (0, 2), "compareWith", "method", "method"),
    ]
    r = S.score_scinlp_unit(scinlp_gold(), [], ok, {"compareWith"})
    assert r["rel"] == PRF(2, 0, 0) and r["rel_plus"] == PRF(2, 0, 0)  # reversed symmetric passes
    rev = [((5, 6), (0, 2), "UsedFor", "task", "method")]
    assert (
        S.score_scinlp_unit(scinlp_gold(), [], rev, {"compareWith"})["rel"].tp == 0
    )  # reversed directional fails
    wrong_type = [((0, 2), (5, 6), "UsedFor", "method", "metric")]
    r2 = S.score_scinlp_unit(scinlp_gold(), [], wrong_type, {"compareWith"})
    assert r2["rel"].tp == 1 and r2["rel_plus"].tp == 0


def test_node_edges_are_projected_to_evidence_grounded_mentions_only():
    nodes = [
        PredNode("a", "d", "method", "x", ((0, 2), (50, 52))),
        PredNode("b", "d", "task", "y", ((5, 6),)),
    ]
    rels, ungrounded = S.project_edges_to_mentions(
        nodes, [PredEdge("d", "a", "b", "UsedFor", evidence_span=(0, 10))]
    )
    assert (
        rels == [((0, 2), (5, 6), "UsedFor", "method", "task")] and ungrounded == 0
    )  # the mention at 50 is outside the evidence
    _r, ung = S.project_edges_to_mentions(
        nodes, [PredEdge("d", "a", "b", "UsedFor", evidence_span=None)]
    )
    assert ung == 1


def test_scinlp_aggregation_reports_micro_per_document_macro_and_small_n_status():
    per = {"d1": {"rel": PRF(1, 1, 1)}, "d2": {"rel": PRF(3, 0, 1)}, "d3": {"rel": PRF(0, 2, 2)}}
    a = S.aggregate_documents(per, "rel")
    assert (
        a["micro"]["tp"] == 4
        and set(a["per_document"]) == {"d1", "d2", "d3"}
        and a["CI_status"] == "NOT_EVALUABLE_SMALL_N"
    )
    assert a["min_document_f1"] <= a["max_document_f1"] and a["macro_mean"]["f1"] is not None


# ---------------------------------------------------------------- oracles
def test_oracles_inject_only_into_their_stage_and_hide_relation_labels():
    g = gold_graph()
    e1 = O.oracle_e1(g)
    assert e1.clusters is None and all(
        len(m) == 2 for m in e1.mentions
    )  # spans + types only, no concept ids
    e2 = O.oracle_e2(g, identity_supported=True)
    assert e2.clusters is not None
    with pytest.raises(O.OracleNotSupported):
        O.oracle_e2(g, identity_supported=False)  # SciNLP
    e3, e4 = O.oracle_e3(g, "concept"), O.oracle_e4(g, "concept")
    assert e3.pairs == e4.pairs == (("A", "B"), ("A", "C"))
    for o in (e1, e2, e3, e4):
        O.assert_no_label_leak(o, g)


def test_pair_order_is_hidden_so_direction_does_not_leak():
    g = UnitGold("u")
    g.relations = [GoldRelation("u", "UsedFor", src_span=(9, 10), tgt_span=(1, 2))]
    assert O.oracle_e3(g, "mention").pairs == (((1, 2), (9, 10)),)  # sorted, not (src, tgt)


def test_leakage_guard_catches_a_visible_label():
    g = gold_graph()
    bad = O.InjectedPairs("u", (("A", "acts_on"),), "concept")
    with pytest.raises(AssertionError):
        O.assert_no_label_leak(bad, g)


def test_leakage_scan_matches_whole_tokens_only():
    assert O.leakage_scan({"x": "the chapter 2 layout"}, ["r 2"]) == {}
    assert O.leakage_scan({"x": "an r 2 value"}, ["r 2"]) == {"x": ["r 2"]}


def test_leakage_scan_finds_heldout_surfaces_in_development_artefacts():
    hits = O.leakage_scan(
        {"prompt": "classify Pre-trained Language Models here"},
        ["pre-trained language models", "accuracy"],
    )
    assert hits == {
        "prompt": ["pre-trained language models"]
    }  # single-token surfaces are not scanned


# ---------------------------------------------------------------- attribution
def trace(**kw):
    base = {
        "endpoints": ("A", "B"),
        "span_status": ("exact", "exact"),
        "false_merge": (False, False),
        "split": (False, False),
        "pairs_proposed": (True,),
        "no_relation": (False,),
        "predicted_relations": ("uses",),
        "gold_relation": "uses",
        "symmetric": False,
        "reversed_only": False,
        "types_ok": True,
        "qualifiers_ok": True,
        "evidence_valid": True,
    }
    return A.EdgeTrace(**{**base, **kw})


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"span_status": ("absent", "exact")}, "N0"),
        ({"span_status": ("exact", "partial")}, "N1"),
        ({"false_merge": (True, False)}, "C1"),
        (
            {"split": (True, False), "pairs_proposed": (True, False), "predicted_relations": ()},
            "C0",
        ),
        ({"pairs_proposed": (False,), "predicted_relations": ()}, "P0"),
        ({"no_relation": (True,), "predicted_relations": ()}, "R0"),
        ({"predicted_relations": ("causes",)}, "R1"),
        ({"reversed_only": True}, "R2"),
        ({"types_ok": False}, "R3"),
        ({"evidence_valid": False}, "E0"),
        ({}, None),
    ],
)
def test_earliest_failure_attribution(change, code):
    assert A.attribute(trace(**change)) == code


def test_an_earlier_failure_hides_downstream_ones_and_sleep_codes_are_not_applicable():
    assert (
        A.attribute(
            trace(span_status=("absent", "exact"), pairs_proposed=(False,), predicted_relations=())
        )
        == "N0"
    )
    assert "S0" not in A.CODES and set(A.NOT_APPLICABLE) == {"S0", "S1"}
    assert A.attribute(trace(symmetric=True, reversed_only=True)) is None


def test_build_traces_end_to_end_on_a_small_graph():
    g = gold_graph()
    nodes = nodes_ok()[:2]  # TCP missing
    tr = A.build_traces(
        g, nodes, [PredEdge("u", "n1", "n2", "acts_on")], {frozenset(("n1", "n2"))}, set(), SYM
    )
    codes = {t.endpoints: A.attribute(t) for t in tr}
    assert codes[("A", "B")] is None and codes[("A", "C")] == "N0"


# ---------------------------------------------------------------- bootstrap
def units(n=12):
    return {f"s{i}": PRF(5 + i % 3, 2, 3 - i % 2) for i in range(n)}


def test_bootstrap_is_deterministic_and_resamples_units_not_edges():
    a, b = BS.cluster_bootstrap(units(), b=500), BS.cluster_bootstrap(units(), b=500)
    assert (
        a == b and a["CI_status"] == "OK" and a["resampled_unit"].startswith("document or section")
    )
    assert a["ci"]["f1"][0] <= a["point"]["f1"] <= a["ci"]["f1"][1]


def test_three_document_bootstrap_is_descriptive_small_n_only():
    r = BS.cluster_bootstrap(units(3), b=200)
    assert (
        r["CI_status"] == "NOT_EVALUABLE_SMALL_N"
        and r["label"] == "DESCRIPTIVE_SMALL_N_ONLY"
        and r["distinct_resamples_possible"] == math.comb(5, 3)
    )


def test_paired_bootstrap_requires_the_same_units():
    a, b = units(8), {k: PRF(v.tp + 1, v.fp, v.fn) for k, v in units(8).items()}
    d = BS.paired_bootstrap_delta(a, b, b=300)
    assert d["delta_f1"] > 0 and d["units"] == 8
    with pytest.raises(AssertionError):
        BS.paired_bootstrap_delta(a, units(7))


# ---------------------------------------------------------------- stability
def run(i, names, edges_rel="uses", f1=0.5):
    nodes = tuple(
        PredNode(f"n{j}", "u", "Protocol", nm, ((j * 10, j * 10 + 3),))
        for j, nm in enumerate(names)
    )
    es = (PredEdge("u", "n0", "n1", edges_rel),)
    return ST.RunGraph(f"r{i}", nodes, es, f1, f"cache/{i}")


def test_stability_reports_every_run_and_selects_none():
    runs = [
        run(1, ["a", "b"], f1=0.4),
        run(2, ["a", "b", "c"], "causes", f1=0.5),
        run(3, ["a", "b"], f1=0.6),
    ]
    rep = ST.stability_report(runs)
    assert (
        len(rep["per_run"]) == 3
        and "best" not in str(rep.keys()).lower()
        and rep["selection"].startswith("none")
    )
    assert rep["strict_e2e_f1_mean"] == pytest.approx(0.5) and 0 < rep["edge_set_jaccard_mean"] < 1
    assert rep["relation_disagreement_rate_mean"] > 0


def test_stability_runs_must_not_share_a_cache_namespace():
    a, b = (
        run(1, ["a", "b"]),
        ST.RunGraph("r2", run(2, ["a", "b"]).nodes, run(2, ["a", "b"]).edges, 0.5, "cache/1"),
    )
    with pytest.raises(AssertionError):
        ST.stability_report([a, b])


def test_stored_stability_runs_are_never_overwritten(tmp_path):
    r = run(1, ["a", "b"])
    ST.save_run(r, tmp_path)
    with pytest.raises(AssertionError):
        ST.save_run(r, tmp_path)


def test_each_stability_run_gets_its_own_llm_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("CUMAP_LLM_BACKEND", "mock")
    (_c1, d1), (_c2, d2) = ST.client_for_run(1, str(tmp_path)), ST.client_for_run(2, str(tmp_path))
    assert d1 != d2 and d1.endswith("run_1") and d2.endswith("run_2")


# ---------------------------------------------------------------- budget
def test_pair_budget_formula():
    assert pair_budget(1000, 10_000) == math.ceil(14.2) == 15
    assert (
        pair_budget(0, 50) == 1 and pair_budget(30_000, 100) == 100
    )  # minimum 1, capped at the candidate pool
    assert pair_budget(77_300, 10_000) == math.ceil(14.2 * 77.3)


# ---------------------------------------------------------------- SciNLP adapter
def test_detokenisation_keeps_exact_token_offsets():
    text, offs, ends = detokenise([["A", "model", "."], ["It", "works"]])
    assert text == "A model .\nIt works" and ends == [3, 5]
    assert [text[a:b] for a, b in offs] == ["A", "model", ".", "It", "works"]


@pytest.mark.skipif(not (SCINLP_DIR / "dev.json").exists(), reason="SciNLP is local-only data")
def test_scinlp_dev_gold_round_trips_through_the_detokenised_text():
    ad = SciNLPAdapter()
    doc = ad.load_documents("dev")[0]
    g = ad.gold("dev")[doc.doc_key]
    assert g.mentions and g.relations
    for m in g.mentions[:50]:
        s, e = doc.span_to_chars(m.span)
        assert doc.chars_to_span(s, e) == m.span and doc.text[s:e] == " ".join(
            doc.tokens[m.span[0] : m.span[1]]
        )
    assert ad.symmetric_relations() == {"compareWith", "similarWith"}
    assert ad.gold_clusters("dev") is None
    with pytest.raises(NotImplementedError):
        ad.official_score()


# ---------------------------------------------------------------- P&D-E2E
def test_pd_selection_is_deterministic_blind_and_uses_untouched_chapters_for_heldout():
    rows = PD.load_sections()
    a, b = PD.select(rows), PD.select(rows)
    assert a == b and len(a["pilot"]) == 2 and 6 <= len(a["heldout"]) <= 8
    assert {s["chapter"] for s in a["pilot"]} <= {1, 2, 3} and {
        s["chapter"] for s in a["heldout"]
    } <= {4, 5, 6, 7, 8, 9}
    assert not {s["section_id"] for s in a["pilot"]} & {s["section_id"] for s in a["heldout"]}
    assert a["frozen_before_any_final_cum_prediction_was_viewed"] is True


def test_pd_blind_sheet_has_only_prefilled_structure(tmp_path):
    rows = PD.load_sections()
    info = PD.blind_sheet(rows, ["2.3"], tmp_path / "s.csv")
    with (tmp_path / "s.csv").open(encoding="utf-8") as f:
        sheet = list(csv.DictReader(f))
    assert info["sentences"] > 50 and list(sheet[0]) == PD.COLUMNS
    assert {r["row_type"] for r in sheet} == {"SECTION", "SENTENCE"}
    assert not any(
        r["concept_id"] or r["relation"] or r["span_text"] or r["annotator_id"] for r in sheet
    )


def test_pd_gold_loader_converts_to_character_spans_and_validates():
    text = (FX / "section_fixture.txt").read_text()
    reg = PD.registry()
    gold, problems = PD.load_gold(FX / "pd_gold_fixture.csv", {"F1": text}, reg)
    assert problems == [] and len(gold["F1"].relations) == 2
    spans = {(m.concept_id, m.span) for m in gold["F1"].mentions}
    assert ("C1", (text.index("router"), text.index("router") + 6)) in spans
    assert [text[a:b] for c, (a, b) in sorted(spans) if c == "C4"] == ["TCP", "TCP"]


def test_pd_gold_validator_rejects_bad_sheets(tmp_path):
    text = (FX / "section_fixture.txt").read_text()
    reg = PD.registry()
    with (FX / "pd_gold_fixture.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    bad = [dict(r) for r in rows]
    bad.append(
        {
            **rows[0],
            "row_type": "MENTION",
            "sentence_id": "S001",
            "span_text": "switch",
            "occurrence": "1",
            "concept_id": "C1",
        }
    )
    bad.append(
        {
            **rows[0],
            "row_type": "RELATION",
            "relation": "part_of",
            "source_concept_id": "C3",
            "target_concept_id": "C1",
            "qualifiers": "",
            "evidence_sentence_ids": "S002",
        }
    )
    bad.append(
        {
            **rows[0],
            "row_type": "RELATION",
            "relation": "invented",
            "source_concept_id": "C1",
            "target_concept_id": "C2",
            "evidence_sentence_ids": "S001",
        }
    )
    p = tmp_path / "bad.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=PD.COLUMNS)
        w.writeheader()
        w.writerows(bad)
    _g, problems = PD.load_gold(p, {"F1": text}, reg)
    joined = " | ".join(problems)
    assert (
        "not in the sentence" in joined
        and "part_type" in joined
        and "not in the registry" in joined
    )


# ---------------------------------------------------------------- gold safety
def test_no_cr012_module_writes_to_the_gold_folder_or_reads_the_scinlp_test_split():
    for f in Path("src/cumap/cr012").glob("*.py"):
        src = f.read_text()
        assert "data/gold" not in src and '"gold"' not in src, f
        if f.name not in {
            "stop1.py",
            "isolation.py",
        }:  # these two read the test split once, as data (hash / string search)
            assert (
                "test.json" not in src
                and 'load_documents("test")' not in src
                and 'gold("test")' not in src
            ), f

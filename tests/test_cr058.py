"""CR-058: stage funnel and gold-vs-built graph of the pipeline diagnostics page (fixture paper; no network, no key)."""

from cumap.cr012.adapters import SciNLPDoc
from cumap.cr012.types import GoldMention, GoldRelation, UnitGold
from cumap.cr058 import funnel as FN
from cumap.cr058 import graphs as GR
from cumap.cr058.page import TEMPLATE

SYM = {"compareWith", "similarWith"}
TEXT = "We use BERT for parsing . BERT is evaluated on PTB ."
Q0 = "We use BERT for parsing"


def _doc():
    toks = TEXT.split()
    offs, pos = [], 0
    for t in toks:
        offs.append((pos, pos + len(t)))
        pos += len(t) + 1
    return SciNLPDoc("d", toks, [6, 12], " ".join(toks), offs, len(toks))


def _gold():
    ms = [GoldMention("d", (2, 3), "method"), GoldMention("d", (4, 5), "task"),
          GoldMention("d", (6, 7), "method"), GoldMention("d", (10, 11), "dataset")]  # fmt: skip
    rels = [
        GoldRelation("d", "UsedFor", (2, 3), (4, 5)),
        GoldRelation("d", "evaluatedOn", (6, 7), (10, 11)),
    ]
    return UnitGold("d", mentions=ms, relations=rels)


def _concept(cid, name, quote, typ="method"):
    return {"concept_id": cid, "canonical_name": name, "aliases": [], "node_type": typ,
            "mentions": [{"section_id": "d", "role": "used", "quote": quote}]}  # fmt: skip


def _result(x, y, family, relation, outcome, reason=None, quote=Q0):
    return {"outcome": outcome, "reason": reason, "family": family, "relation": relation, "direction": "forward",
            "evidence_quote": quote, "qualifiers": {"polarity": "affirmed"}, "group": "selected",
            "pair": {"pair_id": f"{x}-{y}", "section_id": "d", "concept_x_id": x, "concept_y_id": y, "sentence": Q0}}  # fmt: skip


def _cp():
    return {
        "concepts": [_concept("c_bert", "BERT", Q0), _concept("c_parsing", "parsing", Q0, "task"),
                     _concept("c_we", "We", Q0)],
        "relation_results_v3": [
            _result("c_bert", "c_parsing", "scinlp", "UsedFor", "edge"),
            _result("c_we", "c_bert", "scinlp", "UsedFor", "rejected", "domain_range"),
            _result("c_we", "c_parsing", "no_relation", None, "no_relation"),
        ],
        "merges": [{"rule_id": "G-link"}, {"rule_id": "R2"}, {"rule_id": None, "llm_called": True}],
    }  # fmt: skip


def _v4():
    bert = {"name": "BERT", "aliases": [], "node_type": "method", "role": "used", "evidence": Q0}
    parsing = {
        "name": "parsing",
        "aliases": [],
        "node_type": "task",
        "role": "used",
        "evidence": Q0,
    }
    return {
        "sections": {"d#1": {
            "iterations": [{"output": {"new_concepts": [bert], "existing_mentions": []},
                            "verified": {"new_concepts": [bert], "existing_mentions": []}}],
            "final": {"new_concepts": [bert, parsing], "existing_mentions": []},
            "rejected": [{"kind": "new_concepts", "rules": ["F3"], "item": {"name": "PTB"}},
                         {"kind": "new_concepts", "rules": ["F2"], "item": {"name": "the model"}}],
            "hints_added": 2, "hints_rejected": 1, "restored": 0, "unresolved_hints": [], "flags_by_rule": {}}},
        "nodes": {"n_1": {"id": "n_1", "name": "BERT", "aliases": [], "node_type": "method",
                          "mentions": [{"section_id": "d#1", "evidence": Q0, "role": "used"}]},
                  "n_2": {"id": "n_2", "name": "parsing", "aliases": [], "node_type": "task",
                          "mentions": [{"section_id": "d#1", "evidence": Q0, "role": "used"}]}},
        "pruned": [],
        "merges": [{"rule_id": "G-link-rejected"}, {"rule_id": "G-link"}],
    }  # fmt: skip


def test_an_existing_mention_counts_under_the_card_node_it_names():
    nodes = {"n_9": {"name": "language model", "aliases": ["LM"]}}
    out = FN.items_to_concepts(
        [{"node_id": "n_9", "surface": "LMs", "evidence": "the LMs we use"},
         {"name": "BERT", "evidence": "BERT"}, {"name": "bert", "evidence": "a bert"}],
        "d", nodes,
    )  # fmt: skip
    names = {c["canonical_name"]: c for c in out}
    assert set(names) == {"language model", "BERT"}
    assert names["language model"]["aliases"] == ["LM"] and len(names["BERT"]["mentions"]) == 2


def test_concept_stages_are_scored_by_placement_and_the_last_stage_is_the_prediction():
    doc, g, cp, v4 = _doc(), _gold(), _cp(), _v4()
    cf = FN.concept_funnel(doc, g, cp, v4, SYM)
    first, final = cf["stages"]["generator_first_pass"], cf["stages"]["consolidation"]
    assert (first["tp"], first["fp"], first["fn"]) == (2, 0, 2)  # BERT placed at both occurrences
    assert (final["tp"], final["fp"], final["fn"]) == (
        3,
        1,
        1,
    )  # + parsing, + the non-gold "We"; PTB missed
    assert FN.relation_funnel(doc, g, cp, SYM)["concept_strict"] == {"tp": 3, "fp": 1, "fn": 1}


def test_verifier_drops_split_into_gold_and_non_gold_items():
    v = FN.verifier_drops(_v4(), FN.gold_surface_keys(_doc(), _gold()), final_keys=set())
    assert v["counts"] == {"concept_correct": 1, "concept_wrong": 1}
    assert v["rules"] == {"correct": {"F3": 1}, "wrong": {"F2": 1}} and v["hints"]["added"] == 2


def test_consolidation_skips_the_relabelled_generator_copies():
    c = FN.consolidation_stats(_v4(), _cp())
    assert c["merges"] == {"R2": 1, "R4 (LLM judge)": 1}
    assert c["links"] == {"G-link-rejected": 1, "G-link": 1}


def test_relation_funnel_follows_pairs_and_gold_relations_through_the_steps():
    rf = FN.relation_funnel(_doc(), _gold(), _cp(), SYM)
    p = rf["pairs"]
    assert (p["selected"], p["selected_positive"], p["selected_negative"]) == (3, 1, 2)
    assert (p["family_tp"], p["family_fp"], p["family_tn"]) == (1, 1, 1)
    assert p["choice_right"] == 1 and p["choice_on_negative"] == 1
    assert p["checks_dropped_wrong"] == 1 and p["in_graph_correct"] == 1
    assert rf["checks"] == {"correct": {}, "wrong": {"domain_range": 1}}
    g = rf["gold_stages"]
    assert (
        g["gold"] == 2 and g["endpoints_placed"] == 1 and g["credited"] == 1
    )  # PTB is never placed
    assert rf["lost_at"] == ["credited", "endpoints_placed"]
    assert rf["relation_strict"] == {"tp": 1, "fp": 0, "fn": 1}


def test_a_correct_pair_dropped_by_a_check_is_counted_as_a_correct_drop():
    cp = _cp()
    cp["relation_results_v3"][0] |= {"outcome": "rejected", "reason": "endpoint_not_grounded"}
    rf = FN.relation_funnel(_doc(), _gold(), cp, SYM)
    assert rf["pairs"]["checks_dropped_correct"] == 1 and rf["checks"]["correct"] == {
        "endpoint_not_grounded": 1
    }
    assert rf["gold_stages"]["choice_right"] == 1 and rf["gold_stages"]["checks_passed"] == 0


def test_graph_marks_found_missed_and_non_gold_concepts_and_shares_one_layout():
    doc, g, cp = _doc(), _gold(), _cp()
    rf = FN.relation_funnel(doc, g, cp, SYM)
    trace = {"proposed": set(), "dropped": {}, "hints": {}, "merged": {}, "gen_nodes": set()}
    out = GR.build(doc, g, cp, rf["pred"], rf["lost_at"], SYM, trace)
    st = {n["label"]: n["status"] for n in out["gold_nodes"]}
    assert st == {"BERT": "found", "parsing": "found", "PTB": "missed"}
    assert {n["label"]: n["status"] for n in out["built_nodes"]} == {
        "BERT": "gold",
        "parsing": "gold",
        "We": "non_gold",
    }
    assert [(m["text"], m["stage"]) for m in out["missed_mentions"]] == [("PTB", "never_proposed")]
    ge = {e["rel"]: e["status"] for e in out["gold_edges"]}
    assert ge == {"UsedFor": "credited", "evaluatedOn": "endpoints_placed"}
    assert [e["status"] for e in out["built_edges"]] == ["correct"]
    bert = next(n for n in out["built_nodes"] if n["label"] == "BERT")
    assert bert["u"] == bert["gold_id"] and bert["u"] in out["pos"]


def test_the_page_template_has_the_data_slot_and_no_external_script():
    html = TEMPLATE.read_text(encoding="utf-8")
    assert "/*__DATA_B64__*/" in html and "<script src" not in html

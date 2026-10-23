"""CR-039 DRAFT: the misconception family in relation classification (registry v1.6, prompts family v5 / choice v7). Mock fixtures only; never run."""

import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from test_cr035 import lex
from test_relations_v3 import rc

from cumap.expert_kg import misconception as MC
from cumap.expert_kg import relations_v7 as R7
from cumap.expert_kg.mentions import MentionMatcher
from cumap.expert_kg.pair_selection import select_pairs
from cumap.expert_kg.relations import CandidatePair, concept_vocab
from cumap.expert_kg.relations_v3 import classify_pair_v3
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt
from cumap.schemas import registry_patch as RP
from cumap.schemas.relations import RelationRegistry

REPO = Path(__file__).parents[1]
V15 = RelationRegistry.from_yaml(REPO / "configs/relations_v1.5.yaml")
V16 = RelationRegistry.from_yaml(REPO / "configs/relations_v1.6.yaml")
P = {
    t: load_prompt(REPO / "prompts", t, v)
    for t, v in (
        ("relation_family", "v5"),
        ("relation_choice", "v7"),
        ("relation_qualifiers", "v6"),
    )
}
RT, FT = rc("c_rt", "routing table", "Concept"), rc("c_ft", "forwarding table", "Concept")
SENT = "A common mistake is to think a routing table is the same as a forwarding table; they are different tables."
MATCHER = MentionMatcher(concept_vocab([RT, FT]))


# ---------------------------------------------------------------- registry v1.6
def test_v16_is_v15_plus_one_family_and_one_misconception_layer_relation():
    patch = yaml.safe_load(
        (REPO / "configs/registry-patches/CR-039-relations-v1.6.yaml").read_text()
    )
    base = yaml.safe_load((REPO / "configs/relations_v1.5.yaml").read_text())
    assert RP.apply_patch(base, patch) == yaml.safe_load(
        (REPO / "configs/relations_v1.6.yaml").read_text()
    )
    assert (
        V16.version_label == "1.6"
        and "misconception" in V16.families
        and V16.get("conflated_with").layer == "misconception"
    )
    assert {r.name for r in V16.all_relations()} - {r.name for r in V15.all_relations()} == {
        "conflated_with"
    }
    assert (
        V16.qualifiers.keys() == V15.qualifiers.keys()
        and V16.qualifiers["modality"].values == V15.qualifiers["modality"].values
    )  # inherits v1.5
    assert (
        "NOT from relations_v1.4.yaml"
        in (REPO / "configs/relations_v1.6.yaml").read_text().splitlines()[1]
    )
    with pytest.raises(ValueError, match="registry minor"):
        RP.apply_patch(
            yaml.safe_load((REPO / "configs/relations_v1.3.yaml").read_text()), patch
        )  # built on v1.5 only


# ---------------------------------------------------------------- closed-choice schema
OK = {
    "is_misconception": True, "wrong_relation": "conflated_with", "wrong_direction": "forward", "wrong_polarity": "affirmed", "perturbation_type": "conflation",
    "correct_relation": "contrasts_with", "correct_direction": "forward", "correct_polarity": "affirmed", "misconception_quote": "q", "correction_quote": "c",
    "prevalence_cue": "stated_common", "reason": "r",
}  # fmt: skip


def test_misconception_choice_is_closed_flat_and_required():
    s = R7.build_misconception_choice(V16)
    assert s.model_validate(OK).wrong_relation == "conflated_with" and all(
        f.is_required() for f in s.model_fields.values()
    )
    for bad in (
        {**OK, "wrong_relation": "made_up"}, {**OK, "perturbation_type": "typo"}, {**OK, "correct_relation": "conflated_with"},  # the correct statement is a semantic relation
        {**OK, "extra": 1}, {k: v for k, v in OK.items() if k != "reason"}, {**OK, "misconception_quote": None}, {**OK, "wrong_relation": "none"},
    ):  # fmt: skip
        with pytest.raises(ValidationError):
            s.model_validate(bad)
    empty = {**OK, "is_misconception": False, "wrong_relation": "none", "perturbation_type": "none", "correct_relation": "none", "misconception_quote": None, "correction_quote": None}  # fmt: skip
    assert s.model_validate(empty).is_misconception is False


def test_other_families_keep_the_v6_choice_schema():
    s = R7.build_relation_choice_v7(V16, "comparison")
    assert "dimension_quote" in s.model_fields and "is_misconception" not in s.model_fields
    assert "is_misconception" in R7.build_relation_choice_v7(V16, "misconception").model_fields
    block = R7.misconception_options_block(V16, "routing table", "forwarding table")
    assert (
        "conflated_with" in block
        and "routing table is confused with forwarding table" in block
        and "- none:" in block
    )


# ---------------------------------------------------------------- the drafted prompts
def test_prompts_are_new_drafts_with_rules_first_and_the_case_last():
    for t in ("relation_family", "relation_choice"):
        p = P[t]
        assert "DRAFT" in p.notes and p.body.index("Rules") < p.body.index("Now decide this case")
    assert P["relation_family"].version == "v5" and P["relation_choice"].version == "v7"
    assert set(re.findall(r"\{(\w+)\}", P["relation_family"].body)) == {
        "concept_x",
        "concept_y",
        "sentence",
        "family_options",
    }
    assert set(re.findall(r"\{(\w+)\}", P["relation_choice"].body)) == {
        "family",
        "concept_x",
        "concept_y",
        "sentence",
        "relation_options",
    }
    assert (
        "plain negation" in P["relation_family"].body
        or "negated relation, not a misconception" in P["relation_family"].body
    )
    for v in (("relation_family", "v3"), ("relation_family", "v4"), ("relation_choice", "v6")):
        assert (REPO / f"prompts/{v[0]}/{v[1]}.md").exists()


# ---------------------------------------------------------------- classification (mock fixtures)
def run7(tmp_settings, fixtures_dir, choice, **kw):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    pr = CandidatePair("P1", "1.1", RT.concept_id, FT.concept_id, SENT)
    return classify_pair_v3(client, P["relation_family"], P["relation_choice"], P["relation_qualifiers"], V16, pr, RT, FT, MATCHER, fixtures=("v5_misconception", choice, "v6_acts_on"), amendments="v6", **kw)  # fmt: skip


def test_a_misconception_answer_becomes_a_layer_item_source_never_an_edge(
    tmp_settings, fixtures_dir
):
    r = run7(
        tmp_settings,
        fixtures_dir,
        "v7_misconception_conflation",
        misconception_source="classification",
    )
    assert (
        r.outcome == "misconception"
        and r.relation is None
        and r.misconception["wrong_relation"] == "conflated_with"
    )
    d = r.to_dict()
    assert (
        d["misconception"]["perturbation_type"] == "conflation" and d["outcome"] == "misconception"
    )
    assert (
        MC.expert_edges([{**d, "group": "selected"}]) == {}
    )  # rule 22: invisible to the expert layer


def test_not_a_misconception_is_logged_as_no_relation(tmp_settings, fixtures_dir):
    r = run7(
        tmp_settings, fixtures_dir, "v7_not_misconception", misconception_source="classification"
    )
    assert (r.outcome, r.reason) == ("no_relation", "not_a_misconception")


def test_a_misconception_quote_not_in_the_sentence_is_rejected(tmp_settings, fixtures_dir):
    r = run7(
        tmp_settings,
        fixtures_dir,
        "v7_misconception_badquote",
        misconception_source="classification",
    )
    assert (r.outcome, r.reason) == ("rejected", "misconception_quote_not_in_sentence")


def test_the_family_is_not_enabled_without_the_switch_and_the_switch_needs_amendments_v6(
    tmp_settings, fixtures_dir
):
    r = run7(tmp_settings, fixtures_dir, "v7_misconception_conflation")
    assert (r.outcome, r.reason) == (
        "other",
        "family_misconception_not_enabled",
    ) and "misconception" not in r.to_dict()
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    pr = CandidatePair("P1", "1.1", RT.concept_id, FT.concept_id, SENT)
    with pytest.raises(ValueError, match="amendments v6"):
        classify_pair_v3(client, P["relation_family"], P["relation_choice"], P["relation_qualifiers"], V16, pr, RT, FT, MATCHER, fixtures=("v5_misconception", "x", "x"), misconception_source="classification")  # fmt: skip


# ---------------------------------------------------------------- the layer from classification results
def concepts():
    return [
        {
            "concept_id": c.concept_id,
            "canonical_name": c.canonical_name,
            "node_type": c.node_type,
            "aliases": [],
        }
        for c in (RT, FT, rc("c_a", "alpha"), rc("c_b", "beta"))
    ]


def result(choice, pair_id="P1", x="c_rt", y="c_ft", sentence=SENT, outcome="misconception"):
    return {"outcome": outcome, "group": "selected", "relation": None, "direction": "forward", "misconception": choice, "family_reason": "r",
            "reason": "not_a_misconception" if outcome == "no_relation" else None,
            "pair": {"pair_id": pair_id, "section_id": "1.1", "concept_x_id": x, "concept_y_id": y, "sentence": sentence}}  # fmt: skip


CHOICE = {**OK, "misconception_quote": "A common mistake is to think a routing table is the same as a forwarding table", "correction_quote": "they are different tables"}  # fmt: skip


def test_a_conflation_links_to_the_lexicon_different_entry_and_has_the_legacy_layer_shape(tmp_path):
    lx = lex(tmp_path, different=[("routing table", "forwarding table")])
    cp = {"concepts": concepts(), "relation_results_v3": [result(CHOICE)]}
    layer = MC.layer_from_classification(cp, V16, [("1.1", SENT)], lx)
    assert set(layer) >= {
        "items",
        "not_warning",
        "needs_review",
        "needs_correct_edge",
        "proposed_lexicon",
        "stats",
    }
    assert (
        len(layer["items"]) == 1
        and layer["items"][0]["contradicts"][0].startswith("L:")
        and layer["items"][0]["source"] == "relation_classification"
    )
    assert (
        layer["proposed_lexicon"]
        and layer["stats"]["warnings"] == 1
        and layer["needs_review"] == []
    )


def edge_result(pair_id, x, y, rel, quote):
    return {"outcome": "edge", "group": "selected", "relation": rel, "direction": "forward", "evidence_quote": quote, "qualifiers": {"polarity": "affirmed"},
            "pair": {"pair_id": pair_id, "section_id": "1.1", "concept_x_id": x, "concept_y_id": y, "sentence": quote}}  # fmt: skip


def test_a_polarity_flip_is_linked_to_the_expert_edge_it_contradicts():
    sent = "Some think alpha does not use beta, but alpha uses beta."
    choice = {**OK, "wrong_relation": "uses", "perturbation_type": "polarity_flip", "wrong_polarity": "negated", "correct_relation": "uses",
              "misconception_quote": "alpha does not use beta", "correction_quote": "alpha uses beta"}  # fmt: skip
    cp = {
        "concepts": concepts(),
        "relation_results_v3": [
            edge_result("E1", "c_a", "c_b", "uses", "alpha uses beta"),
            result(choice, "P2", "c_a", "c_b", sent),
        ],
    }
    layer = MC.layer_from_classification(cp, V16, [("1.1", sent)], None)
    assert [i["contradicts"] for i in layer["items"]] == [["E:E1"]] and layer["items"][0][
        "perturbation_type"
    ] == "polarity_flip"


def test_a_missing_correct_edge_waits_and_a_bad_quote_goes_to_the_owner_not_dropped():
    sent = "Some think alpha does not use beta, but alpha uses beta."
    choice = {**OK, "wrong_relation": "uses", "perturbation_type": "polarity_flip", "wrong_polarity": "negated", "correct_relation": "uses",
              "misconception_quote": "alpha does not use beta", "correction_quote": "alpha uses beta"}  # fmt: skip
    cp = {"concepts": concepts(), "relation_results_v3": [result(choice, "P2", "c_a", "c_b", sent)]}
    layer = MC.layer_from_classification(
        cp, V16, [("1.1", sent)], None
    )  # no verifier: the correct edge is not classified here
    assert layer["items"] == [] and len(layer["needs_correct_edge"]) == 1
    bad = {**choice, "misconception_quote": "this is not in the section"}
    layer2 = MC.layer_from_classification(
        {"concepts": concepts(), "relation_results_v3": [result(bad, "P3", "c_a", "c_b", sent)]},
        V16,
        [("1.1", sent)],
        None,
    )
    assert layer2["items"] == [] and "not a verbatim substring" in layer2["needs_review"][0]["errors"][0] or any("verbatim" in e for e in layer2["needs_review"][0]["errors"])  # fmt: skip


def test_not_a_misconception_results_are_counted_as_not_warnings():
    cp = {
        "concepts": concepts(),
        "relation_results_v3": [result(None, "P4", outcome="no_relation")],
    }
    layer = MC.layer_from_classification(cp, V16, [("1.1", SENT)], None)
    assert layer["stats"]["not_warning"] == 1 and layer["items"] == []


# ---------------------------------------------------------------- the kept $0 cue scan as a selection priority
def test_the_cue_scan_raises_selection_priority_without_making_items_and_default_selection_is_unchanged():
    cands = MC.scan_cues([("1.1", SENT)], None)
    prio = MC.cue_pair_priority(cands, MATCHER)
    assert prio == {frozenset(("c_rt", "c_ft"))}
    pool = {
        "1.1": [
            CandidatePair("A", "1.1", "c_rt", "c_ft", SENT, 1, 0),
            CandidatePair("B", "1.1", "c_x", "c_y", "s", 5, 9),
        ]
    }
    roles = {"c_rt": "mentioned", "c_ft": "mentioned", "c_x": "mentioned", "c_y": "mentioned"}
    base = select_pairs(pool, roles, budget=1, min_per_section=0, sample_unselected=0)
    pri = select_pairs(
        pool, roles, budget=1, min_per_section=0, sample_unselected=0, priority_pairs=prio
    )
    assert [p.pair_id for p in base.selected] == ["B"] and [p.pair_id for p in pri.selected] == [
        "A"
    ]
    assert (
        "phase0c_cue_priority_pairs" not in base.stats
        and pri.stats["phase0c_cue_priority_pairs"] == 1
    )


# ---------------------------------------------------------------- switch
def test_source_switch_defaults_to_legacy_and_needs_registry_v16():
    assert (
        R7.resolve_source() == "legacy" and R7.resolve_source("classification") == "classification"
    )
    with pytest.raises(ValueError):
        R7.resolve_source("both")
    R7.check_registry_for_misconceptions(V16)
    with pytest.raises(ValueError, match="relations_v1.6"):
        R7.check_registry_for_misconceptions(V15)
    assert (
        yaml.safe_load((REPO / "configs/relation_policy.yaml").read_text())["misconception_source"]
        == "legacy"
    )

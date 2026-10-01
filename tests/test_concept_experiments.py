"""CR-007 §3.2 tests: E1-E5 pieces on fixtures and the mock backend (no network, no key)."""

from pathlib import Path

import pytest

from cumap.expert_kg.concept_experiments import (
    BASELINE,
    SINGLES,
    Variant,
    aggregate_runs,
    build_fewshot_pool,
    combine_variants,
    pick_fewshot,
    propagate,
    render_vars,
    run_variant,
    select_by_rule,
)
from cumap.expert_kg.face_scorer import GoldConcept
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

REPO = Path(__file__).parents[1]
PROMPTS = REPO / "prompts"


def m(name, role="used", sid="s1"):
    return {
        "canonical_name": name,
        "node_type": "Concept",
        "role": role,
        "definition": None,
        "evidence_quote": name,
        "section_id": sid,
        "run_index": 0,
        "source": "llm",
    }


@pytest.fixture(scope="module")
def nlp():
    import spacy

    return spacy.load("en_core_web_sm", disable=["ner"])


def test_baseline_v2_renders_without_extra_variables_and_v3x_blocks_toggle():
    assert render_vars(BASELINE, 0, PROMPTS, []) == {}
    v = Variant("x", codebook=True, granularity=True)
    rv = render_vars(v, 0, PROMPTS, [])
    assert (
        "Annotation conventions" in rv["codebook_block"]
        and "Granularity" in rv["granularity_block"]
    )
    assert rv["few_shot_block"] == "" and rv["pass_note"] == ""
    off = render_vars(Variant("y"), 0, PROMPTS, [])
    assert set(off.values()) == {""}  # all blocks empty when off


def test_v3x_with_all_blocks_off_is_v2_plus_only_whitespace_and_contains_no_gold_style_examples():
    v2 = load_prompt(PROMPTS, "concept_extraction", "v2").body
    v3x = load_prompt(PROMPTS, "concept_extraction", "v3x").body
    blocks = {"codebook_block": "", "granularity_block": "", "few_shot_block": "", "pass_note": ""}
    other = {"domain": "d", "heading_path": "h", "candidate_terms": "c", "section_text": "t"}
    norm = lambda t: " ".join(t.split())
    assert norm(v3x.format_map({**other, **blocks})) == norm(v2.format_map(other))
    codebook = (PROMPTS / "concept_extraction/blocks_v3x/codebook.md").read_text().lower()
    for leaked in ("postings", "inverted index", "tf-idf", "boolean retrieval", "posting"):
        assert leaked not in codebook  # networking-only examples, no IIR terms


def test_e2_run_notes_differ_and_aggregation_union_vs_vote():
    v = Variant("E2", samples=3, aggregate="union")
    notes = [render_vars(v, r, PROMPTS, [])["pass_note"] for r in range(3)]
    assert notes[0] == "" and notes[1] != notes[2] and "Pass 2 of 3" in notes[1]
    runs = [[m("a"), m("b")], [m("b"), m("c")], [m("b"), m("a")]]
    assert {x["canonical_name"] for x in aggregate_runs(runs, "union")} == {"a", "b", "c"}
    assert {x["canonical_name"] for x in aggregate_runs(runs, "vote2")} == {"a", "b"}
    assert [x["canonical_name"] for x in aggregate_runs(runs, "single")] == ["a", "b"]


def test_e3_propagation_tags_later_occurrences_as_mentioned_with_source_propagation():
    final = {"s1": [m("bit rate", "defined", "s1")], "s2": [m("frame", "used", "s2")]}
    texts = {"s1": "A frame carries bits.", "s2": "The bit rate is fixed. A frame follows."}
    out = propagate(final, texts)
    s1 = {x["canonical_name"]: x for x in out["s1"]}
    assert s1["frame"]["role"] == "mentioned" and s1["frame"]["source"] == "propagation"
    assert (
        s1["frame"]["evidence_quote"] in texts["s1"] and "bit rate" in s1
    )  # already-found kept as-is
    assert [x["canonical_name"] for x in out["s2"]] == [
        "frame",
        "bit rate",
    ]  # 'bit rate' propagated, not 'bit'


def test_e4_fewshot_is_leave_one_section_out_and_uses_only_terms_present_in_the_excerpt():
    secs = [
        {"section_id": f"s{i}", "text": f"Alpha beta gamma delta. Term{i} appears here. " * 10}
        for i in range(4)
    ]
    gold = [
        GoldConcept(f"s{i}", t)
        for i in range(4)
        for t in ("alpha beta", f"term{i}", "gamma delta", "absent term")
    ]
    pool = build_fewshot_pool(secs, gold)
    assert all("absent term" not in f.terms and len(f.terms) >= 3 for f in pool)
    picked = pick_fewshot(pool, "s0", 2)
    assert "s0" not in {f.section_id for f in picked} and len(picked) == 2
    assert pick_fewshot(pool, "s0", 2) == picked  # deterministic


def test_selection_rule_takes_the_best_and_breaks_ties_toward_the_simpler():
    variants = {"E1": SINGLES[0], "E2-union": SINGLES[1], "E4": SINGLES[4]}
    assert select_by_rule({"E1": 0.60, "E2-union": 0.70, "E4": 0.61}, variants) == "E2-union"
    assert (
        select_by_rule({"E1": 0.69, "E2-union": 0.70, "E4": 0.61}, variants) == "E1"
    )  # within 0.02: 1 call beats 3
    assert (
        select_by_rule({"E1": 0.70, "E4": 0.69}, variants) == "E1"
    )  # equal calls: fewer components/name
    combo = combine_variants("C", [SINGLES[0], SINGLES[5], SINGLES[1]])
    assert combo.codebook and combo.granularity and combo.samples == 3 and combo.n_components == 3


def test_run_variant_end_to_end_on_the_mock_backend_records_per_run_outputs(
    tmp_settings, fixtures_dir, nlp
):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    reg = RelationRegistry.from_yaml(REPO / "configs/relations_v1.yaml")
    sections = [
        {
            "section_id": "s1",
            "text": "TCP uses sliding window. It also performs slow start.",
            "heading_path": ["Ch", "TCP"],
        }
    ]
    v = Variant("E2-union", samples=3, aggregate="union", propagate=True)
    res = run_variant(
        client,
        v,
        sections,
        nlp=nlp,
        registry=reg,
        prompts_dir=PROMPTS,
        domain="computer networking",
        fixture_name="demo",
    )
    assert len(res.runs["s1"]) == 3  # per-run outputs stored (feeds CR-002 §4 later)
    names = {x["canonical_name"] for x in res.final["s1"]}
    assert names == {
        "TCP",
        "sliding window",
    }  # the demo fixture's main pass (slow start is gleaning-only)
    assert client.backend_call_count == 0 or client.backend_call_count <= 3
    with pytest.raises(FileNotFoundError):
        run_variant(
            client,
            Variant("bad", prompt="nope"),
            sections,
            nlp=nlp,
            registry=reg,
            prompts_dir=PROMPTS,
            fixture_name="demo",
        )

"""CR-013 STOP 2: trace model, lineage, deterministic renderer, Why-not localiser, coverage and gap honesty, on a small synthetic retained run (no network, no model)."""

import hashlib
import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from cumap.explain import lineage as L
from cumap.explain import render as R
from cumap.explain.adapters_pd import PDAdapter
from cumap.explain.coverage import coverage
from cumap.explain.trace import TraceEvent, TraceStore, make_event_id
from cumap.explain.why_not import pair_index, why_not
from cumap.explain.why_not_eval import localise

RUN = "fixture_run"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _pair(pid, x, y, sentence="A router uses a forwarding table to forward packets.", sec="1.1"):
    return {
        "pair_id": pid,
        "section_id": sec,
        "concept_x_id": x,
        "concept_y_id": y,
        "sentence": sentence,
        "cooccurrence_count": 2,
        "cue_score": 1,
    }


def make_run(root: Path):
    d = root / RUN
    (d / "snapshots/ch1").mkdir(parents=True)
    mention = lambda sec, ev, order=0: {
        "section_id": sec,
        "order": order,
        "role": "used",
        "para": "P1",
        "evidence": ev,
        "surface": "router",
        "linked_by": "generator",
    }
    v4 = {
        "nodes": {
            "n_0001": {"id": "n_0001", "name": "router", "aliases": [], "node_type": "Component", "first_section": "1.1", "mentions": [mention("1.1", "A router uses a forwarding table", 0), mention("1.2#1", "routers forward packets", 1), mention("1.2#2", "the router drops it", 2)]},
            "n_0002": {"id": "n_0002", "name": "forwarding table", "aliases": [], "node_type": "Mechanism", "first_section": "1.1", "mentions": [mention("1.1", "uses a forwarding table", 0)]},
            "n_0003": {"id": "n_0003", "name": "switch", "aliases": [], "node_type": "Component", "first_section": "1.1", "mentions": [mention("1.1", "a switch connects links", 0)]},
            "n_0004": {"id": "n_0004", "name": "hub", "aliases": [], "node_type": "Component", "first_section": "1.1", "mentions": [mention("1.1", "a hub repeats bits", 0)]},
        },
        "sections": {
            "1.1": {"iterations": [{"iteration": 0, "output": {}, "verified": {}, "flags": [{"rule": "F2", "where": "new", "idx": 0, "detail": "evidence not verbatim", "sub": None}], "hints": [{"rule": "M2", "type": "longer_span", "text": "forwarding table", "detail": "tail of a longer term"}], "autofixes": [{"rule": "F2", "what": "whitespace", "where": "new 0"}], "warnings": []}],
                    "final": {"new_concepts": [{"name": "router", "independence_check": "No known concept relates to router here."}]},
                    "rejected": [{"kind": "new_concepts", "rules": ["F3"], "item": {"name": "foo", "evidence": "foo bar"}}], "rejected_hints": [{"hint_id": "h1", "rule": "M2", "text": "x y", "reason": "ordinary modifier"}]},
            "1.2#1": {"iterations": [], "final": {"new_concepts": []}, "rejected": [], "rejected_hints": []},
            "1.2#2": {"iterations": [], "final": {"new_concepts": []}, "rejected": [], "rejected_hints": []},
        },
        "section_meta": {"1.1": {"p": [{"name": "router", "p": 0.9, "role": "used"}, {"name": "forwarding table", "p": 0.6, "role": "used"}], "pruned": [], "new_nodes": ["n_0001", "n_0002", "n_0003", "n_0004"]},
                         "1.2#1": {"p": [], "pruned": [], "new_nodes": []}, "1.2#2": {"p": [], "pruned": [], "new_nodes": []}},
        "pruned": [], "backfill": [], "extra": {},
        "merges": [{"rule_id": "G-link", "node_id": "n_0001", "surface": "routers", "section_id": "1.2#1", "evidence": "routers forward packets", "trivial": False}],
    }  # fmt: skip
    concept = lambda cid, name, typ, quotes: {"concept_id": cid, "canonical_name": name, "node_type": typ, "definition": None, "first_introduced": "1.1", "aliases": [], "description_history": [], "merged_from": [], "alias_provenance": [],
                                               "mentions": [{"section_id": "1.1", "role": "used", "quote": q, "definition": None, "source": "llm"} for q in quotes]}  # fmt: skip
    results = [
        {"outcome": "edge", "reason": None, "family": "function_means", "relation": "uses", "direction": "forward", "statement": "A router uses a forwarding table.", "evidence_quote": "uses a forwarding table", "qualifiers": {"polarity": "affirmed"}, "comparison_dimension": None,
         "other_description": None, "family_reason": "The sentence says the router relies on the table.", "grounding": {"quote_x": True}, "type_errors": [], "prompt_hashes": {"family": "h1", "choice": "h2", "qualifiers": "h3"}, "pair": _pair("RP-1.1-0", "c_router", "c_forwarding_table"), "group": "selected"},
        {"outcome": "no_relation", "reason": "family_no_relation", "family": None, "relation": None, "direction": None, "statement": None, "evidence_quote": None, "qualifiers": None, "family_reason": "Only listed together.", "grounding": None, "type_errors": None, "prompt_hashes": {"family": "h4"}, "pair": _pair("RP-1.1-1", "c_router", "c_switch"), "group": "selected"},
        {"outcome": "rejected", "reason": "domain_range", "family": "classification_structure", "relation": "part_of", "direction": "forward", "statement": "x", "evidence_quote": "connects links", "qualifiers": None, "family_reason": "x", "grounding": {"quote_x": True}, "type_errors": ["domain"], "prompt_hashes": {"family": "h5", "choice": "h6"}, "pair": _pair("RP-1.1-2", "c_switch", "c_forwarding_table", "A switch connects links."), "group": "selected"},
        {"outcome": "rejected", "reason": "endpoint_not_grounded", "family": "classification_structure", "relation": "is_a", "direction": "forward", "statement": "x", "evidence_quote": "repeats bits", "qualifiers": None, "family_reason": "x", "grounding": {"quote_x": False}, "type_errors": [], "prompt_hashes": {"family": "h7", "choice": "h8"}, "pair": _pair("RP-1.1-3", "c_hub", "c_forwarding_table", "A hub repeats bits."), "group": "selected"},
    ]  # fmt: skip
    cp = {
        "run_id": RUN, "stage": "snapshots", "concepts": [concept("c_router", "router", "Component", ["A router uses a forwarding table", "routers forward packets"]), concept("c_forwarding_table", "forwarding table", "Mechanism", ["uses a forwarding table"]),
                                                         concept("c_switch", "switch", "Component", ["a switch connects links"]), concept("c_hub", "hub", "Component", ["a hub repeats bits"]), concept("c_extra", "extra", "Component", ["an extra thing"])],
        "merges": [{"concept_id": "c_router", "alias": "routers", "section_id": "1.2#1", "llm_called": False, "auto_merged": True, "overridden": False, "reason": None, "similarity": 0.95, "rule_id": "exact", "evidence_quote": None, "stage": "canonicalize_v4"}],
        "taxonomy_candidates": [{"concept_id": "c_switch", "matched_concept_id": "c_router", "decision": "broader", "reason": "A switch is a kind of node, not a router.", "section_id": "1.1"}],
        "merge_review": [], "related_candidates": [], "anchors": [],
        "selected_pairs": [_pair("RP-1.1-0", "c_router", "c_forwarding_table"), _pair("RP-1.1-1", "c_router", "c_switch"), _pair("RP-1.1-2", "c_switch", "c_forwarding_table", "A switch connects links."), _pair("RP-1.1-3", "c_hub", "c_forwarding_table", "A hub repeats bits.")],
        "sample_pairs": [], "selection_stats": {"unique_candidate_pairs": 6, "selected": 4, "budget": 4, "min_per_section": 1},
        "relation_results_v3": results, "pair_registry": [], "misconceptions": {},
    }  # fmt: skip
    (d / "v4_concepts.json").write_text(json.dumps(v4), encoding="utf-8")
    (d / "checkpoint.json").write_text(json.dumps(cp), encoding="utf-8")
    nodes = [
        {
            "concept_id": c["concept_id"],
            "canonical_name": c["canonical_name"],
            "node_type": c["node_type"],
            "first_introduced_chapter": 1,
            "aliases": [],
            "mention_section_count": 1,
        }
        for c in cp["concepts"]
        if c["concept_id"] != "c_extra"
    ]
    (d / "snapshots/ch1/nodes.jsonl").write_text(
        "\n".join(json.dumps(n) for n in nodes) + "\n", encoding="utf-8"
    )
    (d / "snapshots/ch1/edges.jsonl").write_text(
        json.dumps(
            {
                "edge_id": "RP-1.1-0",
                "source_concept_id": "c_router",
                "relation": "uses",
                "target_concept_id": "c_forwarding_table",
                "family": "function_means",
                "source_chapter": 1,
                "target_chapter": 1,
                "section_id": "1.1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    pool = [
        ("RP-1.1-0", "c_router", "c_forwarding_table", 1, True),
        ("RP-1.1-1", "c_router", "c_switch", 2, True),
        ("RP-1.1-2", "c_switch", "c_forwarding_table", 3, True),
        ("RP-1.1-3", "c_hub", "c_forwarding_table", 4, True),
        ("RP-1.1-4", "c_router", "c_hub", 5, False),
        ("RP-1.1-5", "c_extra", "c_hub", 6, False),
    ]
    replay = {"valid": True, "mismatches": [], "eligible_count": 6, "budget": 4, "code_hashes": {}, "pool": [
        {"pair_id": pid, "pool_pair_id": pid, "pair_key": "|".join(sorted((x, y))), "concept_x_id": x, "concept_y_id": y, "section_id": "1.1", "best_occurrence_section": "1.1", "cue_score": 1.0, "cooccurrence_count": 2, "global_rank": rk,
         "rank_basis": "best-ranked occurrence of the concept pair", "section_rank": rk, "section_pool": 6, "selected": sel, "in_unselected_sample": False, "rank_key": [-1, -2, pid]} for pid, x, y, rk, sel in pool]}  # fmt: skip
    return d, replay


@pytest.fixture()
def built(tmp_path):
    d, replay = make_run(tmp_path)
    before = {p: _sha(p) for p in d.rglob("*") if p.is_file()}
    ad = PDAdapter(RUN, "pd", kg_root=tmp_path, calls_path=tmp_path / "none.jsonl")
    bf = ad.build(replay)
    return d, before, bf


def ev_of(bf, stage, action_prefix=None, obj=None):
    return [
        e
        for e in bf.store.events.values()
        if e.stage == stage
        and (action_prefix is None or e.action.startswith(action_prefix))
        and (obj is None or e.object_id == obj)
    ]


# ---------------------------------------------------------------- schema, integrity, round trip
def test_source_artifacts_are_byte_identical_after_a_trace_build(built):
    d, before, _ = built
    assert before == {p: _sha(p) for p in d.rglob("*") if p.is_file()}


def test_trace_event_round_trip_preserves_ids_stage_outcome_evidence_and_provenance(
    built, tmp_path
):
    _, _, bf = built
    h = bf.store.to_jsonl(tmp_path / "t.jsonl")
    back = TraceStore.from_jsonl(tmp_path / "t.jsonl")
    assert set(back.events) == set(bf.store.events)
    for eid, e in bf.store.events.items():
        b = back.events[eid]
        assert (
            b.stage,
            b.outcome,
            b.object_id,
            b.evidence_refs,
            b.model_id,
            b.prompt_version,
            b.source_artifact,
            b.source_locator,
            b.layer,
        ) == (
            e.stage,
            e.outcome,
            e.object_id,
            e.evidence_refs,
            e.model_id,
            e.prompt_version,
            e.source_artifact,
            e.source_locator,
            e.layer,
        )
    assert back.to_jsonl(tmp_path / "t2.jsonl") == h  # stable serialisation


def test_event_ids_are_deterministic_and_unique_and_extra_fields_are_rejected(built):
    _, _, bf = built
    assert make_event_id("r", "generator", "o", "a", "l") == make_event_id(
        "r", "generator", "o", "a", "l"
    )
    assert len(bf.store.events) == len({e.event_id for e in bf.store.events.values()})
    with pytest.raises(ValidationError):
        TraceEvent.model_validate(
            {**next(iter(bf.store.events.values())).model_dump(), "invented_field": 1}
        )


# ---------------------------------------------------------------- lineage (DAG)
def test_lineage_reaches_resolvable_evidence_for_final_nodes_and_edges(built):
    _, _, bf = built
    lin = L.Lineage(bf.links, bf.finals, bf.evidence)
    for oid in ("concept:c_router", "edge:RP-1.1-0"):
        tb = lin.trace_back(oid)
        assert tb["evidence"], oid
        for ref in tb["evidence"]:
            v = L.resolve(ref)
            assert isinstance(v, str) and v.strip(), ref


def test_many_mentions_fan_in_to_one_concept_and_many_evidence_fan_in_to_one_edge(built):
    _, _, bf = built
    lin = L.Lineage(bf.links, bf.finals, bf.evidence)
    tb = lin.trace_back("concept:c_router")
    mentions = [n for n in tb["nodes"] if n.startswith("mention:n_0001#")]
    assert len(mentions) == 3 and len(tb["evidence"]) >= 3
    edge = lin.trace_back("edge:RP-1.1-0")
    assert len([r for r in edge["evidence"] if "evidence_quote" in r or "sentence" in r]) >= 2
    assert (
        "concept:c_router" in edge["nodes"] and "concept:c_forwarding_table" in edge["nodes"]
    )  # endpoints reached through the pair and the committed edge


def test_joins_carry_method_and_key_and_ambiguous_joins_are_not_made(built):
    _, _, bf = built
    joined = [ln for ln in bf.links if ln["layer"] == "JOINED"]
    assert joined and all(
        ln["join"] and ln["join"]["method"] and ln["join"]["key"] for ln in joined
    )
    assert any(ln["join"]["method"] == "equal_pair_id_unique" for ln in joined)


# ---------------------------------------------------------------- renderer
def test_renderer_is_deterministic_and_every_value_is_supported_by_a_trace_field(built):
    _, _, bf = built
    first = [R.render_event(e) for e in bf.store.events.values()]
    second = [R.render_event(e) for e in bf.store.events.values()]
    assert (
        hashlib.sha256(json.dumps(first, sort_keys=True).encode()).hexdigest()
        == hashlib.sha256(json.dumps(second, sort_keys=True).encode()).hexdigest()
    )
    assert all(
        not R.verify_support(e, r) for e, r in zip(bf.store.events.values(), first, strict=True)
    )


def test_tampered_explanation_text_is_detected_by_the_support_check(built):
    _, _, bf = built
    e = ev_of(bf, "pair_selection", "rank_replayed", "pair:RP-1.1-4")[0]
    r = R.render_event(e)
    r["sentences"][0]["segments"][1]["text"] = "999"  # a number that is not the trace field
    assert R.verify_support(e, r)


def test_missing_reason_score_and_confidence_render_not_recorded(built):
    _, _, bf = built
    e = ev_of(bf, "relation_classification", "classify_pair", "relrow:RP-1.1-1:0")[0]
    r = R.render_event(e)
    assert (
        e.model_id is None
        and "model NOT_RECORDED" in r["text"]
        and "prompt version NOT_RECORDED" in r["text"]
    )
    assert "NOT_RECORDED" in r["text"] and "relation NOT_RECORDED" in r["text"]
    pr = R.render_event(ev_of(bf, "pruner", "prune_score")[0])
    assert "threshold: NOT_RECORDED" in pr["text"]


def test_pair_rank_above_and_below_the_selection_boundary_are_explained_from_the_trace(built):
    _, _, bf = built
    inside = R.render_event(ev_of(bf, "pair_selection", "rank_replayed", "pair:RP-1.1-3")[0])[
        "text"
    ]
    outside = R.render_event(ev_of(bf, "pair_selection", "rank_replayed", "pair:RP-1.1-4")[0])[
        "text"
    ]
    assert (
        "ranked 4 out of 6" in inside
        and "budget was 4" in inside
        and "outcome: selected" in inside
        and "REPLAYED" in inside
    )
    assert (
        "ranked 5 out of 6" in outside
        and "budget was 4" in outside
        and "outcome: not_selected" in outside
    )
    assert "not originally recorded" in outside


def test_a_recorded_taxonomy_guard_keeps_concepts_separate_and_shows_the_recorded_reason(built):
    _, _, bf = built
    r = R.render_event(ev_of(bf, "canonicalisation", "taxonomy_candidate")[0])["text"]
    assert (
        "not_selected" in r
        and "were not merged" in r
        and "A switch is a kind of node, not a router." in r
        and "broader" in r
    )


def test_relation_explanation_uses_only_stored_fields(built):
    _, _, bf = built
    text = R.render_event(
        ev_of(bf, "relation_classification", "classify_pair", "relrow:RP-1.1-0:0")[0]
    )["text"]
    for fact in (
        "uses",
        "forward",
        "function_means",
        "The sentence says the router relies on the table.",
        "uses a forwarding table",
    ):
        assert fact in text
    assert "confidence" not in text.lower().replace(
        "not_recorded", ""
    )  # no invented confidence wording


def test_authority_and_layer_labels_are_present_on_events(built):
    _, _, bf = built
    assert {e.authority for e in bf.store.events.values()} >= {
        "MODEL",
        "RULE",
        "SCORE",
        "STRUCTURAL",
    }
    assert {e.layer for e in bf.store.events.values()} == {"RECORDED", "REPLAYED", "JOINED"}
    assert all(e.layer != "RECORDED" or e.join is None for e in bf.store.events.values())


# ---------------------------------------------------------------- Why not? (production)
def wn(bf, a, b):
    return why_not(bf.store, a, b, pair_index(bf.store))


def test_why_not_localises_N0_P0_R0_R3_E0_and_reports_an_existing_edge(built):
    _, _, bf = built
    assert wn(bf, "concept:c_router", "concept:c_missing")["earliest_failure"] == "N0"
    assert (
        wn(bf, "concept:c_switch", "concept:c_hub")["earliest_failure"] == "P0"
    )  # not an eligible pair (replayed pool)
    out = wn(
        bf, "concept:c_router", "concept:c_hub"
    )  # eligible, rank 5 of 6, budget 4, not selected
    assert out["earliest_failure"] == "P0" and any(
        c["fields"].get("rank") == 5 and c["fields"].get("rank_layer") == "REPLAYED"
        for c in out["checks"]
    )
    assert wn(bf, "concept:c_router", "concept:c_switch")["earliest_failure"] == "R0"
    assert wn(bf, "concept:c_switch", "concept:c_forwarding_table")["earliest_failure"] == "R3"
    assert wn(bf, "concept:c_hub", "concept:c_forwarding_table")["earliest_failure"] == "E0"
    ok = wn(bf, "concept:c_router", "concept:c_forwarding_table")
    assert ok["earliest_failure"] is None and ok["status"] == "edge_exists"


def test_why_not_never_claims_a_missing_edge_should_exist_and_marks_unassessable_identity(built):
    _, _, bf = built
    out = wn(bf, "concept:c_router", "concept:c_hub")
    text = " ".join(out["sentences"]).lower()
    assert "should" not in text and "production mode" in out["note"]
    assert any(c["answer"] == "not_assessed_in_production" for c in out["checks"])


def test_why_not_without_a_replay_layer_says_unknown_instead_of_guessing(tmp_path):
    make_run(tmp_path)
    bf = PDAdapter(RUN, "pd", kg_root=tmp_path, calls_path=tmp_path / "none.jsonl").build(None)
    out = why_not(bf.store, "concept:c_router", "concept:c_hub")
    assert (
        any(c["answer"] == "unknown" for c in out["checks"])
        and out["earliest_failure"] is None
        and out["status"] == "unknown"
    )
    assert any(g["stage"] == "pair_selection" and g["status"] == "NOT_RECORDED" for g in bf.gaps)


# ---------------------------------------------------------------- Why not? (evaluation), frozen attribution order
BASE = {"endpoints": ("A", "B"), "span_status": ("exact", "exact"), "false_merge": (False, False), "split": (False, False), "pairs_proposed": (True,), "no_relation": (False,), "predicted_relations": ("uses",), "gold_relation": "uses",
            "symmetric": False, "reversed_only": False, "types_ok": True, "qualifiers_ok": True, "evidence_valid": True}  # fmt: skip


@pytest.mark.parametrize("change,code", [
    ({"span_status": ("absent", "exact")}, "N0"), ({"span_status": ("exact", "partial")}, "N1"), ({"false_merge": (True, False)}, "C1"),
    ({"split": (True, False), "pairs_proposed": (False, False), "predicted_relations": ()}, "C0"), ({"pairs_proposed": (False,), "predicted_relations": ()}, "P0"),
    ({"no_relation": (True,), "predicted_relations": ()}, "R0"), ({"predicted_relations": ("part_of",)}, "R1"), ({"reversed_only": True}, "R2"),
    ({"types_ok": False}, "R3"), ({"evidence_valid": False}, "E0"), ({}, None),
])  # fmt: skip
def test_evaluation_localiser_attributes_each_fixture_to_the_intended_stage(change, code):
    out = localise({**BASE, **change})
    assert out["code"] == code and "EVALUATION" in out["scope"]


def test_production_modules_never_import_gold_or_evaluation_code():
    for name in (
        "trace",
        "lineage",
        "render",
        "why_not",
        "coverage",
        "adapters_pd",
        "replay",
        "build",
    ):
        src = Path(f"src/cumap/explain/{name}.py").read_text()
        assert not re.search(
            r"^\s*(from|import)\s+cumap\.(cr012|explain\.why_not_eval)|data/gold",
            src,
            flags=re.MULTILINE,
        ), name


# ---------------------------------------------------------------- coverage, gaps, honesty
def test_coverage_reports_full_evidence_lineage_and_documents_gaps_honestly(built):
    _, _, bf = built
    lin = L.Lineage(bf.links, bf.finals, bf.evidence)
    cov = coverage(bf.store, lin, bf.finals, {}, bf.gaps)
    assert (
        cov["final_objects"]["concept"]["pct_lineage_to_evidence"] == 100.0
        and cov["final_objects"]["edge"]["pct_lineage_to_evidence"] == 100.0
    )
    assert (
        cov["evidence"]["pct_locators_resolve"] == 100.0
        and cov["explanations"]["pct_supported"] == 100.0
        and cov["explanations"]["pct_unknown_honesty"] == 100.0
    )
    fields = {(g["stage"], g["field"]) for g in bf.gaps if g["scope"] == "run"}
    assert {
        ("canonicalisation", "alias_provenance"),
        ("canonicalisation", "blocked_merges"),
        ("generator", "input_hash_link"),
        ("relation_classification", "confidence"),
        ("pruner", "threshold"),
    } <= fields
    assert [g["object_id"] for g in bf.gaps if g["status"] == "INCONSISTENT"] == [
        "concept:c_extra"
    ]  # the only inconsistency planted in the fixture is reported, with its id


def test_unresolvable_locators_are_reported_not_hidden(built):
    _, _, bf = built
    assert L.resolve(next(iter(bf.evidence.values()))[0] + "x") is None
    assert L.resolve("nonexistent/file.json::a.b") is None


def test_the_trace_build_twice_gives_the_identical_trace(tmp_path):
    _d, replay = make_run(tmp_path)
    a = (
        PDAdapter(RUN, "pd", kg_root=tmp_path, calls_path=tmp_path / "n.jsonl")
        .build(replay)
        .store.to_jsonl(tmp_path / "a.jsonl")
    )
    b = (
        PDAdapter(RUN, "pd", kg_root=tmp_path, calls_path=tmp_path / "n.jsonl")
        .build(replay)
        .store.to_jsonl(tmp_path / "b.jsonl")
    )
    assert a == b


# ---------------------------------------------------------------- the real slice3_c2 build (skipped when the derived output is absent)
def _latest_manifest():
    root = Path("data/processed/explainability/slice3_c2")
    ms = sorted(root.glob("*/manifest.json")) if root.exists() else []
    return json.loads(ms[-1].read_text()) if ms else None


@pytest.mark.skipif(_latest_manifest() is None, reason="derived trace for slice3_c2 not built")
def test_slice3_c2_trace_meets_the_stop2_integrity_and_coverage_criteria():
    m = _latest_manifest()
    assert (
        m["source_hashes_unchanged"]
        and m["replay_determinism_trace_hash_equal"]
        and m["base_commit"] == "2e50b6538ab5a8c97c9df3a218ab70646af90695"
    )
    assert (
        m["replay"]["valid"]
        and m["replay"]["mismatches"] == []
        and m["replay"].get("deterministic") is True
    )
    c = m["coverage"]
    assert (
        c["final_objects"]["concept"]["pct_lineage_to_evidence"] >= 95
        and c["final_objects"]["edge"]["pct_lineage_to_evidence"] >= 95
    )
    assert (
        c["evidence"]["pct_locators_resolve"] == 100.0
        and c["explanations"]["pct_supported"] == 100.0
        and c["explanations"]["pct_unknown_honesty"] == 100.0
    )


def test_explain_modules_make_no_model_call_and_import_no_llm_client():
    for f in Path("src/cumap/explain").glob("*.py"):
        src = f.read_text()
        assert not re.search(r"^\s*(from|import)\s+(openai|cumap\.llm)", src, flags=re.MULTILINE), f

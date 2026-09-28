"""CR-005 §2 task 4 tests: candidate pairs (Stage A) + family/relation/qualifier
calls (Stage B/C) for the M5 relation-extraction pipeline.
"""

from __future__ import annotations

from pathlib import Path

from cumap.expert_kg.canonicalize import RegisteredConcept
from cumap.expert_kg.relations import (
    classify_candidate_pair,
    extract_relations_for_section,
    find_candidate_pairs,
)
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

REPO_ROOT = Path(__file__).parents[1]

PARA_1 = "TCP uses the congestion window to limit how much unacknowledged data can be in flight."
PARA_2 = "Slow start is a separate mechanism that increases the congestion window rapidly at the start of a connection."
PARA_3 = "TCP relies on the congestion window throughout the connection."
SECTION_TEXT = f"{PARA_1}\n\n{PARA_2}\n\n{PARA_3}"


def _concept(concept_id, name) -> RegisteredConcept:
    return RegisteredConcept(
        concept_id=concept_id,
        canonical_name=name,
        node_type="Mechanism",
        definition=None,
        first_introduced="s1",
    )


def _concepts() -> list[RegisteredConcept]:
    return [
        _concept("c_tcp", "TCP"),
        _concept("c_congestion_window", "congestion window"),
        _concept("c_slow_start", "slow start"),
    ]


def _registry() -> RelationRegistry:
    return RelationRegistry.from_yaml(REPO_ROOT / "configs" / "relations_v1.yaml")


def _client(tmp_settings, fixtures_dir) -> LLMClient:
    return LLMClient(tmp_settings, fixtures_dir=fixtures_dir)


def _prompts():
    return (
        load_prompt(REPO_ROOT / "prompts", "relation_family", "v1"),
        load_prompt(REPO_ROOT / "prompts", "relation_choice", "v1"),
        load_prompt(REPO_ROOT / "prompts", "relation_qualifiers", "v1"),
    )


def test_find_candidate_pairs_from_paragraph_cooccurrence():
    pairs = find_candidate_pairs("s1", SECTION_TEXT, _concepts())
    pair_endpoints = {frozenset((p.concept_x_id, p.concept_y_id)) for p in pairs}
    assert frozenset(("c_tcp", "c_congestion_window")) in pair_endpoints
    assert frozenset(("c_congestion_window", "c_slow_start")) in pair_endpoints
    assert (
        frozenset(("c_tcp", "c_slow_start")) not in pair_endpoints
    )  # never co-occur in a paragraph


def test_find_candidate_pairs_dedupes_across_paragraphs():
    pairs = find_candidate_pairs("s1", SECTION_TEXT, _concepts())
    # TCP + congestion window co-occur in both paragraph 1 and paragraph 3, but should
    # only be proposed once (at its first occurrence).
    tcp_cw_pairs = [
        p for p in pairs if {p.concept_x_id, p.concept_y_id} == {"c_tcp", "c_congestion_window"}
    ]
    assert len(tcp_cw_pairs) == 1
    assert tcp_cw_pairs[0].paragraph == PARA_1


def test_find_candidate_pairs_empty_when_no_cooccurrence():
    pairs = find_candidate_pairs("s1", "Ethernet is a widely used LAN technology.", _concepts())
    assert pairs == []


def test_classify_candidate_pair_accepts_full_pipeline(tmp_settings, fixtures_dir):
    registry = _registry()
    concepts = _concepts()
    pair = find_candidate_pairs("s1", SECTION_TEXT, concepts)[
        0
    ]  # TCP / congestion window, from PARA_1
    family_prompt, relation_prompt, qualifier_prompt = _prompts()
    client = _client(tmp_settings, fixtures_dir)
    by_id = {c.concept_id: c for c in concepts}

    result = classify_candidate_pair(
        client,
        family_prompt,
        relation_prompt,
        qualifier_prompt,
        registry,
        pair,
        by_id[pair.concept_x_id],
        by_id[pair.concept_y_id],
        family_fixture="uses",
        relation_fixture="uses",
        qualifier_fixture="uses",
    )

    assert result.reason is None
    assert result.edge is not None
    assert result.edge.family == "function_means"
    assert result.edge.relation == "uses"
    assert result.edge.direction == "forward"
    assert result.edge.qualifiers.surface_phrase == "uses"
    assert client.backend_call_count == 3  # family + relation + qualifiers


def test_classify_candidate_pair_stops_at_no_relation(tmp_settings, fixtures_dir):
    registry = _registry()
    concepts = _concepts()
    pair = find_candidate_pairs("s1", SECTION_TEXT, concepts)[0]
    family_prompt, relation_prompt, qualifier_prompt = _prompts()
    client = _client(tmp_settings, fixtures_dir)
    by_id = {c.concept_id: c for c in concepts}

    result = classify_candidate_pair(
        client,
        family_prompt,
        relation_prompt,
        qualifier_prompt,
        registry,
        pair,
        by_id[pair.concept_x_id],
        by_id[pair.concept_y_id],
        family_fixture="no_relation",
    )

    assert result.edge is None
    assert result.reason == "family_no_relation"
    assert client.backend_call_count == 1  # relation/qualifier calls never happen


def test_classify_candidate_pair_stops_at_other_relation(tmp_settings, fixtures_dir):
    registry = _registry()
    concepts = _concepts()
    pair = find_candidate_pairs("s1", SECTION_TEXT, concepts)[0]
    family_prompt, relation_prompt, qualifier_prompt = _prompts()
    client = _client(tmp_settings, fixtures_dir)
    by_id = {c.concept_id: c for c in concepts}

    result = classify_candidate_pair(
        client,
        family_prompt,
        relation_prompt,
        qualifier_prompt,
        registry,
        pair,
        by_id[pair.concept_x_id],
        by_id[pair.concept_y_id],
        family_fixture="uses",
        relation_fixture="other",
    )

    assert result.edge is None
    assert result.reason == "relation_other"
    assert client.backend_call_count == 2  # qualifier call never happens


def test_classify_candidate_pair_rejects_bad_relation_evidence(tmp_settings, fixtures_dir):
    registry = _registry()
    concepts = _concepts()
    pair = find_candidate_pairs("s1", SECTION_TEXT, concepts)[0]
    family_prompt, relation_prompt, qualifier_prompt = _prompts()
    client = _client(tmp_settings, fixtures_dir)
    by_id = {c.concept_id: c for c in concepts}

    result = classify_candidate_pair(
        client,
        family_prompt,
        relation_prompt,
        qualifier_prompt,
        registry,
        pair,
        by_id[pair.concept_x_id],
        by_id[pair.concept_y_id],
        family_fixture="uses",
        relation_fixture="bad_evidence",
    )

    assert result.edge is None
    assert "evidence_quote" in result.reason


def test_classify_candidate_pair_rejects_bad_surface_phrase(tmp_settings, fixtures_dir):
    registry = _registry()
    concepts = _concepts()
    pair = find_candidate_pairs("s1", SECTION_TEXT, concepts)[0]
    family_prompt, relation_prompt, qualifier_prompt = _prompts()
    client = _client(tmp_settings, fixtures_dir)
    by_id = {c.concept_id: c for c in concepts}

    result = classify_candidate_pair(
        client,
        family_prompt,
        relation_prompt,
        qualifier_prompt,
        registry,
        pair,
        by_id[pair.concept_x_id],
        by_id[pair.concept_y_id],
        family_fixture="uses",
        relation_fixture="uses",
        qualifier_fixture="bad_surface_phrase",
    )

    assert result.edge is None
    assert "surface_phrase" in result.reason


def test_extract_relations_for_section_orchestrates_all_pairs(tmp_settings, fixtures_dir):
    registry = _registry()
    concepts = _concepts()
    family_prompt, relation_prompt, qualifier_prompt = _prompts()
    client = _client(tmp_settings, fixtures_dir)

    def fixture_for_pair(pair):
        if {pair.concept_x_id, pair.concept_y_id} == {"c_tcp", "c_congestion_window"}:
            return "uses", "uses", "uses"
        return "no_relation", "default", "default"

    results = extract_relations_for_section(
        client,
        family_prompt,
        relation_prompt,
        qualifier_prompt,
        registry,
        section_id="s1",
        section_text=SECTION_TEXT,
        concepts=concepts,
        fixture_for_pair=fixture_for_pair,
    )

    assert len(results) == 2  # TCP/congestion window, congestion window/slow start
    accepted = [r for r in results if r.edge is not None]
    rejected = [r for r in results if r.edge is None]
    assert len(accepted) == 1
    assert accepted[0].edge.relation == "uses"
    assert len(rejected) == 1
    assert rejected[0].reason == "family_no_relation"

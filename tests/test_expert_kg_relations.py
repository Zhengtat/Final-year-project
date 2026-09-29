"""CR-005 §2 task 4 tests, redesigned by §9: sentence-level candidate pairs (Stage A)
+ family/relation/qualifier calls (Stage B/C) + run-level pair dedup (PairRegistry).
"""

from __future__ import annotations

from pathlib import Path

from cumap.expert_kg.canonicalize import RegisteredConcept
from cumap.expert_kg.relations import (
    PairRegistry,
    classify_candidate_pair,
    extract_relations_for_section,
    find_candidate_pairs,
)
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

REPO_ROOT = Path(__file__).parents[1]

SENT_1 = "TCP uses the congestion window to limit how much unacknowledged data can be in flight."
SENT_2 = "Slow start is a separate mechanism that increases the congestion window rapidly at the start of a connection."
SENT_3 = "TCP relies on the congestion window throughout the connection."
SECTION_TEXT = f"{SENT_1} {SENT_2} {SENT_3}"


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
        load_prompt(REPO_ROOT / "prompts", "relation_family", "v2"),
        load_prompt(REPO_ROOT / "prompts", "relation_choice", "v2"),
        load_prompt(REPO_ROOT / "prompts", "relation_qualifiers", "v2"),
    )


def test_find_candidate_pairs_from_sentence_cooccurrence():
    kept, overflow = find_candidate_pairs("s1", SECTION_TEXT, _concepts(), _registry())
    pair_endpoints = {frozenset((p.concept_x_id, p.concept_y_id)) for p in kept}
    assert frozenset(("c_tcp", "c_congestion_window")) in pair_endpoints
    assert frozenset(("c_congestion_window", "c_slow_start")) in pair_endpoints
    assert frozenset(("c_tcp", "c_slow_start")) not in pair_endpoints  # never share a sentence
    assert overflow == []


def test_find_candidate_pairs_dedupes_within_a_section():
    kept, _ = find_candidate_pairs("s1", SECTION_TEXT, _concepts(), _registry())
    # TCP + congestion window co-occur in both sentence 1 and sentence 3, but should
    # only be proposed once per section, with cooccurrence_count reflecting both.
    tcp_cw_pairs = [
        p for p in kept if {p.concept_x_id, p.concept_y_id} == {"c_tcp", "c_congestion_window"}
    ]
    assert len(tcp_cw_pairs) == 1
    assert tcp_cw_pairs[0].sentence == SENT_1
    assert tcp_cw_pairs[0].cooccurrence_count == 2


def test_find_candidate_pairs_empty_when_no_cooccurrence():
    kept, overflow = find_candidate_pairs(
        "s1", "Ethernet is a widely used LAN technology.", _concepts(), _registry()
    )
    assert kept == []
    assert overflow == []


def test_find_candidate_pairs_respects_window():
    # sentence 2 and sentence 3 don't share concepts within window=0, but slow start
    # (sentence 2) and TCP (sentences 1 and 3) become a pair once window=1 allows it.
    kept0, _ = find_candidate_pairs("s1", SECTION_TEXT, _concepts(), _registry(), window=0)
    kept1, _ = find_candidate_pairs("s1", SECTION_TEXT, _concepts(), _registry(), window=1)
    endpoints0 = {frozenset((p.concept_x_id, p.concept_y_id)) for p in kept0}
    endpoints1 = {frozenset((p.concept_x_id, p.concept_y_id)) for p in kept1}
    assert frozenset(("c_tcp", "c_slow_start")) not in endpoints0
    assert frozenset(("c_tcp", "c_slow_start")) in endpoints1


def test_find_candidate_pairs_caps_and_logs_overflow():
    # 3 concepts sharing one sentence -> 3 pairs total; capping at 2 must move exactly
    # 1 to overflow, never silently drop it.
    kept, overflow = find_candidate_pairs(
        "s1", SECTION_TEXT, _concepts(), _registry(), window=2, max_pairs=2
    )
    assert len(kept) == 2
    assert len(overflow) == 1


def test_classify_candidate_pair_accepts_full_pipeline(tmp_settings, fixtures_dir):
    registry = _registry()
    concepts = _concepts()
    kept, _ = find_candidate_pairs("s1", SECTION_TEXT, concepts, registry)
    pair = kept[0]  # TCP / congestion window
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
    kept, _ = find_candidate_pairs("s1", SECTION_TEXT, concepts, registry)
    pair = kept[0]
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
    kept, _ = find_candidate_pairs("s1", SECTION_TEXT, concepts, registry)
    pair = kept[0]
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
    kept, _ = find_candidate_pairs("s1", SECTION_TEXT, concepts, registry)
    pair = kept[0]
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
    kept, _ = find_candidate_pairs("s1", SECTION_TEXT, concepts, registry)
    pair = kept[0]
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
    pair_registry = PairRegistry()

    def fixture_for_pair(pair):
        if {pair.concept_x_id, pair.concept_y_id} == {"c_tcp", "c_congestion_window"}:
            return "uses", "uses", "uses"
        return "no_relation", "default", "default"

    result = extract_relations_for_section(
        client,
        family_prompt,
        relation_prompt,
        qualifier_prompt,
        registry,
        pair_registry,
        section_id="s1",
        section_text=SECTION_TEXT,
        concepts=concepts,
        fixture_for_pair=fixture_for_pair,
    )

    assert len(result.classifications) == 2  # TCP/cwnd, cwnd/slow_start
    accepted = [r for r in result.classifications if r.edge is not None]
    rejected = [r for r in result.classifications if r.edge is None]
    assert len(accepted) == 1
    assert accepted[0].edge.relation == "uses"
    assert len(rejected) == 1
    assert rejected[0].reason == "family_no_relation"


def test_pair_repeated_across_three_sections_is_classified_once(tmp_settings, fixtures_dir):
    """CR-005 §9 item 6's required regression test."""
    registry = _registry()
    concepts = _concepts()
    family_prompt, relation_prompt, qualifier_prompt = _prompts()
    client = _client(tmp_settings, fixtures_dir)
    pair_registry = PairRegistry()

    def fixture_for_pair(pair):
        return "uses", "uses", "uses"

    section_text = SENT_1  # TCP + congestion window, same pair every time
    for i in range(3):
        extract_relations_for_section(
            client,
            family_prompt,
            relation_prompt,
            qualifier_prompt,
            registry,
            pair_registry,
            section_id=f"s{i}",
            section_text=section_text,
            concepts=concepts,
            fixture_for_pair=fixture_for_pair,
        )

    assert client.backend_call_count == 3  # family + relation + qualifiers, ONCE total
    resolution = pair_registry.get("c_tcp", "c_congestion_window")
    assert resolution.resolved is True
    assert len(resolution.evidence_sentences) == 1  # SENT_1 repeated, deduped (not "1 per section")


def test_pair_registry_records_no_relation_as_resolved_terminal():
    registry = PairRegistry()
    registry.resolve("c_a", "c_b", edge=None, reason="family_no_relation")
    assert registry.is_resolved("c_a", "c_b") is True
    assert registry.get("c_a", "c_b").edge is None
    assert registry.get("c_a", "c_b").reason == "family_no_relation"

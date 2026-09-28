"""CR-001 §7.2 acceptance tests: v2 suggest-expert/suggest-student (registry-aware
qualifiers, chain-link proposals), via the mock LLM backend."""

from __future__ import annotations

from pathlib import Path

from cumap.gold.suggest_expert import suggest_expert_subgraph_v2
from cumap.gold.suggest_student import suggest_student_graph_v2
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

REPO_ROOT = Path(__file__).parents[1]
V1_REGISTRY_PATH = REPO_ROOT / "configs" / "relations_v1.yaml"

SECTION_TEXT = (
    "TCP performs slow start. Slow start is part of TCP congestion control. "
    "A timeout triggers cwnd reset because a timeout signals severe congestion."
)


def _client(tmp_settings, fixtures_dir) -> LLMClient:
    return LLMClient(tmp_settings, fixtures_dir=fixtures_dir)


def test_suggest_expert_v2_applies_qualifiers_and_relation_family(tmp_settings, fixtures_dir):
    registry = RelationRegistry.from_yaml(V1_REGISTRY_PATH)
    prompt_template = load_prompt(REPO_ROOT / "prompts", "expert_subgraph", "v2")
    client = _client(tmp_settings, fixtures_dir)

    draft = suggest_expert_subgraph_v2(
        client,
        prompt_template,
        registry,
        question_id="q_12345678",
        question="Explain TCP slow start.",
        reference_answer="TCP performs slow start as part of congestion control.",
        section_ids=["6.3"],
        sections_by_id={"6.3": SECTION_TEXT},
        fixture_name="v2",
    )

    assert draft["rejected"] == []
    assert draft["registry_version"] == 1
    assert len(draft["concepts"]) == 5
    assert len(draft["edges"]) == 3

    part_of_edge = next(e for e in draft["edges"] if e["relation"] == "part_of")
    assert part_of_edge["part_type"] == "phase"
    assert part_of_edge["relation_family"] == "classification_structure"

    performs_edge = next(e for e in draft["edges"] if e["relation"] == "performs")
    assert performs_edge["relation_family"] == "mechanism_process"
    assert performs_edge["surface_phrase"] == "performs"


def test_suggest_expert_v2_resolves_chain_link_indices_to_real_edge_ids(tmp_settings, fixtures_dir):
    registry = RelationRegistry.from_yaml(V1_REGISTRY_PATH)
    prompt_template = load_prompt(REPO_ROOT / "prompts", "expert_subgraph", "v2")
    client = _client(tmp_settings, fixtures_dir)

    draft = suggest_expert_subgraph_v2(
        client,
        prompt_template,
        registry,
        question_id="q_87654321",
        question="Explain TCP slow start.",
        reference_answer="TCP performs slow start as part of congestion control.",
        section_ids=["6.3"],
        sections_by_id={"6.3": SECTION_TEXT},
        fixture_name="v2",
    )

    assert len(draft["chain_links"]) == 1
    link = draft["chain_links"][0]
    assert link["type"] == "cause"
    triggers_edge_id = next(e["edge_id"] for e in draft["edges"] if e["relation"] == "triggers")
    performs_edge_id = next(e["edge_id"] for e in draft["edges"] if e["relation"] == "performs")
    assert link["from_edge_id"] == triggers_edge_id
    assert link["to_edge_id"] == performs_edge_id


def test_suggest_expert_v2_rejects_unverified_edge_and_dangling_chain_link(tmp_settings, fixtures_dir):
    registry = RelationRegistry.from_yaml(V1_REGISTRY_PATH)
    prompt_template = load_prompt(REPO_ROOT / "prompts", "expert_subgraph", "v2")
    client = _client(tmp_settings, fixtures_dir)

    draft = suggest_expert_subgraph_v2(
        client,
        prompt_template,
        registry,
        question_id="q_99999999",
        question="Explain TCP slow start.",
        reference_answer="TCP performs slow start.",
        section_ids=["6.3"],
        sections_by_id={"6.3": SECTION_TEXT},
        fixture_name="v2_with_rejections",
    )

    assert draft["edges"] == []  # the one edge had an unverifiable evidence_quote
    assert draft["chain_links"] == []  # its chain link referenced a rejected/out-of-range edge
    reasons = [r["reason"] for r in draft["rejected"]]
    assert any("evidence_quote not found" in r for r in reasons)
    assert any("from/to edge index was rejected or out of range" in r for r in reasons)


def test_suggest_student_v2_applies_qualifiers_and_resolves_chain_links(tmp_settings, fixtures_dir):
    registry = RelationRegistry.from_yaml(V1_REGISTRY_PATH)
    prompt_template = load_prompt(REPO_ROOT / "prompts", "student_graph", "v2")
    client = _client(tmp_settings, fixtures_dir)

    answer_text = "TCP performs slow start because it wants to probe available bandwidth."
    known_concepts = [{"canonical_name": "TCP", "node_type": "Protocol", "concept_id": "c_tcp"}]

    draft = suggest_student_graph_v2(
        client,
        prompt_template,
        registry,
        answer_id="a_1234567890",
        question_id="q_12345678",
        question="Explain TCP slow start.",
        answer_text=answer_text,
        known_concepts=known_concepts,
        fixture_name="v2",
    )

    assert draft["rejected"] == []
    assert draft["registry_version"] == 1
    assert len(draft["edges"]) == 2
    linked_edge = draft["edges"][0]
    assert linked_edge["source_id"] == "c_tcp"
    unlinked_edge = draft["edges"][1]
    assert unlinked_edge["source_id"] == "unlinked:it"
    assert unlinked_edge["link_confidence"] == 0.0  # forced to 0 when both endpoints unlinked

    assert len(draft["chain_links"]) == 1
    link = draft["chain_links"][0]
    assert link["from_edge_id"] == "SE-0"
    assert link["to_edge_id"] == "SE-1"
    assert link["type"] == "purpose"

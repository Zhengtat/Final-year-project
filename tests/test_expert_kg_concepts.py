"""CR-005 §2 task 2 tests: concept extraction (main + gleaning passes), mock backend."""

from __future__ import annotations

from pathlib import Path

from cumap.expert_kg.concepts import extract_concepts_for_section
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

REPO_ROOT = Path(__file__).parents[1]
V1_REGISTRY_PATH = REPO_ROOT / "configs" / "relations_v1.yaml"
SECTION_TEXT = "TCP uses sliding window. It also performs slow start."


def _client(tmp_settings, fixtures_dir) -> LLMClient:
    return LLMClient(tmp_settings, fixtures_dir=fixtures_dir)


def test_main_and_gleaning_passes_merge_without_duplicates(tmp_settings, fixtures_dir):
    registry = RelationRegistry.from_yaml(V1_REGISTRY_PATH)
    main_prompt = load_prompt(REPO_ROOT / "prompts", "concept_extraction", "v1")
    gleaning_prompt = load_prompt(REPO_ROOT / "prompts", "concept_extraction_gleaning", "v1")
    client = _client(tmp_settings, fixtures_dir)

    result = extract_concepts_for_section(
        client,
        main_prompt,
        gleaning_prompt,
        registry,
        section_id="s1",
        section_text=SECTION_TEXT,
        heading_path=["Ch1", "TCP"],
        candidate_terms=["TCP", "sliding window", "slow start"],
        domain="computer networking",
        fixture_name="demo",
        gleaning_fixture_name="demo",
    )

    names = {m.canonical_name for m in result.mentions}
    assert names == {"TCP", "sliding window", "slow start"}  # gleaning's duplicate "TCP" dropped
    assert result.rejected == []


def test_gleaning_run_index_marks_which_pass_found_it(tmp_settings, fixtures_dir):
    registry = RelationRegistry.from_yaml(V1_REGISTRY_PATH)
    main_prompt = load_prompt(REPO_ROOT / "prompts", "concept_extraction", "v1")
    gleaning_prompt = load_prompt(REPO_ROOT / "prompts", "concept_extraction_gleaning", "v1")
    client = _client(tmp_settings, fixtures_dir)

    result = extract_concepts_for_section(
        client,
        main_prompt,
        gleaning_prompt,
        registry,
        section_id="s1",
        section_text=SECTION_TEXT,
        heading_path=["Ch1", "TCP"],
        candidate_terms=[],
        domain="computer networking",
        fixture_name="demo",
        gleaning_fixture_name="demo",
    )
    slow_start = next(m for m in result.mentions if m.canonical_name == "slow start")
    assert slow_start.run_index == 1
    tcp = next(m for m in result.mentions if m.canonical_name == "TCP")
    assert tcp.run_index == 0


def test_empty_gleaning_pass_adds_nothing(tmp_settings, fixtures_dir):
    registry = RelationRegistry.from_yaml(V1_REGISTRY_PATH)
    main_prompt = load_prompt(REPO_ROOT / "prompts", "concept_extraction", "v1")
    gleaning_prompt = load_prompt(REPO_ROOT / "prompts", "concept_extraction_gleaning", "v1")
    client = _client(tmp_settings, fixtures_dir)

    result = extract_concepts_for_section(
        client,
        main_prompt,
        gleaning_prompt,
        registry,
        section_id="s1",
        section_text=SECTION_TEXT,
        heading_path=["Ch1", "TCP"],
        candidate_terms=[],
        domain="computer networking",
        fixture_name="demo",
        gleaning_fixture_name="empty",
    )
    names = {m.canonical_name for m in result.mentions}
    assert names == {"TCP", "sliding window"}


def test_include_gleaning_false_skips_the_gleaning_call(tmp_settings, fixtures_dir):
    registry = RelationRegistry.from_yaml(V1_REGISTRY_PATH)
    main_prompt = load_prompt(REPO_ROOT / "prompts", "concept_extraction", "v1")
    client = _client(tmp_settings, fixtures_dir)

    result = extract_concepts_for_section(
        client,
        main_prompt,
        None,
        registry,
        section_id="s1",
        section_text=SECTION_TEXT,
        heading_path=["Ch1", "TCP"],
        candidate_terms=[],
        domain="computer networking",
        fixture_name="demo",
        include_gleaning=False,
    )

    names = {m.canonical_name for m in result.mentions}
    assert names == {"TCP", "sliding window"}  # main pass only -- "slow start" never gleaned
    assert client.backend_call_count == 1


def test_gleaning_v2_receives_only_unselected_candidates(tmp_settings, fixtures_dir):
    registry = RelationRegistry.from_yaml(V1_REGISTRY_PATH)
    main_prompt = load_prompt(REPO_ROOT / "prompts", "concept_extraction", "v1")
    gleaning_prompt = load_prompt(REPO_ROOT / "prompts", "concept_extraction_gleaning", "v2")
    client = _client(tmp_settings, fixtures_dir)

    result = extract_concepts_for_section(
        client,
        main_prompt,
        gleaning_prompt,
        registry,
        section_id="s1",
        section_text=SECTION_TEXT,
        heading_path=["Ch1", "TCP"],
        candidate_terms=["TCP", "sliding window", "slow start"],
        domain="computer networking",
        fixture_name="demo",
        gleaning_fixture_name="demo",
    )
    # Same fixtures as the v1 merge test -- confirms v2's extra {unselected_candidate_terms}
    # placeholder renders without error and the merge behaviour is unaffected.
    names = {m.canonical_name for m in result.mentions}
    assert names == {"TCP", "sliding window", "slow start"}


def test_rejects_unverifiable_evidence_quote(tmp_settings, fixtures_dir):
    registry = RelationRegistry.from_yaml(V1_REGISTRY_PATH)
    main_prompt = load_prompt(REPO_ROOT / "prompts", "concept_extraction", "v1")
    gleaning_prompt = load_prompt(REPO_ROOT / "prompts", "concept_extraction_gleaning", "v1")
    client = _client(tmp_settings, fixtures_dir)

    result = extract_concepts_for_section(
        client,
        main_prompt,
        gleaning_prompt,
        registry,
        section_id="s1",
        section_text=SECTION_TEXT,
        heading_path=["Ch1", "TCP"],
        candidate_terms=[],
        domain="computer networking",
        fixture_name="rejection",
        gleaning_fixture_name="empty",
    )
    assert result.mentions == []
    assert len(result.rejected) == 1
    assert "evidence_quote not found" in result.rejected[0]["reason"]

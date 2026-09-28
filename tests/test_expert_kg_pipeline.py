"""CR-005 §2 pipeline orchestration smoke tests: multi-section, multi-chapter
end-to-end wiring (growing registry, snapshot writing) and the live budget-cap
enforcement added before the real calibration/IIR-dev run (spend_for_run-based hard
stop, not just the pre-run cost_estimate.py prediction).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from cumap.expert_kg.pipeline import PromptSet, SectionInput, run_slice
from cumap.llm.client import LLMClient
from cumap.schemas.relations import RelationRegistry

REPO_ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def nlp():
    import spacy

    return spacy.load("en_core_web_sm")


def _fake_embed(text: str) -> np.ndarray:
    """Distinct vocab per concept name used in this test, so no two *different*
    concepts are similar enough to trigger a canonicalize LLM call, but the *same*
    name re-embeds identically (similarity 1.0) so a genuine re-mention across
    chapters does trigger one (tested indirectly via chapter grouping, not asserted
    on directly here -- kept simple to avoid needing extra canonicalize fixtures).
    """
    vocab = ["tcp", "sliding", "window", "slow", "start", "congestion"]
    text_lower = text.lower()
    return np.array([1.0 if w in text_lower else 0.0 for w in vocab])


def _registry() -> RelationRegistry:
    return RelationRegistry.from_yaml(REPO_ROOT / "configs" / "relations_v1.yaml")


def _prompts() -> PromptSet:
    return PromptSet.load(REPO_ROOT / "prompts")


def _sections() -> list[SectionInput]:
    return [
        SectionInput(
            section_id="ch1_s1",
            chapter_num=1,
            text="TCP uses sliding window. It also performs slow start.",
            heading_path=["Chapter 1"],
            domain="computer networking",
        ),
        SectionInput(
            section_id="ch2_s1",
            chapter_num=2,
            text="Congestion window differs from sliding window in scope.",
            heading_path=["Chapter 2"],
            domain="computer networking",
        ),
    ]


def _no_relation_fixtures(pair):
    return "no_relation", "default", "default"


def test_run_slice_processes_both_chapters_and_writes_snapshots(
    tmp_settings, fixtures_dir, tmp_path, nlp
):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    registry = _registry()
    prompts = _prompts()
    from cumap.expert_kg import pipeline as pipeline_module

    original_extract = pipeline_module.extract_relations_for_section
    original_concepts = pipeline_module.extract_concepts_for_section

    def patched_extract(*args, **kwargs):
        kwargs["fixture_for_pair"] = _no_relation_fixtures
        return original_extract(*args, **kwargs)

    def patched_concepts(client_, main_prompt, gleaning_prompt, registry_, *, section_id, **kwargs):
        # extract_concepts_for_section has no per-section fixture hook, so route by
        # section_id here instead -- the real pipeline routes by real content, not a
        # fixture name, so this indirection is test-only.
        fixture_name = "demo" if section_id == "ch1_s1" else "congestion_window"
        gleaning_fixture = "demo" if section_id == "ch1_s1" else "empty"
        return original_concepts(
            client_,
            main_prompt,
            gleaning_prompt,
            registry_,
            section_id=section_id,
            fixture_name=fixture_name,
            gleaning_fixture_name=gleaning_fixture,
            **kwargs,
        )

    pipeline_module.extract_relations_for_section = patched_extract
    pipeline_module.extract_concepts_for_section = patched_concepts
    try:
        result = run_slice(
            client,
            tmp_settings,
            registry,
            prompts,
            _fake_embed,
            _sections(),
            nlp,
            snapshots_dir=tmp_path / "snapshots",
        )
    finally:
        pipeline_module.extract_relations_for_section = original_extract
        pipeline_module.extract_concepts_for_section = original_concepts

    assert result.stopped_early is False
    assert [c.chapter_num for c in result.chapters] == [1, 2]

    ch1 = result.chapters[0].snapshot
    ch1_names = {n.canonical_name for n in ch1.nodes}
    assert {"TCP", "sliding window", "slow start"} <= ch1_names

    ch2 = result.chapters[1].snapshot
    ch2_names = {n.canonical_name for n in ch2.nodes}
    assert "congestion window" in ch2_names

    assert (tmp_path / "snapshots" / "ch1" / "manifest.json").exists()
    assert (tmp_path / "snapshots" / "ch2" / "manifest.json").exists()


def test_run_slice_stops_before_exceeding_budget(tmp_settings, fixtures_dir, tmp_path, nlp):
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    registry = _registry()
    prompts = _prompts()
    from cumap.expert_kg import pipeline as pipeline_module

    original_extract = pipeline_module.extract_relations_for_section
    original_concepts = pipeline_module.extract_concepts_for_section

    def patched_extract(*args, **kwargs):
        kwargs["fixture_for_pair"] = _no_relation_fixtures
        return original_extract(*args, **kwargs)

    def patched_concepts(client_, main_prompt, gleaning_prompt, registry_, *, section_id, **kwargs):
        fixture_name = "demo" if section_id == "ch1_s1" else "congestion_window"
        gleaning_fixture = "demo" if section_id == "ch1_s1" else "empty"
        return original_concepts(
            client_,
            main_prompt,
            gleaning_prompt,
            registry_,
            section_id=section_id,
            fixture_name=fixture_name,
            gleaning_fixture_name=gleaning_fixture,
            **kwargs,
        )

    pipeline_module.extract_relations_for_section = patched_extract
    pipeline_module.extract_concepts_for_section = patched_concepts
    try:
        # Any real spend at all (chapter 1's mock calls still log nonzero token usage,
        # costed at tmp_settings' real tier prices) exceeds this near-zero cap, so
        # chapter 2 must never be processed.
        result = run_slice(
            client,
            tmp_settings,
            registry,
            prompts,
            _fake_embed,
            _sections(),
            nlp,
            snapshots_dir=tmp_path / "snapshots",
            max_usd_per_command=1e-9,
        )
    finally:
        pipeline_module.extract_relations_for_section = original_extract
        pipeline_module.extract_concepts_for_section = original_concepts

    assert (
        len(result.chapters) == 1
    )  # chapter 1 always runs; the cap is checked *before* each chapter
    assert result.stopped_early is True
    assert "cap" in result.stop_reason

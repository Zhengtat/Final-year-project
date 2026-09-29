"""CR-005 §2 pipeline tests, redesigned by §9: stage-by-stage orchestration
(concepts -> canonicalize -> offline pair enumeration -> relations -> snapshots),
checkpoint/resume, and the regression tests §9 item 6 explicitly asks for.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from cumap.config import load_demo_slice
from cumap.expert_kg import pipeline as pipeline_module
from cumap.expert_kg.pipeline import (
    Checkpoint,
    PromptSet,
    SectionInput,
    build_snapshots_stage,
    enumerate_pairs_stage,
    load_checkpoint,
    run_canonicalize_stage,
    run_concepts_stage,
    run_relations_stage,
)
from cumap.llm.client import BudgetExceededError, LLMClient
from cumap.schemas.relations import RelationRegistry

REPO_ROOT = Path(__file__).parents[1]


def _fake_embed(text: str) -> np.ndarray:
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


@pytest.fixture(scope="module")
def nlp():
    import spacy

    return spacy.load("en_core_web_sm")


def _patch_concepts(monkeypatch):
    original = pipeline_module.extract_concepts_for_section

    def patched(client_, main_prompt, gleaning_prompt, registry_, *, section_id, **kwargs):
        fixture_name = "demo" if section_id == "ch1_s1" else "congestion_window"
        gleaning_fixture = "demo" if section_id == "ch1_s1" else "empty"
        return original(
            client_,
            main_prompt,
            gleaning_prompt,
            registry_,
            section_id=section_id,
            fixture_name=fixture_name,
            gleaning_fixture_name=gleaning_fixture,
            **kwargs,
        )

    monkeypatch.setattr(pipeline_module, "extract_concepts_for_section", patched)


def _patch_relations_no_relation(monkeypatch):
    original = pipeline_module.extract_relations_for_section

    def patched(*args, **kwargs):
        kwargs["fixture_for_pair"] = lambda pair: ("no_relation", "default", "default")
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline_module, "extract_relations_for_section", patched)


def test_full_stage_pipeline_end_to_end(tmp_settings, fixtures_dir, tmp_path, nlp, monkeypatch):
    _patch_concepts(monkeypatch)
    _patch_relations_no_relation(monkeypatch)

    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    registry = _registry()
    prompts = _prompts()
    sections = _sections()
    run_dir = tmp_path / "run"

    checkpoint = Checkpoint(run_id=client.run_id, stage="concepts")
    checkpoint = run_concepts_stage(
        client, prompts, registry, sections, nlp, run_dir, checkpoint, include_gleaning=True
    )
    assert checkpoint.stage == "canonicalize"
    assert set(checkpoint.mentions_by_section) == {"ch1_s1", "ch2_s1"}

    checkpoint, concept_registry = run_canonicalize_stage(
        client, prompts, sections, _fake_embed, run_dir, checkpoint
    )
    assert checkpoint.stage == "pairs_enumerated"
    names = {c.canonical_name for c in concept_registry.all()}
    assert {"TCP", "sliding window", "slow start", "congestion window"} <= names

    enumeration = enumerate_pairs_stage(registry, sections, concept_registry)
    assert len(enumeration.per_section) == 2
    assert enumeration.total_new_pairs >= 0

    checkpoint, pair_registry = run_relations_stage(
        client, prompts, registry, sections, concept_registry, run_dir, checkpoint
    )
    assert checkpoint.stage == "snapshots"

    results = build_snapshots_stage(
        registry,
        sections,
        concept_registry,
        pair_registry,
        run_dir / "snapshots",
        client.run_id,
        merges=checkpoint.merges,
    )
    assert [r.chapter_num for r in results] == [1, 2]
    assert (run_dir / "snapshots" / "ch1" / "manifest.json").exists()
    assert (run_dir / "snapshots" / "ch2" / "manifest.json").exists()


def test_concepts_stage_checkpoint_resume_skips_completed_sections(
    tmp_settings, fixtures_dir, tmp_path, nlp, monkeypatch
):
    _patch_concepts(monkeypatch)
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    registry = _registry()
    prompts = _prompts()
    sections = _sections()
    run_dir = tmp_path / "run"

    checkpoint = Checkpoint(run_id=client.run_id, stage="concepts")
    checkpoint = run_concepts_stage(
        client, prompts, registry, sections[:1], nlp, run_dir, checkpoint, include_gleaning=True
    )
    calls_after_first_section = client.backend_call_count

    # "Resume": load the checkpoint back and continue with the full section list.
    checkpoint.stage = (
        "concepts"  # run_concepts_stage advances it to "canonicalize"; reset for resume
    )
    checkpoint.completed_section_ids = ["ch1_s1"]
    checkpoint = run_concepts_stage(
        client, prompts, registry, sections, nlp, run_dir, checkpoint, include_gleaning=True
    )

    # ch1_s1 must not be re-processed (no new calls for it, only ch2_s1's).
    assert client.backend_call_count == calls_after_first_section + 2  # ch2_s1: main + gleaning
    assert set(checkpoint.mentions_by_section) == {"ch1_s1", "ch2_s1"}


def test_run_concepts_stage_defaults_to_no_gleaning(
    tmp_settings, fixtures_dir, tmp_path, nlp, monkeypatch
):
    """CR-005 §9's STOP-2 ablation chose "v2" (no gleaning) over "v2+g" -- confirms
    run_concepts_stage's default matches that decision.
    """
    _patch_concepts(monkeypatch)
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    registry = _registry()
    prompts = _prompts()
    run_dir = tmp_path / "run"

    checkpoint = Checkpoint(run_id=client.run_id, stage="concepts")
    checkpoint = run_concepts_stage(
        client, prompts, registry, _sections()[:1], nlp, run_dir, checkpoint
    )

    assert client.backend_call_count == 1  # main pass only, no gleaning call
    names = {m["canonical_name"] for m in checkpoint.mentions_by_section["ch1_s1"]}
    assert "slow start" not in names  # only found by the (skipped) gleaning fixture


def test_budget_exceeded_stops_mid_run_and_checkpoints(
    tmp_settings, fixtures_dir, tmp_path, nlp, monkeypatch
):
    _patch_concepts(monkeypatch)
    tmp_settings.llm.max_usd_per_command = 0.0000001  # any real call exceeds this
    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    registry = _registry()
    prompts = _prompts()
    sections = _sections()
    run_dir = tmp_path / "run"

    checkpoint = Checkpoint(run_id=client.run_id, stage="concepts")
    with pytest.raises(BudgetExceededError):
        run_concepts_stage(client, prompts, registry, sections, nlp, run_dir, checkpoint)

    assert checkpoint.completed_section_ids == []  # never got past the very first call
    saved = load_checkpoint(run_dir)
    assert saved is not None
    assert saved.stage == "concepts"  # never advanced


def test_run_canonicalize_stage_persists_taxonomy_candidates_without_merging(
    tmp_settings, fixtures_dir, tmp_path, monkeypatch
):
    """CR-005 §9 follow-up: narrower/broader decisions must never merge, but the
    kind/instance relationship they found must not be silently discarded either.
    """
    from cumap.expert_kg.canonicalize import CanonicalizationOutcome

    call_count = 0

    def patched(client_, prompt_, registry_, mention, **kwargs):
        nonlocal call_count
        call_count += 1
        concept = registry_.add_new(mention)
        return CanonicalizationOutcome(
            decision="broader",
            concept_id=concept.concept_id,
            llm_called=True,
            matched_concept_id="c_existing",
            reason="the new mention is a kind of the existing concept",
        )

    monkeypatch.setattr(pipeline_module, "canonicalize_mention", patched)

    client = LLMClient(tmp_settings, fixtures_dir=fixtures_dir)
    prompts = _prompts()
    sections = _sections()
    run_dir = tmp_path / "run"

    checkpoint = Checkpoint(run_id=client.run_id, stage="canonicalize")
    checkpoint.mentions_by_section = {
        "ch1_s1": [
            {
                "canonical_name": "TCP",
                "node_type": "Protocol",
                "role": "used",
                "definition": None,
                "evidence_quote": "q",
                "section_id": "ch1_s1",
                "run_index": 0,
            }
        ],
        "ch2_s1": [],
    }

    checkpoint, _registry = run_canonicalize_stage(
        client, prompts, sections, _fake_embed, run_dir, checkpoint
    )

    assert call_count == 1
    assert len(checkpoint.merges) == 0  # broader must never merge
    assert len(checkpoint.taxonomy_candidates) == 1
    candidate = checkpoint.taxonomy_candidates[0]
    assert candidate["decision"] == "broader"
    assert candidate["matched_concept_id"] == "c_existing"
    assert candidate["section_id"] == "ch1_s1"


def test_demo_slice_iir_face_has_no_relation_stage():
    demo_slice = load_demo_slice()
    assert demo_slice.iir_face.relations_enabled is False
    assert demo_slice.pd.relations_enabled is True

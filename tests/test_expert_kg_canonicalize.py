"""CR-005 §2 task 3 tests: canonicalisation against the growing concept registry."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from cumap.expert_kg.canonicalize import ConceptRegistry, canonicalize_mention
from cumap.expert_kg.concepts import ConceptMentionCandidate
from cumap.llm.client import LLMClient
from cumap.llm.prompts import load_prompt

REPO_ROOT = Path(__file__).parents[1]


def _fake_embed(text: str) -> np.ndarray:
    """Deterministic bag-of-words embedding over a tiny fixed vocabulary, so
    similarity is predictable without loading a real sentence-transformers model.
    """
    vocab = ["tcp", "congestion", "window", "sliding", "slow", "start", "udp", "unrelated"]
    text_lower = text.lower()
    return np.array([1.0 if w in text_lower else 0.0 for w in vocab])


def _client(tmp_settings, fixtures_dir) -> LLMClient:
    return LLMClient(tmp_settings, fixtures_dir=fixtures_dir)


def _mention(
    name, node_type="Mechanism", definition=None, section_id="s1", role="used", quote="q"
) -> ConceptMentionCandidate:
    return ConceptMentionCandidate(
        canonical_name=name,
        node_type=node_type,
        role=role,
        definition=definition,
        evidence_quote=quote,
        section_id=section_id,
    )


def test_registry_add_new_assigns_stable_concept_id():
    registry = ConceptRegistry(_fake_embed)
    concept = registry.add_new(_mention("Congestion Window"))
    assert concept.concept_id == "c_congestion_window"
    assert len(registry) == 1


def test_registry_add_new_dedupes_id_on_name_collision():
    registry = ConceptRegistry(_fake_embed)
    a = registry.add_new(_mention("Congestion Window", section_id="s1"))
    b = registry.add_new(
        _mention("Congestion Window", section_id="s2")
    )  # e.g. two genuinely different concepts sharing a name
    assert a.concept_id != b.concept_id


def test_registry_top_k_similar_ranks_by_cosine_similarity():
    registry = ConceptRegistry(_fake_embed)
    registry.add_new(_mention("congestion window"))
    registry.add_new(_mention("UDP"))
    results = registry.top_k_similar("sliding window", None, k=5)
    assert results[0][0].canonical_name == "congestion window"  # shares "window"
    assert results[0][1] > 0


def test_registry_top_k_similar_empty_when_no_concepts():
    registry = ConceptRegistry(_fake_embed)
    assert registry.top_k_similar("anything", None) == []


def test_below_threshold_creates_new_concept_without_llm_call(tmp_settings, fixtures_dir):
    registry = ConceptRegistry(_fake_embed)
    registry.add_new(
        _mention("UDP")
    )  # shares nothing with "congestion window" in the fake embedding
    prompt_template = load_prompt(REPO_ROOT / "prompts", "canonicalize", "v1")
    client = _client(tmp_settings, fixtures_dir)

    outcome = canonicalize_mention(
        client,
        prompt_template,
        registry,
        _mention("congestion window"),
        similarity_threshold=0.6,
    )
    assert outcome.llm_called is False
    assert outcome.decision == "different"
    assert len(registry) == 2
    assert client.backend_call_count == 0


def test_above_threshold_same_merges_as_alias(tmp_settings, fixtures_dir):
    registry = ConceptRegistry(_fake_embed)
    registry.add_new(_mention("congestion window", section_id="s1"))
    prompt_template = load_prompt(REPO_ROOT / "prompts", "canonicalize", "v1")
    client = _client(tmp_settings, fixtures_dir)

    outcome = canonicalize_mention(
        client,
        prompt_template,
        registry,
        _mention("cwnd", definition="congestion window", section_id="s2"),
        similarity_threshold=0.1,
        fixture_name="same",
    )
    assert outcome.llm_called is True
    assert outcome.decision == "same"
    assert len(registry) == 1  # no new concept created
    merged = registry.get(outcome.concept_id)
    assert "cwnd" in merged.aliases
    assert len(merged.mentions) == 2


def test_above_threshold_different_creates_new_concept(tmp_settings, fixtures_dir):
    registry = ConceptRegistry(_fake_embed)
    registry.add_new(_mention("congestion window", section_id="s1"))
    prompt_template = load_prompt(REPO_ROOT / "prompts", "canonicalize", "v1")
    client = _client(tmp_settings, fixtures_dir)

    outcome = canonicalize_mention(
        client,
        prompt_template,
        registry,
        _mention("slow start", section_id="s2"),
        similarity_threshold=0.1,
        fixture_name="different",
    )
    assert outcome.decision == "different"
    assert len(registry) == 2


def test_broader_creates_new_concept_and_records_matched(tmp_settings, fixtures_dir):
    registry = ConceptRegistry(_fake_embed)
    registry.add_new(_mention("slow start", section_id="s1"))
    prompt_template = load_prompt(REPO_ROOT / "prompts", "canonicalize", "v1")
    client = _client(tmp_settings, fixtures_dir)

    outcome = canonicalize_mention(
        client,
        prompt_template,
        registry,
        _mention(
            "TCP congestion control",
            definition="a family of mechanisms including slow start",
            section_id="s2",
        ),
        similarity_threshold=0.1,
        fixture_name="broader",
    )
    assert outcome.decision == "broader"
    assert outcome.matched_concept_id is not None
    assert len(registry) == 2

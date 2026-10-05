"""CR-005 §2 task 3 tests: canonicalisation against the growing concept registry."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from cumap.expert_kg.canonicalize import CanonicalOverrides, ConceptRegistry, canonicalize_mention
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


def test_exact_string_duplicate_auto_merges_without_llm_call(tmp_settings, fixtures_dir):
    registry = ConceptRegistry(_fake_embed)
    registry.add_new(_mention("congestion window", section_id="s1"))
    prompt_template = load_prompt(REPO_ROOT / "prompts", "canonicalize", "v1")
    client = _client(tmp_settings, fixtures_dir)

    outcome = canonicalize_mention(
        client, prompt_template, registry, _mention("congestion window", section_id="s2")
    )

    assert outcome.decision == "same"
    assert outcome.llm_called is False
    assert outcome.auto_merged is True
    assert client.backend_call_count == 0
    assert len(registry) == 1
    merged = registry.get(outcome.concept_id)
    assert len(merged.mentions) == 2


def test_exact_string_duplicate_case_insensitive(tmp_settings, fixtures_dir):
    registry = ConceptRegistry(_fake_embed)
    registry.add_new(_mention("Congestion Window", section_id="s1"))
    prompt_template = load_prompt(REPO_ROOT / "prompts", "canonicalize", "v1")
    client = _client(tmp_settings, fixtures_dir)

    outcome = canonicalize_mention(
        client, prompt_template, registry, _mention("congestion window", section_id="s2")
    )
    assert outcome.auto_merged is True
    assert client.backend_call_count == 0


def test_exact_string_duplicate_matches_against_an_alias(tmp_settings, fixtures_dir):
    registry = ConceptRegistry(_fake_embed)
    concept = registry.add_new(_mention("congestion window", section_id="s1"))
    concept.aliases.append("cwnd")
    prompt_template = load_prompt(REPO_ROOT / "prompts", "canonicalize", "v1")
    client = _client(tmp_settings, fixtures_dir)

    outcome = canonicalize_mention(
        client, prompt_template, registry, _mention("cwnd", section_id="s2")
    )
    assert outcome.auto_merged is True
    assert outcome.concept_id == concept.concept_id


def test_never_merge_override_blocks_exact_string_auto_merge(tmp_settings, fixtures_dir):
    registry = ConceptRegistry(_fake_embed)
    registry.add_new(_mention("congestion window", section_id="s1"))
    prompt_template = load_prompt(REPO_ROOT / "prompts", "canonicalize", "v1")
    client = _client(tmp_settings, fixtures_dir)
    # Block a similar-but-not-identical pair from ever reaching "same", even above
    # the similarity threshold and even though "cwnd" is a plausible abbreviation.
    overrides = CanonicalOverrides(never_merge={frozenset({"cwnd", "congestion window"})})
    outcome = canonicalize_mention(
        client,
        prompt_template,
        registry,
        _mention("cwnd", definition="congestion window", section_id="s2"),
        similarity_threshold=0.1,
        fixture_name="different",
        overrides=overrides,
    )
    assert outcome.decision == "different"
    assert outcome.overridden is True
    assert client.backend_call_count == 0  # never_merge filtered it out before any LLM call
    assert len(registry) == 2  # "cwnd" became its own concept, not merged


def test_force_merge_override_merges_without_llm_call(tmp_settings, fixtures_dir):
    registry = ConceptRegistry(_fake_embed)
    concept = registry.add_new(_mention("congestion window", section_id="s1"))
    prompt_template = load_prompt(REPO_ROOT / "prompts", "canonicalize", "v1")
    client = _client(tmp_settings, fixtures_dir)
    overrides = CanonicalOverrides(force_merge={frozenset({"cwnd", "congestion window"})})

    outcome = canonicalize_mention(
        client,
        prompt_template,
        registry,
        _mention("cwnd", definition="congestion window", section_id="s2"),
        similarity_threshold=0.1,
        overrides=overrides,
    )
    assert outcome.decision == "same"
    assert outcome.overridden is True
    assert outcome.concept_id == concept.concept_id
    assert client.backend_call_count == 0
    assert len(registry) == 1


def test_canonical_overrides_load_from_yaml(tmp_path):
    path = tmp_path / "overrides.yaml"
    path.write_text("never_merge:\n  - [HDLC, SDLC]\nforce_merge:\n  - [cwnd, congestion window]\n")
    overrides = CanonicalOverrides.load(path)
    assert overrides.is_never_merge("hdlc", "sdlc") is True
    assert overrides.is_never_merge("SDLC", "HDLC") is True  # order-independent
    assert overrides.is_force_merge("CWND", "Congestion Window") is True
    assert overrides.is_never_merge("cwnd", "congestion window") is False


def test_canonical_overrides_load_missing_file_returns_empty(tmp_path):
    overrides = CanonicalOverrides.load(tmp_path / "does-not-exist.yaml")
    assert overrides.is_never_merge("a", "b") is False
    assert overrides.is_force_merge("a", "b") is False


def _registry_with(name, node_type):
    registry = ConceptRegistry(_fake_embed)
    concept = registry.add_new(_mention(name, node_type=node_type))
    return registry, concept


def _canon(tmp_settings, fixtures_dir, registry, mention, **kw):
    prompt = load_prompt(REPO_ROOT / "prompts", "canonicalize", "v2")
    return canonicalize_mention(
        _client(tmp_settings, fixtures_dir), prompt, registry, mention, fixture_name="same", **kw
    )


def test_type_mismatch_is_never_same_and_is_logged_as_a_related_candidate(
    tmp_settings, fixtures_dir
):
    """CR-007 §4.3: even if the model would say 'same', a different node_type blocks the merge."""
    registry, existing = _registry_with("congestion window", "Parameter")
    m = _mention("cwnd", node_type="Mechanism", definition="congestion window size")
    out = _canon(tmp_settings, fixtures_dir, registry, m, type_aware=True)
    assert out.decision == "different" and out.llm_called is False
    assert out.related_ids == [existing.concept_id] and out.concept_id != existing.concept_id
    assert len(registry) == 2
    registry2, existing2 = _registry_with("congestion window", "Parameter")
    merged = _canon(tmp_settings, fixtures_dir, registry2, m)  # type_aware off (old behaviour)
    assert merged.decision == "same" and merged.concept_id == existing2.concept_id


def test_low_similarity_same_verdict_goes_to_review_instead_of_merging(tmp_settings, fixtures_dir):
    registry, existing = _registry_with("congestion window", "Mechanism")
    m = _mention("sliding window", node_type="Mechanism")  # cosine 0.5 with the fake embedding
    out = _canon(
        tmp_settings, fixtures_dir, registry, m, similarity_threshold=0.4, review_below=0.70
    )
    assert out.decision == "review" and out.review and out.llm_called
    assert out.matched_concept_id == existing.concept_id and abs(out.similarity - 0.5) < 1e-6
    assert (
        out.concept_id != existing.concept_id and len(registry) == 2
    )  # a new concept, nothing merged or lost
    assert "sliding window" not in registry.get(existing.concept_id).aliases
    old = _canon(
        tmp_settings,
        fixtures_dir,
        _registry_with("congestion window", "Mechanism")[0],
        m,
        similarity_threshold=0.4,
    )
    assert old.decision == "same"  # band off: the previous behaviour


def test_high_similarity_same_verdict_still_merges_under_the_band(tmp_settings, fixtures_dir):
    registry, existing = _registry_with("congestion window", "Mechanism")
    m = _mention("cwnd", node_type="Mechanism", definition="congestion window")
    out = _canon(tmp_settings, fixtures_dir, registry, m, type_aware=True, review_below=0.70)
    assert (
        out.decision == "same" and out.concept_id == existing.concept_id and out.similarity >= 0.7
    )


def test_review_sheet_is_blind(tmp_path):
    from cumap.expert_kg.canonicalize import write_merge_review_sheet

    row = {
        "section_id": "2.1",
        "alias": "sliding window",
        "mention_type": "Mechanism",
        "quote": "q",
        "candidate_name": "congestion window",
        "candidate_type": "Mechanism",
        "candidate_definition": "d",
        "similarity": 0.5,
        "llm_reason": "secret model reason",
    }
    path = tmp_path / "review.csv"
    write_merge_review_sheet([row], path)
    text = path.read_text()
    assert "sliding window" in text and "congestion window" in text
    assert (
        "similarity" not in text.lower() and "secret model reason" not in text and "0.5" not in text
    )


def test_add_new_keeps_the_mentions_source():
    """CR-009 STOP 1: add_new used to drop `source`, relabelling a propagation-created node's first mention as llm."""
    reg = ConceptRegistry(lambda t: np.zeros(3))
    m = _mention("bandwidth")
    m.source = "propagation"
    assert reg.add_new(m).mentions[0].source == "propagation"

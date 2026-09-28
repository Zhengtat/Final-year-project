"""CR-001 §7.3 acceptance tests: relation-agreement sampler."""

from __future__ import annotations

from pathlib import Path

import pytest

from cumap.gold.sample_relation_items import (
    find_candidate_items,
    find_concept_mentions,
    split_paragraphs,
    split_sentences,
    stratified_sample,
    write_relation_agreement_files,
)
from cumap.schemas.relations import RelationRegistry

V1_PATH = Path(__file__).parents[1] / "configs" / "relations_v1.yaml"


@pytest.fixture(scope="module")
def registry() -> RelationRegistry:
    return RelationRegistry.from_yaml(V1_PATH)


def test_split_sentences():
    text = "TCP performs slow start. Slow start is part of congestion control! Is that clear?"
    assert split_sentences(text) == [
        "TCP performs slow start.",
        "Slow start is part of congestion control!",
        "Is that clear?",
    ]


def test_split_paragraphs():
    text = "First paragraph, one sentence.\n\nSecond paragraph.\nStill second paragraph.\n\nThird."
    assert split_paragraphs(text) == [
        "First paragraph, one sentence.",
        "Second paragraph.\nStill second paragraph.",
        "Third.",
    ]


def test_find_concept_mentions_matches_canonical_name_and_alias():
    concepts = [
        {"concept_id": "c_tcp", "canonical_name": "TCP", "aliases": ["Transmission Control Protocol"]},
        {"concept_id": "c_ss", "canonical_name": "slow start", "aliases": []},
    ]
    found = find_concept_mentions("Transmission Control Protocol performs slow start.", concepts)
    assert set(found) == {"c_tcp", "c_ss"}


def test_find_concept_mentions_strips_trailing_parenthetical_for_matching():
    concepts = [{"concept_id": "c_ca", "canonical_name": "congestion avoidance (additive increase)", "aliases": []}]
    found = find_concept_mentions("The sender then enters congestion avoidance.", concepts)
    assert found == ["c_ca"]


def test_find_candidate_items_needs_at_least_two_concepts_in_the_same_paragraph(registry):
    concepts = [
        {"concept_id": "c_tcp", "canonical_name": "TCP", "aliases": []},
        {"concept_id": "c_ss", "canonical_name": "slow start", "aliases": []},
        {"concept_id": "c_udp", "canonical_name": "UDP", "aliases": []},
    ]
    sections = {"6.3": "TCP performs slow start.\n\nUDP is unrelated, in a different paragraph."}
    items = find_candidate_items("q_1", sections, concepts, [], registry)
    assert len(items) == 1
    assert {items[0].concept_x, items[0].concept_y} == {"TCP", "slow start"}


def test_find_candidate_items_predicts_family_from_draft_edges(registry):
    concepts = [
        {"concept_id": "c_tcp", "canonical_name": "TCP", "aliases": []},
        {"concept_id": "c_ss", "canonical_name": "slow start", "aliases": []},
    ]
    sections = {"6.3": "TCP performs slow start."}
    draft_edges = [{"source_id": "c_tcp", "target_id": "c_ss", "relation": "performs"}]
    items = find_candidate_items("q_1", sections, concepts, draft_edges, registry)
    assert items[0].predicted_family == "mechanism_process"


def test_find_candidate_items_unknown_family_when_no_draft_edge(registry):
    concepts = [
        {"concept_id": "c_tcp", "canonical_name": "TCP", "aliases": []},
        {"concept_id": "c_ss", "canonical_name": "slow start", "aliases": []},
    ]
    sections = {"6.3": "TCP performs slow start."}
    items = find_candidate_items("q_1", sections, concepts, [], registry)
    assert items[0].predicted_family is None


def _make_items(registry, per_family=20):
    from cumap.gold.sample_relation_items import RelationItem

    items = []
    for family in registry.families:
        if family == "pedagogical":
            continue
        for i in range(per_family):
            items.append(
                RelationItem(
                    item_id=f"RI-{family}-{i}",
                    question_id="q_1",
                    section_id="6.3",
                    sentence=f"sentence {family} {i}",
                    concept_x="A",
                    concept_y="B",
                    predicted_family=family,
                )
            )
    return items


def test_stratified_sample_hits_min_per_family(registry):
    items = _make_items(registry, per_family=20)
    selected = stratified_sample(items, registry, n=100, seed=42, min_per_family=8)

    counts = {}
    for item in selected:
        counts[item.predicted_family] = counts.get(item.predicted_family, 0) + 1

    semantic_families = [f for f in registry.families if f != "pedagogical"]
    for family in semantic_families:
        assert counts.get(family, 0) >= 8, family


def test_stratified_sample_is_deterministic_given_seed(registry):
    items = _make_items(registry, per_family=20)
    first = stratified_sample(items, registry, n=50, seed=7)
    second = stratified_sample(items, registry, n=50, seed=7)
    assert [i.item_id for i in first] == [i.item_id for i in second]


def test_stratified_sample_respects_n(registry):
    items = _make_items(registry, per_family=20)
    selected = stratified_sample(items, registry, n=30, seed=1)
    assert len(selected) == 30


def test_write_relation_agreement_files_blank_sheets_have_no_prefilled_answers(registry, tmp_path):
    items = _make_items(registry, per_family=1)[:10]
    paths = write_relation_agreement_files(items, tmp_path, registry)

    import pandas as pd

    for key in ("annotator_A", "annotator_B"):
        sheet = pd.read_csv(paths[key])
        for col in ["relation", "direction", "part_type", "dimension", "other_phrase"]:
            assert col in sheet.columns
            assert sheet[col].isna().all() or (sheet[col] == "").all()
        assert "predicted_family" not in sheet.columns  # never shown to annotators

    items_df = pd.read_csv(paths["items"])
    assert list(items_df.columns) == ["item_id", "section_id", "sentence", "concept_x", "concept_y"]

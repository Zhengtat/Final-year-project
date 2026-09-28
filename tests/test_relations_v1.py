"""CR-001 §3 acceptance tests: relation registry v1 (families, templates, near-misses,
qualifiers, choice_set, can_chain, required_qualifiers) — see docs/change-requests/CR-001-relations-v1.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cumap.schemas.relations import EdgeRef, RelationRegistry

V1_PATH = Path(__file__).parents[1] / "configs" / "relations_v1.yaml"
V0_PATH = Path(__file__).parents[1] / "configs" / "relations_v0.yaml"


@pytest.fixture(scope="module")
def v1() -> RelationRegistry:
    return RelationRegistry.from_yaml(V1_PATH)


@pytest.fixture(scope="module")
def v0() -> RelationRegistry:
    return RelationRegistry.from_yaml(V0_PATH)


def test_v0_still_loads(v0: RelationRegistry):
    assert v0.version == 0
    assert "is_a" in v0
    assert v0.get("is_a").family is None  # v0 has no family data


def test_v1_loads_16_relations(v1: RelationRegistry):
    assert v1.version == 1
    assert v1.supersedes == 0
    assert len(v1.all_relations()) == 16


def test_every_v1_relation_has_family_template_example_and_near_miss(v1: RelationRegistry):
    for rel in v1.all_relations():
        assert rel.family is not None, rel.name
        assert rel.family in v1.families, rel.name
        assert rel.template is not None, rel.name
        assert len(rel.examples) >= 1, rel.name
        assert len(rel.near_misses) >= 1, rel.name


def test_conflicts_table_is_symmetric(v1: RelationRegistry):
    for rel in v1.all_relations():
        for other in rel.conflicts_with:
            assert v1.conflicts(rel.name, other)
            assert v1.conflicts(other, rel.name)


def test_compatible_table_is_symmetric(v1: RelationRegistry):
    for rel in v1.all_relations():
        for other, level in rel.compatible_with.items():
            assert v1.compatible(rel.name, other) == level
            assert v1.compatible(other, rel.name) == level


def test_part_of_requires_part_type_polarity_modality(v1: RelationRegistry):
    assert v1.required_qualifiers("part_of") == {"part_type", "polarity", "modality"}


def test_non_part_of_relation_does_not_require_part_type(v1: RelationRegistry):
    assert "part_type" not in v1.required_qualifiers("causes")
    assert v1.required_qualifiers("causes") == {"polarity", "modality"}


def test_can_chain_part_of_same_part_type(v1: RelationRegistry):
    a = EdgeRef("c_x", "part_of", "c_y")
    b = EdgeRef("c_y", "part_of", "c_z")
    assert v1.can_chain(a, b, part_type_a="component", part_type_b="component") is True


def test_can_chain_part_of_different_part_type(v1: RelationRegistry):
    a = EdgeRef("c_x", "part_of", "c_y")
    b = EdgeRef("c_y", "part_of", "c_z")
    assert v1.can_chain(a, b, part_type_a="component", part_type_b="member") is False


def test_can_chain_requires_matching_endpoints(v1: RelationRegistry):
    a = EdgeRef("c_x", "part_of", "c_y")
    b = EdgeRef("c_other", "part_of", "c_z")  # b.source != a.target
    assert v1.can_chain(a, b, part_type_a="component", part_type_b="component") is False


def test_can_chain_unconditionally_transitive_relation(v1: RelationRegistry):
    a = EdgeRef("c_x", "causes", "c_y")
    b = EdgeRef("c_y", "causes", "c_z")
    assert v1.can_chain(a, b) is True


def test_choice_set_directional_relation_includes_reversed_none_and_other(v1: RelationRegistry):
    choices = v1.choice_set("slow start", "congestion avoidance", families=["mechanism_process"])
    relation_names = {(c.relation, c.reversed) for c in choices if c.kind == "relation"}
    assert ("precedes", False) in relation_names
    assert ("precedes", True) in relation_names  # precedes is directional
    kinds = {c.kind for c in choices}
    assert "no_relation" in kinds
    assert "other" in kinds


def test_choice_set_respects_family_filter(v1: RelationRegistry):
    choices = v1.choice_set("X", "Y", families=["comparison"])
    relation_names = {c.relation for c in choices if c.kind == "relation"}
    assert relation_names <= {"contrasts_with", "equivalent_to"}


def test_has_purpose_domain_rejects_event_source(v1: RelationRegistry):
    edge = EdgeRef("e_timeout", "has_purpose", "c_reliability")  # Event is not in has_purpose's domain_types
    errors = v1.check_types(edge, {"e_timeout": "Event", "c_reliability": "Property"})
    assert errors


def test_causes_has_purpose_partially_compatible(v1: RelationRegistry):
    assert v1.compatible("causes", "has_purpose") == "partial"


def test_uses_performs_partially_compatible(v1: RelationRegistry):
    assert v1.compatible("uses", "performs") == "partial"


def test_family_of_and_same_family(v1: RelationRegistry):
    assert v1.family_of("causes") == "cause_effect"
    assert v1.same_family("causes", "prevents") is True
    assert v1.same_family("causes", "is_a") is False


def test_template_for_fills_placeholders(v1: RelationRegistry):
    assert v1.template_for("causes", "packet loss", "throughput drop") == "packet loss causes throughput drop"


def test_template_for_reverse_requires_directional(v1: RelationRegistry):
    with pytest.raises(ValueError, match="directional"):
        v1.template_for("contrasts_with", "A", "B", reverse=True)


def test_v1_only_functions_raise_clearly_on_v0(v0: RelationRegistry):
    with pytest.raises(ValueError, match="v0 registry"):
        v0.family_of("is_a")

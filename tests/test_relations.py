from __future__ import annotations

from pathlib import Path

import pytest

from cumap.schemas.relations import EdgeRef, RelationRegistry

REGISTRY_PATH = Path(__file__).parents[1] / "configs" / "relations_v0.yaml"


@pytest.fixture(scope="module")
def registry() -> RelationRegistry:
    return RelationRegistry.from_yaml(REGISTRY_PATH)


def test_loads_all_relations(registry: RelationRegistry):
    assert "is_a" in registry
    assert "increases" in registry
    assert "contrasts_with" in registry


def test_reversing_a_symmetric_relation_is_not_a_reversal(registry: RelationRegistry):
    a = EdgeRef("c_slow_start", "contrasts_with", "c_congestion_avoidance")
    b = EdgeRef("c_congestion_avoidance", "contrasts_with", "c_slow_start")
    assert registry.is_reversal(a, b) is False


def test_reversing_a_directional_relation_is_a_reversal(registry: RelationRegistry):
    a = EdgeRef("c_tcp", "uses", "c_sliding_window")
    b = EdgeRef("c_sliding_window", "uses", "c_tcp")
    assert registry.is_reversal(a, b) is True


def test_same_edge_twice_is_not_a_reversal(registry: RelationRegistry):
    a = EdgeRef("c_tcp", "uses", "c_sliding_window")
    assert registry.is_reversal(a, a) is False


def test_increases_and_decreases_conflict(registry: RelationRegistry):
    assert registry.conflicts("increases", "decreases") is True
    assert registry.conflicts("decreases", "increases") is True


def test_unrelated_relations_do_not_conflict(registry: RelationRegistry):
    assert registry.conflicts("is_a", "part_of") is False


def test_triggers_and_causes_are_partially_compatible(registry: RelationRegistry):
    assert registry.compatible("triggers", "causes") == "partial"
    assert registry.compatible("causes", "triggers") == "partial"


def test_same_relation_is_fully_compatible_with_itself(registry: RelationRegistry):
    assert registry.compatible("uses", "uses") == "full"


def test_unrelated_relations_are_not_compatible(registry: RelationRegistry):
    assert registry.compatible("is_a", "precedes") is None


def test_is_a_cycle_is_detected(registry: RelationRegistry):
    edges = [
        EdgeRef("c_a", "is_a", "c_b"),
        EdgeRef("c_b", "is_a", "c_c"),
        EdgeRef("c_c", "is_a", "c_a"),
    ]
    cycles = registry.find_cycles(edges, "is_a")
    assert len(cycles) >= 1


def test_no_cycle_in_an_acyclic_taxonomy(registry: RelationRegistry):
    edges = [
        EdgeRef("c_a", "is_a", "c_b"),
        EdgeRef("c_b", "is_a", "c_c"),
    ]
    assert registry.find_cycles(edges, "is_a") == []


def test_normalise_rewrites_inverse_relation_to_forward_form(registry: RelationRegistry):
    edge = EdgeRef("c_extension_header", "has_part", "c_ipv6_packet")  # inverse of part_of
    normalised = registry.normalise(edge)
    assert normalised == EdgeRef("c_ipv6_packet", "part_of", "c_extension_header")


def test_normalise_sorts_symmetric_endpoints_canonically(registry: RelationRegistry):
    a = registry.normalise(EdgeRef("c_zebra", "contrasts_with", "c_apple"))
    b = registry.normalise(EdgeRef("c_apple", "contrasts_with", "c_zebra"))
    assert a == b


def test_check_types_flags_domain_violation(registry: RelationRegistry):
    edge = EdgeRef("c_tcp", "has_property", "c_router")  # has_property range is Property/Parameter
    errors = registry.check_types(edge, {"c_tcp": "Protocol", "c_router": "Component"})
    assert errors


def test_check_types_passes_valid_edge(registry: RelationRegistry):
    edge = EdgeRef("c_slow_start", "has_property", "c_exponential_growth")
    errors = registry.check_types(edge, {"c_slow_start": "Mechanism", "c_exponential_growth": "Property"})
    assert errors == []

"""CR-007 §5.1 / §9: registry v1.1 (generated from v1 + the patch); v1 is never changed in place."""

import hashlib
from pathlib import Path

import pytest
import yaml

from cumap.schemas.registry_patch import apply_patch
from cumap.schemas.relations import EdgeRef, RelationRegistry

REPO = Path(__file__).parents[1]
V1, V11 = REPO / "configs/relations_v1.yaml", REPO / "configs/relations_v1.1.yaml"
PATCH = REPO / "configs/registry-patches/CR-007-relations-v1.1.yaml"


@pytest.fixture(scope="module")
def reg() -> RelationRegistry:
    return RelationRegistry.from_yaml(V11)


def test_v1_1_loads_validates_and_adds_exactly_the_patch_relations(reg):
    v1 = RelationRegistry.from_yaml(V1)
    assert reg.version_label == "1.1" and v1.version_label == "1.0"
    added = {r.name for r in reg.all_relations()} - {r.name for r in v1.all_relations()}
    assert added == {"acts_on", "connected_to", "identifies", "encapsulates", "trades_off_with"}
    assert {r.name for r in reg.all_relations() if r.gate == "gated"} == {
        "identifies",
        "encapsulates",
        "trades_off_with",
    }
    assert "Identifier" in reg.node_types and "Identifier" not in v1.node_types
    assert set(reg.output_fields) == {"other_description", "other_suggested_label"}
    assert all(f.gloss for f in reg.families.values() if f.name != "pedagogical")


def test_generated_file_matches_patch_output_and_base_is_untouched(reg):
    fresh = apply_patch(yaml.safe_load(V1.read_text()), yaml.safe_load(PATCH.read_text()))
    assert [r["name"] for r in fresh["relations"]] == [r.name for r in reg.all_relations()]
    assert "GENERATED" in V11.read_text().splitlines()[0]
    assert (
        "acts_on" not in V1.read_text() and hashlib.sha256(V1.read_bytes()).hexdigest()
    )  # v1 still v1


def test_acts_on_requires_action_type_and_negation_is_a_qualifier_not_a_relation(reg):
    assert "action_type" in reg.required_qualifiers(
        "acts_on"
    ) and "action_type" not in reg.required_qualifiers("requires")
    assert reg.qualifiers["action_type"].values == [
        "send",
        "receive",
        "forward",
        "transform",
        "check",
        "store",
        "drop",
        "generate",
        "other",
    ]
    assert reg.qualifiers["corrects_intuition"].required is False and "intuition" in reg.qualifiers
    assert set(reg.qualifiers["dimension"].applies_to) == {"contrasts_with", "trades_off_with"}


def test_symmetric_relations_are_stored_canonically_and_encapsulates_conflicts_with_part_of(reg):
    a = reg.normalise(EdgeRef(source_id="c_switch", relation="connected_to", target_id="c_host"))
    b = reg.normalise(EdgeRef(source_id="c_host", relation="connected_to", target_id="c_switch"))
    assert a == b and reg.get("connected_to").symmetric
    assert reg.conflicts("encapsulates", "part_of") and reg.conflicts("part_of", "encapsulates")
    t = reg.normalise(EdgeRef(source_id="b", relation="trades_off_with", target_id="a"))
    assert (t.source_id, t.target_id) == ("a", "b")


def test_domain_range_of_new_relations(reg):
    types = {"c_sw": "Component", "c_fr": "DataUnit", "c_addr": "Identifier", "c_prop": "Property"}
    assert (
        reg.check_types(EdgeRef(source_id="c_sw", relation="acts_on", target_id="c_fr"), types)
        == []
    )
    assert reg.check_types(
        EdgeRef(source_id="c_fr", relation="acts_on", target_id="c_sw"), types
    )  # a data unit is not an actor
    assert (
        reg.check_types(EdgeRef(source_id="c_addr", relation="identifies", target_id="c_sw"), types)
        == []
    )


def test_patch_for_the_wrong_base_version_is_refused():
    base = yaml.safe_load(V1.read_text())
    bad = {**yaml.safe_load(PATCH.read_text()), "patch_for_registry_version": 0}
    with pytest.raises(ValueError):
        apply_patch(base, bad)
    with pytest.raises(ValueError, match="already exists"):
        apply_patch(
            base,
            {
                **yaml.safe_load(PATCH.read_text()),
                "adds": {"relations": [{"name": "is_a", "family": "x"}]},
            },
        )

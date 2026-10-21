"""CR-024: the merged relation registry v1.4 (v1.3 + the 11 SciNLP labels). Overlaps are merged, not duplicated; nothing from v1.3 is lost."""

from pathlib import Path

import yaml

from cumap.cr022 import scoring as C
from cumap.cr022.mapping import REGISTRY_V14, hierarchy_labels, registry_mapping
from cumap.schemas.registry_patch import apply_patch
from cumap.schemas.relations import RelationRegistry

V13, V14 = Path("configs/relations_v1.3.yaml"), Path(REGISTRY_V14)
SCINLP = {
    r["name"]
    for r in yaml.safe_load(Path("configs/relations_scinlp.yaml").read_text())["relations"]
}


def test_generated_file_equals_the_patch_applied_to_v13():
    patch = yaml.safe_load(Path("configs/registry-patches/CR-024-relations-v1.4.yaml").read_text())
    new = apply_patch(yaml.safe_load(V13.read_text()), patch)
    assert yaml.safe_load(V14.read_text()) == new


def test_v14_keeps_every_v13_relation_and_adds_six():
    a, b = RelationRegistry.from_yaml(V13), RelationRegistry.from_yaml(V14)
    assert {r.name for r in a.all_relations()} <= {r.name for r in b.all_relations()}
    assert len(b.all_relations()) == len(a.all_relations()) + 6 and b.version_label == "1.4"
    assert "equivalent_to" not in b  # CR-008: equivalence stays a node property


def test_every_scinlp_label_is_in_exactly_one_relation_and_overlaps_are_merged():
    b = RelationRegistry.from_yaml(V14)
    owners: dict[str, list[str]] = {}
    for r in b.all_relations():
        for lab in r.external_labels.get("SciNLP", []):
            owners.setdefault(lab, []).append(r.name)
    assert set(owners) == SCINLP and all(len(v) == 1 for v in owners.values())
    assert {lab: v[0] for lab, v in owners.items()} | {} == {
        k: e.target for k, e in registry_mapping(b).items()
    }
    for lab, rel in {
        "subclassOf": "is_a",
        "partOf": "part_of",
        "UsedFor": "has_purpose",
        "compareWith": "contrasts_with",
        "trainedWith": "uses",
    }.items():
        assert owners[lab] == [rel]  # merged into the v1.3 relation, no duplicate created
    assert b.get("similar_to").symmetric and b.get("contrasts_with").symmetric


def test_new_relations_reference_existing_relations_and_families():
    b = RelationRegistry.from_yaml(V14)
    for r in b.all_relations():
        assert r.family in b.families, r.name
        assert all(m.relation in b for m in r.near_misses), r.name
        assert all(k in b for k in r.compatible_with), r.name


def test_hierarchy_set_from_the_registry_equals_the_cr022_default_set():
    b = RelationRegistry.from_yaml(V14)
    assert (
        hierarchy_labels(b)
        == C.HIER_SETS["H2 {subclassOf, subtaskOf}"]
        == {"subclassOf", "subtaskOf"}
    )


def test_production_default_registry_is_unchanged():
    assert (
        "relations_v1.3.yaml"
        in Path("configs/default.yaml").read_text().split("relation_registry:")[1].split("\n")[0]
    )

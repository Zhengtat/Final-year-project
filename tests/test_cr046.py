"""CR-046: registry v1.4.1 = v1.4 + the owner-approved CR-040 wording, nothing else (no network, no key)."""

import hashlib
from pathlib import Path

import yaml

from cumap.schemas import registry_patch as RP
from cumap.schemas.relations import RelationRegistry

REPO = Path(__file__).resolve().parents[1]
V14 = REPO / "configs/relations_v1.4.yaml"
V141 = REPO / "configs/relations_v1.4.1.yaml"
PATCH = REPO / "configs/registry-patches/CR-046-relations-v1.4.1.yaml"
WORDING = ("definition", "template", "examples", "near_misses")


def _body(p: Path) -> dict:
    return yaml.safe_load(p.read_text())


def test_v14_is_unchanged_and_v141_loads():
    assert hashlib.sha256(V14.read_bytes()).hexdigest().startswith("bd835ec399b74eb4")
    reg = RelationRegistry.from_yaml(V141)
    assert reg.patch == 1 and len(reg._by_name) == len(RelationRegistry.from_yaml(V14)._by_name)
    raw = _body(V141)
    assert (raw["minor"], raw["patch"]) == (4, 1)


def test_v141_is_the_generated_file():
    new = RP.apply_patch(_body(V14), _body(PATCH))
    assert new == _body(V141)


def test_only_the_wording_of_the_six_relations_changes():
    prop = _body(REPO / "docs/cr040/v14_wording_proposals.yaml")["relations"]
    old = {r["name"]: r for r in _body(V14)["relations"]}
    new = {r["name"]: r for r in _body(V141)["relations"]}
    assert old.keys() == new.keys()
    for name in new:
        if name in prop:
            assert {k: new[name][k] for k in WORDING} == {k: prop[name][k] for k in WORDING}
            assert {k: v for k, v in new[name].items() if k not in WORDING} == {
                k: v for k, v in old[name].items() if k not in WORDING
            }
        else:
            assert new[name] == old[name]
    a, b = _body(V14), _body(V141)
    for k in ("families", "node_types", "qualifiers"):
        assert a[k] == b[k]

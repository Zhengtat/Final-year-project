"""CR-047: registry v1.5 for new P&D runs, SciNLP registry v1.0.1 / profile v2, amendments on (no network, no key)."""

import hashlib
from pathlib import Path

import yaml

from cumap.concepts_v4.cr009_run import production_registry_path
from cumap.config import get_settings
from cumap.expert_kg import relations_v6 as R6
from cumap.schemas.relations import RelationRegistry

REPO = Path(__file__).resolve().parents[1]


def test_new_pd_runs_load_v15_and_default_yaml_keeps_v13(monkeypatch):
    monkeypatch.delenv("CUMAP_RELATION_REGISTRY", raising=False)
    assert production_registry_path(get_settings()).name == "relations_v1.5.yaml"
    assert yaml.safe_load((REPO / "configs/default.yaml").read_text())[
        "relation_registry"
    ].endswith("v1.3.yaml")
    R6.check_registry_for_v6(RelationRegistry.from_yaml(REPO / "configs/relations_v1.5.yaml"))


def test_benchmark_registry_env_wins(monkeypatch):
    monkeypatch.setenv("CUMAP_RELATION_REGISTRY", "configs/relations_scinlp_v1.0.1.yaml")
    get_settings.cache_clear()
    try:
        assert production_registry_path(get_settings()).name == "relations_scinlp_v1.0.1.yaml"
    finally:
        get_settings.cache_clear()


def test_scinlp_v101_is_the_frozen_registry_minus_never_and_frozen_files_unchanged():
    frozen = yaml.safe_load((REPO / "configs/relations_scinlp.yaml").read_text())
    new = yaml.safe_load((REPO / "configs/relations_scinlp_v1.0.1.yaml").read_text())
    assert "never" not in new["qualifiers"]["modality"]["values"]
    frozen["qualifiers"]["modality"]["values"].remove("never")
    assert {k: v for k, v in new.items() if k != "patch"} == {
        k: v for k, v in frozen.items() if k != "patch"
    }
    R6.check_registry_for_v6(
        RelationRegistry.from_yaml(REPO / "configs/relations_scinlp_v1.0.1.yaml")
    )
    import json

    pins = json.loads((REPO / "reports/cr012/frozen_hashes.json").read_text())[
        "scinlp_schema_freeze"
    ]["files"]
    for k in ("scinlp_profile", "scinlp_relation_registry"):
        assert (
            hashlib.sha256((REPO / pins[k]["path"]).read_bytes()).hexdigest() == pins[k]["sha256"]
        )
    p1 = yaml.safe_load((REPO / "configs/cr012_scinlp_schema.yaml").read_text())
    p2 = yaml.safe_load((REPO / "configs/scinlp_profile_v2.yaml").read_text())
    assert p2["relation_registry"] == "configs/relations_scinlp_v1.0.1.yaml"
    assert {k: v for k, v in p1.items() if k not in ("relation_registry", "status")} == {
        k: v for k, v in p2.items() if k not in ("relation_registry", "status")
    }


def test_wrapper_sets_profile_v2():
    from cumap.cr012 import scinlp_run as SR
    from cumap.cr047.scinlp_run import PROFILE_V2, use_profile_v2

    old = SR.PROFILE
    try:
        use_profile_v2()
        assert SR.PROFILE == PROFILE_V2
    finally:
        SR.PROFILE = old

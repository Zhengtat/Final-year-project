"""CR-064: role-explicit SciNLP registry v1.0.2, relation_choice v9 and profile v12 (no model call)."""

from pathlib import Path

import pytest
import yaml

from cumap.cr064 import arm_relations as AR
from cumap.expert_kg.relations_v3 import filled_options
from cumap.expert_kg.relations_v8 import choice_prompt_version
from cumap.llm.prompts import load_prompt
from cumap.schemas.registry_patch import apply_patch
from cumap.schemas.relations import RelationRegistry

REPO = Path(__file__).parents[1]
V101 = REPO / "configs/relations_scinlp_v1.0.1.yaml"
V102 = REPO / "configs/relations_scinlp_v1.0.2.yaml"
PATCH = REPO / "configs/registry-patches/CR-064-relations-scinlp-v1.0.2.yaml"


def test_v102_is_the_generated_patch_and_changes_wording_only():
    base, new = yaml.safe_load(V101.read_text()), yaml.safe_load(V102.read_text())
    assert new == apply_patch(base, yaml.safe_load(PATCH.read_text()))
    assert (new["version"], new["minor"], new["patch"]) == (1, 0, 2)
    assert [r["name"] for r in new["relations"]] == [r["name"] for r in base["relations"]]
    for a, b in zip(base["relations"], new["relations"], strict=True):
        assert {k for k in a if a[k] != b[k]} <= {"definition", "near_misses"}
        assert b["definition"] != a["definition"] and b["near_misses"]


def test_near_misses_name_registry_relations_and_use_role_patterns_only():
    reg = RelationRegistry.from_yaml(V102)
    names = {r.name for r in reg.all_relations()}
    for r in reg.all_relations():
        for nm in r.near_misses:
            assert nm.relation in names and nm.relation != r.name
            assert nm.example.startswith("[a ")  # a role pattern, never a sentence from a paper
        assert " X " not in f" {r.definition} " and " Y " not in f" {r.definition} "


def test_options_block_shows_the_role_definitions_and_contrasts():
    block = filled_options(RelationRegistry.from_yaml(V102), "scinlp", "A", "B")
    assert "not evaluatedOn:" in block and "(not a task)" in block


def test_choice_prompt_defaults_to_v8_and_profile_v12_selects_v9(monkeypatch):
    monkeypatch.delenv("CUMAP_BENCHMARK_PROFILE", raising=False)
    assert choice_prompt_version() == "v8"
    monkeypatch.setenv("CUMAP_BENCHMARK_PROFILE", str(REPO / "configs/scinlp_profile_v12.yaml"))
    assert choice_prompt_version() == "v9"
    with pytest.raises(ValueError):
        choice_prompt_version("v7")


def test_prompt_v9_is_v8_plus_the_roles_rule():
    v9 = load_prompt(REPO / "prompts", "relation_choice", "v9")
    assert v9.version == "v9"
    body8, body9 = (
        (REPO / f"prompts/relation_choice/{v}.md").read_text().split("---\n", 2)[2]
        for v in ("v8", "v9")
    )
    assert (
        body9.replace(
            body9[body9.index("- Roles come first.") : body9.index("- endpoint_fit:")], ""
        )
        == body8
    )
    assert "SciNLP" not in body9 and "dataset" not in body9  # no domain wording in the prompt


def test_profile_v12_is_v7r_with_only_the_registry_and_choice_prompt():
    p7 = yaml.safe_load((REPO / "configs/scinlp_profile_v7r.yaml").read_text())
    p12 = yaml.safe_load((REPO / "configs/scinlp_profile_v12.yaml").read_text())
    assert {k for k in set(p7) | set(p12) if p7.get(k) != p12.get(k)} == {
        "status",
        "relation_registry",
        "choice_prompt",
    }
    assert (
        p12["relation_registry"] == "configs/relations_scinlp_v1.0.2.yaml"
        and p12["endpoint_check"] == "choice"
    )


def test_the_arm_refuses_while_the_registry_is_a_draft(monkeypatch, tmp_path):
    draft = tmp_path / "p.yaml"
    draft.write_text("header_note: 'x DRAFT'\n")
    monkeypatch.setattr(AR, "PATCH", draft)
    assert not AR.approved()
    with pytest.raises(SystemExit):
        AR.worker("train", "any")


def test_profile_v13_is_v12_with_choice_prompt_v10(monkeypatch):
    p12 = yaml.safe_load((REPO / "configs/scinlp_profile_v12.yaml").read_text())
    p13 = yaml.safe_load((REPO / "configs/scinlp_profile_v13.yaml").read_text())
    assert {k for k in set(p12) | set(p13) if p12.get(k) != p13.get(k)} == {
        "status",
        "choice_prompt",
    }
    monkeypatch.setenv("CUMAP_BENCHMARK_PROFILE", str(REPO / "configs/scinlp_profile_v13.yaml"))
    assert choice_prompt_version() == "v10"
    body9, body10 = (
        (REPO / f"prompts/relation_choice/{v}.md").read_text().split("---\n", 2)[2]
        for v in ("v9", "v10")
    )
    i, j = body10.index("- Specific concepts only."), body10.index("- endpoint_fit:")
    assert body10[:i] + body10[j:] == body9

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
    monkeypatch.setattr(AR, "PATCHES", {"r2": "p.yaml", "r4": "p.yaml"})
    assert not AR.approved()
    with pytest.raises(SystemExit):
        AR.worker("train", "any")
    with pytest.raises(SystemExit):
        AR.worker("train", "any", arm="r4")


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


V103 = REPO / "configs/relations_scinlp_v1.0.3.yaml"
PATCH103 = REPO / "configs/registry-patches/CR-064-relations-scinlp-v1.0.3.yaml"


def test_v103_is_the_generated_patch_and_changes_only_the_partof_wording(tmp_path):
    from cumap.schemas.registry_patch import apply_patch

    base = yaml.safe_load(V102.read_text())
    new = yaml.safe_load(V103.read_text())
    assert apply_patch(base, yaml.safe_load(PATCH103.read_text())) == new
    assert new["patch"] == 3 and new["minor"] == 0
    by = lambda reg: {r["name"]: r for r in reg["relations"]}
    changed = [n for n, r in by(new).items() if r != by(base)[n]]
    assert changed == ["partOf"]
    for k in ("name", "template", "family", "directed", "symmetric"):
        assert by(new)["partOf"].get(k) == by(base)["partOf"].get(k)
    names = set(by(new))
    assert {nm["relation"] for nm in by(new)["partOf"]["near_misses"]} <= names


def test_profile_v14_is_v13_with_only_the_registry_changed():
    p13 = yaml.safe_load((REPO / "configs/scinlp_profile_v13.yaml").read_text())
    p14 = yaml.safe_load((REPO / "configs/scinlp_profile_v14.yaml").read_text())
    diff = {k for k in p13 if p13[k] != p14.get(k)}
    assert diff == {"relation_registry", "status"}
    assert p14["relation_registry"] == "configs/relations_scinlp_v1.0.3.yaml"
    assert p14["choice_prompt"] == "v10" and p14["endpoint_check"] == "choice"


def _concept(cid, name, quote, section="s1", role="defined", source="llm"):
    from cumap.expert_kg.canonicalize import Mention, RegisteredConcept

    return RegisteredConcept(
        concept_id=cid,
        canonical_name=name,
        node_type="method",
        definition=None,
        first_introduced=section,
        mentions=[Mention(section_id=section, role=role, quote=quote, source=source)],
    )


def test_origin_sentence_is_the_whole_sentence_of_the_first_defined_mention():
    from cumap.expert_kg import choice_context as CC

    text = "First sentence here. We present   LM-BFF, a better method. Last one."
    c = _concept("c1", "LM-BFF", "We present LM-BFF")
    assert CC.origin_sentence(c, {"s1": text}) == "We present LM-BFF, a better method."
    spans = _concept(
        "c2", "X", "Alpha ends. Beta begins"
    )  # a quote across two sentences stays as it is
    assert (
        CC.origin_sentence(spans, {"s1": "Alpha ends. Beta begins here."})
        == "Alpha ends. Beta begins"
    )
    assert CC.origin_sentence(_concept("c3", "Y", "q", source="propagation"), {"s1": "q"}) is None


def test_neighbour_lines_leave_out_the_pair_edge_and_use_the_registry_template():
    from cumap.expert_kg import choice_context as CC

    names = {"a": "A", "b": "B", "c": "C", "d": "D"}
    tpl = {"UsedFor": "{X} is used for {Y}", "partOf": "{X} is part of {Y}"}
    edges = [
        {"src": "a", "relation": "UsedFor", "tgt": "b"},  # the pair's own edge: never shown
        {"src": "a", "relation": "UsedFor", "tgt": "c"},
        {"src": "d", "relation": "partOf", "tgt": "a"},
        {"src": "c", "relation": "partOf", "tgt": "d"},  # not a neighbour of a
    ]
    got = CC.neighbour_lines("a", "b", edges, names, tpl)
    assert got == ["A is used for C", "D is part of A"]
    assert CC.neighbour_lines("a", "b", [], names, tpl) == []


def test_graph_from_results_orients_edges_and_keeps_selected_edges_only():
    from cumap.expert_kg import choice_context as CC

    def r(out, x, y, d, group="selected"):
        return {"outcome": out, "relation": "UsedFor", "direction": d, "group": group,
                "pair": {"concept_x_id": x, "concept_y_id": y}}  # fmt: skip

    got = CC.graph_from_results(
        [r("edge", "a", "b", "forward"), r("edge", "a", "c", "reversed"), r("rejected", "a", "d", "forward"), r("edge", "a", "e", "forward", "sample")]
    )  # fmt: skip
    assert got == [
        {"src": "a", "relation": "UsedFor", "tgt": "b"},
        {"src": "c", "relation": "UsedFor", "tgt": "a"},
    ]


def test_context_modes_need_their_prompt_and_the_default_changes_nothing(monkeypatch):
    from cumap.expert_kg import choice_context as CC
    from cumap.expert_kg import relations_v8 as R8

    assert CC.resolve_choice_context() == "none"
    assert CC.build_context_fn("none", {}, RelationRegistry.from_yaml(V102)) is None
    assert CC.PROMPT_FOR == {"origin": "v11", "neighbours": "v12"}
    assert set(CC.PROMPT_FOR.values()) <= set(R8.CHOICE_PROMPTS)
    with pytest.raises(ValueError):
        CC.resolve_choice_context("both")


def test_prompts_v11_and_v12_are_v10_plus_the_background_rule_and_blocks():
    body = lambda v: (REPO / f"prompts/relation_choice/{v}.md").read_text().split("---\n\n", 1)[1]
    v10 = body("v10")
    for v, key in (("v11", "first introduced"), ("v12", "other relations")):
        b = body(v)
        assert "- Background." in b and "{context_x}" in b and "{context_y}" in b and key in b
        stripped = b.replace("{context_x}", "").replace("{context_y}", "")
        keep = [ln for ln in v10.splitlines() if ln.strip()]
        assert all(ln in stripped.splitlines() for ln in keep)  # every v10 line survives unchanged
        rendered = load_prompt(REPO / "prompts", "relation_choice", v).render(
            concept_x="X", concept_y="Y", family="f", sentence="S.", relation_options="O",
            context_x="CX", context_y="CY",
        )  # fmt: skip
        assert "CX" in rendered and "CY" in rendered and "{" not in rendered.replace("{X}", "")


def test_profiles_v15_and_v16_are_v13_plus_one_context_each():
    p13 = yaml.safe_load((REPO / "configs/scinlp_profile_v13.yaml").read_text())
    for name, prompt, ctx in (("v15", "v11", "origin"), ("v16", "v12", "neighbours")):
        p = yaml.safe_load((REPO / f"configs/scinlp_profile_{name}.yaml").read_text())
        assert {k for k in {**p13, **p} if p13.get(k) != p.get(k)} == {
            "status",
            "choice_prompt",
            "choice_context",
        }
        assert (p["choice_prompt"], p["choice_context"]) == (prompt, ctx)
        assert (
            p["relation_registry"]
            == p13["relation_registry"]
            == "configs/relations_scinlp_v1.0.2.yaml"
        )


V104 = REPO / "configs/relations_scinlp_v1.0.4.yaml"
PATCH104 = REPO / "configs/registry-patches/CR-064-relations-scinlp-v1.0.4-drop-partOf.yaml"


def test_v104_is_v102_minus_partof_and_nothing_else_changes():
    import json

    from cumap.schemas.registry_patch import apply_drops

    base, new = yaml.safe_load(V102.read_text()), yaml.safe_load(V104.read_text())
    assert apply_drops(base, yaml.safe_load(PATCH104.read_text())) == new
    assert (new["version"], new["minor"], new["patch"]) == (1, 0, 4)
    old_rel = {r["name"]: r for r in base["relations"]}
    new_rel = {r["name"]: r for r in new["relations"]}
    assert set(old_rel) - set(new_rel) == {"partOf"}
    for name, r in new_rel.items():  # only references to partOf are pruned
        assert {k for k in r if r[k] != old_rel[name].get(k)} <= {
            "near_misses",
            "conflicts_with",
            "compatible_with",
        }
        assert r["definition"] == old_rel[name]["definition"]
    assert "partOf" not in json.dumps(new)
    assert len(RelationRegistry.from_yaml(V104).all_relations()) == 10


def test_profiles_v17_v18_v19_are_their_twins_on_registry_v104():
    for twin, name in (("v13", "v17"), ("v15", "v18"), ("v16", "v19")):
        a = yaml.safe_load((REPO / f"configs/scinlp_profile_{twin}.yaml").read_text())
        b = yaml.safe_load((REPO / f"configs/scinlp_profile_{name}.yaml").read_text())
        assert {k for k in {**a, **b} if a.get(k) != b.get(k)} == {"status", "relation_registry"}
        assert b["relation_registry"] == "configs/relations_scinlp_v1.0.4.yaml"


def test_arms_without_partof_are_gated_by_the_drop_patch_and_neighbour_arms_have_a_source():
    assert AR.ARMS["r5"][0] == "cr064relR5" and AR.GRAPH_SOURCES == {
        "r7": "cr064relR3",
        "r9": "cr064relR5",
    }
    for arm in ("r5", "r8", "r9"):
        assert AR.PATCHES[arm] == PATCH104.name
        assert AR.approved(arm)  # no DRAFT in the header: owner-directed 2026-11-01


# ---- pair-delivery arms A1-A3 (every co-occurrence sentence, abbreviation-aware splitter, second look at declined pairs)
def test_abbrev_splitter_keeps_citations_together():
    from cumap.expert_kg.relations import split_sentences, split_sentences_abbrev

    t = "We fine-tune BERT or GPT - 2 ( Radford et al . , 2019 ) on Persona-Chat . Results are good ( e.g . , TREC ) . Done."
    assert len(split_sentences(t)) > 3
    assert split_sentences_abbrev(t) == [
        "We fine-tune BERT or GPT - 2 ( Radford et al . , 2019 ) on Persona-Chat .",
        "Results are good ( e.g . , TREC ) .",
        "Done.",
    ]


def _concepts(*names):
    from cumap.expert_kg.canonicalize import RegisteredConcept

    return [RegisteredConcept(f"C{i}", n, "method", None, "S1") for i, n in enumerate(names)]


def test_every_cooccurrence_sentence_is_a_candidate():
    from cumap.expert_kg import cooccurrence as CO
    from cumap.schemas.relations import RelationRegistry

    reg = RelationRegistry.from_yaml(REPO / "configs/relations_scinlp_v1.0.4.yaml")
    text = "BERT is tested on GLUE. Nothing here. We run BERT on GLUE again. GLUE only."
    cs = _concepts("BERT", "GLUE")
    first = CO.build_pairs([("S1", text)], cs, reg, split="plain", cooccurrence="first")
    every = CO.build_pairs([("S1", text)], cs, reg, split="plain", cooccurrence="all")
    assert len(first) == 1 and len(every) == 2
    assert every[0].sentence == first[0].sentence and every[1].sentence == "We run BERT on GLUE again."
    assert every[1].pair_id.endswith("~s2") and every[0].pair_id == first[0].pair_id


def test_default_enumeration_unchanged():
    from cumap.expert_kg.relations import enumerate_candidates
    from cumap.schemas.relations import RelationRegistry

    reg = RelationRegistry.from_yaml(REPO / "configs/relations_scinlp_v1.0.4.yaml")
    text = "BERT is tested on GLUE. We run BERT on GLUE again."
    a = enumerate_candidates("S", text, _concepts("BERT", "GLUE"), reg)
    assert len(a) == 1 and a[0].sentence == "BERT is tested on GLUE." and a[0].cooccurrence_count == 2


def test_pair_delivery_profiles_and_prompt():
    import yaml

    from cumap.cr064 import arm_relations as AR
    from cumap.llm.prompts import load_prompt

    v18 = yaml.safe_load((REPO / "configs/scinlp_profile_v18.yaml").read_text())
    for n, extra in ((20, {"cooccurrence": "all"}), (21, {"cooccurrence": "all", "sentence_split": "abbrev"}),
                     (22, {"cooccurrence": "all", "sentence_split": "abbrev", "declined_pass": "v13"})):  # fmt: skip
        p = yaml.safe_load((REPO / f"configs/scinlp_profile_v{n}.yaml").read_text())
        for k, v in p.items():
            if k in extra:
                assert v == extra[k]
            elif k != "status":
                assert v == v18[k], k
        assert set(extra) <= set(p)
    assert AR.ARMS["a1"][0] == "cr064relA1" and AR.BUILD_ARMS == ("a1", "a2", "a3") and AR.approved("a3")
    v11 = load_prompt(REPO / "prompts", "relation_choice", "v11")
    v13 = load_prompt(REPO / "prompts", "relation_choice", "v13")
    assert "Second reading" in v13.body and "Second reading" not in v11.body

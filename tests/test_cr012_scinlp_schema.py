"""CR-012 SciNLP benchmark-local schema: exact literal labels of the frozen release, the ruled type constraints, no networking labels,
prompt variant limited to the schema lines, no test material, and the default CUM path untouched."""

import difflib
import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from cumap.concepts_v4 import schema as GS
from cumap.concepts_v4.bank import render_examples
from cumap.cr012.schema_profile import active_profile, load_profile
from cumap.expert_kg.relations_v3 import build_relation_choice_v3
from cumap.schemas.relations import RelationRegistry

PROFILE = Path("configs/cr012_scinlp_schema.yaml")
REG = RelationRegistry.from_yaml(Path("configs/relations_scinlp.yaml"))
MANIFEST = json.loads(Path("reports/cr012/dataset_manifest.json").read_text())["scinlp"]
NETWORKING = {
    "Protocol",
    "Component",
    "Mechanism",
    "DataUnit",
    "Parameter",
    "Concept",
    "Identifier",
    "Property",
    "Event",
    "State",
    "Layer",
}


def release_labels():
    ents, rels = set(), set()
    for sp in MANIFEST["splits"].values():
        ents |= set(sp["entity_types"])
        rels |= set(sp["relation_types"])
    return ents, rels


def test_entity_types_are_exactly_the_literal_labels_of_the_frozen_release():
    ents, _ = release_labels()
    p = load_profile(PROFILE)
    assert (
        set(p.entity_types) == ents == {"task", "method", "dataset", "metric"}
        and set(REG.node_types) == ents
    )
    assert (
        not (set(REG.node_types) & NETWORKING) and "Concept" not in REG.node_types
    )  # no generic catch-all, no networking type


def test_relations_are_exactly_the_eleven_release_labels_plus_no_relation_and_other():
    _, rels = release_labels()
    names = [r.name for r in REG.all_relations()]
    assert set(names) == rels and len(names) == 11
    kinds = {c.kind for c in REG.choice_set("A", "B")}
    assert kinds == {"relation", "no_relation", "other"}
    assert {r.family for r in REG.all_relations()} == {"scinlp"} and list(REG.families) == [
        "scinlp"
    ]


def test_directionality_and_the_ruled_type_constraints():
    sym = {r.name for r in REG.all_relations() if r.symmetric}
    assert sym == {"similarWith", "compareWith"} and all(
        r.directional for r in REG.all_relations() if r.name not in sym
    )
    rule = {
        "MeasuredBy": ("method", "metric"), "UsedFor": ("method", "task"), "trainedWith": ("method", "dataset"),
        "enhancedBy": ("method", "method"), "subtaskOf": ("task", "task"), "evaluatedBy": ("task", "metric"), "evaluatedOn": ("task", "dataset"),
    }  # fmt: skip
    for name, (d, r) in rule.items():
        rel = REG.get(name)
        assert rel.domain_types == [d] and rel.range_types == [r], name
    for free in (
        "subclassOf",
        "partOf",
        "compareWith",
        "similarWith",
    ):  # no narrower hard rule than the benchmark supports
        rel = REG.get(free)
        assert (
            set(rel.domain_types) == set(rel.range_types) == {"task", "method", "dataset", "metric"}
        ), free


def test_no_cum_qualifier_is_defined_or_required_and_negation_is_representable():
    assert not ({"part_type", "action_type", "dimension"} & set(REG.qualifiers))
    for r in REG.all_relations():
        assert not (REG.required_qualifiers(r.name) - {"polarity", "modality"})
    assert "negated" in REG.qualifiers["polarity"].values


def test_benchmark_relations_cannot_become_cum_merge_instructions():
    schema = build_relation_choice_v3(REG, "scinlp", True)  # same_concept requested
    fields = json.dumps(schema.model_json_schema())
    assert (
        "same_concept" not in fields and "similarWith" in fields
    )  # similarWith stays an ordinary relation


def test_generator_schema_accepts_scinlp_types_only():
    sch = GS.make_schemas(("task", "method", "dataset", "metric"))
    item = {
        "name": "BERT",
        "aliases": [],
        "node_type": "method",
        "role": "used",
        "evidence": "x",
        "para": "P1",
        "extraction_origin": "independent",
        "anchors": [],
        "independence_check": None,
        "found_via_anchor": False,
    }
    ok = {"existing_mentions": [], "not_mentions": [], "new_concepts": [item], "hint_responses": []}
    assert sch.generator.model_validate(ok)
    for bad in ("Protocol", "Concept", "Model"):
        with pytest.raises(ValidationError):
            sch.generator.model_validate({**ok, "new_concepts": [{**item, "node_type": bad}]})
    assert sch.generator.__name__ != GS.ConceptGeneratorV4LLM.__name__


def test_the_default_cum_path_is_untouched(monkeypatch):
    monkeypatch.delenv("CUMAP_BENCHMARK_PROFILE", raising=False)
    monkeypatch.delenv("CUMAP_RELATION_REGISTRY", raising=False)
    assert active_profile() is None
    assert (
        GS.make_schemas(None) is GS.DEFAULT_SCHEMAS
        and GS.make_schemas(GS.NODE_TYPES) is GS.DEFAULT_SCHEMAS
    )
    from cumap.config import load_settings

    assert load_settings().relation_registry == Path("configs/relations_v1.3.yaml")
    monkeypatch.setenv("CUMAP_RELATION_REGISTRY", "configs/relations_scinlp.yaml")
    assert load_settings().relation_registry == Path("configs/relations_scinlp.yaml")


def test_zero_shot_means_no_examples_are_rendered():
    assert render_examples({"examples": []}) == ""
    assert yaml.safe_load(PROFILE.read_text())["few_shot_bank"].startswith("none")


def test_prompt_variant_differs_from_v4_only_in_the_schema_lines():
    a = Path("prompts/concept_generator/v4.md").read_text().splitlines()
    b = Path("prompts/concept_generator/v4_scinlp.md").read_text().splitlines()
    changed = [
        l[1:]
        for l in difflib.unified_diff(a, b, lineterm="", n=0)
        if l[:1] in "+-" and not l.startswith(("+++", "---"))
    ]
    allowed = (
        "version:",
        "  CR-012 SciNLP",
        "You are building a knowledge graph",
        "interchangeable in any sentence",
        "Node types",
        "Concept. Give the type",
        "and no other node type",
        "- task:",
        "- method:",
        "- dataset:",
        "- metric:",
        "  classification, named",
        "Give the type of what",
        "Protocol, Mechanism",
    )
    stray = [
        l
        for l in changed
        if not l.lstrip("+-").startswith(allowed) and not any(l.startswith(x) for x in allowed)
    ]
    assert not stray, stray
    node_section = "\n".join(b).split("Node types (only these four")[1].split("Anchor types")[0]
    assert not any(
        t in node_section for t in ("Protocol", "DataUnit", "Component", "Identifier", "Concept.")
    )


def test_schema_files_contain_no_test_derived_material():
    scan = json.loads(Path("reports/cr012/isolation_scan.json").read_text())
    assert (
        scan["verdict"] == "CLEAN"
        and scan["scinlp_test_surfaces_found_in_development_artefacts"] == {}
    )
    for f in (
        "configs/relations_scinlp.yaml",
        "configs/cr012_scinlp_schema.yaml",
        "prompts/concept_generator/v4_scinlp.md",
    ):
        text = Path(f).read_text()
        for doc in MANIFEST["splits"]["test"]["doc_keys"]:
            assert doc not in text


def test_scinlp_prediction_uses_evidence_grounded_token_spans_and_drops_negated_edges():
    from cumap.cr012 import scinlp_run as SR
    from cumap.cr012.adapters import SciNLPAdapter

    doc = SciNLPAdapter().load_documents("dev", paragraph_every=10)[
        0
    ]  # dev only; the test split is never read
    sent = doc.text
    qa = sent[: doc.span_to_chars((0, 5))[1]]

    def node(cid, name):
        return {
            "concept_id": cid,
            "canonical_name": name,
            "aliases": [],
            "node_type": "method",
            "mentions": [{"section_id": doc.doc_key, "role": "used", "quote": qa}],
        }

    def res(qual):
        return {
            "outcome": "edge",
            "group": "selected",
            "direction": "forward",
            "relation": "UsedFor",
            "qualifiers": qual,
            "evidence_quote": qa,
            "pair": {"concept_x_id": "x", "concept_y_id": "y"},
        }

    surf_a, surf_b = (
        sent[slice(*doc.span_to_chars((0, 2)))],
        sent[slice(*doc.span_to_chars((3, 5)))],
    )
    cp = {
        "concepts": [node("x", surf_a), node("y", surf_b)],
        "relation_results_v3": [res({}), res({"polarity": "negated"})],
    }
    out = SR.predict(doc, cp)
    assert {n.node_id: n.mentions for n in out["nodes"]} == {"x": ((0, 2),), "y": ((3, 5),)}
    assert len(out["edges"]) == 1 and out["stats"]["negated_dropped"] == 1


def test_the_scinlp_test_split_is_refused_unless_stop4_is_authorised(monkeypatch):
    from cumap.cr012 import scinlp_run as SR

    monkeypatch.delenv("CUMAP_CR012_STOP4", raising=False)
    assert SR.split_allowed("dev") and not SR.split_allowed("test")
    monkeypatch.setenv("CUMAP_CR012_STOP4", "1")
    assert SR.split_allowed("test")


def test_surface_gold_converts_token_spans_to_characters_and_drops_same_surface_relations():
    from cumap.cr012.adapters import SciNLPAdapter
    from cumap.cr012.scinlp_oracle import surface_gold

    ad = SciNLPAdapter()
    doc = ad.load_documents("dev", paragraph_every=10)[0]
    g = ad.gold("dev")[doc.doc_key]
    pg, stats = surface_gold(doc, g)
    assert stats["gold_mentions"] == len(g.mentions) and len(pg.mentions) == len(g.mentions)
    for m, om in zip(pg.mentions, sorted(g.mentions, key=lambda x: x.span), strict=True):
        a, b = doc.span_to_chars(om.span)
        assert m.span == (a, b) and m.type == om.type
    assert all(r.src_concept != r.tgt_concept for r in pg.relations)
    assert stats["relations_between_distinct_surfaces"] + stats[
        "relations_with_identical_endpoint_surface"
    ] == len(g.relations)


def test_stop4_refuses_without_authorisation_and_names_runs_consistently(monkeypatch, capsys):
    from cumap.cr012 import stop4

    assert stop4.run_id("pd", "4.4", "E3") == "cr012_heldout_4_4_E3"
    assert (
        stop4.run_id("sc", "P17-1058.grobid", "E1", "stab2")
        == "cr012_scinlp_stab2_P17_1058_grobid_E1"
    )
    monkeypatch.setattr("sys.argv", ["stop4", "run"])
    with pytest.raises(SystemExit):
        stop4.main()


def test_stop5_reports_exist_and_state_the_ruled_wordings():
    r = Path("reports/cr012")
    final = (r / "FINAL_EVALUATION.md").read_text()
    for needle in (
        "NOT_APPLICABLE_NO_ADOPTED_TRANSFORMATION",
        "NOT_EVALUABLE_SINGLE_ANNOTATOR",
        "DESCRIPTIVE_SMALL_N",
        "not pooled" if False else "never pooled",
    ):
        assert needle in final, needle
    assert "delta_F1_sleep = 0" not in final.replace("no delta_F1_sleep exist", "")
    assert "NON_INFORMATIVE_UNDER_CURRENT_DENOMINATOR" in (r / "stability.md").read_text()
    assert len(list((r / "figures").glob("*.svg"))) == 5

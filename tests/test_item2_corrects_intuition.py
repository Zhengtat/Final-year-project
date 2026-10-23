"""CR-008 item 2: corrects_intuition / intuition are gone from qualifiers v4 and registry v1.3; old
edges that still carry them are ignored by the validators and reports (no network, no key)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from cumap.expert_kg.checks import check_structure
from cumap.expert_kg.pipeline import Checkpoint
from cumap.expert_kg.relations import CandidatePair, QualifiersLLM, RelationEdgeCandidate
from cumap.expert_kg.relations_v3 import build_qualifiers_v3
from cumap.expert_kg.slice_rerun import build_pair_registry
from cumap.llm.prompts import load_prompt
from cumap.schemas.relations import RelationRegistry

REPO = Path(__file__).parents[1]
REG = RelationRegistry.from_yaml(REPO / "configs/relations_v1.3.yaml")

V4_FIELDS = {
    "polarity": "affirmed",
    "modality": "always",
    "conditions": [],
    "part_type": None,
    "dimension": None,
    "action_type": None,
    "surface_phrase": "is part of",
}


def test_registry_v13_and_prompt_v4_have_no_intuition_fields():
    assert "corrects_intuition" not in REG.qualifiers and "intuition" not in REG.qualifiers
    body = load_prompt(REPO / "prompts", "relation_qualifiers", "v4").body
    assert "corrects_intuition" not in body and "intuition" not in body


def test_v4_schema_rejects_the_legacy_fields_and_v3_still_requires_them():
    v4 = build_qualifiers_v3(REG, intuition=False)
    v4.model_validate(V4_FIELDS)
    with pytest.raises(ValidationError):
        v4.model_validate({**V4_FIELDS, "corrects_intuition": False, "intuition": None})
    v3 = build_qualifiers_v3(REG, intuition=True)
    with pytest.raises(ValidationError):
        v3.model_validate(V4_FIELDS)  # the frozen v3 schema is unchanged


def _old_edge_result(pid, x, y):
    return {
        "outcome": "edge",
        "reason": None,
        "family": "classification_structure",
        "relation": "part_of",
        "direction": "forward",
        "statement": "x is part of y",
        "evidence_quote": "x is part of y",
        "group": "selected",
        "qualifiers": {**V4_FIELDS, "corrects_intuition": True, "intuition": "a wrong belief"},
        "pair": {
            "pair_id": pid,
            "section_id": "s1",
            "concept_x_id": x,
            "concept_y_id": y,
            "sentence": "x is part of y",
        },
    }


def test_old_edges_carrying_the_field_are_ignored_by_the_validator_and_snapshot_inputs():
    results = [_old_edge_result("P1", "a", "b")]
    ck = Checkpoint(run_id="r", stage="snapshots", relation_results_v3=results)
    reg = build_pair_registry(ck)
    (res,) = reg.all()
    assert res.edge is not None and res.edge.relation == "part_of"
    assert not hasattr(
        res.edge.qualifiers, "corrects_intuition"
    )  # never carried into the edge model
    assert "corrects_intuition" not in QualifiersLLM.model_fields
    edge = RelationEdgeCandidate(
        pair=CandidatePair("P1", "s1", "a", "b", "x is part of y"),
        family="classification_structure",
        relation="part_of",
        direction="forward",
        statement="s",
        evidence_quote="q",
        qualifiers=res.edge.qualifiers,
    )
    out = check_structure([edge], {"a": "Component", "b": "Component"}, REG)
    assert out.domain_range_errors == [] and out.cycles == []  # the legacy field changes nothing

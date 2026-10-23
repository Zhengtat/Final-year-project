"""CR-036: `assembly: v2` edge store and "save graph" export (no network, no key)."""

import json
from pathlib import Path

import numpy as np
import pytest
from test_relations_v3 import FRAME, SWITCH, run

from cumap.config import REPO_ROOT
from cumap.expert_kg import edge_store as ES
from cumap.expert_kg import slice_rerun as sr
from cumap.expert_kg.canonicalize import ConceptRegistry, RegisteredConcept
from cumap.expert_kg.pipeline import build_snapshots_stage
from cumap.expert_kg.relations import CandidatePair
from cumap.expert_kg.slice_rerun import SectionInput
from cumap.schemas.relations import RelationRegistry

REG_PATH = REPO_ROOT / "configs/relations_v1.3.yaml"
REG = RelationRegistry.from_yaml(REG_PATH)
TYPES = {
    "sw": "Component",
    "fr": "DataUnit",
    "pr": "Protocol",
    "ev": "Event",
    "st": "State",
    "a": "Concept",
    "b": "Concept",
}


def res(pid, x, y, rel, direction="forward", quote="q", group="selected", family="f", **kw):
    return {"outcome": "edge", "group": group, "relation": rel, "direction": direction, "evidence_quote": quote, "family": family,
            "pair": {"pair_id": pid, "section_id": "1.1", "concept_x_id": x, "concept_y_id": y, "sentence": "s"}, **kw}  # fmt: skip


def test_a_reversed_answer_is_stored_as_y_to_x():
    s = ES.build_edge_store([res("P1", "fr", "sw", "acts_on", "reversed")], TYPES, REG)
    e = s.edges[0]
    assert (e.source_id, e.target_id, e.direction_model, e.flags) == ("sw", "fr", "reversed", [])


def test_a_one_orientation_pair_gets_the_type_valid_direction_and_a_log_entry():
    s = ES.build_edge_store(
        [res("P1", "fr", "sw", "acts_on", "forward")], TYPES, REG
    )  # frame acts_on switch is type-invalid
    e = s.edges[0]
    assert (e.source_id, e.target_id) == ("sw", "fr") and "direction_set_by_types" in e.flags
    assert s.log == [
        {
            "pair_id": "P1",
            "event": "direction_set_by_types",
            "model_direction": "forward",
            "relation": "acts_on",
        }
    ]
    both = ES.build_edge_store(
        [res("P2", "a", "b", "uses", "forward")], TYPES, REG
    )  # both orientations valid: the model's answer stands
    assert (both.edges[0].source_id, both.edges[0].flags) == ("a", [])


def test_two_different_relations_on_one_pair_are_both_kept_with_distinct_ids():
    s = ES.build_edge_store(
        [res("P1", "pr", "fr", "uses"), res("P1", "pr", "fr", "acts_on")], TYPES, REG
    )
    assert [(e.edge_id, e.relation) for e in s.edges] == [("P1", "uses"), ("P1~acts_on", "acts_on")]


def test_two_identical_edges_merge_with_both_quotes():
    s = ES.build_edge_store(
        [
            res("P1", "a", "b", "uses", quote="A uses B"),
            res("P9", "a", "b", "uses", quote="B is used by A"),
        ],
        TYPES,
        REG,
    )
    assert (
        len(s.edges) == 1
        and s.edges[0].quotes == ["A uses B", "B is used by A"]
        and s.edges[0].pair_ids == ["P1", "P9"]
    )


def test_a_symmetric_edge_found_both_ways_is_one_edge():
    s = ES.build_edge_store(
        [res("P1", "b", "a", "connected_to"), res("P2", "a", "b", "connected_to")], TYPES, REG
    )
    assert len(s.edges) == 1 and (s.edges[0].source_id, s.edges[0].target_id) == ("a", "b")


def test_a_conflicts_with_pair_in_one_direction_is_flagged_and_neither_is_dropped():
    s = ES.build_edge_store(
        [
            res("P1", "ev", "st", "causes"),
            res("P1b", "ev", "st", "prevents"),
            res("P2", "st", "ev", "causes"),
        ],
        TYPES,
        REG,
    )
    assert len(s.edges) == 3 and len(s.conflicts) == 1
    assert (
        "conflict:prevents" in s.edges[0].flags
        and "conflict:causes" in s.edges[1].flags
        and s.edges[2].flags == []
    )


def test_sample_results_stay_out_of_the_edge_store_and_the_snapshots(tmp_path):
    results = [res("P1", "a", "b", "uses"), res("S1", "a", "b", "requires", group="sample")]
    s = ES.build_edge_store(results, TYPES, REG)
    assert [e.pair_id for e in s.edges] == ["P1"] and [m["pair_id"] for m in s.measurement] == [
        "S1"
    ]
    reg, secs = _concepts(), [SectionInput("1.1", 1, "text", [], "d")]
    rows = [{"edge_id": e.edge_id, "source_id": e.source_id, "target_id": e.target_id, "relation": e.relation, "family": e.family, "section_id": e.section_id} for e in s.edges]  # fmt: skip
    out = build_snapshots_stage(
        REG,
        secs,
        reg,
        None,
        tmp_path,
        "r",
        edge_rows=rows,
        run_checks=False,
        extra_manifest={"assembly": "v2"},
    )
    assert [e.edge_id for e in out[0].snapshot.edges] == ["P1"]
    assert json.loads((tmp_path / "ch1" / "manifest.json").read_text())["assembly"] == "v2"


def _concepts():
    reg = ConceptRegistry(lambda t: np.zeros(1))
    from cumap.expert_kg.canonicalize import Mention

    cs = []
    for cid, typ in (("a", "Concept"), ("b", "Concept")):
        c = RegisteredConcept(cid, cid, typ, None, "1.1")
        c.mentions = [Mention("1.1", "used", "q")]
        cs.append(c)
    reg.restore(cs)
    return reg


def test_a_registry_mismatch_on_load_stops_and_a_missing_record_stops():
    rec = ES.registry_record(REG, REG_PATH)
    ES.check_registry_record({"registry": rec}, REG, REG_PATH)  # same version and hash: fine
    other = RelationRegistry.from_yaml(REPO_ROOT / "configs/relations_v1.4.yaml")
    with pytest.raises(ValueError, match="registry mismatch"):
        ES.check_registry_record(
            {"registry": rec}, other, REPO_ROOT / "configs/relations_v1.4.yaml"
        )
    with pytest.raises(ValueError, match="no registry version"):
        ES.check_registry_record({}, REG, REG_PATH)


def test_v2_snapshots_equal_legacy_snapshots_when_no_new_rule_fires(tmp_path):
    from cumap.expert_kg.pipeline import PairRegistry, PairResolution
    from cumap.expert_kg.relations import QualifiersLLM, RelationEdgeCandidate

    pair = CandidatePair("P1", "1.1", "a", "b", "A uses B.")
    edge = RelationEdgeCandidate(pair=pair, family="function_means", relation="uses", direction="forward", statement="s", evidence_quote="A uses B",
                                 qualifiers=QualifiersLLM(polarity="affirmed", modality="always", conditions=[], part_type=None, dimension=None, surface_phrase="uses"))  # fmt: skip
    prs = PairRegistry()
    prs.restore([PairResolution("a", "b", True, edge, None, ["A uses B."])])
    secs = [SectionInput("1.1", 1, "text", [], "d")]
    legacy = build_snapshots_stage(REG, secs, _concepts(), prs, tmp_path / "legacy", "r")
    store = ES.build_edge_store(
        [res("P1", "a", "b", "uses", quote="A uses B", family="function_means")], TYPES, REG
    )
    rows = [{"edge_id": e.edge_id, "source_id": e.source_id, "target_id": e.target_id, "relation": e.relation, "family": e.family, "section_id": e.section_id} for e in store.edges]  # fmt: skip
    v2 = build_snapshots_stage(
        REG, secs, _concepts(), None, tmp_path / "v2", "r", edge_rows=rows, run_checks=False
    )
    for name in ("nodes.jsonl", "edges.jsonl", "merges.jsonl", "rejected.jsonl", "manifest.json"):
        assert (tmp_path / "legacy/ch1" / name).read_bytes() == (
            tmp_path / "v2/ch1" / name
        ).read_bytes(), name
    assert legacy[0].snapshot == v2[0].snapshot


def test_classification_sets_the_type_valid_orientation_under_v2_and_rejects_under_legacy(
    tmp_settings, fixtures_dir
):
    args = (
        tmp_settings,
        fixtures_dir,
        FRAME,
        SWITCH,
        "The frame forwards the switch.",
        "v3_mechanism",
        "v3_acts_on_frame_first",
    )
    legacy = run(*args)
    assert (
        legacy.outcome == "rejected"
        and legacy.reason == "domain_range"
        and "direction_by_types" not in legacy.to_dict()
    )
    v2 = run(*args, direction_by_types=True)
    assert (
        v2.outcome == "edge"
        and v2.direction == "reversed"
        and v2.direction_by_types == {"model": "forward", "set": "reversed"}
    )
    assert v2.to_dict()["direction_by_types"]["set"] == "reversed"


def test_recoverable_domain_range_counts_only_results_whose_reverse_is_valid():
    rej = [
        {"outcome": "rejected", "reason": "domain_range", "relation": "acts_on", "direction": "forward", "pair": {"pair_id": "R1", "concept_x_id": "fr", "concept_y_id": "sw"}},
        {"outcome": "rejected", "reason": "domain_range", "relation": "acts_on", "direction": "forward", "pair": {"pair_id": "R2", "concept_x_id": "fr", "concept_y_id": "fr"}},
    ]  # fmt: skip
    r = ES.recoverable_domain_range(rej, TYPES, REG)
    assert r["domain_range_rejections"] == 2 and r["recoverable_by_direction_from_types"] == 1


def test_misconception_proposal_reuses_an_existing_result_instead_of_a_new_classification():
    existing = res("P3", "pr", "fr", "uses")
    assert ES.find_existing_result([existing], "pr", "uses", "fr") is existing
    assert (
        ES.find_existing_result([existing], "fr", "uses", "pr") is None
    )  # a directed relation matches only in the proposed direction
    sym = res("P4", "a", "b", "connected_to")
    assert ES.find_existing_result([sym], "b", "connected_to", "a", REG) is sym


def test_policy_default_is_legacy_and_invalid_values_raise():
    assert ES.resolve_assembly() == "legacy" and ES.resolve_assembly("v2") == "v2"
    with pytest.raises(ValueError):
        ES.resolve_assembly("v3")


@pytest.mark.skipif(
    not (REPO_ROOT / "data/processed/kg/slice3_c2/snapshots/ch1/edges.jsonl").exists(),
    reason="local slice3_c2 not present",
)
def test_legacy_replay_of_slice3_c2_snapshots_is_byte_identical(tmp_path):
    from cumap.config import load_demo_slice
    from cumap.expert_kg.pipeline import load_checkpoint

    run_dir = REPO_ROOT / "data/processed/kg/slice3_c2"
    cp = load_checkpoint(run_dir)
    sc = load_demo_slice()
    sections = sr.load_sections(REPO_ROOT / sc.pd.source_jsonl, list(sc.pd.chapters))
    registry = RelationRegistry.from_yaml(REPO_ROOT / "configs/relations_v1.3.yaml")
    sr.mark_gated_dropped(cp, registry)
    pairs = sr.build_pair_registry(cp)
    build_snapshots_stage(
        registry,
        sections,
        sr._restore_concept_registry(cp, lambda t: np.zeros(1)),
        pairs,
        tmp_path,
        cp.run_id,
        merges=cp.merges,
    )
    for ch in sorted(Path(run_dir / "snapshots").glob("ch*")):
        for name in (
            "nodes.jsonl",
            "edges.jsonl",
            "merges.jsonl",
            "rejected.jsonl",
            "manifest.json",
        ):
            assert (ch / name).read_bytes() == (tmp_path / ch.name / name).read_bytes(), (
                ch.name,
                name,
            )


def test_replay_compares_v2_with_legacy_and_counts_recoverable_rejections():
    from cumap.cr036.replay import markdown, replay

    cp = {
        "concepts": [{"concept_id": k, "node_type": v} for k, v in TYPES.items()],
        "relation_results_v3": [
            res("P1", "b", "a", "connected_to"),
            res("P2", "a", "b", "uses"),
            res("P3", "a", "b", "uses"),
            res("S1", "a", "b", "requires", group="sample"),
            {"outcome": "rejected", "reason": "domain_range", "relation": "acts_on", "direction": "forward", "pair": {"pair_id": "R1", "concept_x_id": "fr", "concept_y_id": "sw"}},
        ],
    }  # fmt: skip
    r = replay(cp, REG, {("b", "connected_to", "a"), ("a", "uses", "b")})
    assert (r["v2_store_edges"], r["merged_identical"], r["measurement_sample_results"]) == (
        2,
        1,
        1,
    )
    assert r["only_in_legacy"] == [("b", "connected_to", "a")] and r["only_in_v2"] == [
        ("a", "connected_to", "b")
    ]  # symmetric ids sorted
    assert (
        r["domain_range"]["recoverable_by_direction_from_types"] == 1
        and r["run_records_a_registry_version"] is False
    )
    assert "NOT adopted" in markdown("fx", "1.3", r, True)

"""End-to-end `kg organise` on a tiny synthetic run (no real data, no network, no key)."""

import hashlib
import json
from pathlib import Path

import pytest

from cumap.expert_kg.snapshots import ChapterSnapshot, SnapshotEdge, SnapshotNode, write_snapshot
from cumap.organisation.config import OrgConfig, load_config
from cumap.organisation.pipeline import make_org_id, run_organisation
from cumap.organisation.principles import InstantiatesEdge, activation_chapters, principles_present
from cumap.organisation.schemas import LABEL_STRUCTURAL, OrgNodeState, RestructureEvent
from cumap.schemas.relations import RelationRegistry

REPO = Path(__file__).parents[1]
RUN = "kg_fixture"


def cfg_fast() -> OrgConfig:
    raw = load_config().model_dump()
    raw["null_model"]["iterations"] = 8
    return OrgConfig(**raw)


def _edge(i, s, rel, t, fam, ch, sec, sc=2, tc=2):
    return SnapshotEdge(f"E{i}", s, rel, t, fam, sc, tc, sec)


@pytest.fixture
def world(tmp_path: Path):
    run_dir = tmp_path / "data/processed/kg" / RUN
    ch2 = ["H", "a1", "a2", "a3", "a4", "a5", "a6", "p1", "p2", "data", "x1", "x2"]
    ch3 = ["b1", "b2", "b3", "b4", "lonely"]
    cls, sem = "classification_structure", "function_means"
    e2 = [_edge(1, f"a{i}", "is_a", "H", cls, 2, "s2a") for i in range(1, 7)]
    e2 += [
        _edge(7, "H", "has_property", "p1", cls, 2, "s2b"),
        _edge(8, "H", "has_property", "p2", cls, 2, "s2b"),
        _edge(9, "data", "uses", "x1", sem, 2, "s2c"),
        _edge(10, "x1", "uses", "x2", sem, 2, "s2d"),
    ]
    e2 = [
        SnapshotEdge(
            f"E{i}",
            e.source_concept_id,
            e.relation,
            e.target_concept_id,
            e.family,
            2,
            2,
            e.section_id,
        )
        for i, e in enumerate(e2, 1)
    ]
    e3 = [
        SnapshotEdge("E11", "b1", "is_a", "H", cls, 3, 2, "s3a"),
        SnapshotEdge("E12", "b2", "is_a", "H", cls, 3, 2, "s3a"),
        SnapshotEdge("E13", "b3", "is_a", "b1", cls, 3, 3, "s3b"),
        SnapshotEdge("E14", "b4", "uses", "x2", sem, 3, 2, "s3c"),
        SnapshotEdge("E15", "a1", "uses", "b3", sem, 2, 3, "s3d"),
    ]
    fc = {**{c: 2 for c in ch2}, **{c: 3 for c in ch3}}
    nodes = lambda ids, ch: [SnapshotNode(c, c, "Concept", fc[c], [], 1) for c in ids]
    snap_root = run_dir / "snapshots"
    write_snapshot(ChapterSnapshot(RUN, 2, nodes(ch2, 2), e2), snap_root)
    write_snapshot(ChapterSnapshot(RUN, 3, nodes(ch2 + ch3, 3), e3), snap_root)

    secs = ["s2a", "s2b", "s2c", "s2d", "s3a", "s3b", "s3c", "s3d"]
    mentions: dict[str, list] = {}
    for c in ch2 + ch3:
        first = 0 if c in ch2 else 4
        mentions[c] = [
            {"section_id": secs[first], "role": "defined", "quote": "q"},
            {"section_id": secs[first + 1], "role": "used", "quote": "q"},
        ]
    mentions["data"] = [{"section_id": s, "role": "used", "quote": "q"} for s in secs[:7]]
    checkpoint = {
        "run_id": RUN,
        "concepts": [
            {"concept_id": c, "canonical_name": c, "node_type": "Concept", "mentions": m}
            for c, m in mentions.items()
        ],
    }
    (run_dir / "checkpoint.json").write_text(json.dumps(checkpoint))
    sections = tmp_path / "sections.jsonl"
    sections.write_text(
        "\n".join(
            json.dumps(
                {"section_id": s, "chapter_num": 2 if s.startswith("s2") else 3, "order_index": i}
            )
            for i, s in enumerate(secs)
        )
    )
    gold = tmp_path / "data/gold"
    gold.mkdir(parents=True)
    (gold / "sentinel.txt").write_text("human-owned")
    return run_dir, sections, tmp_path


def _hashes(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _run(world, **kw):
    run_dir, sections, _ = world
    registry = RelationRegistry.from_yaml(REPO / "configs/relations_v1.yaml")
    return run_organisation(
        run_dir, sections, registry, kw.pop("cfg", cfg_fast()), version="test", **kw
    )


def test_kg_organise_never_modifies_content_and_writes_only_under_organisation(world):
    run_dir, _, root = world
    before = _hashes(run_dir)
    gold_before = _hashes(root / "data/gold")
    org = _run(world)
    after = _hashes(run_dir)
    new = set(after) - set(before)
    assert all(p.startswith(f"organisation/{org.org_id}/") for p in new) and new
    assert {
        k: v for k, v in after.items() if k in before
    } == before  # snapshots + checkpoint byte-identical
    assert _hashes(root / "data/gold") == gold_before
    assert {p.split("/")[-1] for p in new} == {
        "org_nodes.jsonl",
        "communities.jsonl",
        "events.jsonl",
        "manifest.json",
    }


def test_outputs_validate_against_schemas_and_manifest_is_complete(world):
    org = _run(world)
    for ch in (2, 3):
        for line in (org.org_dir / f"ch{ch}" / "org_nodes.jsonl").read_text().splitlines():
            OrgNodeState(**json.loads(line))
        for line in (org.org_dir / f"ch{ch}" / "events.jsonl").read_text().splitlines():
            RestructureEvent(**json.loads(line))
    m = json.loads((org.org_dir / "manifest.json").read_text())
    assert m["org_id"] == org.org_id and m["kg_run_id"] == RUN and m["mode"] == "provisional"
    assert m["label_source"] == LABEL_STRUCTURAL and m["seeds"]["null_model"] == 42
    c3 = m["chapters"]["3"]
    assert {"primary", "secondary", "label", "rho_obs"} <= set(c3["core_periphery"])
    assert (
        c3["stability"]["jaccard_core"] is not None
        and m["chapters"]["2"]["stability"]["jaccard_core"] is None
    )


def test_rings_bands_and_guard_on_the_fixture(world):
    org = _run(world)
    ch3 = {n.concept_id: n for n in org.chapters[1].nodes}
    assert ch3["lonely"].ring == "unlinked" and ch3["lonely"].n_typed_edges == 0
    assert (
        ch3["data"].background_flag and ch3["data"].ring == "background"
    )  # never defined, in most sections
    assert (
        ch3["H"].ring in {"centre", "inner"} and ch3["H"].importance_raw > ch3["a6"].importance_raw
    )
    assert 0.0 <= ch3["H"].radius <= 1.0 and ch3["lonely"].radius > 1.0


def test_dual_basis_rings_and_split_flags_are_written(world):
    org = _run(world)
    ch3 = {n.concept_id: n for n in org.chapters[1].nodes}
    for n in ch3.values():
        assert n.ring == n.ring_adj  # config default basis is adjusted
        assert n.radius == n.radius_adj
    assert ch3["lonely"].persistent_unlinked is False  # unlinked in only one snapshot (born in ch3)
    assert all(not n.persistent_periphery for n in ch3.values() if n.n_typed_edges == 0)


def test_events_point_at_the_new_edges_of_the_chapter(world):
    org = _run(world)
    ch3_events = org.chapters[1].events
    new_edge_ids = {"E11", "E12", "E13", "E14", "E15"}
    node_new = [e for e in ch3_events if e.type == "node_new"]
    assert {e.subject_ids[0] for e in node_new} == {"b1", "b2", "b3", "b4", "lonely"}
    assert all(
        set(e.because_edge_ids) <= new_edge_ids
        for e in ch3_events
        if e.subject_ids and e.subject_ids[0] in {"H", "b1"}
    )
    assert any(e.type.startswith("community_") for e in ch3_events)


def test_run_is_deterministic_and_org_id_tracks_config_and_code_version(world):
    a = _run(world)
    b = _run(world)
    assert a.org_id == b.org_id
    assert (a.org_dir / "ch3" / "org_nodes.jsonl").read_text() == (
        b.org_dir / "ch3" / "org_nodes.jsonl"
    ).read_text()
    raw = load_config().model_dump()
    raw["rings"]["shares"] = {"centre": 0.1, "inner": 0.1, "middle": 0.3, "outer": 0.5}
    cfg2 = OrgConfig(**raw)
    assert make_org_id(RUN, "provisional", cfg2, "test") != a.org_id
    assert make_org_id(RUN, "provisional", cfg_fast(), "other") != a.org_id


def test_through_chapter_and_principle_mode_guard(world):
    org = _run(world, through_chapter=2)
    assert [c.chapter for c in org.chapters] == [2]
    with pytest.raises(NotImplementedError, match="STOP C"):
        _run(world, mode="principles")


def test_principle_activation_is_time_aware():
    edges = [
        InstantiatesEdge("I1", "c1", "P1", "s2"),
        InstantiatesEdge("I2", "c2", "P1", "s3"),
        InstantiatesEdge("I3", "c3", "P2", "s2"),
    ]
    first = {"c1": 2, "c2": 2, "c3": 3}
    sec_ch = {"s2": 2, "s3": 3}
    act = activation_chapters(edges, first, sec_ch)
    assert act == {"I1": 2, "I2": 3, "I3": 3}  # max(concept's first chapter, evidence chapter)
    assert principles_present(edges, act, 2) == {"P1": ["I1"]}  # P2 not yet active
    assert principles_present(edges, act, 3) == {"P1": ["I1", "I2"], "P2": ["I3"]}

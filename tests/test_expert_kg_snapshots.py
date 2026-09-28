"""CR-005 §6 required tests: "Snapshot writer/loader round-trip; the growth metrics
give known values on a 2-chapter fixture (including a cross-chapter edge, a merge
and a forward reference)."
"""

from __future__ import annotations

from cumap.expert_kg.snapshots import (
    ChapterSnapshot,
    SnapshotEdge,
    SnapshotMerge,
    SnapshotNode,
    compute_growth_metrics,
    load_snapshot,
    write_snapshot,
)


def test_snapshot_writer_loader_round_trip(tmp_path):
    snapshot = ChapterSnapshot(
        run_id="run_abc123",
        chapter_num=1,
        nodes=[
            SnapshotNode(
                concept_id="c_tcp",
                canonical_name="TCP",
                node_type="Protocol",
                first_introduced_chapter=1,
                aliases=["Transmission Control Protocol"],
                mention_section_count=3,
            ),
        ],
        edges=[
            SnapshotEdge(
                edge_id="E1",
                source_concept_id="c_tcp",
                relation="uses",
                target_concept_id="c_cwnd",
                family="function_means",
                source_chapter=1,
                target_chapter=1,
                section_id="ch1_s1",
            ),
        ],
        merges=[SnapshotMerge(concept_id="c_cwnd", alias="cwnd", section_id="ch1_s1")],
        rejected=[{"section_id": "ch1_s1", "reason": "evidence_quote not found"}],
        prerequisite_candidate_count=2,
        forward_reference_count=1,
    )

    snapshots_dir = tmp_path / "snapshots"
    ch_dir = write_snapshot(snapshot, snapshots_dir)
    assert ch_dir == snapshots_dir / "ch1"
    assert (ch_dir / "nodes.jsonl").exists()
    assert (ch_dir / "edges.jsonl").exists()
    assert (ch_dir / "merges.jsonl").exists()
    assert (ch_dir / "rejected.jsonl").exists()
    assert (ch_dir / "manifest.json").exists()

    loaded = load_snapshot(snapshots_dir, chapter_num=1)
    assert loaded.run_id == "run_abc123"
    assert loaded.chapter_num == 1
    assert loaded.nodes == snapshot.nodes
    assert loaded.edges == snapshot.edges
    assert loaded.merges == snapshot.merges
    assert loaded.rejected == snapshot.rejected
    assert loaded.prerequisite_candidate_count == 2
    assert loaded.forward_reference_count == 1


def _two_chapter_fixture() -> list[ChapterSnapshot]:
    """Chapter 1 introduces TCP and congestion window, with an edge between them and
    one merge (cwnd -> congestion window) and one forward reference (slow start used
    in ch1 before it's defined in ch2). Chapter 2 introduces slow start and reuses
    congestion window, with one cross-chapter edge (slow_start -> congestion_window,
    endpoints introduced in different chapters).
    """
    ch1 = ChapterSnapshot(
        run_id="run_x",
        chapter_num=1,
        nodes=[
            SnapshotNode("c_tcp", "TCP", "Protocol", first_introduced_chapter=1),
            SnapshotNode("c_cwnd", "congestion window", "Mechanism", first_introduced_chapter=1),
        ],
        edges=[
            SnapshotEdge(
                "E1",
                "c_tcp",
                "uses",
                "c_cwnd",
                "function_means",
                source_chapter=1,
                target_chapter=1,
                section_id="ch1_s1",
            ),
        ],
        merges=[SnapshotMerge("c_cwnd", "cwnd", "ch1_s1")],
        rejected=[],
        prerequisite_candidate_count=0,
        forward_reference_count=1,  # slow start used in ch1, defined in ch2
    )
    ch2 = ChapterSnapshot(
        run_id="run_x",
        chapter_num=2,
        nodes=[
            SnapshotNode("c_slow_start", "slow start", "Mechanism", first_introduced_chapter=2),
            SnapshotNode(
                "c_cwnd", "congestion window", "Mechanism", first_introduced_chapter=1
            ),  # reused
        ],
        edges=[
            SnapshotEdge(
                "E2",
                "c_slow_start",
                "increases",
                "c_cwnd",
                "cause_effect",
                source_chapter=2,
                target_chapter=1,
                section_id="ch2_s1",  # cross-chapter
            ),
        ],
        merges=[],
        rejected=[],
        prerequisite_candidate_count=1,  # cwnd defined ch1, used ch2
        forward_reference_count=0,
    )
    return [ch1, ch2]


def test_growth_metrics_known_values_on_two_chapter_fixture():
    metrics = compute_growth_metrics(_two_chapter_fixture())
    assert [m.chapter_num for m in metrics] == [1, 2]
    m1, m2 = metrics

    assert m1.concepts_total == 2
    assert m1.concepts_new == 2
    assert m1.concepts_reused == 0
    assert m1.merges == 1
    assert m1.edges_total == 1
    assert m1.edges_new == 1
    assert m1.cross_chapter_edges == 0
    assert m1.forward_references == 1
    assert m1.prerequisite_candidates == 0

    assert m2.concepts_total == 3  # tcp, cwnd, slow_start
    assert m2.concepts_new == 1  # slow_start
    assert m2.concepts_reused == 1  # cwnd, seen again
    assert m2.merges == 0
    assert m2.edges_total == 2
    assert m2.edges_new == 1
    assert m2.cross_chapter_edges == 1  # slow_start (ch2) -> cwnd (ch1)
    assert m2.forward_references == 0
    assert m2.prerequisite_candidates == 1
    assert m2.family_share == {"cause_effect": 1.0}

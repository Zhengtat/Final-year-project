"""Derived graph layers for the report: transitive inference and conflict flags (no evidence, $0)."""

from __future__ import annotations

from pathlib import Path

from cumap.report.derived import conflicting_edge_ids, inferred_edges
from cumap.report.graph import GEdge
from cumap.schemas.relations import RelationRegistry

REG = RelationRegistry.from_yaml(
    Path(__file__).resolve().parents[1] / "configs" / "relations_v1.1.yaml"
)


def e(i, s, rel, t, **kw):
    return GEdge(id=i, source=s, target=t, relation=rel, family=REG.family_of(rel), **kw)


def test_transitive_inference_is_one_hop_and_skips_existing_and_negated():
    edges = [
        e("1", "a", "is_a", "b"),
        e("2", "b", "is_a", "c"),
        e("3", "c", "is_a", "d"),
        e("4", "a", "is_a", "c"),  # already stated: not inferred
        e("5", "x", "is_a", "y", negated=True),
        e("6", "y", "is_a", "z"),
        e("7", "p", "uses", "q"),  # not transitive
        e("8", "q", "uses", "r"),
    ]
    got = {(d["source"], d["target"]) for d in inferred_edges(edges, REG)}
    assert got == {
        ("b", "d"),
        ("a", "d"),
    }  # a->c is stated so skipped; a->c->d (via the stated edge) infers a->d


def test_conflicting_relations_on_the_same_pair_are_flagged():
    edges = [e("1", "a", "increases", "b"), e("2", "b", "decreases", "a"), e("3", "a", "uses", "c")]
    assert conflicting_edge_ids(edges, REG) == {"1", "2"}

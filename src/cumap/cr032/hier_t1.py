"""CR-032 broader Hierarchy F1, variant `HIER-T1` ($0, scorer only, no model call).

For each relation of the hierarchy set SEPARATELY, the gold edges and the predicted edges are expanded into (concept, ancestor) pairs by transitive
closure (`cr017.hierarchy.ancestor_closure`, unchanged). Pairs of all relations are pooled, keyed (relation, concept, ancestor); P / R / F1 over the two
sets. Chains never mix relations; a relation the registry marks `within_same_part_type` chains only inside one part type, and an edge of such a
relation WITHOUT a part type is scored as a direct edge only (owner, 2026-10-23). Everything else is inherited from the frozen scorer: set semantics,
wrong concept = wrong pair, synthetic ids for unmapped / false-merged nodes, missing concepts lose their pairs, cycles reported, self pairs dropped
and counted. With the hierarchy set {is_a} the result equals the frozen CR-017 number exactly (tested)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from cumap.config import REPO_ROOT
from cumap.cr012 import scoring as S
from cumap.cr012.types import PRF, PredEdge, PredNode, UnitGold
from cumap.cr017.hierarchy import ancestor_closure

CFG_PATH = REPO_ROOT / "configs/hierarchy_eval.yaml"
Edge = tuple[str, str | None, str, str]  # (relation, part_type, child, parent)


def load_config(path: Path = CFG_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def hierarchy_relations(registry, cfg: dict | None = None) -> tuple[frozenset[str], frozenset[str]]:
    """(hierarchy relation names, the subset that chains only within a part type), derived from the registry: relations of the configured family whose
    `transitive` is one of the configured values."""
    cfg = (cfg or load_config())["hierarchy_relations"]
    rels = [
        r
        for r in registry.all_relations()
        if r.family == cfg["family"] and r.transitive in cfg["transitive"]
    ]
    return (
        frozenset(r.name for r in rels),
        frozenset(r.name for r in rels if r.transitive == "within_same_part_type"),
    )


@dataclass
class Closure:
    pairs: set[tuple[str, str, str]] = field(default_factory=set)  # (relation, concept, ancestor)
    direct: set[tuple[str, str, str]] = field(default_factory=set)
    cycles: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)
    self_pairs_dropped: int = 0
    direct_only_edges: int = 0  # typed-relation edges without a part type (never chained)


def closure(edges: set[Edge], typed: frozenset[str]) -> Closure:
    """Per-relation (and, for `typed` relations, per-part-type) transitive closure."""
    out = Closure()
    groups: dict[tuple[str, str | None], set[tuple[str, str]]] = defaultdict(set)
    for rel, pt, a, b in edges:
        if rel in typed and not pt:  # no part type: a direct edge only
            if a == b:
                out.self_pairs_dropped += 1
            else:
                out.pairs.add((rel, a, b))
                out.direct.add((rel, a, b))
                out.direct_only_edges += 1
            continue
        groups[(rel, pt if rel in typed else None)].add((a, b))
    for (rel, _pt), es in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        c = ancestor_closure(es)
        out.pairs |= {(rel, a, b) for a, b in c.pairs}
        out.direct |= {(rel, a, b) for a, b in c.direct_edges}
        out.cycles += [(rel, cyc) for cyc in c.cycles]
        out.self_pairs_dropped += c.self_pairs_dropped
    return out


def score_edges(
    gold_edges: set[Edge], pred_edges: set[Edge], typed: frozenset[str], *, extra_fp: int = 0
) -> dict:
    """`extra_fp`: predicted edges that could not be placed (rule 35: false positives, never silently dropped)."""
    g, p = closure(gold_edges, typed), closure(pred_edges, typed)
    pp = set(p.pairs) | {
        ("unplaced", f"unplaced:{i}", f"unplaced:{i}:parent") for i in range(extra_fp)
    }
    prf = PRF(len(g.pairs & pp), len(pp - g.pairs), len(g.pairs - pp))
    direct = PRF(len(g.direct & p.direct), len(p.direct - g.direct), len(g.direct - p.direct))
    per_rel = {}
    for rel in sorted({x[0] for x in g.pairs | p.pairs}):
        gr = {x for x in g.pairs if x[0] == rel}
        pr = {x for x in p.pairs if x[0] == rel}
        per_rel[rel] = PRF(len(gr & pr), len(pr - gr), len(gr - pr))
    return {
        "prf": prf,
        "direct": direct,
        "per_relation": per_rel,
        "gold_pairs": len(g.pairs),
        "gold_direct_edges": len(g.direct),
        "pred_pairs": len(pp),
        "pred_direct_edges": len(p.direct),
        "gold_cycles": [[r, list(c)] for r, c in g.cycles],
        "pred_cycles": [[r, list(c)] for r, c in p.cycles],
        "self_pairs_dropped": {"gold": g.self_pairs_dropped, "predicted": p.self_pairs_dropped},
        "direct_only_edges": {"gold": g.direct_only_edges, "predicted": p.direct_only_edges},
        "unplaced_counted_as_fp": extra_fp,
    }


def pool(units: dict[str, dict], key: str = "prf") -> PRF:
    return PRF(
        sum(u[key].tp for u in units.values()),
        sum(u[key].fp for u in units.values()),
        sum(u[key].fn for u in units.values()),
    )


def pool_per_relation(units: dict[str, dict]) -> dict[str, PRF]:
    rels = sorted({r for u in units.values() for r in u["per_relation"]})
    return {
        r: PRF(
            sum(u["per_relation"][r].tp for u in units.values() if r in u["per_relation"]),
            sum(u["per_relation"][r].fp for u in units.values() if r in u["per_relation"]),
            sum(u["per_relation"][r].fn for u in units.values() if r in u["per_relation"]),
        )
        for r in rels
    }


# ---------------------------------------------------------------- P&D (concept-level gold, frozen CR-012 alignment)
def edge_part_types(cp: dict, section_id: str) -> dict[tuple[str, str, str], str]:
    """(src, tgt, relation) -> part_type of the production edge (same filters as `production_graph.graph_for_sections`)."""
    out: dict[tuple[str, str, str], str] = {}
    for r in cp["relation_results_v3"]:
        if (
            r["outcome"] != "edge"
            or r.get("group", "selected") != "selected"
            or r.get("gated_dropped")
            or r.get("consolidated_into")
            or r["pair"]["section_id"] != section_id
        ):
            continue
        x, y = r["pair"]["concept_x_id"], r["pair"]["concept_y_id"]
        src, tgt = (y, x) if r["direction"] == "reversed" else (x, y)
        pt = (r.get("qualifiers") or {}).get("part_type")
        if pt:
            out.setdefault((src, tgt, r["relation"]), pt)
    return out


def pd_unit(
    gold: UnitGold,
    nodes: list[PredNode],
    edges: list[PredEdge],
    rels: frozenset[str],
    typed: frozenset[str],
    pred_part_types: dict[tuple[str, str, str], str] | None = None,
) -> dict:
    """One P&D section: gold and predicted edges of the hierarchy set -> `score_edges`. Mapping of predicted nodes to gold concepts is the frozen
    CR-012 mention-span alignment (wrong concept = wrong pair; unmapped / false-merged nodes keep synthetic ids)."""
    n2c = S.align_nodes(nodes, gold.mentions)["node_to_concept"]

    def ident(node_id: str) -> str:
        return n2c.get(node_id, f"pred:{node_id}")

    gold_edges = {
        (r.relation, dict(r.qualifiers).get("part_type"), r.src_concept, r.tgt_concept)
        for r in gold.relations
        if r.relation in rels and r.src_concept and r.tgt_concept
    }
    pts = pred_part_types or {}
    pred_edges = {
        (
            e.relation,
            pts.get((e.src, e.tgt, e.relation)) or dict(e.qualifiers).get("part_type"),
            ident(e.src),
            ident(e.tgt),
        )
        for e in edges
        if e.relation in rels
    }
    return score_edges(gold_edges, pred_edges, typed)
